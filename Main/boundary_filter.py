"""
Boundary Filtering Utility

This module provides global boundary filtering functionality for Quezon City.
It filters out points and edges that are near the boundary to avoid issues with
incomplete road networks at the edges.
"""
import os
import pickle
from pathlib import Path
from typing import Optional, Tuple
from console_formatter import get_logger

logger = get_logger("BoundaryFilter")

try:
    import geopandas as gpd
    import osmnx as ox
    from shapely.geometry import Point, LineString
except ImportError as e:
    logger.error(f"Missing required package: {e}")
    logger.info("Please install: pip install osmnx geopandas shapely")
    raise


# Configuration
PLACE_NAME = "Quezon City, Philippines"
BOUNDARY_BUFFER_METERS = 15  # Exclude points within this distance from boundary (inward)
CACHE_DIR = Path(__file__).parent / "cache"
BOUNDARY_CACHE_FILE = CACHE_DIR / "quezon_city_boundary.pkl"


class BoundaryFilter:
    """
    Global boundary filter for Quezon City.
    
    This class loads and caches the Quezon City boundary polygon,
    then provides methods to check if points are within the valid area
    (i.e., NOT in the boundary exclusion zone).
    """
    
    def __init__(self, buffer_meters: float = BOUNDARY_BUFFER_METERS):
        """
        Initialize the boundary filter.
        
        Args:
            buffer_meters: Distance in meters to buffer inward from boundary
        """
        self.buffer_meters = buffer_meters
        self.boundary_polygon = None
        self.inner_polygon = None
        self._load_boundary()
    
    def _load_boundary(self):
        """Load or fetch the boundary polygon."""
        # Try to load from cache first
        if BOUNDARY_CACHE_FILE.exists():
            try:
                logger.info(f"Loading cached boundary from {BOUNDARY_CACHE_FILE}")
                with open(BOUNDARY_CACHE_FILE, 'rb') as f:
                    cache_data = pickle.load(f)
                    self.boundary_polygon = cache_data['boundary']
                    self.inner_polygon = cache_data['inner']
                    logger.success(f"Loaded cached boundary (buffer: {self.buffer_meters}m)")
                    return
            except Exception as e:
                logger.warning(f"Failed to load cached boundary: {e}")
        
        # Fetch from OSM if not cached
        logger.info(f"Fetching boundary for {PLACE_NAME} from OpenStreetMap...")
        try:
            # Get the boundary polygon from OSM
            gdf = ox.geocode_to_gdf(PLACE_NAME)
            self.boundary_polygon = gdf.geometry.iloc[0]
            
            logger.success(f"Retrieved boundary polygon ({self.boundary_polygon.geom_type})")
            
            # Create inner boundary by buffering inward
            self._create_inner_boundary()
            
            # Cache the boundaries
            self._cache_boundary()
            
        except Exception as e:
            logger.error(f"Failed to fetch boundary: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _create_inner_boundary(self):
        """Create inner boundary by buffering inward."""
        logger.processing(f"Creating inner boundary (buffer: {self.buffer_meters}m inward)...")
        
        # Work in projected CRS for meter-based operations
        graph_crs = "EPSG:4326"
        projected_crs = "EPSG:32651"  # UTM Zone 51N for Philippines
        
        # Create GeoDataFrame and project
        boundary_gdf = gpd.GeoDataFrame([1], geometry=[self.boundary_polygon], crs=graph_crs)
        boundary_projected = boundary_gdf.to_crs(projected_crs)
        
        # Create inner buffer (negative buffer = shrink inward)
        inner_boundary = boundary_projected.buffer(-self.buffer_meters)
        
        # Convert back to geographic coordinates
        inner_boundary_geo = inner_boundary.to_crs(graph_crs)
        self.inner_polygon = inner_boundary_geo.geometry.iloc[0]
        
        logger.success(f"Created inner boundary")
        logger.data(f"   Original area: {self.boundary_polygon.area:.6f} deg²")
        logger.data(f"   Inner area: {self.inner_polygon.area:.6f} deg²")
    
    def _cache_boundary(self):
        """Cache the boundary polygons to disk."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_data = {
                'boundary': self.boundary_polygon,
                'inner': self.inner_polygon,
                'buffer_meters': self.buffer_meters,
                'place_name': PLACE_NAME
            }
            with open(BOUNDARY_CACHE_FILE, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.success(f"Cached boundary to {BOUNDARY_CACHE_FILE}")
        except Exception as e:
            logger.warning(f"Failed to cache boundary: {e}")
    
    def is_point_valid(self, lat: float, lng: float) -> bool:
        """
        Check if a point is within the valid area (NOT in exclusion zone).
        
        Args:
            lat: Latitude
            lng: Longitude
        
        Returns:
            True if point is valid (inside inner boundary), False otherwise
        """
        if self.inner_polygon is None:
            logger.warning("Inner polygon not loaded, accepting all points")
            return True
        
        point = Point(lng, lat)  # Shapely uses (lon, lat) order
        return self.inner_polygon.contains(point)
    
    def is_line_valid(self, lat1: float, lng1: float, lat2: float, lng2: float) -> bool:
        """
        Check if a line segment is fully within the valid area.
        
        Args:
            lat1, lng1: Start point coordinates
            lat2, lng2: End point coordinates
        
        Returns:
            True if line is fully valid (inside inner boundary), False otherwise
        """
        if self.inner_polygon is None:
            logger.warning("Inner polygon not loaded, accepting all lines")
            return True
        
        line = LineString([(lng1, lat1), (lng2, lat2)])  # Shapely uses (lon, lat) order
        return self.inner_polygon.contains(line)
    
    def filter_points(self, points: list) -> list:
        """
        Filter a list of (lat, lng) tuples to only valid points.
        
        Args:
            points: List of (lat, lng) tuples
        
        Returns:
            Filtered list of valid points
        """
        return [p for p in points if self.is_point_valid(p[0], p[1])]
    
    def get_boundary_info(self) -> dict:
        """Get information about the boundary."""
        return {
            'place_name': PLACE_NAME,
            'buffer_meters': self.buffer_meters,
            'boundary_type': self.boundary_polygon.geom_type if self.boundary_polygon else None,
            'boundary_area_deg2': self.boundary_polygon.area if self.boundary_polygon else None,
            'inner_area_deg2': self.inner_polygon.area if self.inner_polygon else None,
            'cached': BOUNDARY_CACHE_FILE.exists()
        }


# Global instance (singleton pattern)
_boundary_filter_instance: Optional[BoundaryFilter] = None


def get_boundary_filter() -> BoundaryFilter:
    """
    Get the global boundary filter instance (singleton).
    
    Returns:
        BoundaryFilter instance
    """
    global _boundary_filter_instance
    if _boundary_filter_instance is None:
        _boundary_filter_instance = BoundaryFilter()
    return _boundary_filter_instance


def is_point_in_valid_area(lat: float, lng: float) -> bool:
    """
    Check if a point is in the valid area (NOT near boundary).
    
    This is a convenience function that uses the global boundary filter.
    
    Args:
        lat: Latitude
        lng: Longitude
    
    Returns:
        True if point is valid, False if in exclusion zone
    """
    return get_boundary_filter().is_point_valid(lat, lng)


def is_line_in_valid_area(lat1: float, lng1: float, lat2: float, lng2: float) -> bool:
    """
    Check if a line is fully in the valid area (NOT near boundary).
    
    This is a convenience function that uses the global boundary filter.
    
    Args:
        lat1, lng1: Start point coordinates
        lat2, lng2: End point coordinates
    
    Returns:
        True if line is valid, False if in exclusion zone
    """
    return get_boundary_filter().is_line_valid(lat1, lng1, lat2, lng2)


# Backward compatibility function (replaces old excluded_bbox logic)
def is_in_excluded_area(lat: float, lng: float) -> bool:
    """
    Check if a point is in the excluded area (near boundary).
    
    This is the inverse of is_point_in_valid_area() for backward compatibility.
    
    Args:
        lat: Latitude
        lng: Longitude
    
    Returns:
        True if point is in exclusion zone, False if valid
    """
    return not is_point_in_valid_area(lat, lng)
