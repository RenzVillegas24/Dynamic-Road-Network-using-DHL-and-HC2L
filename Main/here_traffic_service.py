"""
HERE Traffic API Integration Service - Hash-Based Matching
===========================================================

Fetches real-time traffic data and uses pre-matched edges via hash lookup.
Replaces the geospatial matching approach with simple hash-based lookups.
"""

import os
import requests
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
from datetime import datetime

from config import Config
from traffic_hash_matcher import TrafficHashMatcher

# Load environment variables
load_dotenv()


class HERETrafficService:
    """Service for fetching and processing HERE traffic data with hash-based matching"""
    
    def __init__(self, matched_edges_csv: Path = None):
        """
        Initialize traffic service
        
        Args:
            matched_edges_csv: Path to matched_edges.csv (default: Main/here_osm/matched_edges.csv)
        """
        self.api_key = os.getenv('HERE_API_KEY', '')
        self.bbox = "121.01,14.59,121.14,14.76"  # Quezon City bounds
        self.traffic_mode = 'flow'  # Options: 'flow', 'incidents', 'both'
        
        if not self.api_key:
            raise ValueError("HERE_API_KEY not found in environment variables")
        
        # Initialize hash-based matcher
        if matched_edges_csv is None:
            matched_edges_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
        
        self.matcher = TrafficHashMatcher(matched_edges_csv)
        
        print(f"✅ HERETrafficService initialized")
        print(f"   Mode: {self.traffic_mode}")
    
    def set_traffic_mode(self, mode: str):
        """
        Set the traffic data mode
        
        Args:
            mode: 'flow', 'incidents', or 'both'
        """
        if mode not in ['flow', 'incidents', 'both']:
            raise ValueError(f"Invalid traffic mode: {mode}")
        self.traffic_mode = mode
        print(f"🚦 Traffic mode set to: {mode.upper()}")
    
    def fetch_traffic_flow(self) -> List[Dict]:
        """Fetch real-time traffic flow data from HERE API"""
        flow_url = (
            f"https://data.traffic.hereapi.com/v7/flow"
            f"?in=bbox:{self.bbox}"
            f"&locationReferencing=shape"
            f"&apiKey={self.api_key}"
        )
        
        try:
            print("📡 Fetching HERE Traffic Flow data...")
            response = requests.get(flow_url, timeout=30)
            response.raise_for_status()
            flow_json = response.json()
            
            results = flow_json.get('results', [])
            print(f"   ✅ Received {len(results)} flow segments")
            return results
            
        except requests.RequestException as e:
            print(f"   ❌ Error fetching flow data: {e}")
            return []
    
    def fetch_traffic_incidents(self) -> List[Dict]:
        """Fetch real-time traffic incidents from HERE API"""
        incidents_url = (
            f"https://data.traffic.hereapi.com/v7/incidents"
            f"?in=bbox:{self.bbox}"
            f"&locationReferencing=shape"
            f"&apiKey={self.api_key}"
        )
        
        try:
            print("📡 Fetching HERE Traffic Incidents data...")
            response = requests.get(incidents_url, timeout=30)
            response.raise_for_status()
            incidents_json = response.json()
            
            results = incidents_json.get('results', [])
            print(f"   ✅ Received {len(results)} incidents")
            return results
            
        except requests.RequestException as e:
            print(f"   ❌ Error fetching incidents: {e}")
            return []
    
    def fetch_and_match_traffic(self, mode: str = None) -> pd.DataFrame:
        """
        Fetch traffic data and match to edges via hash lookup
        
        Args:
            mode: Override traffic mode ('flow', 'incidents', 'both')
            
        Returns:
            DataFrame with matched traffic edges
        """
        if mode is None:
            mode = self.traffic_mode
        
        print(f"\n{'='*70}")
        print(f"Fetching and Matching Traffic Data - Mode: {mode.upper()}")
        print(f"{'='*70}\n")
        
        all_edges = []
        
        # Fetch and match flow data
        if mode in ['flow', 'both']:
            flow_results = self.fetch_traffic_flow()
            if flow_results:
                print(f"\n🔍 Matching {len(flow_results)} flow segments...")
                flow_edges = self.matcher.batch_match_flow_data(flow_results)
                all_edges.extend(flow_edges)
        
        # Fetch and match incident data
        if mode in ['incidents', 'both']:
            incident_results = self.fetch_traffic_incidents()
            if incident_results:
                print(f"\n🔍 Matching {len(incident_results)} incidents...")
                incident_edges = self.matcher.batch_match_incident_data(incident_results)
                all_edges.extend(incident_edges)
        
        # Convert to DataFrame
        if all_edges:
            df = pd.DataFrame([edge.to_dict() for edge in all_edges])
            print(f"\n✅ Total matched edges: {len(df)}")
            return df
        else:
            print(f"\n⚠️  No traffic data matched")
            return pd.DataFrame()
    
    def save_traffic_csv(self, df: pd.DataFrame, output_file: Path = None) -> Path:
        """
        Save traffic data to CSV
        
        Args:
            df: DataFrame with traffic edges
            output_file: Output path (default: auto-generated with timestamp)
            
        Returns:
            Path to saved file
        """
        if df.empty:
            print("⚠️  No data to save")
            return None
        
        # Generate filename if not provided
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            filename = f"traffic_{timestamp}_{self.traffic_mode}.csv"
            output_file = Config.DISRUPTIONS_DIR / filename
        
        # Save
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False)
        
        print(f"💾 Saved: {output_file}")
        
        # Create symlink
        symlink = Config.DISRUPTIONS_DIR / f"current_traffic_{self.traffic_mode}.csv"
        if symlink.exists():
            symlink.unlink()
        symlink.symlink_to(output_file.name)
        print(f"🔗 Symlink: {symlink} -> {output_file.name}")
        
        return output_file
    
    def save_traffic_gr(self, df: pd.DataFrame, output_file: Path = None) -> Path:
        """
        Save traffic data to .gr format for C++ routing APIs
        
        Args:
            df: DataFrame with traffic edges
            output_file: Output path (default: auto-generated with timestamp)
            
        Returns:
            Path to saved file
        """
        if df.empty:
            print("⚠️  No data to save")
            return None
        
        # Generate filename if not provided
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            filename = f"traffic_{timestamp}_{self.traffic_mode}.gr"
            output_file = Config.DISRUPTIONS_DIR / filename
        
        # Get unique nodes
        nodes = set(df['source'].tolist() + df['target'].tolist())
        num_nodes = max(nodes) if nodes else 0
        num_edges = len(df)
        
        # Write .gr file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            # Header
            f.write(f"c Traffic data from HERE API (Hash-based matching)\n")
            f.write(f"c Mode: {self.traffic_mode}\n")
            f.write(f"c Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"c Edges: {num_edges}\n")
            f.write(f"p sp {num_nodes} {num_edges}\n")
            
            # Edges with weight based on jam factor
            for _, row in df.iterrows():
                source = int(row['source'])
                target = int(row['target'])
                
                # Support both old and new column names
                jam_factor = float(row.get('flow_jam_factor', row.get('jamFactor', 0.0)))
                speed_kph = float(row.get('flow_speed_kph', row.get('speed_kph', 0.0)))
                free_flow_kph = float(row.get('flow_free_flow_kph', row.get('freeFlow_kph', 50.0)))
                is_closed = bool(row.get('incident_road_closed', row.get('isClosed', False)))
                
                # Weight formula
                if is_closed:
                    weight = 999999
                elif free_flow_kph > 0:
                    weight = int(1000 * (1.0 + jam_factor / 10.0))
                else:
                    weight = int(1000 * (1.0 + jam_factor / 10.0))
                
                f.write(f"a {source} {target} {weight}\n")
        
        print(f"💾 Saved: {output_file}")
        
        # Create symlink
        symlink = Config.DISRUPTIONS_DIR / f"current_traffic_{self.traffic_mode}.gr"
        if symlink.exists():
            symlink.unlink()
        symlink.symlink_to(output_file.name)
        print(f"🔗 Symlink: {symlink} -> {output_file.name}")
        
        return output_file
    
    def fetch_and_save_traffic(self, mode: str = None) -> Tuple[int, Dict]:
        """
        Fetch traffic data, match to edges, and save files
        
        Args:
            mode: Override traffic mode
            
        Returns:
            (number of edges, metadata dict)
        """
        # Fetch and match
        df = self.fetch_and_match_traffic(mode)
        
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'mode': mode or self.traffic_mode,
            'edges_count': len(df)
        }
        
        if not df.empty:
            # Save files
            csv_path = self.save_traffic_csv(df)
            gr_path = self.save_traffic_gr(df)
            
            metadata['csv_file'] = str(csv_path) if csv_path else None
            metadata['gr_file'] = str(gr_path) if gr_path else None
        
        return len(df), metadata


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
    service.set_traffic_mode('flow')
    
    edges_count, metadata = service.fetch_and_save_traffic()
    
    print(f"\n📊 Results:")
    print(f"   Edges affected: {edges_count}")
    print(f"   CSV: {metadata.get('csv_file', 'N/A')}")
    print(f"   GR: {metadata.get('gr_file', 'N/A')}")
