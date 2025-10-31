"""
OSM Geometry Loader with Road Curve Support

This module loads actual road geometry (curves/LineStrings) from OpenStreetMap data
to provide smooth, accurate route visualization that follows actual road shapes.
"""

import os
import pickle
import osmnx as ox
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class OSMGeometryLoader:
    """
    Loads and caches OSM road geometry including curves and intermediate points.
    
    This solves the angular polyline problem by using actual road shape data
    from OpenStreetMap instead of just connecting intersection nodes with straight lines.
    """
    
    def __init__(self, cache_file: str = None):
        """
        Initialize OSM geometry loader.
        
        Args:
            cache_file: Path to cache file for storing downloaded OSM data
        """
        # Import here to avoid circular dependency
        if cache_file is None:
            try:
                from config import Config
                cache_file = str(Config.OSM_GEOMETRY_CACHE)
            except ImportError:
                cache_file = "data/osm_geometry.graphml"
        
        self.cache_file = cache_file
        self.graph = None
        self.edge_geometries: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
        
        self._load_or_download_graph()
        self._extract_edge_geometries()
    
    def _load_or_download_graph(self):
        """Load cached OSM graph or download if not available."""
        cache_path = Path(self.cache_file)
        
        if cache_path.exists():
            print(f"📁 Loading cached OSM graph from {self.cache_file}...")
            try:
                self.graph = ox.load_graphml(self.cache_file)
                print(f"✅ Loaded {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges from cache")
                return
            except Exception as e:
                print(f"⚠️  Failed to load cache: {e}")
                print("   Downloading fresh data...")
        
        # Download from OSM
        print("🌍 Downloading OSM road network for Quezon City, Philippines...")
        print("   This may take a few minutes...")
        
        self.graph = ox.graph_from_place(
            "Quezon City, Philippines",
            network_type="drive"
        )
        
        print(f"✅ Downloaded {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
        
        # Save to cache
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            ox.save_graphml(self.graph, self.cache_file)
            print(f"💾 Saved to cache: {self.cache_file}")
        except Exception as e:
            print(f"⚠️  Could not save cache: {e}")
    
    def _extract_edge_geometries(self):
        """Extract geometry coordinates for each edge."""
        print("🗺️  Extracting road geometries...")
        
        edges_with_geom = 0
        edges_without_geom = 0
        
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            # Get geometry if it exists, otherwise create from node coordinates
            if 'geometry' in data:
                # Road has curve data - extract all intermediate points
                coords = list(data['geometry'].coords)
                self.edge_geometries[(u, v)] = [(lat, lon) for lon, lat in coords]
                edges_with_geom += 1
            else:
                # Straight road - just use start and end nodes
                u_data = self.graph.nodes[u]
                v_data = self.graph.nodes[v]
                self.edge_geometries[(u, v)] = [
                    (u_data['y'], u_data['x']),
                    (v_data['y'], v_data['x'])
                ]
                edges_without_geom += 1
        
        print(f"✅ Extracted geometries for {len(self.edge_geometries)} edges")
        print(f"   📈 {edges_with_geom} edges with curves")
        print(f"   📏 {edges_without_geom} straight edges")
    
    def get_edge_geometry(self, source_osm_id: int, target_osm_id: int) -> Optional[List[Tuple[float, float]]]:
        """
        Get geometry coordinates for an edge between two OSM nodes.
        
        Args:
            source_osm_id: OSM ID of source node
            target_osm_id: OSM ID of target node
        
        Returns:
            List of (lat, lon) tuples representing the road geometry, or None if not found
        """
        return self.edge_geometries.get((source_osm_id, target_osm_id))
    
    def get_path_geometry(self, osm_node_path: List[int]) -> List[Dict[str, float]]:
        """
        Get complete geometry for a path following actual road curves.
        
        Args:
            osm_node_path: List of OSM node IDs representing the path
        
        Returns:
            List of coordinate dicts with 'lat' and 'lng' keys, including all curve points
        """
        if len(osm_node_path) < 2:
            return []
        
        all_coords = []
        
        for i in range(len(osm_node_path) - 1):
            source = osm_node_path[i]
            target = osm_node_path[i + 1]
            
            # Get geometry for this edge
            edge_geom = self.get_edge_geometry(source, target)
            
            if edge_geom:
                # Add all points except the last one (to avoid duplicates)
                for lat, lon in edge_geom[:-1]:
                    all_coords.append({'lat': lat, 'lng': lon})
            else:
                # Edge not found - use node positions as fallback
                if source in self.graph.nodes:
                    node_data = self.graph.nodes[source]
                    all_coords.append({'lat': node_data['y'], 'lng': node_data['x']})
        
        # Add final point
        if osm_node_path[-1] in self.graph.nodes:
            final_node = self.graph.nodes[osm_node_path[-1]]
            all_coords.append({'lat': final_node['y'], 'lng': final_node['x']})
        
        return all_coords
    
    def get_osm_node_id(self, internal_node_id: int, mapping: Dict[int, int] = None) -> Optional[int]:
        """
        Convert internal node ID to OSM node ID if mapping is provided.
        
        Args:
            internal_node_id: Internal node ID from your graph
            mapping: Optional mapping from internal IDs to OSM IDs
        
        Returns:
            OSM node ID or None
        """
        if mapping is None:
            return internal_node_id
        return mapping.get(internal_node_id)


# Test function
if __name__ == "__main__":
    print("🧪 Testing OSM Geometry Loader...")
    
    loader = OSMGeometryLoader()
    
    # Get a sample edge
    if loader.edge_geometries:
        sample_edge = list(loader.edge_geometries.keys())[0]
        source, target = sample_edge
        geom = loader.get_edge_geometry(source, target)
        
        print(f"\n📍 Sample edge from {source} to {target}:")
        print(f"   Geometry points: {len(geom)}")
        if len(geom) > 2:
            print(f"   This edge has curves! ({len(geom) - 2} intermediate points)")
        else:
            print(f"   This is a straight edge (no curves)")
        
        print(f"\n   Coordinates:")
        for i, (lat, lon) in enumerate(geom[:5]):
            print(f"     {i}: ({lat:.6f}, {lon:.6f})")
        if len(geom) > 5:
            print(f"     ... and {len(geom) - 5} more points")
