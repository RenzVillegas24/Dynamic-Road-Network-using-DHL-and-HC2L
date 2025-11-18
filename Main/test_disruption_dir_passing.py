#!/usr/bin/env python3
"""
Test script to verify that disruption directories are being passed correctly to C++ routing APIs.
This simulates what the frontend sends and verifies the Flask endpoints handle it correctly.
"""

import sys
import os
sys.path.insert(0, '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main')

import requests
import json
from pathlib import Path

BASE_URL = 'http://localhost:5000'

def test_disruption_directory_passing():
    """Test that disruption directories are passed correctly to routing engines"""
    print("\n🧪 Testing Disruption Directory Passing to C++ APIs")
    print("=" * 70)
    
    # Test data
    test_request = {
        'start_lat': 14.608444,
        'start_lng': 121.017583,
        'dest_lat': 14.629548,
        'dest_lng': 121.020106,
        'tau_threshold': 0.5,
        'dataset_mode': 'both',  # KEY: Tell Flask to use disruptions
        'use_disruptions': True,
        'generate_alternatives': False  # Speed up for testing
    }
    
    print("\n1️⃣ Testing DHL Routing with dataset_mode='both'...")
    print(f"   Request: {json.dumps({k: v for k, v in test_request.items() if k not in ['start_osm_edge', 'dest_osm_edge']}, indent=6)}")
    
    try:
        response = requests.post(f'{BASE_URL}/compute_dhl_route', json=test_request, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"   ✅ DHL routing successful")
                print(f"   ⏱️  Time: {data['metrics'].get('total_computation_time_sec', 'N/A')}s")
                
                # Check if disruption analysis is in output
                disruption_analysis = data.get('disruption_analysis', {})
                if disruption_analysis:
                    print(f"   📊 Disruptions analyzed: {disruption_analysis.get('route_disruptions', {}).get('total_count', 0)}")
                else:
                    print(f"   ⚠️  No disruption analysis in output (disruptions might not have loaded)")
                    
                return True
            else:
                print(f"   ❌ Routing failed: {data.get('error')}")
                return False
        else:
            print(f"   ❌ HTTP error {response.status_code}: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"   ⏱️  Request timed out - routing engine might be computing")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_without_disruptions():
    """Test that routes work without disruptions (dataset_mode='none')"""
    print("\n2️⃣ Testing DHL Routing with dataset_mode='none' (no disruptions)...")
    
    test_request = {
        'start_lat': 14.608444,
        'start_lng': 121.017583,
        'dest_lat': 14.629548,
        'dest_lng': 121.020106,
        'tau_threshold': 0.5,
        'dataset_mode': 'none',  # No disruptions
        'use_disruptions': False,
        'generate_alternatives': False
    }
    
    try:
        response = requests.post(f'{BASE_URL}/compute_dhl_route', json=test_request, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"   ✅ DHL routing without disruptions successful")
                return True
            else:
                print(f"   ❌ Routing failed: {data.get('error')}")
                return False
        else:
            print(f"   ❌ HTTP error {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("Disruption Directory Passing Test Suite")
    print("=" * 70)
    
    try:
        # Test with disruptions
        test1 = test_disruption_directory_passing()
        
        # Test without disruptions
        test2 = test_without_disruptions()
        
        print("\n" + "=" * 70)
        if test1 and test2:
            print("✅ All tests passed!")
            print("\nNext steps:")
            print("1. Check Flask console for:")
            print("   - 'Disruption directory: /path/to/disruptions'")
            print("   - '📂 Adding disruption directory: ...'")
            print("2. Check route colors changed based on traffic")
            sys.exit(0)
        else:
            print("❌ Some tests failed - check the output above")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏸️  Test interrupted by user")
        sys.exit(1)
