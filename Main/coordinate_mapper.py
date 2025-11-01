# coordinate_mapper.py
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
import os
from typing import Optional, Dict, Tuple

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance between two points on Earth"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of Earth in kilometers
    return c * r * 1000  # Return in meters

class NodeMapper:
    def __init__(self, nodes_csv_path):
        """Load node coordinates from CSV"""
        self.nodes_df = pd.read_csv(nodes_csv_path)
        self.nodes_csv_path = nodes_csv_path
        
        # Initialize OSM road snapper for geometry-aware selection
        try:
            from osm_road_snapper import OSMRoadSnapper
            edges_csv_path = nodes_csv_path.replace('nodes.csv', 'edges.csv')
            if os.path.exists(edges_csv_path):
                self.osm_snapper = OSMRoadSnapper(edges_csv_path, nodes_csv_path)
                print("✅ OSM road-aware snapping enabled (CSV-based)")
            else:
                print(f"⚠️  Edges CSV file not found at {edges_csv_path}")
                self.osm_snapper = None
        except Exception as e:
            print(f"⚠️  Could not initialize OSM road snapper: {e}")
            import traceback
            traceback.print_exc()
            self.osm_snapper = None
        
        # Initialize accessible node finder for one-way aware selection
        edges_csv_path = nodes_csv_path.replace('nodes.csv', 'edges.csv')
        if os.path.exists(edges_csv_path):
            try:
                from accessible_node_finder import AccessibleNodeFinder
                self.accessible_finder = AccessibleNodeFinder(nodes_csv_path, edges_csv_path)
                print("✅ One-way street aware node finding enabled")
            except Exception as e:
                print(f"⚠️  Could not initialize one-way aware finder: {e}")
                self.accessible_finder = None
        else:
            print(f"⚠️  Edges file not found, one-way awareness disabled")
            self.accessible_finder = None
        
    def find_nearest_node(self, lat, lng, max_distance_m=500, is_start_point=None):
        """
        Find nearest graph node to given coordinates
        
        Args:
            lat, lng: GPS coordinates
            max_distance_m: Maximum acceptable distance in meters
            is_start_point: If True, find accessible start node. If False, find accessible destination.
                           If None, use legacy simple distance-based selection (no one-way awareness)
        
        Returns:
            tuple: (node_id, distance) or (node_id, distance, metadata)
        """
        # Use one-way aware selection if enabled and role specified
        if self.accessible_finder is not None and is_start_point is not None:
            node_id, distance, metadata = self.accessible_finder.find_nearest_accessible_node(
                lat, lng, 
                is_start_point=is_start_point, 
                max_distance_m=max_distance_m
            )
            
            if not metadata['accessible']:
                print(f"⚠️  {metadata['selection_reason']}")
            
            return node_id, distance, metadata
        
        # Fallback to legacy simple distance-based selection
        distances = []
        for _, node in self.nodes_df.iterrows():
            dist = haversine(lng, lat, node['longitude'], node['latitude'])
            distances.append((node['node_id'], dist))
        
        # Find closest node
        closest = min(distances, key=lambda x: x[1])
        node_id, distance = closest
        
        if distance > max_distance_m:
            return None, distance  # Too far from any road
        
        return int(node_id), distance
    
    def snap_to_nearest_road(self, lat, lng, max_distance=500):
        """
        Find nearest road segment and snap point to it
        
        Args:
            lat, lng: GPS coordinates
            max_distance: Maximum snap distance in meters
        
        Returns:
            dict or None: {
                'edge': (source_id, target_id),
                'projection_point': {'lat': float, 'lng': float},
                'distance_m': float,
                'road_name': str,
                'segment_length_m': float,
                'original_point': {'lat': lat, 'lng': lng},
                'validation': {...}
            }
        """
        try:
            from road_segment_utils import find_nearest_edge, validate_road_connection
            
            # Get edges data path from nodes path
            edges_csv_path = self.nodes_csv_path.replace('nodes.csv', 'edges.csv')
            edges_df = pd.read_csv(edges_csv_path)
            
            # Find nearest edge
            result = find_nearest_edge(lat, lng, edges_df, self.nodes_df, max_distance)
            
            if result is None:
                return None
            
            # Add validation
            road_point = (result['projection_point']['lat'], result['projection_point']['lng'])
            validation = validate_road_connection((lat, lng), road_point, max_distance)
            
            # Enhance result with original point and validation
            result['original_point'] = {'lat': lat, 'lng': lng}
            result['validation'] = validation
            
            return result
            
        except Exception as e:
            print(f"Error in snap_to_nearest_road: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def snap_to_osm_road(
        self, 
        lat: float, 
        lng: float, 
        max_distance_m: float = 25.0,
        consider_hierarchy: bool = True,
        fallback_to_node: bool = False  # Changed default to False
    ) -> Optional[Dict]:
        """
        Snap point to nearest OSM road geometry (road-aware snapping).
        
        This method uses actual OSM road geometries from the GraphML file
        to provide more accurate snapping that follows real road shapes.
        If no road is found within max_distance_m, it progressively increases
        the search radius to always find a road (never falls back to nodes).
        
        Args:
            lat: Latitude of point to snap
            lng: Longitude of point to snap
            max_distance_m: Initial maximum snapping distance in meters
            consider_hierarchy: Whether to weight by road hierarchy
            fallback_to_node: DEPRECATED - System always finds nearest road
        
        Returns:
            dict or None: {
                'method': 'osm_geometry',
                'original_point': {'lat': float, 'lng': float},
                'snapped_point': {'lat': float, 'lng': float},
                'distance_m': float,
                'road_name': str,
                'highway_type': str,
                'oneway': bool,
                'osm_nodes': [u, v],
                'routing_nodes': [node_id1, node_id2],
                'edge_length_m': float,
                'snap_position': float,
                'metadata': dict,
                'validation': dict
            }
        """
        # Try OSM-based snapping first if available
        if self.osm_snapper is not None:
            # Progressive search with increasing radius
            search_distances = [max_distance_m, 50, 100, 200, 500, 1000]
            
            for search_dist in search_distances:
                try:
                    result = self.osm_snapper.snap_to_nearest_road(
                        lat, lng, 
                        max_distance_m=search_dist,
                        consider_hierarchy=consider_hierarchy
                    )
                    
                    if result is not None:
                        # Add validation
                        from road_segment_utils import validate_road_connection
                        road_point = (result['snapped_point']['lat'], result['snapped_point']['lng'])
                        validation = validate_road_connection(
                            (lat, lng), 
                            road_point, 
                            search_dist
                        )
                        
                        result['method'] = 'osm_geometry'
                        result['validation'] = validation
                        
                        # Add warning if we had to expand search
                        if search_dist > max_distance_m:
                            result['metadata']['warning'] = f'Expanded search to {search_dist}m to find nearest road'
                            print(f"⚠️  Expanded search to {search_dist}m to find road: {result['road_name']}")
                        
                        return result
                except Exception as e:
                    print(f"⚠️  OSM snapping failed at {search_dist}m: {e}")
                    continue
            
            # If we still haven't found anything, log error
            print(f"❌ Critical: Could not find any OSM road even with 1000m radius")
        else:
            print(f"❌ OSM snapper not initialized - cannot perform road-aware snapping")
        
        return None
    
    def get_routing_node_from_edge(
        self,
        routing_nodes: list,
        snap_position: float,
        is_start: bool
    ) -> int:
        """
        Select best routing node from an OSM edge based on snap position.
        
        For start points: Choose the node closer to the snap position for better accuracy
        For destinations: Choose the node that makes sense for arriving
        
        Args:
            routing_nodes: [node_id1, node_id2] from the edge
            snap_position: Position along edge (0.0 to 1.0)
            is_start: True if this is a start point, False for destination
            
        Returns:
            int: The best node ID to use for routing
        """
        if not routing_nodes or len(routing_nodes) != 2:
            raise ValueError("routing_nodes must contain exactly 2 nodes")
        
        # Use snap position to pick the closer node
        # snap_position 0.0 = closer to first node, 1.0 = closer to second node
        if snap_position < 0.5:
            # Closer to first node
            return routing_nodes[0]
        else:
            # Closer to second node
            return routing_nodes[1]