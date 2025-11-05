#!/usr/bin/env python3
"""
Unified Data Generator - Hash-Based Traffic Matching
=====================================================

Simplified version using pre-matched edges from matched_edges.csv
No runtime geospatial matching - just hash lookup!

Usage:
    python unified_data_generator.py --mode flow
    python unified_data_generator.py --mode both --continuous --interval 60
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Add Main directory to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))

from config import Config
from realtime_traffic_service import RealtimeTrafficService

# Load environment
load_dotenv()


def check_and_generate_graph():
    """Check if OSM graph files exist, generate if needed"""
    required_files = [
        Config.EDGES_CSV,
        Config.NODES_CSV,
        Config.PROCESSED_DATA_DIR / "quezon_city.graph"
    ]
    
    missing_files = [f for f in required_files if not f.exists()]
    
    if missing_files:
        print("\n" + "="*70)
        print("⚠️  OSM GRAPH FILES MISSING")
        print("="*70)
        print("\nMissing files:")
        for f in missing_files:
            print(f"  ❌ {f}")
        print()
        
        response = input("Would you like to download and generate the OSM graph now? (Y/n): ").strip().lower()
        
        if response in ['', 'y', 'yes']:
            print("\n🚀 Starting OSM graph generation...")
            print("This will download OpenStreetMap data for Quezon City.")
            print("This may take 5-10 minutes depending on your internet connection.\n")
            
            try:
                # Run osm_graph_generator.py
                generator_script = SCRIPT_DIR / "osm_graph_generator.py"
                
                if not generator_script.exists():
                    print(f"❌ Error: {generator_script} not found!")
                    return False
                
                # Use conda python if available
                if (SCRIPT_DIR / ".conda" / "bin" / "python").exists():
                    python_cmd = str(SCRIPT_DIR / ".conda" / "bin" / "python")
                else:
                    python_cmd = sys.executable
                
                result = subprocess.run(
                    [python_cmd, str(generator_script)],
                    cwd=str(SCRIPT_DIR),
                    check=True
                )
                
                if result.returncode == 0:
                    print("\n✅ Graph generation completed successfully!")
                    return True
                else:
                    print(f"\n❌ Graph generation failed with code {result.returncode}")
                    return False
                    
            except subprocess.CalledProcessError as e:
                print(f"\n❌ Error generating graph: {e}")
                return False
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print("\n❌ Cannot proceed without OSM graph files.")
            print("\nTo generate manually, run:")
            print("  python osm_graph_generator.py")
            return False
    
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Unified traffic data generator with hash-based matching'
    )
    parser.add_argument(
        '--mode', 
        choices=['flow', 'incidents', 'both'], 
        default='flow',
        help='Traffic data mode'
    )
    parser.add_argument(
        '--continuous', 
        action='store_true',
        help='Run continuously with periodic updates'
    )
    parser.add_argument(
        '--interval', 
        type=int, 
        default=60,
        help='Update interval in seconds (for continuous mode)'
    )
    
    args = parser.parse_args()
    
    # First, check if OSM graph exists
    print("🔍 Checking for required OSM graph files...")
    if not check_and_generate_graph():
        print("\n❌ Exiting: OSM graph files are required")
        return 1
    
    print("\n" + "="*70)
    print("Unified Data Generator V2 - Hash-Based Traffic Matching")
    print("="*70)
    print(f"Mode: {args.mode}")
    print(f"Continuous: {args.continuous}")
    if args.continuous:
        print(f"Interval: {args.interval}s")
    print("="*70 + "\n")
    
    # Initialize service
    try:
        service = RealtimeTrafficService()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Make sure HERE_API_KEY is set in your .env file")
        return 1
    
    # Run
    if args.continuous:
        service.run_continuous(mode=args.mode, interval=args.interval)
    else:
        metadata = service.fetch_and_save(mode=args.mode)
        
        print(f"\n✅ Done!")
        print(f"   CSV: {metadata.get('csv_file', 'N/A')}")
        print(f"   GR: {metadata.get('gr_file', 'N/A')}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
