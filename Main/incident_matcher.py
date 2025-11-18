"""
Incident Matcher - OSM Edge Matching for Traffic Incidents
===========================================================

Matches HERE API traffic incidents to OSM road edges using:
1. Hash-based matching (preferred) - Uses pre-matched edges from matched_edges.csv
2. Spatial matching (fallback) - Finds nearest edges using haversine distance

The hash-based approach matches incident locations to the same hash keys used
for flow data, enabling consistent edge mapping between incidents and flow.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from traffic_hash_matcher import TrafficHashMatcher


class IncidentMatcher:
    """Matches traffic incidents to OSM road network edges"""
    
    def __init__(self, edges_csv: Path, nodes_csv: Path, matched_edges_csv: Path = None):
        """
        Initialize incident matcher with OSM road network data
        
        Args:
            edges_csv: Path to edges CSV file with OSM network
            nodes_csv: Path to nodes CSV file with coordinates
            matched_edges_csv: Path to matched_edges.csv for hash-based matching (optional)
        """
        print(f"🔧 Initializing IncidentMatcher...")
        
        # Initialize hash matcher if matched_edges provided
        self.hash_matcher = None
        if matched_edges_csv and matched_edges_csv.exists():
            try:
                self.hash_matcher = TrafficHashMatcher(matched_edges_csv)
                print(f"   ✅ Hash-based matching enabled")
            except Exception as e:
                print(f"   ⚠️  Hash matching disabled: {e}")
        
        # Load OSM edges for spatial fallback
        self.edges_df = pd.read_csv(edges_csv)
        print(f"   ✅ Loaded {len(self.edges_df)} OSM edges")
        
        # Load OSM nodes for coordinate lookup
        self.nodes_df = pd.read_csv(nodes_csv)
        self.node_coords = {}
        for _, row in self.nodes_df.iterrows():
            self.node_coords[row['node_id']] = (row['latitude'], row['longitude'])
        print(f"   ✅ Loaded {len(self.node_coords)} node coordinates")
        
        # Precompute edge geometries and midpoints for matching
        self._precompute_edge_data()
        
        print(f"   ✅ IncidentMatcher ready")
    
    def _precompute_edge_data(self):
        """Precompute edge midpoints and bounding boxes for efficient matching"""
        edge_data = []
        
        for _, edge in self.edges_df.iterrows():
            source_id = edge['source']
            target_id = edge['target']
            
            if source_id not in self.node_coords or target_id not in self.node_coords:
                continue
            
            source_lat, source_lon = self.node_coords[source_id]
            target_lat, target_lon = self.node_coords[target_id]
            
            # Calculate edge midpoint
            mid_lat = (source_lat + target_lat) / 2
            mid_lon = (source_lon + target_lon) / 2
            
            edge_data.append({
                'source': source_id,
                'target': target_id,
                'source_lat': source_lat,
                'source_lon': source_lon,
                'target_lat': target_lat,
                'target_lon': target_lon,
                'mid_lat': mid_lat,
                'mid_lon': mid_lon,
                'highway_type': edge['highway_type'] if 'highway_type' in edge else 'unknown',
                'road_name': edge['road_name'] if 'road_name' in edge else '',
                'oneway': edge['oneway'] if 'oneway' in edge else 0
            })
        
        self.edge_data = pd.DataFrame(edge_data)
        print(f"   📊 Precomputed {len(self.edge_data)} edge geometries")
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate haversine distance between two points in meters
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)
        
        a = np.sin(delta_lat / 2) ** 2 + \
            np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        return R * c
    
    def _point_to_segment_distance(self, px: float, py: float,
                                   x1: float, y1: float, x2: float, y2: float) -> float:
        """
        Calculate minimum distance from point to line segment
        
        Args:
            px, py: Point coordinates (lat, lon)
            x1, y1: Segment start (lat, lon)
            x2, y2: Segment end (lat, lon)
            
        Returns:
            Distance in meters
        """
        # Calculate distances
        dist_to_start = self._haversine_distance(px, py, x1, y1)
        dist_to_end = self._haversine_distance(px, py, x2, y2)
        
        # Vector from segment start to end
        dx = x2 - x1
        dy = y2 - y1
        
        # Handle zero-length segments
        if dx == 0 and dy == 0:
            return dist_to_start
        
        # Calculate projection parameter
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        # Find closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Return distance to closest point
        return self._haversine_distance(px, py, closest_x, closest_y)
    
    def find_nearest_edges(self, lat: float, lon: float, max_distance: float = 100.0,
                          max_results: int = 3) -> List[Dict]:
        """
        Find nearest OSM edges to a given point
        
        Args:
            lat, lon: Point coordinates
            max_distance: Maximum distance in meters to search
            max_results: Maximum number of edges to return
            
        Returns:
            List of matching edges with distances
        """
        matches = []
        
        for _, edge in self.edge_data.iterrows():
            # Calculate distance from point to edge segment
            distance = self._point_to_segment_distance(
                lat, lon,
                edge['source_lat'], edge['source_lon'],
                edge['target_lat'], edge['target_lon']
            )
            
            if distance <= max_distance:
                matches.append({
                    'source': edge['source'],
                    'target': edge['target'],
                    'source_lat': edge['source_lat'],
                    'source_lon': edge['source_lon'],
                    'target_lat': edge['target_lat'],
                    'target_lon': edge['target_lon'],
                    'highway_type': edge['highway_type'],
                    'road_name': edge['road_name'],
                    'distance': distance
                })
        
        # Sort by distance and return top N
        matches.sort(key=lambda x: x['distance'])
        return matches[:max_results]
    
    def _create_incident_edges_from_hash_match(self, incident: Dict, matched_edges: List[Dict]) -> List[Dict]:
        """
        Create incident edge records from hash-matched edges
        
        Args:
            incident: Incident data from HERE API
            matched_edges: List of edges from hash matcher (contains source, target, coords)
            
        Returns:
            List of incident edge dictionaries
        """
        # Extract incident attributes
        incident_id = incident.get('incidentDetails', {}).get('id', '')
        incident_type = incident.get('incidentDetails', {}).get('type', {})
        
        # Handle incident_type which could be dict or string
        if isinstance(incident_type, dict):
            incident_type = incident_type.get('id', 'unknown')
        else:
            incident_type = str(incident_type) if incident_type else 'unknown'
        
        # Map criticality - HERE API v7 returns 0-3 numeric values
        criticality_value = incident.get('incidentDetails', {}).get('criticality')
        if isinstance(criticality_value, dict):
            criticality_value = criticality_value.get('id', criticality_value.get('value'))
        
        criticality_map = {0: 'minor', 1: 'major', 2: 'severe', 3: 'critical'}
        try:
            if criticality_value is not None:
                incident_criticality = criticality_map.get(int(criticality_value), 'unknown')
            else:
                incident_criticality = 'unknown'
        except (ValueError, TypeError):
            criticality_str_map = {'0': 'minor', '1': 'major', '2': 'severe', '3': 'critical'}
            incident_criticality = criticality_str_map.get(str(criticality_value), 'unknown')
        
        incident_description = incident.get('incidentDetails', {}).get('description', {})
        if isinstance(incident_description, dict):
            incident_description = incident_description.get('value', '')
        else:
            incident_description = str(incident_description) if incident_description else ''
        
        # Check if road is closed
        incident_road_closed = 'ROAD_CLOSED' in str(incident_type).upper() or 'CLOSURE' in str(incident_type).upper()
        
        # Extract start/end times
        incident_start_time = incident.get('incidentDetails', {}).get('startTime', '')
        incident_end_time = incident.get('incidentDetails', {}).get('endTime', '')
        
        # Create incident edge records from matched edges
        incident_edges = []
        for edge in matched_edges:
            incident_edges.append({
                'source': edge.get('source'),
                'target': edge.get('target'),
                'source_lat': edge.get('source_lat'),
                'source_lon': edge.get('source_lon'),
                'target_lat': edge.get('target_lat'),
                'target_lon': edge.get('target_lon'),
                'incident_id': incident_id,
                'incident_type': incident_type,
                'incident_criticality': incident_criticality,
                'incident_description': incident_description,
                'incident_road_closed': incident_road_closed,
                'incident_start_time': incident_start_time,
                'incident_end_time': incident_end_time,
                'highway_type': edge.get('highway_type', 'unknown'),
                'road_name': edge.get('road_name', '')
            })
        
        return incident_edges
    
    def match_incident(self, incident: Dict) -> List[Dict]:
        """
        Match a single incident to OSM edges
        
        Tries hash-based matching first (if available), then falls back to spatial matching.
        
        Args:
            incident: Incident data from HERE API
            
        Returns:
            List of matched edges with incident data
        """
        # Validate incident is a dictionary
        if not isinstance(incident, dict):
            print(f"   ⚠️  Skipping non-dict incident: {type(incident)}")
            return []
        
        try:
            # Extract incident location
            location = incident.get('location', {})
            
            # TRY HASH MATCHING FIRST (preferred method)
            if self.hash_matcher and location:
                try:
                    location_hash = TrafficHashMatcher.hash_location_javascript_style(location)
                    matched_edges = self.hash_matcher.lookup_edges_by_hash(location_hash)
                    
                    if matched_edges:
                        print(f"   ✅ Hash match: {len(matched_edges)} edges for hash {location_hash}")
                        # Extract incident attributes and apply to matched edges
                        return self._create_incident_edges_from_hash_match(
                            incident, matched_edges
                        )
                except Exception as e:
                    print(f"   ⚠️  Hash matching failed: {e}, falling back to spatial")
            
            # FALLBACK: SPATIAL MATCHING (original behavior)
            shape = location.get('shape', {})
            links = shape.get('links', [])
            
            if not links:
                return []
            
            # Get first link's points (incident location)
            first_link = links[0]
            points = first_link.get('points', [])
            
            if not points:
                return []
            
            # Use first point as incident location
            first_point = points[0]
            lat = first_point.get('lat')
            lon = first_point.get('lng')
            
            if lat is None or lon is None:
                return []
            
            # Extract incident attributes
            incident_id = incident.get('incidentDetails', {}).get('id', '')
            incident_type = incident.get('incidentDetails', {}).get('type', {})
            
            # Handle incident_type which could be dict or string
            if isinstance(incident_type, dict):
                incident_type = incident_type.get('id', 'unknown')
            else:
                incident_type = str(incident_type) if incident_type else 'unknown'
            
            # Map criticality - HERE API v7 returns 0-3 numeric values
            # 0=minor, 1=major, 2=severe, 3=critical
            criticality_value = incident.get('incidentDetails', {}).get('criticality')
            
            # Handle both numeric and dict formats
            if isinstance(criticality_value, dict):
                criticality_value = criticality_value.get('id', criticality_value.get('value'))
            
            # Convert to int and map
            criticality_map = {
                0: 'minor',
                1: 'major',
                2: 'severe',
                3: 'critical'
            }
            
            # Try to convert to int
            try:
                if criticality_value is not None:
                    criticality_int = int(criticality_value)
                    incident_criticality = criticality_map.get(criticality_int, 'unknown')
                else:
                    incident_criticality = 'unknown'
            except (ValueError, TypeError):
                # Fallback for string values '0', '1', '2', '3'
                criticality_str_map = {
                    '0': 'minor',
                    '1': 'major',
                    '2': 'severe',
                    '3': 'critical'
                }
                incident_criticality = criticality_str_map.get(str(criticality_value), 'unknown')
            
            incident_description = incident.get('incidentDetails', {}).get('description', {})
            if isinstance(incident_description, dict):
                incident_description = incident_description.get('value', '')
            else:
                incident_description = str(incident_description) if incident_description else ''
            
            # Check if road is closed
            incident_road_closed = 'ROAD_CLOSED' in str(incident_type).upper() or 'CLOSURE' in str(incident_type).upper()
            
            # Extract start/end times
            incident_start_time = incident.get('incidentDetails', {}).get('startTime', '')
            incident_end_time = incident.get('incidentDetails', {}).get('endTime', '')
            
            # Find ONLY the single nearest edge (closest match ONLY)
            nearest_edges = self.find_nearest_edges(lat, lon, max_distance=50.0, max_results=1)
            
            if not nearest_edges:
                return []
            
            # Create incident edge records
            incident_edges = []
            for edge in nearest_edges:
                incident_edges.append({
                    'source': edge['source'],
                    'target': edge['target'],
                    'source_lat': edge['source_lat'],
                    'source_lon': edge['source_lon'],
                    'target_lat': edge['target_lat'],
                    'target_lon': edge['target_lon'],
                    'incident_id': incident_id,
                    'incident_type': incident_type,
                    'incident_criticality': incident_criticality,
                    'incident_description': incident_description,
                    'incident_road_closed': incident_road_closed,
                    'incident_start_time': incident_start_time,
                    'incident_end_time': incident_end_time,
                    'highway_type': edge['highway_type'],
                    'road_name': edge['road_name']
                })
            
            return incident_edges
            
        except Exception as e:
            print(f"   ⚠️  Error matching incident: {e}")
            return []
    
    def batch_match_incidents(self, incidents: List[Dict]) -> List[Dict]:
        """
        Match multiple incidents to OSM edges
        
        Args:
            incidents: List of incident data from HERE API
            
        Returns:
            List of all matched edges
        """
        all_edges = []
        matched_count = 0
        
        print(f"🔍 Matching {len(incidents)} incidents to OSM edges...")
        
        for incident in incidents:
            matched_edges = self.match_incident(incident)
            if matched_edges:
                all_edges.extend(matched_edges)
                matched_count += 1
        
        print(f"   ✅ Matched {matched_count}/{len(incidents)} incidents to {len(all_edges)} edges")
        
        return all_edges
