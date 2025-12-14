# road_network_utils.py - Shared Road Network Utilities
"""
Shared utility functions for road network operations.
These functions can be used by flask_server.py, experiment_runner_backend.py, and other modules.

Provides:
- get_random_road_points_data(): Get random valid road points from the network
- snap_location_to_edge_data(): Snap a location to nearest road edge with full data
- get_node_coordinates(): Get lat/lng coordinates for a node ID
"""

import random
from typing import Optional, Dict, List, Tuple
from pathlib import Path

from console_formatter import get_logger
from config import Config

logger = get_logger("RoadNetworkUtils")

# Module-level cache for node coordinates lookup
_node_coords_cache: Optional[Dict[int, Tuple[float, float]]] = None
_edges_data_cache: Optional[List[Dict]] = None


def _load_node_coordinates() -> Dict[int, Tuple[float, float]]:
    """
    Load node coordinates from CSV file into a lookup dictionary.
    Cached for performance.
    
    Returns:
        Dict mapping node_id -> (lat, lng)
    """
    global _node_coords_cache
    
    if _node_coords_cache is not None:
        return _node_coords_cache
    
    import pandas as pd
    
    try:
        nodes_df = pd.read_csv(str(Config.NODES_CSV))
        _node_coords_cache = {}
        
        for _, node in nodes_df.iterrows():
            node_id = int(node['node_id'])
            lat = float(node['latitude'])
            lng = float(node['longitude'])
            _node_coords_cache[node_id] = (lat, lng)
        
        logger.success(f"Loaded {len(_node_coords_cache)} node coordinates")
        return _node_coords_cache
        
    except Exception as e:
        logger.error(f"Failed to load node coordinates: {e}")
        return {}


def get_node_coordinates(node_id: int) -> Optional[Tuple[float, float]]:
    """
    Get coordinates for a specific node ID.
    
    Args:
        node_id: The node ID to look up
        
    Returns:
        Tuple of (lat, lng) or None if not found
    """
    node_coords = _load_node_coordinates()
    return node_coords.get(node_id)


def _get_available_matched_edges() -> List[Dict]:
    """
    Load all available matched edges from matched_edges.csv file.
    Cached for performance.
    
    Returns:
        List of edge dictionaries with source/target coordinates
    """
    global _edges_data_cache
    
    if _edges_data_cache is not None:
        return _edges_data_cache
    
    import csv
    from boundary_filter import is_in_excluded_area
    
    matched_edges_file = Path(Config.HERE_OSM_DIR) / 'matched_edges.csv'
    
    all_edges = []
    
    if matched_edges_file.exists():
        try:
            with open(matched_edges_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = row.get('source')
                    target = row.get('target')
                    
                    if source and target:
                        source_lat = row.get('source_lat')
                        source_lon = row.get('source_lon')
                        target_lat = row.get('target_lat')
                        target_lon = row.get('target_lon')
                        
                        try:
                            s_lat = float(source_lat) if source_lat else None
                            s_lon = float(source_lon) if source_lon else None
                            t_lat = float(target_lat) if target_lat else None
                            t_lon = float(target_lon) if target_lon else None
                            
                            # Skip edges near boundary
                            if s_lat and s_lon and is_in_excluded_area(s_lat, s_lon):
                                continue
                            if t_lat and t_lon and is_in_excluded_area(t_lat, t_lon):
                                continue
                            
                            edge = {
                                'source': int(source),
                                'target': int(target),
                                'source_lat': s_lat,
                                'source_lon': s_lon,
                                'target_lat': t_lat,
                                'target_lon': t_lon,
                                'road_name': row.get('road_name', 'Unknown Road'),
                                'highway_type': row.get('highway_type', 'unknown'),
                                'free_flow_speed': float(row.get('free_flow_speed', 60))
                            }
                            all_edges.append(edge)
                            
                        except (ValueError, TypeError):
                            continue
            
            logger.success(f"Loaded {len(all_edges)} matched edges")
            _edges_data_cache = all_edges
            
        except Exception as e:
            logger.error(f"Error loading matched edges: {e}")
    
    return all_edges or []


def get_random_road_points_data(
    count: int = 10,
    min_lat: float = 14.55,
    max_lat: float = 14.78,
    min_lng: float = 120.98,
    max_lng: float = 121.12
) -> List[Dict]:
    """
    Get random valid road points directly from the road network.
    Much faster than generating random lat/lng and validating.
    
    This is the data-layer equivalent of the /api/demo/random_road_points endpoint.
    
    Args:
        count: Number of points to return
        min_lat, max_lat, min_lng, max_lng: Bounding box for point selection
        
    Returns:
        List of point dicts: [{lat, lng, road_name, highway_type, source, target}, ...]
    """
    from boundary_filter import is_point_in_valid_area
    
    edges = _get_available_matched_edges()
    
    if not edges:
        logger.error("No road edges available for random point generation")
        return []
    
    # Filter edges within bounds and collect valid points
    valid_points = []
    
    for edge in edges:
        try:
            src_lat = edge.get('source_lat')
            src_lng = edge.get('source_lon')
            
            if src_lat and src_lng:
                if min_lat <= src_lat <= max_lat and min_lng <= src_lng <= max_lng:
                    if is_point_in_valid_area(src_lat, src_lng):
                        valid_points.append({
                            'lat': src_lat,
                            'lng': src_lng,
                            'road_name': edge.get('road_name', 'Unknown Road'),
                            'highway_type': edge.get('highway_type', 'unknown'),
                            'source': edge.get('source'),
                            'target': edge.get('target')
                        })
            
            tgt_lat = edge.get('target_lat')
            tgt_lng = edge.get('target_lon')
            
            if tgt_lat and tgt_lng:
                if min_lat <= tgt_lat <= max_lat and min_lng <= tgt_lng <= max_lng:
                    if is_point_in_valid_area(tgt_lat, tgt_lng):
                        valid_points.append({
                            'lat': tgt_lat,
                            'lng': tgt_lng,
                            'road_name': edge.get('road_name', 'Unknown Road'),
                            'highway_type': edge.get('highway_type', 'unknown'),
                            'source': edge.get('source'),
                            'target': edge.get('target')
                        })
                        
        except (ValueError, TypeError):
            continue
    
    if not valid_points:
        logger.error("No edges within bounds for random point selection")
        return []
    
    # Sample unique random points
    sample_size = min(count, len(valid_points))
    selected = random.sample(valid_points, sample_size)
    
    # If we need more than available, duplicate with slight variation
    while len(selected) < count:
        base = random.choice(valid_points)
        new_lat = base['lat'] + random.uniform(-0.001, 0.001)
        new_lng = base['lng'] + random.uniform(-0.001, 0.001)
        if is_point_in_valid_area(new_lat, new_lng):
            selected.append({
                'lat': new_lat,
                'lng': new_lng,
                'road_name': base['road_name'],
                'highway_type': base['highway_type'],
                'source': base.get('source'),
                'target': base.get('target')
            })
    
    return selected


def snap_location_to_edge_data(
    lat: float, 
    lng: float, 
    node_mapper = None,
    max_distance: float = 500
) -> Dict:
    """
    Snap a location to the nearest road edge.
    Returns edge source/target and coordinates.
    
    This is the data-layer equivalent of snap_location_to_edge() in flask_server.py.
    
    Args:
        lat: Latitude of point to snap
        lng: Longitude of point to snap
        node_mapper: NodeMapper instance (if None, creates a new one)
        max_distance: Maximum snap distance in meters
        
    Returns:
        dict: {
            'success': True/False,
            'source': int,           # Edge source node ID
            'target': int,           # Edge target node ID  
            'source_lat': float,     # Source node latitude
            'source_lon': float,     # Source node longitude
            'target_lat': float,     # Target node latitude
            'target_lon': float,     # Target node longitude
            'snap_lat': float,       # Snapped point latitude
            'snap_lng': float,       # Snapped point longitude
            'road_name': str,
            'highway_type': str,
            'oneway': int            # 0 or 1
        } or {'success': False, 'error': str}
    """
    try:
        # Create mapper if not provided
        if node_mapper is None:
            from coordinate_mapper import NodeMapper
            node_mapper = NodeMapper(str(Config.NODES_CSV))
        
        # Try OSM-based snapping first (more accurate)
        snap_result = node_mapper.snap_to_osm_road(lat, lng, max_distance_m=max_distance)
        
        if snap_result:
            # OSM snapping succeeded
            routing_nodes = snap_result.get('routing_nodes', [0, 0])
            source_id = routing_nodes[0] if len(routing_nodes) > 0 else 0
            target_id = routing_nodes[1] if len(routing_nodes) > 1 else 0
            
            # Get node coordinates from cache
            node_coords = _load_node_coordinates()
            source_coords = node_coords.get(source_id, (lat, lng))
            target_coords = node_coords.get(target_id, (lat, lng))
            
            return {
                'success': True,
                'source': source_id,
                'target': target_id,
                'source_lat': source_coords[0],
                'source_lon': source_coords[1],
                'target_lat': target_coords[0],
                'target_lon': target_coords[1],
                'snap_lat': snap_result['snapped_point']['lat'],
                'snap_lng': snap_result['snapped_point']['lng'],
                'road_name': snap_result.get('road_name', 'Unknown'),
                'highway_type': snap_result.get('highway_type', 'unknown'),
                'oneway': 1 if snap_result.get('oneway', False) else 0
            }
        
        # Fall back to simple snap_to_nearest_road
        simple_result = node_mapper.snap_to_nearest_road(lat, lng, max_distance=max_distance)
        
        if simple_result:
            source_id = simple_result['edge'][0]
            target_id = simple_result['edge'][1]
            
            # Get node coordinates from cache
            node_coords = _load_node_coordinates()
            source_coords = node_coords.get(source_id, (lat, lng))
            target_coords = node_coords.get(target_id, (lat, lng))
            
            return {
                'success': True,
                'source': source_id,
                'target': target_id,
                'source_lat': source_coords[0],
                'source_lon': source_coords[1],
                'target_lat': target_coords[0],
                'target_lon': target_coords[1],
                'snap_lat': simple_result['projection_point']['lat'],
                'snap_lng': simple_result['projection_point']['lng'],
                'road_name': simple_result.get('road_name', 'Unknown'),
                'highway_type': simple_result.get('highway_type', 'unknown'),
                'oneway': 0  # Simple snap doesn't provide oneway info
            }
        
        return {'success': False, 'error': 'No nearby edge found'}
        
    except Exception as e:
        logger.error(f"Error snapping location ({lat}, {lng}): {e}")
        return {'success': False, 'error': str(e)}


def generate_routes_with_snap_data(
    count: int,
    node_mapper = None,
    progress_callback = None
) -> List[Dict]:
    """
    Generate routes with full snap data for C++ API.
    Each route contains: pin coords, snap coords, edge source/target, oneway flag.
    
    C++ API format:
    <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> 
    <start_edge_source> <start_edge_target> <start_edge_oneway> 
    <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> 
    <dest_edge_source> <dest_edge_target> <dest_edge_oneway>
    
    Args:
        count: Number of routes to generate
        node_mapper: NodeMapper instance (optional)
        progress_callback: Callback function for progress updates: callback(completed, total)
        
    Returns:
        List of route dictionaries with full snap data
    """
    logger.info(f"Generating {count} routes with snap data...")
    
    # Get random road points (request extra for filtering)
    road_points = get_random_road_points_data(count * 3)
    
    if len(road_points) < count * 2:
        logger.error(f"Insufficient road points: got {len(road_points)}, need {count * 2}")
        return []
    
    # Create mapper if not provided
    if node_mapper is None:
        from coordinate_mapper import NodeMapper
        node_mapper = NodeMapper(str(Config.NODES_CSV))
    
    routes = []
    
    for i in range(count):
        # Pick two points for start and end
        start_point = road_points[i * 2]
        end_point = road_points[i * 2 + 1]
        
        # Snap both points to get full edge data
        start_snap = snap_location_to_edge_data(
            start_point['lat'], 
            start_point['lng'],
            node_mapper=node_mapper
        )
        end_snap = snap_location_to_edge_data(
            end_point['lat'], 
            end_point['lng'],
            node_mapper=node_mapper
        )
        
        if not start_snap.get('success') or not end_snap.get('success'):
            logger.warning(f"Route {i}: Failed to snap points, skipping")
            continue
        
        route = {
            "id": f"route_{i}",
            "start": {
                "pin_lat": start_point['lat'],
                "pin_lng": start_point['lng'],
                "snap_lat": start_snap['snap_lat'],
                "snap_lng": start_snap['snap_lng'],
                "edge_source": start_snap['source'],
                "edge_target": start_snap['target'],
                "edge_oneway": start_snap['oneway'],
                "name": start_point.get('road_name', 'Start Location')
            },
            "end": {
                "pin_lat": end_point['lat'],
                "pin_lng": end_point['lng'],
                "snap_lat": end_snap['snap_lat'],
                "snap_lng": end_snap['snap_lng'],
                "edge_source": end_snap['source'],
                "edge_target": end_snap['target'],
                "edge_oneway": end_snap['oneway'],
                "name": end_point.get('road_name', 'End Location')
            }
        }
        
        routes.append(route)
        
        # Progress logging and callback
        if (i + 1) % 100 == 0:
            logger.info(f"Generated {i + 1}/{count} routes...")
            if progress_callback:
                progress_callback(i + 1, count)
    
    logger.success(f"Successfully generated {len(routes)} routes with snap data")
    return routes


def clear_caches():
    """Clear all module-level caches. Useful for testing or after data updates."""
    global _node_coords_cache, _edges_data_cache
    _node_coords_cache = None
    _edges_data_cache = None
    logger.info("Road network caches cleared")
