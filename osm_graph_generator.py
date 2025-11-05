#!/usr/bin/env python3
"""
OSM Graph Generator for Quezon City
====================================

Downloads OpenStreetMap data for Quezon City and generates:
1. quezon_city_edges.csv - Edge data with geometry
2. quezon_city_nodes.csv - Node coordinates
3. quezon_city.graph - Graph format for C++ indexing
4. node_id_mapping.csv - OSM ID to sequential ID mapping

Usage:
    python osm_graph_generator.py
"""

import sys
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Add Main directory to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))

try:
    import osmnx as ox
    import networkx as nx
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import LineString, Point
    from shapely import wkt
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("\nPlease install required packages:")
    print("  conda install -c conda-forge osmnx geopandas shapely")
    print("  or")
    print("  pip install osmnx geopandas shapely")
    sys.exit(1)


# Location configuration
PLACE_NAME = "Quezon City, Philippines"


def download_osm_graph():
    """Download road network graph from OpenStreetMap"""
    print("\n" + "="*70)
    print("Downloading OSM Graph for Quezon City")
    print("="*70 + "\n")
    
    print("📍 Location: Quezon City, Philippines")
    print()
    
    # Configure OSMnx
    ox.settings.use_cache = True
    ox.settings.log_console = True
    
    try:
        print("🌐 Downloading from OpenStreetMap (this may take a few minutes)...")
        
        # Download graph for driving network using place name
        # This is more reliable than bbox for well-defined locations
        G = ox.graph_from_place(
            "Quezon City, Philippines",
            network_type='drive',
            simplify=True,
            retain_all=False
        )
        
        print(f"✅ Downloaded OSM graph")
        print(f"   Nodes: {len(G.nodes())}")
        print(f"   Edges: {len(G.edges())}")
        
        return G
        
    except Exception as e:
        print(f"❌ Error downloading OSM data: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_sequential_node_mapping(G):
    """Create mapping from OSM node IDs to sequential IDs (1-based)"""
    print("\n📋 Creating node ID mapping...")
    
    osm_nodes = list(G.nodes())
    osm_nodes.sort()  # Sort for consistency
    
    # Create bidirectional mapping (1-based indexing)
    osm_to_seq = {osm_id: seq_id for seq_id, osm_id in enumerate(osm_nodes, start=1)}
    seq_to_osm = {seq_id: osm_id for osm_id, seq_id in osm_to_seq.items()}
    
    print(f"   ✅ Created mapping for {len(osm_to_seq)} nodes")
    print(f"   Sequential IDs: 1 to {len(osm_to_seq)}")
    
    return osm_to_seq, seq_to_osm


def generate_edges_csv(G, osm_to_seq, output_path: Path):
    """Generate edges CSV with geometry"""
    print(f"\n📄 Generating edges CSV: {output_path}")
    
    edges_data = []
    
    for u, v, key, data in G.edges(keys=True, data=True):
        # Get sequential IDs
        source = osm_to_seq[u]
        target = osm_to_seq[v]
        
        # Get edge attributes
        highway = data.get('highway', 'unknown')
        if isinstance(highway, list):
            highway = highway[0]
        
        road_name = data.get('name', '')
        if isinstance(road_name, list):
            road_name = ', '.join(road_name)
        
        length = data.get('length', 0.0)
        oneway = data.get('oneway', False)
        
        # Get geometry
        if 'geometry' in data:
            geom = data['geometry']
        else:
            # Create straight line from node coordinates
            u_node = G.nodes[u]
            v_node = G.nodes[v]
            geom = LineString([
                (u_node['x'], u_node['y']),
                (v_node['x'], v_node['y'])
            ])
        
        # Convert geometry to list of [lat, lon] pairs
        coords = [[coord[1], coord[0]] for coord in geom.coords]  # [lon, lat] -> [lat, lon]
        
        edges_data.append({
            'source': source,
            'target': target,
            'osm_source': u,
            'osm_target': v,
            'length': round(length, 2),
            'highway_type': highway,
            'road_name': road_name,
            'oneway': oneway,
            'geometry': json.dumps(coords)  # Store as JSON string
        })
    
    # Write to CSV
    df = pd.DataFrame(edges_data)
    df.to_csv(output_path, index=False)
    
    print(f"   ✅ Wrote {len(df)} edges")
    print(f"   Columns: {', '.join(df.columns)}")
    
    return df


def generate_nodes_csv(G, osm_to_seq, output_path: Path):
    """Generate nodes CSV with coordinates"""
    print(f"\n📄 Generating nodes CSV: {output_path}")
    
    nodes_data = []
    
    for osm_id, node_data in G.nodes(data=True):
        seq_id = osm_to_seq[osm_id]
        
        nodes_data.append({
            'node_id': seq_id,
            'osm_id': osm_id,
            'latitude': node_data['y'],
            'longitude': node_data['x']
        })
    
    # Write to CSV
    df = pd.DataFrame(nodes_data)
    df = df.sort_values('node_id')  # Sort by sequential ID
    df.to_csv(output_path, index=False)
    
    print(f"   ✅ Wrote {len(df)} nodes")
    print(f"   Columns: {', '.join(df.columns)}")
    
    return df


def generate_node_mapping_csv(osm_to_seq, output_path: Path):
    """Generate node ID mapping CSV"""
    print(f"\n📄 Generating node mapping CSV: {output_path}")
    
    mapping_data = []
    for osm_id, seq_id in sorted(osm_to_seq.items(), key=lambda x: x[1]):
        mapping_data.append({
            'sequential_id': seq_id,
            'osm_id': osm_id
        })
    
    df = pd.DataFrame(mapping_data)
    df.to_csv(output_path, index=False)
    
    print(f"   ✅ Wrote {len(df)} mappings")
    
    return df


def generate_graph_file(edges_df, output_path: Path):
    """
    Generate .graph file in DIMACS format for C++ indexing
    
    Format:
        c <comment>
        p sp <num_nodes> <num_edges>
        a <source> <target> <weight>
    """
    print(f"\n📄 Generating graph file: {output_path}")
    
    # Get unique nodes
    all_nodes = set(edges_df['source'].tolist() + edges_df['target'].tolist())
    num_nodes = max(all_nodes) if all_nodes else 0
    num_edges = len(edges_df)
    
    print(f"   Nodes: {num_nodes}")
    print(f"   Edges: {num_edges}")
    
    with open(output_path, 'w') as f:
        # Header
        f.write(f"c Quezon City road network\n")
        f.write(f"c Generated from OpenStreetMap\n")
        f.write(f"p sp {num_nodes} {num_edges}\n")
        
        # Edges (weight = length in meters, converted to integer)
        for _, row in edges_df.iterrows():
            source = int(row['source'])
            target = int(row['target'])
            weight = int(row['length'])  # Convert to integer meters
            
            f.write(f"a {source} {target} {weight}\n")
    
    print(f"   ✅ Graph file created")
    
    return output_path


def save_graphml(G, output_path: Path):
    """Save graph in GraphML format (for compatibility)"""
    print(f"\n📄 Saving GraphML: {output_path}")
    
    try:
        ox.save_graphml(G, filepath=output_path)
        print(f"   ✅ GraphML saved")
        return True
    except Exception as e:
        print(f"   ⚠️  Could not save GraphML: {e}")
        return False


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("OSM GRAPH GENERATOR FOR QUEZON CITY")
    print("="*70)
    
    # Setup directories
    raw_data_dir = MAIN_DIR / "data" / "raw"
    processed_data_dir = MAIN_DIR / "data" / "processed"
    data_dir = MAIN_DIR / "data"
    
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    processed_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Output files
    edges_csv = raw_data_dir / "quezon_city_edges.csv"
    nodes_csv = raw_data_dir / "quezon_city_nodes.csv"
    mapping_csv = raw_data_dir / "node_id_mapping.csv"
    graph_file = processed_data_dir / "quezon_city.graph"
    graphml_file = data_dir / "osm_geometry.graphml"
    
    # Step 1: Download OSM graph
    G = download_osm_graph()
    if G is None:
        print("\n❌ Failed to download OSM data")
        return 1
    
    # Step 2: Create node mapping
    osm_to_seq, seq_to_osm = create_sequential_node_mapping(G)
    
    # Step 3: Generate CSV files
    edges_df = generate_edges_csv(G, osm_to_seq, edges_csv)
    nodes_df = generate_nodes_csv(G, osm_to_seq, nodes_csv)
    mapping_df = generate_node_mapping_csv(osm_to_seq, mapping_csv)
    
    # Step 4: Generate graph file
    generate_graph_file(edges_df, graph_file)
    
    # Step 5: Save GraphML (optional)
    save_graphml(G, graphml_file)
    
    # Summary
    print("\n" + "="*70)
    print("✅ GRAPH GENERATION COMPLETE")
    print("="*70)
    print(f"\nGenerated files:")
    print(f"  📄 {edges_csv}")
    print(f"  📄 {nodes_csv}")
    print(f"  📄 {mapping_csv}")
    print(f"  📄 {graph_file}")
    print(f"  📄 {graphml_file}")
    print()
    print(f"Graph statistics:")
    print(f"  � Location: {PLACE_NAME}")
    print(f"  �🔢 Nodes: {len(G.nodes())}")
    print(f"  🔗 Edges: {len(G.edges())}")
    print()
    print("Next steps:")
    print("  1. Run traffic data generation: python unified_data_generator.py --mode both")
    print("  2. Build indexes: ./setup.sh --indexes")
    print("  3. Start server: ./setup.sh --server")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
