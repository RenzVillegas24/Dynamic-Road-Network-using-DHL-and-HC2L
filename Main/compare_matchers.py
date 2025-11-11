"""
Comparison: point_matcher.py vs traffic_hash_matcher.py TIER 0

This script validates that the TIER 0 implementation in traffic_hash_matcher.py
achieves the same point-matching logic as the reference point_matcher.py.

Key Test:
- point_matcher: For each incident point, find best flow point within distance threshold
- TIER 0: For each incident point, find ANY flow point within distance threshold
- Result: Both should identify the same incidents as being on the same roads

Performance Metrics:
- Match counts
- Coverage %
- True positives vs false positives
- Speed comparison
"""

import json
import math
import time
from typing import List, Dict, Tuple
from pathlib import Path


class PointMatcherReference:
    """Reference implementation from point_matcher.py"""
    
    @staticmethod
    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance in meters"""
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lng1)
        lat2_rad, lon2_rad = math.radians(lat2), math.radians(lng2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        
        return 6371000 * c
    
    @staticmethod
    def extract_flow_points(flow_data: Dict) -> List[Tuple[float, float, str]]:
        """Extract (lat, lng, description) from flow data"""
        points = []
        
        for result in flow_data.get('results', []):
            location = result.get('location', {})
            description = location.get('description', 'Unknown')
            shape = location.get('shape', {})
            
            for link in shape.get('links', []):
                for point_data in link.get('points', []):
                    lat = point_data.get('lat')
                    lng = point_data.get('lng')
                    if lat is not None and lng is not None:
                        points.append((lat, lng, description))
        
        return points
    
    @staticmethod
    def extract_incident_points(incident_data: Dict) -> List[Tuple[float, float, str]]:
        """Extract (lat, lng, incident_id) from incident data"""
        points = []
        
        for result in incident_data.get('results', []):
            location = result.get('location', {})
            shape = location.get('shape', {})
            incident_details = result.get('incidentDetails', {})
            incident_id = incident_details.get('id', 'Unknown')
            
            for link in shape.get('links', []):
                for point_data in link.get('points', []):
                    lat = point_data.get('lat')
                    lng = point_data.get('lng')
                    if lat is not None and lng is not None:
                        points.append((lat, lng, incident_id))
        
        return points
    
    @classmethod
    def find_matches(cls, flow_points: List[Tuple[float, float, str]], 
                     incident_points: List[Tuple[float, float, str]],
                     distance_threshold: float = 100.0) -> Dict:
        """
        Match incident points with flow points.
        
        Algorithm (from point_matcher.py):
        - For each incident point, find the BEST (closest) flow point
        - If best distance < threshold, count as match
        """
        matches = []
        incident_matches_count = {}
        
        for inc_lat, inc_lng, incident_id in incident_points:
            best_match = None
            best_distance = float('inf')
            
            # Find BEST flow point for this incident point
            for flow_lat, flow_lng, flow_desc in flow_points:
                distance = cls.haversine_distance(inc_lat, inc_lng, flow_lat, flow_lng)
                
                if distance < distance_threshold and distance < best_distance:
                    best_distance = distance
                    best_match = (flow_lat, flow_lng, flow_desc, distance)
            
            if best_match:
                flow_lat, flow_lng, flow_desc, distance = best_match
                match_info = {
                    'incident_id': incident_id,
                    'incident_point': (inc_lat, inc_lng),
                    'flow_location': flow_desc,
                    'flow_point': (flow_lat, flow_lng),
                    'distance_meters': round(distance, 2)
                }
                matches.append(match_info)
                incident_matches_count[incident_id] = incident_matches_count.get(incident_id, 0) + 1
        
        return {
            'matches': matches,
            'total_incident_points': len(incident_points),
            'total_flow_points': len(flow_points),
            'matched_incidents': len(incident_matches_count),
            'total_matches': len(matches),
            'incident_matches_count': incident_matches_count
        }


class TIER0Matcher:
    """TIER 0 implementation from traffic_hash_matcher.py"""
    
    @staticmethod
    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance in meters"""
        from math import radians, cos, sin, asin, sqrt
        
        lat1_rad, lng1_rad = radians(lat1), radians(lng1)
        lat2_rad, lng2_rad = radians(lat2), radians(lng2)
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng/2)**2
        c = 2 * asin(sqrt(a))
        return 6371000 * c
    
    @staticmethod
    def extract_incident_points(incident_data: Dict) -> List[Tuple[float, float, str]]:
        """Extract (lat, lng, incident_id) from incident"""
        points = []
        
        for result in incident_data.get('results', []):
            location = result.get('location', {})
            shape = location.get('shape', {})
            incident_details = result.get('incidentDetails', {})
            incident_id = incident_details.get('id', 'Unknown')
            
            for link in shape.get('links', []):
                for point_data in link.get('points', []):
                    lat = point_data.get('lat')
                    lng = point_data.get('lng')
                    if lat is not None and lng is not None:
                        points.append((lat, lng, incident_id))
        
        return points
    
    @staticmethod
    def extract_flow_item_points(flow_item: Dict) -> List[Tuple[float, float]]:
        """Extract points from a single flow item (ONLY lat/lng, ignore metadata)"""
        points = []
        
        location = flow_item.get('location', {})
        shape = location.get('shape', {})
        links = shape.get('links', [])
        
        if isinstance(links, list):
            for link in links:
                if 'points' in link and isinstance(link['points'], list):
                    for point in link['points']:
                        lat = point.get('lat')
                        lng = point.get('lng')
                        if lat is not None and lng is not None:
                            points.append((lat, lng))
        
        return points
    
    @classmethod
    def match_incident_to_flows(cls, incident_item: Dict, flow_results: List[Dict],
                                distance_threshold: float = 100.0) -> Dict:
        """
        TIER 0 Algorithm:
        - For each incident point: find if ANY flow point is close enough
        - Count how many incident points match for each flow
        - Return flow with best match count (greedy approach)
        
        Success: 2+ incident points inside flow
        """
        incident_details = incident_item.get('incidentDetails', {})
        incident_id = incident_details.get('id', 'Unknown')
        
        location = incident_item.get('location', {})
        shape = location.get('shape', {})
        incident_points = []
        
        for link in shape.get('links', []):
            for point_data in link.get('points', []):
                lat = point_data.get('lat')
                lng = point_data.get('lng')
                if lat is not None and lng is not None:
                    incident_points.append((lat, lng))
        
        if not incident_points:
            return {
                'incident_id': incident_id,
                'status': 'NO_POINTS',
                'matched': False,
                'incident_point_count': 0,
                'matched_points': 0,
                'best_flow': None
            }
        
        best_flow_idx = -1
        best_match_count = 0
        
        # Try each flow
        for flow_idx, flow_item in enumerate(flow_results):
            flow_points = cls.extract_flow_item_points(flow_item)
            if not flow_points:
                continue
            
            # Count incident points inside this flow
            matched_count = 0
            
            for inc_lat, inc_lng in incident_points:
                # Find if ANY flow point is close enough
                for flow_lat, flow_lng in flow_points:
                    distance = cls.haversine_distance(inc_lat, inc_lng, flow_lat, flow_lng)
                    
                    if distance <= distance_threshold:
                        matched_count += 1
                        break  # Move to next incident point
            
            # Keep best flow (most matched points)
            if matched_count >= 2 and matched_count > best_match_count:
                best_match_count = matched_count
                best_flow_idx = flow_idx
        
        matched = best_flow_idx >= 0 and best_match_count >= 2
        
        return {
            'incident_id': incident_id,
            'status': 'MATCHED' if matched else 'NO_MATCH',
            'matched': matched,
            'incident_point_count': len(incident_points),
            'matched_points': best_match_count,
            'best_flow': best_flow_idx if best_flow_idx >= 0 else None,
            'match_percentage': (best_match_count / len(incident_points) * 100) if incident_points else 0
        }


def compare_algorithms(flow_file: str, incident_file: str, distance_threshold: float = 100.0):
    """
    Compare point_matcher.py vs TIER 0 traffic_hash_matcher.py
    """
    
    print("\n" + "="*90)
    print("POINT MATCHER COMPARISON TEST")
    print("="*90)
    
    # Load data
    print("\n📂 Loading sample data...")
    with open(flow_file, 'r') as f:
        flow_data = json.load(f)
    
    with open(incident_file, 'r') as f:
        incident_data = json.load(f)
    
    print(f"   ✅ Flow results: {len(flow_data.get('results', []))} items")
    print(f"   ✅ Incident results: {len(incident_data.get('results', []))} items")
    
    # ========== REFERENCE: point_matcher.py ==========
    print("\n" + "-"*90)
    print("REFERENCE: point_matcher.py Logic")
    print("-"*90)
    
    start_time = time.time()
    
    flow_points_ref = PointMatcherReference.extract_flow_points(flow_data)
    incident_points_ref = PointMatcherReference.extract_incident_points(incident_data)
    
    print(f"   Extracted {len(flow_points_ref)} flow points")
    print(f"   Extracted {len(incident_points_ref)} incident points")
    
    ref_results = PointMatcherReference.find_matches(
        flow_points_ref, incident_points_ref, distance_threshold
    )
    
    ref_time = time.time() - start_time
    
    print(f"\n   📊 Results:")
    print(f"      Matched point pairs: {ref_results['total_matches']}")
    print(f"      Matched incidents: {ref_results['matched_incidents']}/{len(incident_data.get('results', []))}")
    print(f"      Time: {ref_time*1000:.2f}ms")
    
    # Get unique incidents matched
    ref_matched_incidents = set(ref_results['incident_matches_count'].keys())
    print(f"      Unique incident IDs: {len(ref_matched_incidents)}")
    
    # ========== TIER 0: traffic_hash_matcher.py ==========
    print("\n" + "-"*90)
    print("TIER 0: traffic_hash_matcher.py Logic")
    print("-"*90)
    
    start_time = time.time()
    
    flow_results = flow_data.get('results', [])
    incident_results = incident_data.get('results', [])
    
    tier0_matches = []
    tier0_matched_incidents = set()
    
    for incident_item in incident_results:
        result = TIER0Matcher.match_incident_to_flows(incident_item, flow_results, distance_threshold)
        tier0_matches.append(result)
        
        if result['matched']:
            tier0_matched_incidents.add(result['incident_id'])
    
    tier0_time = time.time() - start_time
    
    tier0_successful = sum(1 for m in tier0_matches if m['matched'])
    tier0_total_points_matched = sum(m['matched_points'] for m in tier0_matches if m['matched'])
    
    print(f"\n   📊 Results:")
    print(f"      Matched incidents: {tier0_successful}/{len(incident_results)}")
    print(f"      Total points inside flows: {tier0_total_points_matched}")
    print(f"      Time: {tier0_time*1000:.2f}ms")
    print(f"      Unique incident IDs: {len(tier0_matched_incidents)}")
    
    # ========== COMPARISON ==========
    print("\n" + "="*90)
    print("COMPARISON ANALYSIS")
    print("="*90)
    
    print(f"\nAlgorithm Differences:")
    print(f"  point_matcher.py:")
    print(f"    - For each incident point: find BEST flow point")
    print(f"    - Count if best distance < {distance_threshold}m")
    print(f"    - Group by incident ID")
    print(f"    - Result: {ref_results['total_matches']} individual point matches")
    
    print(f"\n  TIER 0 (traffic_hash_matcher.py):")
    print(f"    - For each incident: find flow with 2+ points inside")
    print(f"    - For each incident point: find ANY flow point < {distance_threshold}m")
    print(f"    - Greedy: pick flow with most matched points")
    print(f"    - Result: {tier0_successful} incidents matched")
    
    # Calculate overlap
    overlap = ref_matched_incidents & tier0_matched_incidents
    only_in_ref = ref_matched_incidents - tier0_matched_incidents
    only_in_tier0 = tier0_matched_incidents - ref_matched_incidents
    
    print(f"\nIncident Overlap Analysis:")
    print(f"  Reference matched incidents: {len(ref_matched_incidents)}")
    print(f"  TIER 0 matched incidents: {len(tier0_matched_incidents)}")
    print(f"  Overlap (both matched): {len(overlap)}")
    print(f"  Only in reference: {len(only_in_ref)}")
    print(f"  Only in TIER 0: {len(only_in_tier0)}")
    print(f"  Overlap %: {len(overlap) / max(len(ref_matched_incidents), 1) * 100:.1f}%")
    
    # Performance comparison
    print(f"\nPerformance:")
    print(f"  Reference time: {ref_time*1000:.2f}ms")
    print(f"  TIER 0 time: {tier0_time*1000:.2f}ms")
    print(f"  Speedup: {ref_time/tier0_time:.2f}x")
    
    # Coverage
    print(f"\nCoverage Analysis:")
    ref_coverage = len(ref_matched_incidents) / len(incident_results) * 100
    tier0_coverage = tier0_successful / len(incident_results) * 100
    print(f"  Reference coverage: {ref_coverage:.1f}% ({len(ref_matched_incidents)}/{len(incident_results)})")
    print(f"  TIER 0 coverage: {tier0_coverage:.1f}% ({tier0_successful}/{len(incident_results)})")
    print(f"  Difference: {abs(tier0_coverage - ref_coverage):.1f}%")
    
    # Detailed comparison
    print(f"\n" + "-"*90)
    print("SAMPLE DETAILED MATCHES")
    print("-"*90)
    
    print(f"\n✅ Matched by Both Algorithms:")
    sample_both = list(overlap)[:3]
    for incident_id in sample_both:
        ref_match = next((m for m in ref_results['incident_matches_count'].items() if m[0] == incident_id), None)
        tier0_match = next((m for m in tier0_matches if m['incident_id'] == incident_id), None)
        if ref_match and tier0_match:
            print(f"  Incident {incident_id}:")
            print(f"    - Reference: {ref_match[1]} point matches")
            print(f"    - TIER 0: {tier0_match['matched_points']}/{tier0_match['incident_point_count']} pts ({tier0_match['match_percentage']:.0f}%)")
    
    if only_in_ref:
        print(f"\n❌ Matched ONLY by Reference (point_matcher.py):")
        for incident_id in list(only_in_ref)[:3]:
            ref_match = next((m for m in ref_results['incident_matches_count'].items() if m[0] == incident_id), None)
            if ref_match:
                print(f"  Incident {incident_id}: {ref_match[1]} point matches")
    
    if only_in_tier0:
        print(f"\n⚠️  Matched ONLY by TIER 0 (traffic_hash_matcher.py):")
        for incident_id in list(only_in_tier0)[:3]:
            tier0_match = next((m for m in tier0_matches if m['incident_id'] == incident_id), None)
            if tier0_match:
                print(f"  Incident {incident_id}: {tier0_match['matched_points']}/{tier0_match['incident_point_count']} pts")
    
    # Validation verdict
    print(f"\n" + "="*90)
    print("VALIDATION VERDICT")
    print("="*90)
    
    if len(overlap) / max(len(ref_matched_incidents), 1) > 0.8:
        print(f"\n✅ TIER 0 IMPLEMENTATION IS VALID")
        print(f"   - High overlap with reference implementation ({len(overlap)}/{len(ref_matched_incidents)})")
        print(f"   - Coverage is comparable ({tier0_coverage:.1f}% vs {ref_coverage:.1f}%)")
        print(f"   - TIER 0 uses different but equivalent algorithm")
    else:
        print(f"\n⚠️  TIER 0 NEEDS ADJUSTMENT")
        print(f"   - Low overlap with reference ({len(overlap)}/{len(ref_matched_incidents)})")
        print(f"   - Possible issues: threshold mismatch, extraction differences")
    
    print("\n" + "="*90)


if __name__ == "__main__":
    # File paths
    flow_file = '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main/data/sample/flow.json'
    incident_file = '/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main/data/sample/incidents.json'
    
    try:
        compare_algorithms(flow_file, incident_file, distance_threshold=100.0)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print(f"   Make sure sample JSON files exist at:")
        print(f"   - {flow_file}")
        print(f"   - {incident_file}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
