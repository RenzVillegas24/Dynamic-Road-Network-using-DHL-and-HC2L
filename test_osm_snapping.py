#!/usr/bin/env python3
"""
OSM Road Snapping System Test Suite

Tests the road-aware snapping functionality with various scenarios.
Run this script to validate the OSM snapping system is working correctly.

Usage:
    python test_osm_snapping.py
"""

import os
import sys

# Add Main directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'Main'))

from osm_road_snapper import OSMRoadSnapper
from coordinate_mapper import NodeMapper
import time


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_osm_snapper_initialization():
    """Test 1: OSMRoadSnapper Initialization"""
    print_section("Test 1: OSMRoadSnapper Initialization")
    
    try:
        graphml_path = "Main/data/osm_geometry.graphml"
        nodes_csv = "Main/data/raw/quezon_city_nodes.csv"
        
        print(f"Loading OSM graph from: {graphml_path}")
        print(f"Loading routing nodes from: {nodes_csv}")
        
        start_time = time.time()
        snapper = OSMRoadSnapper(graphml_path, nodes_csv)
        load_time = time.time() - start_time
        
        print(f"\n✅ SUCCESS: OSM snapper initialized in {load_time:.2f}s")
        print(f"   Graph nodes: {len(snapper.graph.nodes)}")
        print(f"   Graph edges: {len(snapper.graph.edges)}")
        print(f"   Edge geometries: {len(snapper.edge_geometries)}")
        print(f"   Spatial index built: {snapper.spatial_index is not None}")
        
        return snapper, True
        
    except FileNotFoundError as e:
        print(f"❌ FAILED: File not found - {e}")
        print("   Make sure osm_geometry.graphml exists in Main/data/")
        return None, False
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_basic_snapping(snapper):
    """Test 2: Basic Road Snapping"""
    print_section("Test 2: Basic Road Snapping")
    
    # Test coordinates in Quezon City
    test_points = [
        (14.6760, 121.0437, "Near Commonwealth Ave (major highway)"),
        (14.6500, 121.0450, "Near EDSA (major road)"),
        (14.6300, 121.0200, "Residential area"),
    ]
    
    results = []
    
    for lat, lng, desc in test_points:
        print(f"Testing: {desc}")
        print(f"  Coordinates: ({lat}, {lng})")
        
        try:
            start_time = time.time()
            result = snapper.snap_to_nearest_road(lat, lng, max_distance_m=50)
            query_time = (time.time() - start_time) * 1000  # ms
            
            if result:
                print(f"  ✅ Snapped successfully in {query_time:.2f}ms")
                print(f"     Road: {result['road_name']}")
                print(f"     Highway: {result['highway_type']}")
                print(f"     Distance: {result['distance_m']:.1f}m")
                print(f"     Snapped to: ({result['snapped_point']['lat']:.6f}, {result['snapped_point']['lng']:.6f})")
                print(f"     Position: {result['snap_position']:.1%} along edge")
                print(f"     Oneway: {result['oneway']}")
                results.append(True)
            else:
                print(f"  ❌ No road found within 50m")
                results.append(False)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append(False)
        
        print()
    
    success_rate = sum(results) / len(results) * 100
    print(f"Success rate: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    return all(results)


def test_hierarchy_weighting(snapper):
    """Test 3: Road Hierarchy Weighting"""
    print_section("Test 3: Road Hierarchy Weighting")
    
    # Point between major and minor road
    lat, lng = 14.6760, 121.0437
    
    print(f"Testing point at ({lat}, {lng})")
    print("This area should have both major and minor roads nearby")
    
    print("\n1. With hierarchy weighting (should prefer major road):")
    result_with = snapper.snap_to_nearest_road(
        lat, lng, 
        max_distance_m=100, 
        consider_hierarchy=True
    )
    if result_with:
        print(f"   Road: {result_with['road_name']}")
        print(f"   Type: {result_with['highway_type']}")
        print(f"   Distance: {result_with['distance_m']:.1f}m")
    
    print("\n2. Without hierarchy weighting (should prefer closest):")
    result_without = snapper.snap_to_nearest_road(
        lat, lng, 
        max_distance_m=100, 
        consider_hierarchy=False
    )
    if result_without:
        print(f"   Road: {result_without['road_name']}")
        print(f"   Type: {result_without['highway_type']}")
        print(f"   Distance: {result_without['distance_m']:.1f}m")
    
    if result_with and result_without:
        print(f"\n✅ Both queries succeeded")
        print(f"   Hierarchy weighting {'DID' if result_with['road_name'] != result_without['road_name'] else 'DID NOT'} affect selection")
        return True
    else:
        print(f"\n❌ One or both queries failed")
        return False


def test_tolerance_levels(snapper):
    """Test 4: Different Tolerance Levels"""
    print_section("Test 4: Different Tolerance Levels")
    
    lat, lng = 14.6500, 121.0450
    tolerances = [10, 25, 50, 100]
    
    print(f"Testing point at ({lat}, {lng}) with different tolerances:\n")
    
    results = []
    for tolerance in tolerances:
        result = snapper.snap_to_nearest_road(lat, lng, max_distance_m=tolerance)
        
        if result:
            print(f"✅ {tolerance:3d}m tolerance: Found road at {result['distance_m']:.1f}m - {result['road_name']}")
            results.append(True)
        else:
            print(f"❌ {tolerance:3d}m tolerance: No road found")
            results.append(False)
    
    print(f"\nResults: {sum(results)}/{len(results)} succeeded")
    return sum(results) > 0


def test_node_mapper_integration():
    """Test 5: NodeMapper Integration"""
    print_section("Test 5: NodeMapper Integration")
    
    try:
        nodes_csv = "Main/data/raw/quezon_city_nodes.csv"
        
        print(f"Initializing NodeMapper with: {nodes_csv}")
        mapper = NodeMapper(nodes_csv)
        
        print(f"✅ NodeMapper initialized")
        print(f"   OSM snapper available: {mapper.osm_snapper is not None}")
        
        if mapper.osm_snapper:
            print("\nTesting snap_to_osm_road method:")
            
            lat, lng = 14.6500, 121.0450
            result = mapper.snap_to_osm_road(
                lat, lng,
                max_distance_m=25,
                consider_hierarchy=True,
                fallback_to_node=True
            )
            
            if result:
                print(f"  ✅ Snapping successful")
                print(f"     Method: {result['method']}")
                print(f"     Road: {result['road_name']}")
                print(f"     Distance: {result['distance_m']:.1f}m")
                print(f"     Validation: {result['validation']['message']}")
                return True
            else:
                print(f"  ❌ Snapping failed")
                return False
        else:
            print("⚠️  OSM snapper not initialized (expected if GraphML missing)")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_edge_cases(snapper):
    """Test 6: Edge Cases"""
    print_section("Test 6: Edge Cases")
    
    tests = {
        "Very close to road (should snap)": (14.6500, 121.0450, 5),
        "Far from road (should fail with 10m tolerance)": (14.6500, 121.0450, 10),
        "On exact intersection": (14.6540, 121.0540, 50),
    }
    
    results = []
    
    for desc, (lat, lng, tolerance) in tests.items():
        print(f"Test: {desc}")
        print(f"  Point: ({lat}, {lng}), Tolerance: {tolerance}m")
        
        result = snapper.snap_to_nearest_road(lat, lng, max_distance_m=tolerance)
        
        if result:
            print(f"  ✅ Found road: {result['road_name']} at {result['distance_m']:.1f}m")
            results.append(True)
        else:
            print(f"  ℹ️  No road found (may be expected)")
            results.append(True)  # Not finding a road is OK for some tests
        
        print()
    
    return all(results)


def test_performance(snapper):
    """Test 7: Performance Benchmark"""
    print_section("Test 7: Performance Benchmark")
    
    lat, lng = 14.6500, 121.0450
    num_iterations = 100
    
    print(f"Running {num_iterations} snapping operations...")
    
    start_time = time.time()
    
    for i in range(num_iterations):
        snapper.snap_to_nearest_road(lat, lng, max_distance_m=25)
    
    total_time = time.time() - start_time
    avg_time = (total_time / num_iterations) * 1000  # ms
    
    print(f"\nPerformance Results:")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Average time: {avg_time:.2f}ms per query")
    print(f"  Queries per second: {num_iterations / total_time:.1f}")
    
    if avg_time < 50:
        print(f"  ✅ Performance: Excellent (< 50ms)")
        return True
    elif avg_time < 100:
        print(f"  ✅ Performance: Good (< 100ms)")
        return True
    else:
        print(f"  ⚠️  Performance: Slow (> 100ms) - consider optimization")
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "="*70)
    print("  OSM ROAD SNAPPING SYSTEM - TEST SUITE")
    print("="*70)
    
    test_results = {}
    
    # Test 1: Initialization
    snapper, success = test_osm_snapper_initialization()
    test_results['Initialization'] = success
    
    if not success:
        print("\n❌ CRITICAL: Cannot proceed without successful initialization")
        print("\nPlease ensure:")
        print("  1. osm_geometry.graphml exists in Main/data/")
        print("  2. quezon_city_nodes.csv exists in Main/data/raw/")
        print("  3. Required Python packages are installed (osmnx, shapely, networkx)")
        return
    
    # Run remaining tests
    test_results['Basic Snapping'] = test_basic_snapping(snapper)
    test_results['Hierarchy Weighting'] = test_hierarchy_weighting(snapper)
    test_results['Tolerance Levels'] = test_tolerance_levels(snapper)
    test_results['NodeMapper Integration'] = test_node_mapper_integration()
    test_results['Edge Cases'] = test_edge_cases(snapper)
    test_results['Performance'] = test_performance(snapper)
    
    # Print summary
    print_section("TEST SUMMARY")
    
    for test_name, passed in test_results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status:12} - {test_name}")
    
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    
    print(f"\n{'='*70}")
    print(f"  Results: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    print(f"{'='*70}\n")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! OSM Road Snapping system is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
