# flask_server.py - Enhanced with HC2L (Hierarchical Cut Labelling) Routing
from flask import Flask, request, jsonify, render_template
import pandas as pd
import time
from pathlib import Path
import atexit
import logging
from collections import deque
from datetime import datetime

# Import configuration
from config import Config

# Import your coordinate mapper and GPS HC2L router
from coordinate_mapper import NodeMapper
from gps_hc2l_router import GPSRoutingService
from dhl_router import DHLRouter

# Import auto-disruption service
from auto_disruption_service import init_auto_disruption_service, shutdown_auto_disruption_service, get_auto_disruption_service

# Import Google Maps service
from google_maps_service import GoogleMapsService

# Import HERE Traffic service (V2 - hash-based)
from realtime_traffic_service import RealtimeTrafficService


app = Flask(__name__)

# Configure Flask from config file
app.config['DEBUG'] = Config.FLASK_DEBUG
app.config['ENV'] = Config.FLASK_ENV

# ============================================================
# BACKEND LOGGING SYSTEM
# ============================================================

# In-memory log buffer (thread-safe circular buffer)
backend_logs = deque(maxlen=1000)  # Keep last 1000 logs
backend_log_counter = 0

class BackendLogHandler(logging.Handler):
    """Custom log handler that captures logs to in-memory buffer"""
    
    def emit(self, record):
        global backend_log_counter
        backend_log_counter += 1
        
        try:
            log_entry = {
                'id': backend_log_counter,
                'timestamp': record.created,
                'level': record.levelname,
                'message': self.format(record),
                'module': record.module,
                'line': record.lineno,
                'function': record.funcName
            }
            backend_logs.append(log_entry)
        except Exception as e:
            # Fail silently to avoid breaking the app
            print(f"Error in BackendLogHandler: {e}")

# Configure backend logging
backend_handler = BackendLogHandler()
backend_handler.setLevel(logging.DEBUG)
backend_formatter = logging.Formatter('%(levelname)s - %(module)s:%(lineno)d - %(message)s')
backend_handler.setFormatter(backend_formatter)

# Add handler to Flask logger and root logger
app.logger.addHandler(backend_handler)
logging.getLogger().addHandler(backend_handler)
logging.getLogger().setLevel(logging.DEBUG)

# Add initial log
app.logger.info("Backend logging system initialized")

# ============================================================
# END BACKEND LOGGING SYSTEM
# ============================================================

# Initialize components using config paths
mapper = NodeMapper(str(Config.NODES_CSV))
try:
    gps_router = GPSRoutingService()
    print("✅ GPS HC2L Router initialized successfully")
except Exception as e:
    print(f"❌ Error initializing GPS HC2L Router: {e}")
    gps_router = None

# Initialize DHL Router
try:
    dhl_router = DHLRouter()
    print("✅ DHL Router initialized successfully")
except Exception as e:
    print(f"❌ Error initializing DHL Router: {e}")
    dhl_router = None

# Initialize Google Maps Service
try:
    gmaps_service = GoogleMapsService()
    print("✅ Google Maps Service initialized successfully")
except Exception as e:
    print(f"❌ Error initializing Google Maps Service: {e}")
    gmaps_service = None

# Initialize HERE Traffic Service (V2 - hash-based)
try:
    traffic_service = RealtimeTrafficService()
    print("✅ HERE Traffic Service V2 initialized successfully")
except Exception as e:
    print(f"❌ Error initializing HERE Traffic Service: {e}")
    traffic_service = None

# Auto-disruption service with 1-minute updates
auto_service = init_auto_disruption_service(app, update_interval=60)

# Shutdown service on exit
atexit.register(shutdown_auto_disruption_service)

# ============================================================
# GLOBAL CACHES - Prevent reloading data on every request
# ============================================================

# Cache for OSM edges with geometry (loaded once, reused across requests)
_edges_cache = {
    'data': None,          # Dataframe with all edges
    'lookup': None,        # Dictionary for fast edge lookup by (source, target)
    'file_mtime': 0,       # File modification time for cache invalidation
    'loaded_at': 0         # Timestamp when cache was loaded
}

# Cache for traffic data (invalidates based on file modification time)
_traffic_cache = {
    'segments': None,       # Processed traffic segments with geometry
    'file_path': None,      # Path to traffic file
    'file_mtime': 0,        # File modification time
    'loaded_at': 0          # Timestamp when cache was loaded
}


def load_edges_with_cache():
    """
    Load OSM edges with geometry using cache.
    Only reloads if file has been modified since last load.
    
    Returns:
        tuple: (edges_df, edge_lookup) or (None, None) on error
    """
    global _edges_cache
    import os
    
    edges_file = str(Config.EDGES_CSV)
    
    try:
        # Get current file modification time
        current_mtime = os.path.getmtime(edges_file)
        
        # Check if cache is valid
        if (_edges_cache['data'] is not None and 
            _edges_cache['lookup'] is not None and
            _edges_cache['file_mtime'] == current_mtime):
            # Cache hit - reuse existing data
            return _edges_cache['data'], _edges_cache['lookup']
        
        # Cache miss or invalidated - reload
        print(f"🔄 Loading OSM edges with geometry from {Config.EDGES_CSV.name}...")
        edges_df = pd.read_csv(edges_file)
        print(f"   📂 Loaded {len(edges_df)} OSM edges")
        
        # Build edge lookup dictionary
        edge_lookup = {}
        for _, edge in edges_df.iterrows():
            key = (int(edge['source']), int(edge['target']))
            
            # Parse geometry
            geometry_str = edge['geometry']
            if isinstance(geometry_str, str):
                try:
                    import json
                    geometry = json.loads(geometry_str)
                except (json.JSONDecodeError, ValueError):
                    try:
                        import ast
                        geometry = ast.literal_eval(geometry_str)
                    except (ValueError, SyntaxError):
                        geometry = [[float(edge['source_lat']), float(edge['source_lon'])], 
                                   [float(edge['target_lat']), float(edge['target_lon'])]]
            else:
                geometry = geometry_str
            
            if not isinstance(geometry, list) or len(geometry) < 2:
                geometry = [[float(edge['source_lat']), float(edge['source_lon'])], 
                           [float(edge['target_lat']), float(edge['target_lon'])]]
                
            edge_lookup[key] = {
                'geometry': geometry,
                'road_name': str(edge.get('road_name', 'Unknown Road')),
                'highway_type': str(edge.get('highway_type', 'unknown')),
                'length': float(edge.get('length', 0)),
                'freeFlow_kph': float(edge.get('freeFlow_kph', 50.0)) if pd.notna(edge.get('freeFlow_kph')) else 50.0
            }
        
        # Update cache
        _edges_cache['data'] = edges_df
        _edges_cache['lookup'] = edge_lookup
        _edges_cache['file_mtime'] = current_mtime
        _edges_cache['loaded_at'] = time.time()
        
        print(f"   ✅ Cached {len(edge_lookup)} edges with geometries")
        return edges_df, edge_lookup
        
    except Exception as e:
        print(f"   ❌ Error loading edges: {e}")
        return None, None


def load_traffic_with_cache(edge_lookup):
    """
    Load traffic data with geometry using cache.
    Only reloads if traffic file has changed.
    
    Args:
        edge_lookup: Dictionary mapping (source, target) to edge data
        
    Returns:
        list: Traffic segments with geometry
    """
    global _traffic_cache
    import glob
    import os
    
    try:
        # Find latest disruption files
        disruptions_dir = Config.DISRUPTIONS_DIR
        both_files = glob.glob(str(disruptions_dir / 'traffic_*_both.csv'))
        
        if not both_files:
            print("   ℹ️  No traffic files found")
            return []
        
        # Get most recent file
        latest_file = max(both_files, key=os.path.getmtime)
        current_mtime = os.path.getmtime(latest_file)
        
        # Check cache validity
        if (_traffic_cache['segments'] is not None and
            _traffic_cache['file_path'] == latest_file and
            _traffic_cache['file_mtime'] == current_mtime):
            # Cache hit
            return _traffic_cache['segments']
        
        # Cache miss - reload traffic data
        print(f"   🔄 Loading traffic data from: {os.path.basename(latest_file)}")
        traffic_df = pd.read_csv(latest_file)
        
        traffic_segments = []
        for _, row in traffic_df.iterrows():
            edge_key = (int(row['source']), int(row['target']))
            edge_data = edge_lookup.get(edge_key)
            
            if not edge_data:
                continue
            
            # Determine severity
            jam_factor = float(row.get('jamFactor', 0.0))
            if jam_factor >= 8.0:
                severity = 'Heavy'
            elif jam_factor >= 5.0:
                severity = 'Medium'
            else:
                severity = 'Light'
            
            # Sanitize geometry
            geometry = edge_data['geometry']
            if isinstance(geometry, list):
                geometry = [[float(coord[0]), float(coord[1])] for coord in geometry 
                           if len(coord) >= 2 and 
                           not (pd.isna(coord[0]) or pd.isna(coord[1]) or 
                                coord[0] == float('inf') or coord[1] == float('inf'))]
            
            if not geometry or len(geometry) < 2:
                continue
            
            traffic_segments.append({
                'type': 'flow',
                'incident_type': str(row.get('incident_type', 'Congestion')),
                'severity': severity,
                'geometry': geometry,
                'road_name': str(row.get('road_name', edge_data['road_name'])),
                'highway_type': str(row.get('highway_type', edge_data['highway_type'])),
                'length': float(edge_data['length']),
                'speed_kph': float(row['speed_kph']),
                'free_flow_kph': float(row['freeFlow_kph']),
                'jam_factor': float(jam_factor),
                'is_closed': bool(row.get('isClosed', False)),
                'source': int(row['source']),
                'target': int(row['target'])
            })
        
        # Update cache
        _traffic_cache['segments'] = traffic_segments
        _traffic_cache['file_path'] = latest_file
        _traffic_cache['file_mtime'] = current_mtime
        _traffic_cache['loaded_at'] = time.time()
        
        print(f"   ✅ Cached {len(traffic_segments)} traffic segments")
        return traffic_segments
        
    except Exception as e:
        print(f"   ❌ Error loading traffic: {e}")
        return []


def get_dynamic_disruption_file(algorithm: str = 'hc2l', dataset_mode: str = None) -> str:
    """
    Get the path to the current traffic disruption CSV file.
    
    **CACHE-ONLY SYSTEM**: 
    - Only uses existing CSV files (NO auto-fetching)
    - Returns latest CSV file regardless of age
    - Traffic updates must be manually triggered via /fetch_here_traffic endpoint
    - This prevents automatic API calls on every route calculation
    
    Args:
        algorithm: 'hc2l' or 'dhl' (for backward compatibility, not used)
        dataset_mode: 'none' or 'both' (simplified from old 4-option system)
        
    Returns:
        Path to disruption CSV file as string, or empty string if no disruptions
    """
    import time
    from pathlib import Path
    
    # Simplified: only 'none' or 'both' modes now
    if dataset_mode is None:
        dataset_mode = 'both'  # Default to using traffic data
    
    # If mode is 'none', return empty string (no disruptions)
    if dataset_mode == 'none':
        return ""
    
    # Find latest traffic CSV file
    traffic_pattern = f"traffic_*_{dataset_mode}.csv"
    traffic_files = sorted(Config.DISRUPTIONS_DIR.glob(traffic_pattern), reverse=True)
    
    # Use latest file if available (regardless of age - CACHE ONLY)
    if traffic_files:
        latest_file = traffic_files[0]
        file_age = time.time() - latest_file.stat().st_mtime
        # Always use cached file, never auto-fetch
        return str(latest_file)
    
    # No traffic files found - return empty (do NOT auto-fetch)
    return ""


def enhance_alternative_routes_with_geometry(alternative_routes):
    """
    Alternative routes geometry is now provided by C++ APIs directly.
    Geometry structure (NEW):
        - Each geometry segment includes: edge (source-target), source, target, coordinates, color, highway_type
        - Removed: path_nodes, path_node_ids, distance_meters per segment (distance_meters is at route level only)
        - highway_type now follows the actual road type (not "alternative")
    
    Args:
        alternative_routes: List of alternative route objects from C++ API
        
    Returns:
        list: Alternative routes (unchanged, geometry already from C++)
    """
    if not alternative_routes:
        return []
    
    try:
        enhanced_routes = []
        
        for route in alternative_routes:
            # Check if route already has geometry from C++ API
            if route.get('geometry') and len(route.get('geometry', [])) > 0:
                print(f"✅ Alternative route rank {route.get('rank')} has {len(route['geometry'])} geometry segments from C++")
                enhanced_routes.append(route)
            else:
                # Fallback: just pass through the route as-is
                print(f"⚠️  Alternative route rank {route.get('rank')} has no geometry from C++, will use geometry as-is")
                enhanced_routes.append(route)
        
        print(f"✅ Processed {len(enhanced_routes)} alternative routes with geometry")
        return enhanced_routes
        
    except Exception as e:
        print(f"⚠️  Error processing alternative routes: {e}")
        return alternative_routes


def cleanup_old_traffic_files(mode: str, max_files: int = 10):
    """
    Remove old traffic files, keeping only the latest N files
    
    Args:
        mode: Traffic mode (flow/incidents/both)
        max_files: Maximum number of files to keep per mode
    """
    traffic_pattern = f"traffic_*_{mode}.csv"
    traffic_files = sorted(Config.DISRUPTIONS_DIR.glob(traffic_pattern), reverse=True)
    
    # Keep only the latest max_files
    if len(traffic_files) > max_files:
        files_to_remove = traffic_files[max_files:]
        for old_file in files_to_remove:
            try:
                old_file.unlink()
                print(f"   🗑️  Removed old file: {old_file.name}")
            except Exception as e:
                print(f"   ⚠️  Failed to remove {old_file.name}: {e}")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_backend_logs')
def get_backend_logs():
    """
    Return backend logs for Developer View
    Optional 'since' parameter to get only new logs
    """
    try:
        since_timestamp = float(request.args.get('since', 0))
        
        # Filter logs newer than 'since' timestamp
        filtered_logs = [
            log for log in backend_logs 
            if log['timestamp'] > since_timestamp
        ]
        
        return jsonify({
            'success': True,
            'logs': filtered_logs,
            'total': len(filtered_logs),
            'buffer_size': len(backend_logs)
        })
    except Exception as e:
        app.logger.error(f"Error retrieving backend logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': []
        })

@app.route('/request_new_dataset')
def request_new_dataset():
    """Fetch latest traffic data using hash-based matching"""
    try:
        if traffic_service:
            # Fetch and save latest traffic data
            metadata = traffic_service.fetch_and_save(mode='both')
            
            return jsonify({
                'success': True,
                'message': f'Traffic data updated: {metadata.get("total_edges", 0)} edges affected',
                'metadata': metadata
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Traffic service not initialized'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@app.route('/report_disruption', methods=['POST'])
def report_disruption():
    """
    Save user-reported disruption with custom traffic flow parameters
    
    Enhanced to support:
    - Custom speed settings (km/h)
    - Road closure toggle (completely blocks road)
    - Automatic jam factor calculation
    - Saving to disruptions CSV for route calculation
    - OSM snapping for accurate road matching
    """
    import csv
    from datetime import datetime
    
    data = request.json
    print(f"📝 Received disruption report: {data}")
    
    try:
        # Extract location
        lat = float(data.get('lat', 0))
        lng = float(data.get('lng', 0))
        
        # Extract incident details
        incident_type = data.get('incident_type', 'other')
        severity = data.get('severity', 'medium')
        description = data.get('description', 'User-reported disruption')
        
        # Extract custom flow parameters
        custom_speed = float(data.get('custom_speed', 30.0))
        free_flow_speed = float(data.get('free_flow_speed', 50.0))
        jam_factor = float(data.get('jam_factor', 5.0))
        is_closed = bool(data.get('is_closed', False))
        
        # Use OSM road snapping for better accuracy
        print(f"🗺️  Attempting OSM road snapping for ({lat}, {lng})...")
        snap_result = mapper.snap_to_osm_road(lat, lng, max_distance_m=100)
        
        if snap_result is None:
            print(f"⚠️  OSM snapping failed, falling back to basic snap")
            # Fallback to basic nearest road snap
            snap_result = mapper.snap_to_nearest_road(lat, lng, max_distance=100)
            
            if snap_result is None:
                return jsonify({
                    'success': False,
                    'error': 'No road within 100m of this location'
                })
            
            # Use basic snap result
            source_id = snap_result['edge'][0]
            target_id = snap_result['edge'][1]
            road_name = snap_result['road_name']
            snapped_lat = snap_result['projection_point']['lat']
            snapped_lng = snap_result['projection_point']['lng']
        else:
            # Use OSM snap result (routing nodes are the actual graph nodes)
            if snap_result.get('routing_nodes') and len(snap_result['routing_nodes']) >= 2:
                source_id = snap_result['routing_nodes'][0]
                target_id = snap_result['routing_nodes'][1]
            else:
                # Fallback to OSM nodes if routing nodes not available
                source_id = snap_result['osm_nodes'][0]
                target_id = snap_result['osm_nodes'][1]
            
            road_name = snap_result['road_name']
            snapped_lat = snap_result['snapped_point']['lat']
            snapped_lng = snap_result['snapped_point']['lng']
            
            print(f"✅ OSM snap successful: {road_name} (Edge: {source_id}→{target_id})")
        
        print(f"✅ Mapped to road: {road_name} (Edge: {source_id}→{target_id})")
        print(f"   Custom flow: {custom_speed} km/h, Jam Factor: {jam_factor}, Closed: {is_closed}")
        
        # Save to user disruptions CSV file
        user_disruptions_file = Config.DISRUPTIONS_DIR / 'user_reported_disruptions.csv'
        
        # Check if file exists to write header
        file_exists = user_disruptions_file.exists()
        
        with open(user_disruptions_file, 'a', newline='') as csvfile:
            fieldnames = [
                'timestamp', 'source', 'target', 'lat', 'lng',
                'snapped_lat', 'snapped_lng', 
                'road_name', 'incident_type', 'severity',
                'speed_kph', 'freeFlow_kph', 'jamFactor', 'isClosed',
                'description'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'timestamp': datetime.now().isoformat(),
                'source': source_id,
                'target': target_id,
                'lat': lat,
                'lng': lng,
                'snapped_lat': snapped_lat,
                'snapped_lng': snapped_lng,
                'road_name': road_name,
                'incident_type': incident_type,
                'severity': severity,
                'speed_kph': custom_speed,
                'freeFlow_kph': free_flow_speed,
                'jamFactor': jam_factor,
                'isClosed': 1 if is_closed else 0,
                'description': description
            })
        
        print(f"💾 Saved user disruption to: {user_disruptions_file.name}")
        
        # IMPORTANT: Merge user disruptions with existing traffic data
        merge_user_disruptions_with_traffic()
        
        return jsonify({
            'success': True,
            'message': f'Disruption reported on {road_name}',
            'road_name': road_name,
            'edge': {'source': source_id, 'target': target_id},
            'snapped_location': {'lat': snapped_lat, 'lng': snapped_lng},
            'custom_flow': {
                'speed_kph': custom_speed,
                'jam_factor': jam_factor,
                'is_closed': is_closed
            }
        })
        
    except Exception as e:
        print(f"❌ Error saving disruption: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


def merge_user_disruptions_with_traffic():
    """
    Merge user-reported disruptions with existing traffic data
    This ensures user disruptions appear on top of real-time traffic
    """
    import glob
    import pandas as pd
    
    try:
        user_disruptions_file = Config.DISRUPTIONS_DIR / 'user_reported_disruptions.csv'
        
        if not user_disruptions_file.exists():
            print("ℹ️  No user disruptions to merge")
            return
        
        # Load user disruptions
        user_df = pd.read_csv(user_disruptions_file)
        print(f"📊 Found {len(user_df)} user-reported disruptions")
        
        # Find latest traffic file
        traffic_pattern = "traffic_*_both.csv"
        traffic_files = sorted(Config.DISRUPTIONS_DIR.glob(traffic_pattern), reverse=True)
        
        if traffic_files:
            # Load existing traffic data
            latest_traffic = traffic_files[0]
            traffic_df = pd.read_csv(latest_traffic)
            print(f"📊 Loaded {len(traffic_df)} traffic segments from {latest_traffic.name}")
            
            # Rename columns to match traffic format
            user_df_renamed = user_df.rename(columns={
                'snapped_lat': 'source_lat',
                'snapped_lng': 'source_lon'
            })
            
            # Add missing columns with defaults
            if 'target_lat' not in user_df_renamed.columns:
                user_df_renamed['target_lat'] = user_df_renamed['source_lat']
            if 'target_lon' not in user_df_renamed.columns:
                user_df_renamed['target_lon'] = user_df_renamed['source_lon']
            
            # Ensure all required columns exist
            required_cols = ['source', 'target', 'source_lat', 'source_lon', 'target_lat', 'target_lon',
                           'road_name', 'speed_kph', 'freeFlow_kph', 'jamFactor', 'isClosed']
            
            for col in required_cols:
                if col not in user_df_renamed.columns:
                    if col in ['speed_kph', 'freeFlow_kph', 'jamFactor']:
                        user_df_renamed[col] = 30.0 if col == 'speed_kph' else 50.0 if col == 'freeFlow_kph' else 5.0
                    elif col == 'isClosed':
                        user_df_renamed[col] = 0
                    else:
                        user_df_renamed[col] = ''
            
            # Merge: user disruptions take priority (added first)
            merged_df = pd.concat([user_df_renamed[required_cols], traffic_df[required_cols]], ignore_index=True)
            
            # Remove duplicates (keep user-reported ones)
            merged_df = merged_df.drop_duplicates(subset=['source', 'target'], keep='first')
            
            # Save merged data
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            merged_file = Config.DISRUPTIONS_DIR / f'traffic_{timestamp}_both.csv'
            merged_df.to_csv(merged_file, index=False)
            
            print(f"✅ Merged traffic data saved: {merged_file.name} ({len(merged_df)} total segments)")
            print(f"   📍 User disruptions: {len(user_df_renamed)}, Traffic: {len(traffic_df)}")
            
        else:
            # No existing traffic data, just save user disruptions as traffic data
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_file = Config.DISRUPTIONS_DIR / f'traffic_{timestamp}_both.csv'
            
            # Prepare user disruptions in traffic format
            user_traffic = user_df.copy()
            user_traffic = user_traffic.rename(columns={
                'snapped_lat': 'source_lat',
                'snapped_lng': 'source_lon'
            })
            
            required_cols = ['source', 'target', 'source_lat', 'source_lon',
                           'road_name', 'speed_kph', 'freeFlow_kph', 'jamFactor', 'isClosed']
            
            user_traffic.to_csv(new_file, index=False, columns=required_cols)
            print(f"✅ Created traffic file from user disruptions: {new_file.name}")
            
    except Exception as e:
        print(f"⚠️  Error merging user disruptions: {e}")
        import traceback
        traceback.print_exc()

@app.route('/search_location', methods=['POST'])
def search_location():
    """
    Search for locations within Quezon City using Photon API (OSM alternative to Nominatim)
    Returns list of matching places with coordinates
    """
    import requests
    
    data = request.json
    query = data.get('query', '').strip()
    print(f"[SEARCH] Query received: '{query}'")
    
    if not query:
        print("[SEARCH] ❌ Query is empty")
        return jsonify({
            'success': False,
            'error': 'Search query is required'
        })
    
    try:
        # Quezon City coordinates (approximate center)
        qc_lat = 14.6760
        qc_lng = 121.0437
        
        # Try Photon API first (faster, more reliable than Nominatim)
        photon_url = "https://photon.komoot.io/api"
        params = {
            'q': query,
            'lat': qc_lat,
            'lon': qc_lng,
            'limit': 10,
            'bbox': '121.000,14.500,121.150,14.800'  # Quezon City bounds
        }
        
        headers = {
            'User-Agent': 'REACT-Navigation-App/1.0'
        }
        
        print(f"[SEARCH] Trying Photon API: {photon_url}")
        response = requests.get(photon_url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        data_response = response.json()
        results = data_response.get('features', [])
        print(f"[SEARCH] Photon returned {len(results)} results")
        
        # Process Photon results
        filtered_results = []
        for result in results:
            try:
                properties = result.get('properties', {})
                geometry = result.get('geometry', {})
                coords = geometry.get('coordinates', [])
                
                if len(coords) < 2:
                    continue
                
                lng = float(coords[0])
                lat = float(coords[1])
                
                # Build location name
                name_parts = []
                if properties.get('name'):
                    name_parts.append(properties['name'])
                if properties.get('city'):
                    name_parts.append(properties['city'])
                if properties.get('state'):
                    name_parts.append(properties['state'])
                
                name = ', '.join(name_parts) if name_parts else 'Unknown Location'
                loc_type = properties.get('osm_type', 'place')
                
                # Double-check if within Quezon City bounds (with 5km tolerance)
                if 14.45 <= lat <= 14.85 and 120.95 <= lng <= 121.20:
                    filtered_results.append({
                        'name': name,
                        'lat': lat,
                        'lng': lng,
                        'type': loc_type,
                        'address': properties
                    })
                    print(f"  ✅ Added: {name} ({lat:.4f}, {lng:.4f})")
                else:
                    print(f"  ⚠️  Outside bounds: {name} ({lat:.4f}, {lng:.4f})")
            except (ValueError, TypeError, KeyError) as e:
                print(f"  ⚠️  Parse error: {e}")
                continue
        
        print(f"[SEARCH] ✅ Returning {len(filtered_results)} results from Photon")
        return jsonify({
            'success': True,
            'results': filtered_results,
            'count': len(filtered_results)
        })
        
    except requests.exceptions.Timeout:
        print(f"[SEARCH] ⚠️  Photon timeout, trying fallback...")
        # Fallback: try Nominatim if Photon fails
        try:
            nominatim_url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': f"{query}, Quezon City",
                'format': 'json',
                'limit': 10,
                'viewbox': '121.000,14.500,121.150,14.800',
                'bounded': 1,
                'addressdetails': 1
            }
            headers = {'User-Agent': 'REACT-Navigation-App/1.0'}
            
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            results = response.json()
            
            filtered_results = []
            for result in results:
                try:
                    lat = float(result.get('lat', 0))
                    lng = float(result.get('lon', 0))
                    name = result.get('display_name', 'Unknown')
                    
                    if 14.45 <= lat <= 14.85 and 120.95 <= lng <= 121.20:
                        filtered_results.append({
                            'name': name,
                            'lat': lat,
                            'lng': lng,
                            'type': result.get('type', 'place'),
                            'address': result.get('address', {})
                        })
                except (ValueError, TypeError):
                    continue
            
            return jsonify({
                'success': True,
                'results': filtered_results,
                'count': len(filtered_results)
            })
        except Exception as e:
            print(f"[SEARCH] ❌ Nominatim fallback also failed: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Location search unavailable: {str(e)}'
            })
    
    except requests.exceptions.RequestException as e:
        print(f"[SEARCH] ❌ API request failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Search service error: {str(e)}'
        })
    except Exception as e:
        print(f"[SEARCH] ❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}'
        })

@app.route('/get_all_nodes')
def get_all_nodes():
    """Return all nodes for display on map"""
    try:
        # Load all nodes using config
        nodes_df = pd.read_csv(Config.NODES_CSV)
        
        # Convert to list of dictionaries for JSON
        nodes_list = []
        for _, row in nodes_df.iterrows():
            nodes_list.append({
                'node_id': int(row['node_id']),
                'lat': float(row['latitude']),
                'lng': float(row['longitude'])
            })
        
        return jsonify({
            'success': True,
            'nodes': nodes_list,
            'count': len(nodes_list)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/get_all_edges')
def get_all_edges():
    """Return all edges for display on map"""
    try:
        # Load edges and nodes using config
        edges_df = pd.read_csv(Config.EDGES_CSV)
        nodes_df = pd.read_csv(Config.NODES_CSV)
        
        # Create node lookup for coordinates
        node_lookup = {}
        for _, row in nodes_df.iterrows():
            node_lookup[int(row['node_id'])] = {
                'lat': float(row['latitude']),
                'lng': float(row['longitude'])
            }
        
        # Process edges
        edges_list = []
        skipped_edges = 0
        
        for _, edge in edges_df.iterrows():
            source_id = int(edge['source'])
            target_id = int(edge['target'])
            
            # Check if both nodes exist in our nodes dataset
            if source_id in node_lookup and target_id in node_lookup:
                edges_list.append({
                    'source_id': source_id,
                    'target_id': target_id,
                    'source_lat': node_lookup[source_id]['lat'],
                    'source_lng': node_lookup[source_id]['lng'],
                    'target_lat': node_lookup[target_id]['lat'],
                    'target_lng': node_lookup[target_id]['lng'],
                    'length': float(edge['length']),
                    'name': str(edge['name']) if pd.notna(edge['name']) else 'Unnamed Road',
                    'highway': str(edge['highway']) if pd.notna(edge['highway']) else 'unclassified'
                })
            else:
                skipped_edges += 1
        
        return jsonify({
            'success': True,
            'edges': edges_list,
            'edges_count': len(edges_list),
            'skipped_edges': skipped_edges,
            'total_edges_in_file': len(edges_df)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/get_scenario_data')
def get_scenario_data():
    """Return scenario data with coordinates and traffic conditions"""
    try:
        # Load scenario data with coordinates using config
        scenario_df = pd.read_csv(Config.DISRUPTIONS_CSV)
        
        # Convert to format suitable for visualization
        edges_with_traffic = []
        
        for _, row in scenario_df.iterrows():
            edges_with_traffic.append({
                'source_id': int(row['source']),
                'target_id': int(row['target']),
                'source_lat': float(row['source_lat']),
                'source_lng': float(row['source_lon']),
                'target_lat': float(row['target_lat']),
                'target_lng': float(row['target_lon']),
                'road_name': str(row['road_name']),
                'speed_kph': float(row['speed_kph']),
                'freeFlow_kph': float(row['freeFlow_kph']),
                'jamFactor': float(row['jamFactor']),
                'isClosed': bool(row['isClosed']),
                'segmentLength': float(row['segmentLength'])
            })
        
        return jsonify({
            'success': True,
            'edges': edges_with_traffic,
            'count': len(edges_with_traffic),
            'description': 'Quezon City traffic scenario with real coordinates and traffic conditions'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/find_nearest_node', methods=['POST'])
def find_nearest_node():
    """
    Find nearest node to clicked coordinates
    
    Enhanced to support one-way street awareness:
    - Pass is_start_point=true for start location selection
    - Pass is_start_point=false for destination selection
    - Omit is_start_point for legacy behavior (no one-way awareness)
    """
    data = request.json
    
    try:
        lat = data['lat']
        lng = data['lng']
        
        # Get optional is_start_point parameter
        is_start_point = data.get('is_start_point', None)
        if is_start_point is not None:
            is_start_point = bool(is_start_point)
        
        # Find nearest node (with or without one-way awareness)
        result = mapper.find_nearest_node(
            lat, lng, 
            max_distance_m=1000,  # Increased range
            is_start_point=is_start_point
        )
        
        # Handle different return formats
        if is_start_point is not None and len(result) == 3:
            node_id, distance, metadata = result
        else:
            node_id, distance = result
            metadata = None
        
        if not node_id:
            error_msg = f'No nodes within 1km. Nearest is {distance:.1f}m away.'
            if metadata:
                error_msg = metadata.get('selection_reason', error_msg)
            
            return jsonify({
                'success': False,
                'error': error_msg
            })
        
        # Get node details using config
        nodes_df = pd.read_csv(Config.NODES_CSV)
        node_data = nodes_df[nodes_df['node_id'] == node_id].iloc[0]
        
        response = {
            'success': True,
            'node_id': int(node_id),
            'lat': float(node_data['latitude']),
            'lng': float(node_data['longitude']),
            'distance_m': round(distance, 1),
            'clicked_lat': lat,
            'clicked_lng': lng
        }
        
        # Add metadata if available (one-way aware selection)
        if metadata:
            response['metadata'] = {
                'accessible': metadata['accessible'],
                'outgoing_edges': metadata['outgoing_count'],
                'incoming_edges': metadata['incoming_count'],
                'selection_reason': metadata['selection_reason'],
                'role': metadata['role']
            }
            
            # Add warning if not accessible
            if not metadata['accessible']:
                response['warning'] = metadata['selection_reason']
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/find_nearest_road_segment', methods=['POST'])
def find_nearest_road_segment():
    """
    Find nearest road segment and project point onto it
    This provides better snap-to-road functionality than find_nearest_node
    """
    data = request.json
    
    try:
        lat = float(data['lat'])
        lng = float(data['lng'])
        max_distance = float(data.get('max_distance', 500))
        
        # Use mapper's snap function
        result = mapper.snap_to_nearest_road(lat, lng, max_distance=max_distance)
        
        if result is None:
            return jsonify({
                'success': False,
                'error': f'No road within {max_distance}m of this location',
                'lat': lat,
                'lng': lng
            })
        
        # Return enhanced result
        return jsonify({
            'success': True,
            'edge': {
                'source': result['edge'][0],
                'target': result['edge'][1]
            },
            'projection_point': result['projection_point'],
            'original_point': result['original_point'],
            'distance_m': round(result['distance_m'], 1),
            'road_name': result['road_name'],
            'segment_length_m': round(result['segment_length_m'], 1),
            'validation': result['validation']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Error finding nearest road segment: {str(e)}"
        })


@app.route('/find_nearest_osm_road', methods=['POST'])
def find_nearest_osm_road():
    """
    Find nearest OSM road using actual road geometries (road-aware snapping).
    
    This endpoint uses the OSM GraphML data to snap points to real road
    geometries rather than just intersection nodes, providing more accurate
    and road-aware location selection.
    
    The system will automatically expand the search radius up to 1000m to
    always find the nearest road (never falls back to node-based selection).
    """
    data = request.json
    
    try:
        lat = float(data['lat'])
        lng = float(data['lng'])
        max_distance = float(data.get('max_distance', 25.0))  # Default 25m initial search
        consider_hierarchy = data.get('consider_hierarchy', True)
        
        # Use mapper's OSM snapping function
        # Note: fallback_to_node parameter is deprecated and ignored
        result = mapper.snap_to_osm_road(
            lat, lng, 
            max_distance_m=max_distance,
            consider_hierarchy=consider_hierarchy
        )
        
        if result is None:
            return jsonify({
                'success': False,
                'error': f'Critical error: Could not find any road even with expanded search',
                'original_point': {'lat': lat, 'lng': lng}
            })
        
        # Prepare metadata without geometry (not JSON serializable)
        metadata = result.get('metadata', {})
        if 'geometry' in metadata:
            del metadata['geometry']
        
        # Return comprehensive result (excluding non-serializable fields)
        return jsonify({
            'success': True,
            'method': result['method'],
            'original_point': result['original_point'],
            'snapped_point': result['snapped_point'],
            'distance_m': round(result['distance_m'], 1),
            'road_name': result['road_name'],
            'highway_type': result['highway_type'],
            'oneway': result['oneway'],
            'osm_nodes': result['osm_nodes'],
            'routing_nodes': result['routing_nodes'],
            'edge_length_m': round(result['edge_length_m'], 1),
            'snap_position': round(result['snap_position'], 3),
            'validation': result['validation'],
            'metadata': metadata
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error finding nearest OSM road: {str(e)}",
            'original_point': {'lat': lat, 'lng': lng}
        })


@app.route('/get_osm_graph_edges', methods=['GET'])
def get_osm_graph_edges():
    """Get all OSM road edges for map visualization"""
    try:
        # Check if OSM road snapper is available
        if not hasattr(mapper, 'osm_snapper') or mapper.osm_snapper is None:
            return jsonify({
                'success': False,
                'error': 'OSM road snapper not initialized'
            })
        
        snapper = mapper.osm_snapper
        edges_data = []
        
        # Get limit from query params (default 500 for performance)
        limit = request.args.get('limit', type=int, default=500)
        max_limit = float('inf')  #2000  # Safety cap
        limit = min(limit, max_limit)
        
        # Extract edge geometries with metadata
        for metadata in snapper.edge_metadata[:limit]:
            try:
                geom = metadata['geometry']
                coords = [(lat, lng) for lng, lat in geom.coords]  # Convert to lat/lng
                
                edges_data.append({
                    'coordinates': coords,
                    'u': int(metadata['u']),
                    'v': int(metadata['v']),
                    'name': metadata.get('name', 'Unnamed Road'),
                    'highway': metadata.get('highway', 'unknown'),
                    'oneway': metadata.get('oneway', 0),
                    'length': round(metadata.get('length', 0), 2)
                })
            except Exception as e:
                # Skip edges with invalid geometry
                continue
        
        return jsonify({
            'success': True,
            'edges': edges_data,
            'count': len(edges_data),
            'total_edges': len(snapper.edge_metadata),
            'message': f'Showing {len(edges_data)} of {len(snapper.edge_metadata)} total edges (limit: {limit})'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error getting OSM graph edges: {str(e)}"
        })


@app.route('/compute_dhc2l_route', methods=['POST'])
def compute_dhc2l_route():
    """Compute optimal route using GPS HC2L (Hierarchical Cut Labelling) algorithm"""
    data = request.json
    
    try:
        if gps_router is None:
            return jsonify({
                'success': False,
                'error': 'GPS HC2L Router not initialized properly'
            })
        
        # Extract pin coordinates (original user click points)
        start_pin_lat = float(data['start_lat'])
        start_pin_lng = float(data['start_lng'])
        dest_pin_lat = float(data['dest_lat'])
        dest_pin_lng = float(data['dest_lng'])
        tau_threshold = float(data['tau_threshold']) if 'tau_threshold' in data else 0.5
        
        # Check if OSM edge-based routing should be used (snap point data)
        start_osm_edge = data.get('start_osm_edge')
        dest_osm_edge = data.get('dest_osm_edge')
        
        # Default to pin coordinates if no snap info
        start_snap_lat = start_pin_lat
        start_snap_lng = start_pin_lng
        dest_snap_lat = dest_pin_lat
        dest_snap_lng = dest_pin_lng
        
        # Default edge information (will be overridden if snap data available)
        start_edge_source = 0
        start_edge_target = 0
        start_edge_oneway = 0
        dest_edge_source = 0
        dest_edge_target = 0
        dest_edge_oneway = 0
        
        # Extract snap point and edge information from OSM snap result
        if start_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in start_osm_edge:
                start_snap_lat = float(start_osm_edge['snapped_point']['lat'])
                start_snap_lng = float(start_osm_edge['snapped_point']['lng'])
            
            # Get edge information (CRITICAL: tells us which road the snap is on)
            if 'osm_nodes' in start_osm_edge and len(start_osm_edge['osm_nodes']) >= 2:
                start_edge_source = int(start_osm_edge['osm_nodes'][0])
                start_edge_target = int(start_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = start_osm_edge.get('oneway', '0')
            try:
                start_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                start_edge_oneway = 0
            
            print(f"🗺️  Start snap: {start_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {start_edge_source}→{start_edge_target}, oneway={start_edge_oneway})")
        
        if dest_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in dest_osm_edge:
                dest_snap_lat = float(dest_osm_edge['snapped_point']['lat'])
                dest_snap_lng = float(dest_osm_edge['snapped_point']['lng'])
            
            # Get edge information
            if 'osm_nodes' in dest_osm_edge and len(dest_osm_edge['osm_nodes']) >= 2:
                dest_edge_source = int(dest_osm_edge['osm_nodes'][0])
                dest_edge_target = int(dest_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = dest_osm_edge.get('oneway', '0')
            try:
                dest_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                dest_edge_oneway = 0
            
            print(f"🗺️  Dest snap: {dest_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {dest_edge_source}→{dest_edge_target}, oneway={dest_edge_oneway})")
        
        # LazyHC2L: Extract optional disruption parameters
        # disruption_file: path to .gr disruption file (optional)
        # tau_threshold: threshold for lazy vs immediate update (default 0.5)
        disruption_file = data.get('disruption_file', '')
        dataset_mode = data.get('dataset_mode', None)  # Get dataset mode from request
        generate_alternatives = data.get('generate_alternatives', True)  # NEW: Control alternative route generation
        
        # If no disruption file specified, use dynamic disruptions based on dataset mode
        if not disruption_file:
            disruption_file = get_dynamic_disruption_file('hc2l', dataset_mode)
                
        print(f"Computing GPS HC2L route with snap points:")
        print(f"  Start: Pin({start_pin_lat}, {start_pin_lng}) → Snap({start_snap_lat}, {start_snap_lng})")
        print(f"  Dest:  Pin({dest_pin_lat}, {dest_pin_lng}) → Snap({dest_snap_lat}, {dest_snap_lng})")
        print(f"  Dataset mode: {dataset_mode if dataset_mode else 'auto'}")
        print(f"  Disruption file: {disruption_file if disruption_file else '(none)'}")
        print(f"  Tau threshold: {tau_threshold}")
        print(f"  Generate alternatives: {generate_alternatives}")
        
        # Compute route using GPS HC2L with LazyHC2L parameters
        start_time = time.time()
        route_result = gps_router.compute_route(
            start_pin_lat, start_pin_lng,
            dest_pin_lat, dest_pin_lng,
            start_snap_lat, start_snap_lng,
            dest_snap_lat, dest_snap_lng,
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway,
            disruption_file, tau_threshold, generate_alternatives  # Pass disruption_file, tau_threshold, and generate_alternatives
        )
        computation_time = time.time() - start_time
        
        if not route_result['success']:
            return jsonify({
                'success': False,
                'error': route_result['error'],
                'debug_info': route_result.get('raw_output', '')
            })
        
        # Get polylines for Google Maps
        polylines = gps_router.get_route_polylines_for_gmaps(route_result)
        
        # Get route summary
        summary = gps_router.get_route_summary(route_result)
        summary['total_computation_time_sec'] = round(computation_time, 3)
        
        # Get the full metrics from C++ output
        cpp_metrics = route_result.get('metrics', {})
        
        # Merge summary into cpp_metrics (keeping all C++ fields, adding Python-calculated fields)
        full_metrics = {**cpp_metrics, **summary}
        
        # # Debug: Print labeling metrics
        # print(f"Route Summary Metrics:")
        # print(f"Labeling size: {summary.get('labeling_size_mb', 'N/A')} MB")
        # print(f"Labeling time: {summary.get('labeling_time_ms', 'N/A')} s")

        # Debug: Print the route structure
        # print(f"Route result structure: {list(route_result.get('route', {}).keys())}")
        if 'turn_by_turn_directions' in route_result.get('route', {}):
            directions = route_result['route']['turn_by_turn_directions']
            # print(f"Turn-by-turn directions ({len(directions)} steps): {directions[:3]}...")  # First 3 steps
        
        # Debug: Check HC2L geometry
        hc2l_geometry = route_result.get('route', {}).get('geometry', [])
        print(f"🔍 HC2L geometry in Flask: {len(hc2l_geometry)} segments")
        if hc2l_geometry:
            print(f"🔍 HC2L First segment keys: {list(hc2l_geometry[0].keys()) if hc2l_geometry else 'No segments'}")
        
        # Extract disruption_analysis from C++ output
        disruption_analysis = route_result.get('disruption_analysis', {})
        if disruption_analysis:
            print(f"🔍 Disruption analysis detected: {disruption_analysis.get('route_disruptions', {}).get('total_count', 0)} disruptions")
        
        # Enhance alternative routes with geometry (only if requested)
        if generate_alternatives:
            enhanced_alt_routes = enhance_alternative_routes_with_geometry(route_result.get('alternative_routes', []))
        else:
            enhanced_alt_routes = []
            print(f"⏭️  Alternative routes generation skipped (generate_alternatives=False)")
        
        return jsonify({
            'success': True,
            'route': {
                'polylines': polylines,
                'start_point': {'lat': start_snap_lat, 'lng': start_snap_lng},
                'end_point': {'lat': dest_snap_lat, 'lng': dest_snap_lng},
                'pin_start': {'lat': start_pin_lat, 'lng': start_pin_lng},
                'pin_end': {'lat': dest_pin_lat, 'lng': dest_pin_lng},
                'coordinates': route_result.get('route', {}).get('coordinates', []),
                'path_nodes': route_result.get('route', {}).get('path_nodes', []),
                'road_segments': route_result.get('route', {}).get('road_segments', []),
                'route_summary': route_result.get('route', {}).get('route_summary', ''),
                'turn_by_turn_directions': route_result.get('route', {}).get('turn_by_turn_directions', []),
                'display_format': route_result.get('route', {}).get('display_format', {}),
                'geometry': route_result.get('route', {}).get('geometry', [])  # Edge details with distance, highway type, speeds, traffic status
            },
            'metrics': full_metrics,  # Use full_metrics with all C++ fields
            'disruption_analysis': disruption_analysis,  # Pass disruption analysis from C++ to frontend
            'disruptions_summary': route_result.get('disruptions_summary', {}),  # Also pass disruptions_summary for additional details
            'alternative_routes': enhanced_alt_routes,  # Pass enhanced alternative routes (or empty if not requested)
            'lazy_hc2l': route_result.get('lazy_hc2l', {}),  # Pass LazyHC2L update strategy info
            'disruption_config': route_result.get('disruption_config', {}),  # Pass disruption configuration
            'algorithm': summary.get('algorithm', 'D-HC2L Dynamic'),  # Use algorithm from summary
            'algorithm_base': summary.get('algorithm_base', 'D-HC2L'),
            'routing_mode': summary.get('routing_mode', 'BASE'),
            'update_strategy': summary.get('update_strategy', 'none'),
            'mode_explanation': summary.get('mode_explanation', ''),
            'labels_status': summary.get('labels_status', 'original'),
            'gps_mapping': route_result.get('gps_mapping', {}),
            'snap_edges': route_result.get('snap_edges', {}),
            'raw_output': route_result.get('raw_output', '')
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Route computation error: {str(e)}"
        })


@app.route('/compare_routes', methods=['POST'])
def compare_routes():
    """Compare GPS HC2L base route with disrupted route"""
    data = request.json
    
    try:
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        threshold = float(data.get('threshold', 0.5))
        
        # Use the GPS router's built-in comparison function
        comparison_result = gps_router.compare_routes(start_lat, start_lng, dest_lat, dest_lng, threshold)

        if not comparison_result['success']:
            return jsonify({
                'success': False,
                'error': comparison_result['error']
            })
        
        # Add straight line for additional comparison
        straight_line = [{
            'path': [
                {'lat': start_lat, 'lng': start_lng},
                {'lat': dest_lat, 'lng': dest_lng}
            ],
            'strokeColor': '#00FF00',  # Green
            'strokeOpacity': 0.5,
            'strokeWeight': 2,
            'geodesic': True
        }]
        
        comparison_result['routes']['straight_line'] = {
            'polylines': straight_line,
            'name': 'Straight Line',
            'color': '#00FF00'
        }
        
        comparison_result['start_point'] = {'lat': start_lat, 'lng': start_lng}
        comparison_result['end_point'] = {'lat': dest_lat, 'lng': dest_lng}
        
        return jsonify(comparison_result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Route comparison error: {str(e)}"
        })


@app.route('/get_active_disruptions')
def get_active_disruptions():
    """
    Get all active disruptions from HERE API data using hash-based matching
    Maps HERE traffic data to actual road network edges using pre-matched edges
    """
    try:
        # Use the hash-based traffic matcher (already initialized in traffic_service)
        from config import Config
        from traffic_hash_matcher import TrafficHashMatcher
        
        # Initialize hash matcher with pre-matched edges
        print("🚀 Initializing TrafficHashMatcher for traffic overlay...")
        matcher = traffic_service.matcher
        
        disruptions_by_type = {}
        total_disruptions = 0
        matched_edges_count = 0
        
        # ============================================================
        # FETCH INCIDENTS (primary data source for incident types)
        # ============================================================
        incidents = traffic_service.fetch_incidents_data()
        
        print(f"\n📊 Processing {len(incidents)} HERE Traffic incidents with hash-based matching...")
        
        for incident in incidents:
            try:
                # Extract HERE API fields directly
                incident_details = incident.get('incidentDetails', {})
                incident_type = incident_details.get('type', 'other')
                criticality = incident_details.get('criticality', 'low')
                road_closed = incident_details.get('roadClosed', False)
                
                # Match incident to edges using hash-based matcher
                matched_edges = matcher.match_traffic_incident_item(incident)
                
                if not matched_edges:
                    print(f"   ⚠️  No edges matched for incident: {incident_type}")
                    continue
                
                matched_edges_count += len(matched_edges)
                
                # Map HERE incident types to our display types
                type_map = {
                    'accident': 'Accident',
                    'construction': 'Construction',
                    'congestion': 'Congestion',
                    'disabledVehicle': 'Disabled Vehicle',
                    'massTransit': 'Mass Transit Event',
                    'plannedEvent': 'Planned Event',
                    'roadHazard': 'Road Hazard',
                    'roadClosure': 'Road Closure',
                    'weather': 'Weather',
                    'laneRestriction': 'Lane Restriction',
                    'other': 'Other'
                }
                
                # Map HERE criticality to our severity
                criticality_map = {
                    'low': 'Light',
                    'minor': 'Light',
                    'major': 'Medium',
                    'critical': 'Heavy'
                }
                
                display_type = type_map.get(incident_type, 'Other')
                severity = criticality_map.get(criticality, 'Light')
                
                # Calculate jam factor based on HERE data
                if road_closed or incident_type == 'roadClosure':
                    jam_factor = 10.0
                elif criticality == 'critical':
                    jam_factor = 8.0
                elif criticality == 'major':
                    jam_factor = 6.0
                elif criticality == 'minor':
                    jam_factor = 4.0
                else:
                    jam_factor = 2.0
                
                # Calculate speed reduction
                if road_closed or incident_type == 'roadClosure':
                    speed_reduction = 1.0
                    current_speed_kph = 0
                else:
                    speed_reduction = 1.0 - (jam_factor / 10.0)
                    current_speed_kph = 50 * (1 - speed_reduction)
                
                # Create disruption entries for each matched edge (TrafficEdge objects)
                for edge in matched_edges:
                    disruption = {
                        'source_id': edge.source,
                        'target_id': edge.target,
                        'source_lat': edge.source_lat,
                        'source_lng': edge.source_lon,
                        'target_lat': edge.target_lat,
                        'target_lng': edge.target_lon,
                        'road_name': incident_details.get('description', {}).get('value', 'Unknown Road'),
                        'incident_type': display_type,
                        'severity': severity,
                        'speed_kph': edge.speed_kph,
                        'free_flow_kph': edge.freeFlow_kph,
                        'jam_factor': edge.jamFactor,
                        'is_closed': edge.isClosed,
                        'slowdown_ratio': round(1.0 - speed_reduction, 3),
                        'criticality': criticality,
                        'here_type': incident_type,
                        'start_time': incident_details.get('startTime', ''),
                        'end_time': incident_details.get('endTime', '')
                    }
                    
                    # Group by incident type
                    if display_type not in disruptions_by_type:
                        disruptions_by_type[display_type] = []
                    disruptions_by_type[display_type].append(disruption)
                    total_disruptions += 1
                
                print(f"   ✅ {display_type} ({severity}) matched to {len(matched_edges)} edges")
                    
            except Exception as e:
                print(f"   ⚠️  Error processing incident: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # ============================================================
        # FETCH FLOW DATA (congestion/traffic conditions)
        # ============================================================
        flow_data = traffic_service.fetch_flow_data()
        
        print(f"\n📊 Processing {len(flow_data)} HERE Traffic flow segments...")
        
        for flow in flow_data:
            try:
                current_flow = flow.get('currentFlow', {})
                free_flow = flow.get('freeFlow', {})
                jam_factor = float(current_flow.get('jamFactor', 0.0))
                speed = float(current_flow.get('speed', 0.0))
                free_flow_speed = float(free_flow.get('speed', 50.0))
                confidence = float(current_flow.get('confidence', 0.0))
                
                # Skip if no significant congestion
                if jam_factor < 2.0:
                    continue
                
                # Match flow segment to edges using hash-based matcher
                matched_edges = matcher.match_traffic_flow_item(flow)
                
                if not matched_edges:
                    continue  # Skip silently for flow - too many segments
                
                matched_edges_count += len(matched_edges)
                
                # Map jam factor to severity
                if jam_factor >= 8.0:
                    severity = 'Heavy'
                elif jam_factor >= 5.0:
                    severity = 'Medium'
                else:
                    severity = 'Light'
                
                # Create disruption entries for each matched edge (TrafficEdge objects)
                for edge in matched_edges:
                    # Create disruption entry for flow
                    disruption = {
                        'source_id': edge.source,
                        'target_id': edge.target,
                        'source_lat': edge.source_lat,
                        'source_lng': edge.source_lon,
                        'target_lat': edge.target_lat,
                        'target_lng': edge.target_lon,
                        'road_name': flow.get('location', {}).get('description', 'Traffic Congestion'),
                        'incident_type': 'Congestion',
                        'severity': severity,
                        'speed_kph': edge.speed_kph,
                        'free_flow_kph': edge.freeFlow_kph,
                        'jam_factor': edge.jamFactor,
                        'is_closed': edge.isClosed,
                        'slowdown_ratio': round(max(0, 1.0 - (speed / free_flow_speed if free_flow_speed > 0 else 1)), 3),
                        'confidence': confidence,
                        'here_type': 'flow'
                    }
                    
                    # Group congestion separately
                    if 'Congestion' not in disruptions_by_type:
                        disruptions_by_type['Congestion'] = []
                    disruptions_by_type['Congestion'].append(disruption)
                    total_disruptions += 1
                
            except Exception as e:
                # Silently skip problematic flow items - there are many
                continue
        
        # Calculate statistics
        type_counts = {incident_type: len(disruptions) for incident_type, disruptions in disruptions_by_type.items()}
        severity_counts = {'Heavy': 0, 'Medium': 0, 'Light': 0}
        
        for disruptions in disruptions_by_type.values():
            for disruption in disruptions:
                severity_counts[disruption['severity']] += 1
        
        print(f"\n📈 Summary:")
        print(f"   Total disruptions: {total_disruptions}")
        print(f"   Matched edges: {matched_edges_count}")
        print(f"   By type: {type_counts}")
        print(f"   By severity: {severity_counts}")
        
        return jsonify({
            'success': True,
            'total_disruptions': total_disruptions,
            'matched_edges_count': matched_edges_count,
            'disruptions_by_type': disruptions_by_type,
            'type_counts': type_counts,
            'severity_counts': severity_counts,
            'timestamp': time.time(),
            'note': 'Using HERE API with hash-based edge matching - pre-matched edges from CSV'
        })
        
    except Exception as e:
        print(f"❌ Error in get_active_disruptions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error loading disruptions: {str(e)}"
        })


@app.route('/get_raw_here_traffic')
def get_raw_here_traffic():
    """
    Get raw HERE API traffic data (non-matched to OSM edges)
    Returns original HERE flow segments and incidents with their geometries
    """
    try:
        here_service = traffic_service
        
        raw_traffic = {
            'flow_segments': [],
            'incidents': []
        }
        
        # Fetch flow data
        flow_data = traffic_service.fetch_flow_data()
        print(f"📊 Fetching {len(flow_data)} raw HERE flow segments...")
        
        for flow in flow_data:
            try:
                current_flow = flow.get('currentFlow', {})
                jam_factor = float(current_flow.get('jamFactor', 0.0))
                speed = float(current_flow.get('speed', 0.0))
                free_flow_speed = float(current_flow.get('freeFlowSpeed', 50.0))
                confidence = float(current_flow.get('confidence', 0.0))
                
                # Extract location/shape data
                location = flow.get('location', {})
                shape = location.get('shape', {})
                links = shape.get('links', [])
                
                # Parse coordinates from shape
                coordinates = []
                for link in links:
                    points = link.get('points', [])
                    for point in points:
                        lat = point.get('lat', 0)
                        lng = point.get('lng', 0)
                        if lat and lng:
                            coordinates.append([lat, lng])
                
                if not coordinates:
                    continue
                
                # Map jam factor to severity
                if jam_factor >= 8.0:
                    severity = 'Heavy'
                elif jam_factor >= 5.0:
                    severity = 'Medium'
                else:
                    severity = 'Light'
                
                raw_traffic['flow_segments'].append({
                    'coordinates': coordinates,
                    'jam_factor': jam_factor,
                    'speed_kph': speed * 3.6,  # m/s to km/h
                    'free_flow_kph': free_flow_speed * 3.6,
                    'severity': severity,
                    'confidence': confidence,
                    'type': 'flow',
                    'description': location.get('description', 'Traffic Flow')
                })
                
            except Exception as e:
                continue
        
        # Fetch incidents
        incidents = traffic_service.fetch_incidents_data()
        print(f"📊 Fetching {len(incidents)} raw HERE incidents...")
        
        for incident in incidents:
            try:
                incident_details = incident.get('incidentDetails', {})
                incident_type = incident_details.get('type', 'other')
                criticality = incident_details.get('criticality', 'low')
                road_closed = incident_details.get('roadClosed', False)
                
                location = incident.get('location', {})
                shape = location.get('shape', {})
                links = shape.get('links', [])
                
                # Parse coordinates from shape
                coordinates = []
                for link in links:
                    points = link.get('points', [])
                    for point in points:
                        lat = point.get('lat', 0)
                        lng = point.get('lng', 0)
                        if lat and lng:
                            coordinates.append([lat, lng])
                
                if not coordinates:
                    continue
                
                # Map criticality to severity
                criticality_map = {
                    'low': 'Light',
                    'minor': 'Light',
                    'major': 'Medium',
                    'critical': 'Heavy'
                }
                
                severity = criticality_map.get(criticality, 'Light')
                
                raw_traffic['incidents'].append({
                    'coordinates': coordinates,
                    'type': incident_type,
                    'severity': severity,
                    'criticality': criticality,
                    'road_closed': road_closed,
                    'description': incident_details.get('description', {}).get('value', 'Incident'),
                    'start_time': incident_details.get('startTime', ''),
                    'end_time': incident_details.get('endTime', '')
                })
                
            except Exception as e:
                continue
        
        print(f"✅ Returning {len(raw_traffic['flow_segments'])} flow segments and {len(raw_traffic['incidents'])} incidents")
        
        return jsonify({
            'success': True,
            'data': raw_traffic,
            'total_flow': len(raw_traffic['flow_segments']),
            'total_incidents': len(raw_traffic['incidents'])
        })
        
    except Exception as e:
        print(f"❌ Error in get_raw_here_traffic: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error loading raw traffic: {str(e)}"
        })


@app.route('/get_traffic_with_geometry')
def get_traffic_with_geometry():
    """
    Get traffic data with full OSM road geometries (CACHED VERSION)
    Returns matched traffic edges with their LineString geometries from quezon_city_edges.csv
    Uses intelligent caching to avoid reloading data on every request
    """
    try:
        # Load edges with cache (only reloads if file changed)
        edges_df, edge_lookup = load_edges_with_cache()
        
        if edge_lookup is None:
            return jsonify({
                'success': False,
                'error': 'Failed to load OSM edges'
            })
        
        # Load traffic data with cache (only reloads if traffic file changed)
        traffic_segments = load_traffic_with_cache(edge_lookup)
        
        return jsonify({
            'success': True,
            'segments': traffic_segments,
            'total_segments': len(traffic_segments),
            'cached': {
                'edges_loaded_at': _edges_cache['loaded_at'],
                'traffic_loaded_at': _traffic_cache['loaded_at']
            }
        })
        
    except Exception as e:
        print(f"❌ Error in get_traffic_with_geometry: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error loading traffic: {str(e)}"
        })


@app.route('/compute_dhl_route', methods=['POST'])
def compute_dhl_route():
    """Compute optimal route using DHL algorithm"""
    data = request.json
    
    try:
        if dhl_router is None:
            return jsonify({
                'success': False,
                'error': 'DHL Router not initialized properly'
            })
        
        # Extract pin coordinates (original user click points)
        start_pin_lat = float(data['start_lat'])
        start_pin_lng = float(data['start_lng'])
        dest_pin_lat = float(data['dest_lat'])
        dest_pin_lng = float(data['dest_lng'])
        
        # Check if OSM edge-based routing should be used (snap point data)
        start_osm_edge = data.get('start_osm_edge')
        dest_osm_edge = data.get('dest_osm_edge')
        
        # Default to pin coordinates if no snap info
        start_snap_lat = start_pin_lat
        start_snap_lng = start_pin_lng
        dest_snap_lat = dest_pin_lat
        dest_snap_lng = dest_pin_lng
        
        # Default edge information (will be overridden if snap data available)
        start_edge_source = 0
        start_edge_target = 0
        start_edge_oneway = 0
        dest_edge_source = 0
        dest_edge_target = 0
        dest_edge_oneway = 0
        
        # Extract snap point and edge information from OSM snap result
        if start_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in start_osm_edge:
                start_snap_lat = float(start_osm_edge['snapped_point']['lat'])
                start_snap_lng = float(start_osm_edge['snapped_point']['lng'])
            
            # Get edge information (CRITICAL: tells us which road the snap is on)
            if 'osm_nodes' in start_osm_edge and len(start_osm_edge['osm_nodes']) >= 2:
                start_edge_source = int(start_osm_edge['osm_nodes'][0])
                start_edge_target = int(start_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = start_osm_edge.get('oneway', '0')
            try:
                start_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                start_edge_oneway = 0
            
            print(f"🗺️  Start snap (DHL): {start_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {start_edge_source}→{start_edge_target}, oneway={start_edge_oneway})")
        
        if dest_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in dest_osm_edge:
                dest_snap_lat = float(dest_osm_edge['snapped_point']['lat'])
                dest_snap_lng = float(dest_osm_edge['snapped_point']['lng'])
            
            # Get edge information
            if 'osm_nodes' in dest_osm_edge and len(dest_osm_edge['osm_nodes']) >= 2:
                dest_edge_source = int(dest_osm_edge['osm_nodes'][0])
                dest_edge_target = int(dest_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = dest_osm_edge.get('oneway', '0')
            try:
                dest_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                dest_edge_oneway = 0
            
            print(f"🗺️  Dest snap (DHL): {dest_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {dest_edge_source}→{dest_edge_target}, oneway={dest_edge_oneway})")
        
        # Check if disruptions should be used
        use_disruptions = data.get('use_disruptions', False)
        dataset_mode = data.get('dataset_mode', None)  # Get dataset mode from request
        
        # DHL: Convert use_disruptions to actual disruption file path
        # If disruption_file is explicitly provided, use it
        # Otherwise, if use_disruptions is True or dataset_mode is provided, use appropriate file
        disruption_file = data.get('disruption_file', '')
        
        # Handle different ways disruptions can be specified
        if not disruption_file or disruption_file in ['', 'null', 'NULL']:
            # If use_disruptions is True or dataset_mode is set, use appropriate disruption file
            if use_disruptions or dataset_mode:
                # Get the file based on dataset mode (incidents/flow/both)
                disruption_file = get_dynamic_disruption_file('dhl', dataset_mode)
                
                # If no dynamic file and use_disruptions is True, fall back to static file
                if not disruption_file and use_disruptions:
                    disruption_gr = Config.PROCESSED_DATA_DIR / 'qc_disrupted_scenario_1.gr'
                    if disruption_gr.exists():
                        disruption_file = str(disruption_gr)
                        print(f"📍 Using static disruption file: {disruption_file}")
                    else:
                        print(f"⚠️  No disruption file found")
                        disruption_file = ''
            else:
                disruption_file = ''
        elif disruption_file == 'active_disruptions':
            # Frontend sent 'active_disruptions' - use dynamic disruptions based on mode
            disruption_file = get_dynamic_disruption_file('dhl', dataset_mode)
            if not disruption_file:
                # Fall back to static
                disruption_gr = Config.PROCESSED_DATA_DIR / 'qc_disrupted_scenario_1.gr'
                if disruption_gr.exists():
                    disruption_file = str(disruption_gr)
                    print(f"📍 Using static disruption file: {disruption_file}")
                else:
                    print(f"⚠️  No disruption file found")
                    disruption_file = ''
        
        tau_threshold = float(data.get('tau_threshold', 0.5))
        generate_alternatives = data.get('generate_alternatives', True)  # Default: True (generate alternatives)
        
        print(f"Computing DHL route with snap points:")
        print(f"  Start: Pin({start_pin_lat}, {start_pin_lng}) → Snap({start_snap_lat}, {start_snap_lng})")
        print(f"  Dest:  Pin({dest_pin_lat}, {dest_pin_lng}) → Snap({dest_snap_lat}, {dest_snap_lng})")
        print(f"  Dataset mode: {dataset_mode if dataset_mode else 'auto'}")
        print(f"  Disruption file: {disruption_file if disruption_file else '(none)'}")
        print(f"  Tau threshold: {tau_threshold}")
        print(f"  Generate alternatives: {generate_alternatives}")
        
        # Compute route using DHL with disruption parameters
        start_time = time.time()
        route_result = dhl_router.compute_route(
            start_pin_lat, start_pin_lng,
            dest_pin_lat, dest_pin_lng,
            start_snap_lat, start_snap_lng,
            dest_snap_lat, dest_snap_lng,
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway,
            disruption_file, tau_threshold, generate_alternatives  # Pass disruption_file, tau_threshold, and generate_alternatives
        )
        computation_time = time.time() - start_time
        
        if not route_result['success']:
            return jsonify({
                'success': False,
                'error': route_result['error'],
                'debug_info': route_result.get('raw_output', '')
            })
        
        # Get polylines for Google Maps
        polylines = dhl_router.get_route_polylines_for_gmaps(route_result)
        
        # Get route summary
        summary = dhl_router.get_route_summary(route_result)
        summary['total_computation_time_sec'] = round(computation_time, 3)
        
        # Get the full metrics from C++ output
        cpp_metrics = route_result.get('metrics', {})
        
        # Merge summary into cpp_metrics (keeping all C++ fields, adding Python-calculated fields)
        full_metrics = {**cpp_metrics, **summary}
        
        # Get enhanced road name information using the new methods
        turn_by_turn_directions = dhl_router.get_turn_by_turn_directions(route_result)
        route_summary_text = dhl_router.get_route_summary_text(route_result)
        detailed_route_info = dhl_router.get_detailed_route_info(route_result)
        
        # Extract disruption_analysis from C++ output
        disruption_analysis = route_result.get('disruption_analysis', {})
        if disruption_analysis:
            print(f"🔍 DHL Disruption analysis detected: {disruption_analysis.get('route_disruptions', {}).get('total_count', 0)} disruptions")
        
        # Enhance alternative routes with geometry (only if requested)
        if generate_alternatives:
            enhanced_alt_routes = enhance_alternative_routes_with_geometry(route_result.get('alternative_routes', []))
        else:
            enhanced_alt_routes = []
            print(f"⏭️  Alternative routes generation skipped (generate_alternatives=False)")
        
        return jsonify({
            'success': True,
            'route': {
                'polylines': polylines,
                'geometry': route_result.get('route', {}).get('geometry', []),  # Add C++ geometry with edge details
                'start_point': {'lat': start_snap_lat, 'lng': start_snap_lng},
                'end_point': {'lat': dest_snap_lat, 'lng': dest_snap_lng},
                'pin_start': {'lat': start_pin_lat, 'lng': start_pin_lng},
                'pin_end': {'lat': dest_pin_lat, 'lng': dest_pin_lng},
                'coordinates': route_result.get('route', {}).get('coordinates', []),
                'path_nodes': route_result.get('route', {}).get('path_nodes', []),
                'road_segments': route_result.get('route', {}).get('road_segments', []),
                'route_summary': route_summary_text, 
                'route_summary_detailed': route_result.get('route', {}).get('route_summary', ''),  # Original trace
                'turn_by_turn_directions': turn_by_turn_directions,
                'display_format': route_result.get('route', {}).get('display_format', {}),
                'detailed_info': detailed_route_info
            },
            'metrics': full_metrics,  # Use full_metrics with all C++ fields
            'disruption_analysis': disruption_analysis,  # Pass disruption analysis from C++ to frontend
            'disruptions_summary': route_result.get('disruptions_summary', {}),  # Also pass disruptions_summary for additional details
            'alternative_routes': enhanced_alt_routes,  # Pass enhanced alternative routes (or empty if not requested)
            'dhl_update_info': route_result.get('dhl_update_info', {}),  # Pass DHL update strategy info
            'disruption_config': route_result.get('disruption_config', {}),  # Pass disruption configuration
            'algorithm': 'DHL (Dual-Hierarchy Labelling)',
            'gps_mapping': route_result.get('gps_mapping', {}),
            'snap_edges': route_result.get('snap_edges', {}),
            'disruptions': route_result.get('disruptions', {}),
            'raw_dhl_output': route_result.get('raw_dhl_output', {})
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"DHL route computation error: {str(e)}"
        })


@app.route('/compare_dhl_routes', methods=['POST'])
def compare_dhl_routes():
    """Compare DHL base route with disrupted route"""
    data = request.json
    
    try:
        if dhl_router is None:
            return jsonify({
                'success': False,
                'error': 'DHL Router not initialized properly'
            })
        
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        
        # Use the DHL router's built-in comparison function
        comparison_result = dhl_router.compare_routes(start_lat, start_lng, dest_lat, dest_lng)
        
        if not comparison_result['success']:
            return jsonify({
                'success': False,
                'error': comparison_result['error']
            })
        
        # Enhance the comparison result with detailed road name information
        if 'routes' in comparison_result:
            for route_type in ['base', 'disrupted']:
                if route_type in comparison_result['routes']:
                    route_data = comparison_result['routes'][route_type]
                    
                    # Create a mock route result to use with our new methods
                    mock_route_result = {
                        'success': True,
                        'route': {
                            'path_nodes': route_data.get('summary', {}).get('path_nodes', []),
                            'road_segments': route_data.get('road_segments', []),
                            'turn_by_turn_directions': route_data.get('turn_by_turn_directions', []),
                            'route_summary': route_data.get('route_summary', ''),
                            'display_format': route_data.get('display_format', {})
                        }
                    }
                    
                    # Add enhanced information if path nodes are available
                    if route_data.get('summary', {}).get('path_nodes'):
                        enhanced_summary = dhl_router.get_route_summary_text(mock_route_result)
                        enhanced_directions = dhl_router.get_turn_by_turn_directions(mock_route_result)
                        enhanced_details = dhl_router.get_detailed_route_info(mock_route_result)
                        
                        # Add enhanced data to the route
                        route_data['enhanced_summary'] = enhanced_summary
                        route_data['enhanced_directions'] = enhanced_directions
                        route_data['enhanced_details'] = enhanced_details
                        
                        print(f"🛣️  Enhanced {route_type} route: {enhanced_summary}")
        
        # Add straight line for additional comparison
        straight_line = [{
            'path': [
                {'lat': start_lat, 'lng': start_lng},
                {'lat': dest_lat, 'lng': dest_lng}
            ],
            'strokeColor': '#00FF00',  # Green
            'strokeOpacity': 0.5,
            'strokeWeight': 2,
            'geodesic': True
        }]
        
        comparison_result['routes']['straight_line'] = {
            'polylines': straight_line,
            'name': 'Straight Line',
            'color': '#00FF00'
        }
        
        comparison_result['start_point'] = {'lat': start_lat, 'lng': start_lng}
        comparison_result['end_point'] = {'lat': dest_lat, 'lng': dest_lng}
        
        return jsonify(comparison_result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"DHL route comparison error: {str(e)}"
        })


@app.route('/compare_algorithms', methods=['POST'])
def compare_algorithms():
    """
    DEPRECATED: Compare HC2L and DHL algorithms side by side
    
    This endpoint is deprecated. The new routing flow uses individual algorithm
    endpoints (/compute_gps_hc2l_route and /compute_dhl_route) with proper OSM
    snapping and doesn't require this comparison endpoint.
    
    Kept for backward compatibility but may return errors due to API changes.
    """
    return jsonify({
        'success': False,
        'error': 'This endpoint is deprecated. Please use the individual algorithm endpoints with OSM snapping.',
        'alternative': 'Use /compute_gps_hc2l_route and /compute_dhl_route separately with proper snap point data'
    }), 410  # 410 Gone status code


@app.route('/compare_with_google_maps', methods=['POST'])
def compare_with_google_maps():
    """
    Compare current algorithm route with Google Maps route
    
    IMPORTANT: This function uses the CURRENT ROUTE already calculated on frontend.
    No route recalculation is needed - we just compare the existing route.
    
    Frontend sends:
    - start_lat, start_lng, dest_lat, dest_lng: Origin/destination coordinates
    - algorithm: Algorithm name used (HC2L, DHC2L, DHL, etc)
    - existing_route_geometry: Current route geometry from the calculated route
    
    Steps:
    1. Extract algorithm route coordinates from the passed geometry
    2. Fetch Google Maps route for the same origin/destination
    3. Calculate Fréchet distance and overlap metrics
    4. Return both routes for map display (no recalculation!)
    """
    data = request.json
    
    try:
        # Validate required input parameters
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        algorithm_name = data.get('algorithm', 'Unknown Algorithm')
        
        print(f"\n🗺️  === GOOGLE MAPS COMPARISON (Dynamic) ===")
        print(f"   Algorithm: {algorithm_name}")
        print(f"   Route: ({start_lat}, {start_lng}) → ({dest_lat}, {dest_lng})")
        print(f"   Using existing route data (no recalculation)")
        
        # Validate Google Maps service is initialized
        if not gmaps_service:
            print(f"   ❌ Google Maps service not initialized")
            return jsonify({
                'success': False,
                'error': 'Google Maps service not initialized. Check API key in .env'
            })
        
        # ============================================================
        # STEP 1: Extract algorithm route coordinates from passed geometry
        # ============================================================
        print(f"\n📍 Step 1: Extract current algorithm route coordinates")
        
        algorithm_coords = []
        existing_geometry = data.get('existing_route_geometry')
        print(f"   Received geometry type: {type(existing_geometry)}")
        
        if not existing_geometry:
            print(f"   ❌ No route geometry provided")
            return jsonify({
                'success': False,
                'error': 'No route geometry found. Please calculate a route first.'
            })
        
        # Debug: print raw geometry
        print(f"   Raw geometry (first 200 chars): {str(existing_geometry)[:200]}")
        
        # Handle different geometry formats from various routing algorithms
        if isinstance(existing_geometry, list):
            # Format 1: Array of segments with coordinates
            for segment in existing_geometry:
                if isinstance(segment, dict):
                    # Format 1a: Direct dict with lat/lng keys (MOST COMMON - DHL format)
                    if 'lat' in segment and 'lng' in segment:
                        try:
                            lat = float(segment['lat'])
                            lng = float(segment['lng'])
                            algorithm_coords.append([lat, lng])
                        except (ValueError, TypeError) as e:
                            print(f"   ⚠️  Skipping invalid lat/lng dict: {segment} - {e}")
                    # Format 1b: Dict with nested coordinates key
                    elif 'coordinates' in segment:
                        coords_list = segment['coordinates']
                        if isinstance(coords_list, list):
                            for coord in coords_list:
                                if isinstance(coord, list) and len(coord) >= 2:
                                    try:
                                        lat = float(coord[1]) if len(coord) > 1 else float(coord[0])
                                        lng = float(coord[0]) if len(coord) > 1 else float(coord[1])
                                        # Swap if detected as [lat, lng] format
                                        if lat > 90 or lat < -90:
                                            lat, lng = lng, lat
                                        algorithm_coords.append([lat, lng])
                                    except (ValueError, IndexError) as e:
                                        print(f"   ⚠️  Skipping invalid coord: {coord} - {e}")
                    # Format 1c: Dict with path key
                    elif 'path' in segment:
                        path = segment['path']
                        if isinstance(path, list):
                            for pt in path:
                                if isinstance(pt, dict) and 'lat' in pt and 'lng' in pt:
                                    algorithm_coords.append([float(pt['lat']), float(pt['lng'])])
                    # Format 1d: Dict with polyline key (Google Maps)
                    elif 'polyline' in segment:
                        # Handle polyline format (Google Maps)
                        try:
                            import polyline
                            decoded = polyline.decode(segment['polyline'])
                            algorithm_coords.extend(decoded)
                        except:
                            pass
                            
                elif isinstance(segment, (list, tuple)) and len(segment) >= 2:
                    # Format 2: Direct coordinate array [lat, lng] or [lng, lat]
                    try:
                        lat = float(segment[0])
                        lng = float(segment[1])
                        # Detect format: if first value > 90, it's probably [lng, lat]
                        if lat > 90 or lat < -90:
                            lat, lng = lng, lat
                        algorithm_coords.append([lat, lng])
                    except (ValueError, TypeError) as e:
                        print(f"   ⚠️  Skipping invalid segment: {segment} - {e}")
        
        # Remove duplicate consecutive points
        if algorithm_coords:
            deduplicated = [algorithm_coords[0]]
            for coord in algorithm_coords[1:]:
                if coord != deduplicated[-1]:
                    deduplicated.append(coord)
            algorithm_coords = deduplicated
            print(f"   ✅ Deduped to {len(algorithm_coords)} unique points")
        
        if not algorithm_coords:
            print(f"   ❌ Could not extract coordinates from geometry")
            print(f"   Geometry structure: {existing_geometry}")
            return jsonify({
                'success': False,
                'error': 'Route geometry format is invalid or empty. Check server logs for details.'
            })
        
        print(f"   ✅ Extracted {len(algorithm_coords)} unique points from algorithm route")
        print(f"      Start point: [{algorithm_coords[0][0]:.6f}, {algorithm_coords[0][1]:.6f}]")
        print(f"      End point: [{algorithm_coords[-1][0]:.6f}, {algorithm_coords[-1][1]:.6f}]")
        
        # ============================================================
        # STEP 2: Fetch Google Maps route using same origin/destination
        # ============================================================
        print(f"\n🌐 Step 2: Fetch Google Maps route")
        
        google_route = gmaps_service.get_directions(start_lat, start_lng, dest_lat, dest_lng)
        
        if not google_route or not google_route.get('success'):
            error_msg = google_route.get('error') if google_route else 'Google Maps API call failed'
            print(f"   ❌ Error: {error_msg}")
            return jsonify({
                'success': False,
                'error': f"Failed to fetch Google Maps route: {error_msg}"
            })
        
        google_coords = google_route.get('coordinates', [])
        
        if not google_coords:
            print(f"   ❌ Google Maps returned no coordinates")
            return jsonify({
                'success': False,
                'error': 'Google Maps route has no coordinates'
            })
        
        print(f"   ✅ Google Maps route fetched: {len(google_coords)} points")
        print(f"      Distance: {google_route.get('distance_text', 'N/A')}")
        print(f"      Duration: {google_route.get('duration_text', 'N/A')}")
        print(f"      Distance (meters): {google_route.get('distance_meters', 'N/A')}")
        
        # ============================================================
        # STEP 3: Calculate comparison metrics
        # ============================================================
        print(f"\n📊 Step 3: Calculate comparison metrics")
        
        # Calculate Fréchet distance (measures max deviation between routes)
        frechet_distance = gmaps_service.compute_frechet_distance(algorithm_coords, google_coords)
        
        # Calculate segment overlap (percentage of matching points)
        segment_overlap = gmaps_service.compute_segment_overlap(algorithm_coords, google_coords)
        
        print(f"   ✅ Fréchet distance: {frechet_distance:.2f} meters")
        print(f"   ✅ Segment overlap: {segment_overlap:.2f}%")
        
        google_distance_meters = google_route.get('distance_meters', 1)
        frechet_ratio = round((frechet_distance / max(google_distance_meters, 1)) * 100, 2)
        print(f"   ✅ Fréchet/Distance ratio: {frechet_ratio}%")
        
        # ============================================================
        # STEP 4: Build response with both routes for map display
        # ============================================================
        print(f"\n✅ Comparison complete!")
        
        result = {
            'success': True,
            'algorithm_route': {
                'coordinates': algorithm_coords,
                'name': algorithm_name,
                'point_count': len(algorithm_coords),
                'format': 'Dynamic (current route data)'
            },
            'google_maps_route': {
                'coordinates': google_coords,
                'distance_meters': google_route.get('distance_meters', 0),
                'duration_seconds': google_route.get('duration_seconds', 0),
                'distance_text': google_route.get('distance_text', ''),
                'duration_text': google_route.get('duration_text', ''),
                'point_count': len(google_coords)
            },
            'comparison': {
                'frechet_distance_meters': round(frechet_distance, 2),
                'segment_overlap_percent': round(segment_overlap, 2),
                'algorithm_distance_ratio': frechet_ratio,
                'interpretation': {
                    'frechet_status': 'Excellent' if frechet_distance < 500 else 'Very Good' if frechet_distance < 1000 else 'Good' if frechet_distance < 2000 else 'Fair',
                    'overlap_status': 'Perfect' if segment_overlap >= 90 else 'Very Good' if segment_overlap >= 75 else 'Good' if segment_overlap >= 60 else 'Fair'
                }
            },
            'metadata': {
                'comparison_time': time.time(),
                'algorithm': algorithm_name,
                'origin': {'lat': start_lat, 'lng': start_lng},
                'destination': {'lat': dest_lat, 'lng': dest_lng}
            }
        }
        
        print(f"   📊 Fréchet Status: {result['comparison']['interpretation']['frechet_status']}")
        print(f"   📊 Overlap Status: {result['comparison']['interpretation']['overlap_status']}")
        
        return jsonify(result)
        
    except KeyError as e:
        error_msg = f"Missing required parameter: {str(e)}"
        print(f"\n❌ {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg
        })
    except ValueError as e:
        error_msg = f"Invalid parameter value: {str(e)}"
        print(f"\n❌ {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg
        })
    except Exception as e:
        import traceback
        print(f"\n❌ Google Maps comparison error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Comparison failed: {str(e)}"
        })


@app.route('/register_active_route', methods=['POST'])
def register_active_route():
    """Register a route for automatic disruption monitoring"""
    try:
        data = request.json
        route_id = data.get('route_id', f"route_{int(time.time())}")
        
        auto_service = get_auto_disruption_service()
        if auto_service:
            auto_service.register_active_route(route_id, {
                'algorithm': data.get('algorithm', 'unknown'),
                'start_lat': data.get('start_lat'),
                'start_lng': data.get('start_lng'),
                'dest_lat': data.get('dest_lat'),
                'dest_lng': data.get('dest_lng'),
                'use_disruptions': data.get('use_disruptions', False)
            })
            return jsonify({
                'success': True,
                'route_id': route_id,
                'message': 'Route registered for monitoring'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Auto-disruption service not available'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/unregister_active_route', methods=['POST'])
def unregister_active_route():
    """Unregister a route from monitoring"""
    try:
        data = request.json
        route_id = data.get('route_id')
        
        auto_service = get_auto_disruption_service()
        if auto_service and route_id:
            auto_service.unregister_route(route_id)
            return jsonify({
                'success': True,
                'message': 'Route unregistered'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid route_id or service unavailable'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/check_disruption_updates')
def check_disruption_updates():
    """Check if disruption files have been updated (polling endpoint)"""
    try:
        import hashlib
        
        files_to_check = [
            Config.DISRUPTIONS_DIR / "dynamic_disruptions_hc2l.gr",
            Config.DISRUPTIONS_DIR / "dynamic_disruptions_dhl.gr",
            Config.DISRUPTIONS_DIR / "dynamic_disruptions_current.gr"
        ]
        
        combined_content = ""
        file_mtimes = {}
        
        for file_path in files_to_check:
            if file_path.exists():
                combined_content += file_path.read_text()
                file_mtimes[file_path.name] = file_path.stat().st_mtime
        
        current_hash = hashlib.md5(combined_content.encode()).hexdigest() if combined_content else None
        
        return jsonify({
            'success': True,
            'hash': current_hash,
            'file_mtimes': file_mtimes,
            'timestamp': time.time()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/fetch_here_traffic', methods=['POST'])
def fetch_here_traffic():
    """
    Fetch real-time traffic data from HERE API and generate disruption file
    
    Request body:
    {
        "algorithm": "hc2l" or "dhl",  // Optional, defaults to "current"
        "apply_immediately": true,      // Optional, whether to use this as dynamic disruption
        "traffic_mode": "incidents" | "flow" | "both"  // Required: specify data mode
    }
    """
    try:
        data = request.get_json() or {}
        algorithm = data.get('algorithm', 'current')
        apply_immediately = data.get('apply_immediately', True)
        traffic_mode = data.get('traffic_mode', 'both')  # Default to both
        
        # Validate traffic mode
        if traffic_mode not in ['incidents', 'flow', 'both']:
            return jsonify({
                'success': False,
                'error': f"Invalid traffic_mode: {traffic_mode}. Must be 'incidents', 'flow', or 'both'"
            })
        
        # Get HERE traffic service
        here_service = traffic_service
        
        # Determine output file
        if algorithm in ['hc2l', 'dhl']:
            output_file = Config.DISRUPTIONS_DIR / f"here_traffic_disruptions_{algorithm}.gr"
        else:
            output_file = Config.DISRUPTIONS_DIR / "here_traffic_disruptions_current.gr"
        
        # Fetch and save traffic data using new hash-based system
        metadata = traffic_service.fetch_and_save(mode=traffic_mode)
        edges_count = metadata.get('total_edges', 0)
        
        # If apply_immediately, the files are already created as current_traffic_*.gr
        if apply_immediately and edges_count > 0:
            print(f"✅ Traffic data updated ({traffic_mode} mode): {edges_count} edges")
        
        return jsonify({
            'success': True,
            'edges_affected': edges_count,
            'metadata': metadata,
            'output_file': str(output_file),
            'traffic_mode': traffic_mode
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/set_traffic_mode', methods=['POST'])
def set_traffic_mode():
    """
    Set the traffic data mode for HERE API integration
    
    Request body:
    {
        "mode": "incidents" | "flow" | "both"
    }
    """
    try:
        data = request.get_json() or {}
        mode = data.get('mode', 'both')
        
        # Validate mode
        if mode not in ['incidents', 'flow', 'both']:
            return jsonify({
                'success': False,
                'error': f"Invalid mode: {mode}. Must be 'incidents', 'flow', or 'both'"
            })
        
        # Get HERE traffic service and set mode
        here_service = traffic_service
        traffic_service.set_traffic_mode(mode)
        
        return jsonify({
            'success': True,
            'mode': mode,
            'message': f'Traffic mode set to: {mode.upper()}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/get_traffic_status', methods=['GET'])
def get_traffic_status():
    """Get current traffic mode and statistics"""
    try:
        here_service = traffic_service
        
        return jsonify({
            'success': True,
            'traffic_mode': traffic_service.traffic_mode,
            'api_key_configured': bool(traffic_service.api_key),
            'bbox': traffic_service.bbox
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


if __name__ == '__main__':
    # Print configuration summary
    print(Config.get_config_summary())
    
    print("\n" + "="*80)
    print("🔄 Auto-Disruption Service Status:")
    print(f"   Update Interval: 90 seconds")
    print(f"   Monitoring: Dynamic disruption files")
    print(f"   Auto-recalculation: Enabled for active routes")
    print("="*80 + "\n")
    
    # Start Flask server
    app.run(
        debug=Config.FLASK_DEBUG,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        # use_reloader=False  # Disable auto-reloader to prevent unwanted restarts
    )
