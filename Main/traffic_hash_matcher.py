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

from console_formatter import get_logger

logger = get_logger("TrafficHashMatcher")

@dataclass
class TrafficEdge:
    """Represents a traffic-matched OSM edge with separated flow and incident data"""
    id_hash: str
    source: int
    target: int
    source_lat: float
    source_lon: float
    target_lat: float
    target_lon: float
    
    # FLOW DATA (from HERE API flow results)
    flow_speed_kph: float = 0.0
    flow_free_flow_kph: float = 0.0
    flow_jam_factor: float = 0.0
    flow_confidence: float = 0.0
    flow_traversability: str = 'open'
    
    # INCIDENT DATA (from HERE API incidents results)
    incident_id: str = ''
    incident_type: str = ''
    incident_criticality: str = ''
    incident_description: str = ''
    incident_road_closed: bool = False
    incident_start_time: str = ''
    incident_end_time: str = ''
    
    # Road attributes (from OSM edge data)
    highway_type: str = 'unknown'
    road_name: str = ''
    
    # DEPRECATED: Use flow_* and incident_* instead
    speed_kph: float = 0.0
    freeFlow_kph: float = 0.0
    jamFactor: float = 0.0
    isClosed: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV export with flow_* and incident_* prefixes"""
        return {
            'id_hash': self.id_hash,
            'source_lat': self.source_lat,
            'source_lon': self.source_lon,
            'target_lat': self.target_lat,
            'target_lon': self.target_lon,
            'source': self.source,
            'target': self.target,
            'highway_type': self.highway_type,
            'road_name': self.road_name,
            # Flow data with flow_ prefix
            'flow_speed_kph': self.flow_speed_kph,
            'flow_free_flow_kph': self.flow_free_flow_kph,
            'flow_jam_factor': self.flow_jam_factor,
            'flow_confidence': self.flow_confidence,
            'flow_traversability': self.flow_traversability,
            # Incident data with incident_ prefix
            'incident_id': self.incident_id,
            'incident_type': self.incident_type,
            'incident_criticality': self.incident_criticality,
            'incident_description': self.incident_description,
            'incident_road_closed': 1 if self.incident_road_closed else 0,
            'incident_start_time': self.incident_start_time,
            'incident_end_time': self.incident_end_time,
        }


class TrafficHashMatcher:
    """
    Hash-based matcher for HERE traffic data using pre-matched edges
    """
    
    def __init__(self, matched_edges_csv: Path):
        """
        Initialize matcher with pre-matched edges
        
        Args:
            matched_edges_csv: Path to matched_edges.csv file (should use sequential IDs)
        """
        self.matched_edges_csv = matched_edges_csv
        self.hash_to_edges: Dict[str, List[TrafficEdge]] = {}
        
        # Load OSM edges for highway_type lookup
        from config import Config
        osm_edges_csv = Config.EDGES_CSV
        self.edge_attributes = self._load_edge_attributes(osm_edges_csv)
        
        self._load_matched_edges()
        
        logger.success(f"TrafficHashMatcher initialized: {len(self.hash_to_edges)} unique traffic hashes, "
                      f"{sum(len(edges) for edges in self.hash_to_edges.values())} total edges")
    
    def _load_edge_attributes(self, edges_csv: Path) -> Dict:
        """Load highway_type and road_name from OSM edges CSV"""
        logger.file_op(f"Loading OSM edge attributes from {edges_csv}...")
        
        edge_attrs = {}
        try:
            df = pd.read_csv(edges_csv)
            for _, row in df.iterrows():
                # Use SEQUENTIAL IDs as key (for C++ routing)
                key = (int(row['source']), int(row['target']))
                highway = str(row.get('highway_type', 'unknown')).strip()
                # Handle NaN values
                if pd.isna(row.get('highway_type')):
                    highway = 'unknown'
                edge_attrs[key] = {
                    'highway_type': highway,
                    'road_name': str(row.get('road_name', '')).strip()
                }
            logger.data(f"Loaded attributes for {len(edge_attrs)} OSM edges (sequential IDs)")
            # Debug: show a sample
            if edge_attrs:
                sample_key = list(edge_attrs.keys())[0]
                logger.data(f"Sample: {sample_key} -> {edge_attrs[sample_key]}")
        except Exception as e:
            logger.warning(f"Could not load edge attributes: {e}")
            import traceback
            traceback.print_exc()
        
        return edge_attrs
    
    def _load_osm_to_seq_mapping(self, edges_csv: Path) -> Dict[int, int]:
        """
        Load OSM ID to Sequential ID mapping from edges CSV
        
        Returns:
            Dict mapping OSM ID -> Sequential ID
        """
        logger.file_op(f"Loading OSM->Sequential ID mapping from {edges_csv}...")
        
        osm_to_seq = {}
        try:
            df = pd.read_csv(edges_csv)
            
            # Extract unique node mappings from edges
            for _, row in df.iterrows():
                if 'osm_source' in df.columns and 'source' in df.columns:
                    osm_source = int(row['osm_source'])
                    seq_source = int(row['source'])
                    osm_to_seq[osm_source] = seq_source
                
                if 'osm_target' in df.columns and 'target' in df.columns:
                    osm_target = int(row['osm_target'])
                    seq_target = int(row['target'])
                    osm_to_seq[osm_target] = seq_target
            
            logger.data(f"Loaded {len(osm_to_seq)} OSM->Sequential ID mappings")
            # Debug: show a sample
            if osm_to_seq:
                sample_osm = list(osm_to_seq.keys())[0]
                logger.data(f"Sample: OSM {sample_osm} -> Sequential {osm_to_seq[sample_osm]}")
        except Exception as e:
            logger.warning(f"Could not load OSM->Sequential mapping: {e}")
            logger.warning(f"Will use OSM IDs directly (may cause issues in C++ routing)")
            import traceback
            traceback.print_exc()
        
        return osm_to_seq
    
    def _load_matched_edges(self):
        """
        Load matched edges CSV into hash lookup table with highway_type
        
        UPDATED: matched_edges.csv now uses Sequential IDs directly (after update_matched_edges.py)
        """
        logger.file_op(f"Loading matched edges from {self.matched_edges_csv}...")
        
        df = pd.read_csv(self.matched_edges_csv)
        
        # Debug counters
        found_attrs = 0
        missing_attrs = 0
        
        # Group by id_hash
        for _, row in df.iterrows():
            id_hash = row['id_hash']
            
            # matched_edges.csv NOW uses Sequential IDs directly (after conversion)
            seq_source = int(row['source'])
            seq_target = int(row['target'])
            
            # Get highway_type from OSM edges using SEQUENTIAL IDs
            edge_key = (seq_source, seq_target)
            attrs = self.edge_attributes.get(edge_key, {})
            highway_type = attrs.get('highway_type', 'unknown')
            road_name = attrs.get('road_name', '')
            
            if attrs:
                found_attrs += 1
            else:
                missing_attrs += 1
            
            edge = TrafficEdge(
                id_hash=id_hash,
                source=seq_source,  # Use sequential IDs directly from matched_edges.csv
                target=seq_target,  # Use sequential IDs directly from matched_edges.csv
                source_lat=float(row['source_lat']),
                source_lon=float(row['source_lon']),
                target_lat=float(row['target_lat']),
                target_lon=float(row['target_lon']),
                highway_type=highway_type,
                road_name=road_name
            )
            
            if id_hash not in self.hash_to_edges:
                self.hash_to_edges[id_hash] = []
            
            self.hash_to_edges[id_hash].append(edge)
        
        logger.data(f"Loaded {len(self.hash_to_edges)} unique traffic segments")
        logger.data(f"Matched attributes: {found_attrs}/{found_attrs + missing_attrs} edges")
    
    def lookup_edges_by_hash(self, id_hash: str) -> List[Dict]:
        """Return hash-matched edges as dictionaries (used by IncidentMatcher)."""
        edges = self.hash_to_edges.get(id_hash, [])
        if not edges:
            return []
        return [edge.to_dict() for edge in edges]

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
        Populates FLOW DATA fields (flow_speed_kph, flow_jam_factor, etc)
        
        Args:
            flow_item: A single item from HERE API flow results
            
        Returns:
            List of matched TrafficEdge objects with FLOW metrics populated
        """
        location = flow_item.get('location')
        if not location:
            return []
        
        # Hash the location
        id_hash = self.hash_location_javascript_style(location)
        
        # Lookup matched edges
        matched_edges = self.hash_to_edges.get(id_hash, [])
        
        if not matched_edges:
            # print(f"⚠️  No match for hash: {id_hash}")
            return []
        
        # Extract FLOW DATA from HERE API
        current_flow = flow_item.get('currentFlow', {})
        
        # HERE API returns speed in m/s, convert to km/h
        speed_ms = current_flow.get('speed', 0.0)
        speed_kph = speed_ms * 3.6 if speed_ms > 0 else 0.0
        
        # Get free flow speed (assume from highway type if not provided)
        free_flow_ms = current_flow.get('freeFlow', 0.0)
        free_flow_kph = free_flow_ms * 3.6 if free_flow_ms > 0 else 0.0
        
        jam_factor = current_flow.get('jamFactor', 0.0)
        confidence = current_flow.get('confidence', 0.0)
        traversability = current_flow.get('traversability', 'open')
        
        # CRITICAL FIX: If free_flow_kph is 0 or missing, estimate from highway type
        if free_flow_kph == 0.0:
            if matched_edges:
                highway = matched_edges[0].highway_type.lower() if matched_edges[0].highway_type else 'unknown'
                if 'motorway' in highway:
                    free_flow_kph = 110.0
                elif 'trunk' in highway:
                    free_flow_kph = 90.0
                elif 'primary' in highway:
                    free_flow_kph = 70.0
                elif 'secondary' in highway:
                    free_flow_kph = 60.0
                elif 'tertiary' in highway:
                    free_flow_kph = 50.0
                elif 'residential' in highway:
                    free_flow_kph = 40.0
                else:
                    free_flow_kph = 50.0
            else:
                free_flow_kph = 50.0
        
        # FIX: If current speed is 0 but we have jam_factor, estimate from free flow
        if speed_kph == 0.0 and jam_factor > 0.0 and free_flow_kph > 0.0:
            speed_reduction_ratio = min(1.0, jam_factor / 10.0)
            speed_kph = free_flow_kph * (1.0 - speed_reduction_ratio * 0.9)
        elif speed_kph == 0.0:
            speed_kph = free_flow_kph
        
        # Populate FLOW data for all matched edges
        result_edges = []
        for edge in matched_edges:
            traffic_edge = TrafficEdge(
                id_hash=edge.id_hash,
                source=edge.source,
                target=edge.target,
                source_lat=edge.source_lat,
                source_lon=edge.source_lon,
                target_lat=edge.target_lat,
                target_lon=edge.target_lon,
                # Populate FLOW fields
                flow_speed_kph=speed_kph,
                flow_free_flow_kph=free_flow_kph,
                flow_jam_factor=jam_factor,
                flow_confidence=confidence,
                flow_traversability=traversability,
                # Incident fields remain empty (no incident data in this flow item)
                highway_type=edge.highway_type,
                road_name=edge.road_name,
                # DEPRECATED: Keep for backward compatibility
                speed_kph=speed_kph,
                freeFlow_kph=free_flow_kph,
                jamFactor=jam_factor,
                isClosed=False
            )
            result_edges.append(traffic_edge)
        
        return result_edges
    
    def _try_tier1_frechet_matching(self, incident_item: Dict, incident_points: list) -> List[TrafficEdge]:
        """
        TIER 1: Fréchet distance-based geometry matching
        
        Compare incident geometry with OSM edge geometries using Fréchet distance.
        This measures how similar two curves (paths) are in shape.
        
        Algorithm:
        1. For each edge in hash_to_edges:
           - Create edge curve from (source_lat, source_lon) to (target_lat, target_lon)
           - Calculate Fréchet distance between incident points and edge curve
           - Keep edges within threshold
        2. Sort by Fréchet distance (lower = better match)
        3. Select best edges within tolerance
        4. Return edges with incident data
        
        Args:
            incident_item: HERE API incident data
            incident_points: Pre-extracted incident points [(lat, lng), ...]
            
        Returns:
            List[TrafficEdge] with incident data, or [] if no match
        """
        from math import radians, cos, sin, asin, sqrt
        
        def haversine_distance(lat1, lng1, lat2, lng2):
            """Calculate distance in meters"""
            lat1_rad, lng1_rad = radians(lat1), radians(lng1)
            lat2_rad, lng2_rad = radians(lat2), radians(lng2)
            dlat = lat2_rad - lat1_rad
            dlng = lng2_rad - lng1_rad
            a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng/2)**2
            c = 2 * asin(sqrt(a))
            return 6371000 * c
        
        def frechet_distance(curve1, curve2):
            """
            Calculate discrete Fréchet distance between two curves.
            Uses dynamic programming with memoization.
            
            Returns distance in meters.
            """
            n, m = len(curve1), len(curve2)
            if n == 0 or m == 0:
                return float('inf')
            
            # Memoization table
            ca = {}
            
            def compute(i, j):
                if (i, j) in ca:
                    return ca[(i, j)]
                
                dist = haversine_distance(curve1[i][0], curve1[i][1],
                                         curve2[j][0], curve2[j][1])
                
                if i == 0 and j == 0:
                    result = dist
                elif i > 0 and j == 0:
                    result = max(compute(i-1, 0), dist)
                elif i == 0 and j > 0:
                    result = max(compute(0, j-1), dist)
                else:
                    result = max(min(compute(i-1, j), compute(i, j-1), compute(i-1, j-1)), dist)
                
                ca[(i, j)] = result
                return result
            
            return compute(n-1, m-1)
        
        # Extract incident details for logging and edge creation
        incident_details = incident_item.get('incidentDetails', {})
        incident_id = incident_details.get('id', 'unknown')
        incident_type = incident_details.get('type', 'unknown')
        incident_criticality = incident_details.get('criticality', '')
        incident_description = incident_details.get('description', {}).get('value', '')
        incident_road_closed = incident_details.get('roadClosed', False)
        incident_start_time = incident_details.get('startTime', '')
        incident_end_time = incident_details.get('endTime', '')
        
        # Map criticality to jam factor
        criticality_map = {'critical': 9.0, 'severe': 7.0, 'major': 5.0, 'minor': 2.0}
        jam_factor = criticality_map.get(incident_criticality.lower(), 0.0) if incident_criticality else 0.0
        speed_kph = 0.0 if incident_road_closed else 10.0
        
        # TIER 1 parameters
        frechet_threshold_m = 500.0  # Max Fréchet distance to consider
        tolerance_ratio = 0.10  # Accept edges within 10% of best
        
        # Score each edge using Fréchet distance
        edge_scores = []
        
        for edge_list in self.hash_to_edges.values():
            for edge in edge_list:
                # Create edge curve (simple 2-point line)
                edge_curve = [
                    (edge.source_lat, edge.source_lon),
                    (edge.target_lat, edge.target_lon)
                ]
                
                # Calculate Fréchet distance
                frechet_dist = frechet_distance(incident_points, edge_curve)
                
                # Keep only edges within threshold
                if frechet_dist <= frechet_threshold_m:
                    edge_scores.append({
                        'edge': edge,
                        'frechet_distance': frechet_dist
                    })
        
        if not edge_scores:
            return []
        
        # Sort by Fréchet distance (best first)
        edge_scores.sort(key=lambda x: x['frechet_distance'])
        
        # Select best edges within tolerance
        best_frechet = edge_scores[0]['frechet_distance']
        tolerance = best_frechet * tolerance_ratio
        
        result_edges = []
        for item in edge_scores:
            if item['frechet_distance'] <= best_frechet + tolerance:
                edge = item['edge']
                traffic_edge = TrafficEdge(
                    id_hash=edge.id_hash,
                    source=edge.source,
                    target=edge.target,
                    source_lat=edge.source_lat,
                    source_lon=edge.source_lon,
                    target_lat=edge.target_lat,
                    target_lon=edge.target_lon,
                    incident_id=incident_id,
                    incident_type=incident_type,
                    incident_criticality=incident_criticality,
                    incident_description=incident_description,
                    incident_road_closed=incident_road_closed,
                    incident_start_time=incident_start_time,
                    incident_end_time=incident_end_time,
                    highway_type=edge.highway_type,
                    road_name=edge.road_name,
                    speed_kph=speed_kph,
                    freeFlow_kph=50.0,
                    jamFactor=jam_factor,
                    isClosed=incident_road_closed
                )
                result_edges.append(traffic_edge)
        
        # Log success
        if result_edges:
            logger.algorithm(f"[{incident_id}] TIER 1: Fréchet {best_frechet:.1f}m → {len(result_edges)} edge(s)")
        
        return result_edges
        
    
    def _try_tier0_point_matching(self, incident_item: Dict, flow_results: List[Dict],
                                   incident_points: list) -> List[TrafficEdge]:
        """
        TIER 0: Point-based matching using flow data hash lookup
        
        Algorithm (based on point_matcher.py reference):
        1. For each flow item, extract all points from location.shape.links
        2. Count how many incident points are inside each flow (distance ≤ threshold)
        3. Require minimum 2 points to match
        4. Select flow with most matched points
        5. Use flow's hash to lookup edges directly
        6. Return edges with incident data populated
        
        Success Criteria:
        - At least 2 incident points must be within 100m of flow points
        - Uses hash-based edge lookup (same as flow matching - most reliable)
        
        Args:
            incident_item: HERE API incident data
            flow_results: List of flow items from HERE API
            incident_points: Pre-extracted incident points [(lat, lng), ...]
            
        Returns:
            List[TrafficEdge] with incident data, or [] if no match
        """
        from math import radians, cos, sin, asin, sqrt
        
        def haversine_distance(lat1, lng1, lat2, lng2):
            """Calculate distance in meters"""
            lat1_rad, lng1_rad = radians(lat1), radians(lng1)
            lat2_rad, lng2_rad = radians(lat2), radians(lng2)
            dlat = lat2_rad - lat1_rad
            dlng = lng2_rad - lng1_rad
            a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng/2)**2
            c = 2 * asin(sqrt(a))
            return 6371000 * c
        
        def extract_flow_points(flow_location):
            """Extract points from flow location.shape.links (ONLY lat/lng)"""
            points = []
            shape = flow_location.get('shape', {})
            links = shape.get('links', [])
            
            if isinstance(links, list):
                for link in links:
                    if 'points' in link and isinstance(link['points'], list):
                        for pt in link['points']:
                            lat = pt.get('lat')
                            lng = pt.get('lng')
                            if lat is not None and lng is not None:
                                points.append((lat, lng))
            return points
        
        # Extract incident ID for logging
        incident_details = incident_item.get('incidentDetails', {})
        incident_id = incident_details.get('id', 'unknown')
        incident_type = incident_details.get('type', 'unknown')
        
        # TIER 0 matching parameters
        distance_threshold_m = 100.0  # 100 meters tolerance
        min_points_required = 2  # Need at least 2 points inside flow
        
        best_flow = None
        best_match_count = 0
        best_matched_points = []
        
        # Try each flow item
        for flow_idx, flow_item in enumerate(flow_results):
            flow_location = flow_item.get('location', {})
            if not flow_location:
                continue
            
            flow_points = extract_flow_points(flow_location)
            if not flow_points:
                continue
            
            # Count how many incident points are inside this flow
            matched_count = 0
            matched_point_distances = []
            
            for inc_lat, inc_lng in incident_points:
                # Find if ANY flow point is within threshold
                for flow_lat, flow_lng in flow_points:
                    dist = haversine_distance(inc_lat, inc_lng, flow_lat, flow_lng)
                    
                    if dist <= distance_threshold_m:
                        matched_count += 1
                        matched_point_distances.append(dist)
                        break  # Move to next incident point
            
            # Keep flow with most matched points
            if matched_count >= min_points_required and matched_count > best_match_count:
                best_match_count = matched_count
                best_flow = flow_item
                best_matched_points = matched_point_distances
        
        # If found match, use flow's hash to get edges
        if best_flow and best_match_count >= min_points_required:
            flow_location = best_flow.get('location', {})
            
            try:
                # Compute hash from flow location (same as flow matching)
                flow_hash = self.hash_location_javascript_style(flow_location)
                
                # Lookup edges using hash
                if flow_hash in self.hash_to_edges:
                    edges = self.hash_to_edges[flow_hash]
                    
                    # Extract full incident details
                    incident_criticality = incident_details.get('criticality', '')
                    incident_description = incident_details.get('description', {}).get('value', '')
                    incident_road_closed = incident_details.get('roadClosed', False)
                    incident_start_time = incident_details.get('startTime', '')
                    incident_end_time = incident_details.get('endTime', '')
                    
                    # Map criticality to jam factor
                    criticality_map = {'critical': 9.0, 'severe': 7.0, 'major': 5.0, 'minor': 2.0}
                    jam_factor = criticality_map.get(incident_criticality.lower(), 0.0) if incident_criticality else 0.0
                    speed_kph = 0.0 if incident_road_closed else 10.0
                    
                    # Create TrafficEdge objects with incident data
                    result_edges = []
                    for edge in edges:
                        traffic_edge = TrafficEdge(
                            id_hash=edge.id_hash,
                            source=edge.source,
                            target=edge.target,
                            source_lat=edge.source_lat,
                            source_lon=edge.source_lon,
                            target_lat=edge.target_lat,
                            target_lon=edge.target_lon,
                            incident_id=incident_id,
                            incident_type=incident_type,
                            incident_criticality=incident_criticality,
                            incident_description=incident_description,
                            incident_road_closed=incident_road_closed,
                            incident_start_time=incident_start_time,
                            incident_end_time=incident_end_time,
                            highway_type=edge.highway_type,
                            road_name=edge.road_name,
                            speed_kph=speed_kph,
                            freeFlow_kph=50.0,
                            jamFactor=jam_factor,
                            isClosed=incident_road_closed
                        )
                        result_edges.append(traffic_edge)
                    
                    # Log success with incident details
                    avg_dist = sum(best_matched_points) / len(best_matched_points) if best_matched_points else 0
                    logger.algorithm(f"[{incident_id}] TIER 0: {best_match_count}/{len(incident_points)} pts " +
                                    f"(avg {avg_dist:.1f}m) → {len(result_edges)} edge(s) via hash")
                    
                    return result_edges
                    
            except Exception as e:
                logger.error(f"[{incident_id}] TIER 0 error: {e}")
        
        return []  # No match, try TIER 1
    
    def match_traffic_incident_item(self, incident_item: Dict, 
                                      flow_results: List[Dict] = None) -> List[TrafficEdge]:
        """
        Match a single HERE API incident item to edges using two-tier approach:
        
        TIER 0: Point-based matching with flow data hash lookup
           - Check if incident points are inside flow points (≥2 points within 100m)
           - Use flow's hash to lookup edges directly (most reliable)
           - Skip to next tier if no match
        
        TIER 1: Fréchet distance geometry matching
           - Compare incident geometry with all OSM edge geometries
           - Use Fréchet distance to measure curve similarity
           - Select best matching edges
        
        Args:
            incident_item: A single item from HERE API incidents results
            flow_results: Optional list of flow data items from HERE API
            
        Returns:
            List of matched TrafficEdge objects with INCIDENT metrics populated
        """
        # Extract incident details for logging
        incident_details = incident_item.get('incidentDetails', {})
        incident_id = incident_details.get('id', 'unknown')
        incident_type = incident_details.get('type', 'unknown')
        
        location = incident_item.get('location')
        if not location:
            logger.warning(f"[{incident_id}] No location data")
            return []
        
        # Extract all points from incident geometry
        incident_points = []
        
        if 'shape' in location and 'links' in location['shape']:
            links = location['shape']['links']
            if isinstance(links, list):
                for link in links:
                    if 'points' in link and isinstance(link['points'], list):
                        for point in link['points']:
                            lat = point.get('lat')
                            lng = point.get('lng')
                            if lat is not None and lng is not None:
                                incident_points.append((lat, lng))
        
        if not incident_points:
            logger.warning(f"[{incident_id}] No coordinate points extracted")
            return []
        
        # TIER 0: Point matching with flow data (if flow_results available)
        if flow_results:
            matched_edges = self._try_tier0_point_matching(
                incident_item, flow_results, incident_points
            )
            if matched_edges:
                return matched_edges  # Success, skip TIER 1
        
        # TIER 1: Fréchet distance geometry matching (fallback)
        matched_edges = self._try_tier1_frechet_matching(
            incident_item, incident_points
        )
        if matched_edges:
            return matched_edges
        
        # No match found in any tier
        logger.warning(f"[{incident_id}] No edges matched")
        return []
    
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
        
        logger.success(f"Matched {matched_count}/{len(flow_results)} flow items "
                       f"-> {len(all_edges)} total edges")
        
        return all_edges
        centroid_lat = sum(p[0] for p in incident_points) / len(incident_points)
        centroid_lng = sum(p[1] for p in incident_points) / len(incident_points)
        
        # Helper functions
        def haversine_distance(lat1, lng1, lat2, lng2):
            """Calculate distance in meters between two coordinates"""
            lat1_rad, lng1_rad = radians(lat1), radians(lng1)
            lat2_rad, lng2_rad = radians(lat2), radians(lng2)
            dlat = lat2_rad - lat1_rad
            dlng = lng2_rad - lng1_rad
            a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng/2)**2
            c = 2 * asin(sqrt(a))
            return 6371000 * c  # Earth radius in meters
        
        def distance_to_segment(point_lat, point_lng, seg_lat1, seg_lng1, seg_lat2, seg_lng2):
            """Calculate perpendicular distance from point to line segment"""
            px, py = point_lng, point_lat
            x1, y1 = seg_lng1, seg_lat1
            x2, y2 = seg_lng2, seg_lat2
            
            dx = x2 - x1
            dy = y2 - y1
            
            if dx == 0 and dy == 0:
                return haversine_distance(point_lat, point_lng, seg_lat1, seg_lng1)
            
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
            closest_x = x1 + t * dx
            closest_y = y1 + t * dy
            
            return haversine_distance(point_lat, point_lng, closest_y, closest_x)
        
        def frechet_distance(curve1, curve2):
            """
            Calculate Fréchet Distance between two curves (lists of (lat, lng) tuples)
            Uses dynamic programming approach for discrete Fréchet distance.
            
            Fréchet distance = inf over all pairings the max distance between paired points
            For curve matching: lower distance means curves are more similar in shape
            
            Returns distance in meters
            """
            n, m = len(curve1), len(curve2)
            if n == 0 or m == 0:
                return float('inf')
            
            # Initialize memoization table
            # ca[i][j] = Fréchet distance between curve1[0:i+1] and curve2[0:j+1]
            ca = {}
            
            def compute_frechet(i, j):
                """Compute frechet distance recursively with memoization"""
                if (i, j) in ca:
                    return ca[(i, j)]
                
                dist = haversine_distance(curve1[i][0], curve1[i][1], 
                                        curve2[j][0], curve2[j][1])
                
                if i == 0 and j == 0:
                    result = dist
                elif i > 0 and j == 0:
                    result = max(compute_frechet(i-1, 0), dist)
                elif i == 0 and j > 0:
                    result = max(compute_frechet(0, j-1), dist)
                else:
                    result = max(min(compute_frechet(i-1, j),
                                   compute_frechet(i, j-1),
                                   compute_frechet(i-1, j-1)),
                               dist)
                
                ca[(i, j)] = result
                return result
            
            return compute_frechet(n-1, m-1)
        
        # STEP 3: Score each edge using Fréchet Distance + proximity metrics
        edge_scores = []
        threshold_m = 1000  # Slightly increased for Fréchet-based matching (more permissive)
        
        for edge_list in self.hash_to_edges.values():
            for edge in edge_list:
                # Create edge curve: edge represented as a line segment
                edge_curve = [(edge.source_lat, edge.source_lon),
                             (edge.target_lat, edge.target_lon)]
                
                # Calculate Fréchet Distance between incident and edge
                frechet_dist = frechet_distance(incident_points, edge_curve)
                
                # Distance from incident centroid to edge
                dist_to_source = haversine_distance(
                    centroid_lat, centroid_lng,
                    edge.source_lat, edge.source_lon
                )
                dist_to_target = haversine_distance(
                    centroid_lat, centroid_lng,
                    edge.target_lat, edge.target_lon
                )
                dist_to_segment = distance_to_segment(
                    centroid_lat, centroid_lng,
                    edge.source_lat, edge.source_lon,
                    edge.target_lat, edge.target_lon
                )
                min_distance = min(dist_to_source, dist_to_target, dist_to_segment)
                
                # Geometry overlap: count incident points close to edge
                overlap_count = 0
                for inc_lat, inc_lng in incident_points:
                    dist_to_seg = distance_to_segment(
                        inc_lat, inc_lng,
                        edge.source_lat, edge.source_lon,
                        edge.target_lat, edge.target_lon
                    )
                    if dist_to_seg < 250:  # Slightly increased overlap threshold
                        overlap_count += 1
                
                overlap_ratio = overlap_count / len(incident_points) if incident_points else 0
                
                # Only consider edges where Fréchet distance is reasonable
                # (incident geometry roughly aligns with edge direction)
                if frechet_dist <= threshold_m:
                    # Combined scoring: Fréchet takes priority, then proximity, then overlap
                    # Normalize Fréchet distance to 0-1 scale (lower is better)
                    frechet_score = frechet_dist / threshold_m if threshold_m > 0 else 1.0
                    
                    # Combined score prioritizes Fréchet distance
                    # frechet_score: 0-1 (lower better)
                    # overlap_ratio bonus: subtract to reward high overlap
                    score = frechet_score - (overlap_ratio * 0.3)  # Overlap has small weight
                    
                    edge_scores.append({
                        'edge': edge,
                        'frechet_distance': frechet_dist,
                        'min_distance': min_distance,
                        'overlap_ratio': overlap_ratio,
                        'overlap_count': overlap_count,
                        'score': score
                    })
        
        if not edge_scores:
            logger.warning(f"No edges within {threshold_m}m (Fréchet) of incident geometry")
            return []
        
        # STEP 4: Rank and select best edges
        # Primary sort: Fréchet distance (lower is better)
        # Secondary: overlap ratio (higher is better)
        # Tertiary: proximity (lower is better)
        edge_scores.sort(key=lambda x: (x['frechet_distance'], -x['overlap_ratio'], x['min_distance']))
        
        # Select best edge(s) with similar Fréchet distance
        best_edges = []
        if edge_scores:
            best_frechet = edge_scores[0]['frechet_distance']
            # Accept edges with Fréchet distance within 5% of best
            frechet_tolerance = best_frechet * 0.05
            
            for item in edge_scores:
                if item['frechet_distance'] <= best_frechet + frechet_tolerance:
                    best_edges.append(item['edge'])
                else:
                    break
        
        # Extract INCIDENT DATA from HERE API
        incident_details = incident_item.get('incidentDetails', {})
        
        incident_id = incident_details.get('id', '')
        incident_type = incident_details.get('type', '')
        incident_criticality = incident_details.get('criticality', '')
        incident_description = incident_details.get('description', {}).get('value', '')
        incident_road_closed = incident_details.get('roadClosed', False)
        incident_start_time = incident_details.get('startTime', '')
        incident_end_time = incident_details.get('endTime', '')
        
        # Estimate jam factor from criticality for weighting
        criticality_map = {
            'critical': 9.0,
            'severe': 7.0,
            'major': 5.0,
            'minor': 2.0
        }
        jam_factor = criticality_map.get(incident_criticality.lower(), 0.0) if incident_criticality else 0.0
        
        # Set speed based on closure status
        speed_kph = 0.0 if incident_road_closed else 10.0
        
        # Populate INCIDENT data for all matched edges
        result_edges = []
        for edge in best_edges:
            traffic_edge = TrafficEdge(
                id_hash=edge.id_hash,
                source=edge.source,
                target=edge.target,
                source_lat=edge.source_lat,
                source_lon=edge.source_lon,
                target_lat=edge.target_lat,
                target_lon=edge.target_lon,
                # Populate INCIDENT fields
                incident_id=incident_id,
                incident_type=incident_type,
                incident_criticality=incident_criticality,
                incident_description=incident_description,
                incident_road_closed=incident_road_closed,
                incident_start_time=incident_start_time,
                incident_end_time=incident_end_time,
                # Flow fields remain empty (no flow data in incident-only item)
                highway_type=edge.highway_type,
                road_name=edge.road_name,
                # DEPRECATED: Keep for backward compatibility
                speed_kph=speed_kph,
                freeFlow_kph=50.0,
                jamFactor=jam_factor,
                isClosed=incident_road_closed
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
        
        logger.success(f"Matched {matched_count}/{len(flow_results)} flow items "
                       f"-> {len(all_edges)} total edges")
        
        return all_edges
    
    def batch_match_incident_data(self, incident_results: List[Dict], 
                                  flow_results: List[Dict] = None) -> List[TrafficEdge]:
        """
        Match all incident results to edges using multi-tier approach:
        1. Try traffic-data-based matching (if flow_results provided)
        2. Fall back to Fréchet distance geometric matching
        
        Args:
            incident_results: List of incident items from HERE API
            flow_results: Optional list of flow items for Tier 1 matching
            
        Returns:
            List of all matched TrafficEdge objects
        """
        all_edges = []
        matched_count = 0
        tier1_count = 0
        
        for i, incident_item in enumerate(incident_results):
            edges = self.match_traffic_incident_item(incident_item, flow_results)
            if edges:
                matched_count += 1
                all_edges.extend(edges)
                incident_details = incident_item.get('incidentDetails', {})
                incident_type = incident_details.get('type', 'unknown')
                logger.success(f"Incident {i+1}: {incident_type} matched to {len(edges)} edge(s)")
            else:
                incident_details = incident_item.get('incidentDetails', {})
                incident_type = incident_details.get('type', 'unknown')
                logger.warning(f"Incident {i+1}: {incident_type} - no nearby edges found")
        
        logger.success(f"Matched {matched_count}/{len(incident_results)} incidents " +
                       f"-> {len(all_edges)} total edge(s)")
        
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
    
    logger.info("\n" + "="*70)
    logger.info("Testing TrafficHashMatcher")
    logger.info("="*70 + "\n")
    
    # Initialize matcher
    matched_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
    matcher = TrafficHashMatcher(matched_csv)
    
    # Show stats
    stats = matcher.get_stats()
    logger.data(f"\n📊 Matcher Statistics:")
    logger.data(f"   Unique traffic hashes: {stats['unique_hashes']}")
    logger.data(f"   Total mapped edges: {stats['total_edges']}")
    logger.data(f"   Avg edges per hash: {stats['avg_edges_per_hash']:.1f}")
    
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
    
    logger.test(f"\n🧪 Testing with sample flow data...")
    edges = matcher.match_traffic_flow_item(sample_flow)
    
    logger.data(f"   Found {len(edges)} matched edges")
    for edge in edges[:3]:
        logger.data(f"      {edge.source} -> {edge.target}: "
                    f"{edge.speed_kph:.1f} km/h (jam: {edge.jamFactor:.1f})")
    
    logger.info("\n" + "="*70)


if __name__ == '__main__':
    test_traffic_hash_matcher()
