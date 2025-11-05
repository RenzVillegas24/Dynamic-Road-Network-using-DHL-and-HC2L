"""
Real-Time Traffic Data Service
===============================

Fetches HERE API traffic data periodically and generates edge files
using hash-based matching with pre-matched edges.

Output Format (CSV):
    traffic_hash,source_lat,source_lon,target_lat,target_lon,source,target,speed_kph,freeFlow_kph,jamFactor,isClosed

Output Format (.gr):
    c <metadata>
    p sp <num_nodes> <num_edges>
    a <source> <target> <weight>

Files are timestamped and symlinked to 'current_traffic_<mode>.csv/gr'
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from dotenv import load_dotenv

from config import Config
from traffic_hash_matcher import TrafficHashMatcher

# Load environment
load_dotenv()


class RealtimeTrafficService:
    """Service for fetching and processing real-time HERE traffic data"""
    
    def __init__(self, matched_edges_csv: Path = None):
        """
        Initialize real-time traffic service
        
        Args:
            matched_edges_csv: Path to matched_edges.csv (default: Main/here_osm/matched_edges.csv)
        """
        self.api_key = os.getenv('HERE_API_KEY', '')
        if not self.api_key:
            raise ValueError("HERE_API_KEY not found in environment variables")
        
        self.bbox = "121.01,14.59,121.14,14.76"  # Quezon City bounds
        
        # Initialize hash matcher
        if matched_edges_csv is None:
            matched_edges_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
        
        self.matcher = TrafficHashMatcher(matched_edges_csv)
        
        # Output directories
        self.output_dir = Config.DISRUPTIONS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ RealtimeTrafficService initialized")
        print(f"   API Key: {self.api_key[:10]}...")
        print(f"   BBox: {self.bbox}")
        print(f"   Output: {self.output_dir}")
    
    def fetch_flow_data(self) -> List[Dict]:
        """Fetch real-time traffic flow data from HERE API"""
        flow_url = (
            f"https://data.traffic.hereapi.com/v7/flow"
            f"?in=bbox:{self.bbox}"
            f"&locationReferencing=shape"
            f"&apiKey={self.api_key}"
        )
        
        try:
            print(f"🌐 Fetching flow data from HERE API...")
            response = requests.get(flow_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            print(f"   ✅ Received {len(results)} flow segments")
            return results
            
        except requests.RequestException as e:
            print(f"   ❌ Error fetching flow data: {e}")
            return []
    
    def fetch_incidents_data(self) -> List[Dict]:
        """Fetch real-time traffic incidents from HERE API"""
        incidents_url = (
            f"https://data.traffic.hereapi.com/v7/incidents"
            f"?in=bbox:{self.bbox}"
            f"&locationReferencing=shape"
            f"&apiKey={self.api_key}"
        )
        
        try:
            print(f"🌐 Fetching incidents data from HERE API...")
            response = requests.get(incidents_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            print(f"   ✅ Received {len(results)} incidents")
            return results
            
        except requests.RequestException as e:
            print(f"   ❌ Error fetching incidents: {e}")
            return []
    
    def generate_traffic_data(self, mode: str = 'flow') -> Tuple[pd.DataFrame, Dict]:
        """
        Fetch and match traffic data
        
        Args:
            mode: 'flow', 'incidents', or 'both'
            
        Returns:
            (DataFrame with traffic edges, metadata dict)
        """
        print(f"\n{'='*70}")
        print(f"Generating Traffic Data - Mode: {mode.upper()}")
        print(f"{'='*70}\n")
        
        all_edges = []
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'mode': mode,
            'flow_count': 0,
            'incident_count': 0,
            'total_edges': 0
        }
        
        # Fetch and match flow data
        if mode in ['flow', 'both']:
            flow_results = self.fetch_flow_data()
            metadata['flow_count'] = len(flow_results)
            
            if flow_results:
                print(f"\n🔍 Matching flow data...")
                flow_edges = self.matcher.batch_match_flow_data(flow_results)
                all_edges.extend(flow_edges)
        
        # Fetch and match incident data
        if mode in ['incidents', 'both']:
            incident_results = self.fetch_incidents_data()
            metadata['incident_count'] = len(incident_results)
            
            if incident_results:
                print(f"\n🔍 Matching incident data...")
                incident_edges = self.matcher.batch_match_incident_data(incident_results)
                all_edges.extend(incident_edges)
        
        # Convert to DataFrame
        if all_edges:
            df = pd.DataFrame([edge.to_dict() for edge in all_edges])
            metadata['total_edges'] = len(df)
            
            print(f"\n✅ Generated {len(df)} traffic edges")
            return df, metadata
        else:
            print(f"\n⚠️  No traffic data matched")
            return pd.DataFrame(), metadata
    
    def save_traffic_csv(self, df: pd.DataFrame, mode: str) -> Path:
        """
        Save traffic data to timestamped CSV file
        
        Args:
            df: DataFrame with traffic edges
            mode: Traffic mode for filename
            
        Returns:
            Path to saved CSV file
        """
        if df.empty:
            print(f"⚠️  No data to save")
            return None
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"traffic_{timestamp}_{mode}.csv"
        filepath = self.output_dir / filename
        
        # Save CSV
        df.to_csv(filepath, index=False)
        print(f"   💾 Saved CSV: {filepath}")
        
        # Create/update symlink to latest
        symlink = self.output_dir / f"current_traffic_{mode}.csv"
        if symlink.exists():
            symlink.unlink()
        symlink.symlink_to(filepath.name)
        print(f"   🔗 Symlink: {symlink} -> {filepath.name}")
        
        return filepath
    
    def save_traffic_gr(self, df: pd.DataFrame, mode: str) -> Path:
        """
        Save traffic data to .gr format for C++ routing APIs
        
        Args:
            df: DataFrame with traffic edges
            mode: Traffic mode for filename
            
        Returns:
            Path to saved .gr file
        """
        if df.empty:
            print(f"⚠️  No data to save")
            return None
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"traffic_{timestamp}_{mode}.gr"
        filepath = self.output_dir / filename
        
        # Get unique nodes
        nodes = set(df['source'].tolist() + df['target'].tolist())
        num_nodes = max(nodes) if nodes else 0
        num_edges = len(df)
        
        # Write .gr file
        with open(filepath, 'w') as f:
            # Header
            f.write(f"c Traffic data from HERE API\n")
            f.write(f"c Mode: {mode}\n")
            f.write(f"c Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"c Edges: {num_edges}\n")
            f.write(f"p sp {num_nodes} {num_edges}\n")
            
            # Edges with weight based on jam factor
            for _, row in df.iterrows():
                source = int(row['source'])
                target = int(row['target'])
                
                # Calculate weight from jam factor and speed
                jam_factor = float(row['jamFactor'])
                speed_kph = float(row['speed_kph'])
                free_flow_kph = float(row['freeFlow_kph'])
                is_closed = bool(row['isClosed'])
                
                # Weight formula: higher jam factor = higher weight
                if is_closed:
                    weight = 999999  # Very high penalty for closed roads
                elif free_flow_kph > 0:
                    # Weight proportional to travel time
                    # Higher jam factor means slower speed, higher weight
                    weight = int(1000 * (1.0 + jam_factor / 10.0))
                else:
                    weight = int(1000 * (1.0 + jam_factor / 10.0))
                
                f.write(f"a {source} {target} {weight}\n")
        
        print(f"   💾 Saved .gr: {filepath}")
        
        # Create/update symlink to latest
        symlink = self.output_dir / f"current_traffic_{mode}.gr"
        if symlink.exists():
            symlink.unlink()
        symlink.symlink_to(filepath.name)
        print(f"   🔗 Symlink: {symlink} -> {filepath.name}")
        
        return filepath
    
    def fetch_and_save(self, mode: str = 'flow') -> Dict:
        """
        Fetch traffic data and save to files
        
        Args:
            mode: 'flow', 'incidents', or 'both'
            
        Returns:
            Metadata dictionary
        """
        # Generate traffic data
        df, metadata = self.generate_traffic_data(mode)
        
        if not df.empty:
            # Save CSV
            csv_path = self.save_traffic_csv(df, mode)
            metadata['csv_file'] = str(csv_path) if csv_path else None
            
            # Save .gr
            gr_path = self.save_traffic_gr(df, mode)
            metadata['gr_file'] = str(gr_path) if gr_path else None
            
            print(f"\n📊 Summary:")
            print(f"   Flow segments: {metadata['flow_count']}")
            print(f"   Incidents: {metadata['incident_count']}")
            print(f"   Total edges: {metadata['total_edges']}")
        
        return metadata
    
    def run_continuous(self, mode: str = 'flow', interval: int = 60):
        """
        Run continuous traffic data fetching
        
        Args:
            mode: 'flow', 'incidents', or 'both'
            interval: Update interval in seconds
        """
        print(f"\n{'='*70}")
        print(f"Starting Continuous Traffic Service")
        print(f"{'='*70}")
        print(f"Mode: {mode}")
        print(f"Update interval: {interval}s")
        print(f"Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Fetch and save
                self.fetch_and_save(mode)
                
                # Wait for next update
                print(f"\n⏱️  Waiting {interval}s for next update...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Service stopped by user")


def main():
    """Main entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time HERE traffic data service')
    parser.add_argument('--mode', choices=['flow', 'incidents', 'both'], 
                       default='flow', help='Traffic data mode')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously with periodic updates')
    parser.add_argument('--interval', type=int, default=60,
                       help='Update interval in seconds (for continuous mode)')
    
    args = parser.parse_args()
    
    # Initialize service
    service = RealtimeTrafficService()
    
    # Run
    if args.continuous:
        service.run_continuous(mode=args.mode, interval=args.interval)
    else:
        service.fetch_and_save(mode=args.mode)


if __name__ == '__main__':
    main()
