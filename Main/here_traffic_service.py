"""
HERE Traffic API Integration Service
Fetches real-time traffic data and converts it to disruption format
"""

import os
import requests
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
from config import Config
import json
from datetime import datetime
from geospatial_matcher import GeospatialMatcher

# Load environment variables
load_dotenv()

class HERETrafficService:
    """Service for fetching and processing HERE traffic data"""
    
    def __init__(self):
        self.api_key = os.getenv('HERE_API_KEY', '')
        self.bbox = "121.01,14.59,121.14,14.76"  # Quezon City bounds
        self.traffic_mode = 'none'  # Options: 'none', 'incidents', 'flow', 'both'
        self.geospatial_matcher = None  # Lazy initialization
        
        if not self.api_key:
            print("⚠️  Warning: HERE_API_KEY not found in environment variables")
            print("   Set it in .env file or disable HERE API integration")
    
    def _get_geospatial_matcher(self) -> GeospatialMatcher:
        """Lazy initialization of geospatial matcher"""
        if self.geospatial_matcher is None:
            self.geospatial_matcher = GeospatialMatcher(Config.EDGES_CSV, Config.NODES_CSV)
        return self.geospatial_matcher
    
    def set_traffic_mode(self, mode: str):
        """
        Set the traffic data mode
        Args:
            mode: 'none', 'incidents', 'flow', or 'both'
        """
        if mode not in ['none', 'incidents', 'flow', 'both']:
            raise ValueError(f"Invalid traffic mode: {mode}. Must be 'none', 'incidents', 'flow', or 'both'")
        self.traffic_mode = mode
        print(f"🚦 Traffic mode set to: {mode.upper()}")
    
    def fetch_traffic_flow(self) -> List[Dict]:
        """Fetch real-time traffic flow data from HERE API"""
        if not self.api_key:
            return []
        
        flow_url = f"https://data.traffic.hereapi.com/v7/flow?in=bbox:{self.bbox}&locationReferencing=shape&apiKey={self.api_key}"
        
        try:
            print("📡 Fetching HERE Traffic Flow data...")
            response = requests.get(flow_url, timeout=30)
            response.raise_for_status()
            flow_json = response.json()
            flow_data = flow_json.get('results', [])
            print(f"✅ Fetched {len(flow_data)} flow segments")
            return flow_data
        except requests.RequestException as e:
            print(f"⚠️  Failed to fetch flow data: {e}")
            return []
    
    def fetch_traffic_incidents(self) -> List[Dict]:
        """Fetch real-time traffic incidents from HERE API"""
        if not self.api_key:
            return []
        
        incidents_url = f"https://data.traffic.hereapi.com/v7/incidents?in=bbox:{self.bbox}&locationReferencing=shape&apiKey={self.api_key}"
        
        try:
            print("📡 Fetching HERE Traffic Incidents data...")
            response = requests.get(incidents_url, timeout=30)
            response.raise_for_status()
            incidents_json = response.json()
            incidents_data = incidents_json.get('results', [])
            print(f"✅ Fetched {len(incidents_data)} incidents")
            return incidents_data
        except requests.RequestException as e:
            print(f"⚠️  Failed to fetch incidents data: {e}")
            return []
    
    def process_flow_to_disruptions(self, flow_data: List[Dict]) -> List[Dict]:
        """Convert flow data to disruption records"""
        disruptions = []
        
        for flow in flow_data:
            try:
                current_flow = flow.get('currentFlow', {})
                
                # Extract traffic metrics
                speed = current_flow.get('speed', 0)
                free_flow_speed = current_flow.get('freeFlowSpeed', 50)
                jam_factor = current_flow.get('jamFactor', 0.0)
                
                # Calculate speed reduction
                if free_flow_speed > 0:
                    speed_reduction = 1.0 - (speed / free_flow_speed)
                else:
                    speed_reduction = 0.0
                
                # Determine severity (1=Light, 2=Medium, 3=Heavy)
                if jam_factor < 0.3:
                    severity = 1
                elif jam_factor < 0.7:
                    severity = 2
                else:
                    severity = 3
                
                disruptions.append({
                    'type': 'congestion',
                    'severity': severity,
                    'jam_factor': jam_factor,
                    'speed_reduction': speed_reduction,
                    'current_speed': speed,
                    'free_flow_speed': free_flow_speed,
                    'location': flow.get('location', {})
                })
                
            except Exception as e:
                print(f"⚠️  Error processing flow segment: {e}")
                continue
        
        return disruptions
    
    def process_incidents_to_disruptions(self, incidents: List[Dict]) -> List[Dict]:
        """Convert incident data to disruption records"""
        disruptions = []
        
        for incident in incidents:
            try:
                incident_type = incident.get('type', 'UNKNOWN')
                severity = incident.get('severity', 1)
                traffic_impact = incident.get('trafficImpact', 'unknown')
                
                # Determine disruption parameters based on incident type
                if incident_type == 'ROAD_CLOSURE':
                    jam_factor = 10.0  # Complete blockage
                    speed_reduction = 1.0
                    severity_level = 3
                elif incident_type == 'ACCIDENT':
                    if traffic_impact == 'heavy':
                        jam_factor = 8.0
                        speed_reduction = 0.85
                        severity_level = 3
                    elif traffic_impact == 'medium':
                        jam_factor = 6.0
                        speed_reduction = 0.65
                        severity_level = 2
                    else:
                        jam_factor = 4.0
                        speed_reduction = 0.35
                        severity_level = 1
                else:
                    jam_factor = 5.0
                    speed_reduction = 0.4
                    severity_level = 2
                
                disruptions.append({
                    'type': incident_type.lower(),
                    'severity': severity_level,
                    'jam_factor': jam_factor,
                    'speed_reduction': speed_reduction,
                    'location': incident.get('location', {})
                })
                
            except Exception as e:
                print(f"⚠️  Error processing incident: {e}")
                continue
        
        return disruptions
    
    def merge_disruptions(self, incidents: List[Dict], flow: List[Dict]) -> List[Dict]:
        """
        Merge incident and flow disruptions with incident precedence
        
        Args:
            incidents: List of incident-based disruptions
            flow: List of flow-based disruptions
            
        Returns:
            Merged list with incidents taking precedence for overlapping segments
        """
        # Create a map of flow disruptions by location
        flow_map = {}
        for f in flow:
            loc = f.get('location', {})
            loc_key = str(loc)  # Simple key for now
            flow_map[loc_key] = f
        
        # Start with all incidents (they have priority)
        merged = incidents.copy()
        
        # Add flow data that doesn't overlap with incidents
        incident_locs = {str(inc.get('location', {})): True for inc in incidents}
        
        for f in flow:
            loc_key = str(f.get('location', {}))
            if loc_key not in incident_locs:
                merged.append(f)
        
        print(f"   🔀 Merge: {len(incidents)} incidents + {len(flow)-len(merged)+len(incidents)} non-overlapping flow = {len(merged)} total")
        
        return merged
    
    def convert_to_gr_format(self, disruptions: List[Dict], base_edges_df: pd.DataFrame, 
                           output_file: Path, use_geospatial_matching: bool = True) -> int:
        """
        Convert disruptions to .gr format file for C++ routing APIs
        
        Args:
            disruptions: List of disruption dictionaries
            base_edges_df: DataFrame with base graph edges
            output_file: Path to output .gr file
            use_geospatial_matching: Use geospatial matching instead of random sampling
        
        Returns:
            Number of disrupted edges written
        """
        if not disruptions:
            print("⚠️  No disruptions to write")
            return 0
        
        print(f"\n📝 Converting {len(disruptions)} disruptions to .gr format...")
        
        if use_geospatial_matching:
            return self._convert_with_geospatial_matching(disruptions, output_file)
        else:
            return self._convert_with_random_sampling(disruptions, base_edges_df, output_file)
    
    def _convert_with_geospatial_matching(self, disruptions: List[Dict], output_file: Path) -> int:
        """
        Convert disruptions using geospatial matching to road network edges
        
        Args:
            disruptions: List of disruption dictionaries
            output_file: Path to output .gr file
        
        Returns:
            Number of disrupted edges written
        """
        matcher = self._get_geospatial_matcher()
        
        disrupted_edges = []
        matched_count = 0
        total_matches = 0
        
        print(f"   🗺️  Using geospatial matching with highway priority...")
        
        for i, disruption in enumerate(disruptions, 1):
            # Match disruption to edges
            matched_edges = matcher.match_disruption_to_edges(
                disruption,
                max_distance=100.0,  # 100m tolerance
                max_matches=10       # Top 10 best matches
            )
            
            if not matched_edges:
                continue
            
            matched_count += 1
            total_matches += len(matched_edges)
            
            # Process each matched edge
            for match in matched_edges:
                # Calculate impact score
                impact_score = matcher.calculate_impact_score(disruption, match)
                
                # Get disruption parameters
                jam_factor = disruption.get('jam_factor', 5.0)
                speed_reduction = disruption.get('speed_reduction', 0.5)
                current_speed = disruption.get('current_speed', 0)
                free_flow_speed = disruption.get('free_flow_speed', 50.0)
                disruption_type = disruption.get('type', 'unknown')
                
                # Check if road is closed
                is_closed = (disruption_type == 'road_closure' or 
                           jam_factor >= 10.0)
                
                # Calculate new weight
                if is_closed:
                    # Road closure: set to very high weight (effectively infinite)
                    new_weight = 999999.0
                else:
                    # Calculate based on speed reduction and impact
                    base_weight = match.length
                    
                    if current_speed > 0 and free_flow_speed > 0:
                        speed_ratio = current_speed / free_flow_speed
                        new_weight = base_weight / max(speed_ratio, 0.1)
                    else:
                        new_weight = base_weight / max(1.0 - speed_reduction, 0.1)
                    
                    # Apply impact score multiplier
                    new_weight *= (1.0 + impact_score)
                    
                    # Cap maximum weight increase (20x)
                    new_weight = min(new_weight, base_weight * 20.0)
                
                disrupted_edges.append({
                    'source': match.source,
                    'target': match.target,
                    'new_weight': new_weight,
                    'jam_factor': jam_factor,
                    'current_speed': current_speed if current_speed > 0 else free_flow_speed * (1 - speed_reduction),
                    'free_flow_speed': free_flow_speed,
                    'impact_score': impact_score,
                    'match_confidence': match.confidence,
                    'highway_type': match.highway_type,
                    'is_closed': is_closed,
                    'disruption_type': disruption_type
                })
            
            if i % 10 == 0:
                print(f"   Progress: {i}/{len(disruptions)} disruptions processed...")
        
        # Write to .gr file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write(f"c HERE Traffic API disruption file (Geospatial Matching)\n")
            f.write(f"c Generated at {datetime.now().isoformat()}\n")
            f.write(f"c Matched {matched_count}/{len(disruptions)} disruptions to {len(disrupted_edges)} edges\n")
            f.write(f"c Format: source target new_weight jam_factor current_speed free_flow_speed impact_score confidence highway is_closed type\n")
            f.write(f"p sp {len(disrupted_edges)} edges_disrupted\n")
            
            for edge in disrupted_edges:
                f.write(f"{edge['source']} {edge['target']} {edge['new_weight']:.4f} ")
                f.write(f"{edge['jam_factor']:.2f} {edge['current_speed']:.2f} {edge['free_flow_speed']:.2f} ")
                f.write(f"{edge['impact_score']:.4f} {edge['match_confidence']:.4f} ")
                f.write(f"{edge['highway_type']} {1 if edge['is_closed'] else 0} {edge['disruption_type']}\n")
        
        print(f"   ✅ Matched {matched_count}/{len(disruptions)} disruptions ({matched_count/len(disruptions)*100:.1f}%)")
        print(f"   ✅ Wrote {len(disrupted_edges)} disrupted edges to {output_file.name}")
        print(f"   📊 Avg edges per disruption: {total_matches/matched_count:.1f}")
        
        return len(disrupted_edges)
    
    def _convert_with_random_sampling(self, disruptions: List[Dict], 
                                     base_edges_df: pd.DataFrame, 
                                     output_file: Path,
                                     sample_ratio: float = 0.05) -> int:
        """
        Legacy: Convert disruptions using random edge sampling
        
        Args:
            disruptions: List of disruption dictionaries
            base_edges_df: DataFrame with base graph edges
            output_file: Path to output .gr file
            sample_ratio: Ratio of edges to apply each disruption to (default 5%)
        
        Returns:
            Number of disrupted edges written
        """
        print(f"   ⚠️  Using legacy random sampling (not recommended)")
        
        disrupted_edges = []
        
        for disruption in disruptions:
            # Sample edges to apply this disruption
            sample_size = max(1, int(len(base_edges_df) * sample_ratio))
            sample_edges = base_edges_df.sample(n=min(sample_size, len(base_edges_df)))
            
            for _, edge in sample_edges.iterrows():
                source = int(edge['source'])
                target = int(edge['target'])
                base_weight = float(edge['length'])
                
                # Calculate new weight based on speed reduction
                jam_factor = disruption.get('jam_factor', 5.0)
                speed_reduction = disruption.get('speed_reduction', 0.5)
                current_speed = disruption.get('current_speed', 0)
                free_flow_speed = disruption.get('free_flow_speed', 50.0)
                
                # New weight = base_weight / (1 - speed_reduction)
                if current_speed > 0 and free_flow_speed > 0:
                    speed_ratio = current_speed / free_flow_speed
                    new_weight = base_weight / max(speed_ratio, 0.1)
                else:
                    new_weight = base_weight / max(1.0 - speed_reduction, 0.1)
                
                # Cap maximum weight increase (10x)
                new_weight = min(new_weight, base_weight * 10.0)
                
                disrupted_edges.append({
                    'source': source,
                    'target': target,
                    'new_weight': new_weight,
                    'jam_factor': jam_factor,
                    'current_speed': current_speed if current_speed > 0 else free_flow_speed * (1 - speed_reduction),
                    'free_flow_speed': free_flow_speed
                })
        
        # Write to .gr file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write(f"c HERE Traffic API disruption file (Random Sampling)\n")
            f.write(f"c Generated at {datetime.now().isoformat()}\n")
            f.write(f"c Format: source target new_weight jam_factor current_speed free_flow_speed\n")
            f.write(f"p sp {len(disrupted_edges)} edges_disrupted\n")
            
            for edge in disrupted_edges:
                f.write(f"{edge['source']} {edge['target']} {edge['new_weight']:.4f} ")
                f.write(f"{edge['jam_factor']:.2f} {edge['current_speed']:.2f} {edge['free_flow_speed']:.2f}\n")
        
        print(f"✅ Wrote {len(disrupted_edges)} disrupted edges to {output_file}")
        return len(disrupted_edges)
    
    def fetch_and_save_traffic(self, 
                              base_edges_csv: Path = Config.EDGES_CSV,
                              traffic_mode: str = None) -> Tuple[int, Dict]:
        """
        Fetch HERE traffic data and save as separate disruption files
        
        Args:
            base_edges_csv: Path to base edges CSV (default: Config.EDGES_CSV)
            traffic_mode: Override instance traffic_mode ('none', 'incidents', 'flow', 'both')
            
        Returns:
            Tuple of (total_edges_affected, metadata_dict)
        """
        if not self.api_key:
            print("❌ No HERE API key configured")
            return 0, {'error': 'No API key'}
        
        # Use provided mode or instance mode
        mode = traffic_mode if traffic_mode else self.traffic_mode
        print(f"🚦 Traffic Data Mode: {mode.upper()}")
        
        # Handle 'none' mode - no disruptions
        if mode == 'none':
            print("ℹ️  Dataset mode is NONE - no disruptions will be applied")
            # Create empty files for consistency
            self._create_empty_disruption_files()
            return 0, {'traffic_mode': 'none', 'flow_count': 0, 'incident_count': 0, 'total_disruptions': 0}
        
        # Load base edges
        try:
            base_edges_df = pd.read_csv(base_edges_csv)
            print(f"✅ Loaded {len(base_edges_df)} base edges from {base_edges_csv}")
        except Exception as e:
            print(f"❌ Failed to load base edges: {e}")
            return 0, {'error': str(e)}
        
        flow_disruptions = []
        incident_disruptions = []
        
        # Fetch and process based on mode
        if mode in ['flow', 'both']:
            flow_data = self.fetch_traffic_flow()
            flow_disruptions = self.process_flow_to_disruptions(flow_data)
            print(f"   📊 Flow disruptions: {len(flow_disruptions)}")
            
            # Save flow disruptions to separate file
            flow_output = Config.DISRUPTIONS_DIR / "dynamic_disruptions_flow.gr"
            flow_edges = self.convert_to_gr_format(flow_disruptions, base_edges_df, flow_output)
            print(f"   💾 Saved flow disruptions to {flow_output}")
        
        if mode in ['incidents', 'both']:
            incidents_data = self.fetch_traffic_incidents()
            incident_disruptions = self.process_incidents_to_disruptions(incidents_data)
            print(f"   🚨 Incident disruptions: {len(incident_disruptions)}")
            
            # Save incident disruptions to separate file
            incidents_output = Config.DISRUPTIONS_DIR / "dynamic_disruptions_incidents.gr"
            incident_edges = self.convert_to_gr_format(incident_disruptions, base_edges_df, incidents_output)
            print(f"   � Saved incident disruptions to {incidents_output}")
        
        # For 'both' mode, also create a merged file (incidents have precedence)
        if mode == 'both':
            merged_disruptions = self.merge_disruptions(incident_disruptions, flow_disruptions)
            merged_output = Config.DISRUPTIONS_DIR / "dynamic_disruptions_both.gr"
            merged_edges = self.convert_to_gr_format(merged_disruptions, base_edges_df, merged_output)
            print(f"   💾 Saved merged disruptions to {merged_output}")
        
        # Create symlink for current mode (for backward compatibility)
        self._create_current_symlink(mode)
        
        metadata = {
            'traffic_mode': mode,
            'flow_count': len(flow_disruptions),
            'incident_count': len(incident_disruptions),
            'total_disruptions': len(flow_disruptions) + len(incident_disruptions),
            'timestamp': datetime.now().isoformat()
        }
        
        total_edges = 0
        if mode == 'flow':
            total_edges = len(flow_disruptions)
        elif mode == 'incidents':
            total_edges = len(incident_disruptions)
        elif mode == 'both':
            total_edges = len(merged_disruptions)
        
        return total_edges, metadata
    
    def _create_empty_disruption_files(self):
        """Create empty disruption files when mode is 'none'"""
        for filename in ['dynamic_disruptions_flow.gr', 'dynamic_disruptions_incidents.gr', 'dynamic_disruptions_both.gr']:
            filepath = Config.DISRUPTIONS_DIR / filename
            filepath.write_text("")
            print(f"   📄 Created empty file: {filepath}")
    
    def _create_current_symlink(self, mode: str):
        """Create symlink to current disruption file based on mode"""
        import os
        
        source_file = f"dynamic_disruptions_{mode}.gr"
        target_file = Config.DISRUPTIONS_DIR / "dynamic_disruptions_current.gr"
        
        # Remove existing symlink/file
        if target_file.exists() or target_file.is_symlink():
            target_file.unlink()
        
        try:
            # Create symlink
            os.symlink(source_file, target_file)
            print(f"   🔗 Created symlink: dynamic_disruptions_current.gr -> {source_file}")
        except Exception as e:
            print(f"   ⚠️  Could not create symlink: {e}")
            # Fallback: copy file instead
            source_path = Config.DISRUPTIONS_DIR / source_file
            if source_path.exists():
                import shutil
                shutil.copy(source_path, target_file)
                print(f"   📋 Copied {source_file} to dynamic_disruptions_current.gr")


# Global service instance
_here_service = None

def get_here_traffic_service() -> HERETrafficService:
    """Get or create the global HERE traffic service instance"""
    global _here_service
    if _here_service is None:
        _here_service = HERETrafficService()
    return _here_service


if __name__ == "__main__":
    # Test the service
    service = HERETrafficService()
    
    base_edges = Config.EDGES_CSV
    output_file = Config.DISRUPTIONS_DIR / "here_traffic_disruptions.gr"
    
    edges_count, metadata = service.fetch_and_generate_disruptions(base_edges, output_file)
    
    print(f"\n📊 Results:")
    print(f"   Flow disruptions: {metadata.get('flow_count', 0)}")
    print(f"   Incident disruptions: {metadata.get('incident_count', 0)}")
    print(f"   Total edges affected: {metadata.get('edges_affected', 0)}")
