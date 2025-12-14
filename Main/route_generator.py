# route_generator.py - Generate random routes for experiments
"""
Route Generator for Experiment Preset

Generates random routes with all required parameters for DHL/HC2L routing APIs:
- start_pin_lat, start_pin_lng, start_snap_lat, start_snap_lng
- start_edge_source, start_edge_target, start_edge_oneway
- dest_pin_lat, dest_pin_lng, dest_snap_lat, dest_snap_lng
- dest_edge_source, dest_edge_target, dest_edge_oneway

Routes are generated within the Quezon City bounding box and saved to JSON.
"""

import json
import random
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple
from console_formatter import get_logger

logger = get_logger("RouteGenerator")

# Quezon City bounding box (from config.py)
BBOX = {
    "min_lat": 14.5760,
    "max_lat": 14.7845,
    "min_lng": 121.0049,
    "max_lng": 121.1464
}

class RouteGenerator:
    """Generate random routes for experiments"""
    
    def __init__(self, nodes_csv: str, edges_csv: str):
        """
        Initialize route generator with network data
        
        Args:
            nodes_csv: Path to nodes CSV file
            edges_csv: Path to edges CSV file
        """
        self.nodes_csv = nodes_csv
        self.edges_csv = edges_csv
        self.nodes_df = None
        self.edges_df = None
        self.valid_nodes = []
        self.edge_lookup = {}
        
        self._load_network_data()
    
    def _load_network_data(self):
        """Load nodes and edges from CSV files"""
        try:
            logger.info(f"Loading nodes from: {self.nodes_csv}")
            self.nodes_df = pd.read_csv(self.nodes_csv)
            
            logger.info(f"Loading edges from: {self.edges_csv}")
            self.edges_df = pd.read_csv(self.edges_csv)
            
            # Filter nodes within bounding box
            self.valid_nodes = self.nodes_df[
                (self.nodes_df['lat'] >= BBOX['min_lat']) &
                (self.nodes_df['lat'] <= BBOX['max_lat']) &
                (self.nodes_df['lon'] >= BBOX['min_lng']) &
                (self.nodes_df['lon'] <= BBOX['max_lng'])
            ].copy()
            
            # Create edge lookup for connectivity
            for _, edge in self.edges_df.iterrows():
                source = edge['source']
                target = edge['target']
                oneway = edge.get('oneway', 0)
                
                if source not in self.edge_lookup:
                    self.edge_lookup[source] = []
                self.edge_lookup[source].append({
                    'target': target,
                    'oneway': oneway
                })
            
            logger.success(f"Loaded {len(self.nodes_df)} nodes, {len(self.edges_df)} edges")
            logger.info(f"Valid nodes in bbox: {len(self.valid_nodes)}")
            
        except Exception as e:
            logger.error(f"Failed to load network data: {e}")
            raise
    
    def _get_random_edge(self) -> Tuple[Dict, Dict, int]:
        """
        Get a random edge with source and target nodes
        
        Returns:
            Tuple of (source_node, target_node, oneway)
        """
        # Get random node with outgoing edges
        nodes_with_edges = [n for n in self.valid_nodes['node_id'].values if n in self.edge_lookup]
        
        if not nodes_with_edges:
            raise ValueError("No valid nodes with edges found")
        
        source_id = random.choice(nodes_with_edges)
        
        # Get random outgoing edge
        edges = self.edge_lookup[source_id]
        edge_info = random.choice(edges)
        target_id = edge_info['target']
        oneway = edge_info['oneway']
        
        # Get node details
        source_node = self.nodes_df[self.nodes_df['node_id'] == source_id].iloc[0].to_dict()
        target_node = self.nodes_df[self.nodes_df['node_id'] == target_id].iloc[0].to_dict()
        
        return source_node, target_node, oneway
    
    def _generate_snap_point(self, node1: Dict, node2: Dict) -> Tuple[float, float]:
        """
        Generate snap point along edge between two nodes
        
        Args:
            node1: Source node
            node2: Target node
            
        Returns:
            Tuple of (snap_lat, snap_lng)
        """
        # Random position along edge (0.0 to 1.0)
        t = random.uniform(0.1, 0.9)
        
        snap_lat = node1['lat'] + t * (node2['lat'] - node1['lat'])
        snap_lng = node1['lon'] + t * (node2['lon'] - node1['lon'])
        
        return snap_lat, snap_lng
    
    def generate_route(self) -> Dict:
        """
        Generate a single random route
        
        Returns:
            Dictionary with all route parameters
        """
        # Generate start edge
        start_source, start_target, start_oneway = self._get_random_edge()
        start_snap_lat, start_snap_lng = self._generate_snap_point(start_source, start_target)
        
        # Generate destination edge (different from start)
        dest_source, dest_target, dest_oneway = self._get_random_edge()
        
        # Ensure dest is different from start
        max_attempts = 10
        attempts = 0
        while (dest_source['node_id'] == start_source['node_id'] and 
               dest_target['node_id'] == start_target['node_id'] and 
               attempts < max_attempts):
            dest_source, dest_target, dest_oneway = self._get_random_edge()
            attempts += 1
        
        dest_snap_lat, dest_snap_lng = self._generate_snap_point(dest_source, dest_target)
        
        # Pin points are same as snap points for simplicity
        route = {
            "start_pin_lat": start_snap_lat,
            "start_pin_lng": start_snap_lng,
            "start_snap_lat": start_snap_lat,
            "start_snap_lng": start_snap_lng,
            "start_edge_source": int(start_source['node_id']),
            "start_edge_target": int(start_target['node_id']),
            "start_edge_oneway": int(start_oneway),
            
            "dest_pin_lat": dest_snap_lat,
            "dest_pin_lng": dest_snap_lng,
            "dest_snap_lat": dest_snap_lat,
            "dest_snap_lng": dest_snap_lng,
            "dest_edge_source": int(dest_source['node_id']),
            "dest_edge_target": int(dest_target['node_id']),
            "dest_edge_oneway": int(dest_oneway)
        }
        
        return route
    
    def generate_routes(self, count: int) -> List[Dict]:
        """
        Generate multiple random routes
        
        Args:
            count: Number of routes to generate
            
        Returns:
            List of route dictionaries
        """
        logger.info(f"Generating {count} routes...")
        
        routes = []
        for i in range(count):
            try:
                route = self.generate_route()
                route['route_id'] = i
                routes.append(route)
                
                if (i + 1) % 100 == 0:
                    logger.info(f"Generated {i + 1}/{count} routes")
                    
            except Exception as e:
                logger.error(f"Error generating route {i}: {e}")
                continue
        
        logger.success(f"Successfully generated {len(routes)} routes")
        return routes
    
    def save_routes(self, routes: List[Dict], output_file: str):
        """
        Save routes to JSON file
        
        Args:
            routes: List of route dictionaries
            output_file: Path to output JSON file
        """
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(routes, f, indent=2)
            
            logger.success(f"Saved {len(routes)} routes to: {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save routes: {e}")
            raise


def generate_preset_routes(
    nodes_csv: str,
    edges_csv: str,
    output_file: str,
    route_count: int = 3000
) -> List[Dict]:
    """
    Generate routes for preset experiment
    
    Args:
        nodes_csv: Path to nodes CSV
        edges_csv: Path to edges CSV
        output_file: Path to output JSON file
        route_count: Number of routes to generate (default 3000)
        
    Returns:
        List of generated routes
    """
    generator = RouteGenerator(nodes_csv, edges_csv)
    routes = generator.generate_routes(route_count)
    generator.save_routes(routes, output_file)
    
    return routes


if __name__ == "__main__":
    # Test route generation
    from config import Config
    
    nodes_csv = Path(Config.DATA_DIR) / "raw" / "quezon_city_nodes.csv"
    edges_csv = Path(Config.DATA_DIR) / "raw" / "quezon_city_edges.csv"
    output_file = Path(Config.DATA_DIR) / "experiments" / "preset" / "routes.json"
    
    routes = generate_preset_routes(str(nodes_csv), str(edges_csv), str(output_file), 3000)
    print(f"Generated {len(routes)} routes")
