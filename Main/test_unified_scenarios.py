#!/usr/bin/env python3
"""
Test script for unified data generator scenarios
Tests HC2L and DHL with scenarios generated from unified_data_generator.py
"""

import subprocess
import json
from pathlib import Path

# Configure paths
BASE_DIR = Path(__file__).parent
MAIN_DIR = BASE_DIR / "Main"
BUILD_DIR = MAIN_DIR / "build"
DATA_DIR = MAIN_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
DISRUPTIONS_DIR = DATA_DIR / "disruptions"

# Test route coordinates (Quezon City landmarks)
TEST_ROUTES = [
    {
        "name": "Araneta to QC Hall",
        "start_lat": 14.6250,
        "start_lon": 121.0500,
        "end_lat": 14.6449,
        "end_lon": 121.0308
    },
    {
        "name": "UP Diliman to Gateway Mall",
        "start_lat": 14.6537,
        "start_lon": 121.0685,
        "end_lat": 14.6183,
        "end_lon": 121.0561
    }
]

def snap_to_nearest_edge(lat, lon, edges_csv):
    """Simple snapping to nearest edge - returns mock snapped coordinates"""
    # For testing, we'll use the same coordinates
    # In production, use osm_road_snapper.py
    return {
        "pin_lat": lat,
        "pin_lon": lon,
        "snap_lat": lat,
        "snap_lon": lon,
        "edge_source": 0,
        "edge_target": 0,
        "oneway": 1
    }

def test_gps_routing(algorithm, scenario_file):
    """Test GPS-based routing with HC2L or DHL"""
    
    print(f"\n{'='*70}")
    print(f"Testing {algorithm.upper()} with {scenario_file.name}")
    print(f"{'='*70}")
    
    # Build API path
    api_binary = BUILD_DIR / algorithm / f"{algorithm}_routing_api"
    
    if not api_binary.exists():
        print(f"❌ {algorithm.upper()} binary not found: {api_binary}")
        print(f"   Run './build_all.fish' to build the algorithms")
        return False
    
    # Test each route
    for route in TEST_ROUTES:
        print(f"\n📍 Testing route: {route['name']}")
        print(f"   Start: ({route['start_lat']}, {route['start_lon']})")
        print(f"   End:   ({route['end_lat']}, {route['end_lon']})")
        
        # Snap coordinates (simplified for testing)
        start = snap_to_nearest_edge(route['start_lat'], route['start_lon'], RAW_DIR / "quezon_city_edges.csv")
        end = snap_to_nearest_edge(route['end_lat'], route['end_lon'], RAW_DIR / "quezon_city_edges.csv")
        
        # Build command
        cmd = [
            str(api_binary),
            str(start['pin_lat']), str(start['pin_lon']),
            str(start['snap_lat']), str(start['snap_lon']),
            str(start['edge_source']), str(start['edge_target']), str(start['oneway']),
            str(end['pin_lat']), str(end['pin_lon']),
            str(end['snap_lat']), str(end['snap_lon']),
            str(end['edge_source']), str(end['edge_target']), str(end['oneway']),
            str(RAW_DIR / "quezon_city_nodes.csv"),
            str(RAW_DIR / "quezon_city_edges.csv"),
            str(PROCESSED_DIR / f"quezon_city.{algorithm}.index"),
            str(scenario_file),
            "0.5"  # tau_threshold
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Parse JSON response
            try:
                response = json.loads(result.stdout)
                
                if response.get('success'):
                    print(f"   ✅ Route found!")
                    print(f"      Distance: {response.get('distance_meters', 0):.2f} meters")
                    print(f"      Duration: {response.get('duration_seconds', 0):.2f} seconds")
                    print(f"      ETA: {response.get('eta_minutes', 0):.2f} minutes")
                    print(f"      Disruptions considered: {response.get('num_disruptions_loaded', 0)}")
                    print(f"      Strategy: {response.get('strategy', 'N/A')}")
                else:
                    print(f"   ⚠️  Error: {response.get('error', 'Unknown error')}")
                    
            except json.JSONDecodeError:
                print(f"   ❌ Invalid JSON response:")
                print(f"      stdout: {result.stdout[:200]}")
                print(f"      stderr: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            print(f"   ❌ Timeout after 30 seconds")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return True

def main():
    print("="*70)
    print("UNIFIED DATA GENERATOR - SCENARIO TESTING")
    print("="*70)
    
    # Find all scenario files
    scenario_files = list(DISRUPTIONS_DIR.glob("scenario_*_synthetic.csv"))
    
    if not scenario_files:
        print("❌ No scenario files found in data/disruptions/")
        print("   Run: python unified_data_generator.py --mode synthetic --scenarios 1")
        return
    
    print(f"\nFound {len(scenario_files)} scenario(s):")
    for sf in scenario_files:
        print(f"   - {sf.name}")
    
    # Check if indexes exist
    hc2l_index = PROCESSED_DIR / "quezon_city.hc2l.index"
    dhl_index = PROCESSED_DIR / "quezon_city.dhl.index"
    
    if not hc2l_index.exists() or not dhl_index.exists():
        print("\n⚠️  Warning: Index files not found")
        print("   Run: ./build_all.fish")
        print("   This will build the indexes needed for routing")
        return
    
    # Test with HC2L
    for scenario in scenario_files:
        test_gps_routing("hc2l", scenario)
    
    # Test with DHL
    for scenario in scenario_files:
        test_gps_routing("dhl", scenario)
    
    print("\n" + "="*70)
    print("✅ TESTING COMPLETE")
    print("="*70)

if __name__ == "__main__":
    main()
