"""
Real-Time Flow Data Service
============================

Fetches HERE API traffic flow data periodically and generates CSV files
with hash-based matching using pre-matched edges.

Output Format (CSV):
    id_hash,source_lat,source_lon,target_lat,target_lon,source,target,
    flow_speed_kph,flow_free_flow_kph,flow_jam_factor,flow_confidence,
    flow_traversability,highway_type,road_name

Files are timestamped as 'flow_YYYYMMDDTHHMMSS.csv'
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


class FlowService:
    """Service for fetching and processing real-time HERE traffic flow data"""
    
    def __init__(self, matched_edges_csv: Path = None):
        """
        Initialize real-time flow service
        
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
        
        # Output directory for flow data
        self.output_dir = Config.FLOW_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ FlowService initialized")
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
    
    def generate_flow_data(self) -> Tuple[pd.DataFrame, Dict]:
        """
        Fetch and match flow data
        
        Returns:
            (DataFrame with flow edges, metadata dict)
        """
        print(f"\n{'='*70}")
        print(f"Generating Flow Data")
        print(f"{'='*70}\n")
        
        flow_edges = []
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'flow_count': 0,
            'total_edges': 0
        }
        
        # Fetch and match flow data
        flow_results = self.fetch_flow_data()
        metadata['flow_count'] = len(flow_results)
        
        if flow_results:
            print(f"\n🔍 Matching flow data...")
            flow_edges = self.matcher.batch_match_flow_data(flow_results)
        
        # Convert to DataFrame
        if flow_edges:
            df = pd.DataFrame([edge.to_dict() for edge in flow_edges])
            
            # Keep only flow-related columns
            flow_columns = [
                'id_hash', 'source_lat', 'source_lon', 'target_lat', 'target_lon',
                'source', 'target', 'flow_speed_kph', 'flow_free_flow_kph',
                'flow_jam_factor', 'flow_confidence', 'flow_traversability',
                'highway_type', 'road_name'
            ]
            
            # Filter to only include columns that exist
            existing_columns = [col for col in flow_columns if col in df.columns]
            df = df[existing_columns]
            
            metadata['total_edges'] = len(df)
            
            print(f"\n✅ Generated {len(df)} flow edges")
            return df, metadata
        else:
            print(f"\n⚠️  No flow data matched")
            return pd.DataFrame(), metadata
    
    def save_flow_csv(self, df: pd.DataFrame) -> Path:
        """
        Save flow data to timestamped CSV file
        Auto-cleanup old files to maintain max 10 files
        
        Args:
            df: DataFrame with flow edges
            
        Returns:
            Path to saved CSV file
        """
        if df.empty:
            print(f"⚠️  No flow data to save")
            return None
        
        # Cleanup old files first (keep max 10)
        self._cleanup_old_files(max_files=10)
        
        # Generate timestamp filename with centiseconds for uniqueness
        # Format: YYYYMMDDTHHMMSSCC (CC = centiseconds, 00-99)
        now = datetime.now()
        centiseconds = str(now.microsecond // 10000).zfill(2)
        timestamp = now.strftime("%Y%m%dT%H%M%S") + centiseconds
        filename = f"flow_{timestamp}.csv"
        filepath = self.output_dir / filename
        
        # Save CSV
        df.to_csv(filepath, index=False)
        print(f"   💾 Saved Flow CSV: {filepath}")
        
        return filepath
    
    def _cleanup_old_files(self, max_files: int = 10):
        """
        Remove old flow files, keeping only the latest N files
        
        Args:
            max_files: Maximum number of files to keep
        """
        flow_files = sorted(self.output_dir.glob("flow_*.csv"), reverse=True)
        
        # Keep only the latest max_files
        if len(flow_files) >= max_files:
            files_to_remove = flow_files[max_files-1:]  # Keep max_files-1 to make room for new file
            for old_file in files_to_remove:
                try:
                    old_file.unlink()
                    print(f"   🗑️  Removed old flow file: {old_file.name}")
                except Exception as e:
                    print(f"   ⚠️  Failed to remove {old_file.name}: {e}")
    
    def fetch_and_save(self) -> Dict:
        """
        Fetch flow data and save to CSV file
        
        Returns:
            Metadata dictionary
        """
        # Generate flow data
        df, metadata = self.generate_flow_data()
        
        if not df.empty:
            # Save CSV
            csv_path = self.save_flow_csv(df)
            metadata['csv_file'] = str(csv_path) if csv_path else None
            
            print(f"\n📊 Summary:")
            print(f"   Flow segments: {metadata['flow_count']}")
            print(f"   Total edges: {metadata['total_edges']}")
        
        return metadata
    
    def run_continuous(self, interval: int = 60):
        """
        Run continuous flow data fetching
        
        Args:
            interval: Update interval in seconds
        """
        print(f"\n{'='*70}")
        print(f"Starting Continuous Flow Service")
        print(f"{'='*70}")
        print(f"Update interval: {interval}s")
        print(f"Press Ctrl+C to stop\n")
        
        try:
            while True:
                # Fetch and save
                self.fetch_and_save()
                
                # Wait for next update
                print(f"\n⏱️  Waiting {interval}s for next update...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n\n🛑 Flow Service stopped by user")


def main():
    """Main entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time HERE flow data service')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously with periodic updates')
    parser.add_argument('--interval', type=int, default=60,
                       help='Update interval in seconds (for continuous mode)')
    
    args = parser.parse_args()
    
    # Initialize service
    service = FlowService()
    
    # Run
    if args.continuous:
        service.run_continuous(interval=args.interval)
    else:
        service.fetch_and_save()


if __name__ == '__main__':
    main()
