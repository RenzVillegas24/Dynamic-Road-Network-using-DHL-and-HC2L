# road_name_mapper.py - Map nodes to road names for route display
import csv
import os
from typing import Dict, List, Tuple, Optional

class RoadNameMapper:
    """
    Maps node-to-node transitions to road names using the edges CSV data
    """
    
    def __init__(self, edges_csv_path: str = '../data/raw/quezon_city_edges.csv'):
        """Initialize with path to edges CSV file"""
        self.edges_csv_path = edges_csv_path
        self.edge_to_road = {}  # (source, target) -> road_name
        self.node_connections = {}  # node_id -> [(connected_node, road_name), ...]
        self._load_road_mapping()
    
    def _load_road_mapping(self):
        """Load road name mapping from edges CSV"""
        try:
            if not os.path.exists(self.edges_csv_path):
                print(f"⚠️  Warning: Edges file not found at {self.edges_csv_path}")
                return
            
            edge_count = 0
            with open(self.edges_csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = int(row['source'])
                    target = int(row['target'])
                    road_name = row['name'].strip() if row['name'].strip() else 'Unnamed Road'
                    highway_type = row['highway'] if 'highway' in row else 'unclassified'
                    
                    # Store bidirectional mapping (most roads are bidirectional)
                    self.edge_to_road[(source, target)] = {
                        'name': road_name,
                        'highway': highway_type,
                        'length': float(row['length']) if row['length'] else 0.0
                    }
                    self.edge_to_road[(target, source)] = {
                        'name': road_name,
                        'highway': highway_type,
                        'length': float(row['length']) if row['length'] else 0.0
                    }
                    
                    # Build node connections for path analysis
                    if source not in self.node_connections:
                        self.node_connections[source] = []
                    if target not in self.node_connections:
                        self.node_connections[target] = []
                    
                    self.node_connections[source].append((target, road_name))
                    self.node_connections[target].append((source, road_name))
                    
                    edge_count += 1
            
            print(f"✅ Loaded {edge_count} road segments with names")
            print(f"📍 Total mapped edges: {len(self.edge_to_road)}")
            
        except Exception as e:
            print(f"❌ Error loading road mapping: {e}")
            self.edge_to_road = {}
            self.node_connections = {}
    
    def get_road_name(self, source_node: int, target_node: int) -> str:
        """Get road name for a node-to-node transition"""
        road_info = self.edge_to_road.get((source_node, target_node))
        if road_info:
            return road_info['name']
        return f"Unknown Road (Node {source_node} → {target_node})"
    
    def get_road_info(self, source_node: int, target_node: int) -> Dict:
        """Get detailed road information for a node-to-node transition"""
        road_info = self.edge_to_road.get((source_node, target_node))
        if road_info:
            return road_info
        return {
            'name': f"Unknown Road (Node {source_node} → {target_node})",
            'highway': 'unknown',
            'length': 0.0
        }
    
    def get_route_with_road_names(self, node_path: List[int]) -> List[Dict]:
        """
        Convert a node path to a list of road segments with names
        
        Args:
            node_path: List of node IDs in order
            
        Returns:
            List of dictionaries with road information for each segment
        """
        if len(node_path) < 2:
            return []
        
        road_segments = []
        
        for i in range(len(node_path) - 1):
            source_node = node_path[i]
            target_node = node_path[i + 1]
            
            road_info = self.get_road_info(source_node, target_node)
            
            segment = {
                'segment_number': i + 1,
                'from_node': source_node,
                'to_node': target_node,
                'road_name': road_info['name'],
                'highway_type': road_info['highway'],
                'length_meters': road_info['length'],
                'instruction': f"Continue on {road_info['name']}"
            }
            
            road_segments.append(segment)
        
        # Merge consecutive segments on the same road
        return self._merge_consecutive_roads(road_segments)
    
    def _merge_consecutive_roads(self, segments: List[Dict]) -> List[Dict]:
        """Merge consecutive segments that are on the same road"""
        if not segments:
            return []
        
        merged = []
        current_segment = segments[0].copy()
        
        for i in range(1, len(segments)):
            next_segment = segments[i]
            
            # If same road name, merge the segments
            if (current_segment['road_name'] == next_segment['road_name'] and 
                current_segment['road_name'] != 'Unknown Road'):
                
                # Update the end node and total length
                current_segment['to_node'] = next_segment['to_node']
                current_segment['length_meters'] += next_segment['length_meters']
                current_segment['instruction'] = f"Continue on {current_segment['road_name']} for {current_segment['length_meters']:.0f}m"
            else:
                # Different road, add current segment and start new one
                merged.append(current_segment)
                current_segment = next_segment.copy()
        
        # Add the last segment
        merged.append(current_segment)
        
        # Update instructions for merged segments
        for i, segment in enumerate(merged):
            if i == 0:
                segment['instruction'] = f"Start on {segment['road_name']}"
            elif i == len(merged) - 1:
                segment['instruction'] = f"Continue on {segment['road_name']} to destination"
            else:
                segment['instruction'] = f"Turn onto {segment['road_name']}"
        
        return merged
    
    def get_route_summary_text(self, node_path: List[int]) -> str:
        """Get a human-readable route summary with road names"""
        road_segments = self.get_route_with_road_names(node_path)
        
        if not road_segments:
            return "No route information available"
        
        # Create a concise route description
        road_names = []
        for segment in road_segments:
            if segment['road_name'] not in road_names and 'Unknown Road' not in segment['road_name']:
                road_names.append(segment['road_name'])
        
        if len(road_names) <= 3:
            return " → ".join(road_names)
        else:
            return f"{road_names[0]} → ... → {road_names[-1]} ({len(road_names)} roads)"
    
    def get_turn_by_turn_directions(self, node_path: List[int]) -> List[str]:
        """Get turn-by-turn directions as a list of strings"""
        road_segments = self.get_route_with_road_names(node_path)
        
        directions = []
        for i, segment in enumerate(road_segments):
            direction = f"{i + 1}. {segment['instruction']}"
            if segment['length_meters'] > 0:
                direction += f" ({segment['length_meters']:.0f}m)"
            directions.append(direction)
        
        return directions

# Test function
if __name__ == "__main__":
    pass