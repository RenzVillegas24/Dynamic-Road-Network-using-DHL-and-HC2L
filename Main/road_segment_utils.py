"""
Road Segment Geometry Utilities
Provides functions for projecting points onto road segments and finding nearest edges
"""

from math import radians, cos, sin, asin, sqrt
import pandas as pd
from typing import Tuple, Dict, Optional


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate distance between two points on Earth in meters
    
    Args:
        lon1, lat1: First point coordinates
        lon2, lat2: Second point coordinates
    
    Returns:
        Distance in meters
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of Earth in meters
    return c * r


def project_point_to_segment(point: Tuple[float, float], 
                            seg_start: Tuple[float, float], 
                            seg_end: Tuple[float, float]) -> Tuple[Tuple[float, float], float]:
    """
    Project a point onto a line segment (perpendicular projection)
    
    Uses equirectangular projection for computational efficiency on small distances.
    The projection parameter t is clamped to [0,1] to ensure the result stays on the segment.
    
    Args:
        point: (lat, lng) - point to project
        seg_start: (lat, lng) - segment start
        seg_end: (lat, lng) - segment end
    
    Returns:
        tuple: ((projected_lat, projected_lng), distance_meters)
    """
    # Convert to approximate Cartesian coordinates (meters)
    lat_to_m = 111320.0  # meters per degree latitude
    avg_lat = (seg_start[0] + seg_end[0] + point[0]) / 3.0
    lng_to_m = 111320.0 * cos(radians(avg_lat))
    
    # Point coordinates relative to seg_start
    px = (point[1] - seg_start[1]) * lng_to_m
    py = (point[0] - seg_start[0]) * lat_to_m
    
    # Segment vector
    sx = (seg_end[1] - seg_start[1]) * lng_to_m
    sy = (seg_end[0] - seg_start[0]) * lat_to_m
    
    # Segment length squared
    seg_len_sq = sx * sx + sy * sy
    
    if seg_len_sq < 1e-6:  # Segment is essentially a point
        return seg_start, haversine(seg_start[1], seg_start[0], point[1], point[0])
    
    # Calculate projection parameter t
    # t = 0 means projection at seg_start
    # t = 1 means projection at seg_end
    # t in (0,1) means projection is on the segment
    t = (px * sx + py * sy) / seg_len_sq
    t = max(0, min(1, t))  # Clamp to [0, 1]
    
    # Calculate projected point in Cartesian
    proj_x = t * sx
    proj_y = t * sy
    
    # Convert back to lat/lng
    projected_lat = seg_start[0] + (proj_y / lat_to_m)
    projected_lng = seg_start[1] + (proj_x / lng_to_m)
    
    # Calculate distance from original point to projection
    distance = sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    return (projected_lat, projected_lng), distance


def find_nearest_edge(lat: float, lng: float, 
                     edges_df: pd.DataFrame, 
                     nodes_df: pd.DataFrame, 
                     max_distance: float = 500) -> Optional[Dict]:
    """
    Find the nearest road edge to a given point
    
    Args:
        lat, lng: GPS coordinates
        edges_df: DataFrame with columns [source, target, name, ...]
        nodes_df: DataFrame with columns [node_id, latitude, longitude]
        max_distance: Maximum search distance in meters
    
    Returns:
        dict or None: {
            'edge': (source_id, target_id),
            'projection_point': {'lat': float, 'lng': float},
            'distance_m': float,
            'road_name': str,
            'segment_length_m': float
        }
    """
    min_distance = float('inf')
    best_segment = None
    
    # Create node lookup for faster access
    node_coords = {}
    for _, node in nodes_df.iterrows():
        node_coords[node['node_id']] = (node['latitude'], node['longitude'])
    
    # Check each edge
    for _, edge in edges_df.iterrows():
        source_id = edge['source']
        target_id = edge['target']
        
        # Get segment endpoints
        if source_id not in node_coords or target_id not in node_coords:
            continue
        
        seg_start = node_coords[source_id]  # (lat, lng)
        seg_end = node_coords[target_id]    # (lat, lng)
        
        # Project point onto segment
        projection, distance = project_point_to_segment(
            (lat, lng), seg_start, seg_end
        )
        
        # Track minimum distance
        if distance < min_distance and distance <= max_distance:
            min_distance = distance
            segment_length = haversine(
                seg_start[1], seg_start[0],
                seg_end[1], seg_end[0]
            )
            best_segment = {
                'edge': (int(source_id), int(target_id)),
                'projection_point': {
                    'lat': projection[0],
                    'lng': projection[1]
                },
                'distance_m': distance,
                'road_name': str(edge.get('name', 'Unnamed Road')),
                'segment_length_m': segment_length
            }
    
    return best_segment


def validate_road_connection(point: Tuple[float, float], 
                            road_point: Tuple[float, float], 
                            max_snap_distance: float = 500) -> Dict:
    """
    Validate if a road connection is reasonable
    
    Args:
        point: (lat, lng) - original point
        road_point: (lat, lng) - snapped road point
        max_snap_distance: Maximum acceptable distance in meters
    
    Returns:
        dict: {
            'valid': bool,
            'distance': float,
            'message': str,
            'warning_level': str  # 'none', 'info', 'warning', 'error'
        }
    """
    distance = haversine(point[1], point[0], road_point[1], road_point[0])
    
    if distance <= 50:
        return {
            'valid': True,
            'distance': distance,
            'message': 'Location is very close to road',
            'warning_level': 'none'
        }
    elif distance <= 100:
        return {
            'valid': True,
            'distance': distance,
            'message': f'Walking distance to road: {distance:.0f}m',
            'warning_level': 'info'
        }
    elif distance <= max_snap_distance:
        return {
            'valid': True,
            'distance': distance,
            'message': f'Location is {distance:.0f}m from road. Please confirm.',
            'warning_level': 'warning'
        }
    else:
        return {
            'valid': False,
            'distance': distance,
            'message': f'Location is {distance:.0f}m from road (max: {max_snap_distance}m). Please select a closer location.',
            'warning_level': 'error'
        }


# Test the functions
if __name__ == "__main__":
    print("Testing road segment utilities...")
    
    # Test 1: Point between two nodes
    point = (14.6500, 121.0450)
    seg_start = (14.6498, 121.0445)
    seg_end = (14.6502, 121.0455)
    
    projection, distance = project_point_to_segment(point, seg_start, seg_end)
    print(f"\n✅ Test 1: Point projection")
    print(f"   Point: {point}")
    print(f"   Segment: {seg_start} → {seg_end}")
    print(f"   Projection: {projection}")
    print(f"   Distance: {distance:.2f}m")
    
    # Test 2: Point before segment start (should clamp to start)
    point2 = (14.6495, 121.0440)
    projection2, distance2 = project_point_to_segment(point2, seg_start, seg_end)
    print(f"\n✅ Test 2: Point before segment (should clamp)")
    print(f"   Point: {point2}")
    print(f"   Projection: {projection2}")
    print(f"   Distance: {distance2:.2f}m")
    print(f"   Clamped to start: {abs(projection2[0] - seg_start[0]) < 0.0001}")
    
    # Test 3: Point after segment end (should clamp to end)
    point3 = (14.6505, 121.0460)
    projection3, distance3 = project_point_to_segment(point3, seg_start, seg_end)
    print(f"\n✅ Test 3: Point after segment (should clamp)")
    print(f"   Point: {point3}")
    print(f"   Projection: {projection3}")
    print(f"   Distance: {distance3:.2f}m")
    print(f"   Clamped to end: {abs(projection3[0] - seg_end[0]) < 0.0001}")
    
    # Test 4: Validation tests
    print(f"\n✅ Test 4: Validation")
    test_cases = [
        ((14.6500, 121.0450), (14.6500, 121.0451), "Very close (30m)"),
        ((14.6500, 121.0450), (14.6501, 121.0450), "Close (100m)"),
        ((14.6500, 121.0450), (14.6505, 121.0450), "Far (500m)"),
        ((14.6500, 121.0450), (14.6510, 121.0450), "Too far (1100m)")
    ]
    
    for point, road_point, desc in test_cases:
        result = validate_road_connection(point, road_point, max_snap_distance=500)
        print(f"   {desc}: {result['warning_level']} - {result['message']}")
    
    print("\n✅ All basic tests complete!")
