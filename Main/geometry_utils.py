"""
Geometry utilities for route visualization enhancement.
Provides functions to interpolate intermediate GPS points along road segments
to create smoother, more realistic route visualizations.
"""

import math
from typing import List, Tuple, Dict


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.
    
    Args:
        lat1, lon1: Coordinates of first point
        lat2, lon2: Coordinates of second point
    
    Returns:
        Distance in meters
    """
    R = 6371000  # Earth's radius in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def interpolate_point(lat1: float, lon1: float, lat2: float, lon2: float, fraction: float) -> Tuple[float, float]:
    """
    Interpolate a point between two GPS coordinates using great circle path.
    
    Args:
        lat1, lon1: Start coordinates
        lat2, lon2: End coordinates
        fraction: Distance fraction between 0.0 (start) and 1.0 (end)
    
    Returns:
        Tuple of (lat, lon) for interpolated point
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Calculate angular distance
    delta = haversine_distance(lat1, lon1, lat2, lon2) / 6371000  # Angular distance in radians
    
    if delta < 1e-10:  # Points are essentially the same
        return (lat1, lon1)
    
    # Slerp interpolation (spherical linear interpolation)
    a = math.sin((1 - fraction) * delta) / math.sin(delta)
    b = math.sin(fraction * delta) / math.sin(delta)
    
    x = a * math.cos(lat1_rad) * math.cos(lon1_rad) + b * math.cos(lat2_rad) * math.cos(lon2_rad)
    y = a * math.cos(lat1_rad) * math.sin(lon1_rad) + b * math.cos(lat2_rad) * math.sin(lon2_rad)
    z = a * math.sin(lat1_rad) + b * math.sin(lat2_rad)
    
    lat = math.atan2(z, math.sqrt(x * x + y * y))
    lon = math.atan2(y, x)
    
    return (math.degrees(lat), math.degrees(lon))


def interpolate_segment(lat1: float, lon1: float, lat2: float, lon2: float, 
                        max_distance: float = 50.0) -> List[Tuple[float, float]]:
    """
    Interpolate intermediate points along a segment to ensure smooth visualization.
    
    Args:
        lat1, lon1: Start coordinates
        lat2, lon2: End coordinates
        max_distance: Maximum distance between points in meters (default: 50m)
    
    Returns:
        List of (lat, lon) tuples including start, interpolated points, and end
    """
    distance = haversine_distance(lat1, lon1, lat2, lon2)
    
    # If segment is short enough, no interpolation needed
    if distance <= max_distance:
        return [(lat1, lon1), (lat2, lon2)]
    
    # Calculate number of intermediate points needed
    num_points = math.ceil(distance / max_distance)
    
    points = [(lat1, lon1)]
    
    # Add interpolated points
    for i in range(1, num_points):
        fraction = i / num_points
        interpolated = interpolate_point(lat1, lon1, lat2, lon2, fraction)
        points.append(interpolated)
    
    points.append((lat2, lon2))
    
    return points


def enhance_route_geometry(coordinates: List[Dict[str, float]], 
                           max_distance: float = 50.0) -> List[Dict[str, float]]:
    """
    Enhance a route by interpolating intermediate points along all segments.
    
    Args:
        coordinates: List of coordinate dicts with 'lat' and 'lng' keys
        max_distance: Maximum distance between points in meters (default: 50m)
    
    Returns:
        Enhanced list of coordinates with interpolated points
    """
    if len(coordinates) < 2:
        return coordinates
    
    enhanced = []
    
    for i in range(len(coordinates) - 1):
        curr = coordinates[i]
        next_coord = coordinates[i + 1]
        
        # Interpolate segment
        segment_points = interpolate_segment(
            curr['lat'], curr['lng'],
            next_coord['lat'], next_coord['lng'],
            max_distance
        )
        
        # Add all points except the last one (to avoid duplicates)
        for lat, lng in segment_points[:-1]:
            enhanced.append({'lat': lat, 'lng': lng})
    
    # Add the final point
    enhanced.append(coordinates[-1])
    
    return enhanced


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the bearing (direction) from point 1 to point 2.
    
    Args:
        lat1, lon1: Start coordinates
        lat2, lon2: End coordinates
    
    Returns:
        Bearing in degrees (0-360, where 0 is North)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360
    
    return bearing


def smooth_polyline(coordinates: List[Dict[str, float]], 
                    window_size: int = 3) -> List[Dict[str, float]]:
    """
    Smooth a polyline using a simple moving average filter.
    This can help reduce sharp angles in interpolated routes.
    
    Args:
        coordinates: List of coordinate dicts with 'lat' and 'lng' keys
        window_size: Size of smoothing window (must be odd, default: 3)
    
    Returns:
        Smoothed list of coordinates
    """
    if len(coordinates) < window_size or window_size < 3:
        return coordinates
    
    # Ensure window size is odd
    if window_size % 2 == 0:
        window_size += 1
    
    half_window = window_size // 2
    smoothed = []
    
    for i in range(len(coordinates)):
        # Keep start and end points unchanged
        if i < half_window or i >= len(coordinates) - half_window:
            smoothed.append(coordinates[i])
            continue
        
        # Calculate average of window
        lat_sum = 0.0
        lng_sum = 0.0
        count = 0
        
        for j in range(i - half_window, i + half_window + 1):
            lat_sum += coordinates[j]['lat']
            lng_sum += coordinates[j]['lng']
            count += 1
        
        smoothed.append({
            'lat': lat_sum / count,
            'lng': lng_sum / count
        })
    
    return smoothed
