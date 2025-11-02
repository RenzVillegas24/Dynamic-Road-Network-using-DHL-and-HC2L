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

# Load environment variables
load_dotenv()

class HERETrafficService:
    """Service for fetching and processing HERE traffic data"""
    
    def __init__(self):
        self.api_key = os.getenv('HERE_API_KEY', '')
        self.bbox = "121.01,14.59,121.14,14.76"  # Quezon City bounds
        
        if not self.api_key:
            print("⚠️  Warning: HERE_API_KEY not found in environment variables")
            print("   Set it in .env file or disable HERE API integration")
    
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
    
    def convert_to_gr_format(self, disruptions: List[Dict], base_edges_df: pd.DataFrame, 
                           output_file: Path, sample_ratio: float = 0.05) -> int:
        """
        Convert disruptions to .gr format file for C++ routing APIs
        
        Args:
            disruptions: List of disruption dictionaries
            base_edges_df: DataFrame with base graph edges
            output_file: Path to output .gr file
            sample_ratio: Ratio of edges to apply each disruption to (default 5%)
        
        Returns:
            Number of disrupted edges written
        """
        if not disruptions:
            print("⚠️  No disruptions to write")
            return 0
        
        print(f"\n📝 Converting {len(disruptions)} disruptions to .gr format...")
        
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
            f.write(f"c HERE Traffic API disruption file\n")
            f.write(f"c Generated at {datetime.now().isoformat()}\n")
            f.write(f"c Format: source target new_weight jam_factor current_speed free_flow_speed\n")
            f.write(f"p sp {len(disrupted_edges)} edges_disrupted\n")
            
            for edge in disrupted_edges:
                f.write(f"{edge['source']} {edge['target']} {edge['new_weight']:.4f} ")
                f.write(f"{edge['jam_factor']:.2f} {edge['current_speed']:.2f} {edge['free_flow_speed']:.2f}\n")
        
        print(f"✅ Wrote {len(disrupted_edges)} disrupted edges to {output_file}")
        return len(disrupted_edges)
    
    def fetch_and_generate_disruptions(self, base_edges_csv: Path, 
                                      output_file: Path) -> Tuple[int, Dict]:
        """
        Main method: Fetch HERE data and generate disruption file
        
        Returns:
            Tuple of (edges_count, metadata_dict)
        """
        print("\n" + "="*70)
        print("  HERE Traffic API Integration")
        print("="*70)
        
        if not self.api_key:
            print("❌ No HERE API key configured")
            return 0, {'error': 'No API key'}
        
        # Fetch traffic data
        flow_data = self.fetch_traffic_flow()
        incidents_data = self.fetch_traffic_incidents()
        
        # Process to disruptions
        flow_disruptions = self.process_flow_to_disruptions(flow_data)
        incident_disruptions = self.process_incidents_to_disruptions(incidents_data)
        
        all_disruptions = flow_disruptions + incident_disruptions
        
        if not all_disruptions:
            print("⚠️  No disruptions fetched from HERE API")
            return 0, {'flow_count': 0, 'incident_count': 0}
        
        print(f"📊 Processed {len(flow_disruptions)} flow + {len(incident_disruptions)} incident disruptions")
        
        # Load base edges
        try:
            base_edges_df = pd.read_csv(base_edges_csv)
            print(f"✅ Loaded {len(base_edges_df)} base edges from {base_edges_csv}")
        except Exception as e:
            print(f"❌ Failed to load base edges: {e}")
            return 0, {'error': str(e)}
        
        # Convert to .gr format
        edges_count = self.convert_to_gr_format(all_disruptions, base_edges_df, output_file)
        
        metadata = {
            'flow_count': len(flow_disruptions),
            'incident_count': len(incident_disruptions),
            'total_disruptions': len(all_disruptions),
            'edges_affected': edges_count,
            'timestamp': datetime.now().isoformat()
        }
        
        print("="*70 + "\n")
        
        return edges_count, metadata


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
