"""
Traffic Hash-Based Matcher
===========================

Uses pre-matched edges from matched_edges.csv to map HERE API traffic data
to OSM road network edges via location hashing.

This replaces the geospatial matching approach with a simple hash lookup,
where traffic location objects are hashed to create stable identifiers.

Hash Algorithm:
- Matches JavaScript implementation from map_matcher.html
- JSON.stringify the location object
- Apply Java-style string hash (((hash << 5) - hash) + charCode)
- Convert to base-36 string

Flow:
1. Load matched_edges.csv into memory (hash -> list of edges)
2. Fetch HERE API traffic data
3. Hash each traffic location object
4. Lookup matched edges by hash
5. Generate traffic CSV with edge data + traffic metrics
"""

import json
import re
import hashlib
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TrafficEdge:
    """Represents a traffic-matched OSM edge"""
    traffic_hash: str
    source: int
    target: int
    source_lat: float
    source_lon: float
    target_lat: float
    target_lon: float
    
    # Traffic metrics (populated from HERE API)
    speed_kph: float = 0.0
    freeFlow_kph: float = 0.0
    jamFactor: float = 0.0
    isClosed: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV export"""
        return {
            'traffic_hash': self.traffic_hash,
            'source_lat': self.source_lat,
            'source_lon': self.source_lon,
            'target_lat': self.target_lat,
            'target_lon': self.target_lon,
            'source': self.source,
            'target': self.target,
            'speed_kph': self.speed_kph,
            'freeFlow_kph': self.freeFlow_kph,
            'jamFactor': self.jamFactor,
            'isClosed': self.isClosed
        }


class TrafficHashMatcher:
    """
    Hash-based matcher for HERE traffic data using pre-matched edges
    """
    
    def __init__(self, matched_edges_csv: Path):
        """
        Initialize matcher with pre-matched edges
        
        Args:
            matched_edges_csv: Path to matched_edges.csv file
        """
        self.matched_edges_csv = matched_edges_csv
        self.hash_to_edges: Dict[str, List[TrafficEdge]] = {}
        self._load_matched_edges()
        
        print(f"✅ TrafficHashMatcher initialized: {len(self.hash_to_edges)} unique traffic hashes, "
              f"{sum(len(edges) for edges in self.hash_to_edges.values())} total edges")
    
    def _load_matched_edges(self):
        """Load matched edges CSV into hash lookup table"""
        print(f"📂 Loading matched edges from {self.matched_edges_csv}...")
        
        df = pd.read_csv(self.matched_edges_csv)
        
        # Group by traffic_hash
        for _, row in df.iterrows():
            traffic_hash = row['traffic_hash']
            
            edge = TrafficEdge(
                traffic_hash=traffic_hash,
                source=int(row['source']),
                target=int(row['target']),
                source_lat=float(row['source_lat']),
                source_lon=float(row['source_lon']),
                target_lat=float(row['target_lat']),
                target_lon=float(row['target_lon'])
            )
            
            if traffic_hash not in self.hash_to_edges:
                self.hash_to_edges[traffic_hash] = []
            
            self.hash_to_edges[traffic_hash].append(edge)
        
        print(f"   Loaded {len(self.hash_to_edges)} unique traffic segments")
    
    @staticmethod
    def hash_location_javascript_style(location: Dict) -> str:
        """
        Recreate JavaScript hashing algorithm from map_matcher.html
        
        JavaScript implementation:
        ```javascript
        function hashLocation(location) {
            const str = JSON.stringify(location);
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            return Math.abs(hash).toString(36);
        }
        ```
        
        Args:
            location: The location object from traffic JSON
            
        Returns:
            A base-36 string hash
        """
        # Custom JSON encoder to match JavaScript behavior
        class JavaScriptEncoder(json.JSONEncoder):
            def encode(self, obj):
                if isinstance(obj, float) and obj == int(obj):
                    return str(int(obj))
                return super().encode(obj)
            
            def iterencode(self, obj, _one_shot=False):
                for chunk in super().iterencode(obj, _one_shot):
                    # Remove .0 from integer floats
                    yield re.sub(r'(\d+)\.0\b', r'\1', chunk)
        
        # Match JavaScript JSON.stringify behavior
        json_str = json.dumps(location, separators=(',', ':'), cls=JavaScriptEncoder)
        json_str = re.sub(r'(\d+)\.0\b', r'\1', json_str)
        
        hash_value = 0
        for char in json_str:
            char_code = ord(char)
            hash_value = ((hash_value << 5) - hash_value) + char_code
            # Simulate JavaScript 32-bit signed integer overflow
            hash_value = int(hash_value) & 0xffffffff
            if hash_value >= 0x80000000:
                hash_value -= 0x100000000
        
        # Convert to base-36
        abs_hash = abs(hash_value)
        if abs_hash == 0:
            return '0'
        
        digits = '0123456789abcdefghijklmnopqrstuvwxyz'
        result = ''
        while abs_hash > 0:
            result = digits[abs_hash % 36] + result
            abs_hash //= 36
        
        return result
    
    def match_traffic_flow_item(self, flow_item: Dict) -> List[TrafficEdge]:
        """
        Match a single HERE API flow item to edges by hashing its location
        
        Args:
            flow_item: A single item from HERE API flow results
            
        Returns:
            List of matched TrafficEdge objects with traffic metrics populated
        """
        location = flow_item.get('location')
        if not location:
            return []
        
        # Hash the location
        traffic_hash = self.hash_location_javascript_style(location)
        
        # Lookup matched edges
        matched_edges = self.hash_to_edges.get(traffic_hash, [])
        
        if not matched_edges:
            # print(f"⚠️  No match for hash: {traffic_hash}")
            return []
        
        # Extract traffic metrics from HERE API
        current_flow = flow_item.get('currentFlow', {})
        free_flow = flow_item.get('freeFlow', {})
        
        speed_kph = current_flow.get('speed', 0.0)
        free_flow_kph = free_flow.get('speed', 0.0)
        jam_factor = current_flow.get('jamFactor', 0.0)
        
        # Populate traffic metrics for all matched edges
        result_edges = []
        for edge in matched_edges:
            # Create a copy with traffic data
            traffic_edge = TrafficEdge(
                traffic_hash=edge.traffic_hash,
                source=edge.source,
                target=edge.target,
                source_lat=edge.source_lat,
                source_lon=edge.source_lon,
                target_lat=edge.target_lat,
                target_lon=edge.target_lon,
                speed_kph=speed_kph,
                freeFlow_kph=free_flow_kph,
                jamFactor=jam_factor,
                isClosed=False  # Flow data doesn't indicate closures
            )
            result_edges.append(traffic_edge)
        
        return result_edges
    
    def match_traffic_incident_item(self, incident_item: Dict) -> List[TrafficEdge]:
        """
        Match a single HERE API incident item to edges by hashing its location
        
        Args:
            incident_item: A single item from HERE API incidents results
            
        Returns:
            List of matched TrafficEdge objects with traffic metrics populated
        """
        location = incident_item.get('location')
        if not location:
            return []
        
        # Hash the location
        traffic_hash = self.hash_location_javascript_style(location)
        
        # Lookup matched edges
        matched_edges = self.hash_to_edges.get(traffic_hash, [])
        
        if not matched_edges:
            return []
        
        # Extract incident info
        incident_details = incident_item.get('incidentDetails', {})
        
        # Determine if road is closed
        is_closed = 'ROAD_CLOSED' in str(incident_details.get('type', ''))
        
        # Estimate jam factor from criticality
        criticality = incident_details.get('criticality', 0)
        jam_factor = min(criticality / 10.0 * 10.0, 10.0)  # Scale to 0-10
        
        # Populate traffic metrics
        result_edges = []
        for edge in matched_edges:
            traffic_edge = TrafficEdge(
                traffic_hash=edge.traffic_hash,
                source=edge.source,
                target=edge.target,
                source_lat=edge.source_lat,
                source_lon=edge.source_lon,
                target_lat=edge.target_lat,
                target_lon=edge.target_lon,
                speed_kph=0.0 if is_closed else 10.0,  # Low speed for incidents
                freeFlow_kph=50.0,  # Assume reasonable free flow
                jamFactor=jam_factor,
                isClosed=is_closed
            )
            result_edges.append(traffic_edge)
        
        return result_edges
    
    def batch_match_flow_data(self, flow_results: List[Dict]) -> List[TrafficEdge]:
        """
        Match all flow results to edges
        
        Args:
            flow_results: List of flow items from HERE API
            
        Returns:
            List of all matched TrafficEdge objects
        """
        all_edges = []
        matched_count = 0
        
        for flow_item in flow_results:
            edges = self.match_traffic_flow_item(flow_item)
            if edges:
                matched_count += 1
                all_edges.extend(edges)
        
        print(f"   ✅ Matched {matched_count}/{len(flow_results)} flow items "
              f"-> {len(all_edges)} total edges")
        
        return all_edges
    
    def batch_match_incident_data(self, incident_results: List[Dict]) -> List[TrafficEdge]:
        """
        Match all incident results to edges
        
        Args:
            incident_results: List of incident items from HERE API
            
        Returns:
            List of all matched TrafficEdge objects
        """
        all_edges = []
        matched_count = 0
        
        for incident_item in incident_results:
            edges = self.match_traffic_incident_item(incident_item)
            if edges:
                matched_count += 1
                all_edges.extend(edges)
        
        print(f"   ✅ Matched {matched_count}/{len(incident_results)} incidents "
              f"-> {len(all_edges)} total edges")
        
        return all_edges
    
    def get_stats(self) -> Dict:
        """Get matcher statistics"""
        total_edges = sum(len(edges) for edges in self.hash_to_edges.values())
        return {
            'unique_hashes': len(self.hash_to_edges),
            'total_edges': total_edges,
            'avg_edges_per_hash': total_edges / len(self.hash_to_edges) if self.hash_to_edges else 0
        }


def test_traffic_hash_matcher():
    """Test the hash matcher with sample data"""
    from config import Config
    
    print("\n" + "="*70)
    print("Testing TrafficHashMatcher")
    print("="*70 + "\n")
    
    # Initialize matcher
    matched_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
    matcher = TrafficHashMatcher(matched_csv)
    
    # Show stats
    stats = matcher.get_stats()
    print(f"\n📊 Matcher Statistics:")
    print(f"   Unique traffic hashes: {stats['unique_hashes']}")
    print(f"   Total mapped edges: {stats['total_edges']}")
    print(f"   Avg edges per hash: {stats['avg_edges_per_hash']:.1f}")
    
    # Test with sample HERE API data
    sample_location = {
        "shape": {
            "links": [
                {
                    "points": [
                        {"lat": 14.6293428, "lng": 121.0409496},
                        {"lat": 14.6286652, "lng": 121.0386239}
                    ]
                }
            ]
        }
    }
    
    sample_flow = {
        "location": sample_location,
        "currentFlow": {"speed": 25.5, "jamFactor": 6.2},
        "freeFlow": {"speed": 50.0}
    }
    
    print(f"\n🧪 Testing with sample flow data...")
    edges = matcher.match_traffic_flow_item(sample_flow)
    
    print(f"   Found {len(edges)} matched edges")
    for edge in edges[:3]:
        print(f"      {edge.source} -> {edge.target}: "
              f"{edge.speed_kph:.1f} km/h (jam: {edge.jamFactor:.1f})")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    test_traffic_hash_matcher()
