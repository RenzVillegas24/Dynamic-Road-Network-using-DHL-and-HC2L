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