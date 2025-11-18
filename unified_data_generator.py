#!/usr/bin/env python3
"""
Unified Data Generator - Separated Flow and Incident Services
==============================================================

Generates separate flow and incident CSV files using pre-matched edges.
Flow data uses hash-based matching (flow_service.py)
Incident data uses spatial matching (incident_service.py)

Usage:
    python unified_data_generator.py --mode flow
    python unified_data_generator.py --mode incidents
    python unified_data_generator.py --mode both
    
Note: --continuous mode removed (use manual refresh in UI)
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
from flow_service import FlowService
from incident_service import IncidentService

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
        description='Unified traffic data generator with separated flow and incident services'
    )
    parser.add_argument(
        '--mode', 
        choices=['flow', 'incidents', 'both'], 
        default='both',
        help='Traffic data mode: flow, incidents, or both (default: both)'
    )
    
    args = parser.parse_args()
    
    # First, check if OSM graph exists
    print("🔍 Checking for required OSM graph files...")
    if not check_and_generate_graph():
        print("\n❌ Exiting: OSM graph files are required")
        return 1
    
    print("\n" + "="*70)
    print("Unified Data Generator - Separated Flow and Incident Services")
    print("="*70)
    print(f"Mode: {args.mode}")
    print(f"Output:")
    print(f"  - Flow data: {Config.FLOW_DIR}")
    print(f"  - Incident data: {Config.INCIDENTS_DIR}")
    print("="*70 + "\n")
    
    try:
        # Generate flow data if requested
        if args.mode in ['flow', 'both']:
            print("📊 Generating flow data...")
            flow_service = FlowService()
            flow_metadata = flow_service.fetch_and_save()
            print(f"✅ Flow data completed")
            print(f"   CSV: {flow_metadata.get('csv_file', 'N/A')}")
            print(f"   Edges: {flow_metadata.get('total_edges', 0)}\n")
        
        # Generate incident data if requested
        if args.mode in ['incidents', 'both']:
            print("🚨 Generating incident data...")
            incident_service = IncidentService()
            incident_metadata = incident_service.fetch_and_save()
            print(f"✅ Incident data completed")
            print(f"   CSV: {incident_metadata.get('csv_file', 'N/A')}")
            print(f"   Matched: {incident_metadata.get('total_matched', 0)}\n")
        
        print(f"✅ Done!")
        print(f"   Use UI refresh button for updates (no auto-refresh)")
        
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Make sure HERE_API_KEY is set in your .env file")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
