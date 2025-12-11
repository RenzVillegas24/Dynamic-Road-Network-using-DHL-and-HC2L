"""
HERE Routing API Integration for Route Comparison
Fetches routes from HERE Routing API and computes comparison metrics
"""

import os
import requests
from typing import Dict, List, Optional, Tuple, Iterator
from collections import namedtuple
from config import Config
from console_formatter import get_logger

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


class HereRoutingService:
    """Service for fetching routes from HERE Routing API"""
    
    def __init__(self):
        self.api_key = Config.HERE_API_KEY
        if not self.api_key:
            logger.warning("HERE API key not set")
        self.base_url = "https://router.hereapi.com/v8/routes"
    
    def get_directions(self, start_lat: float, start_lng: float, 
                       dest_lat: float, dest_lng: float,
                       traffic_mode: str = 'enabled') -> Optional[Dict]:
        """
        Fetch directions from HERE Routing API v8
        
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
        
        params = {
            'origin': f"{start_lat},{start_lng}",
            'destination': f"{dest_lat},{dest_lng}",
            'transportMode': 'car',
            'return': 'polyline,summary,travelSummary',
            'traffic': traffic_mode,
            'apiKey': self.api_key
        }
        
        try:
            logger.network("Fetching HERE Routing route...")
            logger.info(f"Origin: ({start_lat}, {start_lng})")
            logger.info(f"Destination: ({dest_lat}, {dest_lng})")
            
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for errors
            if 'routes' not in data or len(data['routes']) == 0:
                error_msg = data.get('title', 'No routes found')
                logger.error(f"HERE Routing API error: {error_msg}")
                return {
                    'success': False,
                    'error': f"HERE Routing API: {error_msg}"
                }
            
            # Extract route information
            route = data['routes'][0]
            sections = route.get('sections', [])
            
            if not sections:
                return {
                    'success': False,
                    'error': 'HERE Routing returned no route sections'
                }
            
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
                return {
                    'success': False,
                    'error': 'Failed to decode route coordinates'
                }
            
            result = {
                'success': True,
                'coordinates': all_coordinates,
                'distance_meters': total_distance,
                'duration_seconds': total_duration,
                'point_count': len(all_coordinates),
                'sections': len(sections),
                'traffic_mode': traffic_mode
            }
            
            logger.success("HERE route fetched successfully")
            logger.info(f"Distance: {total_distance / 1000:.2f} km")
            logger.info(f"Duration: {total_duration / 60:.1f} min")
            logger.info(f"Coordinates: {len(all_coordinates)} points")
            
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
