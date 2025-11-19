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

from console_formatter import get_logger

# Initialize logger
logger = get_logger("OSMGraphGenerator")

try:
    import osmnx as ox
    import networkx as nx
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import LineString, Point
    from shapely import wkt
except ImportError as e:
    logger.error(f"Missing required package: {e}")
    logger.info("\nPlease install required packages:")
    logger.info("  conda install -c conda-forge osmnx geopandas shapely")
    logger.info("  or")
    logger.info("  pip install osmnx geopandas shapely")
    sys.exit(1)


# Location configuration
PLACE_NAME = "Quezon City, Philippines"


def download_osm_graph():
    """Download road network graph from OpenStreetMap"""
    logger.info("\n" + "="*70)
    logger.info("Downloading OSM Graph for Quezon City")
    logger.info("="*70 + "\n")
    
    logger.location("Location: Quezon City, Philippines")
    logger.info("")
    
    # Configure OSMnx
    ox.settings.use_cache = True
    ox.settings.log_console = True
    
    try:
        logger.download("Downloading from OpenStreetMap (this may take a few minutes)...")
        
        # Download graph for driving network using place name
        # This is more reliable than bbox for well-defined locations
        G = ox.graph_from_place(
            "Quezon City, Philippines",
            network_type='drive',
            simplify=True,
            retain_all=False
        )
        
        logger.success(f"Downloaded OSM graph")
        logger.data(f"   Nodes: {len(G.nodes())}")
        logger.data(f"   Edges: {len(G.edges())}")
        
        return G
        
    except Exception as e:
        logger.error(f"Error downloading OSM data: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_sequential_node_mapping(G):
    """Create mapping from OSM node IDs to sequential IDs (1-based)"""
    logger.processing("Creating node ID mapping...")
    
    osm_nodes = list(G.nodes())
    osm_nodes.sort()  # Sort for consistency
    
    # Create bidirectional mapping (1-based indexing)
    osm_to_seq = {osm_id: seq_id for seq_id, osm_id in enumerate(osm_nodes, start=1)}
    seq_to_osm = {seq_id: osm_id for osm_id, seq_id in osm_to_seq.items()}
    
    logger.success(f"Created mapping for {len(osm_to_seq)} nodes")
    logger.data(f"   Sequential IDs: 1 to {len(osm_to_seq)}")
    
    return osm_to_seq, seq_to_osm


def generate_edges_csv(G, osm_to_seq, output_path: Path):
    """
    Generate edges CSV with geometry
    
    CRITICAL: This CSV is used for TWO purposes:
    1. C++ routing algorithms (use sequential IDs: source, target)
    2. Traffic matching (uses OSM IDs: osm_source, osm_target)
    
    The CSV contains BOTH ID types to support both use cases.
    """
    logger.file_op(f"Generating edges CSV: {output_path}")
    
    edges_data = []
    
    for u, v, key, data in G.edges(keys=True, data=True):
        # Get sequential IDs (for C++ routing - 1-based indexing)
        seq_source = osm_to_seq[u]
        seq_target = osm_to_seq[v]
        
        # Keep OSM IDs (for traffic matching)
        osm_source = u
        osm_target = v
        
        # Get edge attributes
        highway = data.get('highway', 'unknown')
        if isinstance(highway, list):
            highway = highway[0]
        
        road_name = data.get('name', '')
        if isinstance(road_name, list):
            road_name = ', '.join(road_name)
        
        length = data.get('length', 0.0)
        
        # Convert oneway to integer format: 1 (forward), 0 (bidirectional), -1 (reverse)
        # OSMnx returns True for one-way, False for bidirectional
        # For reverse one-way roads, OSMnx already reverses the edge direction
        oneway_raw = data.get('oneway', False)
        if oneway_raw is True or oneway_raw == 'True' or oneway_raw == 1:
            oneway = 1  # One-way forward
        elif oneway_raw is False or oneway_raw == 'False' or oneway_raw == 0:
            oneway = 0  # Bidirectional
        elif oneway_raw == -1 or oneway_raw == '-1':
            oneway = -1  # One-way reverse (rare, as OSMnx usually reverses the edge)
        else:
            oneway = 0  # Default to bidirectional for unknown values
        
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
        
        # Extract source and target coordinates for hash matching
        source_lat = coords[0][0]
        source_lon = coords[0][1]
        target_lat = coords[-1][0]
        target_lon = coords[-1][1]
        
        edges_data.append({
            # Sequential IDs (for C++ routing algorithms - REQUIRED)
            'source': seq_source,
            'target': seq_target,
            
            # OSM IDs (for traffic matching - REQUIRED)
            'osm_source': osm_source,
            'osm_target': osm_target,
            
            # Coordinate endpoints (for traffic matching)
            'source_lat': source_lat,
            'source_lon': source_lon,
            'target_lat': target_lat,
            'target_lon': target_lon,
            
            # Edge attributes
            'length': round(length, 2),
            'highway_type': highway,
            'road_name': road_name,
            'oneway': oneway,
            
            # Full geometry
            'geometry': json.dumps(coords)  # Store as JSON string
        })
    
    # Write to CSV
    df = pd.DataFrame(edges_data)
    df.to_csv(output_path, index=False)
    
    logger.success(f"Wrote {len(df)} edges")
    logger.data(f"   Columns: {', '.join(df.columns)}")
    logger.data(f"   ID Format: source/target = sequential (1-{len(osm_to_seq)})")
    logger.data(f"   ID Format: osm_source/osm_target = OSM IDs (for matching)")
    
    return df


def generate_nodes_csv(G, osm_to_seq, output_path: Path):
    """Generate nodes CSV with coordinates"""
    logger.file_op(f"Generating nodes CSV: {output_path}")
    
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
    
    logger.success(f"Wrote {len(df)} nodes")
    logger.data(f"   Columns: {', '.join(df.columns)}")
    
    return df


def generate_node_mapping_csv(osm_to_seq, output_path: Path):
    """Generate node ID mapping CSV"""
    logger.file_op(f"Generating node mapping CSV: {output_path}")
    
    mapping_data = []
    for osm_id, seq_id in sorted(osm_to_seq.items(), key=lambda x: x[1]):
        mapping_data.append({
            'sequential_id': seq_id,
            'osm_id': osm_id
        })
    
    df = pd.DataFrame(mapping_data)
    df.to_csv(output_path, index=False)
    
    logger.success(f"Wrote {len(df)} mappings")
    
    return df


def generate_graph_file(edges_df, output_path: Path):
    """
    Generate .graph file in DIMACS format for C++ indexing
    
    Format:
        c <comment>
        p sp <num_nodes> <num_edges>
        a <source> <target> <weight>
    """
    logger.file_op(f"Generating graph file: {output_path}")
    
    # Get unique nodes
    all_nodes = set(edges_df['source'].tolist() + edges_df['target'].tolist())
    num_nodes = max(all_nodes) if all_nodes else 0
    num_edges = len(edges_df)
    
    logger.data(f"   Nodes: {num_nodes}")
    logger.data(f"   Edges: {num_edges}")
    
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
    
    logger.success("Graph file created")
    
    return output_path


def save_graphml(G, output_path: Path):
    """Save graph in GraphML format (for compatibility)"""
    logger.file_op(f"Saving GraphML: {output_path}")
    
    try:
        ox.save_graphml(G, filepath=output_path)
        logger.success("GraphML saved")
        return True
    except Exception as e:
        logger.warning(f"Could not save GraphML: {e}")
        return False


def main():
    """Main entry point"""
    logger.info("\n" + "="*70)
    logger.info("OSM GRAPH GENERATOR FOR QUEZON CITY")
    logger.info("="*70)
    
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
        logger.error("Failed to download OSM data")
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
    logger.info("\n" + "="*70)
    logger.success("GRAPH GENERATION COMPLETE")
    logger.info("="*70)
    logger.info(f"\nGenerated files:")
    logger.file_op(f"  {edges_csv}")
    logger.file_op(f"  {nodes_csv}")
    logger.file_op(f"  {mapping_csv}")
    logger.file_op(f"  {graph_file}")
    logger.file_op(f"  {graphml_file}")
    logger.info("")
    logger.info(f"Graph statistics:")
    logger.location(f"  Location: {PLACE_NAME}")
    logger.graph(f"  Nodes: {len(G.nodes())}")
    logger.graph(f"  Edges: {len(G.edges())}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Run traffic data generation: python unified_data_generator.py --mode both")
    logger.info("  2. Build indexes: ./setup.sh --indexes")
    logger.info("  3. Start server: ./setup.sh --server")
    logger.info("")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
