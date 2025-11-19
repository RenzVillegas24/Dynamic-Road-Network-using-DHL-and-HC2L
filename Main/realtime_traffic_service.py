"""
Real-Time Traffic Data Service
===============================

Fetches HERE API traffic data periodically and generates edge files
using hash-based matching with pre-matched edges.

Output Format (CSV):
    id_hash,source_lat,source_lon,target_lat,target_lon,source,target,speed_kph,freeFlow_kph,jamFactor,isClosed

Output Format (.gr):
    c <metadata>
    p sp <num_nodes> <num_edges>
    a <source> <target> <weight>

Files are timestamped and symlinked to 'current_traffic_<mode>.csv/gr'
"""

import os
import time
import requests
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from dotenv import load_dotenv

from config import Config
from traffic_hash_matcher import TrafficHashMatcher
from console_formatter import get_logger

logger = get_logger("RealtimeTrafficService")

# Load environment
load_dotenv()


class RealtimeTrafficService:
    """Service for fetching and processing real-time HERE traffic data"""
    
    def __init__(self, matched_edges_csv: Path = None):
        """
        Initialize real-time traffic service
        
        Args:
            matched_edges_csv: Path to matched_edges.csv (default: Main/here_osm/matched_edges.csv)
        """
        self.api_key = os.getenv('HERE_API_KEY', '')
        if not self.api_key:
            raise ValueError("HERE_API_KEY not found in environment variables")
        
        self.bbox = "121.01,14.59,121.14,14.76"  # Quezon City bounds
        
        # Initialize hash matcher
        if matched_edges_csv is None:
            matched_edges_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
        
        self.matcher = TrafficHashMatcher(matched_edges_csv)
        
        # Output directories
        self.output_dir = Config.DISRUPTIONS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.success("RealtimeTrafficService initialized")
        logger.config(f"API Key: {self.api_key[:10]}...")
        logger.config(f"BBox: {self.bbox}")
        logger.config(f"Output: {self.output_dir}")
    
    def fetch_flow_data(self) -> List[Dict]:
        """Fetch real-time traffic flow data from HERE API"""
        flow_url = (
            f"https://data.traffic.hereapi.com/v7/flow"
            f"?in=bbox:{self.bbox}"
            f"&locationReferencing=shape"
            f"&apiKey={self.api_key}"
        )
        
        try:
            logger.processing("Fetching flow data from HERE API...")
            response = requests.get(flow_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            logger.success(f"Received {len(results)} flow segments")
            return results
            
        except requests.RequestException as e:
            logger.error(f"Error fetching flow data: {e}")
            return []
    
    def fetch_incidents_data(self) -> List[Dict]:
        """Fetch real-time traffic incidents from HERE API"""
        incidents_url = (
            f"https://data.traffic.hereapi.com/v7/incidents"
            f"?in=bbox:{self.bbox}"
            f"&locationReferencing=shape"
            f"&apiKey={self.api_key}"
        )
        
        try:
            logger.processing("Fetching incidents data from HERE API...")
            response = requests.get(incidents_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            logger.success(f"Received {len(results)} incidents")
            return results
            
        except requests.RequestException as e:
            logger.error(f"Error fetching incidents: {e}")
            return []
    
    def generate_traffic_data(self, mode: str = 'flow') -> Tuple[pd.DataFrame, Dict]:
        """
        Fetch and match traffic data with intelligent merging of flow and incident data
        
        Args:
            mode: 'flow', 'incidents', or 'both'
            
        Returns:
            (DataFrame with traffic edges, metadata dict)
        """
        logger.info("="*70)
        logger.info(f"Generating Traffic Data - Mode: {mode.upper()}")
        logger.info("="*70)
        
        flow_edges = []
        incident_edges = []
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'mode': mode,
            'flow_count': 0,
            'incident_count': 0,
            'total_edges': 0
        }
        
        # Fetch and match flow data
        if mode in ['flow', 'both']:
            flow_results = self.fetch_flow_data()
            metadata['flow_count'] = len(flow_results)
            
            if flow_results:
                logger.processing("Matching flow data...")
                flow_edges = self.matcher.batch_match_flow_data(flow_results)
        
        # Fetch and match incident data
        if mode in ['incidents', 'both']:
            incident_results = self.fetch_incidents_data()
            metadata['incident_count'] = len(incident_results)
            
            if incident_results:
                logger.processing("Matching incident data...")
                # Pass flow_results for Tier 1 (traffic-data) matching if available
                incident_edges = self.matcher.batch_match_incident_data(incident_results, flow_results)
        
        # Merge flow and incident data intelligently
        if mode == 'both' and flow_edges and incident_edges:
            all_edges = self._merge_flow_and_incident_edges(flow_edges, incident_edges)
        else:
            all_edges = flow_edges + incident_edges
        
        # Convert to DataFrame
        if all_edges:
            df = pd.DataFrame([edge.to_dict() for edge in all_edges])
            metadata['total_edges'] = len(df)
            
            logger.success(f"Generated {len(df)} traffic edges")
            return df, metadata
        else:
            logger.warning("No traffic data matched")
            return pd.DataFrame(), metadata
    
    def _merge_flow_and_incident_edges(self, flow_edges, incident_edges):
        """
        Intelligently merge flow and incident edges so that the same road edge
        can have both flow and incident data in a single row.
        
        For each unique (source, target) pair:
        - If only flow data exists: use flow edge
        - If only incident data exists: use incident edge
        - If both exist: merge them into single edge with both flow_* and incident_* fields
        
        Args:
            flow_edges: List of TrafficEdge objects from flow data
            incident_edges: List of TrafficEdge objects from incident data
            
        Returns:
            List of merged TrafficEdge objects
        """
        from traffic_hash_matcher import TrafficEdge
        
        # Create dictionaries keyed by (source, target)
        flow_dict = {}
        for edge in flow_edges:
            key = (edge.source, edge.target)
            # If multiple flow entries for same edge, keep the one with highest jam_factor
            if key not in flow_dict or edge.flow_jam_factor > flow_dict[key].flow_jam_factor:
                flow_dict[key] = edge
        
        incident_dict = {}
        for edge in incident_edges:
            key = (edge.source, edge.target)
            # If multiple incidents for same edge, keep the most critical one
            if key not in incident_dict:
                incident_dict[key] = edge
            else:
                # Compare criticality: critical > severe > major > minor
                criticality_rank = {'critical': 4, 'severe': 3, 'major': 2, 'minor': 1}
                new_rank = criticality_rank.get(edge.incident_criticality.lower(), 0)
                existing_rank = criticality_rank.get(incident_dict[key].incident_criticality.lower(), 0)
                if new_rank > existing_rank:
                    incident_dict[key] = edge
        
        merged_edges = []
        all_keys = set(flow_dict.keys()) | set(incident_dict.keys())
        
        for key in all_keys:
            flow_edge = flow_dict.get(key)
            incident_edge = incident_dict.get(key)
            
            if flow_edge and incident_edge:
                # Merge: copy flow data into incident edge (which has empty flow fields)
                merged_edge = TrafficEdge(
                    id_hash=flow_edge.id_hash or incident_edge.id_hash,
                    source=key[0],
                    target=key[1],
                    source_lat=flow_edge.source_lat or incident_edge.source_lat,
                    source_lon=flow_edge.source_lon or incident_edge.source_lon,
                    target_lat=flow_edge.target_lat or incident_edge.target_lat,
                    target_lon=flow_edge.target_lon or incident_edge.target_lon,
                    # Preserve ALL flow data
                    flow_speed_kph=flow_edge.flow_speed_kph,
                    flow_free_flow_kph=flow_edge.flow_free_flow_kph,
                    flow_jam_factor=flow_edge.flow_jam_factor,
                    flow_confidence=flow_edge.flow_confidence,
                    flow_traversability=flow_edge.flow_traversability,
                    # Preserve ALL incident data
                    incident_id=incident_edge.incident_id,
                    incident_type=incident_edge.incident_type,
                    incident_criticality=incident_edge.incident_criticality,
                    incident_description=incident_edge.incident_description,
                    incident_road_closed=incident_edge.incident_road_closed,
                    incident_start_time=incident_edge.incident_start_time,
                    incident_end_time=incident_edge.incident_end_time,
                    # Preserve road attributes
                    highway_type=flow_edge.highway_type or incident_edge.highway_type,
                    road_name=flow_edge.road_name or incident_edge.road_name,
                    # Keep deprecated fields
                    speed_kph=flow_edge.speed_kph,
                    freeFlow_kph=flow_edge.freeFlow_kph,
                    jamFactor=flow_edge.jamFactor,
                    isClosed=incident_edge.isClosed
                )
                merged_edges.append(merged_edge)
            elif flow_edge:
                merged_edges.append(flow_edge)
            else:
                merged_edges.append(incident_edge)
        
        logger.success(f"Merged {len(flow_dict)} flow + {len(incident_dict)} incident edges")
        logger.data(f"-> {len(merged_edges)} unique edges with combined flow+incident data")
        
        return merged_edges
    
    def save_traffic_csv(self, df: pd.DataFrame, mode: str) -> Path:
        """
        Save traffic data to timestamped CSV file
        Auto-cleanup old files to maintain max 10 files per mode
        
        Args:
            df: DataFrame with traffic edges
            mode: Traffic mode for filename
            
        Returns:
            Path to saved CSV file
        """
        if df.empty:
            logger.warning("No data to save")
            return None
        
        # Cleanup old files first (keep max 10)
        self._cleanup_old_files(mode, max_files=10)
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"traffic_{timestamp}_{mode}.csv"
        filepath = self.output_dir / filename
        
        # Save CSV
        df.to_csv(filepath, index=False)
        logger.file_op(f"Saved CSV: {filepath}")
        
        # NOTE: No symlink creation - system now uses latest timestamped file
        
        return filepath
    
    def _cleanup_old_files(self, mode: str, max_files: int = 10):
        """
        Remove old traffic files, keeping only the latest N files
        
        Args:
            mode: Traffic mode (flow/incidents/both)
            max_files: Maximum number of files to keep per mode
        """
        traffic_pattern = f"traffic_*_{mode}.csv"
        traffic_files = sorted(self.output_dir.glob(traffic_pattern), reverse=True)
        
        # Keep only the latest max_files
        if len(traffic_files) >= max_files:
            files_to_remove = traffic_files[max_files-1:]  # Keep max_files-1 to make room for new file
            for old_file in files_to_remove:
                try:
                    old_file.unlink()
                    logger.file_op(f"Removed old file: {old_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove {old_file.name}: {e}")
    
    def save_traffic_gr(self, df: pd.DataFrame, mode: str) -> Path:
        """
        Save traffic data to ENHANCED .gr format for C++ routing APIs
        
        ENHANCED FORMAT allows C++ algorithms to directly consider:
        ✅ jam_factor: Traffic congestion (0.0 = free flow, 10.0 = blocked)
        ✅ current_speed: Actual speed in km/h from HERE API
        ✅ free_flow_speed: Free flow speed in km/h from HERE API
        ✅ highway: Road type (motorway, primary, secondary, residential, etc.)
        ✅ is_closed: Road closure flag (1 = closed, 0 = open)
        ✅ type: Incident/traffic type (closure, accident, congestion, flow, etc.)
        ✅ impact_score: Traffic impact metric (0.0-1.0)
        ✅ confidence: Data reliability score (0.0-1.0)
        
        Format: a source target weight jam_factor current_speed free_flow_speed impact_score confidence highway is_closed type
        Example: a 84509345 430697473 1000 0.00 11.11 0.00 0.500 0.90 secondary 0 flow
        
        The C++ code in hc2l_routing_api.cpp parses this extended format and uses:
        - weight: For shortest path computation
        - jam_factor: To penalize congested roads (cost *= 1.0 + jam_factor/10.0 * 4.0)
        - highway: To prefer higher-class roads (motorway=0.5x, residential=2.0x)
        - is_closed: To block closed roads (weight = 999999999)
        
        Args:
            df: DataFrame with traffic edges
            mode: Traffic mode for filename
            
        Returns:
            Path to saved .gr file
        """
        if df.empty:
            logger.warning("No data to save")
            return None
        
        # Generate timestamp filename
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        filename = f"traffic_{timestamp}_{mode}.gr"
        filepath = self.output_dir / filename
        
        # Get unique nodes
        nodes = set(df['source'].tolist() + df['target'].tolist())
        num_nodes = max(nodes) if nodes else 0
        num_edges = len(df)
        
        # Write .gr file with ENHANCED format
        with open(filepath, 'w') as f:
            # Header
            f.write(f"c Traffic data from HERE API - ENHANCED FORMAT\n")
            f.write(f"c Mode: {mode}\n")
            f.write(f"c Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"c Edges: {num_edges}\n")
            f.write(f"c Format: a source target weight jam_factor current_speed free_flow_speed impact_score confidence highway is_closed type\n")
            f.write(f"p sp {num_nodes} {num_edges}\n")
            
            # Edges with FULL traffic metrics
            for _, row in df.iterrows():
                source = int(row['source'])
                target = int(row['target'])
                
                # Extract traffic metrics - prefer new flow_* fields, fall back to old fields
                jam_factor = float(row.get('flow_jam_factor', row.get('jamFactor', 0.0)))
                speed_kph = float(row.get('flow_speed_kph', row.get('speed_kph', 0.0)))
                free_flow_kph = float(row.get('flow_free_flow_kph', row.get('freeFlow_kph', 0.0)))
                
                # Check for incident data
                incident_road_closed = bool(row.get('incident_road_closed', False))
                incident_criticality = str(row.get('incident_criticality', '')).lower()
                
                # If incident exists, it takes priority for closed status
                is_closed = incident_road_closed or bool(row.get('isClosed', False))
                
                # Boost jam_factor based on incident criticality
                if incident_criticality:
                    criticality_boost = {
                        'critical': 9.0,
                        'severe': 7.0,
                        'major': 5.0,
                        'minor': 2.0
                    }
                    incident_jam = criticality_boost.get(incident_criticality, 0.0)
                    # Use the higher of flow jam_factor or incident jam_factor
                    jam_factor = max(jam_factor, incident_jam)
                
                # Get highway type (from matched edges CSV)
                highway_type = str(row.get('highway_type', 'unknown')).replace(' ', '_')
                
                # CRITICAL FIX: Ensure free_flow_kph is never 0 to avoid division errors
                if free_flow_kph <= 0.0:
                    # Estimate from highway type
                    hw_lower = highway_type.lower()
                    if 'motorway' in hw_lower:
                        free_flow_kph = 110.0
                    elif 'trunk' in hw_lower:
                        free_flow_kph = 90.0
                    elif 'primary' in hw_lower:
                        free_flow_kph = 70.0
                    elif 'secondary' in hw_lower:
                        free_flow_kph = 60.0
                    elif 'tertiary' in hw_lower:
                        free_flow_kph = 50.0
                    elif 'residential' in hw_lower:
                        free_flow_kph = 40.0
                    else:
                        free_flow_kph = 50.0  # Default
                
                # CRITICAL FIX: Ensure speed_kph is valid
                if speed_kph <= 0.0:
                    if jam_factor > 0.0:
                        # Estimate from jam factor
                        speed_reduction = min(1.0, jam_factor / 10.0)
                        speed_kph = free_flow_kph * (1.0 - speed_reduction * 0.9)
                    else:
                        # No congestion, use free flow
                        speed_kph = free_flow_kph
                
                # Ensure speed doesn't exceed free flow
                speed_kph = min(speed_kph, free_flow_kph)
                
                # Calculate weight from jam factor and speed
                if is_closed:
                    weight = 999999  # Very high penalty for closed roads
                    incident_type = 'closure'
                elif free_flow_kph > 0 and speed_kph > 0:
                    # Weight based on travel time: weight ∝ time = distance / speed
                    # Higher jam factor = higher weight multiplier
                    base_weight = 1000
                    time_multiplier = free_flow_kph / speed_kph  # > 1.0 when congested
                    weight = int(base_weight * time_multiplier)
                    
                    # Determine incident type from jam factor
                    if jam_factor >= 8.0:
                        incident_type = 'accident'
                    elif jam_factor >= 5.0:
                        incident_type = 'congestion'
                    else:
                        incident_type = 'flow'
                else:
                    # Fallback: use jam factor only
                    weight = int(1000 * (1.0 + jam_factor / 10.0))
                    incident_type = 'flow'
                
                # Calculate impact score (0.0 to 1.0)
                # Based on actual speed reduction
                if is_closed:
                    impact_score = 1.0
                else:
                    # Speed ratio: how much slower than free flow
                    speed_ratio = speed_kph / free_flow_kph if free_flow_kph > 0 else 1.0
                    # Impact is inverse of speed ratio (0 = no impact, 1 = complete blockage)
                    impact_score = round(max(0.0, min(1.0, 1.0 - speed_ratio)), 3)
                
                # Confidence (assume high for HERE API data)
                confidence = 0.9
                
                # Write ENHANCED format: source target weight jam_factor speed free_flow impact confidence highway closed type
                f.write(f"a {source} {target} {weight} "
                       f"{jam_factor:.2f} {speed_kph:.2f} {free_flow_kph:.2f} "
                       f"{impact_score:.3f} {confidence:.2f} {highway_type} "
                       f"{1 if is_closed else 0} {incident_type}\n")
        
        logger.file_op(f"Saved .gr: {filepath}")
        
        # Create/update symlink to latest
        symlink = self.output_dir / f"current_traffic_{mode}.gr"
        if symlink.exists():
            symlink.unlink()
        symlink.symlink_to(filepath.name)
        logger.file_op(f"Symlink: {symlink} -> {filepath.name}")
        
        return filepath
    
    def fetch_and_save(self, mode: str = 'flow') -> Dict:
        """
        Fetch traffic data and save to CSV file only
        
        Args:
            mode: 'flow', 'incidents', or 'both'
            
        Returns:
            Metadata dictionary
        """
        # Generate traffic data
        df, metadata = self.generate_traffic_data(mode)
        
        if not df.empty:
            # Save CSV only (no .gr files)
            csv_path = self.save_traffic_csv(df, mode)
            metadata['csv_file'] = str(csv_path) if csv_path else None
            
            logger.data("Summary:")
            logger.data(f"  Flow segments: {metadata['flow_count']}")
            logger.data(f"  Incidents: {metadata['incident_count']}")
            logger.data(f"  Total edges: {metadata['total_edges']}")
            logger.data("  CSV only (no .gr files generated)")
        
        return metadata
    
    def run_continuous(self, mode: str = 'flow', interval: int = 60):
        """
        Run continuous traffic data fetching
        
        Args:
            mode: 'flow', 'incidents', or 'both'
            interval: Update interval in seconds
        """
        logger.info("="*70)
        logger.info("Starting Continuous Traffic Service")
        logger.info("="*70)
        logger.info(f"Mode: {mode}")
        logger.info(f"Update interval: {interval}s")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while True:
                # Fetch and save
                self.fetch_and_save(mode)
                
                # Wait for next update
                logger.processing(f"Waiting {interval}s for next update...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Service stopped by user")


def main():
    """Main entry point for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time HERE traffic data service')
    parser.add_argument('--mode', choices=['flow', 'incidents', 'both'], 
                       default='flow', help='Traffic data mode')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously with periodic updates')
    parser.add_argument('--interval', type=int, default=60,
                       help='Update interval in seconds (for continuous mode)')
    
    args = parser.parse_args()
    
    # Initialize service
    service = RealtimeTrafficService()
    
    # Run
    if args.continuous:
        service.run_continuous(mode=args.mode, interval=args.interval)
    else:
        service.fetch_and_save(mode=args.mode)


if __name__ == '__main__':
    main()
