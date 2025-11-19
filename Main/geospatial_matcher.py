"""
Geospatial Matching Service for HERE Traffic Data
Maps HERE Traffic API coordinate data to road network edges with highway priority
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path
from dataclasses import dataclass
from console_formatter import get_logger

logger = get_logger("GeospatialMatcher")
import math


@dataclass
class MatchedEdge:
    """Represents an edge matched to a traffic segment"""
    source: int
    target: int
    distance: float  # Distance from segment to edge (meters)
    highway_type: str
    length: float  # Edge length
    confidence: float  # Match confidence score (0-1)


class GeospatialMatcher:
    """
    Matches HERE Traffic API coordinate shapes to road network edges
    Uses Haversine distance and highway classification priority
    """
    
    # Highway type priority weights (higher = more important)
    HIGHWAY_WEIGHTS = {
        'motorway': 10.0,
        'trunk': 9.0,
        'primary': 8.0,
        'secondary': 7.0,
        'tertiary': 6.0,
        'motorway_link': 5.5,
        'trunk_link': 5.0,
        'primary_link': 4.5,
        'secondary_link': 4.0,
        'residential': 3.0,
        'unclassified': 2.0,
        'service': 1.0,
        'unknown': 1.0
    }
    
    def __init__(self, edges_csv: Path, nodes_csv: Path):
        """
        Initialize matcher with road network data
        
        Args:
            edges_csv: Path to edges CSV file
            nodes_csv: Path to nodes CSV file
        """
        logger.processing("Loading road network for geospatial matching...")
        
        # Load edges and nodes
        self.edges_df = pd.read_csv(edges_csv)
        self.nodes_df = pd.read_csv(nodes_csv)
        
        # Create node coordinate lookup
        self.node_coords = {}
        for _, node in self.nodes_df.iterrows():
            # Handle different column name formats
            if 'osmid' in node:
                node_id = int(node['osmid'])
                lat = float(node['y'])
                lon = float(node['x'])
            elif 'node_id' in node:
                node_id = int(node['node_id'])
                lat = float(node['latitude'])
                lon = float(node['longitude'])
            else:
                raise ValueError("Unknown node CSV format - missing osmid/node_id column")
            
            self.node_coords[node_id] = (lat, lon)  # (lat, lon)
        
        # Enrich edges with start/end coordinates
        self._enrich_edge_coordinates()
        
        logger.success(f"Loaded {len(self.edges_df)} edges and {len(self.nodes_df)} nodes")
    
    def _enrich_edge_coordinates(self):
        """Add start/end coordinates to edges dataframe"""
        self.edges_df['start_lat'] = self.edges_df['source'].map(
            lambda x: self.node_coords.get(x, (None, None))[0]
        )
        self.edges_df['start_lon'] = self.edges_df['source'].map(
            lambda x: self.node_coords.get(x, (None, None))[1]
        )
        self.edges_df['end_lat'] = self.edges_df['target'].map(
            lambda x: self.node_coords.get(x, (None, None))[0]
        )
        self.edges_df['end_lon'] = self.edges_df['target'].map(
            lambda x: self.node_coords.get(x, (None, None))[1]
        )
        
        # Remove edges with missing coordinates
        before_count = len(self.edges_df)
        self.edges_df = self.edges_df.dropna(
            subset=['start_lat', 'start_lon', 'end_lat', 'end_lon']
        )
        after_count = len(self.edges_df)
        
        if before_count > after_count:
            logger.info(f"Removed {before_count - after_count} edges with missing coordinates")
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate haversine distance between two points in meters
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        R = 6371000  # Earth radius in meters
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def point_to_line_distance(self, point_lat: float, point_lon: float,
                               line_start_lat: float, line_start_lon: float,
                               line_end_lat: float, line_end_lon: float) -> float:
        """
        Calculate minimum distance from point to line segment
        
        Args:
            point_lat, point_lon: Point coordinates
            line_start_lat, line_start_lon: Line segment start
            line_end_lat, line_end_lon: Line segment end
            
        Returns:
            Minimum distance in meters
        """
        # Calculate distances to both endpoints
        d_start = self.haversine_distance(point_lat, point_lon, line_start_lat, line_start_lon)
        d_end = self.haversine_distance(point_lat, point_lon, line_end_lat, line_end_lon)
        
        # Calculate line segment length
        line_length = self.haversine_distance(
            line_start_lat, line_start_lon, line_end_lat, line_end_lon
        )
        
        # If line segment has zero length, return distance to start point
        if line_length < 0.1:  # Less than 10cm
            return d_start
        
        # Calculate projection parameter
        # Simplified approach: use squared distances to avoid sqrt
        dx = line_end_lon - line_start_lon
        dy = line_end_lat - line_start_lat
        px = point_lon - line_start_lon
        py = point_lat - line_start_lat
        
        dot_product = px * dx + py * dy
        line_length_squared = dx * dx + dy * dy
        
        t = max(0, min(1, dot_product / line_length_squared))
        
        # Calculate closest point on line segment
        closest_lat = line_start_lat + t * (line_end_lat - line_start_lat)
        closest_lon = line_start_lon + t * (line_end_lon - line_start_lon)
        
        # Return distance to closest point
        return self.haversine_distance(point_lat, point_lon, closest_lat, closest_lon)
    
    def extract_coordinates_from_shape(self, location: Dict) -> List[Tuple[float, float]]:
        """
        Extract coordinate pairs from HERE API location shape
        
        Args:
            location: Location dictionary from HERE API
            
        Returns:
            List of (lat, lon) tuples
        """
        coords = []
        
        # Handle shape-based location referencing
        shape = location.get('shape', {})
        links = shape.get('links', [])
        
        for link in links:
            points = link.get('points', [])
            for point in points:
                lat = point.get('lat')
                lon = point.get('lng')
                if lat is not None and lon is not None:
                    coords.append((lat, lon))
        
        return coords
    
    def match_segment_to_edges(self, segment_coords: List[Tuple[float, float]],
                               max_distance: float = 100.0,
                               min_confidence: float = 0.3) -> List[MatchedEdge]:
        """
        Match a traffic segment to road network edges
        
        Args:
            segment_coords: List of (lat, lon) coordinates from HERE API
            max_distance: Maximum matching distance in meters
            min_confidence: Minimum confidence score to include match
            
        Returns:
            List of MatchedEdge objects sorted by confidence (descending)
        """
        if not segment_coords:
            return []
        
        matched_edges = []
        
        # Calculate bounding box for filtering
        lats = [coord[0] for coord in segment_coords]
        lons = [coord[1] for coord in segment_coords]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # Add buffer (approximately 0.001 degrees ≈ 111 meters)
        buffer = max_distance / 111000.0
        min_lat -= buffer
        max_lat += buffer
        min_lon -= buffer
        max_lon += buffer
        
        # Filter edges within bounding box
        candidate_edges = self.edges_df[
            (self.edges_df['start_lat'] >= min_lat) & 
            (self.edges_df['start_lat'] <= max_lat) &
            (self.edges_df['start_lon'] >= min_lon) & 
            (self.edges_df['start_lon'] <= max_lon)
        ]
        
        # Match each candidate edge
        for _, edge in candidate_edges.iterrows():
            # Calculate minimum distance from segment to edge
            min_dist = float('inf')
            
            for seg_lat, seg_lon in segment_coords:
                dist = self.point_to_line_distance(
                    seg_lat, seg_lon,
                    edge['start_lat'], edge['start_lon'],
                    edge['end_lat'], edge['end_lon']
                )
                min_dist = min(min_dist, dist)
            
            # Skip if too far
            if min_dist > max_distance:
                continue
            
            # Calculate confidence score
            highway_type = edge.get('highway', 'unknown')
            highway_weight = self.HIGHWAY_WEIGHTS.get(highway_type, 1.0)
            
            # Distance score: closer = better (normalized to 0-1)
            distance_score = max(0, 1.0 - (min_dist / max_distance))
            
            # Highway priority score (normalized to 0-1)
            highway_score = highway_weight / 10.0  # Max weight is 10
            
            # Combined confidence: 60% distance, 40% highway priority
            confidence = 0.6 * distance_score + 0.4 * highway_score
            
            # Skip if confidence too low
            if confidence < min_confidence:
                continue
            
            matched_edges.append(MatchedEdge(
                source=int(edge['source']),
                target=int(edge['target']),
                distance=min_dist,
                highway_type=highway_type,
                length=float(edge['length']),
                confidence=confidence
            ))
        
        # Sort by confidence (descending)
        matched_edges.sort(key=lambda x: x.confidence, reverse=True)
        
        return matched_edges
    
    def match_disruption_to_edges(self, disruption: Dict,
                                  max_distance: float = 100.0,
                                  max_matches: int = 10) -> List[MatchedEdge]:
        """
        Match a single disruption to road network edges
        
        Args:
            disruption: Disruption dictionary with 'location' field
            max_distance: Maximum matching distance in meters
            max_matches: Maximum number of edges to return
            
        Returns:
            List of top matched edges
        """
        location = disruption.get('location', {})
        coords = self.extract_coordinates_from_shape(location)
        
        if not coords:
            return []
        
        matches = self.match_segment_to_edges(coords, max_distance)
        
        # Return top N matches
        return matches[:max_matches]
    
    def calculate_impact_score(self, disruption: Dict, edge: MatchedEdge) -> float:
        """
        Calculate impact score for a disruption on a specific edge
        
        Args:
            disruption: Disruption dictionary
            edge: Matched edge
            
        Returns:
            Impact score (higher = more severe)
        """
        # Base factors
        jam_factor = disruption.get('jam_factor', 5.0)  # 0-10 scale
        speed_reduction = disruption.get('speed_reduction', 0.5)  # 0-1 scale
        
        # Road importance weight
        highway_weight = self.HIGHWAY_WEIGHTS.get(edge.highway_type, 1.0)
        importance_factor = highway_weight / 10.0  # Normalize to 0-1
        
        # Length factor (longer roads have more impact)
        length_factor = min(1.0, edge.length / 1000.0)  # Cap at 1km
        
        # Match confidence (higher confidence = more reliable impact)
        confidence_factor = edge.confidence
        
        # Combined impact score
        impact = (
            jam_factor / 10.0 * 0.3 +           # 30% jam factor
            speed_reduction * 0.3 +              # 30% speed reduction
            importance_factor * 0.2 +            # 20% road importance
            length_factor * 0.1 +                # 10% length
            confidence_factor * 0.1              # 10% match confidence
        )
        
        return impact
    
    def get_matching_statistics(self, disruptions: List[Dict]) -> Dict:
        """
        Calculate matching statistics for a list of disruptions
        
        Args:
            disruptions: List of disruption dictionaries
            
        Returns:
            Statistics dictionary
        """
        total_disruptions = len(disruptions)
        matched_count = 0
        total_edges_affected = 0
        confidence_scores = []
        
        for disruption in disruptions:
            matches = self.match_disruption_to_edges(disruption)
            if matches:
                matched_count += 1
                total_edges_affected += len(matches)
                confidence_scores.extend([m.confidence for m in matches])
        
        return {
            'total_disruptions': total_disruptions,
            'matched_disruptions': matched_count,
            'match_rate': matched_count / total_disruptions if total_disruptions > 0 else 0,
            'total_edges_affected': total_edges_affected,
            'avg_edges_per_disruption': total_edges_affected / matched_count if matched_count > 0 else 0,
            'avg_confidence': np.mean(confidence_scores) if confidence_scores else 0,
            'min_confidence': np.min(confidence_scores) if confidence_scores else 0,
            'max_confidence': np.max(confidence_scores) if confidence_scores else 0
        }


def test_geospatial_matching():
    """Test function for geospatial matching"""
    from config import Config
    
    # Initialize matcher
    matcher = GeospatialMatcher(Config.EDGES_CSV, Config.NODES_CSV)
    
    # Test with sample coordinates (Quezon City area - based on actual data)
    # Using coordinates from the edges CSV
    test_coords = [
        (14.617651, 121.00184),   # First node from edges CSV
        (14.617816, 121.001881),  # Second node
        (14.61797, 121.001701)    # Third node
    ]
    
    logger.processing("Testing geospatial matching...")
    logger.info(f"Test coordinates: {len(test_coords)} points")
    
    matches = matcher.match_segment_to_edges(test_coords, max_distance=200.0)
    
    logger.success(f"Found {len(matches)} matching edges:")
    for i, match in enumerate(matches[:5], 1):
        logger.info(f"{i}. Edge {match.source}→{match.target}")
        logger.info(f"   Highway: {match.highway_type}")
        logger.info(f"   Distance: {match.distance:.1f}m")
        logger.info(f"   Confidence: {match.confidence:.3f}")
        logger.info(f"   Length: {match.length:.1f}m")


if __name__ == '__main__':
    test_geospatial_matching()
