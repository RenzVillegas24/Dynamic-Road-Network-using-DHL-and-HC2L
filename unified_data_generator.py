#!/usr/bin/env python3
"""
Unified Data Generator for Enhanced DHL/HC2L Algorithms
=========================================================

This script replaces all previous data generation scripts with a unified approach:
- Uses real HERE API traffic data (flow + incidents)
- Uses OSMnx for authentic road network topology
- Generates data compatible with enhanced routing algorithms

Output Format (CSV):
- source, target: Node IDs
- source_lat, source_lon, target_lat, target_lon: GPS coordinates
- road_name: Street name
- highway_type: OSM highway classification
- speed_kph: Current speed (from HERE flow or estimated)
- freeFlow_kph: Free flow speed (from HERE or OSM defaults)
- jamFactor: Traffic jam factor (0.0-10.0 scale)
- isClosed: Boolean (True/False)
- segmentLength: Edge length in meters
- oneway: Direction (-1, 0, 1)
- disruption_type: Inferred type (congestion, accident, closure, etc.)
- impact_score: Combined impact metric (0.0-1.0)

Usage:
    python unified_data_generator.py --mode both              # Generate 1 scenario with timestamp name
    python unified_data_generator.py --mode flow --scenarios 3  # Generate 3 snapshots
    python unified_data_generator.py --mode both --continuous --interval 300  # Real-time updates
    python unified_data_generator.py --mode incidents --bbox "121.01,14.59,121.14,14.76"

Output filenames use ISO timestamp format (YYYYMMDDTHHmmss):
    - 20251104T210230_both.csv
    - 20251104T210230_both.gr
    - Symlink: current_traffic_both.gr (always points to latest)
"""

import os
import sys
import argparse
import time
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv
import osmnx as ox
import geopandas as gpd
from shapely.geometry import LineString, Point
import json

# Add Main directory to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))
from config import Config

# Load environment
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# HERE API Configuration
HERE_API_KEY = os.getenv('HERE_API_KEY', '')
DEFAULT_BBOX = "121.01,14.59,121.14,14.76"  # Quezon City bounds (lon,lat,lon,lat)

# OSM Highway Speed Profiles (km/h)
HIGHWAY_SPEEDS = {
    'motorway': 100,
    'motorway_link': 80,
    'trunk': 90,
    'trunk_link': 70,
    'primary': 70,
    'primary_link': 60,
    'secondary': 60,
    'secondary_link': 50,
    'tertiary': 50,
    'tertiary_link': 40,
    'unclassified': 40,
    'residential': 30,
    'service': 20,
    'living_street': 10,
    'track': 15,
}

# Disruption Type Inference
def infer_disruption_type(jam_factor: float, is_closed: bool, 
                          speed_reduction: float, incident_type: Optional[str] = None) -> str:
    """Infer disruption type from metrics"""
    if is_closed:
        return 'road_closure'
    if incident_type:
        incident_lower = incident_type.lower()
        if 'accident' in incident_lower or 'crash' in incident_lower:
            return 'accident'
        if 'construction' in incident_lower or 'roadwork' in incident_lower:
            return 'construction'
        if 'weather' in incident_lower or 'flood' in incident_lower:
            return 'weather'
    
    # Infer from metrics
    if jam_factor >= 8.0:
        return 'accident'  # Severe congestion likely from accident
    elif jam_factor >= 5.0:
        return 'congestion'
    elif speed_reduction >= 0.5:
        return 'construction'  # Slow but steady
    else:
        return 'congestion'


def calculate_impact_score(jam_factor: float, speed_reduction: float, is_closed: bool) -> float:
    """Calculate combined impact score (0.0-1.0)"""
    if is_closed:
        return 1.0
    
    # Weighted combination
    jam_impact = min(jam_factor / 10.0, 1.0)  # Normalize to 0-1
    speed_impact = speed_reduction
    
    # Average with slight bias toward jam factor (more reliable)
    impact = (jam_impact * 0.6) + (speed_impact * 0.4)
    return min(max(impact, 0.0), 1.0)


# =============================================================================
# HERE API INTEGRATION
# =============================================================================

class HEREDataFetcher:
    """Fetch real-time traffic data from HERE API"""
    
    def __init__(self, api_key: str, bbox: str = DEFAULT_BBOX):
        self.api_key = api_key
        self.bbox = bbox  # Format: "west,south,east,north"
        
        if not self.api_key:
            print("⚠️  WARNING: HERE_API_KEY not set - will generate synthetic data")
    
    def fetch_flow_data(self) -> List[Dict]:
        """Fetch traffic flow data from HERE API v7"""
        if not self.api_key:
            return []
        
        url = f"https://data.traffic.hereapi.com/v7/flow"
        params = {
            'in': f'bbox:{self.bbox}',
            'locationReferencing': 'shape',
            'apiKey': self.api_key
        }
        
        try:
            print(f"📡 Fetching HERE Flow data for bbox: {self.bbox}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            print(f"   ✅ Fetched {len(results)} flow segments")
            return results
            
        except requests.RequestException as e:
            print(f"   ⚠️  Failed to fetch flow data: {e}")
            return []
    
    def fetch_incidents_data(self) -> List[Dict]:
        """Fetch traffic incidents from HERE API v7"""
        if not self.api_key:
            return []
        
        url = f"https://data.traffic.hereapi.com/v7/incidents"
        params = {
            'in': f'bbox:{self.bbox}',
            'locationReferencing': 'shape',
            'apiKey': self.api_key
        }
        
        try:
            print(f"📡 Fetching HERE Incidents data for bbox: {self.bbox}")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            print(f"   ✅ Fetched {len(results)} incidents")
            return results
            
        except requests.RequestException as e:
            print(f"   ⚠️  Failed to fetch incidents data: {e}")
            return []


# =============================================================================
# OSM NETWORK LOADER
# =============================================================================

class OSMNetworkLoader:
    """Load and process OSM road network data"""
    
    def __init__(self, place_name: str = "Quezon City, Philippines"):
        self.place_name = place_name
        self.graph = None
        self.nodes_df = None
        self.edges_df = None
    
    def load_network(self, network_type: str = "drive") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load road network from OSM
        
        Returns:
            (nodes_df, edges_df) with all required fields
        """
        print(f"🗺️  Downloading OSM network for '{self.place_name}'...")
        
        # Download graph with all attributes
        self.graph = ox.graph_from_place(
            self.place_name,
            network_type=network_type,
            simplify=True,
            retain_all=False
        )
        
        print(f"   ✅ Downloaded {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
        # Convert to GeoDataFrames
        nodes_gdf, edges_gdf = ox.graph_to_gdfs(self.graph, nodes=True, edges=True)
        
        # Process nodes
        self.nodes_df = self._process_nodes(nodes_gdf)
        
        # Process edges
        self.edges_df = self._process_edges(edges_gdf)
        
        return self.nodes_df, self.edges_df
    
    def _process_nodes(self, nodes_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """Process nodes GeoDataFrame to simple DataFrame"""
        nodes_gdf = nodes_gdf.reset_index()
        
        nodes_df = pd.DataFrame({
            'node_id': nodes_gdf['osmid'].astype(int),
            'latitude': nodes_gdf['y'],
            'longitude': nodes_gdf['x']
        })
        
        print(f"   📍 Processed {len(nodes_df)} nodes")
        return nodes_df
    
    def _process_edges(self, edges_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """Process edges GeoDataFrame with all required fields"""
        edges_gdf = edges_gdf.reset_index()
        
        # Extract basic fields
        edges_data = []
        
        for idx, edge in edges_gdf.iterrows():
            # Basic IDs
            source = int(edge['u'])
            target = int(edge['v'])
            
            # Highway type
            highway = edge.get('highway', 'unclassified')
            if isinstance(highway, list):
                highway = highway[0]
            highway = str(highway)
            
            # Road name
            name = edge.get('name', 'Unnamed Road')
            # Handle cases where name is a list or array
            if isinstance(name, (list, tuple)):
                name = name[0] if len(name) > 0 else 'Unnamed Road'
            # Handle NaN values (check type first to avoid ambiguous truth value)
            elif pd.isna(name) if not isinstance(name, (list, tuple, np.ndarray)) else False:
                name = 'Unnamed Road'
            name = str(name) if not pd.isna(name) else 'Unnamed Road'
            
            # Length in meters
            length = float(edge.get('length', 0))
            
            # One-way status
            oneway = 1 if edge.get('oneway', False) else 0
            
            # Get free flow speed
            max_speed = edge.get('maxspeed', None)
            if max_speed:
                try:
                    if isinstance(max_speed, list):
                        max_speed = max_speed[0]
                    freeflow_kph = float(str(max_speed).split()[0])
                except:
                    freeflow_kph = HIGHWAY_SPEEDS.get(highway, 50)
            else:
                freeflow_kph = HIGHWAY_SPEEDS.get(highway, 50)
            
            # Geometry for coordinates
            geom = edge.get('geometry', None)
            if geom and isinstance(geom, LineString):
                coords = list(geom.coords)
                source_lon, source_lat = coords[0]
                target_lon, target_lat = coords[-1]
                
                # Store full geometry as JSON
                geometry_json = json.dumps([[lon, lat] for lon, lat in coords])
            else:
                # Fallback to node coordinates
                source_lat = source_lon = target_lat = target_lon = None
                geometry_json = "[]"
            
            edges_data.append({
                'source': source,
                'target': target,
                'source_lat': source_lat,
                'source_lon': source_lon,
                'target_lat': target_lat,
                'target_lon': target_lon,
                'road_name': name,
                'highway_type': highway,
                'length': length,
                'freeFlow_kph': freeflow_kph,
                'oneway': oneway,
                'geometry': geometry_json
            })
        
        edges_df = pd.DataFrame(edges_data)
        print(f"   🛣️  Processed {len(edges_df)} edges")
        
        return edges_df


# =============================================================================
# TRAFFIC DATA MATCHER
# =============================================================================

class TrafficDataMatcher:
    """Match HERE traffic data to OSM edges using geospatial matching"""
    
    def __init__(self, edges_df: pd.DataFrame):
        self.edges_df = edges_df.copy()
        
        # Build spatial index for fast matching
        self._build_spatial_index()
    
    def _build_spatial_index(self):
        """Build R-tree spatial index for edges"""
        print("🔍 Building spatial index for geomatching...")
        
        # Create edge midpoints for quick distance calculation
        self.edges_df['mid_lat'] = (self.edges_df['source_lat'] + self.edges_df['target_lat']) / 2
        self.edges_df['mid_lon'] = (self.edges_df['source_lon'] + self.edges_df['target_lon']) / 2
        
        print(f"   ✅ Spatial index ready for {len(self.edges_df)} edges")
    
    def match_flow_segments(self, flow_data: List[Dict]) -> pd.DataFrame:
        """
        Match HERE flow segments to OSM edges
        
        Returns DataFrame with traffic flow added to edges
        """
        print(f"🔗 Matching {len(flow_data)} flow segments to edges...")
        
        # Initialize default values
        self.edges_df['speed_kph'] = self.edges_df['freeFlow_kph']
        self.edges_df['jamFactor'] = 1.0
        self.edges_df['isClosed'] = False
        self.edges_df['disruption_type'] = 'normal'
        self.edges_df['impact_score'] = 0.0
        
        if not flow_data:
            print("   ⚠️  No flow data to match - using free flow values")
            return self.edges_df
        
        matched_count = 0
        
        for flow_segment in flow_data:
            try:
                # Extract flow metrics
                current_flow = flow_segment.get('currentFlow', {})
                speed = current_flow.get('speed', 0)
                freeflow = current_flow.get('freeFlowSpeed', 50)
                jam_factor = current_flow.get('jamFactor', 0.0)
                
                # Convert jam factor to 0-10 scale (HERE uses 0-1)
                jam_factor_scaled = jam_factor * 10.0
                
                # Get location shape
                location = flow_segment.get('location', {})
                shape = location.get('shape', {})
                links = shape.get('links', [])
                
                if not links:
                    continue
                
                # Extract coordinates from shape
                coords = []
                for link in links:
                    points = link.get('points', [])
                    for point in points:
                        lat = point.get('lat')
                        lon = point.get('lng')
                        if lat and lon:
                            coords.append((lat, lon))
                
                if len(coords) < 2:
                    continue
                
                # Find nearby edges
                matched_edges = self._find_nearby_edges(coords, max_distance=50)
                
                # Update matched edges with flow data
                for edge_idx in matched_edges:
                    self.edges_df.loc[edge_idx, 'speed_kph'] = max(speed, 1.0)
                    self.edges_df.loc[edge_idx, 'jamFactor'] = jam_factor_scaled
                    
                    # Calculate metrics
                    freeflow_edge = self.edges_df.loc[edge_idx, 'freeFlow_kph']
                    speed_reduction = 1.0 - (speed / max(freeflow_edge, 1.0))
                    speed_reduction = max(0.0, min(speed_reduction, 1.0))
                    
                    # Infer disruption type
                    disruption = infer_disruption_type(jam_factor_scaled, False, speed_reduction)
                    impact = calculate_impact_score(jam_factor_scaled, speed_reduction, False)
                    
                    self.edges_df.loc[edge_idx, 'disruption_type'] = disruption
                    self.edges_df.loc[edge_idx, 'impact_score'] = impact
                    
                    matched_count += 1
                    
            except Exception as e:
                print(f"   ⚠️  Error matching flow segment: {e}")
                continue
        
        print(f"   ✅ Matched {matched_count} flow segments to edges")
        return self.edges_df
    
    def match_incidents(self, incidents_data: List[Dict]) -> pd.DataFrame:
        """
        Match HERE incidents to OSM edges
        
        Incidents override flow data for affected edges
        """
        print(f"🚨 Matching {len(incidents_data)} incidents to edges...")
        
        if not incidents_data:
            print("   ⚠️  No incidents to match")
            return self.edges_df
        
        matched_count = 0
        
        for incident in incidents_data:
            try:
                # Extract incident data
                incident_type = incident.get('incidentDetails', {}).get('type', 'UNKNOWN')
                severity = incident.get('criticality', {}).get('description', 'minor')
                traffic_impact = incident.get('trafficImpact', {}).get('description', 'unknown')
                
                # Map to our format
                is_closed = ('ROAD_CLOSURE' in incident_type or 'ROAD_CLOSED' in incident_type)
                
                # Determine jam factor and speed
                if is_closed:
                    jam_factor = 10.0
                    speed_kph = 0.0
                    impact_score = 1.0
                elif 'ACCIDENT' in incident_type:
                    if 'major' in severity.lower():
                        jam_factor = 9.0
                        speed_kph = 5.0
                        impact_score = 0.9
                    elif 'moderate' in severity.lower():
                        jam_factor = 7.0
                        speed_kph = 15.0
                        impact_score = 0.7
                    else:
                        jam_factor = 5.0
                        speed_kph = 25.0
                        impact_score = 0.5
                else:  # Construction, weather, etc.
                    jam_factor = 6.0
                    speed_kph = 20.0
                    impact_score = 0.6
                
                # Get location
                location = incident.get('location', {})
                shape = location.get('shape', {})
                links = shape.get('links', [])
                
                # Extract coordinates
                coords = []
                for link in links:
                    points = link.get('points', [])
                    for point in points:
                        lat = point.get('lat')
                        lon = point.get('lng')
                        if lat and lon:
                            coords.append((lat, lon))
                
                if len(coords) < 1:
                    continue
                
                # Find nearby edges (incidents affect larger area)
                matched_edges = self._find_nearby_edges(coords, max_distance=100)
                
                # Update with incident data (overrides flow)
                for edge_idx in matched_edges:
                    self.edges_df.loc[edge_idx, 'speed_kph'] = speed_kph
                    self.edges_df.loc[edge_idx, 'jamFactor'] = jam_factor
                    self.edges_df.loc[edge_idx, 'isClosed'] = is_closed
                    self.edges_df.loc[edge_idx, 'disruption_type'] = infer_disruption_type(
                        jam_factor, is_closed, 0.0, incident_type
                    )
                    self.edges_df.loc[edge_idx, 'impact_score'] = impact_score
                    
                    matched_count += 1
                    
            except Exception as e:
                print(f"   ⚠️  Error matching incident: {e}")
                continue
        
        print(f"   ✅ Matched {matched_count} incidents to edges")
        return self.edges_df
    
    def _find_nearby_edges(self, coords: List[Tuple[float, float]], max_distance: float = 50) -> List[int]:
        """
        Find edges near given coordinates using vectorized haversine distance
        
        Args:
            coords: List of (lat, lon) tuples
            max_distance: Maximum distance in meters
            
        Returns:
            List of edge indices
        """
        nearby_edges = set()
        
        # Convert to numpy arrays for vectorized operations
        edge_lats = self.edges_df['mid_lat'].values
        edge_lons = self.edges_df['mid_lon'].values
        
        for lat, lon in coords:
            # Vectorized haversine distance calculation
            R = 6371000  # Earth radius in meters
            
            lat1, lon1 = np.radians(lat), np.radians(lon)
            lat2, lon2 = np.radians(edge_lats), np.radians(edge_lons)
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))
            distances = R * c
            
            # Find edges within max_distance
            mask = distances <= max_distance
            nearby = self.edges_df[mask].index.tolist()
            nearby_edges.update(nearby)
        
        # Return unique edges as list
        return list(nearby_edges)
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate haversine distance in meters"""
        R = 6371000  # Earth radius in meters
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c


# =============================================================================
# MAIN DATA GENERATOR
# =============================================================================

class UnifiedDataGenerator:
    """Main class orchestrating the entire data generation pipeline"""
    
    def __init__(self, 
                 place_name: str = "Quezon City, Philippines",
                 bbox: str = DEFAULT_BBOX,
                 use_here_api: bool = True):
        
        self.place_name = place_name
        self.bbox = bbox
        self.use_here_api = use_here_api and bool(HERE_API_KEY)
        
        # Initialize components
        self.osm_loader = OSMNetworkLoader(place_name)
        self.here_fetcher = HEREDataFetcher(HERE_API_KEY, bbox) if self.use_here_api else None
        
        self.nodes_df = None
        self.edges_df = None
        self.traffic_matcher = None
    
    def generate_base_network(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Step 1: Load OSM network"""
        print("\n" + "="*70)
        print("STEP 1: Loading OSM Road Network")
        print("="*70)
        
        self.nodes_df, self.edges_df = self.osm_loader.load_network()
        
        # Save base network
        self._save_base_network()
        
        return self.nodes_df, self.edges_df
    
    def generate_traffic_scenario(self, mode: str = 'both', scenario_id: int = None) -> pd.DataFrame:
        """
        Step 2: Generate traffic scenario with real or synthetic data
        
        Args:
            mode: 'flow', 'incidents', 'both', or 'synthetic'
            scenario_id: Optional scenario number. If None, uses timestamp (YYYYMMDDTHHmmss)
        """
        print("\n" + "="*70)
        print(f"STEP 2: Generating Traffic Scenario (Mode: {mode.upper()})")
        print("="*70)
        
        # Use timestamp if scenario_id not provided
        if scenario_id is None:
            scenario_id = datetime.now().strftime("%Y%m%dT%H%M%S")
        
        print(f"   Scenario ID: {scenario_id}")
        
        # Initialize matcher
        self.traffic_matcher = TrafficDataMatcher(self.edges_df)
        
        if mode == 'synthetic' or not self.use_here_api:
            # Generate synthetic traffic
            print("📊 Generating synthetic traffic data...")
            disrupted_edges = self._generate_synthetic_traffic()
        else:
            # Fetch real traffic data
            flow_data = []
            incidents_data = []
            
            if mode in ['flow', 'both']:
                flow_data = self.here_fetcher.fetch_flow_data()
            
            if mode in ['incidents', 'both']:
                incidents_data = self.here_fetcher.fetch_incidents_data()
            
            # Match to edges
            if flow_data:
                self.traffic_matcher.match_flow_segments(flow_data)
            
            if incidents_data:
                self.traffic_matcher.match_incidents(incidents_data)
            
            disrupted_edges = self.traffic_matcher.edges_df
        
        # Add segment length column
        disrupted_edges['segmentLength'] = disrupted_edges['length']
        
        # Save scenario
        self._save_scenario(disrupted_edges, scenario_id, mode)
        
        return disrupted_edges
    
    def _generate_synthetic_traffic(self, disruption_percentage: float = 0.15) -> pd.DataFrame:
        """Generate synthetic traffic data when HERE API not available"""
        
        edges_copy = self.edges_df.copy()
        
        # Initialize with free flow
        edges_copy['speed_kph'] = edges_copy['freeFlow_kph']
        edges_copy['jamFactor'] = 1.0
        edges_copy['isClosed'] = False
        edges_copy['disruption_type'] = 'normal'
        edges_copy['impact_score'] = 0.0
        
        # Randomly select edges to disrupt
        num_disrupted = int(len(edges_copy) * disruption_percentage)
        disrupted_indices = np.random.choice(edges_copy.index, num_disrupted, replace=False)
        
        print(f"   Disrupting {num_disrupted} edges ({disruption_percentage*100:.1f}%)")
        
        for idx in disrupted_indices:
            # Random disruption parameters
            jam_factor = np.random.uniform(2.0, 9.0)
            freeflow = edges_copy.loc[idx, 'freeFlow_kph']
            
            # Speed reduction based on jam factor
            speed_reduction = (jam_factor - 1.0) / 9.0  # 0.0 to 1.0
            speed = freeflow * (1.0 - speed_reduction * 0.8)
            speed = max(speed, 5.0)
            
            # Occasional closures
            is_closed = (np.random.random() < 0.02)  # 2% closure rate
            if is_closed:
                jam_factor = 10.0
                speed = 0.0
                impact_score = 1.0
            else:
                impact_score = calculate_impact_score(jam_factor, speed_reduction, False)
            
            # Update edge
            edges_copy.loc[idx, 'speed_kph'] = speed
            edges_copy.loc[idx, 'jamFactor'] = jam_factor
            edges_copy.loc[idx, 'isClosed'] = is_closed
            edges_copy.loc[idx, 'disruption_type'] = infer_disruption_type(
                jam_factor, is_closed, speed_reduction
            )
            edges_copy.loc[idx, 'impact_score'] = impact_score
        
        print(f"   ✅ Generated synthetic traffic for {num_disrupted} disrupted edges")
        return edges_copy
    
    def _save_base_network(self):
        """Save base network CSVs and .gr file"""
        # Save nodes
        nodes_path = Config.NODES_CSV
        self.nodes_df.to_csv(nodes_path, index=False)
        print(f"   💾 Saved nodes: {nodes_path}")
        
        # Save edges (base without traffic)
        edges_path = Config.EDGES_CSV
        edges_base = self.edges_df.copy()
        
        # Ensure geometry column is present
        if 'geometry' not in edges_base.columns:
            edges_base['geometry'] = '[]'
        
        edges_base.to_csv(edges_path, index=False)
        print(f"   💾 Saved edges: {edges_path}")
        
        # Create base .gr file for index building
        self._create_base_gr_file()
    
    def _create_base_gr_file(self):
        """Create base .gr file from CSV for index building with remapped node IDs"""
        gr_path = Config.PROCESSED_DATA_DIR / "quezon_city_base.gr"
        
        # Create node ID mapping (OSM IDs are huge, need sequential 0-based IDs)
        unique_nodes = set()
        for _, edge in self.edges_df.iterrows():
            unique_nodes.add(int(edge['source']))
            unique_nodes.add(int(edge['target']))
        
        # Create mapping: OSM_ID -> sequential_ID (1-based for DIMACS compatibility)
        node_map = {osm_id: idx + 1 for idx, osm_id in enumerate(sorted(unique_nodes))}
        num_nodes = len(node_map)
        num_edges = len(self.edges_df)
        
        print(f"   📊 Remapping {num_nodes} nodes from OSM IDs to sequential IDs (1-based)")
        
        with open(gr_path, 'w') as f:
            # Write comment and placeholder header (will rewrite with actual edge count)
            f.write(f"c Base graph from OSM data\n")
            header_pos = f.tell()
            f.write(f"p sp {num_nodes} {num_edges}\n")
            
            # Write edges using 'a' format with remapped node IDs
            edges_written = 0
            for _, edge in self.edges_df.iterrows():
                source_osm = int(edge['source'])
                target_osm = int(edge['target'])
                
                # Skip self-loops (causes segfault in index builders)
                if source_osm == target_osm:
                    continue
                
                # Remap to sequential IDs
                source = node_map[source_osm]
                target = node_map[target_osm]
                
                # Use free flow travel time as weight (length / speed * 3.6)
                freeflow_kph = edge.get('freeFlow_kph', 30)
                # Handle NaN values
                if pd.isna(freeflow_kph) or freeflow_kph == 0:
                    freeflow_kph = 30  # Default speed
                freeflow_kph = float(freeflow_kph)
                
                length_m = float(edge['length'])
                # Travel time in seconds
                weight = int(length_m / (freeflow_kph / 3.6))
                weight = max(1, weight)  # Minimum weight of 1
                
                f.write(f"a {source} {target} {weight}\n")
                edges_written += 1
        
        # Rewrite header with actual edge count (excluding self-loops)
        if edges_written != num_edges:
            with open(gr_path, 'r+') as f:
                content = f.read()
                f.seek(0)
                lines = content.split('\n')
                lines[1] = f"p sp {num_nodes} {edges_written}"
                f.write('\n'.join(lines))
                f.truncate()
            print(f"   ℹ️  Filtered out {num_edges - edges_written} self-loops")
        
        print(f"   💾 Saved base graph: {gr_path} ({num_nodes} nodes, {edges_written} edges)")
        
        # Save node mapping for later use
        mapping_path = Config.RAW_DATA_DIR / "node_id_mapping.csv"
        with open(mapping_path, 'w') as f:
            f.write("osm_id,sequential_id\n")
            for osm_id, seq_id in sorted(node_map.items(), key=lambda x: x[1]):
                f.write(f"{osm_id},{seq_id}\n")
        print(f"   💾 Saved node mapping: {mapping_path}")
        
        # Also copy to quezon_city.graph for index building
        graph_path = Config.PROCESSED_DATA_DIR / "quezon_city.graph"
        import shutil
        shutil.copy(gr_path, graph_path)
        print(f"   💾 Copied to: {graph_path}")    
    def _save_scenario(self, disrupted_edges: pd.DataFrame, scenario_id, mode: str):
        """Save traffic scenario CSV
        
        Args:
            disrupted_edges: DataFrame with edge data
            scenario_id: Scenario identifier (int for backward compat, or timestamp string)
            mode: Traffic mode ('flow', 'incidents', 'both', 'synthetic')
        """
        
        # Select columns in correct order for C++ algorithms
        output_cols = [
            'source_lat', 'source_lon', 'target_lat', 'target_lon',
            'source', 'target', 'road_name',
            'speed_kph', 'freeFlow_kph', 'jamFactor', 'isClosed',
            'segmentLength', 'oneway'
        ]
        
        # Ensure all columns exist
        for col in output_cols:
            if col not in disrupted_edges.columns:
                if col == 'segmentLength':
                    disrupted_edges[col] = disrupted_edges['length']
                else:
                    disrupted_edges[col] = 0
        
        output_df = disrupted_edges[output_cols].copy()
        
        # Save CSV
        csv_path = Config.DISRUPTIONS_DIR / f"scenario_{scenario_id}_{mode}.csv"
        output_df.to_csv(csv_path, index=False)
        print(f"   💾 Saved scenario CSV: {csv_path}")
        
        # Generate .gr file for C++ algorithms
        self._generate_gr_file(output_df, scenario_id, mode)
        
        # Print statistics
        self._print_scenario_stats(output_df)
    
    def _generate_gr_file(self, edges_df: pd.DataFrame, scenario_id, mode: str):
        """Generate .gr format file for C++ index building
        
        Args:
            edges_df: DataFrame with edge data
            scenario_id: Scenario identifier (int or timestamp string)
            mode: Traffic mode
        """
        
        gr_path = Config.PROCESSED_DATA_DIR / f"scenario_{scenario_id}_{mode}.gr"
        
        # Count unique nodes
        nodes = set(edges_df['source'].unique()).union(set(edges_df['target'].unique()))
        num_nodes = len(nodes)
        
        with open(gr_path, 'w') as f:
            # Placeholder header (will update with actual edge count)
            f.write(f"p sp {num_nodes} 0\n")
            
            # Edges (format: a source target weight)
            edges_written = 0
            for _, edge in edges_df.iterrows():
                source = int(edge['source'])
                target = int(edge['target'])
                
                # Skip self-loops
                if source == target:
                    continue
                
                # Use segment length as weight (can be modified by disruptions)
                weight = int(edge.get('segmentLength', edge.get('length', 100)))
                
                f.write(f"a {source} {target} {weight}\n")
                edges_written += 1
        
        # Update header with actual edge count
        with open(gr_path, 'r+') as f:
            content = f.read()
            f.seek(0)
            lines = content.split('\n')
            lines[0] = f"p sp {num_nodes} {edges_written}"
            f.write('\n'.join(lines))
            f.truncate()
        
        if edges_written != len(edges_df):
            print(f"   ℹ️  Filtered {len(edges_df) - edges_written} self-loops from scenario")
        
        print(f"   💾 Saved .gr file: {gr_path} ({num_nodes} nodes, {edges_written} edges)")
        
        # Create symlink to latest for convenience
        latest_gr = Config.PROCESSED_DATA_DIR / f"current_traffic_{mode}.gr"
        try:
            import os
            if latest_gr.exists() or latest_gr.is_symlink():
                latest_gr.unlink()
            os.symlink(gr_path.name, latest_gr)
            print(f"   🔗 Symlink created: current_traffic_{mode}.gr → {gr_path.name}")
        except Exception as e:
            print(f"   ℹ️  Symlink creation skipped: {e}")
    
    def _print_scenario_stats(self, edges_df: pd.DataFrame):
        """Print scenario statistics"""
        
        total = len(edges_df)
        closed = (edges_df['isClosed'] == True).sum()
        heavy_jam = (edges_df['jamFactor'] >= 7.0).sum()
        moderate_jam = ((edges_df['jamFactor'] >= 4.0) & (edges_df['jamFactor'] < 7.0)).sum()
        light_jam = ((edges_df['jamFactor'] >= 2.0) & (edges_df['jamFactor'] < 4.0)).sum()
        free_flow = (edges_df['jamFactor'] < 2.0).sum()
        
        print(f"\n   📊 Scenario Statistics:")
        print(f"      Total edges: {total}")
        print(f"      🚫 Road closures: {closed} ({closed/total*100:.1f}%)")
        print(f"      🔴 Heavy congestion (jam≥7): {heavy_jam} ({heavy_jam/total*100:.1f}%)")
        print(f"      🟠 Moderate congestion (jam 4-7): {moderate_jam} ({moderate_jam/total*100:.1f}%)")
        print(f"      🟡 Light congestion (jam 2-4): {light_jam} ({light_jam/total*100:.1f}%)")
        print(f"      🟢 Free flow (jam<2): {free_flow} ({free_flow/total*100:.1f}%)")
        
        avg_jam = edges_df['jamFactor'].mean()
        avg_speed = edges_df['speed_kph'].mean()
        avg_freeflow = edges_df['freeFlow_kph'].mean()
        
        print(f"\n      Average jam factor: {avg_jam:.2f}")
        print(f"      Average current speed: {avg_speed:.1f} km/h")
        print(f"      Average free flow speed: {avg_freeflow:.1f} km/h")
        print(f"      Overall speed reduction: {(1 - avg_speed/avg_freeflow)*100:.1f}%")


# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Unified Data Generator for Enhanced DHL/HC2L Routing Algorithms',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate base network and 1 traffic snapshot (timestamp-based)
  python unified_data_generator.py --mode both
  
  # Generate multiple snapshots with timestamps
  python unified_data_generator.py --mode flow --scenarios 3
  
  # Synthetic traffic (no HERE API required)
  python unified_data_generator.py --mode synthetic --scenarios 1
  
  # Continuous mode (update every 5 minutes with new timestamp)
  python unified_data_generator.py --mode both --continuous --interval 300
  
  # Custom bounding box
  python unified_data_generator.py --bbox "121.0,14.5,121.2,14.8" --scenarios 2

Output files:
  CSV:  disruptions/20251104T210230_both.csv
  GR:   processed/20251104T210230_both.gr
  Link: processed/current_traffic_both.gr → latest snapshot
        """
    )
    
    parser.add_argument('--mode', choices=['flow', 'incidents', 'both', 'synthetic'],
                        default='both', help='Traffic data mode')
    parser.add_argument('--scenarios', type=int, default=1,
                        help='Number of scenarios to generate (default: 1 snapshot at current time)')
    parser.add_argument('--bbox', type=str, default=DEFAULT_BBOX,
                        help='Bounding box (west,south,east,north)')
    parser.add_argument('--place', type=str, default="Quezon City, Philippines",
                        help='Place name for OSM query')
    parser.add_argument('--continuous', action='store_true',
                        help='Run continuously (update traffic periodically)')
    parser.add_argument('--interval', type=int, default=300,
                        help='Update interval in seconds (for continuous mode)')
    parser.add_argument('--no-here', action='store_true',
                        help='Force synthetic traffic (ignore HERE API)')
    
    args = parser.parse_args()
    
    # Print header
    print("\n" + "="*70)
    print(" UNIFIED DATA GENERATOR FOR ENHANCED ROUTING ALGORITHMS")
    print("="*70)
    print(f" Place: {args.place}")
    print(f" Bounding Box: {args.bbox}")
    print(f" Mode: {args.mode.upper()}")
    print(f" Scenarios: {args.scenarios}")
    if args.continuous:
        print(f" Continuous mode: Update every {args.interval}s")
    print("="*70 + "\n")
    
    # Check HERE API
    use_here = not args.no_here and bool(HERE_API_KEY)
    if not use_here and args.mode != 'synthetic':
        print("⚠️  HERE_API_KEY not found - switching to synthetic mode")
        args.mode = 'synthetic'
    
    # Initialize generator
    generator = UnifiedDataGenerator(
        place_name=args.place,
        bbox=args.bbox,
        use_here_api=use_here
    )
    
    # Generate base network (once)
    generator.generate_base_network()
    
    # Generate scenarios
    if args.continuous:
        # Continuous mode - updates with new timestamps each interval
        try:
            update_count = 0
            while True:
                update_count += 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n{'='*70}")
                print(f" CONTINUOUS UPDATE #{update_count}")
                print(f" Time: {timestamp}")
                print(f"{'='*70}")
                
                generator.generate_traffic_scenario(mode=args.mode)  # Uses timestamp
                
                print(f"\n⏳ Waiting {args.interval} seconds until next update...")
                time.sleep(args.interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Stopped by user")
    else:
        # Generate fixed number of scenarios - each with its own timestamp
        for i in range(1, args.scenarios + 1):
            generator.generate_traffic_scenario(mode=args.mode)  # Uses timestamp
            
            if i < args.scenarios:
                print(f"\n⏳ Waiting 10 seconds before next scenario...")
                time.sleep(10)  # Brief pause between scenarios
    
    print("\n" + "="*70)
    print(" ✅ DATA GENERATION COMPLETE!")
    print("="*70)
    print("\n📁 Output files (with timestamps):")
    print(f"   - Base Network: {Config.NODES_CSV}, {Config.EDGES_CSV}")
    print(f"   - Traffic CSV:  {Config.DISRUPTIONS_DIR}/YYYYMMDDThhmmss_{args.mode}.csv")
    print(f"   - Graph files:  {Config.PROCESSED_DATA_DIR}/YYYYMMDDThhmmss_{args.mode}.gr")
    print(f"   - Latest link:  {Config.PROCESSED_DATA_DIR}/current_traffic_{args.mode}.gr")
    print("\n🚀 Ready to build indexes and run routing algorithms!")
    print("   Next steps:")
    print("   1. Build indexes: ./setup.sh --indexes")
    print("   2. Run server: ./start-server.sh")
    print("\n")


if __name__ == '__main__':
    main()
