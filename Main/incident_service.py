"""
Real-Time Incident Data Service
================================

Fetches HERE API traffic incidents and generates CSV files
with OSM edge matching for incidents (accidents, closures, hazards).

Output Format (CSV):
    source,target,source_lat,source_lon,target_lat,target_lon,
    incident_id,incident_type,incident_criticality,incident_description,
    incident_road_closed,incident_start_time,incident_end_time,
    highway_type,road_name

Files are timestamped as 'incident_YYYYMMDDTHHMMSS.csv'
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv

from config import Config
from incident_matcher import IncidentMatcher

# Load environment
load_dotenv()


class IncidentService:
    """Service for fetching and processing real-time HERE traffic incidents"""
    
    def __init__(self, edges_csv: Path = None, nodes_csv: Path = None, matched_edges_csv: Path = None):
        """
        Initialize real-time incident service
        
        Args:
            edges_csv: Path to edges CSV file (default: Main/data/raw/quezon_city_edges.csv)
            nodes_csv: Path to nodes CSV file (default: Main/data/raw/quezon_city_nodes.csv)
            matched_edges_csv: Path to matched_edges.csv for hash-based matching (optional)
        """
        self.api_key = os.getenv('HERE_API_KEY', '')
        if not self.api_key:
            raise ValueError("HERE_API_KEY not found in environment variables")
        
        self.bbox = "121.01,14.59,121.14,14.76"  # Quezon City bounds
        
        # Initialize incident matcher with hash-based matching support
        if edges_csv is None:
            edges_csv = Config.EDGES_CSV
        if nodes_csv is None:
            nodes_csv = Config.NODES_CSV
        if matched_edges_csv is None:
            matched_edges_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
            
        self.matcher = IncidentMatcher(edges_csv, nodes_csv, matched_edges_csv)
        
        # Output directory for incident data
        self.output_dir = Config.INCIDENTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✅ IncidentService initialized")
        print(f"   API Key: {self.api_key[:10]}...")
        print(f"   BBox: {self.bbox}")
        print(f"   Output: {self.output_dir}")
    
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
    
    def generate_incident_data(self) -> Tuple[pd.DataFrame, Dict]:
        """
        Fetch and match incident data
        
        Returns:
            (DataFrame with incident edges, metadata dict)
        """
        print(f"\n{'='*70}")
        print(f"Generating Incident Data")
        print(f"{'='*70}\n")
        
        incident_edges = []
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'incident_count': 0,
            'total_edges': 0,
            'total_matched': 0  # Add this for auto_disruption_service
        }
        
        # Fetch and match incident data
        incident_results = self.fetch_incidents_data()
        metadata['incident_count'] = len(incident_results)
        
        if incident_results:
            print(f"\n🔍 Matching incident data to OSM edges...")
            incident_edges = self.matcher.batch_match_incidents(incident_results)
        
        # Convert to DataFrame
        if incident_edges:
            df = pd.DataFrame(incident_edges)
            
            # Keep only incident-related columns
            incident_columns = [
                'source', 'target', 'source_lat', 'source_lon', 'target_lat', 'target_lon',
                'incident_id', 'incident_type', 'incident_criticality',
                'incident_description', 'incident_road_closed',
                'incident_start_time', 'incident_end_time',
                'highway_type', 'road_name'
            ]
            
            # Filter to only include columns that exist
            existing_columns = [col for col in incident_columns if col in df.columns]
            df = df[existing_columns]
            
            metadata['total_edges'] = len(df)
            metadata['total_matched'] = len(df)  # Set total_matched to the number of matched edges
            
            print(f"\n✅ Generated {len(df)} incident edges")
            return df, metadata
        else:
            print(f"\n⚠️  No incident data matched")
            return pd.DataFrame(), metadata
    
    def save_incident_csv(self, df: pd.DataFrame) -> Path:
        """
        Save incident data to timestamped CSV file
        Auto-cleanup old files to maintain max 10 files
        
        Args:
            df: DataFrame with incident edges
            
        Returns:
            Path to saved CSV file
        """
        if df.empty:
            print(f"⚠️  No incident data to save")
            return None
        
        # Cleanup old files first (keep max 10)
        self._cleanup_old_files(max_files=10)
        
        # Generate timestamp filename with centiseconds for uniqueness
        # Format: YYYYMMDDTHHMMSSCC (CC = centiseconds, 00-99)
        now = datetime.now()
        centiseconds = str(now.microsecond // 10000).zfill(2)
        timestamp = now.strftime("%Y%m%dT%H%M%S") + centiseconds
        filename = f"incident_{timestamp}.csv"
        filepath = self.output_dir / filename
        
        # Save CSV
        df.to_csv(filepath, index=False)
        print(f"   💾 Saved Incident CSV: {filepath}")
        
        return filepath
    
    def _cleanup_old_files(self, max_files: int = 10):
        """
        Remove old incident files, keeping only the latest N files
        
        Args:
            max_files: Maximum number of files to keep
        """
        incident_files = sorted(self.output_dir.glob("incident_*.csv"), reverse=True)
        
        # Keep only the latest max_files
        if len(incident_files) >= max_files:
            files_to_remove = incident_files[max_files-1:]  # Keep max_files-1 to make room for new file
            for old_file in files_to_remove:
                try:
                    old_file.unlink()
                    print(f"   🗑️  Removed old incident file: {old_file.name}")
                except Exception as e:
                    print(f"   ⚠️  Failed to remove {old_file.name}: {e}")
    
    def fetch_and_save(self) -> Dict:
        """
        Fetch incident data and save to CSV file
        
        Returns:
            Metadata dictionary
        """
        # Generate incident data
        df, metadata = self.generate_incident_data()
        
        if not df.empty:
            # Save CSV
            csv_path = self.save_incident_csv(df)
            metadata['csv_file'] = str(csv_path) if csv_path else None
            
            print(f"\n📊 Summary:")
            print(f"   Incidents: {metadata['incident_count']}")
            print(f"   Total edges: {metadata['total_edges']}")
        
        return metadata
    
    def run_continuous(self, interval: int = 60):
        """
        Run continuous incident data fetching
        
        Args:
            interval: Update interval in seconds
        """
        print(f"\n{'='*70}")
        print(f"Starting Continuous Incident Service")
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
            print(f"\n\n🛑 Incident Service stopped by user")


def main():
    """Main entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time HERE incident data service')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously with periodic updates')
    parser.add_argument('--interval', type=int, default=60,
                       help='Update interval in seconds (for continuous mode)')
    
    args = parser.parse_args()
    
    # Initialize service
    service = IncidentService()
    
    # Run
    if args.continuous:
        service.run_continuous(interval=args.interval)
    else:
        service.fetch_and_save()


if __name__ == '__main__':
    main()
