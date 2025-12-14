# hc2l_router.py - Enhanced HC2L Routing Integration with Road Names
"""
HC2L-based routing service using the Hierarchical Cut 2-Hop Labelling (HC2L) algorithm.

ALGORITHM ARCHITECTURE:
    HC2L is a LABELING-BASED algorithm designed for ultra-fast distance queries.
    
    Two-Phase Routing Process:
    
    Phase 1: Distance Computation (via Labels)
        - Uses precomputed hierarchical cut labels in ContractionIndex
        - Computes shortest distance via 2-hop label intersection
        - Time complexity: O(1) typical, O(k) where k = label size
        - NO graph search required
    
    Phase 2: Path Reconstruction (via Graph Traversal)
        - Uses actual road network edges
        - Runs Dijkstra to find path matching the label-computed distance
        - Respects one-way roads, road closures, and real topology
        - Time complexity: O(E log V) where E,V are local to the path
    
    Why This Design?
        - Labeling algorithms (HC2L, DHL) are optimized for DISTANCE queries
        - They do NOT store path information in labels (would be too expensive)
        - Path reconstruction requires actual edge data
        - This separation is standard in the field of distance oracles
    
    Reference: https://github.com/henningkoehlernz/road-networks
    Algorithm: Hierarchical Cut Labelling for distance queries
"""
import subprocess
import json
import os
import csv
from typing import Dict, List
from road_name_mapper import RoadNameMapper
from road_geometry_loader import RoadGeometryLoader
from config import Config
from console_formatter import get_logger

# Get logger instance
logger = get_logger("HC2LRouter")

class HC2LRouter:
    """
    Python wrapper for the C++ HC2L Routing Service
    Provides easy integration with Flask applications
    """
    
    def __init__(self, cpp_executable_path: str = None, nodes_csv_path: str = None):
        """Initialize HC2L router with path to C++ executable and nodes data"""
        
        # Use config to find executable if not provided
        if cpp_executable_path is None:
            try:
                cpp_executable_path = str(Config.get_hc2l_executable())
            except FileNotFoundError as e:
                raise FileNotFoundError(f"HC2L executable not found. Please build it using: ./build_all.sh") from e
            
        self.cpp_executable = cpp_executable_path
            
        if not os.path.exists(self.cpp_executable):
            raise FileNotFoundError(f"C++ executable not found: {self.cpp_executable}")
        
        logger.success(f"Using HC2L routing executable: {self.cpp_executable}")
        
        # Load nodes data for coordinate lookup using config
        self.nodes_csv_path = nodes_csv_path or str(Config.NODES_CSV)
        self.nodes_data = None
        self._load_nodes_data()
        
        # Initialize road name mapper using config
        self.road_mapper = RoadNameMapper(str(Config.EDGES_CSV))
        
        # Initialize road geometry loader for accurate path visualization
        mapping_path = str(Config.NODES_CSV).replace('quezon_city_nodes.csv', 'node_id_mapping.csv')
        self.geometry_loader = RoadGeometryLoader(
            str(Config.EDGES_CSV), 
            str(Config.NODES_CSV),
            mapping_path
        )
        logger.success("Road geometry loader initialized")
    
    def _load_nodes_data(self):
        """Load nodes CSV data for coordinate lookup"""
        try:
            if os.path.exists(self.nodes_csv_path):
                # Load CSV using standard library
                self.nodes_data = {}
                with open(self.nodes_csv_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        node_id = int(row['node_id'])
                        self.nodes_data[node_id] = {
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude'])
                        }
                logger.success(f"Loaded {len(self.nodes_data)} nodes from {self.nodes_csv_path}")
            else:
                logger.warning(f"Nodes file not found at {self.nodes_csv_path}")
                logger.info("Route coordinates will be limited to start/end points")
        except Exception as e:
            logger.error(f"Error loading nodes data: {e}")
            self.nodes_data = None
    
    def compute_route(self, 
                     start_pin_lat: float, start_pin_lng: float,
                     dest_pin_lat: float, dest_pin_lng: float,
                     start_snap_lat: float, start_snap_lng: float,
                     dest_snap_lat: float, dest_snap_lng: float,
                     start_edge_source: int, start_edge_target: int, start_edge_oneway: int,
                     dest_edge_source: int, dest_edge_target: int, dest_edge_oneway: int,
                     disruption_file: str = "", tau_threshold: float = 0.5,
                     generate_alternatives: bool = True,
                     verbose: bool = True
                     ) -> Dict:
        """
        Compute route using HC2L Routing Service with snap point information
        Returns enhanced route data with Google Maps integration
        
        Args:
            start_pin_lat: Starting pin point latitude (user click)
            start_pin_lng: Starting pin point longitude (user click)
            dest_pin_lat: Destination pin point latitude (user click)
            dest_pin_lng: Destination pin point longitude (user click)
            start_snap_lat: Starting snap point latitude (snapped to edge)
            start_snap_lng: Starting snap point longitude (snapped to edge)
            dest_snap_lat: Destination snap point latitude (snapped to edge)
            dest_snap_lng: Destination snap point longitude (snapped to edge)
            start_edge_source: Source node of edge where start snap occurred
            start_edge_target: Target node of edge where start snap occurred
            start_edge_oneway: One-way property of start edge (1=forward, -1=reverse, 0=bidirectional)
            dest_edge_source: Source node of edge where dest snap occurred
            dest_edge_target: Target node of edge where dest snap occurred
            dest_edge_oneway: One-way property of dest edge (1=forward, -1=reverse, 0=bidirectional)
            disruption_file: Path to .gr disruption file (empty string or "null" = no disruptions)
            tau_threshold: LazyHC2L threshold parameter (default: 0.5)
            generate_alternatives: Whether to generate alternative routes (default True for backward compatibility)
        """

        logger.disable_logging(not verbose)

        try:
            # Build command with LazyHC2L argument structure
            # Args: 14 routing params + 3 data files + optional disruption_file + optional tau_threshold + optional generate_alternatives
            cmd = [
                self.cpp_executable,
                str(start_pin_lat), str(start_pin_lng),
                str(start_snap_lat), str(start_snap_lng),
                str(start_edge_source), str(start_edge_target), str(start_edge_oneway),
                str(dest_pin_lat), str(dest_pin_lng),
                str(dest_snap_lat), str(dest_snap_lng),
                str(dest_edge_source), str(dest_edge_target), str(dest_edge_oneway),
                str(Config.NODES_CSV),
                str(Config.EDGES_CSV),
                str(Config.HC2L_INDEX_FILE)
            ]
            
            # Add optional disruption parameters if provided
            if disruption_file and disruption_file not in ['', 'null', 'NULL']:
                # CRITICAL: Verify the disruption directory contains BOTH latest flow and incident files
                # This ensures C++ receives the most recent disruption data
                try:
                    from pathlib import Path as PathlibPath
                    disruption_path = PathlibPath(disruption_file)
                    
                    # Check for latest flow and incident CSV files
                    flow_dir = disruption_path / 'flow'
                    incident_dir = disruption_path / 'incidents'
                    
                    if flow_dir.exists():
                        flow_files = sorted(flow_dir.glob('flow_*.csv'), key=lambda f: f.stat().st_mtime, reverse=True)
                        if flow_files:
                            latest_flow = flow_files[0]
                            logger.info(f"Latest flow file: {latest_flow.name} (mtime: {latest_flow.stat().st_mtime})")
                    
                    if incident_dir.exists():
                        incident_files = sorted(incident_dir.glob('incident_*.csv'), key=lambda f: f.stat().st_mtime, reverse=True)
                        if incident_files:
                            latest_incident = incident_files[0]
                            logger.info(f"Latest incident file: {latest_incident.name} (mtime: {latest_incident.stat().st_mtime})")
                except Exception as e:
                    logger.warning(f"Could not verify disruption files: {e}")
                
                logger.info(f"Adding disruption directory: {disruption_file}")
                cmd.append(str(disruption_file))
                cmd.append(str(tau_threshold))
            else:
                logger.warning(f"No disruption directory passed (disruption_file={repr(disruption_file)})")
            
            # Add generate_alternatives flag (pass 1 for True, 0 for False)
            cmd.append(str(1 if generate_alternatives else 0))
            
            logger.processing(f"Executing HC2L routing: {' '.join(cmd)}")
            
            # Execute command directly - file paths are provided as arguments
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f"HC2L routing failed: {result.stderr}",
                    'stdout': result.stdout
                }
            
            # Parse JSON output
            try:
                # Extract JSON from output (might have debug info before it)
                output = result.stdout.strip()
                
                # Find the start of JSON (first '{' character)
                json_start = output.find('{')
                if json_start == -1:
                    return {
                        'success': False,
                        'error': 'No JSON output found',
                        'debug_info': json.dumps({
                            'success': True,
                            'algorithm': 'HC2L (Hierarchical Cut 2-Hop Labelling)',
                            'input': {
                                'start_pin_lat': start_pin_lat,
                                'start_pin_lng': start_pin_lng,
                                'start_snap_lat': start_snap_lat,
                                'start_snap_lng': start_snap_lng,
                                'dest_pin_lat': dest_pin_lat,
                                'dest_pin_lng': dest_pin_lng,
                                'dest_snap_lat': dest_snap_lat,
                                'dest_snap_lng': dest_snap_lng,
                                'disruption_file': disruption_file,
                                'tau_threshold': tau_threshold,
                                'use_disruptions': bool(disruption_file and disruption_file not in ['', 'null', 'NULL'])
                            },
                            'gps_mapping': {},
                            'metrics': {},
                            'route': {}
                        }, indent=2),
                        'raw_output': result.stdout
                    }
                
                # Extract the JSON part (from first '{' to end)
                json_output = output[json_start:]
                
                route_data = json.loads(json_output)
                
                # Debug: Print the metrics received from C++ API
                if route_data.get('success', False):
                    metrics = route_data.get('metrics', {})
                    logger.data(f"Received metrics from C++ API:")
                    logger.info(f"Query time: {metrics.get('query_time_ms', 'N/A')} ms")
                    logger.info(f"Distance: {metrics.get('calculated_distance_km', 'N/A')} km")
                    logger.info(f"ETA: {metrics.get('eta_formatted', 'N/A')}")
                    logger.info(f"Labeling size: {metrics.get('labeling_size_kb', 'N/A')} KB")
                    logger.info(f"Labeling time: {metrics.get('labeling_time_ms', 'N/A')} s")
                    
                    # Log disruption analysis if present
                    disruption_analysis = route_data.get('disruption_analysis', {})
                    if disruption_analysis:
                        route_disruptions = disruption_analysis.get('route_disruptions', {})
                        time_impact = disruption_analysis.get('time_impact', {})
                        logger.warning("Disruption Analysis:")
                        logger.info(f"Total disruptions on route: {route_disruptions.get('total_count', 0)}")
                        logger.info(f"Road closures: {route_disruptions.get('closures', 0)}")
                        logger.info(f"Added delay: {time_impact.get('added_delay_seconds', 0):.1f}s ({time_impact.get('percentage_increase', 0):.1f}%)")
                
                # Enhance with coordinate data if available
                if route_data.get('success', False):
                    route_data = self._enhance_route_with_coordinates(route_data)
                    route_data = self._enhance_route_with_road_names(route_data)
                
                # Debug: Verify geometry is in route_data before returning
                geometry_count = len(route_data.get('route', {}).get('geometry', []))
                logger.data(f"HC2L Router: Returning route_data with {geometry_count} geometry segments")
                
                return route_data
                
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'error': f"Failed to parse JSON output: {e}",
                    'raw_output': result.stdout
                }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': "HC2L route computation timed out (60 seconds)"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Error executing HC2L route computation: {str(e)}"
            }
    
    def _enhance_route_with_coordinates(self, route_data: Dict) -> Dict:
        """Enhance route data with GPS coordinates from C++ API geometry output"""
        
        if not route_data.get('success', False):
            return route_data
        
        try:
            # Check if C++ API already provided geometry
            api_geometry = route_data.get('route', {}).get('geometry', [])
            
            # Preserve geometry for frontend (contains edge details: distance, highway type, speeds, traffic status)
            if api_geometry:
                route_data['route']['geometry'] = api_geometry
            
            if api_geometry:
                # Use geometry from C++ API (already includes road curves from CSV)
                logger.info(f"Using geometry from C++ API: {len(api_geometry)} edge segments")
                
                # Convert C++ API geometry format to coordinate list
                # API format: [{"from": 1, "to": 2, "coordinates": [[lon, lat], ...]}, ...]
                coordinates = []
                
                for segment in api_geometry:
                    segment_coords = segment.get('coordinates', [])
                    for coord_pair in segment_coords:
                        if len(coord_pair) >= 2:
                            coordinates.append({
                                'lat': coord_pair[1],  # lat is second
                                'lng': coord_pair[0]   # lon is first
                            })
                
                logger.success(f"Extracted {len(coordinates)} GPS coordinates from C++ API geometry")
                
                # Get path summary from edges (for statistics)
                path_nodes = route_data.get('route', {}).get('path_nodes', [])
                if path_nodes and self.geometry_loader:
                    path_summary = self.geometry_loader.get_path_summary(path_nodes)
                else:
                    path_summary = {
                        'total_distance_m': route_data.get('metrics', {}).get('total_distance_units', 0),
                        'num_segments': len(api_geometry),
                        'num_nodes': len(path_nodes) if path_nodes else 0
                    }
                
            else:
                # Fallback: C++ API didn't provide geometry (old version or error)
                logger.warning("C++ API didn't provide geometry, using fallback method")
                path_nodes = route_data.get('route', {}).get('path_nodes', [])
                
                if not path_nodes:
                    return route_data
                
                # Use the geometry loader to get coordinates following actual road network
                logger.info(f"Getting road network coordinates for {len(path_nodes)} nodes")
                
                # Get coordinates following actual edges with geometry from CSV
                coordinates = self.geometry_loader.get_path_coordinates(path_nodes, use_osm_geometry=True)
                
                logger.info(f"Route has {len(coordinates)} points following road network (with curves)")
                
                # Validate the path
                is_valid, validation_message = self.geometry_loader.validate_path(path_nodes)
                if not is_valid:
                    logger.warning(f"Path validation: {validation_message}")
                
                # Get path summary
                path_summary = self.geometry_loader.get_path_summary(path_nodes)
                logger.data(f"Path summary: {path_summary['total_distance_m']:.1f}m over {path_summary['num_segments']} segments")
            
            # Apply minimal interpolation if needed (only for very long gaps)
            from geometry_utils import enhance_route_geometry
            interpolated_coordinates = enhance_route_geometry(
                coordinates, 
                max_distance=100.0,  # Higher threshold since CSV geometry already provides curves
                preserve_node_ids=False
            )
            
            logger.success(f"Final route with {len(interpolated_coordinates)} GPS coordinates")
            
            # Update route data with enhanced coordinates
            route_data['route']['coordinates'] = interpolated_coordinates
            route_data['route']['path_summary_stats'] = path_summary
            
            # Create polylines for Google Maps/Leaflet
            if len(interpolated_coordinates) >= 2:
                route_data['route']['polylines'] = [{
                    'path': [{'lat': coord['lat'], 'lng': coord['lng']} for coord in interpolated_coordinates],
                    'strokeColor': '#FF0000',  # Red for HC2L route
                    'strokeOpacity': 0.8,
                    'strokeWeight': 5,
                    'geodesic': True
                }]
            
        except Exception as e:
            logger.warning(f"Failed to enhance coordinates: {e}")
            import traceback
            traceback.print_exc()
        
        return route_data
    
    def _enhance_route_with_road_names(self, route_data: Dict) -> Dict:
        """Enhance route data with road names and turn-by-turn directions"""
        
        if not route_data.get('success', False):
            return route_data
        
        try:
            path_nodes = route_data.get('route', {}).get('path_nodes', [])
            
            if not path_nodes or len(path_nodes) < 2:
                return route_data
            
            # Get road segments with names
            road_segments = self.road_mapper.get_route_with_road_names(path_nodes)
            route_summary = self.road_mapper.get_route_summary_text(path_nodes)

            turn_directions = self.road_mapper.get_turn_by_turn_directions(path_nodes)
            
            # Add road information to route data
            route_data['route']['road_segments'] = road_segments
            route_data['route']['route_summary'] = route_summary
            route_data['route']['turn_by_turn_directions'] = turn_directions
            
            # Create a simplified display format for frontend
            route_data['route']['display_format'] = {
                'node_path': ' → '.join(map(str, path_nodes)),
                'road_path': route_summary,
                'instruction_count': len(turn_directions),
                'road_count': len(road_segments)
            }
            
            logger.success(f"Enhanced route with {len(road_segments)} road segments")
            logger.info(f"Route summary: {route_summary}")
            
        except Exception as e:
            logger.warning(f"Failed to enhance road names: {e}")
        
        return route_data
    
    def get_route_polylines_for_gmaps(self, route_data: Dict) -> List[Dict]:
        """
        Convert route data to Google Maps polyline format
        """
        if not route_data.get('success', False):
            return []
        
        return route_data.get('route', {}).get('polylines', [])
    
    def get_route_summary(self, route_data: Dict) -> Dict:
        """Get summary information for display"""
        if not route_data.get('success', False):
            return {'error': route_data.get('error', 'Unknown error')}
        
        metrics = route_data.get('metrics', {})
        
        # ENHANCED: Extract labeling info from HC2L C++ nested object
        labeling_info = metrics.get('labeling_info', {})
        
        # Extract labeling size and time from C++ labeling_info
        labeling_size_kb = labeling_info.get('index_size_bytes', 0.0) / 1024
        labeling_time_ms = labeling_info.get('index_load_time_ms', 0.0)
        
        # Fallback to direct metrics if labeling_info not available
        if labeling_size_kb == 0.0:
            labeling_size_kb = metrics.get('labeling_size_bytes', 0.0) / 1024
        if labeling_time_ms == 0.0:
            labeling_time_ms = metrics.get('labeling_time_ms', 0.0)
        
        summary = {
            'algorithm': route_data.get('algorithm', 'D-HC2L Dynamic GPS'),
            'algorithm_base': route_data.get('algorithm_base', 'D-HC2L'),
            'query_time_ms': metrics.get('query_time_ms', 0),
            'query_time_microseconds': metrics.get('query_time_microseconds', 0),
            'total_distance_meters': metrics.get('total_distance_meters', 0),  # Keep original field name
            'total_distance_m': metrics.get('total_distance_meters', 0),       # Also provide alternative
            'path_length': metrics.get('path_length', 0),
            'routing_mode': metrics.get('routing_mode', 'BASE'),
            'uses_disruptions': metrics.get('uses_disruptions', False),
            'tau_threshold': metrics.get('tau_threshold', 0.5),
            
            # NEW: Add mode-specific information
            'update_strategy': metrics.get('update_strategy', 'none'),
            'mode_explanation': metrics.get('mode_explanation', ''),
            'labels_status': metrics.get('labels_status', 'original'),
            
            # ENHANCED: Add labeling metrics from C++ labeling_info
            'labeling_size_kb': labeling_size_kb,
            'labeling_time_ms': labeling_time_ms,
            'labeling_info': labeling_info  # Pass through complete labeling_info for debugging
        }
        
        # Add disruption comparison if available
        if metrics.get('distance_difference_meters') is not None:
            summary.update({
                'base_distance_meters': metrics.get('base_distance_meters', 0),
                'base_distance_m': metrics.get('base_distance_meters', 0),
                'distance_difference_meters': metrics.get('distance_difference_meters', 0),
                'distance_difference_m': metrics.get('distance_difference_meters', 0),
                'distance_change_percentage': metrics.get('distance_change_percentage', 0),
                'route_comparison': metrics.get('route_comparison', '')
            })
        
        return summary
    
    def compare_routes(self, start_lat: float, start_lng: float, 
                      dest_lat: float, dest_lng: float) -> Dict:
        """Compare base route vs disrupted route"""
        
        # Get base route
        base_route = self.compute_route(start_lat, start_lng, dest_lat, dest_lng, False)
        
        # Get disrupted route
        disrupted_route = self.compute_route(start_lat, start_lng, dest_lat, dest_lng, True)
        
        if not base_route.get('success') or not disrupted_route.get('success'):
            return {
                'success': False,
                'error': 'Failed to compute one or both routes for comparison'
            }
        
        # Create comparison
        comparison = {
            'success': True,
            'routes': {
                'base': {
                    'polylines': self.get_route_polylines_for_gmaps(base_route),
                    'metrics': self.get_route_summary(base_route),
                    'color': '#0000FF',  # Blue for base
                    'name': 'HC2L Base Route'
                },
                'disrupted': {
                    'polylines': self.get_route_polylines_for_gmaps(disrupted_route),
                    'metrics': self.get_route_summary(disrupted_route),
                    'color': '#FF0000',  # Red for disrupted
                    'name': 'HC2L Disrupted Route'
                }
            },
            'comparison': {
                'distance_difference_m': (
                    disrupted_route['metrics']['total_distance_meters'] - 
                    base_route['metrics']['total_distance_meters']
                ),
                'time_difference_ms': (
                    disrupted_route['metrics']['query_time_ms'] - 
                    base_route['metrics']['query_time_ms']
                )
            }
        }
        
        return comparison
    
    def get_network_stats(self) -> Dict:
        """Get network statistics"""
        return {
            'algorithm': 'HC2L Hierarchical Cut Labelling with GPS Integration',
            'dataset': 'Quezon City, Philippines',
            'nodes': len(self.nodes_data) if self.nodes_data is not None else 13649,
            'coverage': 'Real GPS coordinates with traffic disruption support'
        }

# Test function
def test_hc2l_routing():
    """
    Comprehensive test function for HC2L routing service
    Tests both base and disrupted routing with real coordinates
    """
    logger.processing("Starting HC2L Routing Service Tests")
    logger.info("=" * 60)
    
    try:
        # Initialize the GPS routing service
        logger.processing("Initializing HC2L Routing Service...")
        service = HC2LRouter()
        
        # Test coordinates (Quezon City, Philippines)
        test_cases = [
            {
                'name': 'Short Distance Route',
                'start_lat': 14.6760,
                'start_lng': 121.0437,
                'dest_lat': 14.6542,
                'dest_lng': 121.0790,
                'description': 'Route within Quezon City'
            },
            {
                'name': 'Medium Distance Route',
                'start_lat': 14.6420,
                'start_lng': 121.0580,
                'dest_lat': 14.6455,
                'dest_lng': 121.0572,
                'description': 'Cross-district route'
            }
        ]
        
        logger.success("Service initialized successfully!")
        logger.data(f"Network stats: {service.get_network_stats()}")
        
        # Test each route case
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"Test Case {i}: {test_case['name']}")
            logger.info(f"   {test_case['description']}")
            logger.info(f"   From: ({test_case['start_lat']}, {test_case['start_lng']})")
            logger.info(f"   To: ({test_case['dest_lat']}, {test_case['dest_lng']})")
            logger.info("-" * 50)
            
            # Test 1: Base routing (no disruptions)
            logger.processing("Testing BASE routing (no disruptions)...")
            base_result = service.compute_route(
                test_case['start_lat'], test_case['start_lng'],
                test_case['dest_lat'], test_case['dest_lng'],
                use_disruptions=False
            )
            
            if base_result.get('success'):
                base_summary = service.get_route_summary(base_result)
                logger.success("Base route computed successfully!")
                logger.info(f"Distance: {base_summary.get('total_distance_meters', 0)} meters")
                logger.info(f"Query time: {base_summary.get('query_time_ms', 0):.3f} ms")
                logger.info(f"Path length: {base_summary.get('path_length', 0)} nodes")
                
                # Check if route has coordinates
                coordinates = base_result.get('route', {}).get('coordinates', [])
                logger.info(f"GPS coordinates: {len(coordinates)} points")
                
                # Check if route has road names
                road_segments = base_result.get('route', {}).get('road_segments', [])
                if road_segments:
                    logger.info(f"Road segments: {len(road_segments)} segments")
                    logger.info(f"Route summary: {base_result.get('route', {}).get('route_summary', 'N/A')[:100]}...")
                
                # Check polylines for Google Maps
                polylines = service.get_route_polylines_for_gmaps(base_result)
                logger.info(f"Google Maps polylines: {len(polylines)} polylines")
                
            else:
                logger.error(f"Base route failed: {base_result.get('error', 'Unknown error')}")
                if 'raw_output' in base_result:
                    logger.info(f"Raw output: {base_result['raw_output'][:200]}...")
            
            # Test 2: Disrupted routing
            logger.processing("Testing DISRUPTED routing...")
            disrupted_result = service.compute_route(
                test_case['start_lat'], test_case['start_lng'],
                test_case['dest_lat'], test_case['dest_lng'],
                use_disruptions=True
            )
            
            if disrupted_result.get('success'):
                disrupted_summary = service.get_route_summary(disrupted_result)
                logger.success("Disrupted route computed successfully!")
                logger.info(f"Distance: {disrupted_summary.get('total_distance_meters', 0)} meters")
                logger.info(f"Query time: {disrupted_summary.get('query_time_ms', 0):.3f} ms")
                logger.info(f"Path length: {disrupted_summary.get('path_length', 0)} nodes")
                logger.info(f"Uses disruptions: {disrupted_summary.get('uses_disruptions', False)}")
                
            else:
                logger.error(f"Disrupted route failed: {disrupted_result.get('error', 'Unknown error')}")
                if 'raw_output' in disrupted_result:
                    logger.info(f"Raw output: {disrupted_result['raw_output'][:200]}...")
            
            # Test 3: Route comparison
            if base_result.get('success') and disrupted_result.get('success'):
                logger.processing("Testing route comparison...")
                comparison = service.compare_routes(
                    test_case['start_lat'], test_case['start_lng'],
                    test_case['dest_lat'], test_case['dest_lng']
                )
                
                if comparison.get('success'):
                    comp_data = comparison.get('comparison', {})
                    logger.success("Route comparison successful!")
                    logger.info(f"Distance difference: {comp_data.get('distance_difference_m', 0)} meters")
                    logger.info(f"Time difference: {comp_data.get('time_difference_ms', 0):.3f} ms")
                    
                    # Show route names
                    base_name = comparison['routes']['base']['name']
                    disrupted_name = comparison['routes']['disrupted']['name']
                    logger.info(f"{base_name}: {comparison['routes']['base']['metrics'].get('total_distance_meters', 0)}m")
                    logger.info(f"{disrupted_name}: {comparison['routes']['disrupted']['metrics'].get('total_distance_meters', 0)}m")
                else:
                    logger.error(f"Route comparison failed: {comparison.get('error', 'Unknown error')}")
        
        # Test 4: Error handling
        logger.processing("Testing error handling...")
        logger.info("Testing with invalid coordinates...")
        
        invalid_result = service.compute_route(
            999.0, 999.0,  # Invalid coordinates
            999.0, 999.0,
            use_disruptions=False
        )
        
        if not invalid_result.get('success'):
            logger.success("Error handling works correctly!")
            logger.info(f"Error message: {invalid_result.get('error', 'No error message')}")
        else:
            logger.warning("Invalid coordinates did not trigger error")
        
        # Summary
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.success("HC2L Routing Service tests completed!")
        logger.info("Check the output above for any failures or warnings.")
        logger.info("If all tests passed, the service is ready for web integration.")
        
    except FileNotFoundError as e:
        logger.error(f"Initialization failed: {e}")
        logger.info("Make sure the C++ executable exists and is built correctly.")
        logger.info("Build the executable with: make gps_routing_json_api")
        
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        logger.info("Check the error details above for debugging information.")

def test_hc2l_performance():
    """
    Performance test for HC2L routing service
    Tests multiple routes to measure average performance
    """
    logger.processing("HC2L Performance Test")
    logger.info("=" * 40)
    
    try:
        service = HC2LRouter()
        
        # Performance test coordinates
        test_routes = [
            (14.6760, 121.0437, 14.6542, 121.0790),
            (14.6420, 121.0580, 14.6455, 121.0572)
        ]
        
        logger.processing(f"Testing {len(test_routes)} routes for performance...")
        
        total_time = 0
        successful_routes = 0
        
        for i, (start_lat, start_lng, dest_lat, dest_lng) in enumerate(test_routes, 1):
            logger.info(f"Route {i}: ({start_lat}, {start_lng}) → ({dest_lat}, {dest_lng})")
            
            result = service.compute_route(
                start_lat, start_lng, dest_lat, dest_lng, use_disruptions=False
            )
            
            if result.get('success'):
                summary = service.get_route_summary(result)
                query_time = summary.get('query_time_ms', 0)
                total_time += query_time
                successful_routes += 1
                logger.success(f"{query_time:.3f} ms")
            else:
                logger.error(f"Failed: {result.get('error', 'Unknown')}")
        
        if successful_routes > 0:
            avg_time = total_time / successful_routes
            logger.data("Performance Results:")
            logger.info(f"Successful routes: {successful_routes}/{len(test_routes)}")
            logger.info(f"Average query time: {avg_time:.3f} ms")
            logger.info(f"Total time: {total_time:.3f} ms")
            
            if avg_time < 10:
                logger.success("Excellent performance! (<10ms average)")
            elif avg_time < 50:
                logger.success("Good performance! (<50ms average)")
            else:
                logger.warning("Performance may need optimization (>50ms average)")
        else:
            logger.error("No successful routes for performance analysis")
            
    except Exception as e:
        logger.error(f"Performance test failed: {e}")

if __name__ == "__main__":
    # Run comprehensive tests
    test_hc2l_routing()
    
    # Run performance tests
    # test_hc2l_performance()
    