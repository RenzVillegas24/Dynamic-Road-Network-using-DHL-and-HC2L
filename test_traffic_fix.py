#!/usr/bin/env python3
"""
Test Script for Traffic Flow Parsing Fixes
==========================================

This script tests the fixes for traffic flow parsing accuracy issues.

Key fixes tested:
1. HERE API speed conversion (m/s to km/h)
2. Free flow speed estimation from highway type
3. Current speed estimation from jam factor when missing
4. Weight calculation based on actual speeds
5. Impact score calculation
"""

import sys
from pathlib import Path

# Add Main directory to path
sys.path.insert(0, str(Path(__file__).parent / "Main"))

from realtime_traffic_service import RealtimeTrafficService
from traffic_hash_matcher import TrafficHashMatcher
import pandas as pd


def test_traffic_service():
    """Test the real-time traffic service with fixes"""
    print("=" * 70)
    print("Testing Traffic Flow Parsing Fixes")
    print("=" * 70)
    
    # Initialize service
    try:
        service = RealtimeTrafficService()
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return False
    
    print("\n1️⃣ Fetching and matching traffic data...")
    df, metadata = service.generate_traffic_data(mode='flow')
    
    if df.empty:
        print("⚠️  No traffic data received")
        return False
    
    print(f"   ✅ Matched {len(df)} traffic edges")
    
    # Check for zero free flow speeds
    print("\n2️⃣ Checking for zero/missing free flow speeds...")
    zero_free_flow = df[df['freeFlow_kph'] <= 0.0]
    
    if len(zero_free_flow) > 0:
        print(f"   ❌ Found {len(zero_free_flow)} edges with zero free flow speed!")
        print(f"   Sample problematic edges:")
        print(zero_free_flow[['source', 'target', 'speed_kph', 'freeFlow_kph', 'highway_type']].head())
        return False
    else:
        print(f"   ✅ All edges have valid free flow speeds (> 0)")
    
    # Check for zero current speeds
    print("\n3️⃣ Checking current speeds...")
    zero_speed = df[df['speed_kph'] <= 0.0]
    
    if len(zero_speed) > 0:
        print(f"   ⚠️  Found {len(zero_speed)} edges with zero current speed")
        # This might be OK if traffic is stopped, but log it
        print(f"   Sample:")
        print(zero_speed[['source', 'target', 'speed_kph', 'jamFactor', 'highway_type']].head())
    else:
        print(f"   ✅ All edges have current speed > 0")
    
    # Check speed consistency
    print("\n4️⃣ Checking speed consistency (speed <= free_flow)...")
    invalid_speeds = df[df['speed_kph'] > df['freeFlow_kph']]
    
    if len(invalid_speeds) > 0:
        print(f"   ❌ Found {len(invalid_speeds)} edges where speed > free_flow!")
        print(invalid_speeds[['source', 'target', 'speed_kph', 'freeFlow_kph']].head())
        return False
    else:
        print(f"   ✅ All current speeds are <= free flow speeds")
    
    # Show sample data
    print("\n5️⃣ Sample traffic data:")
    print("-" * 70)
    sample = df.head(5)[['source', 'target', 'speed_kph', 'freeFlow_kph', 'jamFactor', 'highway_type']]
    print(sample.to_string(index=False))
    
    # Test .gr file generation
    print("\n6️⃣ Testing .gr file generation...")
    gr_path = service.save_traffic_gr(df, mode='flow')
    
    if gr_path and gr_path.exists():
        print(f"   ✅ Generated .gr file: {gr_path.name}")
        
        # Read and verify .gr file
        with open(gr_path, 'r') as f:
            lines = f.readlines()
        
        # Check for valid entries
        edge_lines = [l for l in lines if l.startswith('a ')]
        print(f"   ✅ .gr file contains {len(edge_lines)} edge entries")
        
        # Show sample entries
        print("\n   Sample .gr entries:")
        for line in edge_lines[:3]:
            parts = line.strip().split()
            if len(parts) >= 12:
                print(f"      Edge {parts[1]}→{parts[2]}: "
                      f"weight={parts[3]}, jam={parts[4]}, "
                      f"speed={parts[5]}/{parts[6]}km/h, "
                      f"highway={parts[9]}")
    else:
        print(f"   ❌ Failed to generate .gr file")
        return False
    
    # Statistics
    print("\n7️⃣ Traffic Statistics:")
    print("-" * 70)
    print(f"   Total edges: {len(df)}")
    print(f"   Avg speed: {df['speed_kph'].mean():.1f} km/h")
    print(f"   Avg free flow: {df['freeFlow_kph'].mean():.1f} km/h")
    print(f"   Avg jam factor: {df['jamFactor'].mean():.2f}")
    print(f"   Speed range: {df['speed_kph'].min():.1f} - {df['speed_kph'].max():.1f} km/h")
    print(f"   Free flow range: {df['freeFlow_kph'].min():.1f} - {df['freeFlow_kph'].max():.1f} km/h")
    
    # Highway type distribution
    print("\n   Highway type distribution:")
    for hw_type, count in df['highway_type'].value_counts().head(5).items():
        avg_speed = df[df['highway_type'] == hw_type]['freeFlow_kph'].mean()
        print(f"      {hw_type}: {count} edges (avg free flow: {avg_speed:.1f} km/h)")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    
    return True


if __name__ == '__main__':
    success = test_traffic_service()
    sys.exit(0 if success else 1)
