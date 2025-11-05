#!/usr/bin/env python3
"""
Quick integration test for hash-based traffic matching
"""

import sys
from pathlib import Path

# Add Main to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))

from config import Config
from realtime_traffic_service import RealtimeTrafficService

print("\n" + "="*70)
print("Integration Test - Hash-Based Traffic Matching")
print("="*70 + "\n")

# Test 1: Check matched_edges.csv
print("1️⃣  Checking matched_edges.csv...")
matched_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
if matched_csv.exists():
    import pandas as pd
    df = pd.read_csv(matched_csv)
    print(f"   ✅ Found {len(df)} matched edges")
    print(f"   ✅ Unique traffic hashes: {df['traffic_hash'].nunique()}")
else:
    print(f"   ❌ matched_edges.csv not found!")
    sys.exit(1)

# Test 2: Initialize service
print("\n2️⃣  Initializing RealtimeTrafficService...")
try:
    service = RealtimeTrafficService()
    print(f"   ✅ Service initialized")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 3: Check disruption file function
print("\n3️⃣  Testing disruption file lookup...")
from flask_server import get_dynamic_disruption_file

for mode in ['flow', 'both', 'incidents']:
    file_path = get_dynamic_disruption_file('hc2l', mode)
    if file_path:
        print(f"   ✅ {mode}: {Path(file_path).name}")
    else:
        print(f"   ⚠️  {mode}: No file found (expected for incidents)")

# Test 4: Check .gr file format
print("\n4️⃣  Checking .gr file format...")
gr_file = Config.DISRUPTIONS_DIR / "current_traffic_flow.gr"
if gr_file.exists():
    with open(gr_file, 'r') as f:
        lines = f.readlines()[:10]
    print(f"   ✅ File exists: {len(lines)} header lines")
    for line in lines[:5]:
        print(f"      {line.strip()}")
else:
    print(f"   ⚠️  No .gr file found yet (run ./generate_traffic.fish flow)")

# Test 5: Check CSV file format
print("\n5️⃣  Checking CSV file format...")
csv_file = Config.DISRUPTIONS_DIR / "current_traffic_flow.csv"
if csv_file.exists():
    df = pd.read_csv(csv_file)
    print(f"   ✅ CSV has {len(df)} edges")
    print(f"   ✅ Columns: {list(df.columns)}")
    print(f"\n   Sample row:")
    print(df.head(1).to_string(index=False))
else:
    print(f"   ⚠️  No CSV file found yet (run ./generate_traffic.fish flow)")

print("\n" + "="*70)
print("✅ Integration test complete!")
print("="*70 + "\n")
