"""
OSM Road Geometry Snapper with Spatial Indexing

This module provides road-aware point snapping using actual OSM road geometries
from the osm_geometry.graphml file. It uses spatial indexing (STRtree) for
efficient nearest-road queries and considers road hierarchy and directionality.
"""

import osmnx as ox
import networkx as nx
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree
from typing import Dict, List, Tuple, Optional
import numpy as np
from pathlib import Path
import pandas as pd


class OSMRoadSnapper:
    """
    Road-aware point snapping using OSM geometry with spatial indexing.
    
    This class loads OSM road geometries from GraphML and builds a spatial
    index for efficient nearest-road queries. It snaps points to actual
    road geometries rather than just intersection nodes.
    """
    
    def __init__(self, graphml_path: str, nodes_csv: str = None):
        """
        Initialize the OSM Road Snapper.
        
        Args:
            graphml_path: Path to osm_geometry.graphml file
            nodes_csv: Optional path to nodes CSV for routing node mapping
        """
        self.graphml_path = Path(graphml_path)
        self.nodes_csv = Path(nodes_csv) if nodes_csv else None
        
        # Load OSM graph
        print(f"📁 Loading OSM graph from {graphml_path}...")
        self.graph = ox.load_graphml(self.graphml_path)
        print(f"✅ Loaded {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
        
        # Build spatial index
        self._build_spatial_index()
        
        # Load routing nodes mapping if provided
        self.routing_nodes_df = None
        if self.nodes_csv and self.nodes_csv.exists():
            self.routing_nodes_df = pd.read_csv(self.nodes_csv)
            print(f"✅ Loaded {len(self.routing_nodes_df)} routing nodes")
    
    def _build_spatial_index(self):
        """Build spatial index from OSM edge geometries."""
        print("🗺️  Building spatial index from OSM geometries...")
        
        self.edge_geometries = []
        self.edge_metadata = []
        
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            # Get geometry
            if 'geometry' in data:
                geom = data['geometry']
            else:
                # Create straight line from node coordinates
                u_data = self.graph.nodes[u]
                v_data = self.graph.nodes[v]
                geom = LineString([
                    (u_data['x'], u_data['y']),
                    (v_data['x'], v_data['y'])
                ])
            
            # Store geometry and metadata
            self.edge_geometries.append(geom)
            self.edge_metadata.append({
                'u': u,
                'v': v,
                'key': key,
                'name': data.get('name', 'Unnamed Road'),
                'highway': data.get('highway', 'unclassified'),
                'oneway': data.get('oneway', False),
                'length': data.get('length', geom.length * 111320),  # Approximate meters
                'geometry': geom
            })
        
        # Build STRtree for fast spatial queries
        self.spatial_index = STRtree(self.edge_geometries)
        print(f"✅ Built spatial index with {len(self.edge_geometries)} road segments")
    
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
            # Try new API (Shapely 2.0+)
            nearest_geom = self.spatial_index.nearest(point)
            if nearest_geom is None:
                return None
            
            # For multiple candidates, use query with distance
            if consider_hierarchy and num_candidates > 1:
                # Get geometries within a larger radius for comparison
                search_radius = max_distance_m / (111320 * np.cos(np.radians(lat)))
                nearby_indices = self.spatial_index.query(point.buffer(search_radius))
                nearest_geoms = [self.edge_geometries[idx] for idx in nearby_indices]
                if not nearest_geoms:
                    nearest_geoms = [nearest_geom]
            else:
                nearest_geoms = [nearest_geom]
        except Exception as e:
            print(f"Error querying spatial index: {e}")
            return None
        
        if not nearest_geoms or len(nearest_geoms) == 0:
            return None
        
        # Calculate distances and find best match
        candidates = []
        for geom in nearest_geoms:
            # Find metadata for this geometry
            geom_idx = self.edge_geometries.index(geom)
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
            'key': metadata['key'],
            'name': metadata['name'],
            'highway': metadata['highway'],
            'oneway': metadata['oneway'],
            'length': metadata['length']
            # Note: 'geometry' field excluded (not JSON serializable)
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
        
        # Try to find exact matches in routing nodes
        # This assumes routing nodes CSV has OSM ID mapping
        # Adjust column names based on actual CSV structure
        
        # Get OSM node coordinates
        u_data = self.graph.nodes.get(osm_u, {})
        v_data = self.graph.nodes.get(osm_v, {})
        
        u_lat = u_data.get('y')
        u_lng = u_data.get('x')
        v_lat = v_data.get('y')
        v_lng = v_data.get('x')
        
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
    print("🧪 Testing OSM Road Snapper...")
    
    # Paths (adjust based on your structure)
    graphml_path = "data/osm_geometry.graphml"
    nodes_csv = "data/raw/quezon_city_nodes.csv"
    
    try:
        snapper = OSMRoadSnapper(graphml_path, nodes_csv)
        
        # Test coordinates in Quezon City
        test_points = [
            (14.6760, 121.0437, "Near Commonwealth Ave"),
            (14.6500, 121.0450, "Near EDSA"),
            (14.6300, 121.0200, "Residential area")
        ]
        
        for lat, lng, desc in test_points:
            print(f"\n📍 Testing: {desc} ({lat}, {lng})")
            
            result = snapper.snap_to_nearest_road(lat, lng, max_distance_m=50)
            
            if result:
                print(f"✅ Snapped successfully!")
                print(f"   Road: {result['road_name']}")
                print(f"   Highway type: {result['highway_type']}")
                print(f"   Distance: {result['distance_m']:.1f}m")
                print(f"   Snapped to: ({result['snapped_point']['lat']:.6f}, {result['snapped_point']['lng']:.6f})")
                print(f"   Position on edge: {result['snap_position']:.2%}")
                print(f"   OSM nodes: {result['osm_nodes']}")
                print(f"   Routing nodes: {result['routing_nodes']}")
            else:
                print(f"❌ No road found within 50m")
        
        print("\n✅ Test complete!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
