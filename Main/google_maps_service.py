"""
Google Maps Directions API Integration for Route Comparison
Fetches routes from Google Maps and computes comparison metrics
"""

import os
import requests
import polyline
import numpy as np
from typing import Dict, List, Tuple, Optional
from config import Config
from scipy.spatial.distance import directed_hausdorff


class GoogleMapsService:
    """Service for fetching and comparing routes with Google Maps"""
    
    def __init__(self):
        self.api_key = Config.GOOGLE_MAPS_API_KEY
        if not self.api_key:
            print("⚠️  Warning: Google Maps API key not set")
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"
    
    def get_directions(self, start_lat: float, start_lng: float, 
                       dest_lat: float, dest_lng: float) -> Optional[Dict]:
        """
        Fetch directions from Google Maps Directions API
        
        Returns:
            Dict with route data including polyline, distance, duration
        """
        if not self.api_key:
            return {
                'success': False,
                'error': 'Google Maps API key not configured'
            }
        
        params = {
            'origin': f"{start_lat},{start_lng}",
            'destination': f"{dest_lat},{dest_lng}",
            'key': self.api_key,
            'mode': 'driving',
            'alternatives': 'false',
            'units': 'metric'
        }
        
        try:
            print(f"🗺️  Fetching Google Maps route...")
            print(f"   Origin: ({start_lat}, {start_lng})")
            print(f"   Destination: ({dest_lat}, {dest_lng})")
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'OK':
                error_msg = data.get('error_message', data.get('status'))
                print(f"❌ Google Maps API error: {error_msg}")
                return {
                    'success': False,
                    'error': f"Google Maps API: {error_msg}"
                }
            
            # Extract route information
            route = data['routes'][0]
            leg = route['legs'][0]
            
            # Decode polyline to get coordinates
            encoded_polyline = route['overview_polyline']['points']
            decoded_coords = polyline.decode(encoded_polyline)
            
            # Convert to [lat, lng] format
            coordinates = [[lat, lng] for lat, lng in decoded_coords]
            
            result = {
                'success': True,
                'coordinates': coordinates,
                'distance_meters': leg['distance']['value'],
                'duration_seconds': leg['duration']['value'],
                'polyline_encoded': encoded_polyline,
                'steps': len(leg['steps']),
                'summary': route.get('summary', ''),
                'bounds': route['bounds']
            }
            
            print(f"✅ Google Maps route fetched successfully")
            print(f"   Distance: {leg['distance']['text']}")
            print(f"   Duration: {leg['duration']['text']}")
            print(f"   Coordinates: {len(coordinates)} points")
            
            return result
            
        except requests.exceptions.Timeout:
            print("❌ Google Maps API request timed out")
            return {
                'success': False,
                'error': 'Request timeout'
            }
        except requests.exceptions.RequestException as e:
            print(f"❌ Google Maps API request failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            print(f"❌ Error processing Google Maps response: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def compute_frechet_distance(self, route1_coords: List[List[float]], 
                                  route2_coords: List[List[float]]) -> float:
        """
        Compute Fréchet distance between two routes
        
        Args:
            route1_coords: List of [lat, lng] coordinates
            route2_coords: List of [lat, lng] coordinates
            
        Returns:
            Fréchet distance in meters
        """
        try:
            # Convert to numpy arrays
            p = np.array(route1_coords)
            q = np.array(route2_coords)
            
            # Use directed Hausdorff distance as approximation of Fréchet
            # (True Fréchet is computationally expensive)
            forward = directed_hausdorff(p, q)[0]
            backward = directed_hausdorff(q, p)[0]
            hausdorff_dist = max(forward, backward)
            
            # Convert from degrees to meters (approximate)
            # At equator: 1 degree ≈ 111km
            # Using Haversine-like approximation
            avg_lat = (np.mean(p[:, 0]) + np.mean(q[:, 0])) / 2
            meters_per_degree_lat = 111320
            meters_per_degree_lng = 111320 * np.cos(np.radians(avg_lat))
            
            # Compute distance considering both lat and lng
            frechet_meters = hausdorff_dist * np.sqrt(
                (meters_per_degree_lat ** 2 + meters_per_degree_lng ** 2) / 2
            )
            
            return frechet_meters
            
        except Exception as e:
            print(f"❌ Error computing Fréchet distance: {e}")
            return 0.0
    
    def compute_segment_overlap(self, route1_coords: List[List[float]], 
                                 route2_coords: List[List[float]], 
                                 threshold_meters: float = 50.0) -> float:
        """
        Compute percentage of route segments that overlap
        
        Args:
            route1_coords: List of [lat, lng] coordinates
            route2_coords: List of [lat, lng] coordinates
            threshold_meters: Maximum distance to consider as "overlapping"
            
        Returns:
            Overlap percentage (0-100)
        """
        try:
            if not route1_coords or not route2_coords:
                return 0.0
            
            p = np.array(route1_coords)
            q = np.array(route2_coords)
            
            # Convert threshold from meters to degrees (approximate)
            avg_lat = (np.mean(p[:, 0]) + np.mean(q[:, 0])) / 2
            meters_per_degree = 111320 * np.cos(np.radians(avg_lat))
            threshold_degrees = threshold_meters / meters_per_degree
            
            # For each point in route1, find closest point in route2
            overlapping_points = 0
            
            for point1 in p:
                # Compute Euclidean distance to all points in route2
                distances = np.sqrt(np.sum((q - point1) ** 2, axis=1))
                min_distance = np.min(distances)
                
                if min_distance <= threshold_degrees:
                    overlapping_points += 1
            
            # Calculate overlap percentage
            overlap_percent = (overlapping_points / len(p)) * 100
            
            return overlap_percent
            
        except Exception as e:
            print(f"❌ Error computing segment overlap: {e}")
            return 0.0
    
    def compare_with_algorithm_route(self, algorithm_coords: List[List[float]], 
                                      start_lat: float, start_lng: float,
                                      dest_lat: float, dest_lng: float) -> Dict:
        """
        Compare algorithm route with Google Maps route
        
        Returns:
            Dict with comparison metrics
        """
        # Fetch Google Maps route
        gmaps_route = self.get_directions(start_lat, start_lng, dest_lat, dest_lng)
        
        if not gmaps_route.get('success'):
            return {
                'success': False,
                'error': gmaps_route.get('error', 'Failed to fetch Google Maps route')
            }
        
        gmaps_coords = gmaps_route['coordinates']
        
        # Compute comparison metrics
        print(f"\n📊 Computing comparison metrics...")
        print(f"   Algorithm route: {len(algorithm_coords)} points")
        print(f"   Google Maps route: {len(gmaps_coords)} points")
        
        frechet_distance = self.compute_frechet_distance(algorithm_coords, gmaps_coords)
        segment_overlap = self.compute_segment_overlap(algorithm_coords, gmaps_coords)
        
        result = {
            'success': True,
            'google_maps_route': {
                'coordinates': gmaps_coords,
                'distance_meters': gmaps_route['distance_meters'],
                'duration_seconds': gmaps_route['duration_seconds'],
                'polyline_encoded': gmaps_route['polyline_encoded']
            },
            'comparison': {
                'frechet_distance_meters': round(frechet_distance, 2),
                'segment_overlap_percent': round(segment_overlap, 2)
            }
        }
        
        print(f"✅ Comparison complete:")
        print(f"   Fréchet distance: {frechet_distance:.2f} meters")
        print(f"   Segment overlap: {segment_overlap:.2f}%")
        
        return result


# Test function
def test_google_maps_service():
    """Test Google Maps service with sample coordinates"""
    print("🧪 Testing Google Maps Service")
    print("=" * 60)
    
    service = GoogleMapsService()
    
    # Test coordinates in Quezon City
    start_lat, start_lng = 14.6760, 121.0437
    dest_lat, dest_lng = 14.6542, 121.0790
    
    # Fetch directions
    result = service.get_directions(start_lat, start_lng, dest_lat, dest_lng)
    
    if result.get('success'):
        print("\n✅ Test passed!")
        print(f"   Route distance: {result['distance_meters']} meters")
        print(f"   Route duration: {result['duration_seconds']} seconds")
        print(f"   Coordinates: {len(result['coordinates'])} points")
    else:
        print(f"\n❌ Test failed: {result.get('error')}")
    
    # Test comparison with mock algorithm route
    if result.get('success'):
        print("\n📊 Testing route comparison...")
        
        # Create mock algorithm route (slightly different from Google)
        algorithm_coords = [[lat + 0.0001, lng - 0.0001] 
                           for lat, lng in result['coordinates'][::2]]
        
        comparison = service.compare_with_algorithm_route(
            algorithm_coords, start_lat, start_lng, dest_lat, dest_lng
        )
        
        if comparison.get('success'):
            print("\n✅ Comparison test passed!")
            print(f"   Fréchet distance: {comparison['comparison']['frechet_distance_meters']:.2f}m")
            print(f"   Segment overlap: {comparison['comparison']['segment_overlap_percent']:.2f}%")
        else:
            print(f"\n❌ Comparison test failed: {comparison.get('error')}")


if __name__ == '__main__':
    test_google_maps_service()
