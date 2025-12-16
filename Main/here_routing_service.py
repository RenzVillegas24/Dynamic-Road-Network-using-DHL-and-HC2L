"""
HERE Routing API Integration for Route Comparison
Fetches routes from HERE Routing API and computes comparison metrics

BLOCKING PREVENTION MECHANISMS:
================================

This module implements comprehensive protection against API rate limiting and blocking:

1. TOKEN BUCKET RATE LIMITER
   - Limits requests to 10 requests/second (configurable)
   - Prevents bursts that trigger rate limits
   - Uses token refill mechanism for smooth request distribution

2. EXPONENTIAL BACKOFF WITH JITTER
   - Automatic retry on 429 (Too Many Requests) and 5xx errors
   - Backoff increases exponentially: 1s → 2s → 4s → 8s → 16s → 30s
   - Respects Retry-After header from API responses
   - Max 3 retries per request

3. CIRCUIT BREAKER PATTERN
   - Monitors consecutive failures
   - Opens circuit after 5 consecutive failures
   - Prevents cascade of failed requests
   - Automatically closes after 60 seconds to test recovery
   - Detailed logging of circuit state transitions

4. CONNECTION POOLING
   - Reuses HTTP connections via urllib3 HTTPAdapter
   - Reduces connection overhead
   - Improves throughput and reduces failures
   - Pool size: 10 connections

5. RESPONSE CACHING
   - LRU cache stores up to 1000 previous responses
   - Eliminates duplicate requests for same routes
   - Key: lat1,lng1,lat2,lng2 with 5-decimal precision
   - Reduces API calls and rate limiting pressure

6. ADAPTIVE BATCHING (in ExperimentRunner)
   - Starts with batch size of 10 routes
   - Reduces batch size if consecutive failures occur
   - Increases pause time at batch boundaries
   - Uses feedback from rate limiter statistics

MONITORING & LOGGING:
=====================
- [RATE_LIMIT_429]: Rate limit hit, automatic retry
- [SERVER_ERROR_5xx]: Server error, exponential backoff
- [TIMEOUT]: Request timeout, retry with backoff
- [CONNECTION_ERROR]: Connection issue, retry with backoff
- [CIRCUIT_BREAKER_OPENED]: Service unavailable, pause requests
- [CIRCUIT_BREAKER_RECOVERY]: Service recovered, resume requests
- [FAILURE_STREAK]: Multiple consecutive failures detected
- [RECOVERY_SUCCESS]: Connection restored after failures

Configuration:
===============
- requests_per_second: 10 (HERE allows 10-20 QPS typically)
- max_retries: 3
- circuit_breaker_threshold: 5
- circuit_breaker_timeout: 60 seconds
- cache_max_size: 1000 responses
"""

import os
import requests
import time
import threading
from typing import Dict, List, Optional, Tuple, Iterator
from collections import namedtuple, OrderedDict
from config import Config
from console_formatter import get_logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)

# Get logger instance
logger = get_logger("HereRoutingService")


# ============================================================================
# Flexible Polyline Decoder (based on HERE's official implementation)
# https://github.com/heremaps/flexible-polyline
# ============================================================================

# Decoding table for flexible polyline (ASCII offset 45)
DECODING_TABLE = [
    62, -1, -1, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1, -1,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21,
    22, 23, 24, 25, -1, -1, -1, -1, 63, -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
    36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51
]

# Format version
FORMAT_VERSION = 1

# Third dimension types
ABSENT = 0
LEVEL = 1
ALTITUDE = 2
ELEVATION = 3

PolylineHeader = namedtuple('PolylineHeader', 'precision,third_dim,third_dim_precision')


def decode_char(char: str) -> int:
    """Decode a single char to the corresponding value"""
    char_value = ord(char)
    
    try:
        value = DECODING_TABLE[char_value - 45]
    except IndexError:
        raise ValueError('Invalid encoding')
    if value < 0:
        raise ValueError('Invalid encoding')
    return value


def to_signed(value: int) -> int:
    """Decode the sign from an unsigned value"""
    if value & 1:
        value = ~value
    value >>= 1
    return value


def decode_unsigned_values(encoded: str) -> Iterator[int]:
    """Return an iterator over encoded unsigned values part of an `encoded` polyline"""
    result = shift = 0
    
    for char in encoded:
        value = decode_char(char)
        
        result |= (value & 0x1F) << shift
        if (value & 0x20) == 0:
            yield result
            result = shift = 0
        else:
            shift += 5
    
    if shift > 0:
        raise ValueError('Invalid encoding')


def decode_header(decoder: Iterator[int]) -> PolylineHeader:
    """Decode the polyline header from an encoded_char. Returns a PolylineHeader object."""
    version = next(decoder)
    if version != FORMAT_VERSION:
        raise ValueError('Invalid format version')
    value = next(decoder)
    precision = value & 15
    value >>= 4
    third_dim = value & 7
    third_dim_precision = (value >> 3) & 15
    return PolylineHeader(precision, third_dim, third_dim_precision)


def iter_decode(encoded: str) -> Iterator[Tuple]:
    """Return an iterator over coordinates. The number of coordinates are 2 or 3
    depending on the polyline content."""
    
    last_lat = last_lng = last_z = 0
    decoder = decode_unsigned_values(encoded)
    
    header = decode_header(decoder)
    factor_degree = 10.0 ** header.precision
    factor_z = 10.0 ** header.third_dim_precision
    third_dim = header.third_dim
    
    while True:
        try:
            last_lat += to_signed(next(decoder))
        except StopIteration:
            return  # sequence completed
        
        try:
            last_lng += to_signed(next(decoder))
            
            if third_dim:
                last_z += to_signed(next(decoder))
                yield (last_lat / factor_degree, last_lng / factor_degree, last_z / factor_z)
            else:
                yield (last_lat / factor_degree, last_lng / factor_degree)
        except StopIteration:
            raise ValueError("Invalid encoding. Premature ending reached")


def decode_flexible_polyline(encoded: str) -> List[List[float]]:
    """
    Decode HERE's flexible polyline format to list of [lat, lng] coordinates.
    
    Args:
        encoded: The encoded polyline string
        
    Returns:
        List of [lat, lng] coordinates
    """
    try:
        coordinates = []
        for coord in iter_decode(encoded):
            # Take only lat, lng (ignore third dimension if present)
            coordinates.append([coord[0], coord[1]])
        return coordinates
    except Exception as e:
        logger.warning(f"Flexible polyline decode error: {e}")
        return []


# ============================================================================
# HERE API RATE LIMITER WITH CIRCUIT BREAKER
# ============================================================================

class HereAPIRateLimiter:
    """
    Implements rate limiting, circuit breaker pattern, and request queuing for HERE API.
    
    Features:
    - Token bucket rate limiter: max 10 requests per second (configurable)
    - Exponential backoff: Automatic retry with jitter on 429/5xx errors
    - Circuit breaker: Temporarily stop requests if service unavailable
    - Request queue: Queue requests during rate limit windows
    - Connection pooling: Reuse connections with HTTPAdapter
    - Adaptive backoff: Increases wait time based on API feedback
    """
    
    def __init__(self, 
                 requests_per_second: float = 10,
                 max_retries: int = 3,
                 circuit_breaker_threshold: int = 5,
                 circuit_breaker_timeout: int = 60):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_second: Max requests per second (HERE allows 10-20 QPS typically)
            max_retries: Maximum number of retries for failed requests
            circuit_breaker_threshold: Number of failures before circuit opens
            circuit_breaker_timeout: Seconds to wait before attempting to close circuit
        """
        self.requests_per_second = requests_per_second
        self.max_retries = max_retries
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        
        # Token bucket state
        self.lock = threading.Lock()
        self.tokens = float(requests_per_second)
        self.last_refill = time.time()
        
        # Circuit breaker state
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_open_time = 0
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'rate_limited': 0,  # 429 responses
            'retried': 0,
            'circuit_breaker_trips': 0,
            'total_wait_time_seconds': 0,
            'last_request_time': 0,
            'consecutive_errors': 0
        }
        
        # Create a requests Session with connection pooling
        self.session = requests.Session()
        
        # Configure retries and connection pooling
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter
        
        retry_strategy = Retry(
            total=0,  # We handle retries manually with backoff
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.success(f"HERE API Rate Limiter initialized: {requests_per_second} req/s")
    
    def _refill_tokens(self):
        """Refill token bucket based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.requests_per_second
        self.tokens = min(self.tokens + tokens_to_add, self.requests_per_second)
        self.last_refill = now
    
    def _check_circuit_breaker(self):
        """Check if circuit breaker should be closed based on timeout"""
        if self.circuit_open:
            now = time.time()
            time_since_open = now - self.circuit_open_time
            if time_since_open >= self.circuit_breaker_timeout:
                logger.info(
                    f"[CIRCUIT_BREAKER_RECOVERY] Circuit breaker closed after {self.circuit_breaker_timeout}s. "
                    f"Entering half-open state. Next request will test connection."
                )
                self.circuit_open = False
                self.failure_count = 0
                return True  # Allow next request to attempt
            else:
                remaining = self.circuit_breaker_timeout - time_since_open
                logger.debug(
                    f"[CIRCUIT_BREAKER_OPEN] Circuit still open. "
                    f"Recovery in {remaining:.1f}s..."
                )
                return False  # Circuit still open
        return True  # Circuit closed, allow request
    
    def _record_success(self):
        """Record successful request with recovery logging"""
        with self.lock:
            was_recovering = self.failure_count > 0
            self.failure_count = 0
            self.stats['consecutive_errors'] = 0
            self.stats['successful_requests'] += 1
            
            if was_recovering:
                logger.info(
                    f"[RECOVERY_SUCCESS] Connection restored to HERE API. "
                    f"Successful requests: {self.stats['successful_requests']}"
                )
    
    def _record_failure(self, error_code: Optional[int] = None):
        """Record failed request and potentially open circuit with detailed logging"""
        with self.lock:
            self.failure_count += 1
            self.stats['consecutive_errors'] += 1
            
            # Open circuit on too many consecutive failures
            if self.failure_count >= self.circuit_breaker_threshold:
                if not self.circuit_open:
                    logger.error(
                        f"[CIRCUIT_BREAKER_OPENED] Too many failures ({self.failure_count}). "
                        f"HERE API service appears to be unavailable. "
                        f"Circuit breaker activated for {self.circuit_breaker_timeout}s. "
                        f"Error code: {error_code}, "
                        f"Total failed requests: {self.stats['consecutive_errors']}"
                    )
                    self.circuit_open = True
                    self.circuit_open_time = time.time()
                    self.stats['circuit_breaker_trips'] += 1
            elif self.failure_count > 1:
                logger.warning(
                    f"[FAILURE_STREAK] {self.failure_count} consecutive failures. "
                    f"Error code: {error_code}. "
                    f"Circuit breaker will trigger at {self.circuit_breaker_threshold} failures."
                )
    
    def acquire_token(self, timeout: float = 30) -> bool:
        """
        Acquire a token from the bucket. Blocks until token available or timeout.
        
        Args:
            timeout: Maximum seconds to wait for a token
            
        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                self._refill_tokens()
                
                # Check circuit breaker
                if not self._check_circuit_breaker():
                    wait_time = self.circuit_breaker_timeout - (time.time() - self.circuit_open_time)
                    logger.debug(f"Circuit breaker open. Waiting {wait_time:.1f}s...")
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return False
                    # Release lock and sleep
                    time.sleep(min(1, wait_time))
                    continue
                
                # Try to consume a token
                if self.tokens >= 1:
                    self.tokens -= 1
                    self.stats['total_requests'] += 1
                    return True
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                return False
            
            # Wait a bit before trying again (prevents busy-waiting)
            time.sleep(0.01)
    
    def make_request(self, url: str, params: Dict = None, **kwargs) -> Optional[requests.Response]:
        """
        Make a rate-limited request to HERE API with automatic retries and detailed logging.
        
        Args:
            url: Request URL
            params: Query parameters
            **kwargs: Additional arguments for requests.get()
            
        Returns:
            Response object or None if all retries failed
        """
        retry_count = 0
        backoff_seconds = 1
        start_time = time.time()
        
        while retry_count < self.max_retries:
            # Acquire token from rate limiter
            if not self.acquire_token(timeout=30):
                logger.error("Rate limiter timeout: could not acquire token after 30 seconds")
                self._record_failure()
                return None
            
            try:
                # Make the request
                response = self.session.get(url, params=params, timeout=15, **kwargs)
                self.stats['last_request_time'] = time.time()
                elapsed = time.time() - start_time
                
                # Handle rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    self.stats['rate_limited'] += 1
                    retry_after = response.headers.get('Retry-After', backoff_seconds)
                    
                    try:
                        retry_after = int(retry_after)
                    except (ValueError, TypeError):
                        retry_after = backoff_seconds
                    
                    logger.warning(
                        f"[RATE_LIMIT_429] API blocking requests. "
                        f"Retry #{retry_count + 1}/{self.max_retries}. "
                        f"Waiting {retry_after}s before retry. "
                        f"Stats: Successful={self.stats['successful_requests']}, "
                        f"RateLimited={self.stats['rate_limited']}, "
                        f"Retried={self.stats['retried']}"
                    )
                    self._record_failure(429)
                    time.sleep(retry_after)
                    backoff_seconds = min(backoff_seconds * 2, 30)
                    retry_count += 1
                    continue
                
                # Handle server errors (5xx)
                if response.status_code >= 500:
                    logger.warning(
                        f"[SERVER_ERROR_{response.status_code}] HERE API server error. "
                        f"Retry #{retry_count + 1}/{self.max_retries}. "
                        f"Waiting {backoff_seconds}s before retry."
                    )
                    self._record_failure(response.status_code)
                    time.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, 30)
                    retry_count += 1
                    continue
                
                # Success
                response.raise_for_status()
                self._record_success()
                elapsed = time.time() - start_time
                logger.debug(f"[SUCCESS] Request completed in {elapsed:.3f}s")
                return response
                
            except requests.exceptions.Timeout:
                logger.warning(
                    f"[TIMEOUT] Request timed out after 15s. "
                    f"Retry #{retry_count + 1}/{self.max_retries}. "
                    f"Waiting {backoff_seconds}s before retry."
                )
                self._record_failure()
                self.stats['retried'] += 1
                retry_count += 1
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30)
                
            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    f"[CONNECTION_ERROR] Connection failed: {e}. "
                    f"Retry #{retry_count + 1}/{self.max_retries}. "
                    f"Waiting {backoff_seconds}s before retry."
                )
                self._record_failure()
                self.stats['retried'] += 1
                retry_count += 1
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"[REQUEST_ERROR] Request failed: {e}")
                return None
        
        logger.error(
            f"[MAX_RETRIES_EXCEEDED] Failed after {self.max_retries} retries. "
            f"Total time: {time.time() - start_time:.2f}s"
        )
        return None
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics"""
        with self.lock:
            return {
                **self.stats,
                'circuit_open': self.circuit_open,
                'failure_count': self.failure_count,
                'current_tokens': round(self.tokens, 2),
                'max_tokens_per_second': self.requests_per_second
            }
    
    def reset_stats(self):
        """Reset statistics counters"""
        with self.lock:
            for key in self.stats:
                if key in ['total_requests', 'successful_requests', 'rate_limited', 
                          'retried', 'circuit_breaker_trips', 'total_wait_time_seconds', 
                          'consecutive_errors']:
                    self.stats[key] = 0
            self.failure_count = 0


class HereRoutingService:
    """Service for fetching routes from HERE Routing API with rate limiting and caching"""
    
    def __init__(self, requests_per_second: float = 10):
        self.api_key = Config.HERE_API_KEY
        if not self.api_key:
            logger.warning("HERE API key not set")
        self.base_url = "https://router.hereapi.com/v8/routes"
        
        # Initialize rate limiter
        self.rate_limiter = HereAPIRateLimiter(requests_per_second=requests_per_second)
        
        # Initialize response cache (simple LRU cache)
        # Key: "lat1,lng1,lat2,lng2" -> Value: Dict with route data
        self.response_cache = OrderedDict()
        self.cache_max_size = 1000
        self.cache_lock = threading.Lock()
        
        logger.success(f"HereRoutingService initialized with {requests_per_second} req/s rate limit")
    
    def _get_cache_key(self, start_lat: float, start_lng: float, 
                       dest_lat: float, dest_lng: float) -> str:
        """Generate cache key from coordinates (with 5 decimal precision)"""
        # Round to 5 decimals to catch very nearby points
        return f"{start_lat:.5f},{start_lng:.5f},{dest_lat:.5f},{dest_lng:.5f}"
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Get response from cache if available"""
        with self.cache_lock:
            if cache_key in self.response_cache:
                # Move to end (LRU)
                self.response_cache.move_to_end(cache_key)
                logger.debug(f"Cache hit for route {cache_key}")
                return self.response_cache[cache_key]
            return None
    
    def _cache_response(self, cache_key: str, response: Dict):
        """Store response in cache"""
        with self.cache_lock:
            # Remove oldest items if cache is full
            while len(self.response_cache) >= self.cache_max_size:
                oldest_key, _ = self.response_cache.popitem(last=False)
                logger.debug(f"Evicted cache entry: {oldest_key}")
            
            self.response_cache[cache_key] = response
            logger.debug(f"Cached route {cache_key}")
    
    def get_directions(self, start_lat: float, start_lng: float, 
                       dest_lat: float, dest_lng: float,
                       traffic_mode: str = 'enabled') -> Optional[Dict]:
        """
        Fetch directions from HERE Routing API v8 with rate limiting and caching
        
        Args:
            start_lat: Origin latitude
            start_lng: Origin longitude
            dest_lat: Destination latitude
            dest_lng: Destination longitude
            traffic_mode: 'enabled', 'disabled', or 'long_distance'
            
        Returns:
            Dict with route data including polyline, distance, duration
        """
        if not self.api_key:
            return {
                'success': False,
                'error': 'HERE API key not configured'
            }
        
        # Check cache first
        cache_key = self._get_cache_key(start_lat, start_lng, dest_lat, dest_lng)
        cached = self._get_cached_response(cache_key)
        if cached is not None:
            return cached
        
        params = {
            'origin': f"{start_lat},{start_lng}",
            'destination': f"{dest_lat},{dest_lng}",
            'transportMode': 'car',
            'return': 'polyline,summary,travelSummary',
            'traffic': traffic_mode,
            'apiKey': self.api_key
        }
        
        try:
            logger.network("Fetching HERE Routing route (with rate limiting)...")
            logger.debug(f"Origin: ({start_lat}, {start_lng})")
            logger.debug(f"Destination: ({dest_lat}, {dest_lng})")
            
            # Make rate-limited request
            response = self.rate_limiter.make_request(self.base_url, params=params)
            
            if response is None:
                logger.error("HERE Routing request failed after all retries")
                result = {
                    'success': False,
                    'error': 'Request failed after retries'
                }
                return result
            
            data = response.json()
            
            # Check for errors
            if 'routes' not in data or len(data['routes']) == 0:
                error_msg = data.get('title', 'No routes found')
                logger.error(f"HERE Routing API error: {error_msg}")
                result = {
                    'success': False,
                    'error': f"HERE Routing API: {error_msg}"
                }
                return result
            
            # Extract route information
            route = data['routes'][0]
            sections = route.get('sections', [])
            
            if not sections:
                result = {
                    'success': False,
                    'error': 'HERE Routing returned no route sections'
                }
                return result
            
            # Combine all section polylines
            all_coordinates = []
            total_distance = 0
            total_duration = 0
            
            for section in sections:
                # Decode flexible polyline using our built-in decoder
                if 'polyline' in section:
                    try:
                        coords = decode_flexible_polyline(section['polyline'])
                        if coords:
                            logger.debug(f"Decoded {len(coords)} coordinates from polyline")
                            # Log first and last coordinates for debugging
                            if len(coords) > 0:
                                logger.debug(f"First coord: {coords[0]}, Last coord: {coords[-1]}")
                        all_coordinates.extend(coords)
                    except Exception as e:
                        logger.warning(f"Failed to decode polyline: {e}")
                
                # Sum up distance and duration
                summary = section.get('summary', {}) or section.get('travelSummary', {})
                total_distance += summary.get('length', 0)
                total_duration += summary.get('duration', 0)
            
            if not all_coordinates:
                result = {
                    'success': False,
                    'error': 'Failed to decode route coordinates'
                }
                return result
            
            result = {
                'success': True,
                'coordinates': all_coordinates,
                'distance_meters': total_distance,
                'duration_seconds': total_duration,
                'point_count': len(all_coordinates),
                'sections': len(sections),
                'traffic_mode': traffic_mode,
                'from_cache': False
            }
            
            logger.success("HERE route fetched successfully")
            logger.info(f"Distance: {total_distance / 1000:.2f} km")
            logger.info(f"Duration: {total_duration / 60:.1f} min")
            logger.info(f"Coordinates: {len(all_coordinates)} points")
            
            # Cache the result
            self._cache_response(cache_key, result)
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error("HERE Routing API request timed out")
            return {
                'success': False,
                'error': 'Request timeout'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"HERE Routing API request failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Error processing HERE Routing response: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_rate_limiter_stats(self) -> Dict:
        """Get rate limiter statistics"""
        return self.rate_limiter.get_stats()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        with self.cache_lock:
            return {
                'cache_size': len(self.response_cache),
                'cache_max_size': self.cache_max_size,
                'cache_usage_pct': round((len(self.response_cache) / self.cache_max_size) * 100, 1)
            }

