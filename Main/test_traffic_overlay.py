#!/usr/bin/env python3
"""
Test script to verify the traffic overlay loading fix.
Tests the /get_traffic_with_geometry endpoint.
"""

import sys
import os
sys.path.insert(0, '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main')

import requests
import json
import time

BASE_URL = 'http://localhost:5000'

def test_traffic_overlay():
    """Test the traffic overlay endpoint"""
    print("\n🧪 Testing Traffic Overlay Fix")
    print("=" * 60)
    
    try:
        print("\n1️⃣  Testing /get_traffic_with_geometry endpoint...")
        response = requests.get(f'{BASE_URL}/get_traffic_with_geometry', timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Endpoint returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        
        if not data.get('success'):
            print(f"❌ Endpoint returned success=false")
            print(f"Error: {data.get('error')}")
            return False
        
        segments = data.get('segments', [])
        total_segments = data.get('total_segments', 0)
        
        print(f"✅ Endpoint returned successfully")
        print(f"   📊 Total traffic segments: {total_segments}")
        print(f"   📊 Segments in response: {len(segments)}")
        
        if total_segments == 0:
            print(f"⚠️  WARNING: No traffic segments found!")
            print(f"   This means flow_*.csv files are not being loaded.")
            return False
        
        # Show sample segment
        if segments:
            sample = segments[0]
            print(f"\n   Sample traffic segment:")
            print(f"   - Type: {sample.get('type')}")
            print(f"   - Severity: {sample.get('severity')}")
            print(f"   - Road: {sample.get('road_name')}")
            print(f"   - Speed: {sample.get('speed_kph')} kph")
            print(f"   - Geometry points: {len(sample.get('geometry', []))}")
        
        # Analyze by severity
        severity_counts = {}
        for seg in segments:
            severity = seg.get('severity', 'Unknown')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        print(f"\n   Segments by severity:")
        for severity, count in sorted(severity_counts.items()):
            print(f"   - {severity}: {count}")
        
        print(f"\n✅ Traffic overlay is working correctly!")
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Flask server at {BASE_URL}")
        print(f"   Make sure Flask is running: python flask_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_traffic_overlay()
    sys.exit(0 if success else 1)
