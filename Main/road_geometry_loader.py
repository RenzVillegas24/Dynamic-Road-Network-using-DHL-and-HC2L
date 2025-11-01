"""
Road Geometry Loader

Loads and provides access to actual road network geometry for accurate route visualization.
This module solves the problem of linear interpolation by using actual edge data from
the road network graph.
"""

import csv
import os
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class RoadGeometryLoader:
    """
    Loads road network edges and provides geometry for route visualization.
    
    Instead of linearly interpolating between nodes, this class provides
    actual edge connections so routes follow the real road network.
    """
    
    def __init__(self, edges_csv_path: str, nodes_csv_path: str, node_mapping_csv_path: str = None):
        """
        Initialize the road geometry loader.
        
        Args:
            edges_csv_path: Path to edges CSV file (source,target,length,name,highway,oneway,geometry_coords)
            nodes_csv_path: Path to nodes CSV file (node_id,latitude,longitude)
            node_mapping_csv_path: Path to node ID mapping (sequential_id,osm_id)
        """
        self.edges_csv_path = edges_csv_path
        self.nodes_csv_path = nodes_csv_path
        self.node_mapping_csv_path = node_mapping_csv_path
        
        # Node coordinates: node_id -> (lat, lng)
        self.node_coords: Dict[int, Tuple[float, float]] = {}
        
        # Node ID mapping: sequential_id -> osm_id
        self.node_id_to_osm: Dict[int, int] = {}
        self.osm_id_to_node: Dict[int, int] = {}
        
        # Edge lookup: (source, target) -> edge_data (includes geometry)
        self.edges: Dict[Tuple[int, int], Dict] = {}
        
        # Adjacency list for path finding: source -> [(target, length, edge_data)]
        self.adj_list: Dict[int, List[Tuple[int, float, Dict]]] = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load node coordinates, ID mapping, and edge data from CSV files."""
        # Load node ID mapping if available
        if self.node_mapping_csv_path and os.path.exists(self.node_mapping_csv_path):
            with open(self.node_mapping_csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    seq_id = int(row['sequential_id'])
                    osm_id = int(row['osm_id'])
                    self.node_id_to_osm[seq_id] = osm_id
                    self.osm_id_to_node[osm_id] = seq_id
            
            print(f"✅ Loaded {len(self.node_id_to_osm)} node ID mappings")
        
        # Load node coordinates
        if os.path.exists(self.nodes_csv_path):
            with open(self.nodes_csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    node_id = int(row['node_id'])
                    lat = float(row['latitude'])
                    lng = float(row['longitude'])
                    self.node_coords[node_id] = (lat, lng)
            
            print(f"✅ Loaded {len(self.node_coords)} node coordinates")
        else:
            print(f"❌ Nodes file not found: {self.nodes_csv_path}")
            return
        
        # Load edges
        if os.path.exists(self.edges_csv_path):
            import json
            with open(self.edges_csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = int(row['source'])
                    target = int(row['target'])
                    length = float(row['length'])
                    name = row.get('name', 'Unnamed Road')
                    highway = row.get('highway', 'unclassified')
                    oneway = row.get('oneway', '0')
                    
                    # Parse geometry coordinates from JSON
                    geometry_coords = []
                    if 'geometry_coords' in row and row['geometry_coords']:
                        try:
                            geometry_coords = json.loads(row['geometry_coords'])
                        except (json.JSONDecodeError, ValueError):
                            # If geometry parsing fails, fallback to node coordinates
                            geometry_coords = []
                    
                    edge_data = {
                        'source': source,
                        'target': target,
                        'length': length,
                        'name': name,
                        'highway': highway,
                        'oneway': oneway,
                        'geometry_coords': geometry_coords  # List of [lon, lat] pairs
                    }
                    
                    # Store edge
                    self.edges[(source, target)] = edge_data
                    
                    # Add to adjacency list
                    if source not in self.adj_list:
                        self.adj_list[source] = []
                    self.adj_list[source].append((target, length, edge_data))
            
            print(f"✅ Loaded {len(self.edges)} edges with geometry data")
        else:
            print(f"❌ Edges file not found: {self.edges_csv_path}")
    
    def get_node_coords(self, node_id: int) -> Optional[Tuple[float, float]]:
        """
        Get coordinates for a node.
        
        Args:
            node_id: Node ID
            
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        return self.node_coords.get(node_id)
    
    def get_edge(self, source: int, target: int) -> Optional[Dict]:
        """
        Get edge data between two nodes.
        
        Args:
            source: Source node ID
            target: Target node ID
            
        Returns:
            Edge data dict or None if edge doesn't exist
        """
        return self.edges.get((source, target))
    
    def get_path_coordinates(self, path_nodes: List[int], use_osm_geometry: bool = True) -> List[Dict[str, float]]:
        """
        Convert a path (list of node IDs) to GPS coordinates following actual roads.
        
        This method follows the actual edges in the road network using the geometry
        data stored in the edges CSV file (from OSM).
        
        Args:
            path_nodes: List of node IDs representing the path
            use_osm_geometry: If True, use detailed geometry from CSV (includes curves)
            
        Returns:
            List of coordinate dicts with 'lat', 'lng', and optional 'node_id' keys
        """
        if len(path_nodes) < 2:
            # Single node or empty path
            if path_nodes and path_nodes[0] in self.node_coords:
                lat, lng = self.node_coords[path_nodes[0]]
                return [{'lat': lat, 'lng': lng, 'node_id': path_nodes[0]}]
            return []
        
        coordinates = []
        
        for i in range(len(path_nodes) - 1):
            current_node = path_nodes[i]
            next_node = path_nodes[i + 1]
            
            # Get edge data
            edge = self.get_edge(current_node, next_node)
            
            if edge and use_osm_geometry and edge.get('geometry_coords'):
                # Use detailed geometry from CSV (includes road curves)
                geometry_coords = edge['geometry_coords']
                
                # Add all points from this edge's geometry
                # geometry_coords is [[lon1, lat1], [lon2, lat2], ...]
                for coord_pair in geometry_coords:
                    if len(coord_pair) >= 2:
                        lon, lat = coord_pair[0], coord_pair[1]
                        coordinates.append({
                            'lat': lat,
                            'lng': lon
                        })
            else:
                # Fallback: use node coordinates
                if current_node in self.node_coords:
                    lat, lng = self.node_coords[current_node]
                    coordinates.append({
                        'lat': lat,
                        'lng': lng,
                        'node_id': current_node
                    })
        
        # Add final node
        final_node = path_nodes[-1]
        if final_node in self.node_coords:
            lat, lng = self.node_coords[final_node]
            # Check if we haven't already added this point
            if not coordinates or (coordinates[-1]['lat'] != lat or coordinates[-1]['lng'] != lng):
                coordinates.append({
                    'lat': lat,
                    'lng': lng,
                    'node_id': final_node
                })
        
        return coordinates
    
    def get_enhanced_path_coordinates(self, path_nodes: List[int], 
                                     max_segment_length: float = 50.0) -> List[Dict[str, float]]:
        """
        Get path coordinates with optional interpolation for smoother visualization.
        
        This method first gets coordinates following actual roads (with geometry from CSV),
        then optionally interpolates intermediate points on long segments for smoother curves.
        
        Args:
            path_nodes: List of node IDs representing the path
            max_segment_length: Maximum distance (meters) between interpolated points
            
        Returns:
            List of coordinate dicts with 'lat' and 'lng' keys
        """
        # First get the actual road coordinates (with CSV geometry)
        road_coords = self.get_path_coordinates(path_nodes, use_osm_geometry=True)
        
        if len(road_coords) < 2:
            return road_coords
        
        # Optionally add interpolation for smoother visualization
        # (only if segments are very long)
        from geometry_utils import enhance_route_geometry
        
        # Only interpolate if we have very long segments
        enhanced = enhance_route_geometry(road_coords, max_distance=max_segment_length)
        
        return enhanced
    
    def validate_path(self, path_nodes: List[int]) -> Tuple[bool, str]:
        """
        Validate that a path follows actual edges in the road network.
        
        Args:
            path_nodes: List of node IDs representing the path
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(path_nodes) < 2:
            return True, "Path has less than 2 nodes"
        
        missing_edges = []
        missing_nodes = []
        
        for i in range(len(path_nodes) - 1):
            current = path_nodes[i]
            next_node = path_nodes[i + 1]
            
            # Check if nodes exist
            if current not in self.node_coords:
                missing_nodes.append(current)
            if next_node not in self.node_coords:
                missing_nodes.append(next_node)
            
            # Check if edge exists
            if not self.get_edge(current, next_node):
                missing_edges.append((current, next_node))
        
        if missing_nodes or missing_edges:
            error_parts = []
            if missing_nodes:
                error_parts.append(f"Missing nodes: {set(missing_nodes)}")
            if missing_edges:
                error_parts.append(f"Missing edges: {missing_edges[:5]}...")
            return False, "; ".join(error_parts)
        
        return True, "Path is valid"
    
    def get_path_summary(self, path_nodes: List[int]) -> Dict:
        """
        Get summary statistics for a path.
        
        Args:
            path_nodes: List of node IDs representing the path
            
        Returns:
            Dict with path statistics
        """
        if len(path_nodes) < 2:
            return {
                'total_distance_m': 0,
                'num_segments': 0,
                'num_nodes': len(path_nodes)
            }
        
        total_distance = 0.0
        valid_segments = 0
        
        for i in range(len(path_nodes) - 1):
            edge = self.get_edge(path_nodes[i], path_nodes[i + 1])
            if edge:
                total_distance += edge['length']
                valid_segments += 1
        
        return {
            'total_distance_m': total_distance,
            'num_segments': valid_segments,
            'num_nodes': len(path_nodes),
            'invalid_segments': (len(path_nodes) - 1) - valid_segments
        }


# Test function
if __name__ == "__main__":
    from config import Config
    
    print("🧪 Testing Road Geometry Loader...")
    
    # Get node mapping path
    mapping_path = str(Config.NODES_CSV).replace('quezon_city_nodes.csv', 'node_id_mapping.csv')
    
    loader = RoadGeometryLoader(
        str(Config.EDGES_CSV),
        str(Config.NODES_CSV),
        mapping_path
    )
    
    # Test with a simple path
    test_path = [1, 2, 3]
    
    print(f"\n📍 Testing path: {test_path}")
    
    # Get coordinates WITHOUT detailed geometry
    coords_simple = loader.get_path_coordinates(test_path, use_osm_geometry=False)
    print(f"✅ Simple mode (nodes only): {len(coords_simple)} coordinates")
    
    # Get coordinates WITH detailed geometry from CSV
    coords_with_geometry = loader.get_path_coordinates(test_path, use_osm_geometry=True)
    print(f"✅ With CSV geometry (road curves): {len(coords_with_geometry)} coordinates")
    if len(coords_with_geometry) > len(coords_simple):
        print(f"   Improvement: {len(coords_with_geometry) - len(coords_simple)} additional curve points from CSV")
    
    # Validate path
    is_valid, message = loader.validate_path(test_path)
    if is_valid:
        print(f"✅ Path is valid: {message}")
    else:
        print(f"⚠️  Path validation: {message}")
    
    # Get summary
    summary = loader.get_path_summary(test_path)
    print(f"\n📊 Path summary:")
    print(f"   Total distance: {summary['total_distance_m']:.2f} m")
    print(f"   Segments: {summary['num_segments']}")
    print(f"   Nodes: {summary['num_nodes']}")
