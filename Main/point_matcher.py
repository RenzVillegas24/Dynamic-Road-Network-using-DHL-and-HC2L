"""
Point Matcher for Flow and Incident Data

This script matches incident points with flow route points based on geographic proximity.
It uses the Haversine formula to calculate distances between coordinate pairs.
"""

import json
import math
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class Point:
    """Represents a geographic point with latitude and longitude"""
    lat: float
    lng: float
    
    def __repr__(self):
        return f"Point({self.lat}, {self.lng})"


def haversine_distance(point1: Point, point2: Point) -> float:
    """
    Calculate the great circle distance between two points on the earth (in meters).
    
    Args:
        point1: First point with lat/lng
        point2: Second point with lat/lng
        
    Returns:
        Distance in meters
    """
    lat1, lon1 = math.radians(point1.lat), math.radians(point1.lng)
    lat2, lon2 = math.radians(point2.lat), math.radians(point2.lng)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in meters
    earth_radius = 6371000
    
    return earth_radius * c


def extract_flow_points(flow_data: Dict) -> List[Tuple[Point, str]]:
    """
    Extract all points from flow data.
    
    Args:
        flow_data: Parsed flow JSON data
        
    Returns:
        List of tuples (Point, location_description)
    """
    points = []
    
    for result in flow_data.get('results', []):
        location = result.get('location', {})
        description = location.get('description', 'Unknown')
        shape = location.get('shape', {})
        
        for link in shape.get('links', []):
            for point_data in link.get('points', []):
                point = Point(lat=point_data['lat'], lng=point_data['lng'])
                points.append((point, description))
    
    return points


def extract_incident_points(incident_data: Dict) -> List[Tuple[Point, Dict]]:
    """
    Extract all points from incident data.
    
    Args:
        incident_data: Parsed incident JSON data
        
    Returns:
        List of tuples (Point, incident_details)
    """
    points = []
    
    for result in incident_data.get('results', []):
        location = result.get('location', {})
        shape = location.get('shape', {})
        incident_details = result.get('incidentDetails', {})
        
        for link in shape.get('links', []):
            for point_data in link.get('points', []):
                point = Point(lat=point_data['lat'], lng=point_data['lng'])
                points.append((point, incident_details))
    
    return points


def find_matches(flow_points: List[Tuple[Point, str]], 
                 incident_points: List[Tuple[Point, Dict]],
                 distance_threshold: float = 100.0) -> Dict:
    """
    Match incident points with flow points based on proximity.
    
    Args:
        flow_points: List of (Point, description) tuples from flow data
        incident_points: List of (Point, incident_details) tuples from incident data
        distance_threshold: Maximum distance in meters to consider as a match (default: 100m)
        
    Returns:
        Dictionary containing matches and statistics
    """
    matches = []
    incident_matches_count = {}
    
    for incident_point, incident_details in incident_points:
        best_match = None
        best_distance = float('inf')
        
        for flow_point, flow_description in flow_points:
            distance = haversine_distance(incident_point, flow_point)
            
            if distance < distance_threshold and distance < best_distance:
                best_distance = distance
                best_match = (flow_point, flow_description, distance)
        
        if best_match:
            flow_point, flow_description, distance = best_match
            incident_id = incident_details.get('id', 'Unknown')
            
            match_info = {
                'incident_id': incident_id,
                'incident_type': incident_details.get('type', 'Unknown'),
                'incident_description': incident_details.get('description', {}).get('value', 'N/A'),
                'incident_point': (incident_point.lat, incident_point.lng),
                'flow_location': flow_description,
                'flow_point': (flow_point.lat, flow_point.lng),
                'distance_meters': round(best_distance, 2)
            }
            matches.append(match_info)
            
            # Count matches per incident
            incident_matches_count[incident_id] = incident_matches_count.get(incident_id, 0) + 1
    
    return {
        'matches': matches,
        'total_incident_points': len(incident_points),
        'total_flow_points': len(flow_points),
        'matched_incidents': len(incident_matches_count),
        'total_matches': len(matches),
        'incident_matches_count': incident_matches_count
    }


def print_results(results: Dict):
    """Print the matching results in a formatted way"""
    print("\n" + "="*80)
    print("POINT MATCHING RESULTS")
    print("="*80)
    
    print(f"\nStatistics:")
    print(f"  Total flow points: {results['total_flow_points']}")
    print(f"  Total incident points: {results['total_incident_points']}")
    print(f"  Matched incident records: {results['matched_incidents']}")
    print(f"  Total point matches: {results['total_matches']}")
    
    print(f"\n{'-'*80}")
    print("Detailed Matches:")
    print(f"{'-'*80}\n")
    
    for i, match in enumerate(results['matches'], 1):
        print(f"Match #{i}:")
        print(f"  Incident ID: {match['incident_id']}")
        print(f"  Incident Type: {match['incident_type']}")
        print(f"  Incident Description: {match['incident_description']}")
        print(f"  Incident Coordinates: {match['incident_point']}")
        print(f"  Flow Location: {match['flow_location']}")
        print(f"  Flow Coordinates: {match['flow_point']}")
        print(f"  Distance: {match['distance_meters']} meters")
        print()
    
    print(f"{'-'*80}")
    print("Matches per Incident:")
    print(f"{'-'*80}")
    for incident_id, count in results['incident_matches_count'].items():
        print(f"  Incident {incident_id}: {count} match(es)")
    
    print("\n" + "="*80)
    print(f"SUMMARY: {results['total_matches']} total matches found")
    print("="*80 + "\n")


def main():
    """Main function to load data and perform matching"""
    
    # File paths
    flow_file = '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main/data/sample/flow.json'
    incident_file = '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main/data/sample/incidents.json'
    
    try:
        # Load JSON files
        print("Loading flow data...")
        with open(flow_file, 'r') as f:
            flow_data = json.load(f)
        
        print("Loading incident data...")
        with open(incident_file, 'r') as f:
            incident_data = json.load(f)
        
        # Extract points
        print("Extracting flow points...")
        flow_points = extract_flow_points(flow_data)
        
        print("Extracting incident points...")
        incident_points = extract_incident_points(incident_data)
        
        # Perform matching (distance threshold: 200 meters)
        print("Matching points (threshold: 5 meters)...")
        results = find_matches(flow_points, incident_points, distance_threshold=5.0)
        
        # Print results
        print_results(results)
        
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
