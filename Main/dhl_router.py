# dhl_router.py - DHL Routing Integration
"""
DHL (Dual-Hierarchy Labelling) Routing Service

ALGORITHM ARCHITECTURE:
    DHL is a LABELING-BASED algorithm designed for ultra-fast distance queries.
    
    Two-Phase Routing Process:
    
    Phase 1: Distance Computation (via Labels)
        - Uses precomputed ContractionIndex labels
        - Computes shortest distance via label intersection
        - Time complexity: O(log n) typical
        - NO graph search required
    
    Phase 2: Path Reconstruction (via Graph Traversal)
        - Uses actual road network edges
        - Runs Dijkstra to find path matching the label-computed distance
        - Respects one-way roads, road closures, and real topology
        - Time complexity: O(E log V) where E,V are local to the path
    
    Why This Design?
        - Labeling algorithms (DHL, HC2L) are optimized for DISTANCE queries
        - They do NOT store path information in labels (would be too expensive)
        - Path reconstruction requires actual edge data
        - This separation is standard in the field of distance oracles
    
    Reference: https://github.com/mufarhan/Dual-Hierarchy-Labelling
"""
import subprocess
import json
import os
from typing import Dict, List
from road_name_mapper import RoadNameMapper
from road_geometry_loader import RoadGeometryLoader
from config import Config
from console_formatter import get_logger

# Get logger instance
logger = get_logger("DHLRouter")

class DHLRouter:
    def __init__(self, cpp_executable_path: str = None):
        """Initialize DHL router with path to C++ JSON API executable"""
        
        # If no path provided, use the config to find executable
        if cpp_executable_path is None:
            try:
                cpp_executable_path = str(Config.get_dhl_executable())
            except FileNotFoundError as e:
                raise FileNotFoundError(f"DHL executable not found. Please build it using: ./build_all.sh") from e
        
        self.cpp_executable = cpp_executable_path
        if not os.path.exists(cpp_executable_path):
            raise FileNotFoundError(f"DHL JSON API executable not found: {cpp_executable_path}")
        
        # Initialize road name mapper for turn-by-turn directions using config
        self.road_mapper = RoadNameMapper(str(Config.EDGES_CSV))
        
        # Initialize road geometry loader for accurate path visualization
        mapping_path = str(Config.NODES_CSV).replace('quezon_city_nodes.csv', 'node_id_mapping.csv')
        self.geometry_loader = RoadGeometryLoader(
            str(Config.EDGES_CSV), 
            str(Config.NODES_CSV),
            mapping_path
        )
        
        logger.success(f"Using DHL routing executable: {self.cpp_executable}")
        logger.success("Road geometry loader initialized")
    
    def compute_route(self, 
                     start_pin_lat: float, start_pin_lng: float,
                     dest_pin_lat: float, dest_pin_lng: float,
                     start_snap_lat: float, start_snap_lng: float,
                     dest_snap_lat: float, dest_snap_lng: float,
                     start_edge_source: int, start_edge_target: int, start_edge_oneway: int,
                     dest_edge_source: int, dest_edge_target: int, dest_edge_oneway: int,
                     disruption_file: str = "",
                     tau_threshold: float = 0.5,
                     generate_alternatives: bool = True,
                     verbose: bool = False
                     ) -> Dict:
        """
        Compute route using DHL algorithm via JSON API with snap point information
        Returns route data with polylines and metrics
        
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
            tau_threshold: NOTE: DHL does not use tau threshold (it's only for HC2L/LazyHC2L).
                          This parameter is accepted but ignored by DHL for API compatibility.
                          DHL always performs immediate updates, unlike LazyHC2L.
            generate_alternatives: Whether to generate alternative routes (default True for backward compatibility)
        """

        logger.disable_logging(not verbose)

        try:
            logger.processing("Executing DHL JSON API route computation...")
            
            # Build command with DHL argument structure
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
                str(Config.DHL_INDEX_FILE)
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
            
            logger.processing(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            logger.info(f"DHL executable return code: {result.returncode}")
            logger.info(f"DHL stdout: {result.stdout[:500] if result.stdout else '(empty)'}")
            logger.info(f"DHL stderr: {result.stderr[:500] if result.stderr else '(empty)'}")
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else result.stdout
                return {
                    'success': False,
                    'error': f"DHL JSON API failed (code {result.returncode}): {error_msg}",
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'return_code': result.returncode
                }
            
            # Parse JSON output from DHL JSON API
            try:
                # The DHL executable outputs initialization messages followed by JSON
                # We need to extract just the JSON part
                output_lines = result.stdout.strip()
                
                # Find the start of JSON (first '{' character)
                json_start = output_lines.find('{')
                if json_start == -1:
                    return {
                        'success': False,
                        'error': "No JSON found in DHL output",
                        'raw_output': result.stdout
                    }
                
                # Extract just the JSON part
                json_output = output_lines[json_start:]
                
                dhl_data = json.loads(json_output)
                if not dhl_data.get('success', False):
                    return {
                        'success': False,
                        'error': dhl_data.get('error', 'Unknown DHL error')
                    }
                
                # Log disruption analysis if present
                disruption_analysis = dhl_data.get('disruption_analysis', {})
                if disruption_analysis:
                    route_disruptions = disruption_analysis.get('route_disruptions', {})
                    time_impact = disruption_analysis.get('time_impact', {})
                    logger.warning("DHL Disruption Analysis:")
                    logger.info(f"Total disruptions on route: {route_disruptions.get('total_count', 0)}")
                    logger.info(f"Road closures: {route_disruptions.get('closures', 0)}")
                    logger.info(f"Added delay: {time_impact.get('added_delay_seconds', 0):.1f}s ({time_impact.get('percentage_increase', 0):.1f}%)")
                
                # Convert DHL JSON output to our route format
                parsed_data = self._convert_dhl_to_route_format(dhl_data)
                parsed_data['success'] = True
                parsed_data['raw_dhl_output'] = dhl_data
                
                return parsed_data
                
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'error': f"Failed to parse DHL JSON output: {str(e)}",
                    'raw_output': result.stdout
                }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': "DHL JSON API computation timed out (30 seconds)"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Error executing DHL JSON API: {str(e)}"
            }
    
    def _convert_dhl_to_route_format(self, dhl_data: Dict) -> Dict:
        """Convert DHL JSON API output to our standard route format"""
        
        # Extract path nodes from DHL output
        path_nodes = dhl_data.get('route', {}).get('path_nodes', [])
        
        # Check if C++ API already provided geometry
        api_geometry = dhl_data.get('route', {}).get('geometry', [])
        
        coordinates = []
        if api_geometry:
            # Use geometry from C++ API (already includes road curves from CSV)
            logger.info(f"Using geometry from C++ DHL API: {len(api_geometry)} edge segments")
            
            # Convert C++ API geometry format to coordinate list
            # API format: [{"from": 1, "to": 2, "coordinates": [[lon, lat], ...]}, ...]
            for segment in api_geometry:
                segment_coords = segment.get('coordinates', [])
                for coord_pair in segment_coords:
                    if len(coord_pair) >= 2:
                        coordinates.append({
                            'lat': coord_pair[1],  # lat is second
                            'lng': coord_pair[0]   # lon is first
                        })
            
            logger.success(f"Extracted {len(coordinates)} GPS coordinates from C++ DHL API geometry")
            
            # Get path summary from edges (for statistics)
            if path_nodes and self.geometry_loader:
                path_summary = self.geometry_loader.get_path_summary(path_nodes)
            else:
                path_summary = {
                    'total_distance_m': dhl_data.get('metrics', {}).get('total_distance_units', 0),
                    'num_segments': len(api_geometry),
                    'num_nodes': len(path_nodes) if path_nodes else 0
                }
                
        elif path_nodes:
            # Fallback: C++ API didn't provide geometry (old version or error)
            logger.warning("C++ DHL API didn't provide geometry, using fallback method")
            logger.info(f"Getting road network coordinates for {len(path_nodes)} DHL nodes")
            
            # Get coordinates following actual edges with geometry from CSV
            coordinates = self.geometry_loader.get_path_coordinates(path_nodes, use_osm_geometry=True)
            
            logger.info(f"DHL route has {len(coordinates)} points following road network (with curves)")
            
            # Validate the path
            is_valid, validation_message = self.geometry_loader.validate_path(path_nodes)
            if not is_valid:
                logger.warning(f"DHL path validation: {validation_message}")
            
            # Get path summary
            path_summary = self.geometry_loader.get_path_summary(path_nodes)
            logger.data(f"DHL path summary: {path_summary['total_distance_m']:.1f}m over {path_summary['num_segments']} segments")
        
        # Create route data structure with enhanced metrics from API
        # CRITICAL FIX: Pass through ALL C++ fields to preserve labeling_info, dhl_update_info, disruptions_summary, etc.
        route_data = {
            'metrics': dhl_data.get('metrics', {}),  # Pass through entire metrics object from C++
            'route': {
                'path_nodes': path_nodes,
                'coordinates': coordinates,
                'polylines': [],
                'geometry': api_geometry,  # Add C++ geometry data with full edge details
                'start_node': dhl_data.get('gps_mapping', {}).get('start_node', 0),
                'dest_node': dhl_data.get('gps_mapping', {}).get('dest_node', 0),
                'route_summary': dhl_data.get('route', {}).get('complete_trace', ''),
                'road_segments': []
            },
            'gps_mapping': dhl_data.get('gps_mapping', {}),
            'disruptions': dhl_data.get('disruptions', {}),
            'disruptions_summary': dhl_data.get('disruptions_summary', {}),  # Pass through disruptions_summary
            'dhl_update_info': dhl_data.get('dhl_update_info', {}),  # Pass through DHL update info
            'disruption_config': dhl_data.get('disruption_config', {}),  # Pass through disruption config
            'alternative_routes': dhl_data.get('alternative_routes', []),  # Pass through alternative routes
            'data_sources': dhl_data.get('data_sources', {}),
            'input': dhl_data.get('input', {}),
            'snap_edges': dhl_data.get('snap_edges', {}),  # Pass through snap edge info
            'algorithm': dhl_data.get('algorithm', 'DHL')  # Pass through algorithm name
        }
        
        # Create polylines from coordinates
        if len(coordinates) >= 2:
            logger.info(f"DHL route has {len(coordinates)} coordinate points")
            
            # Apply minimal interpolation if needed (only for very long gaps)
            from geometry_utils import enhance_route_geometry
            interpolated_coordinates = enhance_route_geometry(
                coordinates, 
                max_distance=100.0,  # Higher threshold since CSV geometry already provides curves
                preserve_node_ids=False
            )
            
            logger.success(f"Final DHL route with {len(interpolated_coordinates)} GPS coordinates")
            
            # Update coordinates with interpolated version
            route_data['route']['coordinates'] = interpolated_coordinates
            
            polyline_coords = []
            for coord in interpolated_coordinates:
                polyline_coords.append([coord['lat'], coord['lng']])
            
            route_data['route']['polylines'] = [{
                'coordinates': polyline_coords,
                'color': '#0066FF',  # Blue for DHL route
                'weight': 5,
                'opacity': 0.8
            }]
        
        # Enhance route with road names and turn-by-turn directions
        route_data = self._enhance_route_with_road_names(route_data)
        
        return route_data
    
    def _extract_coordinates_from_trace(self, complete_trace: str, node_ids: List[int]) -> List[Dict]:
        """Extract GPS coordinates from the complete_trace string"""
        coordinates = []
        
        try:
            # Parse the complete trace to extract coordinates
            # Format: "DHL Route (2184 (14.676090, 121.043758) -> 12130 (14.674896, 121.043668) -> ...)"
            
            # Remove the prefix and suffix
            trace_content = complete_trace
            if trace_content.startswith("DHL Route ("):
                trace_content = trace_content[11:]  # Remove "DHL Route ("
            if trace_content.endswith(")"):
                trace_content = trace_content[:-1]  # Remove final ")"
            
            # Split by " -> " to get individual node entries
            node_entries = trace_content.split(" -> ")
            
            for i, entry in enumerate(node_entries):
                # Parse each entry: "2184 (14.676090, 121.043758)"
                entry = entry.strip()
                
                # Find the node ID (before the first space and parenthesis)
                if "(" in entry and ")" in entry:
                    node_part = entry[:entry.find("(")].strip()
                    coord_start = entry.find("(")
                    coord_end = entry.rfind(")")
                    coord_part = entry[coord_start:coord_end+1]
                    
                    try:
                        node_id = int(node_part)
                        
                        # Extract coordinates from "(lat, lng)"
                        coord_content = coord_part[1:-1]  # Remove parentheses
                        coord_parts = coord_content.split(", ")
                        if len(coord_parts) == 2:
                            lat_str, lng_str = coord_parts
                            lat = float(lat_str)
                            lng = float(lng_str)
                            
                            coordinates.append({
                                'node_id': node_id,
                                'lat': lat,
                                'lng': lng
                            })
                        else:
                            logger.warning(f"Invalid coordinate format in '{entry}': {coord_parts}")
                        
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse entry '{entry}': {e}")
                        continue
                else:
                    logger.warning(f"No coordinates found in entry '{entry}'")
            
            # Verify we got all the nodes we expected
            if len(coordinates) != len(node_ids):
                logger.warning(f"Expected {len(node_ids)} nodes but extracted {len(coordinates)} coordinates")
            
        except Exception as e:
            logger.error(f"Error extracting coordinates from trace: {e}")
            coordinates = []
        
        return coordinates
    
    def _load_coordinates_for_nodes(self, coord_file: str, node_ids: List[int]) -> List[Dict]:
        """Load GPS coordinates for given node IDs"""
        coordinates = []
        
        try:
            # Try different possible paths for the coordinate file
            possible_paths = [
                coord_file,
                os.path.join('data', 'quezon_city_nodes.csv'),
                os.path.join('..', 'data', 'raw', 'quezon_city_nodes.csv'),
                'quezon_city_nodes.csv'
            ]
            
            coord_data = None
            for path in possible_paths:
                if os.path.exists(path):
                    coord_data = {}
                    with open(path, 'r') as f:
                        # Skip header
                        next(f)
                        for line in f:
                            parts = line.strip().split(',')
                            if len(parts) >= 3:
                                node_id = int(parts[0])
                                lat = float(parts[1])
                                lng = float(parts[2])
                                coord_data[node_id] = {'lat': lat, 'lng': lng}
                    break
            
            if coord_data:
                for node_id in node_ids:
                    if node_id in coord_data:
                        coordinates.append({
                            'node_id': node_id,
                            'lat': coord_data[node_id]['lat'],
                            'lng': coord_data[node_id]['lng']
                        })
                    else:
                        logger.warning(f"Node {node_id} not found in coordinate data")
            
        except Exception as e:
            logger.error(f"Error loading coordinates: {e}")
        
        return coordinates
    
    def _create_road_segments(self, coordinates: List[Dict]) -> List[Dict]:
        """Create road segments from coordinates for turn-by-turn directions"""
        segments = []
        
        for i in range(len(coordinates) - 1):
            current = coordinates[i]
            next_coord = coordinates[i + 1]
            
            # Calculate distance between points (simplified)
            lat_diff = next_coord['lat'] - current['lat']
            lng_diff = next_coord['lng'] - current['lng']
            distance = ((lat_diff ** 2 + lng_diff ** 2) ** 0.5) * 111320  # Rough meters
            
            segments.append({
                'from_node': current['node_id'],
                'to_node': next_coord['node_id'],
                'from_lat': current['lat'],
                'from_lng': current['lng'],
                'to_lat': next_coord['lat'],
                'to_lng': next_coord['lng'],
                'distance_m': round(distance, 1),
                'instruction': f"Head from node {current['node_id']} to node {next_coord['node_id']}"
            })
        
        return segments
    
    def _enhance_route_with_road_names(self, route_data: Dict) -> Dict:
        """Enhance route data with road names and turn-by-turn directions using RoadNameMapper"""
        
        if not route_data.get('route', {}).get('path_nodes'):
            return route_data
        
        try:
            path_nodes = route_data['route']['path_nodes']
            
            if len(path_nodes) < 2:
                logger.warning("Path has less than 2 nodes, cannot generate road names")
                return route_data
            
            logger.processing(f"Enhancing DHL route with road names for {len(path_nodes)} nodes...")
            
            # Get road segments with names using RoadNameMapper
            road_segments = self.road_mapper.get_route_with_road_names(path_nodes)
            route_summary = self.road_mapper.get_route_summary_text(path_nodes)
            turn_directions = self.road_mapper.get_turn_by_turn_directions(path_nodes)
            
            # Update the route data with enhanced road information
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
            
            # Update existing road_segments with road names if they exist
            if route_data['route'].get('coordinates'):
                for i, segment in enumerate(route_data['route'].get('road_segments', [])):
                    if i < len(road_segments):
                        # Replace the generic instruction with road name instruction
                        segment.update({
                            'road_name': road_segments[i]['road_name'],
                            'highway_type': road_segments[i]['highway_type'],
                            'instruction': road_segments[i]['instruction']
                        })
            
            logger.success(f"Enhanced DHL route with {len(road_segments)} road segments")
            logger.info(f"Route summary: {route_summary}")
            
        except Exception as e:
            logger.warning(f"Failed to enhance DHL route with road names: {e}")
        
        return route_data
    
    def get_turn_by_turn_directions(self, route_data: Dict) -> List[str]:
        """Get turn-by-turn directions from enhanced route data"""
        if not route_data.get('success', False):
            return []
        
        return route_data.get('route', {}).get('turn_by_turn_directions', [])
    
    def get_route_summary_text(self, route_data: Dict) -> str:
        """Get human-readable route summary with road names"""
        if not route_data.get('success', False):
            return "Route computation failed"
        
        return route_data.get('route', {}).get('route_summary', 'No route summary available')
    
    def get_detailed_route_info(self, route_data: Dict) -> Dict:
        """Get detailed route information including road segments and directions"""
        if not route_data.get('success', False):
            return {'error': 'Route computation failed'}
        
        route = route_data.get('route', {})
        
        return {
            'success': True,
            'path_nodes': route.get('path_nodes', []),
            'road_segments': route.get('road_segments', []),
            'turn_by_turn_directions': route.get('turn_by_turn_directions', []),
            'route_summary': route.get('route_summary', ''),
            'display_format': route.get('display_format', {}),
            'total_nodes': len(route.get('path_nodes', [])),
            'total_road_segments': len(route.get('road_segments', [])),
            'total_instructions': len(route.get('turn_by_turn_directions', []))
        }
    
    def get_route_polylines_for_gmaps(self, route_data: Dict) -> List[Dict]:
        """
        Convert route data to Google Maps polyline format
        """
        if not route_data.get('success', False):
            return []
        
        polylines = []
        
        # Main route polyline
        if route_data['route']['polylines']:
            for polyline in route_data['route']['polylines']:
                polylines.append({
                    'path': [{'lat': coord[0], 'lng': coord[1]} for coord in polyline['coordinates']],
                    'strokeColor': polyline['color'],
                    'strokeOpacity': polyline['opacity'],
                    'strokeWeight': polyline['weight'],
                    'geodesic': True
                })
        
        return polylines
    
    def get_route_summary(self, route_data: Dict) -> Dict:
        """Get summary information for display - enhanced for new JSON API"""
        if not route_data.get('success', False):
            return {'error': route_data.get('error', 'Unknown error')}
        
        metrics = route_data.get('metrics', {})
        labeling_info = metrics.get('labeling_info', {})
        
        summary = {
            'algorithm': 'DHL (Dual-Hierarchy Labelling)',
            'routing_mode': metrics.get('routing_mode', 'DHL'),
            'query_time_ms': metrics.get('query_time_ms', 0),
            'query_time_microseconds': metrics.get('query_time_microseconds', 0),
            'labeling_time_ms': metrics.get('labeling_time_ms', 0),
            'labeling_size_bytes': labeling_info.get('index_size_bytes', 0.0) / 1024,
            'total_distance_units': metrics.get('total_distance_units', 0),
            'path_length': metrics.get('path_length', 0),
            'hoplinks_examined': metrics.get('hoplinks_examined', 0),
            'uses_disruptions': metrics.get('uses_disruptions', False),
            
            # DHL-specific metrics
            'index_height': metrics.get('index_height', 0),
            'avg_cut_size': round(metrics.get('avg_cut_size', 0), 2),
            'total_labels': metrics.get('total_labels', 0),
            'graph_nodes': metrics.get('graph_nodes', 0),
            'graph_edges': metrics.get('graph_edges', 0),
            'edge_count': len(route_data['route']['coordinates']) - 1 if len(route_data['route']['coordinates']) > 1 else 0,
            
            # Data source information from API
            'data_sources': route_data.get('data_sources', {}),
            'labeling_efficiency': {
                'labels_per_node': round(metrics.get('total_labels', 0) / max(metrics.get('graph_nodes', 1), 1), 2),
                'bytes_per_node': round(metrics.get('labeling_size_bytes', 0) / max(metrics.get('graph_nodes', 1), 1), 2)
            }
        }
        logger.data(f"DHL route summary: {summary}")
        return summary
    
    def compare_routes(self, start_lat: float, start_lng: float, 
                      dest_lat: float, dest_lng: float) -> Dict:
        """Compare routes with and without disruptions"""
        try:
            # Compute route without disruptions
            logger.processing("Computing DHL route without disruptions...")
            base_route = self.compute_route(start_lat, start_lng, dest_lat, dest_lng, use_disruptions=False)
            
            # Compute route with disruptions
            logger.processing("Computing DHL route with disruptions...")
            disrupted_route = self.compute_route(start_lat, start_lng, dest_lat, dest_lng, use_disruptions=True)
            
            if not base_route['success']:
                return {
                    'success': False,
                    'error': f"Base route failed: {base_route['error']}"
                }
            
            if not disrupted_route['success']:
                return {
                    'success': False,
                    'error': f"Disrupted route failed: {disrupted_route['error']}"
                }
            
            # Create comparison result
            comparison = {
                'success': True,
                'algorithm': 'DHL Comparison',
                'routes': {
                    'base': {
                        'polylines': self.get_route_polylines_for_gmaps(base_route),
                        'summary': self.get_route_summary(base_route),
                        'name': 'DHL Base Route',
                        'color': '#0066FF'
                    },
                    'disrupted': {
                        'polylines': self.get_route_polylines_for_gmaps(disrupted_route),
                        'summary': self.get_route_summary(disrupted_route),
                        'name': 'DHL Disrupted Route',
                        'color': '#FF6600'
                    }
                },
                'comparison_metrics': {
                    'distance_difference_units': (
                        disrupted_route['metrics']['total_distance_units'] - 
                        base_route['metrics']['total_distance_units']
                    ),
                    'query_time_difference_ms': (
                        disrupted_route['metrics']['query_time_ms'] - 
                        base_route['metrics']['query_time_ms']
                    ),
                    'path_length_difference': (
                        disrupted_route['metrics']['path_length'] - 
                        base_route['metrics']['path_length']
                    ),
                    'blocked_edges_count': len(disrupted_route.get('disruptions', {}).get('blocked_edges', [])),
                    'blocked_nodes_count': len(disrupted_route.get('disruptions', {}).get('blocked_nodes', []))
                }
            }
            
            return comparison
            
        except Exception as e:
            return {
                'success': False,
                'error': f"DHL route comparison error: {str(e)}"
            }

# Test function
if __name__ == "__main__":
    # Test with automatic path detection
    logger.processing("Testing DHL Router with automatic path detection...")
    
    try:
        router = DHLRouter()  # No path specified - will auto-detect
        
        logger.processing("Testing DHL Router with new JSON API...")
        result = router.compute_route(14.6760, 121.0437, 14.6348, 121.0480, use_disruptions=False)
        
        if result['success']:
            logger.success("DHL JSON API route computation successful!")
            logger.info(f"Metrics: {result['metrics']}")
            logger.info(f"Route nodes: {len(result['route']['path_nodes'])}")
            logger.info(f"Coordinates: {len(result['route']['coordinates'])}")
            
            # Test polyline generation
            polylines = router.get_route_polylines_for_gmaps(result)
            logger.info(f"Generated {len(polylines)} polylines for Google Maps")
            
            # Test summary
            summary = router.get_route_summary(result)
            logger.info(f"Route summary: {summary}")
            
            # Test NEW road name and turn-by-turn direction features
            logger.processing("Testing road name mapping and turn-by-turn directions...")
            
            # Get turn-by-turn directions
            directions = router.get_turn_by_turn_directions(result)
            logger.success(f"Generated {len(directions)} turn-by-turn directions:")
            for i, direction in enumerate(directions[:5]):  # Show first 5 directions
                logger.info(f"  {direction}")
            if len(directions) > 5:
                logger.info(f"  ... and {len(directions) - 5} more directions")
            
            # Get route summary with road names
            route_summary = router.get_route_summary_text(result)
            logger.info("Route summary with road names:")
            logger.info(f"  {route_summary}")
            
            # Get detailed route information
            detailed_info = router.get_detailed_route_info(result)
            if detailed_info.get('success'):
                logger.data("Detailed route information:")
                logger.info(f"  Total nodes: {detailed_info['total_nodes']}")
                logger.info(f"  Total road segments: {detailed_info['total_road_segments']}")
                logger.info(f"  Total instructions: {detailed_info['total_instructions']}")
                
                # Show some road segments
                road_segments = detailed_info.get('road_segments', [])
                if road_segments:
                    logger.info("Road segments preview:")
                    for i, segment in enumerate(road_segments[:3]):  # Show first 3 segments
                        logger.info(f"  {i+1}. {segment.get('road_name', 'Unknown')} ({segment.get('highway_type', 'unknown')})")
                        logger.info(f"     {segment.get('instruction', 'No instruction')}")
                    if len(road_segments) > 3:
                        logger.info(f"  ... and {len(road_segments) - 3} more segments")
            
            # Test comparison
            logger.processing("Testing route comparison...")
            comparison = router.compare_routes(14.6760, 121.0437, 14.6507, 121.0323)
            if comparison['success']:
                logger.success("Route comparison successful!")
                logger.info(f"Comparison metrics: {comparison['comparison_metrics']}")
            else:
                logger.error(f"Route comparison failed: {comparison['error']}")
        else:
            logger.error("DHL JSON API route computation failed:")
            logger.error(result['error'])
            
    except FileNotFoundError as e:
        logger.error(f"DHL Router initialization failed: {e}")
        logger.info("Please build the DHL project first.")
        logger.info("Build command: cd ../DHL && make dhl_routing_json_api")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")