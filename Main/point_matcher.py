"""
Point Matcher for Flow and Incident Data

This script matches incident points with flow route points based on geographic proximity.
It uses the Haversine formula to calculate distances between coordinate pairs.
"""

import json
import math
from typing import List, Dict, Tuple
from dataclasses import dataclass

from console_formatter import get_logger

logger = get_logger("PointMatcher")


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
    logger.info("="*80)
    logger.info("POINT MATCHING RESULTS")
    logger.info("="*80)
    
    logger.data(f"Statistics:")
    logger.data(f"  Total flow points: {results['total_flow_points']}")
    logger.data(f"  Total incident points: {results['total_incident_points']}")
    logger.data(f"  Matched incident records: {results['matched_incidents']}")
    logger.data(f"  Total point matches: {results['total_matches']}")
    
    logger.info(f"{'-'*80}")
    logger.info("Detailed Matches:")
    logger.info(f"{'-'*80}")
    
    for i, match in enumerate(results['matches'], 1):
        logger.data(f"Match #{i}:")
        logger.data(f"  Incident ID: {match['incident_id']}")
        logger.data(f"  Incident Type: {match['incident_type']}")
        logger.data(f"  Incident Description: {match['incident_description']}")
        logger.data(f"  Incident Coordinates: {match['incident_point']}")
        logger.data(f"  Flow Location: {match['flow_location']}")
        logger.data(f"  Flow Coordinates: {match['flow_point']}")
        logger.data(f"  Distance: {match['distance_meters']} meters")
    
    logger.info(f"{'-'*80}")
    logger.info("Matches per Incident:")
    logger.info(f"{'-'*80}")
    for incident_id, count in results['incident_matches_count'].items():
        logger.data(f"  Incident {incident_id}: {count} match(es)")
    
    logger.success(f"SUMMARY: {results['total_matches']} total matches found")


def main():
    """Main function to load data and perform matching"""
    
    # File paths
    flow_file = '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main/data/sample/flow.json'
    incident_file = '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main/data/sample/incidents.json'
    
    try:
        # Load JSON files
        logger.processing("Loading flow data...")
        with open(flow_file, 'r') as f:
            flow_data = json.load(f)
        
        logger.processing("Loading incident data...")
        with open(incident_file, 'r') as f:
            incident_data = json.load(f)
        
        # Extract points
        logger.processing("Extracting flow points...")
        flow_points = extract_flow_points(flow_data)
        
        logger.processing("Extracting incident points...")
        incident_points = extract_incident_points(incident_data)
        
        # Perform matching (distance threshold: 200 meters)
        logger.processing("Matching points (threshold: 5 meters)...")
        results = find_matches(flow_points, incident_points, distance_threshold=5.0)
        
        # Print results
        print_results(results)
        
    except FileNotFoundError as e:
        logger.error(f"File not found - {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON - {e}")
    except Exception as e:
        logger.error(f"{e}")


if __name__ == "__main__":
    main()
