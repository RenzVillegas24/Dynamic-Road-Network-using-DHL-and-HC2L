"""
Route Recalculation Endpoint
Triggered automatically after disruption changes (incident add/remove)
"""

from flask import request, jsonify
import time
from console_formatter import ConsoleFormatter
from config import Config

# Will be injected from flask_server
gps_router = None
dhl_router = None
console_logger = None

def init_route_recalculation(app, gps_router_ref, dhl_router_ref, logger):
    """Initialize the module with dependencies"""
    global gps_router, dhl_router, console_logger
    gps_router = gps_router_ref
    dhl_router = dhl_router_ref
    console_logger = logger
    
    @app.route('/trigger_route_recalculation', methods=['POST'])
    def trigger_route_recalculation():
        """
        Trigger automatic route recalculation after disruption changes (incident add/remove)
        
        Called by frontend after disruption file is updated
        Uses the currently stored snap points and algorithm selection
        
        Request body should include:
        - start_lat, start_lng: Original user pin coordinates
        - dest_lat, dest_lng: Original user pin coordinates
        - start_osm_edge: Optional snap point data for start
        - dest_osm_edge: Optional snap point data for destination
        - algorithm: 'dhl' or 'hc2l'
        - use_disruptions: boolean
        - dataset_mode: dataset selection
        - tau_threshold: HC2L threshold (optional)
        """
        data = request.json
        
        try:
            console_logger.info("=== TRIGGERING AUTO ROUTE RECALCULATION ===")
            console_logger.info(f"Reason: Disruption file updated (incident add/remove/reload)")
            
            # Extract routing parameters - using same structure as direct route computation
            start_lat = float(data.get('start_lat', 0))
            start_lng = float(data.get('start_lng', 0))
            dest_lat = float(data.get('dest_lat', 0))
            dest_lng = float(data.get('dest_lng', 0))
            
            algorithm = data.get('algorithm', 'hc2l').lower()
            use_disruptions = data.get('use_disruptions', True)
            dataset_mode = data.get('dataset_mode', 'none')
            tau_threshold = float(data.get('tau_threshold', 0.5))
            generate_alternatives = data.get('generate_alternatives', False)
            
            console_logger.data(f"Algorithm: {algorithm}")
            console_logger.data(f"Pin coords: ({start_lat}, {start_lng}) → ({dest_lat}, {dest_lng})")
            console_logger.data(f"Use disruptions: {use_disruptions}")
            console_logger.data(f"Generate alternatives: {generate_alternatives}")
            
            # Validate coordinates
            if not (start_lat and start_lng and dest_lat and dest_lng):
                return jsonify({
                    'success': False,
                    'error': 'Missing or invalid coordinates'
                }), 400
            
            # Delegate to appropriate route computation function
            if algorithm == 'dhl':
                console_logger.processing("Computing DHL route with updated disruptions...")
                # Build DHL-style request
                dhl_request = {
                    'start_lat': start_lat,
                    'start_lng': start_lng,
                    'dest_lat': dest_lat,
                    'dest_lng': dest_lng,
                    'dataset_mode': dataset_mode,
                    'use_disruptions': use_disruptions,
                    'generate_alternatives': generate_alternatives,
                }
                
                # Add OSM edge data if provided
                if 'start_osm_edge' in data:
                    dhl_request['start_osm_edge'] = data['start_osm_edge']
                if 'dest_osm_edge' in data:
                    dhl_request['dest_osm_edge'] = data['dest_osm_edge']
                
                response_data = compute_dhl_route_internal(dhl_request)
                
            else:  # hc2l
                console_logger.processing("Computing HC2L route with updated disruptions...")
                # Build HC2L-style request
                hc2l_request = {
                    'start_lat': start_lat,
                    'start_lng': start_lng,
                    'dest_lat': dest_lat,
                    'dest_lng': dest_lng,
                    'dataset_mode': dataset_mode,
                    'use_disruptions': use_disruptions,
                    'tau_threshold': tau_threshold,
                    'generate_alternatives': generate_alternatives,
                }
                
                # Add OSM edge data if provided
                if 'start_osm_edge' in data:
                    hc2l_request['start_osm_edge'] = data['start_osm_edge']
                if 'dest_osm_edge' in data:
                    hc2l_request['dest_osm_edge'] = data['dest_osm_edge']
                
                response_data = compute_dhc2l_route_internal(hc2l_request)
            
            if response_data.get('success'):
                console_logger.success("✅ Auto route recalculation completed successfully")
                response_data['auto_triggered'] = True
                return jsonify(response_data)
            else:
                console_logger.error(f"❌ Route recalculation failed: {response_data.get('error')}")
                return jsonify(response_data), 400
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            console_logger.error(f"Error in route recalculation trigger: {str(e)}")
            return jsonify({
                'success': False,
                'error': f"Route recalculation error: {str(e)}"
            }), 500


def compute_dhc2l_route_internal(data):
    """
    Internal HC2L route computation (used by both direct API and auto-trigger)
    """
    from config import Config
    
    try:
        if gps_router is None:
            return {
                'success': False,
                'error': 'HC2L Router not initialized properly'
            }
        
        # Extract pin coordinates (original user click points)
        start_pin_lat = float(data['start_lat'])
        start_pin_lng = float(data['start_lng'])
        dest_pin_lat = float(data['dest_lat'])
        dest_pin_lng = float(data['dest_lng'])
        tau_threshold = float(data.get('tau_threshold', 0.5))
        
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
            
            console_logger.success(f"Start snap: {start_osm_edge.get('road_name', 'Unknown')} " +
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
            
            console_logger.success(f"Dest snap: {dest_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {dest_edge_source}→{dest_edge_target}, oneway={dest_edge_oneway})")
        
        # LazyHC2L: Extract optional disruption parameters
        dataset_mode = data.get('dataset_mode', 'none')
        use_disruptions = data.get('use_disruptions', False)
        generate_alternatives = data.get('generate_alternatives', False)
        
        # Get disruption files based on dataset mode
        # Match the same logic as compute_dhc2l_route in flask_server.py
        disruption_files = ''
        
        if use_disruptions and dataset_mode != 'none':
            # Use disruptions: return the disruptions directory
            if Config.DISRUPTIONS_DIR.exists():
                disruption_files = str(Config.DISRUPTIONS_DIR)
                console_logger.data(f"📍 Using disruption directory for mode {dataset_mode}: {disruption_files}")
            else:
                console_logger.warning(f"⚠️  Disruptions directory not found at {Config.DISRUPTIONS_DIR}")
                disruption_files = ''
        else:
            # No disruptions - pass empty string
            disruption_files = ''
                
        console_logger.processing(f"Computing HC2L route with snap points:")
        console_logger.data(f"  Start: Pin({start_pin_lat}, {start_pin_lng}) → Snap({start_snap_lat}, {start_snap_lng})")
        console_logger.data(f"  Dest:  Pin({dest_pin_lat}, {dest_pin_lng}) → Snap({dest_snap_lat}, {dest_snap_lng})")
        console_logger.data(f"  Dataset mode: {dataset_mode if dataset_mode else 'auto'}")
        console_logger.data(f"  Disruption directory: {disruption_files if disruption_files else '(none)'}")
        console_logger.data(f"  Tau threshold: {tau_threshold}")
        console_logger.data(f"  Generate alternatives: {generate_alternatives}")
        
        # Compute route using HC2L with LazyHC2L parameters
        # Pass disruption directory to C++ - it will find flow/incident CSV files automatically
        start_time = time.time()
        route_result = gps_router.compute_route(
            start_pin_lat, start_pin_lng,
            dest_pin_lat, dest_pin_lng,
            start_snap_lat, start_snap_lng,
            dest_snap_lat, dest_snap_lng,
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway,
            disruption_files, tau_threshold, generate_alternatives  # Pass directory path
        )
        query_time = time.time() - start_time
        
        if not route_result.get('success', False):
            console_logger.error(f"HC2L C++ API returned error: {route_result.get('error')}")
            return route_result
        
        # Process route result (rest of logic same as compute_dhc2l_route)
        polylines = route_result.get('polylines', [])
        polyline_metrics = route_result.get('polyline_metrics', {})
        
        console_logger.success(f"HC2L route computed in {query_time:.2f}s")
        
        # Build response
        return {
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
                'geometry': route_result.get('route', {}).get('geometry', [])
            },
            'input': {
                'start_snap_lat': start_snap_lat,
                'start_snap_lng': start_snap_lng,
                'dest_snap_lat': dest_snap_lat,
                'dest_snap_lng': dest_snap_lng
            },
            'metrics': route_result.get('metrics', {})
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f"Route computation error: {str(e)}"
        }


def compute_dhl_route_internal(data):
    """
    Internal DHL route computation (used by both direct API and auto-trigger)
    """
    
    try:
        if dhl_router is None:
            return {
                'success': False,
                'error': 'DHL Router not initialized properly'
            }
        
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
            
            console_logger.success(f"Start snap (DHL): {start_osm_edge.get('road_name', 'Unknown')} " +
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
            
            console_logger.success(f"Dest snap (DHL): {dest_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {dest_edge_source}→{dest_edge_target}, oneway={dest_edge_oneway})")
        
        # Extract disruption parameters
        dataset_mode = data.get('dataset_mode', 'none')
        use_disruptions = data.get('use_disruptions', False)
        generate_alternatives = data.get('generate_alternatives', False)
        
        # Get disruption files based on dataset mode
        # Match the same logic as compute_dhl_route in flask_server.py
        disruption_files = ''
        
        if use_disruptions and dataset_mode != 'none':
            # Use disruptions: return the disruptions directory
            if Config.DISRUPTIONS_DIR.exists():
                disruption_files = str(Config.DISRUPTIONS_DIR)
                console_logger.data(f"📍 Using disruption directory for mode {dataset_mode}: {disruption_files}")
            else:
                console_logger.warning(f"⚠️  Disruptions directory not found at {Config.DISRUPTIONS_DIR}")
                disruption_files = ''
        else:
            # No disruptions - pass empty string
            disruption_files = ''
        
        # Support legacy single disruption_file parameter
        disruption_file = data.get('disruption_file', '')
        if disruption_file and not disruption_files:
            disruption_files = disruption_file
        
        tau_threshold = float(data.get('tau_threshold', 0.5))
        
        console_logger.processing(f"Computing DHL route with snap points:")
        console_logger.data(f"  Start: Pin({start_pin_lat}, {start_pin_lng}) → Snap({start_snap_lat}, {start_snap_lng})")
        console_logger.data(f"  Dest:  Pin({dest_pin_lat}, {dest_pin_lng}) → Snap({dest_snap_lat}, {dest_snap_lng})")
        console_logger.data(f"  Dataset mode: {dataset_mode if dataset_mode else 'auto'}")
        console_logger.data(f"  Disruption directory: {disruption_files if disruption_files else '(none)'}")
        console_logger.data(f"  Tau threshold: {tau_threshold}")
        console_logger.data(f"  Generate alternatives: {generate_alternatives}")
        
        # Compute route using DHL with disruption parameters
        # Pass disruption directory to C++ - it will find flow/incident CSV files automatically
        start_time = time.time()
        route_result = dhl_router.compute_route(
            start_pin_lat, start_pin_lng,
            dest_pin_lat, dest_pin_lng,
            start_snap_lat, start_snap_lng,
            dest_snap_lat, dest_snap_lng,
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway,
            disruption_files, tau_threshold, generate_alternatives
        )
        query_time = time.time() - start_time
        
        if not route_result.get('success', False):
            console_logger.error(f"DHL C++ API returned error: {route_result.get('error')}")
            return route_result
        
        console_logger.success(f"DHL route computed in {query_time:.2f}s")
        
        # Build response (rest of logic same as compute_dhl_route)
        return {
            'success': True,
            'route': route_result.get('route', {}),
            'input': {
                'start_snap_lat': start_snap_lat,
                'start_snap_lng': start_snap_lng,
                'dest_snap_lat': dest_snap_lat,
                'dest_snap_lng': dest_snap_lng
            },
            'metrics': route_result.get('metrics', {})
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f"Route computation error: {str(e)}"
        }
