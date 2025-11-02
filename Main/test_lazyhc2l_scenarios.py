#!/usr/bin/env python3
"""
LazyHC2L Test Scenarios
Tests the implementation with 5 different disruption scenarios and logs metrics
"""

import os
import sys
import csv
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Add Main directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import config
try:
    from config import Config
except ImportError as e:
    print(f"❌ Could not import config.py: {e}")
    print(f"   Current directory: {Path.cwd()}")
    print(f"   Script directory: {Path(__file__).parent}")
    sys.exit(1)

# Configure paths using Config
BASE_DIR = Path(__file__).parent
BUILD_DIR = BASE_DIR / "build"
HC2L_API = BUILD_DIR / "hc2l" / "hc2l_routing_api"
DHL_API = BUILD_DIR / "dhl" / "dhl_routing_api"
DATA_DIR = Config.PROCESSED_DATA_DIR
RAW_DATA_DIR = Config.RAW_DATA_DIR
RESULTS_DIR = BASE_DIR / "test_results"

# Ensure results directory exists
RESULTS_DIR.mkdir(exist_ok=True)

# Test scenarios configuration
SCENARIOS = {
    "light_congestion": {
        "name": "Light Congestion",
        "description": "jam_factor=0.3, Impact=0.15",
        "disruption_content": """c Light congestion scenario - E. Rodriguez Sr. Avenue area
p sp 20000 40000
1 11068 34
2 8424 37
""",
        "expected_hc2l_strategy": "lazy_mark",
        "expected_impact_range": (0.1, 0.2),
        "tau_threshold": 0.5
    },
    "medium_jam": {
        "name": "Medium Jam",
        "description": "jam_factor=0.6, Impact=0.36",
        "disruption_content": """c Medium traffic jam scenario - Quezon Avenue area
p sp 20000 40000
1 2 29
2 3 41
3 4 38
""",
        "expected_hc2l_strategy": "lazy_mark",
        "expected_impact_range": (0.3, 0.4),
        "tau_threshold": 0.5
    },
    "heavy_closure": {
        "name": "Heavy Closure",
        "description": "closure_factor=1.0, Impact=0.8",
        "disruption_content": """c Road closure scenario (high weight = closure) - Mabuhay Rotonda
p sp 20000 40000
1 2 999999
2 3 999999
""",
        "expected_hc2l_strategy": "immediate_update",
        "expected_impact_range": (0.7, 1.0),
        "tau_threshold": 0.5
    },
    "mixed_accident": {
        "name": "Mixed Accident",
        "description": "jam_factor=0.7 + severity=2",
        "disruption_content": """c Accident scenario with heavy impact - Multiple roads
p sp 20000 40000
1 11068 40
2 8424 43
1 2 50
""",
        "expected_hc2l_strategy": "immediate_update",
        "expected_impact_range": (0.5, 0.7),
        "tau_threshold": 0.5
    },
    "multi_segment": {
        "name": "Multi-Segment Disruption",
        "description": "Multiple edges disrupted - Chain effect",
        "disruption_content": """c Multiple segment disruption - Sequential edges
p sp 20000 40000
1 2 30
2 3 32
3 4 35
1 11068 28
2 8424 31
""",
        "expected_hc2l_strategy": "lazy_mark",
        "expected_impact_range": (0.2, 0.4),
        "tau_threshold": 0.5
    }
}

# Sample routing parameters (using actual Quezon City data)
# These are realistic coordinates and edges from the graph
TEST_ROUTE = {
    "start_pin_lat": 14.617651,
    "start_pin_lng": 121.00184,
    "start_snap_lat": 14.617651,
    "start_snap_lng": 121.00184,
    "start_edge_source": 1,
    "start_edge_target": 2,
    "start_edge_oneway": 1,
    "dest_pin_lat": 14.61797,
    "dest_pin_lng": 121.001701,
    "dest_snap_lat": 14.61797,
    "dest_snap_lng": 121.001701,
    "dest_edge_source": 2,
    "dest_edge_target": 3,
    "dest_edge_oneway": 1
}

def create_disruption_file(scenario_name, content):
    """Create a disruption .gr file for testing"""
    disruption_file = DATA_DIR / f"test_disruption_{scenario_name}.gr"
    with open(disruption_file, 'w') as f:
        f.write(content)
    return disruption_file

def run_hc2l_test(scenario_name, disruption_file, tau_threshold):
    """Run HC2L routing API with disruption"""
    # Use RAW_DATA_DIR for CSV files, PROCESSED for index files
    nodes_csv = RAW_DATA_DIR / "quezon_city_nodes.csv"
    edges_csv = RAW_DATA_DIR / "quezon_city_edges.csv"
    index_file = DATA_DIR / "quezon_city.hc2l.index"
    
    # Check if files exist
    if not nodes_csv.exists():
        print(f"❌ Missing nodes CSV: {nodes_csv}")
        return None
    if not edges_csv.exists():
        print(f"❌ Missing edges CSV: {edges_csv}")
        return None
    if not index_file.exists():
        print(f"❌ Missing HC2L index: {index_file}")
        return None
    if not HC2L_API.exists():
        print(f"❌ Missing HC2L API executable: {HC2L_API}")
        return None
    
    cmd = [
        str(HC2L_API),
        str(TEST_ROUTE["start_pin_lat"]),
        str(TEST_ROUTE["start_pin_lng"]),
        str(TEST_ROUTE["start_snap_lat"]),
        str(TEST_ROUTE["start_snap_lng"]),
        str(TEST_ROUTE["start_edge_source"]),
        str(TEST_ROUTE["start_edge_target"]),
        str(TEST_ROUTE["start_edge_oneway"]),
        str(TEST_ROUTE["dest_pin_lat"]),
        str(TEST_ROUTE["dest_pin_lng"]),
        str(TEST_ROUTE["dest_snap_lat"]),
        str(TEST_ROUTE["dest_snap_lng"]),
        str(TEST_ROUTE["dest_edge_source"]),
        str(TEST_ROUTE["dest_edge_target"]),
        str(TEST_ROUTE["dest_edge_oneway"]),
        str(nodes_csv),
        str(edges_csv),
        str(index_file),
        str(disruption_file),
        str(tau_threshold)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as e:
                print(f"❌ HC2L JSON parse error: {e}")
                print(f"   Output: {result.stdout[:200]}")
                return None
        else:
            print(f"❌ HC2L error (exit code {result.returncode}): {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print(f"❌ HC2L timeout (>30s)")
        return None
    except Exception as e:
        print(f"❌ HC2L exception: {e}")
        return None

def run_dhl_test(scenario_name, disruption_file, tau_threshold):
    """Run DHL routing API with disruption"""
    # Use RAW_DATA_DIR for CSV files, PROCESSED for index files
    nodes_csv = RAW_DATA_DIR / "quezon_city_nodes.csv"
    edges_csv = RAW_DATA_DIR / "quezon_city_edges.csv"
    index_file = DATA_DIR / "quezon_city.dhl.index"
    
    # Check if files exist
    if not nodes_csv.exists():
        print(f"❌ Missing nodes CSV: {nodes_csv}")
        return None
    if not edges_csv.exists():
        print(f"❌ Missing edges CSV: {edges_csv}")
        return None
    if not index_file.exists():
        print(f"❌ Missing DHL index: {index_file}")
        return None
    if not DHL_API.exists():
        print(f"❌ Missing DHL API executable: {DHL_API}")
        return None
    
    cmd = [
        str(DHL_API),
        str(TEST_ROUTE["start_pin_lat"]),
        str(TEST_ROUTE["start_pin_lng"]),
        str(TEST_ROUTE["start_snap_lat"]),
        str(TEST_ROUTE["start_snap_lng"]),
        str(TEST_ROUTE["start_edge_source"]),
        str(TEST_ROUTE["start_edge_target"]),
        str(TEST_ROUTE["start_edge_oneway"]),
        str(TEST_ROUTE["dest_pin_lat"]),
        str(TEST_ROUTE["dest_pin_lng"]),
        str(TEST_ROUTE["dest_snap_lat"]),
        str(TEST_ROUTE["dest_snap_lng"]),
        str(TEST_ROUTE["dest_edge_source"]),
        str(TEST_ROUTE["dest_edge_target"]),
        str(TEST_ROUTE["dest_edge_oneway"]),
        str(nodes_csv),
        str(edges_csv),
        str(index_file),
        str(disruption_file),
        str(tau_threshold)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as e:
                print(f"❌ DHL JSON parse error: {e}")
                print(f"   Output: {result.stdout[:200]}")
                return None
        else:
            print(f"❌ DHL error (exit code {result.returncode}): {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print(f"❌ DHL timeout (>30s)")
        return None
    except Exception as e:
        print(f"❌ DHL exception: {e}")
        return None

def extract_metrics(response, algorithm):
    """Extract metrics from API response"""
    if not response or not response.get('success'):
        return None
    
    metrics = {}
    metrics['algorithm'] = algorithm
    
    # Common metrics
    response_metrics = response.get('metrics', {})
    metrics['query_time_ms'] = response_metrics.get('query_time_ms', 0)
    metrics['path_length'] = response_metrics.get('path_length', 0)
    
    # Algorithm-specific metrics
    if algorithm == 'LazyHC2L':
        lazy = response.get('lazy_hc2l', {})
        metrics['impact_score'] = lazy.get('disruption_impact_score', 0)
        metrics['update_strategy'] = lazy.get('update_strategy', 'unknown')
        metrics['dirty_nodes_marked'] = lazy.get('dirty_nodes_marked', 0)
        metrics['nodes_repaired'] = lazy.get('nodes_repaired', 0)
        metrics['lazy_repair_time_ms'] = lazy.get('lazy_repair_time_ms', 0)
        metrics['cache_hit'] = lazy.get('cache_hit', False)
    else:  # DHL
        dhl = response.get('dhl_update_info', {})
        metrics['impact_score'] = dhl.get('disruption_impact_score', 0)
        metrics['update_strategy'] = dhl.get('update_strategy', 'unknown')
        metrics['nodes_updated'] = dhl.get('nodes_updated', 0)
    
    return metrics

def run_all_scenarios():
    """Run all test scenarios and collect metrics"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"lazyhc2l_test_results_{timestamp}.csv"
    
    print("=" * 80)
    print("🧪 LazyHC2L Test Scenarios")
    print("=" * 80)
    
    # Verify prerequisites
    print("\n📋 Checking prerequisites...")
    prerequisites_ok = True
    
    # Check executables
    if not HC2L_API.exists():
        print(f"❌ HC2L API not found: {HC2L_API}")
        prerequisites_ok = False
    else:
        print(f"✅ HC2L API: {HC2L_API}")
    
    if not DHL_API.exists():
        print(f"❌ DHL API not found: {DHL_API}")
        prerequisites_ok = False
    else:
        print(f"✅ DHL API: {DHL_API}")
    
    # Check data files
    nodes_csv = RAW_DATA_DIR / "quezon_city_nodes.csv"
    edges_csv = RAW_DATA_DIR / "quezon_city_edges.csv"
    hc2l_index = DATA_DIR / "quezon_city.hc2l.index"
    dhl_index = DATA_DIR / "quezon_city.dhl.index"
    
    for file_path, name in [
        (nodes_csv, "Nodes CSV"),
        (edges_csv, "Edges CSV"),
        (hc2l_index, "HC2L Index"),
        (dhl_index, "DHL Index")
    ]:
        if not file_path.exists():
            print(f"❌ {name} not found: {file_path}")
            prerequisites_ok = False
        else:
            print(f"✅ {name}: {file_path}")
    
    if not prerequisites_ok:
        print("\n❌ Prerequisites check failed. Please build the executables and data files first.")
        print("   Run: ./build_all.sh (or build_all.bat on Windows)")
        return
    
    print("\n✅ All prerequisites satisfied\n")
    
    all_results = []
    
    for scenario_id, scenario in SCENARIOS.items():
        print(f"\n🔬 Running Scenario: {scenario['name']}")
        print(f"   Description: {scenario['description']}")
        print(f"   Tau threshold: {scenario['tau_threshold']}")
        
        # Create disruption file
        disruption_file = create_disruption_file(scenario_id, scenario['disruption_content'])
        print(f"   Disruption file: {disruption_file}")
        
        # Run LazyHC2L (HC2L with lazy updates)
        print("   🔹 Running LazyHC2L...")
        hc2l_response = run_hc2l_test(scenario_id, disruption_file, scenario['tau_threshold'])
        hc2l_metrics = extract_metrics(hc2l_response, 'LazyHC2L')
        
        # Run DHL (baseline)
        print("   🔹 Running DHL...")
        dhl_response = run_dhl_test(scenario_id, disruption_file, scenario['tau_threshold'])
        dhl_metrics = extract_metrics(dhl_response, 'DHL')
        
        # Store results
        if hc2l_metrics:
            hc2l_metrics['scenario'] = scenario['name']
            hc2l_metrics['tau_threshold'] = scenario['tau_threshold']
            all_results.append(hc2l_metrics)
            print(f"   ✅ LazyHC2L: {hc2l_metrics['update_strategy']} (Impact={hc2l_metrics['impact_score']:.3f})")
        
        if dhl_metrics:
            dhl_metrics['scenario'] = scenario['name']
            dhl_metrics['tau_threshold'] = scenario['tau_threshold']
            all_results.append(dhl_metrics)
            print(f"   ✅ DHL: {dhl_metrics['update_strategy']} (Impact={dhl_metrics['impact_score']:.3f})")
    
    # Write results to CSV
    if all_results:
        fieldnames = ['scenario', 'algorithm', 'impact_score', 'tau_threshold', 'update_strategy',
                     'dirty_nodes_marked', 'nodes_updated', 'nodes_repaired', 'lazy_repair_time_ms',
                     'query_time_ms', 'path_length', 'cache_hit']
        
        with open(results_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\n✅ Results saved to: {results_file}")
    
    print("\n" + "=" * 80)
    print("🎉 All scenarios completed!")
    print("=" * 80)

if __name__ == "__main__":
    run_all_scenarios()
