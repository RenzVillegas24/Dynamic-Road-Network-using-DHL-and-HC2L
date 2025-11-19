"""
Performance Optimization - Caching and Batching Module
========================================================

Provides efficient caching for frequently accessed data:
- OSM edges with geometry
- Traffic data with geometry
- Disruption lookups
- Path computation results

Reduces redundant file I/O and accelerates disruption updates and route recalculation.
"""

import time
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from threading import Lock
import pandas as pd


class CacheEntry:
    """Single cache entry with TTL support"""
    
    def __init__(self, data: Any, ttl: float = None):
        self.data = data
        self.created_at = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl is None:
            return False
        return (time.time() - self.created_at) > self.ttl
    
    def get(self) -> Any:
        """Get data if not expired"""
        if self.is_expired():
            return None
        return self.data


class SmartCache:
    """Thread-safe cache with TTL and file-based invalidation"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            entry = self.cache.get(key)
            if entry is None:
                return None
            value = entry.get()
            if value is None:
                del self.cache[key]
            return value
    
    def set(self, key: str, value: Any, ttl: float = None):
        """Set value in cache"""
        with self._lock:
            # Simple LRU: if cache is full, clear oldest entries
            if len(self.cache) >= self.max_size:
                # Remove oldest 10% of entries
                num_to_remove = max(1, self.max_size // 10)
                oldest_keys = sorted(
                    self.cache.items(),
                    key=lambda x: x[1].created_at
                )[:num_to_remove]
                for k, _ in oldest_keys:
                    del self.cache[k]
            
            self.cache[key] = CacheEntry(value, ttl)
    
    def clear(self):
        """Clear all cache"""
        with self._lock:
            self.cache.clear()
    
    def invalidate(self, pattern: str = None):
        """Invalidate entries matching pattern"""
        with self._lock:
            if pattern is None:
                self.cache.clear()
            else:
                keys_to_remove = [k for k in self.cache.keys() if pattern in k]
                for k in keys_to_remove:
                    del self.cache[k]
    
    def size(self) -> int:
        """Get current cache size"""
        with self._lock:
            return len(self.cache)


class FileHashCache:
    """Cache based on file modification times"""
    
    def __init__(self):
        self.file_hashes: Dict[str, Tuple[str, float]] = {}  # {filepath: (hash, mtime)}
        self._lock = Lock()
    
    def file_changed(self, filepath: Path) -> bool:
        """Check if file has changed since last check"""
        filepath = Path(filepath)
        
        try:
            current_mtime = filepath.stat().st_mtime
        except FileNotFoundError:
            return True
        
        with self._lock:
            if filepath not in self.file_hashes:
                self.file_hashes[filepath] = ("", current_mtime)
                return True
            
            _, cached_mtime = self.file_hashes[filepath]
            if current_mtime != cached_mtime:
                self.file_hashes[filepath] = ("", current_mtime)
                return True
            
            return False
    
    def update_hash(self, filepath: Path, hash_value: str):
        """Update cached hash"""
        with self._lock:
            current_mtime = filepath.stat().st_mtime
            self.file_hashes[filepath] = (hash_value, current_mtime)


class PerformanceOptimizer:
    """Central performance optimization manager"""
    
    def __init__(self):
        self.edge_cache = SmartCache(max_size=10)  # Cache edge dataframes
        self.traffic_cache = SmartCache(max_size=5)  # Cache traffic segments
        self.lookup_cache = SmartCache(max_size=50)  # Cache lookups
        self.file_hash_cache = FileHashCache()
    
    def cache_edges(self, edges_key: str, edges_df: pd.DataFrame, ttl: float = 3600):
        """Cache edges dataframe"""
        self.edge_cache.set(edges_key, edges_df, ttl)
    
    def get_cached_edges(self, edges_key: str) -> Optional[pd.DataFrame]:
        """Get cached edges dataframe"""
        return self.edge_cache.get(edges_key)
    
    def cache_traffic(self, traffic_key: str, traffic_data: List[Dict], ttl: float = 300):
        """Cache traffic segments"""
        self.traffic_cache.set(traffic_key, traffic_data, ttl)
    
    def get_cached_traffic(self, traffic_key: str) -> Optional[List[Dict]]:
        """Get cached traffic segments"""
        return self.traffic_cache.get(traffic_key)
    
    def invalidate_traffic(self):
        """Invalidate all traffic caches on disruption update"""
        self.traffic_cache.clear()
        self.lookup_cache.invalidate("traffic")
    
    def batch_lookup(self, lookups: List[Tuple[str, Any]]) -> Dict[str, Any]:
        """Batch multiple lookups"""
        results = {}
        cache_hits = 0
        
        for key, default in lookups:
            value = self.lookup_cache.get(key)
            if value is not None:
                results[key] = value
                cache_hits += 1
            else:
                results[key] = default
        
        return results, cache_hits
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            'edges_cache_size': self.edge_cache.size(),
            'traffic_cache_size': self.traffic_cache.size(),
            'lookup_cache_size': self.lookup_cache.size(),
        }


# Global optimizer instance
_optimizer: Optional[PerformanceOptimizer] = None


def get_optimizer() -> PerformanceOptimizer:
    """Get or create performance optimizer instance"""
    global _optimizer
    if _optimizer is None:
        _optimizer = PerformanceOptimizer()
    return _optimizer


def reset_optimizer():
    """Reset optimizer (clear all caches)"""
    global _optimizer
    _optimizer = PerformanceOptimizer()
