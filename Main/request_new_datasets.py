import os
import random
import requests
import pandas as pd
import numpy as np
import osmnx as ox
import subprocess
import shutil
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from dotenv import load_dotenv
from config import Config

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


# ============================================================
# CONFIGURATION
# ============================================================

def get_config():
    """
    Returns all project configuration constants and paths.
    Uses Config class for directory paths to ensure consistency.
    """
    ox.settings.requests_timeout = 600
    
    # Get HERE API key from environment variable
    here_api_key = os.getenv('HERE_API_KEY', '')
    
    return {
        'USE_HERE_API_DATA': False,
        'NUMBER_OF_SCENARIOS': 2,
        'SYNTHETIC_JAM_PERCENTAGE_RANGE': (0.10, 0.20),
        'SYNTHETIC_CLOSURE_PERCENTAGE_RANGE': (0.005, 0.02),
        'HERE_API_KEY': here_api_key,  # Now loaded from environment
        'PLACE_NAME': "Quezon City, Philippines",
        'DEFAULT_SPEED_KPH': 50,
        'MIN_SPEED_KPH': 1,
        'DISRUPTION_PERCENTAGE': 0.15,

        # File paths - using Config class for consistency
        'BASE_GRAPH_CSV': str(Config.EDGES_CSV),
        'BASE_NODES_CSV': str(Config.NODES_CSV),
        'OUTPUT_DIR': str(Config.DISRUPTIONS_DIR),
        'PROCESSED_DIR': str(Config.PROCESSED_DATA_DIR),
        'DISRUPTED_SCENARIO_GR': 'qc_disrupted_scenario_1.gr',
        'OUTPUT_FILE_TEMPLATE': str(Config.DISRUPTIONS_DIR / 'qc_scenario_for_cpp_{}.csv'),
        'OUTPUT_FOLDER': str(Config.RAW_DATA_DIR),
        'EDGES_FILENAME': 'quezon_city_edges.csv',
        'NODES_FILENAME': 'quezon_city_nodes.csv',
        'MAPPING_FILENAME': 'node_id_mapping.csv',

        # Default speed estimates
        'DEFAULT_SPEEDS': {
            "motorway": 80, "trunk": 70, "primary": 60, "secondary": 40,
            "tertiary": 30, "residential": 20, "unclassified": 25, "service": 15,
        },

        # Synthetic disruption levels
        'DISRUPTION_LEVELS': {
            'Light': {'jam_factor_range': (2.0, 4.0), 'speed_reduction_factor_range': (0.7, 0.9)},
            'Medium': {'jam_factor_range': (4.0, 7.0), 'speed_reduction_factor_range': (0.4, 0.7)},
            'Heavy': {'jam_factor_range': (7.0, 10.0), 'speed_reduction_factor_range': (0.1, 0.4)}
        }
    }


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def kph_to_mps(kph: float) -> float:
    """Convert speed from kilometers per hour to meters per second."""
    return kph * 1000 / 3600


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two lat/lon points in meters."""
    R = 6371000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    a = sin((lat2 - lat1) / 2)**2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def get_estimated_speed(highway: str) -> float:
    """Estimate the average speed (km/h) based on highway type."""
    return get_config()['DEFAULT_SPEEDS'].get(str(highway).lower(), 30)


# ============================================================
# OSM DATASET GENERATION
# ============================================================

def generate_osm_graph_datasets():
    """
    Fetches the OpenStreetMap graph for the configured city,
    processes it into edge, node, and mapping CSVs.
    """
    cfg = get_config()
    place_name = cfg['PLACE_NAME']
    output_folder = cfg['OUTPUT_FOLDER']

    print(f"Fetching road network for '{place_name}' from OpenStreetMap...")
    G = ox.graph_from_place(place_name, network_type=Config.NETWORK_TYPE)

    print("Converting graph data to DataFrames...")
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    gdf_nodes.reset_index(inplace=True)
    gdf_edges.reset_index(inplace=True)
    print(f"Found {len(gdf_nodes)} nodes and {len(gdf_edges)} edges.")

    print("Creating node ID mapping...")
    all_edge_nodes = pd.concat([gdf_edges['u'], gdf_edges['v']]).unique()
    unique_osm_ids = np.sort(all_edge_nodes)
    osm_to_seq = {osm_id: i for i, osm_id in enumerate(unique_osm_ids, start=1)}
    seq_to_osm = {v: k for k, v in osm_to_seq.items()}

    # Prepare Edges
    gdf_edges['name'] = gdf_edges.get('name', 'Unnamed Road')
    
    # Handle oneway field - OSM uses 'yes', 'no', '-1' (reverse direction), or True/False
    # Convert to standardized format: 0 (bidirectional), 1 (forward only), -1 (reverse only)
    def process_oneway(value):
        if pd.isna(value) or value == 'no' or value == False:
            return 0  # Bidirectional
        elif value == 'yes' or value == True or value == '1':
            return 1  # Forward direction only
        elif value == '-1' or value == 'reverse':
            return -1  # Reverse direction only
        else:
            return 0  # Default to bidirectional
    
    gdf_edges['oneway'] = gdf_edges.get('oneway', 0).apply(process_oneway)
    
    # Extract geometry coordinates from LineString/MultiLineString
    def extract_geometry_coords(geom):
        """Extract coordinates from geometry as JSON string"""
        if geom is None or pd.isna(geom):
            return "[]"
        
        coords = []
        if hasattr(geom, 'coords'):
            # LineString
            coords = [[round(lon, 6), round(lat, 6)] for lon, lat in geom.coords]
        elif hasattr(geom, 'geoms'):
            # MultiLineString - concatenate all parts
            for line in geom.geoms:
                coords.extend([[round(lon, 6), round(lat, 6)] for lon, lat in line.coords])
        
        # Return as JSON string for CSV storage
        import json
        return json.dumps(coords)
    
    gdf_edges['geometry_coords'] = gdf_edges['geometry'].apply(extract_geometry_coords)
    
    df_edges = gdf_edges.assign(
        source=gdf_edges['u'].map(osm_to_seq),
        target=gdf_edges['v'].map(osm_to_seq)
    )[["source", "target", "length", "name", "highway", "oneway", "geometry_coords"]].copy()
    df_edges['length'] = df_edges['length'].round(2)

    # Prepare Nodes
    df_nodes = gdf_nodes.assign(node_id=gdf_nodes['osmid'].map(osm_to_seq))
    df_nodes = df_nodes[df_nodes['node_id'].notna()][['node_id', 'y', 'x']].rename(
        columns={'y': 'latitude', 'x': 'longitude'}
    )
    df_nodes = df_nodes.round({'latitude': 6, 'longitude': 6}).sort_values('node_id').reset_index(drop=True)

    # Mapping Table
    df_mapping = pd.DataFrame({'sequential_id': list(seq_to_osm.keys()), 'osm_id': list(seq_to_osm.values())})

    # Validate before saving
    if not validate_graph_data(df_edges, df_nodes):
        raise ValueError("Graph validation failed. Please check the data.")

    # Save all files
    os.makedirs(output_folder, exist_ok=True)

    edges_path = os.path.join(output_folder, cfg['EDGES_FILENAME'])
    nodes_path = os.path.join(output_folder, cfg['NODES_FILENAME'])
    mapping_path = os.path.join(output_folder, cfg['MAPPING_FILENAME'])

    df_edges.to_csv(edges_path, index=False)
    print(f"✅ Created edges file: {edges_path}")

    df_nodes.to_csv(nodes_path, index=False)
    print(f"✅ Created nodes file: {nodes_path}")

    df_mapping.to_csv(mapping_path, index=False)
    print(f"✅ Created mapping file: {mapping_path}")

    print(f"✅ Finished generating OSM graph datasets.\n")



def validate_graph_data(edges_df, nodes_df):
    """Check for missing or inconsistent node references."""
    edge_nodes = set(edges_df['source']) | set(edges_df['target'])
    node_ids = set(nodes_df['node_id'].dropna())
    if missing := (edge_nodes - node_ids):
        print(f"❌ Missing {len(missing)} node(s) referenced in edges.")
        return False
    if node_ids != set(range(1, len(node_ids) + 1)):
        print(f"❌ Node IDs are not sequential.")
        return False
    print("✅ Graph validation passed.")
    return True


# ============================================================
# GRAPH FILE CREATION
# ============================================================

def generate_gr_file_from_edges(edges_csv_path, output_gr_path, directed=True):
    """Generate DIMACS .gr format file from edge data."""
    df = pd.read_csv(edges_csv_path)
    df['speed_kmh'] = df['highway'].apply(get_estimated_speed)
    df['travel_time_sec'] = (df['length'] / 1000) / (df['speed_kmh'] / 3600)
    df['travel_time_sec'] = df['travel_time_sec'].round().astype(int).clip(lower=1)

    node_map = {nid: i + 1 for i, nid in enumerate(sorted(pd.concat([df['source'], df['target']]).unique()))}
    n, m = len(node_map), len(df)

    os.makedirs(os.path.dirname(output_gr_path), exist_ok=True)
    with open(output_gr_path, 'w') as f:
        f.write(f"p sp {n} {m}\n")
        for _, row in df.iterrows():
            u, v, w = node_map[row['source']], node_map[row['target']], row['travel_time_sec']
            f.write(f"a {u} {v} {w}\n")
            if not directed:
                f.write(f"a {v} {u} {w}\n")

    print(f"✅ Wrote {m} edges, {n} nodes to {output_gr_path}")
    print(f"📁 Created GR file: {output_gr_path}\n")


def generate_gr_file_from_disruption_csv():
    """
    Generates a .gr file from an existing base graph CSV by applying
    randomized traffic disruptions (light, medium, heavy).
    """
    cfg = get_config()

    # Use paths from Config class
    base_graph_csv = cfg['BASE_GRAPH_CSV']
    output_gr_file = os.path.join(cfg['PROCESSED_DIR'], cfg['DISRUPTED_SCENARIO_GR'])

    print("\n--- Starting disrupted graph generation ---")
    print(f"Attempting to load base graph from: {base_graph_csv}")

    # Load base graph
    try:
        df = pd.read_csv(base_graph_csv)
        print(f"✅ Loaded base graph with {len(df)} edges.")
    except FileNotFoundError:
        print(f"❌ ERROR: Base graph not found at {base_graph_csv}")
        return

    # Validation
    if 'length' not in df.columns:
        print("❌ ERROR: Input CSV missing 'length' column.")
        return

    # Initialize speed and jam columns
    df['jam_factor'] = 1.0
    df['speed_mps'] = kph_to_mps(cfg['DEFAULT_SPEED_KPH'])

    # Apply random disruptions
    num_disrupted = int(len(df) * cfg['DISRUPTION_PERCENTAGE'])
    disrupted_indices = random.sample(range(len(df)), num_disrupted)
    print(f"Applying randomized disruptions to {num_disrupted} edges...")

    for idx in disrupted_indices:
        level, params = random.choice(list(cfg['DISRUPTION_LEVELS'].items()))
        new_jam = random.uniform(*params['jam_factor_range'])
        reduction = random.uniform(*params['speed_reduction_factor_range'])
        df.loc[idx, 'jam_factor'] = new_jam
        df.loc[idx, 'speed_mps'] *= reduction

    # Compute dynamic weight
    df['speed_mps'] = df['speed_mps'].clip(lower=kph_to_mps(cfg['MIN_SPEED_KPH']))
    df['dynamic_weight'] = (df['length'] / df['speed_mps']) * df['jam_factor']
    print("✅ Calculated dynamic weights for all edges.")

    # Validate node IDs
    min_node_id = df[['source', 'target']].min().min()
    max_node_id = df[['source', 'target']].max().max()
    if min_node_id != 1:
        print(f"❌ ERROR: Node IDs should start from 1 but found {min_node_id}")
        return

    node_count = max_node_id
    edge_count = len(df)
    print(f"Graph stats: {node_count} nodes, {edge_count} edges")

    # Save to .gr file
    os.makedirs(os.path.dirname(output_gr_file), exist_ok=True)
    with open(output_gr_file, 'w') as f:
        f.write(f"p sp {node_count} {edge_count}\n")
        for _, row in df.iterrows():
            f.write(f"a {int(row['source'])} {int(row['target'])} {round(row['dynamic_weight'], 4)}\n")

    print(f"📁 Created disrupted graph file: {output_gr_file}\n")


# ============================================================
# INDEX FILE BUILDING
# ============================================================

def build_index_files():
    """Build DHL and HC2L index files from the generated graph."""
    cfg = get_config()
    
    # Get project root (parent of Main directory)
    main_dir = Path(__file__).parent
    project_root = main_dir.parent
    build_dir = main_dir / 'build'
    processed_dir = Path(cfg['PROCESSED_DIR'])
    
    # File paths
    gr_input = processed_dir / 'qc_from_csv.gr'
    graph_output = processed_dir / 'quezon_city.graph'
    dhl_index_base = processed_dir / 'quezon_city'
    hc2l_index_output = processed_dir / 'quezon_city.hc2l.index'
    
    # Check if index executables exist
    dhl_index_exe = build_dir / 'dhl' / 'index'
    hc2l_index_exe = build_dir / 'hc2l' / 'index'
    
    # Check for Windows executables
    if not dhl_index_exe.exists():
        dhl_index_exe = build_dir / 'dhl' / 'index.exe'
    if not hc2l_index_exe.exists():
        hc2l_index_exe = build_dir / 'hc2l' / 'index.exe'
    
    if not dhl_index_exe.exists() or not hc2l_index_exe.exists():
        print("\n⚠️  Warning: Index executables not found!")
        print(f"   Expected locations:")
        print(f"     - DHL: {build_dir / 'dhl' / 'index'}")
        print(f"     - HC2L: {build_dir / 'hc2l' / 'index'}")
        print("\n   Please run the build script first:")
        print("     Linux/Mac: ./build_all.sh")
        print("     Windows:   build_all.bat")
        print("\n   Skipping index building...")
        return False
    
    print("\n" + "="*70)
    print("  Building Graph Indexes")
    print("="*70)
    
    # Step 1: Create binary graph file
    print("\n📊 Step 1: Converting .gr to binary graph format...")
    print(f"   Input:  {gr_input}")
    print(f"   Output: {graph_output}")
    
    try:
        shutil.copy(str(gr_input), str(graph_output))
        print("   ✅ Graph file created")
    except Exception as e:
        print(f"   ❌ Error creating graph file: {e}")
        return False
    
    # Step 2: Build DHL index
    print("\n📊 Step 2: Building DHL index...")
    print(f"   Input:  {graph_output}")
    print(f"   Output: {dhl_index_base}.dhl.index")
    
    try:
        # Run DHL index builder
        result = subprocess.run(
            [str(dhl_index_exe), str(graph_output), str(dhl_index_base)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        # The DHL builder creates files with _dhl and _ch suffixes
        # Rename them to match API expectations
        dhl_file = Path(f"{dhl_index_base}_dhl")
        ch_file = Path(f"{dhl_index_base}_ch")
        
        if dhl_file.exists():
            dhl_file.rename(f"{dhl_index_base}.dhl.index")
            print("   ✅ DHL index built successfully")
        else:
            print("   ⚠️  DHL index file not found at expected location")
        
        if ch_file.exists():
            ch_file.rename(f"{dhl_index_base}.dhl.ch")
            print("   ✅ DHL contraction hierarchy built")
            
    except subprocess.TimeoutExpired:
        print("   ❌ DHL index building timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error building DHL index: {e}")
        return False
    
    # Step 3: Build HC2L index
    print("\n📊 Step 3: Building HC2L index...")
    print(f"   Input:  {graph_output}")
    print(f"   Output: {hc2l_index_output}")
    
    try:
        # Run HC2L index builder (reads from stdin, writes to stdout)
        with open(graph_output, 'r') as input_file:
            with open(hc2l_index_output, 'w') as output_file:
                result = subprocess.run(
                    [str(hc2l_index_exe)],
                    stdin=input_file,
                    stdout=output_file,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
        
        if hc2l_index_output.exists() and hc2l_index_output.stat().st_size > 0:
            print("   ✅ HC2L index built successfully")
        else:
            print("   ⚠️  HC2L index file not found or empty")
            
    except subprocess.TimeoutExpired:
        print("   ❌ HC2L index building timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error building HC2L index: {e}")
        return False
    
    # Step 4: Verify all files
    print("\n📊 Step 4: Verifying created files...")
    
    files_to_check = [
        graph_output,
        Path(f"{dhl_index_base}.dhl.index"),
        hc2l_index_output
    ]
    
    all_ok = True
    for file_path in files_to_check:
        if file_path.exists() and file_path.stat().st_size > 0:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"   ✅ {file_path.name} ({size_mb:.2f} MB)")
        else:
            print(f"   ❌ Missing or empty: {file_path.name}")
            all_ok = False
    
    print("\n" + "="*70)
    if all_ok:
        print("✅ Index building completed successfully!")
    else:
        print("⚠️  Index building completed with warnings")
    print("="*70 + "\n")
    
    return all_ok


# ============================================================
# MAIN CONTROLLER
# ============================================================

def generate_all_datasets():
    """Main controller to generate all required datasets."""
    cfg = get_config()

    # Step 1: Generate base OSM datasets (now includes geometry in CSV)
    generate_osm_graph_datasets()

    # Step 2: Create GR file
    base_edges_path = cfg['BASE_GRAPH_CSV']
    gr_output_path = os.path.join(cfg['PROCESSED_DIR'], 'qc_from_csv.gr')
    generate_gr_file_from_edges(base_edges_path, gr_output_path)

    # Step 3: Load datasets
    base_df = pd.read_csv(base_edges_path)
    nodes_df = pd.read_csv(cfg['BASE_NODES_CSV'])
    node_coords = {row['node_id']: (row['latitude'], row['longitude']) for _, row in nodes_df.iterrows()}

    # Step 4: Generate QC disrupted .gr file
    generate_gr_file_from_disruption_csv()

    # Step 5: Generate scenarios
    os.makedirs(cfg['OUTPUT_DIR'], exist_ok=True)
    for i in range(1, cfg['NUMBER_OF_SCENARIOS'] + 1):
        print(f"\n--- Generating Scenario {i}/{cfg['NUMBER_OF_SCENARIOS']} ---")
        df = base_df.copy()
        df['freeFlow_kph'] = cfg['DEFAULT_SPEED_KPH']
        df['speed_kph'] = df['freeFlow_kph']
        df['jamFactor'] = 1.0
        df['isClosed'] = False

        eligible = df.index.tolist()
        closure_pct = random.uniform(*cfg['SYNTHETIC_CLOSURE_PERCENTAGE_RANGE'])
        jam_pct = random.uniform(*cfg['SYNTHETIC_JAM_PERCENTAGE_RANGE'])

        closures = random.sample(eligible, int(len(eligible) * closure_pct))
        df.loc[closures, ['isClosed', 'jamFactor', 'speed_kph']] = [True, 10.0, cfg['MIN_SPEED_KPH']]
        print(f"Applied {len(closures)} synthetic road closures.")

        remaining = [idx for idx in eligible if idx not in closures]
        disruptions = random.sample(remaining, int(len(remaining) * jam_pct))
        for idx in disruptions:
            params = random.choice(list(cfg['DISRUPTION_LEVELS'].values()))
            df.loc[idx, 'jamFactor'] = random.uniform(*params['jam_factor_range'])
            df.loc[idx, 'speed_kph'] *= random.uniform(*params['speed_reduction_factor_range'])
        print(f"Applied {len(disruptions)} synthetic disruptions.")

        # Merge coordinates
        df = df.merge(nodes_df.rename(columns={'node_id': 'source', 'latitude': 'source_lat', 'longitude': 'source_lon'}),
                      on='source', how='left')
        df = df.merge(nodes_df.rename(columns={'node_id': 'target', 'latitude': 'target_lat', 'longitude': 'target_lon'}),
                      on='target', how='left')

        final_cols = [
            'source_lat', 'source_lon', 'target_lat', 'target_lon',
            'source', 'target', 'name', 'speed_kph', 'freeFlow_kph',
            'jamFactor', 'isClosed', 'length', 'oneway'
        ]
        output_df = df[final_cols].rename(columns={'length': 'segmentLength', 'name': 'road_name'})
        output_path = cfg['OUTPUT_FILE_TEMPLATE'].format(i)
        output_df.to_csv(output_path, index=False, float_format='%.6f')
        print(f"📁 Created scenario file {i}: {output_path}\n")

    # Print summary of created files
    print("\n📂 Files created:")
    print(f"   - Edges CSV (with geometry): {cfg['OUTPUT_FOLDER']}/{cfg['EDGES_FILENAME']}")
    print(f"   - Nodes CSV:                 {cfg['OUTPUT_FOLDER']}/{cfg['NODES_FILENAME']}")
    print(f"   - Mapping CSV:               {cfg['OUTPUT_FOLDER']}/{cfg['MAPPING_FILENAME']}")
    print(f"   - Base Graph (.gr):          {os.path.join(cfg['PROCESSED_DIR'], 'qc_from_csv.gr')}")

    # List generated scenario files
    print("   - Scenario CSVs:")
    for i in range(1, cfg['NUMBER_OF_SCENARIOS'] + 1):
        scenario_path = cfg['OUTPUT_FILE_TEMPLATE'].format(i)
        print(f"       • {scenario_path}")

    print("\n--- Dataset generation completed successfully! ---")
    
    # Step 6: Build index files
    print("\n🔧 Building index files for routing algorithms...")
    index_success = build_index_files()
    
    if index_success:
        print("\n✅ All datasets and indexes generated successfully!")
        print("\n🚀 You can now start the Flask server:")
        print("   Linux/Mac: ./run_server.sh")
        print("   Fish Shell: ./run_server.fish")
        print("   Windows: run_server.bat")
    else:
        print("\n⚠️  Dataset generation completed, but index building had issues.")
        print("   You may need to build the indexes manually using:")
        print("   Linux/Mac: ./generate_data.sh")
        print("   Fish Shell: ./generate_data.fish")
        print("   Windows: generate_data.bat")

    return True

# def test():
#     return 'New set of dataset added successfully'

if __name__ == "__main__":
    generate_all_datasets()
