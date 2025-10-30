# dhc2l_router.py - D-HC2L Routing Integration
import subprocess
import json
import os
import re
from typing import Dict, List, Tuple, Optional

class DHC2LRouter:
    def __init__(self, cpp_executable_path: str):
        """Initialize D-HC2L router with path to C++ executable"""
        self.cpp_executable = cpp_executable_path
        if not os.path.exists(cpp_executable_path):
            raise FileNotFoundError(f"C++ executable not found: {cpp_executable_path}")
    
    def compute_route(self, start_lat: float, start_lng: float, 
                     dest_lat: float, dest_lng: float, threshold: float = 0.5, 
                     use_disruptions: bool = False) -> Dict:
        """
        Compute route using D-HC2L algorithm via GPS JSON API
        Returns route data with polylines and metrics
        """
        try:
            # Call GPS JSON API (which implements HC2L Dynamic algorithm)
            cmd = [
                self.cpp_executable,
                str(start_lat), str(start_lng),
                str(dest_lat), str(dest_lng),
                "true" if use_disruptions else "false",
                str(threshold)
            ]
            
            print(f"Executing D-HC2L GPS JSON API: {' '.join(cmd)}")
            
            # Get the directory containing the executable
            exec_dir = os.path.dirname(self.cpp_executable)
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                cwd=exec_dir
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f"D-HC2L GPS JSON API failed: {result.stderr}",
                    'stdout': result.stdout
                }
            
            # Parse JSON output from GPS API
            try:
                # The GPS API outputs initialization messages followed by JSON
                output_lines = result.stdout.strip()
                
                # Find the start of JSON (first '{' character)
                json_start = output_lines.find('{')
                if json_start == -1:
                    return {
                        'success': False,
                        'error': "No JSON found in D-HC2L output",
                        'raw_output': result.stdout
                    }
                
                # Extract just the JSON part
                json_output = output_lines[json_start:]
                
                hc2l_data = json.loads(json_output)
                if not hc2l_data.get('success', False):
                    return {
                        'success': False,
                        'error': hc2l_data.get('error', 'Unknown D-HC2L error')
                    }
                
                # Convert HC2L JSON output to our route format
                parsed_data = self._convert_hc2l_to_route_format(hc2l_data)
                parsed_data['success'] = True
                parsed_data['raw_hc2l_output'] = hc2l_data
                
                return parsed_data
                
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'error': f"Failed to parse D-HC2L JSON output: {str(e)}",
                    'raw_output': result.stdout
                }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': "D-HC2L route computation timed out (30 seconds)"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Error executing D-HC2L route computation: {str(e)}"
            }
    
    def _convert_hc2l_to_route_format(self, hc2l_data: Dict) -> Dict:
        """Convert HC2L JSON API output to our standard route format"""
        
        # Extract coordinates from path nodes using GPS mapping info
        coordinates = []
        path_nodes = hc2l_data.get('route', {}).get('path_nodes', [])
        
        # Try to extract coordinates from input GPS points
        input_data = hc2l_data.get('input', {})
        gps_mapping = hc2l_data.get('gps_mapping', {})
        
        if path_nodes and input_data:
            # Create basic coordinate data (start and end points)
            start_lat = input_data.get('start_lat', 0)
            start_lng = input_data.get('start_lng', 0)
            dest_lat = input_data.get('dest_lat', 0)
            dest_lng = input_data.get('dest_lng', 0)
            start_node = gps_mapping.get('start_node', 0)
            dest_node = gps_mapping.get('dest_node', 0)
            
            # In a full implementation, you'd load coordinates for all nodes
            coordinates = [
                {'node_id': start_node, 'lat': start_lat, 'lng': start_lng},
                {'node_id': dest_node, 'lat': dest_lat, 'lng': dest_lng}
            ]
        
        # Create route data structure
        route_data = {
            'metrics': {
                'algorithm': hc2l_data.get('algorithm', 'HC2L Dynamic'),
                'query_time_microseconds': hc2l_data.get('metrics', {}).get('query_time_microseconds', 0),
                'query_time_ms': hc2l_data.get('metrics', {}).get('query_time_ms', 0),
                'total_distance_meters': hc2l_data.get('metrics', {}).get('total_distance_meters', 0),
                'path_length': hc2l_data.get('metrics', {}).get('path_length', 0),
                'routing_mode': hc2l_data.get('metrics', {}).get('routing_mode', 'BASE'),
                'uses_disruptions': hc2l_data.get('metrics', {}).get('uses_disruptions', False),
                'tau_threshold': hc2l_data.get('metrics', {}).get('tau_threshold', 0.5),
                # Additional metrics for comparison
                'distance_change_percentage': hc2l_data.get('metrics', {}).get('distance_change_percentage', 0),
                'base_distance_meters': hc2l_data.get('metrics', {}).get('base_distance_meters', 0),
                'distance_difference_meters': hc2l_data.get('metrics', {}).get('distance_difference_meters', 0),
                'had_disruptions': hc2l_data.get('metrics', {}).get('had_disruptions', False)
            },
            'route': {
                'path_nodes': path_nodes,
                'coordinates': coordinates,
                'polylines': [],
                'start_node': gps_mapping.get('start_node', 0),
                'dest_node': gps_mapping.get('dest_node', 0),
                'route_summary': hc2l_data.get('route', {}).get('complete_trace', ''),
                'edges': self._create_edges_from_nodes(path_nodes)
            },
            'gps_mapping': gps_mapping,
            'input': input_data
        }
        
        # Create polylines from coordinates if we have them
        if len(coordinates) >= 2:
            polyline_coords = []
            for coord in coordinates:
                polyline_coords.append([coord['lat'], coord['lng']])
            
            route_data['route']['polylines'] = [{
                'coordinates': polyline_coords,
                'color': '#FF0000',  # Red for D-HC2L route
                'weight': 5,
                'opacity': 0.8
            }]
        
        return route_data
    
    def _create_edges_from_nodes(self, path_nodes: List[int]) -> List[Dict]:
        """Create edge list from path nodes"""
        edges = []
        for i in range(len(path_nodes) - 1):
            edges.append({
                'edge_number': i + 1,
                'source_node': path_nodes[i],
                'target_node': path_nodes[i + 1]
            })
        return edges
    
    def _parse_cpp_output(self, output: str) -> Dict:
        """Parse C++ output into structured data"""
        
        data = {
            'metrics': {},
            'route': {
                'edges': [],
                'coordinates': [],
                'polylines': []
            },
            'info': {},
            'raw_output': output
        }
        
        lines = output.strip().split('\n')
        
        # Parse metrics section
        for line in lines:
            if 'LABELING_SIZE_MB:' in line:
                data['metrics']['labeling_size_mb'] = float(line.split(':')[1].strip())
            elif 'QUERY_TIME_MICROSECONDS:' in line:
                data['metrics']['query_time_microseconds'] = int(line.split(':')[1].strip())
            elif 'LABELING_TIME_SECONDS:' in line:
                data['metrics']['labeling_time_seconds'] = float(line.split(':')[1].strip())
            elif 'NUMBER_OF_NODES:' in line:
                data['metrics']['number_of_nodes'] = int(line.split(':')[1].strip())
            elif 'Total Distance:' in line:
                # Extract distance value from "Total Distance: 725 meters"
                match = re.search(r'Total Distance:\s*(\d+)\s*meters', line)
                if match:
                    data['metrics']['total_distance_meters'] = int(match.group(1))
            elif 'Estimated Time:' in line:
                # Extract time from "Estimated Time: 1.4 minutes"
                match = re.search(r'Estimated Time:\s*([\d.]+)\s*minutes', line)
                if match:
                    data['metrics']['estimated_time_minutes'] = float(match.group(1))
            elif 'Uses Disruptions:' in line:
                data['metrics']['uses_disruptions'] = 'YES' in line
        
        # Parse step-by-step edges
        edge_section = False
        node_section = False
        
        for line in lines:
            if 'STEP_BY_STEP_EDGES:' in line:
                edge_section = True
                continue
            elif 'AVOIDED_DISRUPTIONS:' in line:
                edge_section = False
                continue
            elif 'NODE_GPS_COORDINATES:' in line:
                node_section = True
                continue
            elif '============================================================' in line:
                edge_section = False
                node_section = False
                continue
            
            if edge_section and 'Edge' in line and '->' in line:
                # Parse "Edge 1: Node 10143 -> Node 61"
                match = re.search(r'Edge\s+(\d+):\s*Node\s+(\d+)\s*->\s*Node\s+(\d+)', line)
                if match:
                    edge_num = int(match.group(1))
                    source_node = int(match.group(2))
                    target_node = int(match.group(3))
                    
                    data['route']['edges'].append({
                        'edge_number': edge_num,
                        'source_node': source_node,
                        'target_node': target_node
                    })
            
            if node_section and 'Node' in line and ':' in line:
                # Parse "Node 10143: (14.649067, 121.048151)"
                match = re.search(r'Node\s+(\d+):\s*\(([\d.-]+),\s*([\d.-]+)\)', line)
                if match:
                    node_id = int(match.group(1))
                    lat = float(match.group(2))
                    lng = float(match.group(3))
                    
                    data['route']['coordinates'].append({
                        'node_id': node_id,
                        'lat': lat,
                        'lng': lng
                    })
        
        # Create polylines from coordinates
        if len(data['route']['coordinates']) >= 2:
            polyline_coords = []
            for coord in data['route']['coordinates']:
                polyline_coords.append([coord['lat'], coord['lng']])
            
            data['route']['polylines'] = [{
                'coordinates': polyline_coords,
                'color': '#FF0000',  # Red for D-HC2L route
                'weight': 5,
                'opacity': 0.8
            }]
        
        # Parse additional info
        for line in lines:
            if 'Input GPS Coordinates:' in line:
                data['info']['has_coordinates'] = True
            elif 'Distance:' in line and 'meters' in line and 'Input GPS' not in line:
                # Extract straight-line distance
                match = re.search(r'Distance:\s*(\d+)\s*meters', line)
                if match:
                    data['info']['straight_line_distance'] = int(match.group(1))
        
        return data
    
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
        """Get summary information for display"""
        if not route_data.get('success', False):
            return {'error': route_data.get('error', 'Unknown error')}
        
        metrics = route_data.get('metrics', {})
        
        summary = {
            'algorithm': 'D-HC2L Dynamic',
            'labeling_size_mb': metrics.get('labeling_size_mb', 0),
            'query_time_ms': metrics.get('query_time_microseconds', 0) / 1000,
            'labeling_time_sec': metrics.get('labeling_time_seconds', 0),
            'total_distance_m': metrics.get('total_distance_meters', 0),
            'estimated_time_min': metrics.get('estimated_time_minutes', 0),
            'number_of_nodes': metrics.get('number_of_nodes', 0),
            'uses_disruptions': metrics.get('uses_disruptions', False),
            'edge_count': len(route_data['route']['edges'])
        }
        
        return summary

# Test function
if __name__ == "__main__":
    # Test with the D-HC2L JSON API (GPS HC2L JSON API)
    dhc2l_json_api = "../core/hc2l_dynamic/build/gps_routing_json_api"
    
    if os.path.exists(dhc2l_json_api):
        router = DHC2LRouter(dhc2l_json_api)
        
        print("Testing D-HC2L Router with GPS JSON API...")
        
        # Test coordinates in Quezon City, Philippines
        test_start_lat = 14.6760
        test_start_lng = 121.0437
        test_dest_lat = 14.6348
        test_dest_lng = 121.0480
        test_threshold = 0.5
        
        print(f"Test route: ({test_start_lat}, {test_start_lng}) → ({test_dest_lat}, {test_dest_lng})")
        print(f"Tau threshold: {test_threshold}")
        
        # Test basic route computation (without disruptions)
        print("\n Testing basic route computation...")
        result = router.compute_route(test_start_lat, test_start_lng, test_dest_lat, test_dest_lng, test_threshold, use_disruptions=False)
        
        if result['success']:
            print("D-HC2L basic route computation successful!")
            print(f"   Algorithm: {result['metrics']['algorithm']}")
            print(f"   Query time: {result['metrics']['query_time_ms']:.3f} ms")
            print(f"   Distance: {result['metrics']['total_distance_meters']} meters")
            print(f"   Path length: {result['metrics']['path_length']} nodes")
            print(f"   Routing mode: {result['metrics']['routing_mode']}")
            print(f"   Start node: {result['route']['start_node']}")
            print(f"   Dest node: {result['route']['dest_node']}")
            print(f"   Edge count: {len(result['route']['edges'])}")
            
            # Test polyline generation
            polylines = router.get_route_polylines_for_gmaps(result)
            print(f"   Generated {len(polylines)} polylines for Google Maps")
            
            # Test summary
            summary = router.get_route_summary(result)
            print(f"   Route summary algorithm: {summary['algorithm']}")
            
        else:
            print("D-HC2L basic route computation failed:")
            print(f"   Error: {result['error']}")
            if 'raw_output' in result:
                print(f"   Raw output: {result['raw_output'][:200]}...")
        
        # Test route computation with disruptions
        print("\n🧪 Testing route computation with disruptions...")
        disrupted_result = router.compute_route(test_start_lat, test_start_lng, test_dest_lat, test_dest_lng, test_threshold, use_disruptions=True)
        
        if disrupted_result['success']:
            print("D-HC2L disrupted route computation successful!")
            print(f"   Algorithm: {disrupted_result['metrics']['algorithm']}")
            print(f"   Query time: {disrupted_result['metrics']['query_time_ms']:.3f} ms")
            print(f"   Distance: {disrupted_result['metrics']['total_distance_meters']} meters")
            print(f"   Path length: {disrupted_result['metrics']['path_length']} nodes")
            print(f"   Routing mode: {disrupted_result['metrics']['routing_mode']}")
            print(f"   Uses disruptions: {disrupted_result['metrics']['uses_disruptions']}")
            print(f"   Had disruptions: {disrupted_result['metrics']['had_disruptions']}")
            
            if disrupted_result['metrics']['had_disruptions']:
                print(f"   Base distance: {disrupted_result['metrics']['base_distance_meters']} meters")
                print(f"   Distance difference: {disrupted_result['metrics']['distance_difference_meters']} meters")
                print(f"   Distance change: {disrupted_result['metrics']['distance_change_percentage']:.1f}%")
            
            # Test polyline generation for disrupted route
            disrupted_polylines = router.get_route_polylines_for_gmaps(disrupted_result)
            print(f"   Generated {len(disrupted_polylines)} disrupted polylines for Google Maps")
            
        else:
            print("D-HC2L disrupted route computation failed:")
            print(f"   Error: {disrupted_result['error']}")
            if 'raw_output' in disrupted_result:
                print(f"   Raw output: {disrupted_result['raw_output'][:200]}...")
        
        # Test different tau thresholds
        print("\n🧪 Testing different tau threshold values...")
        test_thresholds = [0.1, 0.3, 0.7, 1.0]
        
        for tau in test_thresholds:
            print(f"\n   Testing tau = {tau}...")
            tau_result = router.compute_route(test_start_lat, test_start_lng, test_dest_lat, test_dest_lng, tau, use_disruptions=False)
            
            if tau_result['success']:
                print(f"  Tau {tau}: {tau_result['metrics']['query_time_ms']:.3f} ms, {tau_result['metrics']['total_distance_meters']} meters")
            else:
                print(f"  Tau {tau}: {tau_result['error']}")
        
        print("\n🎯 D-HC2L Router Testing Complete!")
        print("Summary:")
        print("- D-HC2L uses GPS coordinates directly (no need for node ID conversion)")
        print("- Supports disruption-aware routing with tau threshold parameter")
        print("- Returns JSON format compatible with web interface")
        print("- Generates polylines for Google Maps visualization")
        print("- Provides comprehensive routing metrics and comparisons")
        
    else:
        print(f"D-HC2L GPS JSON API executable not found at: {dhc2l_json_api}")
        print("Please build the HC2L project first:")
        print("   cd /home/lance/Documents/commissions/LazyHC2L")
        print("   cmake -S core/hc2l_dynamic -B core/hc2l_dynamic/build")
        print("   cmake --build core/hc2l_dynamic/build")
        print("Or run the CMake build task in VS Code")
        
        # Try to find alternative paths
        possible_paths = [
            "../core/hc2l_dynamic/build/gps_routing_json_api",
            "./core/hc2l_dynamic/build/gps_routing_json_api",
            "/app/core/hc2l_dynamic/build/gps_routing_json_api"  # Docker path
        ]
        
        print("\nLooking for alternative paths:")
        for path in possible_paths:
            full_path = os.path.abspath(path)
            if os.path.exists(full_path):
                print(f"   Found alternative: {full_path}")
                print(f"   You can use: router = DHC2LRouter('{full_path}')")
            else:
                print(f" Not found: {full_path}")