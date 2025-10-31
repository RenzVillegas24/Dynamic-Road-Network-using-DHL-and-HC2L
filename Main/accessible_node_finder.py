"""
Accessible Node Finder - One-Way Street Aware Node Selection

This module provides advanced nearest node finding that considers:
1. One-way street directions
2. Whether the node is being used as a start or destination point
3. Accessibility/reachability of nodes based on road network topology

Key Concepts:
- Start node: Must have outgoing edges that can reach the destination
- Destination node: Must be reachable via incoming edges
- One-way values: 0 (bidirectional), 1 (forward only), -1 (reverse only)
"""

import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
from typing import Tuple, Optional, Dict, Set, List
from collections import defaultdict


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate distance between two points on Earth in meters"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of Earth in meters
    return c * r


class AccessibleNodeFinder:
    """
    Find nearest nodes while considering one-way street restrictions
    """
    
    def __init__(self, nodes_csv_path: str, edges_csv_path: str):
        """
        Initialize with node and edge data
        
        Args:
            nodes_csv_path: Path to nodes CSV (node_id, latitude, longitude)
            edges_csv_path: Path to edges CSV (source, target, length, name, highway, oneway)
        """
        self.nodes_df = pd.read_csv(nodes_csv_path)
        self.edges_df = pd.read_csv(edges_csv_path)
        
        # Build adjacency lists for connectivity analysis
        self._build_adjacency_lists()
        
        print(f"✅ Loaded {len(self.nodes_df)} nodes and {len(self.edges_df)} edges")
        print(f"   One-way edges: {len(self.edges_df[self.edges_df['oneway'] != 0])}")
    
    def _build_adjacency_lists(self):
        """
        Build forward and backward adjacency lists considering one-way streets
        
        Forward edges: edges you can travel along (source → target)
        Backward edges: edges you can travel against (for bidirectional roads)
        """
        self.forward_adj = defaultdict(list)  # source -> [(target, edge_data), ...]
        self.backward_adj = defaultdict(list)  # target -> [(source, edge_data), ...]
        
        for _, edge in self.edges_df.iterrows():
            source = int(edge['source'])
            target = int(edge['target'])
            oneway = int(edge.get('oneway', 0))
            
            edge_info = {
                'target': target,
                'source': source,
                'length': edge['length'],
                'name': edge.get('name', 'Unnamed Road'),
                'oneway': oneway
            }
            
            if oneway == 1:
                # Forward only (source → target)
                self.forward_adj[source].append((target, edge_info))
            elif oneway == -1:
                # Reverse only (target → source)
                self.backward_adj[source].append((target, edge_info))
            else:
                # Bidirectional (oneway == 0)
                self.forward_adj[source].append((target, edge_info))
                self.backward_adj[source].append((target, edge_info))
    
    def _get_outgoing_neighbors(self, node_id: int) -> Set[int]:
        """
        Get all nodes reachable from this node (considering one-way streets)
        
        Args:
            node_id: Node to check
            
        Returns:
            Set of node IDs that can be reached from this node
        """
        neighbors = set()
        
        # Add forward neighbors
        for target, _ in self.forward_adj.get(node_id, []):
            neighbors.add(target)
        
        # Add backward neighbors (for bidirectional roads)
        for target, edge_info in self.backward_adj.get(node_id, []):
            # Only add if it's truly bidirectional (oneway == 0)
            if edge_info['oneway'] == 0:
                neighbors.add(target)
        
        return neighbors
    
    def _get_incoming_neighbors(self, node_id: int) -> Set[int]:
        """
        Get all nodes that can reach this node (considering one-way streets)
        
        Args:
            node_id: Node to check
            
        Returns:
            Set of node IDs that can reach this node
        """
        neighbors = set()
        
        # Nodes that have this node as a forward target
        for source, edges in self.forward_adj.items():
            for target, edge_info in edges:
                if target == node_id:
                    neighbors.add(source)
        
        # Nodes that have this node as a backward target (bidirectional)
        for source, edges in self.backward_adj.items():
            for target, edge_info in edges:
                if target == node_id and edge_info['oneway'] == 0:
                    neighbors.add(source)
        
        return neighbors
    
    def _is_node_accessible_as_start(self, node_id: int) -> bool:
        """
        Check if a node can be used as a start point
        
        A node is valid as a start point if it has at least one outgoing edge
        
        Args:
            node_id: Node ID to check
            
        Returns:
            True if node has outgoing edges
        """
        return len(self._get_outgoing_neighbors(node_id)) > 0
    
    def _is_node_accessible_as_destination(self, node_id: int) -> bool:
        """
        Check if a node can be used as a destination point
        
        A node is valid as a destination if it has at least one incoming edge
        
        Args:
            node_id: Node ID to check
            
        Returns:
            True if node has incoming edges
        """
        return len(self._get_incoming_neighbors(node_id)) > 0
    
    def find_nearest_accessible_node(self, lat: float, lng: float, 
                                    is_start_point: bool = True,
                                    max_distance_m: float = 1000,
                                    max_candidates: int = 10) -> Tuple[Optional[int], float, Dict]:
        """
        Find nearest node that is accessible based on its role (start vs destination)
        
        Algorithm:
        1. Find N nearest nodes by Euclidean distance
        2. Filter by accessibility (has outgoing edges for start, incoming for destination)
        3. Return closest accessible node
        
        Args:
            lat, lng: GPS coordinates
            is_start_point: True if finding start node, False for destination
            max_distance_m: Maximum acceptable distance in meters
            max_candidates: Number of nearest candidates to check
            
        Returns:
            tuple: (node_id, distance_m, metadata_dict) or (None, distance, metadata)
            
        Metadata includes:
            - 'accessible': bool - whether node meets accessibility criteria
            - 'outgoing_count': int - number of outgoing edges
            - 'incoming_count': int - number of incoming edges
            - 'candidates_checked': int - how many nodes were evaluated
            - 'selection_reason': str - why this node was selected
        """
        # Calculate distances to all nodes
        distances = []
        for _, node in self.nodes_df.iterrows():
            node_id = int(node['node_id'])
            dist = haversine(lng, lat, node['longitude'], node['latitude'])
            distances.append((node_id, dist))
        
        # Sort by distance and get top candidates
        distances.sort(key=lambda x: x[1])
        candidates = distances[:max_candidates]
        
        # Filter by accessibility
        accessible_nodes = []
        checked_count = 0
        
        for node_id, dist in candidates:
            checked_count += 1
            
            outgoing = self._get_outgoing_neighbors(node_id)
            incoming = self._get_incoming_neighbors(node_id)
            
            outgoing_count = len(outgoing)
            incoming_count = len(incoming)
            
            # Check accessibility based on role
            if is_start_point:
                is_accessible = outgoing_count > 0
            else:
                is_accessible = incoming_count > 0
            
            if is_accessible:
                accessible_nodes.append({
                    'node_id': node_id,
                    'distance': dist,
                    'outgoing_count': outgoing_count,
                    'incoming_count': incoming_count
                })
        
        # Select best accessible node
        if not accessible_nodes:
            # No accessible nodes found in candidates
            metadata = {
                'accessible': False,
                'outgoing_count': 0,
                'incoming_count': 0,
                'candidates_checked': checked_count,
                'selection_reason': f'No accessible {"start" if is_start_point else "destination"} nodes found within {max_candidates} nearest candidates',
                'role': 'start' if is_start_point else 'destination'
            }
            
            # Return nearest node anyway with warning
            if candidates:
                nearest_id, nearest_dist = candidates[0]
                return nearest_id, nearest_dist, metadata
            else:
                return None, float('inf'), metadata
        
        # Return closest accessible node
        best = min(accessible_nodes, key=lambda x: x['distance'])
        
        if best['distance'] > max_distance_m:
            # Too far from any accessible road
            return None, best['distance'], {
                'accessible': True,
                'outgoing_count': best['outgoing_count'],
                'incoming_count': best['incoming_count'],
                'candidates_checked': checked_count,
                'selection_reason': f'Nearest accessible node is {best["distance"]:.0f}m away (max: {max_distance_m}m)',
                'role': 'start' if is_start_point else 'destination'
            }
        
        metadata = {
            'accessible': True,
            'outgoing_count': best['outgoing_count'],
            'incoming_count': best['incoming_count'],
            'candidates_checked': checked_count,
            'selection_reason': f'Selected as nearest accessible {"start" if is_start_point else "destination"} node ({best["distance"]:.1f}m away)',
            'role': 'start' if is_start_point else 'destination'
        }
        
        return best['node_id'], best['distance'], metadata
    
    def get_node_info(self, node_id: int) -> Dict:
        """
        Get detailed information about a node's connectivity
        
        Args:
            node_id: Node ID to query
            
        Returns:
            Dictionary with node information
        """
        node_data = self.nodes_df[self.nodes_df['node_id'] == node_id]
        
        if node_data.empty:
            return {'exists': False}
        
        node_row = node_data.iloc[0]
        outgoing = self._get_outgoing_neighbors(node_id)
        incoming = self._get_incoming_neighbors(node_id)
        
        return {
            'exists': True,
            'node_id': int(node_id),
            'latitude': float(node_row['latitude']),
            'longitude': float(node_row['longitude']),
            'outgoing_edges': len(outgoing),
            'incoming_edges': len(incoming),
            'outgoing_neighbors': list(outgoing),
            'incoming_neighbors': list(incoming),
            'can_be_start': len(outgoing) > 0,
            'can_be_destination': len(incoming) > 0,
            'is_dead_end': len(outgoing) == 0 or len(incoming) == 0
        }


# Testing
if __name__ == "__main__":
    print("=" * 70)
    print("Testing Accessible Node Finder")
    print("=" * 70)
    print()
    
    # Initialize
    nodes_path = "data/raw/quezon_city_nodes.csv"
    edges_path = "data/raw/quezon_city_edges.csv"
    
    finder = AccessibleNodeFinder(nodes_path, edges_path)
    
    # Test location: Commonwealth Avenue area
    test_lat = 14.6538
    test_lng = 121.0685
    
    print()
    print("Test 1: Finding START node")
    print("-" * 70)
    start_id, start_dist, start_meta = finder.find_nearest_accessible_node(
        test_lat, test_lng, is_start_point=True
    )
    print(f"   Location: ({test_lat}, {test_lng})")
    print(f"   Selected Node: {start_id}")
    print(f"   Distance: {start_dist:.1f}m")
    print(f"   Outgoing edges: {start_meta['outgoing_count']}")
    print(f"   Incoming edges: {start_meta['incoming_count']}")
    print(f"   Reason: {start_meta['selection_reason']}")
    
    print()
    print("Test 2: Finding DESTINATION node")
    print("-" * 70)
    dest_id, dest_dist, dest_meta = finder.find_nearest_accessible_node(
        test_lat, test_lng, is_start_point=False
    )
    print(f"   Location: ({test_lat}, {test_lng})")
    print(f"   Selected Node: {dest_id}")
    print(f"   Distance: {dest_dist:.1f}m")
    print(f"   Outgoing edges: {dest_meta['outgoing_count']}")
    print(f"   Incoming edges: {dest_meta['incoming_count']}")
    print(f"   Reason: {dest_meta['selection_reason']}")
    
    print()
    print("Test 3: Node Information Lookup")
    print("-" * 70)
    if start_id:
        info = finder.get_node_info(start_id)
        print(f"   Node {start_id}:")
        print(f"   - Can be start: {info['can_be_start']}")
        print(f"   - Can be destination: {info['can_be_destination']}")
        print(f"   - Is dead end: {info['is_dead_end']}")
        print(f"   - Outgoing neighbors: {info['outgoing_neighbors'][:5]}...")
        print(f"   - Incoming neighbors: {info['incoming_neighbors'][:5]}...")
    
    print()
    print("=" * 70)
    print("✅ Tests complete!")
    print("=" * 70)
