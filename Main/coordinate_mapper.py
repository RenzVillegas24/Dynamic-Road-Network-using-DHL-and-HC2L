# coordinate_mapper.py
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt

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
        
    def find_nearest_node(self, lat, lng, max_distance_m=500):
        """Find nearest graph node to given coordinates"""
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