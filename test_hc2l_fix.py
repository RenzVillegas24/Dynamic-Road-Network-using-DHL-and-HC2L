#!/usr/bin/env python3
"""
Test HC2L with coordinate loading fix
"""
import subprocess
import json
import sys
sys.path.insert(0, './Main')

# Test coordinates
start_lat, start_lng = 14.6760, 121.0437
dest_lat, dest_lng = 14.6348, 121.0480

# Build args
hc2l_path = "./Main/build/hc2l/hc2l_routing_api"
nodes_csv = "./Main/data/raw/quezon_city_nodes.csv"
edges_csv = "./Main/data/raw/quezon_city_edges.csv"
index_file = "./Main/build/hc2l/index"
disruptions_csv = "./Main/data/disruptions/current_traffic_both.csv"

# Run snapper to get snap edges
from osm_road_snapper import OSMRoadSnapper
from config import Config
snapper = OSMRoadSnapper(Config.EDGES_CSV)

start_snap = snapper.snap_to_nearest_road(start_lat, start_lng)
dest_snap = snapper.snap_to_nearest_road(dest_lat, dest_lng)

print(f"Start snap: {start_snap}")
print(f"Dest snap: {dest_snap}")

if start_snap and dest_snap:
    # Extract edge information from snap results
    start_edge = {
        'source': start_snap['routing_nodes'][0],
        'target': start_snap['routing_nodes'][1],
        'oneway': 1 if start_snap['oneway'] == 'True' else 0
    }
    dest_edge = {
        'source': dest_snap['routing_nodes'][0],
        'target': dest_snap['routing_nodes'][1],
        'oneway': 1 if dest_snap['oneway'] == 'True' else 0
    }
    
    cmd = [
        hc2l_path,
        str(start_lat), str(start_lng),
        str(start_snap['lat']), str(start_snap['lng']),
        str(start_edge['source']), str(start_edge['target']), str(start_edge.get('oneway', 0)),
        str(dest_lat), str(dest_lng),
        str(dest_snap['lat']), str(dest_snap['lng']),
        str(dest_edge['source']), str(dest_edge['target']), str(dest_edge.get('oneway', 0)),
        nodes_csv, edges_csv, index_file, disruptions_csv, "0.5"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    # Parse JSON
    json_start = result.stdout.find('{')
    if json_start >= 0:
        try:
            data = json.loads(result.stdout[json_start:])
            print(f"\n✅ HC2L Response:")
            print(f"  Success: {data.get('success')}")
            print(f"  Distance: {data.get('metrics', {}).get('total_distance_meters')} meters")
            if 'gps_mapping' in data:
                gps = data['gps_mapping']
                print(f"  Start node: {gps.get('start_node')}")
                print(f"    Lat: {gps.get('start_node_lat')}")
                print(f"    Lng: {gps.get('start_node_lng')}")
                print(f"  Dest node: {gps.get('dest_node')}")
                print(f"    Lat: {gps.get('dest_node_lat')}")
                print(f"    Lng: {gps.get('dest_node_lng')}")
                
                # Verify coordinates are reasonable (should be ~14.6x, 121.0x)
                start_lat_val = gps.get('start_node_lat', 0)
                if 14 < start_lat_val < 15 and 120 < gps.get('start_node_lng', 0) < 122:
                    print(f"\n✅ Coordinates are VALID!")
                else:
                    print(f"\n❌ Coordinates are INVALID! (start lat={start_lat_val})")
        except json.JSONDecodeError as e:
            print(f"❌ JSON Parse Error: {e}")
            print(f"First 1000 chars:\n{result.stdout[:1000]}")
