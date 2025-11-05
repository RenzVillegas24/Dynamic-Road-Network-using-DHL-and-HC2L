#!/usr/bin/env python3
"""
Test script to verify the matched/non-matched traffic toggle feature
Tests the new /get_raw_here_traffic endpoint
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_raw_traffic_endpoint():
    """Test the raw HERE traffic endpoint"""
    print("🧪 Testing /get_raw_here_traffic endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/get_raw_here_traffic", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                print(f"✅ Endpoint working!")
                print(f"   Total flow segments: {data.get('total_flow', 0)}")
                print(f"   Total incidents: {data.get('total_incidents', 0)}")
                
                # Show sample data
                if data.get('data', {}).get('flow_segments'):
                    sample_flow = data['data']['flow_segments'][0]
                    print(f"\n📊 Sample flow segment:")
                    print(f"   Coordinates: {len(sample_flow['coordinates'])} points")
                    print(f"   Jam Factor: {sample_flow['jam_factor']:.1f}")
                    print(f"   Speed: {sample_flow['speed_kph']:.1f} km/h")
                    print(f"   Severity: {sample_flow['severity']}")
                
                if data.get('data', {}).get('incidents'):
                    sample_incident = data['data']['incidents'][0]
                    print(f"\n🚨 Sample incident:")
                    print(f"   Type: {sample_incident['type']}")
                    print(f"   Description: {sample_incident['description']}")
                    print(f"   Severity: {sample_incident['severity']}")
                    print(f"   Coordinates: {len(sample_incident['coordinates'])} points")
                
                return True
            else:
                print(f"❌ Endpoint returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - is Flask server running?")
        print("   Start server with: python flask_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_matched_traffic_endpoint():
    """Test the matched traffic endpoint for comparison"""
    print("\n🧪 Testing /get_active_disruptions endpoint (matched)...")
    
    try:
        response = requests.get(f"{BASE_URL}/get_active_disruptions", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                print(f"✅ Endpoint working!")
                print(f"   Total disruptions: {data.get('total_disruptions', 0)}")
                print(f"   Matched edges: {data.get('matched_edges', 0)}")
                print(f"   Type counts: {data.get('type_counts', {})}")
                
                return True
            else:
                print(f"❌ Endpoint returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Matched/Non-matched Traffic Toggle Feature")
    print("=" * 60)
    
    # Test raw traffic endpoint
    test1 = test_raw_traffic_endpoint()
    
    # Test matched traffic endpoint
    test2 = test_matched_traffic_endpoint()
    
    print("\n" + "=" * 60)
    if test1 and test2:
        print("✅ All tests passed!")
        print("\n📝 Summary:")
        print("   - Raw traffic endpoint works (/get_raw_here_traffic)")
        print("   - Matched traffic endpoint works (/get_active_disruptions)")
        print("   - Toggle can switch between matched and non-matched views")
        print("\n🎯 Next steps:")
        print("   1. Open browser to http://localhost:5000")
        print("   2. Enable 'Show Traffic Overlay'")
        print("   3. Toggle 'For Current Route Only' to see nested toggle")
        print("   4. Toggle 'Show Matched Edges' ON/OFF to switch views:")
        print("      - ON: Shows traffic mapped to OSM road edges")
        print("      - OFF: Shows raw HERE API traffic data")
    else:
        print("❌ Some tests failed")
        print("   Make sure Flask server is running and HERE API is configured")
    print("=" * 60)


if __name__ == "__main__":
    main()
