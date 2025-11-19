"""
OSM Road Geometry Snapper with Spatial Indexing

This module provides road-aware point snapping using actual OSM road geometries
from the edges CSV file. It uses spatial indexing (STRtree) for
efficient nearest-road queries and considers road hierarchy and directionality.
"""

import csv
import json
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree
from typing import Dict, List, Tuple, Optional
import numpy as np
from pathlib import Path
import pandas as pd
from console_formatter import get_logger

logger = get_logger("OSMRoadSnapper")


class OSMRoadSnapper:
    """
    Road-aware point snapping using OSM geometry with spatial indexing.
    
    This class loads OSM road geometries from the edges CSV file and builds a spatial
    index for efficient nearest-road queries. It snaps points to actual
    road geometries rather than just intersection nodes.
    """
    
    def __init__(self, edges_csv: str, nodes_csv: str = None):
        """
        Initialize the OSM Road Snapper.
        
        Args:
            edges_csv: Path to edges CSV file (source,target,length,name,highway,oneway,geometry_coords)
            nodes_csv: Optional path to nodes CSV for routing node mapping
        """
        self.edges_csv = Path(edges_csv)
        self.nodes_csv = Path(nodes_csv) if nodes_csv else None
        
        # Load edge geometries from CSV
        logger.processing(f"Loading road geometries from {edges_csv}...")
        self._load_edges_from_csv()
        
        # Build spatial index
        self._build_spatial_index()
        
        # Load routing nodes mapping if provided
        self.routing_nodes_df = None
        if self.nodes_csv and self.nodes_csv.exists():
            self.routing_nodes_df = pd.read_csv(self.nodes_csv)
            logger.success(f"Loaded {len(self.routing_nodes_df)} routing nodes")
    
    def _load_edges_from_csv(self):
        """Load edge geometries from CSV file."""
        self.edges_data = []
        self.node_coords = {}
        
        # First load node coordinates if available
        if self.nodes_csv and self.nodes_csv.exists():
            with open(self.nodes_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    node_id = int(row['node_id'])
                    lat = float(row['latitude'])
                    lng = float(row['longitude'])
                    self.node_coords[node_id] = (lng, lat)  # (lon, lat) for Shapely
        
        # Load edges with geometry
        with open(self.edges_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                source = int(row['source'])
                target = int(row['target'])
                length = float(row['length'])
                name = row.get('road_name', row.get('name', 'Unnamed Road'))  # Try 'road_name' first, then 'name'
                highway = row.get('highway_type', row.get('highway', 'unclassified'))  # Try 'highway_type' first
                oneway = row.get('oneway', '0')
                geometry_json = row.get('geometry_coords', row.get('geometry', '[]'))  # Try both column names
                
                # Parse geometry
                try:
                    coords = json.loads(geometry_json) if geometry_json else []
                except (json.JSONDecodeError, ValueError):
                    coords = []
                
                # Create LineString from coordinates
                if coords and len(coords) >= 2:
                    # CRITICAL: Our CSV stores coords as [[lat, lon], [lat, lon], ...]
                    # But Shapely expects [[lon, lat], [lon, lat], ...]
                    # So we need to SWAP the coordinates
                    line_coords = [(coord[1], coord[0]) for coord in coords if len(coord) >= 2]  # Swap: (lon, lat)
                    if len(line_coords) >= 2:
                        geometry = LineString(line_coords)
                    else:
                        geometry = None
                else:
                    # Fallback to straight line between nodes
                    if source in self.node_coords and target in self.node_coords:
                        geometry = LineString([
                            self.node_coords[source],
                            self.node_coords[target]
                        ])
                    else:
                        geometry = None
                
                if geometry:
                    self.edges_data.append({
                        'source': source,
                        'target': target,
                        'name': name,
                        'highway': highway,
                        'oneway': oneway,
                        'length': length,
                        'geometry': geometry
                    })
        
        logger.success(f"Loaded {len(self.edges_data)} edges with geometries")
    
    def _build_spatial_index(self):
        """Build spatial index from edge geometries."""
        logger.processing("Building spatial index from road geometries...")
        
        self.edge_geometries = []
        self.edge_metadata = []
        self.geom_to_idx = {}  # Map geometry id to index
        
        for idx, edge_data in enumerate(self.edges_data):
            geom = edge_data['geometry']
            
            # Store geometry and metadata
            self.edge_geometries.append(geom)
            self.edge_metadata.append({
                'u': edge_data['source'],
                'v': edge_data['target'],
                'name': edge_data['name'],
                'highway': edge_data['highway'],
                'oneway': edge_data['oneway'],
                'length': edge_data['length'],
                'geometry': geom
            })
            
            # Store mapping from geometry ID to index
            self.geom_to_idx[id(geom)] = idx
        
        # Build STRtree for fast spatial queries
        self.spatial_index = STRtree(self.edge_geometries)
        logger.success(f"Built spatial index with {len(self.edge_geometries)} road segments")
    
    def snap_to_nearest_road(
        self, 
        lat: float, 
        lng: float, 
        max_distance_m: float = 25.0,
        consider_hierarchy: bool = True
    ) -> Optional[Dict]:
        """
        Snap a point to the nearest OSM road segment.
        
        Args:
            lat: Latitude of point to snap
            lng: Longitude of point to snap
            max_distance_m: Maximum snapping distance in meters
            consider_hierarchy: Whether to weight by road hierarchy
        
        Returns:
            dict or None: {
                'original_point': {'lat': float, 'lng': float},
                'snapped_point': {'lat': float, 'lng': float},
                'distance_m': float,
                'road_name': str,
                'highway_type': str,
                'oneway': bool,
                'osm_nodes': [u, v],  # OSM node IDs defining the segment
                'routing_nodes': [node_id1, node_id2],  # Internal routing node IDs
                'edge_length_m': float,
                'snap_position': float,  # Position along edge (0.0 to 1.0)
                'geometry': LineString,
                'metadata': dict
            }
        """
        # Create point geometry
        point = Point(lng, lat)
        
        # Find nearest roads using spatial index
        # Query more candidates for hierarchy consideration
        num_candidates = 10 if consider_hierarchy else 1
        
        # STRtree.nearest() returns a single geometry in newer versions
        # We need to query multiple times or use query() with distance
        try:
            # For multiple candidates, use query with distance buffer
            if consider_hierarchy and num_candidates > 1:
                # Get geometries within a larger radius for comparison
                search_radius = max_distance_m / (111320 * np.cos(np.radians(lat)))
                nearby_indices = self.spatial_index.query(point.buffer(search_radius))
                # Convert indices to list if needed
                if hasattr(nearby_indices, '__iter__'):
                    nearby_indices = list(nearby_indices)
                else:
                    nearby_indices = [nearby_indices] if nearby_indices is not None else []
                
                if len(nearby_indices) == 0:
                    return None
                    
                nearest_geoms = [self.edge_geometries[idx] for idx in nearby_indices if idx < len(self.edge_geometries)]
            else:
                # Try new API (Shapely 2.0+)
                nearest_result = self.spatial_index.nearest(point)
                # Handle both single geometry and index return types
                if isinstance(nearest_result, int):
                    if nearest_result < len(self.edge_geometries):
                        nearest_geoms = [self.edge_geometries[nearest_result]]
                    else:
                        return None
                elif hasattr(nearest_result, 'distance'):
                    nearest_geoms = [nearest_result]
                else:
                    return None
                    
        except Exception as e:
            logger.warning(f"Error querying spatial index: {e}")
            return None
        
        if not nearest_geoms or len(nearest_geoms) == 0:
            return None
        
        # Calculate distances and find best match
        candidates = []
        for geom in nearest_geoms:
            # Find metadata for this geometry using robust lookup
            try:
                # Ensure geom is a Geometry object
                if not hasattr(geom, 'distance'):
                    logger.warning("Invalid geometry object (not a Shapely Geometry)")
                    continue
                
                # Try to find by geometry ID first (more reliable)
                geom_idx = self.geom_to_idx.get(id(geom))
                if geom_idx is None:
                    # Fallback: search by geometry equality or bounds
                    for idx, stored_geom in enumerate(self.edge_geometries):
                        if stored_geom.equals(geom) or stored_geom.bounds == geom.bounds:
                            geom_idx = idx
                            break
                
                if geom_idx is None:
                    # If still not found, skip this geometry
                    continue
                    
            except Exception as e:
                logger.warning(f"Error finding geometry index: {e}")
                continue
            
            metadata = self.edge_metadata[geom_idx]
            
            # Calculate distance to road
            distance = point.distance(geom)
            distance_m = distance * 111320 * np.cos(np.radians(lat))  # Approximate
            
            # Apply hierarchy weighting if enabled
            weight = 1.0
            if consider_hierarchy:
                # Weight major roads higher (lower multiplier = higher priority)
                highway_weights = {
                    'motorway': 0.8,
                    'trunk': 0.85,
                    'primary': 0.9,
                    'secondary': 0.95,
                    'tertiary': 1.0,
                    'residential': 1.05,
                    'service': 1.1,
                    'unclassified': 1.05
                }
                highway = metadata['highway']
                if isinstance(highway, list):
                    highway = highway[0]
                weight = highway_weights.get(highway, 1.0)
            
            weighted_distance = distance_m * weight
            
            candidates.append({
                'geom': geom,
                'metadata': metadata,
                'distance_m': distance_m,
                'weighted_distance': weighted_distance,
                'geom_idx': geom_idx
            })
        
        # Sort by weighted distance
        candidates.sort(key=lambda x: x['weighted_distance'])
        best = candidates[0]
        
        # Check if within tolerance
        if best['distance_m'] > max_distance_m:
            return None
        
        # Project point onto the line segment
        geom = best['geom']
        metadata = best['metadata']
        
        # Find nearest point on the line
        snapped_point_geom = geom.interpolate(geom.project(point))
        snapped_lng = snapped_point_geom.x
        snapped_lat = snapped_point_geom.y
        
        # Calculate position along edge (0.0 = start, 1.0 = end)
        snap_position = geom.project(point, normalized=True)
        
        # Map to routing nodes if available
        routing_nodes = self._find_routing_nodes(
            metadata['u'], 
            metadata['v'],
            lat, lng
        )
        
        # Prepare clean metadata without non-serializable objects
        clean_metadata = {
            'u': metadata['u'],
            'v': metadata['v'],
            'name': metadata['name'],
            'highway': metadata['highway'],
            'oneway': metadata['oneway'],
            'length': metadata['length']
            # Note: 'geometry' and 'key' fields excluded (not in CSV data structure)
        }
        
        return {
            'original_point': {'lat': lat, 'lng': lng},
            'snapped_point': {'lat': snapped_lat, 'lng': snapped_lng},
            'distance_m': best['distance_m'],
            'road_name': metadata['name'],
            'highway_type': metadata['highway'],
            'oneway': metadata['oneway'],
            'osm_nodes': [metadata['u'], metadata['v']],
            'routing_nodes': routing_nodes,
            'edge_length_m': metadata['length'],
            'snap_position': snap_position,
            'metadata': clean_metadata
            # Note: 'geometry' field removed to ensure JSON serializability
        }
    
    def _find_routing_nodes(
        self, 
        osm_u: int, 
        osm_v: int,
        lat: float,
        lng: float
    ) -> List[int]:
        """
        Find corresponding routing node IDs for OSM nodes.
        
        Args:
            osm_u: OSM node ID (source)
            osm_v: OSM node ID (target)
            lat: Latitude for fallback nearest search
            lng: Longitude for fallback nearest search
        
        Returns:
            List of routing node IDs [start_node, end_node]
        """
        if self.routing_nodes_df is None:
            # Return OSM IDs as fallback
            return [osm_u, osm_v]
        
        # Get OSM node coordinates from our loaded node_coords
        u_lng, u_lat = self.node_coords.get(osm_u, (None, None))
        v_lng, v_lat = self.node_coords.get(osm_v, (None, None))
        
        routing_nodes = []
        
        # Find nearest routing nodes by coordinates
        for target_lat, target_lng in [(u_lat, u_lng), (v_lat, v_lng)]:
            if target_lat is None or target_lng is None:
                continue
            
            # Calculate distances to all routing nodes
            distances = np.sqrt(
                (self.routing_nodes_df['latitude'] - target_lat) ** 2 +
                (self.routing_nodes_df['longitude'] - target_lng) ** 2
            )
            
            nearest_idx = distances.argmin()
            nearest_node_id = int(self.routing_nodes_df.iloc[nearest_idx]['node_id'])
            routing_nodes.append(nearest_node_id)
        
        return routing_nodes if len(routing_nodes) == 2 else [osm_u, osm_v]
    
    def get_hierarchy_priority(self, highway_type: str) -> int:
        """
        Get priority value for road hierarchy (lower = higher priority).
        
        Args:
            highway_type: OSM highway tag value
        
        Returns:
            Priority integer (0-10, lower is higher priority)
        """
        priorities = {
            'motorway': 0,
            'trunk': 1,
            'primary': 2,
            'secondary': 3,
            'tertiary': 4,
            'residential': 5,
            'service': 6,
            'unclassified': 7,
            'track': 8,
            'path': 9,
            'footway': 10
        }
        
        if isinstance(highway_type, list):
            highway_type = highway_type[0]
        
        return priorities.get(highway_type, 7)


# Test function
if __name__ == "__main__":
    from config import Config
    
    logger.info("Testing OSM Road Snapper (CSV-based)...")
    
    # Use paths from config
    edges_csv = str(Config.EDGES_CSV)
    nodes_csv = str(Config.NODES_CSV)
    
    try:
        snapper = OSMRoadSnapper(edges_csv, nodes_csv)
        
        # Test coordinates in Quezon City
        test_points = [
            (14.6760, 121.0437, "Near Commonwealth Ave"),
            (14.6500, 121.0450, "Near EDSA"),
            (14.6300, 121.0200, "Residential area")
        ]
        
        for lat, lng, desc in test_points:
            logger.location(f"Testing: {desc} ({lat}, {lng})")
            
            result = snapper.snap_to_nearest_road(lat, lng, max_distance_m=50)
            
            if result:
                logger.success("Snapped successfully!")
                logger.data(f"  Road: {result['road_name']}")
                logger.data(f"  Highway type: {result['highway_type']}")
                logger.data(f"  Distance: {result['distance_m']:.1f}m")
                logger.data(f"  Snapped to: ({result['snapped_point']['lat']:.6f}, {result['snapped_point']['lng']:.6f})")
                logger.data(f"  Position on edge: {result['snap_position']:.2%}")
                logger.data(f"  Edge nodes: {result.get('osm_nodes', [])} or {result.get('edge_nodes', [])}")
                logger.data(f"  Routing nodes: {result.get('routing_nodes', [])}")
            else:
                logger.warning("No road found within 50m")
        
        logger.success("Test complete! Road snapping working with CSV geometry")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
