# flask_server.py - Enhanced with HC2L (Hierarchical Cut Labelling) Routing
from flask import Flask, request, jsonify, render_template
import pandas as pd
import time
import json
from pathlib import Path
import atexit
import logging
from collections import deque
from datetime import datetime
import csv
import uuid
import traceback
import glob
import os
import requests
import numpy as np

# Import configuration
from config import Config

# Import new modules for optimization
from settings_manager import init_settings_manager, get_settings_manager
from console_formatter import get_logger, ConsoleFormatter

# Import your coordinate mapper and HC2L router
from coordinate_mapper import NodeMapper
from hc2l_router import HC2LRouter
from dhl_router import DHLRouter

# Import auto-disruption service
from auto_disruption_service import init_auto_disruption_service, shutdown_auto_disruption_service, get_auto_disruption_service

# Import Google Maps service
from google_maps_service import GoogleMapsService

# Import Real-Time Data Services (V3 - Separated Flow and Incidents)
from flow_service import FlowService
from incident_service import IncidentService

# Import user disruptions utilities for loading user-reported disruptions
from user_disruptions import (
    load_user_disruption_rows,
    format_user_disruption_row,
    ensure_user_disruption_fieldnames,
    cleanup_old_user_incidents
)

# Import route recalculation endpoint
import route_recalculation_endpoint

# Import experiment automation API
from experiment_api import experiment_bp

# Get logger instance
console_logger = get_logger("FlaskServer")

app = Flask(__name__)

# Configure Flask from config file
app.config['DEBUG'] = Config.FLASK_DEBUG
app.config['ENV'] = Config.FLASK_ENV

# Register experiment automation API blueprint
app.register_blueprint(experiment_bp)

# Initialize settings manager (persistent storage)
settings_manager = init_settings_manager()

console_logger.info("Flask Server Initialization")

# In-memory log buffer (thread-safe circular buffer)
backend_logs = deque(maxlen=1000)  # Keep last 1000 logs
backend_log_counter = 0

class BackendLogHandler(logging.Handler):
    """Custom log handler that captures logs to in-memory buffer"""
    
    def emit(self, record):
        global backend_log_counter
        backend_log_counter += 1
        
        try:
            log_entry = {
                'id': backend_log_counter,
                'timestamp': record.created,
                'level': record.levelname,
                'message': self.format(record),
                'module': record.module,
                'line': record.lineno,
                'function': record.funcName
            }
            backend_logs.append(log_entry)
        except Exception as e:
            # Fail silently to avoid breaking the app
            console_logger.error(f"Error in BackendLogHandler: {e}")

# Configure backend logging
backend_handler = BackendLogHandler()
backend_handler.setLevel(logging.DEBUG)
backend_formatter = logging.Formatter('%(levelname)s - %(module)s:%(lineno)d - %(message)s')
backend_handler.setFormatter(backend_formatter)

# Add handler to Flask logger and root logger
app.logger.addHandler(backend_handler)
logging.getLogger().addHandler(backend_handler)
logging.getLogger().setLevel(logging.DEBUG)

# Add initial log
app.logger.info("Backend logging system initialized")

# ============================================================
# END BACKEND LOGGING SYSTEM
# ============================================================

# Initialize components using config paths
console_logger.info("Initializing Core Components")

mapper = NodeMapper(str(Config.NODES_CSV))
try:
    gps_router = HC2LRouter()
    console_logger.success("HC2L Router initialized")
except Exception as e:
    console_logger.error(f"Error initializing HC2L Router: {e}")
    gps_router = None

# Initialize DHL Router
try:
    dhl_router = DHLRouter()
    console_logger.success("DHL Router initialized")
except Exception as e:
    console_logger.error(f"Error initializing DHL Router: {e}")
    dhl_router = None

# Initialize Google Maps Service
try:
    gmaps_service = GoogleMapsService()
    console_logger.success("Google Maps Service initialized")
except Exception as e:
    console_logger.error(f"Error initializing Google Maps Service: {e}")
    gmaps_service = None

# Initialize Real-Time Data Services (V3 - Separated Flow and Incidents)
try:
    flow_service = FlowService()
    console_logger.success("Flow Service initialized")
except Exception as e:
    console_logger.error(f"Error initializing Flow Service: {e}")
    flow_service = None

try:
    incident_service = IncidentService()
    console_logger.success("Incident Service initialized")
except Exception as e:
    console_logger.error(f"Error initializing Incident Service: {e}")
    incident_service = None

# Auto-disruption service (load interval from persistent settings)
console_logger.info("Initializing Auto-Disruption Service")
auto_service = init_auto_disruption_service(app)  # Will load interval from settings

# Shutdown service on exit
atexit.register(shutdown_auto_disruption_service)

# Initialize Route Recalculation Endpoint (for automatic route updates on disruption changes)
console_logger.info("Initializing Route Recalculation Endpoint")
route_recalculation_endpoint.init_route_recalculation(app, gps_router, dhl_router, console_logger)
console_logger.success("Route Recalculation Endpoint initialized")

# ============================================================================
# USER-REPORTED DISRUPTIONS HELPERS
# ============================================================================
# NOTE: All user disruption handling is now centralized in user_disruptions.py
# This includes: CSV field definitions, formatting, loading, and cleanup.
# Import functions from user_disruptions module as needed.

def get_user_disruptions_for_api() -> list:
    """Load and format user-reported disruptions for API response."""
    rows = load_user_disruption_rows()
    return [format_user_disruption_row(row) for row in rows]

# ============================================================================
# DEMO DISRUPTIONS API
# ============================================================================
# These functions create demo-specific disruption CSV files for routers

def snap_location_to_edge(lat: float, lng: float) -> dict:
    """
    Snap a location to the nearest road edge.
    Returns edge source/target and coordinates.
    """
    try:
        snap_result = mapper.snap_to_nearest_road(lat, lng, max_distance=500)
        if snap_result:
            return {
                'success': True,
                'source': snap_result['edge'][0],
                'target': snap_result['edge'][1],
                'source_lat': snap_result['source_coord']['lat'],
                'source_lon': snap_result['source_coord']['lng'],
                'target_lat': snap_result['target_coord']['lat'],
                'target_lon': snap_result['target_coord']['lng'],
                'road_name': snap_result.get('road_name', 'Unknown'),
                'highway_type': snap_result.get('highway_type', 'unknown')
            }
        return {'success': False, 'error': 'No nearby edge found'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def validate_location_near_road(lat: float, lng: float, max_distance: float = 100) -> dict:
    """
    Validate if a location is within max_distance meters of a road.
    
    Args:
        lat: Latitude
        lng: Longitude
        max_distance: Maximum distance in meters (default 100m)
        
    Returns:
        dict with success status and snapped coordinates if valid
    """
    try:
        snap_result = mapper.snap_to_nearest_road(lat, lng, max_distance=max_distance)
        if snap_result:
            return {
                'valid': True,
                'snapped_lat': snap_result['point']['lat'],
                'snapped_lng': snap_result['point']['lng'],
                'road_name': snap_result.get('road_name', 'Unknown'),
                'distance': snap_result.get('distance', 0)
            }
        return {'valid': False, 'error': 'No road within distance'}
    except Exception as e:
        return {'valid': False, 'error': str(e)}


# Cache for edge data loaded from quezon_city_edges.csv
_edge_data_cache = None
_edge_data_cache_time = 0
EDGE_CACHE_TTL = 3600  # 1 hour cache


def load_edge_data_from_graph() -> dict:
    """
    Load edge data from quezon_city_edges.csv.
    This provides length, road_name, highway_type, and geometry for edges.
    Returns a dict keyed by (source, target) tuple.
    """
    global _edge_data_cache, _edge_data_cache_time
    
    # Return cached data if still valid
    if _edge_data_cache is not None and (time.time() - _edge_data_cache_time) < EDGE_CACHE_TTL:
        return _edge_data_cache
    
    edges_file = Path(Config.DATA_DIR) / 'raw' / 'quezon_city_edges.csv'
    edge_data = {}
    
    if edges_file.exists():
        try:
            with open(edges_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = row.get('source')
                    target = row.get('target')
                    if source and target:
                        key = (source, target)
                        edge_data[key] = {
                            'length': float(row.get('length', 0)),
                            'road_name': row.get('road_name', 'Unknown Road'),
                            'highway_type': row.get('highway_type', 'unclassified'),
                            'geometry': row.get('geometry', ''),
                            'source_lat': float(row.get('source_lat', 0)),
                            'source_lon': float(row.get('source_lon', 0)),
                            'target_lat': float(row.get('target_lat', 0)),
                            'target_lon': float(row.get('target_lon', 0))
                        }
            console_logger.data(f"Loaded {len(edge_data)} edges from quezon_city_edges.csv")
            _edge_data_cache = edge_data
            _edge_data_cache_time = time.time()
        except Exception as e:
            console_logger.warning(f"Error loading quezon_city_edges.csv: {e}")
    else:
        console_logger.warning(f"quezon_city_edges.csv not found at {edges_file}")
    
    return edge_data


def get_edge_properties(source, target) -> dict:
    """
    Get edge properties (length, road_name, highway_type, geometry) for a source-target pair.
    First checks quezon_city_edges.csv cache, returns defaults if not found.
    """
    edge_data = load_edge_data_from_graph()
    key = (str(source), str(target))
    
    if key in edge_data:
        return edge_data[key]
    
    # Try reverse direction
    reverse_key = (str(target), str(source))
    if reverse_key in edge_data:
        return edge_data[reverse_key]
    
    return {
        'length': 0,
        'road_name': 'Unknown Road',
        'highway_type': 'unclassified',
        'geometry': ''
    }


def calculate_speed_from_jam_factor(free_flow_kph: float, jam_factor: float) -> float:
    """
    Calculate actual speed based on free flow speed and jam factor.
    jam_factor: 0 = no traffic (free flow), 10 = standstill
    """
    # Linear interpolation: speed = free_flow * (1 - jam_factor/10)
    # Minimum speed = 5 kph
    return max(5.0, free_flow_kph * (1.0 - (jam_factor / 10.0)))


def get_highway_free_flow_speed(highway_type: str) -> float:
    """
    Get free flow speed based on highway type.
    """
    speed_map = {
        'motorway': 100.0,
        'motorway_link': 80.0,
        'trunk': 80.0,
        'trunk_link': 60.0,
        'primary': 60.0,
        'primary_link': 50.0,
        'secondary': 50.0,
        'secondary_link': 40.0,
        'tertiary': 40.0,
        'tertiary_link': 30.0,
        'residential': 30.0,
        'unclassified': 30.0,
        'service': 20.0,
        'living_street': 15.0
    }
    return speed_map.get(highway_type, 40.0)


def get_available_matched_edges() -> dict:
    """
    Load all available matched edges from matched_edges.csv file.
    Uses free_flow_speed directly from matched_edges.csv.
    Enriches edge data with additional properties from quezon_city_edges.csv (length, geometry, etc.)
    This is the master source of edges that can be used for random disruption generation.
    """
    import csv
    
    matched_edges_file = Path(Config.HERE_OSM_DIR) / 'matched_edges.csv'
    
    all_edges = []
    
    if matched_edges_file.exists():
        try:
            # Pre-load edge data from graph for enrichment
            edge_graph_data = load_edge_data_from_graph()
            
            with open(matched_edges_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = row.get('source')
                    target = row.get('target')
                    
                    if source and target:
                        # Look up edge properties from graph for additional data
                        edge_props = get_edge_properties(source, target)
                        highway_type = edge_props.get('highway_type', 'primary')
                        
                        # Use free_flow_speed from matched_edges.csv (primary source)
                        # Fall back to highway-based calculation if not available
                        csv_free_flow = row.get('free_flow_speed', '')
                        if csv_free_flow and csv_free_flow.strip():
                            try:
                                free_flow_kph = float(csv_free_flow)
                            except ValueError:
                                free_flow_kph = get_highway_free_flow_speed(highway_type)
                        else:
                            free_flow_kph = get_highway_free_flow_speed(highway_type)
                        
                        # Use road_name from matched_edges.csv if available
                        csv_road_name = row.get('road_name', '')
                        road_name = csv_road_name if csv_road_name.strip() else edge_props.get('road_name', 'Unknown Road')
                        
                        # Build edge with enriched data
                        edge = {
                            'id_hash': row.get('id_hash', ''),
                            'source': source,
                            'target': target,
                            'source_lat': row.get('source_lat'),
                            'source_lon': row.get('source_lon'),
                            'target_lat': row.get('target_lat'),
                            'target_lon': row.get('target_lon'),
                            # Use free_flow_speed from CSV
                            'flow_free_flow_kph': free_flow_kph,
                            'road_name': road_name,
                            # Enriched from quezon_city_edges.csv
                            'length': edge_props.get('length', 0),
                            'highway_type': highway_type,
                            'geometry': edge_props.get('geometry', '')
                        }
                        all_edges.append(edge)
            console_logger.data(f"Loaded {len(all_edges)} edges from matched_edges.csv (using free_flow_speed from CSV)")
        except Exception as e:
            console_logger.warning(f"Error loading matched edges: {e}")
            import traceback
            traceback.print_exc()
    else:
        console_logger.warning(f"matched_edges.csv not found at {matched_edges_file}")
    
    # Return same edges for both flow and incidents (they can use any matched edge)
    return {
        'flow_edges': all_edges,
        'incident_edges': all_edges
    }


def select_random_edges_for_demo(flow_count: int, incident_count: int, 
                                  severity_min: float = 0.3, severity_max: float = 0.9) -> dict:
    """
    Select random edges from existing matched edges for demo disruptions.
    Each edge (source, target pair) can only appear once - no duplicates.
    Now includes speed calculation from free flow and jam factor, plus edge length.
    
    Args:
        flow_count: Number of flow disruptions to generate (0 = no flow)
        incident_count: Number of incident disruptions to generate (0 = no incidents)
        severity_min: Minimum severity (0-1)
        severity_max: Maximum severity (0-1)
        
    Returns:
        dict with selected flow and incident data ready for CSV creation
    """
    import random
    from datetime import datetime, timedelta
    
    # Cap the total at 2000 disruptions
    MAX_TOTAL = 2000
    total_requested = flow_count + incident_count
    if total_requested > MAX_TOTAL:
        # Scale down proportionally
        scale = MAX_TOTAL / total_requested
        flow_count = int(flow_count * scale)
        incident_count = int(incident_count * scale)
    
    # Ensure counts are non-negative integers
    flow_count = max(0, int(flow_count))
    incident_count = max(0, int(incident_count))
    
    edges = get_available_matched_edges()
    
    flow_rows = []
    incident_rows = []
    
    # Return early if no edges or both counts are 0
    if flow_count == 0 and incident_count == 0:
        return {'flow_rows': [], 'incident_rows': []}
    
    # Track used edges to prevent duplicates (key: (source, target))
    used_edges = set()
    
    # Get all available edges and shuffle them
    all_flow_edges = list(edges.get('flow_edges', []))
    random.shuffle(all_flow_edges)
    
    # Select unique random flow edges
    if all_flow_edges and flow_count > 0:
        for edge in all_flow_edges:
            if len(flow_rows) >= flow_count:
                break
                
            edge_key = (edge.get('source'), edge.get('target'))
            if edge_key in used_edges:
                continue
            
            used_edges.add(edge_key)
            severity = random.uniform(severity_min, severity_max)
            jam_factor = severity * 10  # 0-10 scale
            
            # Get free flow speed from edge data (from matched_edges.csv free_flow_speed column)
            free_flow_kph = float(edge.get('flow_free_flow_kph', 60))
            
            # Calculate actual speed using jam factor
            flow_speed = calculate_speed_from_jam_factor(free_flow_kph, jam_factor)
            
            # Get edge length and geometry from enriched data
            edge_length = float(edge.get('length', 0))
            geometry = edge.get('geometry', '')
            
            flow_rows.append({
                'id_hash': edge.get('id_hash', f'{int(time.time())}_{len(flow_rows)}'),
                'source_lat': edge.get('source_lat'),
                'source_lon': edge.get('source_lon'),
                'target_lat': edge.get('target_lat'),
                'target_lon': edge.get('target_lon'),
                'source': edge.get('source'),
                'target': edge.get('target'),
                # Enhanced speed calculation
                'flow_speed_kph': round(flow_speed, 2),
                'flow_free_flow_kph': round(free_flow_kph, 2),
                'flow_jam_factor': round(jam_factor, 2),
                'flow_confidence': round(0.7 + random.uniform(0, 0.25), 2),  # 0.7-0.95
                'flow_traversability': 'open',
                # Edge properties from graph
                'length': round(edge_length, 2),
                'highway_type': edge.get('highway_type', 'primary'),
                'road_name': edge.get('road_name', 'Unknown Road'),
                'geometry': geometry
            })
    
    # Select random incident edges (or use flow edges if no incidents available)
    # Incidents should also not duplicate edges already used
    incident_source = list(edges.get('incident_edges', [])) if edges.get('incident_edges') else list(edges.get('flow_edges', []))
    random.shuffle(incident_source)
    incident_types = ['accident', 'construction', 'roadClosure', 'hazard']
    
    if incident_source and incident_count > 0:
        for edge in incident_source:
            if len(incident_rows) >= incident_count:
                break
                
            edge_key = (edge.get('source'), edge.get('target'))
            if edge_key in used_edges:
                continue
            
            used_edges.add(edge_key)
            severity = random.uniform(severity_min, severity_max)
            if severity > 0.7:
                criticality = 'critical'
            elif severity > 0.4:
                criticality = 'major'
            else:
                criticality = 'minor'
            
            incident_type = random.choice(incident_types)
            road_closed = severity > 0.8
            road_name = edge.get('road_name', 'Unknown Road')
            edge_length = float(edge.get('length', 0))
            
            incident_rows.append({
                'source': edge.get('source'),
                'target': edge.get('target'),
                'source_lat': edge.get('source_lat'),
                'source_lon': edge.get('source_lon'),
                'target_lat': edge.get('target_lat'),
                'target_lon': edge.get('target_lon'),
                'incident_id': edge.get('id_hash', f'{int(time.time())}_{len(incident_rows)}'),
                'incident_type': incident_type,
                'incident_criticality': criticality,
                'incident_description': f'Demo {incident_type} on {road_name}',
                'incident_road_closed': road_closed,
                'incident_start_time': datetime.now().isoformat() + 'Z',
                'incident_end_time': (datetime.now() + timedelta(hours=3)).isoformat() + 'Z',
                # Edge properties from graph
                'length': round(edge_length, 2),
                'highway_type': edge.get('highway_type', 'primary'),
                'road_name': road_name
            })
    
    return {
        'flow_rows': flow_rows,
        'incident_rows': incident_rows
    }


def create_demo_disruption_files(demo_id: str, flow_data: list = None, incident_data: list = None,
                                  use_random_edges: bool = True, flow_count: int = 5, incident_count: int = 3,
                                  severity_min: float = 0.3, severity_max: float = 0.9) -> dict:
    """
    Create disruption CSV files for a demo.
    
    Args:
        demo_id: Unique demo identifier
        flow_data: List of flow disruption dictionaries with lat/lng (for custom locations)
        incident_data: List of incident dictionaries with lat/lng (for custom locations)
        use_random_edges: If True, select random edges from existing matched_edges CSV files
        flow_count: Number of random flow disruptions (when use_random_edges=True)
        incident_count: Number of random incidents (when use_random_edges=True)
        severity_min: Minimum severity for random disruptions
        severity_max: Maximum severity for random disruptions
        
    Returns:
        dict with success status, disruption directory path, and generated disruption details
    """
    import csv
    from datetime import datetime
    
    # Create demo disruptions directory
    demo_dir = Path(Config.DISRUPTIONS_DIR) / 'demos' / demo_id
    flow_dir = demo_dir / 'flow'
    incident_dir = demo_dir / 'incidents'
    
    flow_dir.mkdir(parents=True, exist_ok=True)
    incident_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S%f')[:18]
    
    flow_rows = []
    incident_rows = []
    
    if use_random_edges:
        # NEW: Select random edges from existing matched_edges CSV files
        console_logger.info(f"Generating {flow_count} flow and {incident_count} incident disruptions from matched edges")
        selected = select_random_edges_for_demo(
            flow_count=flow_count,
            incident_count=incident_count,
            severity_min=severity_min,
            severity_max=severity_max
        )
        flow_rows = selected['flow_rows']
        incident_rows = selected['incident_rows']
    else:
        # Original mode: snap custom locations to edges
        if flow_data:
            for i, flow in enumerate(flow_data):
                snap = snap_location_to_edge(flow['lat'], flow['lng'])
                if snap['success']:
                    jam_factor = flow.get('severity', 0.5) * 10
                    flow_speed = max(5, 60 - (jam_factor * 5))
                    
                    flow_rows.append({
                        'id_hash': f'demo_{demo_id}_{i}',
                        'source_lat': snap['source_lat'],
                        'source_lon': snap['source_lon'],
                        'target_lat': snap['target_lat'],
                        'target_lon': snap['target_lon'],
                        'source': snap['source'],
                        'target': snap['target'],
                        'flow_speed_kph': flow_speed,
                        'flow_free_flow_kph': 60,
                        'flow_jam_factor': jam_factor,
                        'flow_confidence': 0.9,
                        'flow_traversability': 'open',
                        'highway_type': snap['highway_type'],
                        'road_name': snap['road_name']
                    })
        
        if incident_data:
            for i, incident in enumerate(incident_data):
                snap = snap_location_to_edge(incident['lat'], incident['lng'])
                if snap['success']:
                    severity = incident.get('severity', 0.5)
                    if severity > 0.7:
                        criticality = 'critical'
                    elif severity > 0.4:
                        criticality = 'major'
                    else:
                        criticality = 'minor'
                    
                    incident_rows.append({
                        'source': snap['source'],
                        'target': snap['target'],
                        'source_lat': snap['source_lat'],
                        'source_lon': snap['source_lon'],
                        'target_lat': snap['target_lat'],
                        'target_lon': snap['target_lon'],
                        'incident_id': f'demo_{demo_id}_{i}',
                        'incident_type': incident.get('type', 'construction'),
                        'incident_criticality': criticality,
                        'incident_description': incident.get('description', f'Demo incident on {snap["road_name"]}'),
                        'incident_road_closed': severity > 0.8,
                        'incident_start_time': datetime.now().isoformat() + 'Z',
                        'incident_end_time': '',
                        'highway_type': snap['highway_type'],
                        'road_name': snap['road_name']
                    })
    
    # Write flow CSV
    flow_file = flow_dir / f'flow_{timestamp}.csv'
    if flow_rows:
        with open(flow_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=flow_rows[0].keys())
            writer.writeheader()
            writer.writerows(flow_rows)
        console_logger.success(f"Created demo flow file: {flow_file} with {len(flow_rows)} entries")
    else:
        # Create empty flow file with headers
        with open(flow_file, 'w', newline='') as f:
            f.write('id_hash,source_lat,source_lon,target_lat,target_lon,source,target,flow_speed_kph,flow_free_flow_kph,flow_jam_factor,flow_confidence,flow_traversability,highway_type,road_name\n')
    
    # Write incident CSV
    incident_file = incident_dir / f'incident_{timestamp}.csv'
    if incident_rows:
        with open(incident_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=incident_rows[0].keys())
            writer.writeheader()
            writer.writerows(incident_rows)
        console_logger.success(f"Created demo incident file: {incident_file} with {len(incident_rows)} entries")
    else:
        # Create empty incident file with headers
        with open(incident_file, 'w', newline='') as f:
            f.write('source,target,source_lat,source_lon,target_lat,target_lon,incident_id,incident_type,incident_criticality,incident_description,incident_road_closed,incident_start_time,incident_end_time,highway_type,road_name\n')
    
    # Build response with disruption details for UI preview (includes speed and length)
    disruption_details = {
        'flow': [
            {
                'id_hash': r.get('id_hash', ''),
                'source_lat': float(r['source_lat']),
                'source_lon': float(r['source_lon']),
                'target_lat': float(r['target_lat']),
                'target_lon': float(r['target_lon']),
                'source': r.get('source'),
                'target': r.get('target'),
                # Speed data
                'speed_kph': float(r.get('flow_speed_kph', 0)),
                'free_flow_kph': float(r.get('flow_free_flow_kph', 60)),
                'jam_factor': float(r.get('flow_jam_factor', 0)),
                'flow_confidence': float(r.get('flow_confidence', 0.7)),
                # Edge properties
                'length': float(r.get('length', 0)),
                'highway_type': r.get('highway_type', 'primary'),
                'road_name': r.get('road_name', 'Unknown Road'),
                'geometry': r.get('geometry', '')
            } for r in flow_rows
        ],
        'incidents': [
            {
                'incident_id': r.get('incident_id', ''),
                'source_lat': float(r['source_lat']),
                'source_lon': float(r['source_lon']),
                'target_lat': float(r['target_lat']),
                'target_lon': float(r['target_lon']),
                'source': r.get('source'),
                'target': r.get('target'),
                'type': r.get('incident_type', 'incident'),
                'criticality': r.get('incident_criticality', 'minor'),
                'description': r.get('incident_description', ''),
                'road_closed': r.get('incident_road_closed', False),
                # Edge properties
                'length': float(r.get('length', 0)),
                'highway_type': r.get('highway_type', 'primary'),
                'road_name': r.get('road_name', 'Unknown Road')
            } for r in incident_rows
        ]
    }
    
    return {
        'success': True,
        'demo_id': demo_id,
        'disruption_dir': str(demo_dir),
        'flow_count': len(flow_rows),
        'incident_count': len(incident_rows),
        'disruptions': disruption_details
    }


def cleanup_demo_disruptions(demo_id: str) -> bool:
    """
    Clean up demo disruption files after demo completes.
    
    Args:
        demo_id: Demo identifier to clean up
        
    Returns:
        True if cleanup successful
    """
    import shutil
    
    demo_dir = Path(Config.DISRUPTIONS_DIR) / 'demos' / demo_id
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
        console_logger.info(f"Cleaned up demo disruptions: {demo_id}")
        return True
    return False


# ============================================================
# GLOBAL CACHES - Prevent reloading data on every request
# ============================================================

# Cache for OSM edges with geometry (loaded once, reused across requests)
_edges_cache = {
    'data': None,          # Dataframe with all edges
    'lookup': None,        # Dictionary for fast edge lookup by (source, target)
    'file_mtime': 0,       # File modification time for cache invalidation
    'loaded_at': 0         # Timestamp when cache was loaded
}

# Cache for traffic data (invalidates based on file modification time)
_traffic_cache = {
    'segments': None,       # Processed traffic segments with geometry
    'file_path': None,      # Path to traffic file
    'file_mtime': 0,        # File modification time
    'loaded_at': 0          # Timestamp when cache was loaded
}


def load_edges_with_cache():
    """
    Load OSM edges with geometry using cache.
    Only reloads if file has been modified since last load.
    
    Returns:
        tuple: (edges_df, edge_lookup) or (None, None) on error
    """
    global _edges_cache
    import os
    
    edges_file = str(Config.EDGES_CSV)
    
    try:
        # Get current file modification time
        current_mtime = os.path.getmtime(edges_file)
        
        # Check if cache is valid
        if (_edges_cache['data'] is not None and 
            _edges_cache['lookup'] is not None and
            _edges_cache['file_mtime'] == current_mtime):
            # Cache hit - reuse existing data
            return _edges_cache['data'], _edges_cache['lookup']
        
        console_logger.processing(f"Loading OSM edges with geometry from {Config.EDGES_CSV.name}...")
        edges_df = pd.read_csv(edges_file)
        console_logger.data(f"Loaded {len(edges_df)} OSM edges")
        
        # Build edge lookup dictionary
        edge_lookup = {}
        for _, edge in edges_df.iterrows():
            key = (int(edge['source']), int(edge['target']))
            
            # Parse geometry
            geometry_str = edge['geometry']
            if isinstance(geometry_str, str):
                try:
                    import json
                    geometry = json.loads(geometry_str)
                except (json.JSONDecodeError, ValueError):
                    try:
                        import ast
                        geometry = ast.literal_eval(geometry_str)
                    except (ValueError, SyntaxError):
                        geometry = [[float(edge['source_lat']), float(edge['source_lon'])], 
                                   [float(edge['target_lat']), float(edge['target_lon'])]]
            else:
                geometry = geometry_str
            
            if not isinstance(geometry, list) or len(geometry) < 2:
                geometry = [[float(edge['source_lat']), float(edge['source_lon'])], 
                           [float(edge['target_lat']), float(edge['target_lon'])]]
                
            edge_lookup[key] = {
                'geometry': geometry,
                'road_name': str(edge.get('road_name', 'Unknown Road')),
                'highway_type': str(edge.get('highway_type', 'unknown')),
                'length': float(edge.get('length', 0)),
                'freeFlow_kph': float(edge.get('freeFlow_kph', 50.0)) if pd.notna(edge.get('freeFlow_kph')) else 50.0
            }
        
        # Update cache
        _edges_cache['data'] = edges_df
        _edges_cache['lookup'] = edge_lookup
        _edges_cache['file_mtime'] = current_mtime
        _edges_cache['loaded_at'] = time.time()
        
        console_logger.success(f"Cached {len(edge_lookup)} edges with geometries")
        return edges_df, edge_lookup
        
    except Exception as e:
        console_logger.error(f"Error loading edges: {e}")
        return None, None


def load_traffic_with_cache(edge_lookup):
    """
    Load traffic data with geometry using cache.
    Only reloads if traffic file has changed.
    
    Args:
        edge_lookup: Dictionary mapping (source, target) to edge data
        
    Returns:
        list: Traffic segments with geometry
    """
    global _traffic_cache
    import glob
    import os
    
    try:
        # Find latest flow files from disruptions directory
        disruptions_dir = Config.DISRUPTIONS_DIR
        flow_files = glob.glob(str(disruptions_dir / 'flow' / 'flow_*.csv'))
        
        if not flow_files:
            console_logger.warning("No traffic files found in disruptions/flow/")
            return []
        
        # Get most recent file
        latest_file = max(flow_files, key=os.path.getmtime)
        current_mtime = os.path.getmtime(latest_file)
        
        # Check cache validity
        if (_traffic_cache['segments'] is not None and
            _traffic_cache['file_path'] == latest_file and
            _traffic_cache['file_mtime'] == current_mtime):
            # Cache hit
            return _traffic_cache['segments']
        
        # Cache miss - reload traffic data
        console_logger.processing(f"Loading traffic data from: {os.path.basename(latest_file)}")
        traffic_df = pd.read_csv(latest_file)
        
        traffic_segments = []
        for _, row in traffic_df.iterrows():
            edge_key = (int(row['source']), int(row['target']))
            edge_data = edge_lookup.get(edge_key)
            
            if not edge_data:
                continue
            
            # Determine severity - check for flow_jam_factor (new CSV format)
            jam_factor = float(row.get('flow_jam_factor', row.get('jamFactor', 0.0)))
            if jam_factor >= 8.0:
                severity = 'Heavy'
            elif jam_factor >= 5.0:
                severity = 'Medium'
            else:
                severity = 'Light'
            
            # Sanitize geometry
            geometry = edge_data['geometry']
            if isinstance(geometry, list):
                geometry = [[float(coord[0]), float(coord[1])] for coord in geometry 
                           if len(coord) >= 2 and 
                           not (pd.isna(coord[0]) or pd.isna(coord[1]) or 
                                coord[0] == float('inf') or coord[1] == float('inf'))]
            
            if not geometry or len(geometry) < 2:
                continue
            
            # Use flow_speed_kph or speed_kph (backward compatibility)
            current_speed = float(row.get('flow_speed_kph', row.get('speed_kph', 0.0)))
            free_flow_speed = float(row.get('flow_free_flow_kph', row.get('freeFlow_kph', 50.0)))
            
            traffic_segments.append({
                'type': 'flow',
                'incident_type': str(row.get('incident_type', 'Congestion')),
                'severity': severity,
                'geometry': geometry,
                'road_name': str(row.get('road_name', edge_data['road_name'])),
                'highway_type': str(row.get('highway_type', edge_data['highway_type'])),
                'length': float(edge_data['length']),
                'speed_kph': current_speed,
                'free_flow_kph': free_flow_speed,
                'jam_factor': jam_factor,
                'is_closed': bool(row.get('incident_road_closed', row.get('isClosed', False))),
                'source': int(row['source']),
                'target': int(row['target'])
            })
        
        # Update cache
        _traffic_cache['segments'] = traffic_segments
        _traffic_cache['file_path'] = latest_file
        _traffic_cache['file_mtime'] = current_mtime
        _traffic_cache['loaded_at'] = time.time()
        
        console_logger.success(f"Cached {len(traffic_segments)} traffic segments")
        return traffic_segments
        
    except Exception as e:
        console_logger.error(f"Error loading traffic: {e}")
        return []


def get_dynamic_disruption_file(algorithm: str = 'hc2l', dataset_mode: str = None) -> str:
    """
    Get the disruption directory path for C++ routers.
    
    The C++ routing engines expect a directory path and automatically look for:
    - {path}/flow/flow_*.csv - Latest flow CSV file
    - {path}/incidents/incident_*.csv - Latest incident CSV file
    
    The C++ code parses these CSV files directly (NOT .gr files).
    
    Args:
        algorithm: 'hc2l' or 'dhl' (for backward compatibility, not used)
        dataset_mode: 'none', 'incidents', 'flow', or 'both'
        
    Returns:
        str: Path to disruptions directory, or "" if no disruptions
    """
    # If mode is 'none', return empty string (no disruptions)
    if dataset_mode == 'none':
        return ""
    
    # Check if disruptions directory exists
    if Config.DISRUPTIONS_DIR.exists():
        console_logger.info(f"Using disruption directory: {Config.DISRUPTIONS_DIR}")
        return str(Config.DISRUPTIONS_DIR)
    
    return ""


def enhance_alternative_routes_with_geometry(alternative_routes):
    """
    Alternative routes geometry is now provided by C++ APIs directly.
    Geometry structure (NEW):
        - Each geometry segment includes: edge (source-target), source, target, coordinates, color, highway_type
        - Removed: path_nodes, path_node_ids, distance_meters per segment (distance_meters is at route level only)
        - highway_type now follows the actual road type (not "alternative")
    
    Args:
        alternative_routes: List of alternative route objects from C++ API
        
    Returns:
        list: Alternative routes (unchanged, geometry already from C++)
    """
    if not alternative_routes:
        return []
    
    try:
        enhanced_routes = []
        
        for route in alternative_routes:
            # Check if route already has geometry from C++ API
            if route.get('geometry') and len(route.get('geometry', [])) > 0:
                console_logger.success(f"Alternative route rank {route.get('rank')} has {len(route['geometry'])} geometry segments from C++")
                enhanced_routes.append(route)
            else:
                # Fallback: just pass through the route as-is
                console_logger.warning(f"Alternative route rank {route.get('rank')} has no geometry from C++, will use geometry as-is")
                enhanced_routes.append(route)
        
        console_logger.success(f"Processed {len(enhanced_routes)} alternative routes with geometry")
        return enhanced_routes
        
    except Exception as e:
        console_logger.warning(f"Error processing alternative routes: {e}")
        return alternative_routes


def cleanup_old_traffic_files(mode: str, max_files: int = 10):
    """
    Remove old traffic files, keeping only the latest N files
    
    Args:
        mode: Traffic mode (flow/incidents/both)
        max_files: Maximum number of files to keep per mode
    """
    traffic_pattern = f"traffic_*_{mode}.csv"
    traffic_files = sorted(Config.DISRUPTIONS_DIR.glob(traffic_pattern), reverse=True)
    
    # Keep only the latest max_files
    if len(traffic_files) > max_files:
        files_to_remove = traffic_files[max_files:]
        for old_file in files_to_remove:
            try:
                old_file.unlink()
                console_logger.info(f"Removed old file: {old_file.name}")
            except Exception as e:
                console_logger.warning(f"Failed to remove {old_file.name}: {e}")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_backend_logs')
def get_backend_logs():
    """
    Return backend logs for Developer View
    Optional 'since' parameter to get only new logs
    """
    try:
        since_timestamp = float(request.args.get('since', 0))
        
        # Filter logs newer than 'since' timestamp
        filtered_logs = [
            log for log in backend_logs 
            if log['timestamp'] > since_timestamp
        ]
        
        return jsonify({
            'success': True,
            'logs': filtered_logs,
            'total': len(filtered_logs),
            'buffer_size': len(backend_logs)
        })
    except Exception as e:
        app.logger.error(f"Error retrieving backend logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': []
        })

@app.route('/get_auto_update_status', methods=['GET'])
def get_auto_update_status():
    """Get the status of the auto-disruption service"""
    try:
        auto_service = get_auto_disruption_service()
        if not auto_service:
            return jsonify({
                'success': False,
                'error': 'Auto-disruption service not available'
            })
        
        # Get current disruption hash to detect changes
        current_hash = auto_service._get_disruption_hash()
        
        return jsonify({
            'success': True,
            'update_interval': auto_service.update_interval,
            'last_fetch_time': auto_service.get_last_fetch_time(),
            'next_fetch_time': auto_service.get_next_fetch_time(),
            'active_routes_count': len(auto_service.active_routes),
            'disruption_hash': current_hash,
            'should_fetch': auto_service.should_fetch_now()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/check_disruption_updates', methods=['GET'])
def check_disruption_updates():
    """
    Check if disruptions have been updated since last check.
    Frontend can poll this endpoint to detect when new disruption files are created.
    
    Query params:
      - last_hash: Last known disruption hash (optional)
    
    Returns:
      - updated: Boolean indicating if disruptions changed
      - current_hash: Current disruption hash
      - message: Update message for notification
    """
    try:
        auto_service = get_auto_disruption_service()
        if not auto_service:
            return jsonify({
                'success': False,
                'error': 'Auto-disruption service not available'
            })
        
        last_hash = request.args.get('last_hash', None)
        current_hash = auto_service._get_disruption_hash()
        
        # Check if hash changed
        updated = (last_hash is not None and current_hash != last_hash)
        
        result = {
            'success': True,
            'updated': updated,
            'current_hash': current_hash,
            'last_fetch_time': auto_service.get_last_fetch_time()
        }
        
        if updated:
            result['message'] = '🔄 Disruptions updated! Routes may have changed.'
            result['notification_type'] = 'info'
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/should_fetch_disruptions', methods=['GET'])
def should_fetch_disruptions():
    """Check if disruptions should be fetched (time-based check)"""
    try:
        auto_service = get_auto_disruption_service()
        if not auto_service:
            return jsonify({
                'success': False,
                'error': 'Auto-disruption service not initialized'
            })
        
        should_fetch = auto_service.should_fetch_now()
        
        return jsonify({
            'success': True,
            'should_fetch': should_fetch,
            'last_fetch_time': auto_service.get_last_fetch_time(),
            'next_fetch_time': auto_service.get_next_fetch_time(),
            'update_interval': auto_service.update_interval
        })
        
    except Exception as e:
        app.logger.error(f"Error checking fetch status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/load_disruptions', methods=['GET'])
def load_disruptions():
    """
    Smart disruption loader:
    1. If disruptions are EMPTY → Fetch fresh data
    2. If disruptions EXIST → Return immediately (respecting toggle states)
    
    Time-based fetching: Only re-fetch if update_interval has elapsed
    """
    try:
        auto_service = get_auto_disruption_service()
        
        # Check if disruptions currently exist by checking CSV files
        from config import Config
        
        disruptions_exist = False
        disruptions_size = 0

        # Check if HERE API disruptions exist (flow and incident CSV files)
        # Look for latest flow and incident files in their respective directories
        flow_files = list(Config.FLOW_DIR.glob("flow_*.csv"))
        incident_files = list(Config.INCIDENTS_DIR.glob("incident_*.csv"))

        # Check if we have any recent disruption data (within last 24 hours)
        import time
        current_time = time.time()
        recent_threshold = 24 * 60 * 60  # 24 hours in seconds

        recent_flow_files = [f for f in flow_files if (current_time - f.stat().st_mtime) < recent_threshold]
        recent_incident_files = [f for f in incident_files if (current_time - f.stat().st_mtime) < recent_threshold]

        if recent_flow_files or recent_incident_files:
            # Count disruption records from ONLY the latest files
            total_flow_records = 0
            total_incident_records = 0
            total_user_incidents = 0

            # Get latest flow file and count its records
            if recent_flow_files:
                latest_flow_file = max(recent_flow_files, key=lambda f: f.stat().st_mtime)
                try:
                    flow_df = pd.read_csv(latest_flow_file)
                    total_flow_records = len(flow_df)
                    console_logger.data(f"Latest flow file: {latest_flow_file.name} ({total_flow_records} records)")
                except Exception as e:
                    console_logger.warning(f"Error reading latest flow file {latest_flow_file.name}: {e}")

            # Get latest incident file and count its records
            if recent_incident_files:
                latest_incident_file = max(recent_incident_files, key=lambda f: f.stat().st_mtime)
                try:
                    incident_df = pd.read_csv(latest_incident_file)
                    total_incident_records = len(incident_df)
                    console_logger.data(f"Latest incident file: {latest_incident_file.name} ({total_incident_records} records)")
                except Exception as e:
                    console_logger.warning(f"Error reading latest incident file {latest_incident_file.name}: {e}")

            # Count user-reported incidents
            try:
                user_disruptions = get_user_disruptions_for_api()
                total_user_incidents = len(user_disruptions)
                if total_user_incidents > 0:
                    console_logger.data(f"User-reported incidents: {total_user_incidents} records")
            except Exception as e:
                console_logger.warning(f"Error counting user incidents: {e}")

            disruptions_size = total_flow_records + total_incident_records + total_user_incidents
            disruptions_exist = disruptions_size > 0

            if disruptions_exist:
                console_logger.info(f"Total disruptions: {total_flow_records} flow + {total_incident_records} HERE incidents + {total_user_incidents} user incidents = {disruptions_size} total records")
                console_logger.data(f"Latest flow file: {latest_flow_file.name if recent_flow_files else 'None'}")
                console_logger.data(f"Latest incident file: {latest_incident_file.name if recent_incident_files else 'None'}")
            else:
                console_logger.info("Latest HERE API disruption files exist but are empty")
        else:
            # Even if no HERE API files, check for user incidents
            try:
                user_disruptions = get_user_disruptions_for_api()
                total_user_incidents = len(user_disruptions)
                if total_user_incidents > 0:
                    disruptions_size = total_user_incidents
                    disruptions_exist = True
                    console_logger.info(f"User-reported incidents found: {total_user_incidents} records")
                else:
                    console_logger.info(f"No recent HERE API disruption files found (checked within {recent_threshold/3600:.1f} hours)")
            except Exception:
                console_logger.info(f"No recent HERE API disruption files found (checked within {recent_threshold/3600:.1f} hours)")
        
        # Decision logic:
        # 1. If NO disruptions exist → MUST fetch
        # 2. If disruptions exist → Check time interval
        if not disruptions_exist:
            console_logger.info("Disruptions empty - fetching fresh data")
            
            # Fetch fresh data
            flow_metadata = {}
            incident_metadata = {}
            
            if flow_service:
                flow_metadata = flow_service.fetch_and_save()
            
            if incident_service:
                incident_metadata = incident_service.fetch_and_save()
            
            # Update fetch time
            if auto_service:
                auto_service.last_fetch_time = time.time()
            
            console_logger.success("Fresh disruptions fetched and loaded")
            
            return jsonify({
                'success': True,
                'action': 'fetched',
                'message': 'Fresh disruptions fetched (was empty)',
                'total_edges': disruptions_size,
                'fetch_time': auto_service.get_last_fetch_time() if auto_service else None
            })
        
        else:
            # Disruptions exist - check if we should refresh based on time interval
            should_fetch = auto_service.should_fetch_now() if auto_service else False
            
            if should_fetch:
                console_logger.info("Disruptions exist and update interval expired - refreshing...")
                
                # Fetch fresh data
                flow_metadata = {}
                incident_metadata = {}
                
                if flow_service:
                    flow_metadata = flow_service.fetch_and_save()
                
                if incident_service:
                    incident_metadata = incident_service.fetch_and_save()
                
                # Update fetch time
                if auto_service:
                    auto_service.last_fetch_time = time.time()
                
                console_logger.success("Disruptions refreshed")
                
                return jsonify({
                    'success': True,
                    'action': 'refreshed',
                    'message': 'Disruptions refreshed (update interval expired)',
                    'total_edges': disruptions_size,
                    'fetch_time': auto_service.get_last_fetch_time() if auto_service else None
                })
            
            else:
                # Disruptions exist and interval hasn't expired - use cached data
                console_logger.info(f"Using cached disruptions ({disruptions_size} edges)")
                
                next_fetch = auto_service.get_next_fetch_time() if auto_service else None
                if next_fetch:
                    # Convert ISO timestamp string to Unix timestamp for calculation
                    from datetime import datetime
                    try:
                        next_fetch_dt = datetime.fromisoformat(next_fetch.replace('Z', '+00:00'))
                        next_fetch_timestamp = next_fetch_dt.timestamp()
                        time_until_next = next_fetch_timestamp - time.time()
                    except (ValueError, TypeError):
                        time_until_next = 0
                else:
                    time_until_next = 0
                
                return jsonify({
                    'success': True,
                    'action': 'cached',
                    'message': 'Using cached disruptions',
                    'total_edges': disruptions_size,
                    'time_until_next_fetch': max(0, time_until_next),
                    'fetch_time': auto_service.get_last_fetch_time() if auto_service else None
                })
    
    except Exception as e:
        app.logger.error(f"Error in load_disruptions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/request_new_dataset')
def request_new_dataset():
    """Fetch latest flow and incident data using separated services"""
    try:
        flow_metadata = {}
        incident_metadata = {}
        total_edges = 0
        
        # Fetch flow data
        if flow_service:
            flow_metadata = flow_service.fetch_and_save()
            total_edges += flow_metadata.get('total_edges', 0)
        
        # Fetch incident data
        if incident_service:
            incident_metadata = incident_service.fetch_and_save()
            total_edges += incident_metadata.get('total_edges', 0)
        
        # Update auto-disruption service's last fetch time
        auto_service = get_auto_disruption_service()
        if auto_service:
            auto_service.last_fetch_time = time.time()
        
        return jsonify({
            'success': True,
            'message': f'Data updated: {total_edges} total edges',
            'flow_metadata': flow_metadata,
            'incident_metadata': incident_metadata
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })



@app.route('/save_custom_disruption', methods=['POST'])
def save_custom_disruption():
    """
    Save a custom user-reported incident to CSV and trigger route updates
    
    This endpoint:
    1. Validates incident data (location, type, criticality, description, etc.)
    2. Saves the incident to timestamped user_incident CSV
    3. Triggers auto-disruption service to recalculate active routes
    """
    data = request.json
    console_logger.info("=== SAVING CUSTOM INCIDENT ===")
    console_logger.data(f"Received data keys: {list(data.keys())}")
    
    try:
        import uuid
        
        # Extract and validate location data
        lat = float(data.get('lat', 0))
        lng = float(data.get('lng', 0))
        snapped_lat = float(data.get('snapped_lat', lat))
        snapped_lng = float(data.get('snapped_lng', lng))
        source_lat = float(data.get('source_lat', snapped_lat))
        source_lng = float(data.get('source_lng', snapped_lng))
        target_lat = float(data.get('target_lat', snapped_lat))
        target_lng = float(data.get('target_lng', snapped_lng))
        source_id = int(data.get('source_id', 0))
        target_id = int(data.get('target_id', 0))
        road_name = str(data.get('road_name', 'Custom Report'))
        highway_type = str(data.get('highway_type', 'unknown'))
        
        # Extract incident details
        incident_type = data.get('incident_type', 'user-incident').lower()
        incident_criticality = data.get('incident_criticality', 'minor').lower()
        incident_description = data.get('incident_description', '')
        incident_road_closed = data.get('incident_road_closed', False)
        incident_start_time = data.get('incident_start_time', datetime.now().isoformat())
        incident_end_time = data.get('incident_end_time', '')
        
        # Ensure road_closed is boolean string
        if isinstance(incident_road_closed, str):
            incident_road_closed = incident_road_closed.lower() in ('true', '1', 'yes')
        road_closed_str = 'true' if incident_road_closed else 'false'
        
        console_logger.success(f"Parsed incident: {incident_type} ({incident_criticality})")
        console_logger.data(f"Location: ({lat:.4f}, {lng:.4f}) → snap: ({snapped_lat:.4f}, {snapped_lng:.4f})")
        console_logger.data(f"Road: {road_name} (Edge: {source_id}→{target_id})")
        console_logger.data(f"Closed: {road_closed_str}")
        
        # Create incident record with standardized format (15 fields)
        incident_id = str(uuid.uuid4())[:8]
        
        incident_record = {
            'source': source_id,
            'target': target_id,
            'source_lat': source_lat,
            'source_lon': source_lng,
            'target_lat': target_lat,
            'target_lon': target_lng,
            'incident_id': incident_id,
            'incident_type': incident_type,
            'incident_criticality': incident_criticality,
            'incident_description': incident_description,
            'incident_road_closed': road_closed_str,
            'incident_start_time': incident_start_time,
            'incident_end_time': incident_end_time,
            'highway_type': highway_type,
            'road_name': road_name
        }
        
        # Save to timestamped user incident CSV
        console_logger.processing("Saving to timestamped user_incident CSV...")
        from user_disruptions import ensure_user_disruption_fieldnames, load_user_disruption_rows, cleanup_old_user_incidents
        
        # Create timestamped filename
        timestamp_str = datetime.now().strftime("%Y%m%dT%H%M%S%f")[:17]
        user_incident_dir = Config.DISRUPTIONS_DIR / "user_incident"
        user_incident_dir.mkdir(parents=True, exist_ok=True)
        csv_path = user_incident_dir / f"user_incident_{timestamp_str}.csv"
        
        # Load existing user disruptions from latest file (if any)
        rows = load_user_disruption_rows()
        rows.append(incident_record)
        
        # Write to new timestamped file
        fieldnames = ensure_user_disruption_fieldnames()
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        # Cleanup old files (keep max 10)
        cleanup_old_user_incidents(max_files=10)
        
        console_logger.success(f"Saved to: {csv_path.name}")
        console_logger.success("User incident saved - will be loaded by C++ routing API")
        
        # Trigger auto route recalculation if an active route exists
        try:
            auto_service = get_auto_disruption_service()
            if auto_service and auto_service.active_routes:
                console_logger.info("Triggering auto route recalculation due to custom incident added...")
                # Manually trigger recalculation for each active route
                for route_id, route_info in list(auto_service.active_routes.items()):
                    auto_service._trigger_route_recalculation(route_id, route_info)
                console_logger.success("Auto route recalculation triggered")
        except Exception as e:
            console_logger.warning(f"Could not trigger auto route recalculation: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Custom incident saved: {road_name}',
            'incident_id': incident_id,
            'timestamp': incident_start_time,
            'road_name': road_name,
            'incident_type': incident_type,
            'criticality': incident_criticality
        })
        
    except ValueError as e:
        console_logger.error(f"Validation error: {e}")
        return jsonify({
            'success': False,
            'error': f'Invalid data format: {str(e)}'
        }), 400
    except Exception as e:
        console_logger.error(f"Error saving incident: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Error saving incident: {str(e)}'
        }), 500


@app.route('/report_disruption', methods=['POST'])
def report_disruption():
    """
    Report an incident location and map it to nearby HERE API incidents
    
    This endpoint:
    1. Takes a user-pinned location
    2. Snaps it to the nearest road
    3. Finds nearby HERE API incidents on that road
    4. Returns the incident info without saving custom user-created incidents
    
    IMPORTANT: Only displays HERE API incidents, not custom user-created ones
    """
    data = request.json
    console_logger.data(f"Received location report: {data}")
    
    try:
        # Extract location
        lat = float(data.get('lat', 0))
        lng = float(data.get('lng', 0))
        
        # Quick validation
        if lat < 14.0 or lat > 15.0 or lng < 120.5 or lng > 121.5:
            return jsonify({
                'success': False,
                'error': 'Location outside Quezon City bounds'
            })
        
        console_logger.processing(f"Snapping location ({lat:.4f}, {lng:.4f}) to nearest road...")
        
        # Snap to nearest OSM road
        snap_result = mapper.snap_to_nearest_road(lat, lng, max_distance=100)
        
        if snap_result is None:
            return jsonify({
                'success': False,
                'error': 'No road found within 100m of this location'
            })
        
        # Extract snapped edge info
        source_id = snap_result['edge'][0]
        target_id = snap_result['edge'][1]
        road_name = snap_result['road_name']
        snapped_lat = snap_result['projection_point']['lat']
        snapped_lng = snap_result['projection_point']['lng']
        
        console_logger.success(f"Snapped to road: {road_name} (Edge: {source_id}→{target_id})")
        
        # Check if any HERE API incidents exist on this road
        # Load latest incident CSV if it exists
        incident_dir = Config.INCIDENTS_DIR
        incident_files = sorted(incident_dir.glob("incident_*.csv"), reverse=True)
        
        nearby_incidents = []
        if incident_files:
            latest_incident_file = incident_files[0]
            try:
                incidents_df = pd.read_csv(latest_incident_file)
                
                # Find incidents on this edge (same source/target or reverse)
                edge_incidents = incidents_df[
                    ((incidents_df['source'] == source_id) & (incidents_df['target'] == target_id)) |
                    ((incidents_df['source'] == target_id) & (incidents_df['target'] == source_id))
                ]
                
                if not edge_incidents.empty:
                    nearby_incidents = edge_incidents.to_dict('records')
                    console_logger.warning(f"Found {len(nearby_incidents)} HERE API incident(s) on this road:")
                    for incident in nearby_incidents:
                        console_logger.data(f"- {incident.get('incident_type')}: {incident.get('incident_description')}")
                        console_logger.data(f"  Severity: {incident.get('incident_criticality')}, Closed: {incident.get('incident_road_closed')}")
                
            except Exception as e:
                console_logger.warning(f"Error reading incident file: {e}")
        
        # Return response (no custom incident is saved)
        response_data = {
            'success': True,
            'message': 'Location mapped to road' if not nearby_incidents else f'⚠️ Found {len(nearby_incidents)} incident(s) on this road',
            'road_name': road_name,
            'edge': {'source': source_id, 'target': target_id},
            'snapped_location': {'lat': snapped_lat, 'lng': snapped_lng},
            'nearby_incidents': nearby_incidents,
            'incident_count': len(nearby_incidents)
        }
        
        # Only show warning if incidents exist
        if nearby_incidents:
            response_data['warning'] = 'Cannot report disruption: active incidents exist on this road. Use incident management instead.'
        
        return jsonify(response_data)
        
    except Exception as e:
        console_logger.error(f"Error in report_disruption: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })



@app.route('/user_disruptions', methods=['GET'])
def get_user_disruptions():
    """Return all user-reported disruptions for management in the UI."""
    try:
        disruptions = get_user_disruptions_for_api()
        return jsonify({
            'success': True,
            'disruptions': disruptions,
            'count': len(disruptions)
        })
    except Exception as e:
        app.logger.error(f"Error loading user disruptions: {e}")
        return jsonify({'success': False, 'error': str(e), 'disruptions': []})


@app.route('/user_disruptions/<incident_id>', methods=['DELETE'])
def delete_user_disruption(incident_id):
    """
    Delete a user-reported incident by incident_id.
    
    Creates a NEW timestamped user_incident file without the deleted incident.
    This triggers route recalculation when C++ API detects the new file.
    """
    from user_disruptions import ensure_user_disruption_fieldnames, load_user_disruption_rows, cleanup_old_user_incidents
    
    rows = load_user_disruption_rows()
    initial_count = len(rows)
    rows_to_keep = [row for row in rows if row.get('incident_id') != incident_id]

    if len(rows_to_keep) == initial_count:
        return jsonify({'success': False, 'error': 'Custom incident not found'}), 404

    # Create NEW timestamped file with remaining incidents
    timestamp_str = datetime.now().strftime("%Y%m%dT%H%M%S%f")[:17]
    user_incident_dir = Config.DISRUPTIONS_DIR / "user_incident"
    user_incident_dir.mkdir(parents=True, exist_ok=True)
    csv_path = user_incident_dir / f"user_incident_{timestamp_str}.csv"
    
    # Write to new timestamped file
    fieldnames = ensure_user_disruption_fieldnames()
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_keep)

        console_logger.info("=== DELETING CUSTOM INCIDENT ===")
        console_logger.data(f"Deleted incident_id: {incident_id}")
        console_logger.data(f"Remaining incidents: {len(rows_to_keep)}")
        console_logger.success(f"Created new timestamped file: {csv_path.name}")
        console_logger.success("C++ API will reload updated user incidents")

    # Cleanup old files (keep max 10)
    cleanup_old_user_incidents(max_files=10)

    # Trigger auto route recalculation if an active route exists
    try:
        auto_service = get_auto_disruption_service()
        if auto_service and auto_service.active_routes:
            console_logger.info("Triggering auto route recalculation due to custom incident removed...")
            # Manually trigger recalculation for each active route
            for route_id, route_info in list(auto_service.active_routes.items()):
                auto_service._trigger_route_recalculation(route_id, route_info)
            console_logger.success("Auto route recalculation triggered")
    except Exception as e:
        console_logger.warning(f"Could not trigger auto route recalculation: {e}")

    return jsonify({
        'success': True, 
        'deleted': incident_id, 
        'remaining': len(rows_to_keep)
    })


# ============================================================================
# DEMO DISRUPTIONS API ROUTES
# ============================================================================

@app.route('/api/demo/disruptions', methods=['POST'])
def create_demo_disruptions():
    """
    Create disruption files for a demo run.
    
    Request body:
    {
        "demo_id": "unique-demo-id",
        "use_random_edges": true,  // NEW: use matched edges from existing CSVs
        "flow_count": 5,           // NEW: number of random flow disruptions
        "incident_count": 3,       // NEW: number of random incidents
        "severity_min": 0.3,
        "severity_max": 0.9,
        "flow_data": [...],        // Optional: custom flow locations (when use_random_edges=false)
        "incident_data": [...]     // Optional: custom incident locations
    }
    
    Returns:
    {
        "success": true,
        "disruption_dir": "/path/to/demo/disruptions",
        "flow_count": 5,
        "incident_count": 3,
        "disruptions": {
            "flow": [...],
            "incidents": [...]
        }
    }
    """
    try:
        data = request.json
        demo_id = data.get('demo_id')
        
        if not demo_id:
            return jsonify({'success': False, 'error': 'demo_id is required'}), 400
        
        # Check for new random edge mode (default: true)
        use_random_edges = data.get('use_random_edges', True)
        flow_count = data.get('flow_count', 5)
        incident_count = data.get('incident_count', 3)
        severity_min = data.get('severity_min', 0.3)
        severity_max = data.get('severity_max', 0.9)
        
        # Legacy custom location data
        flow_data = data.get('flow_data', [])
        incident_data = data.get('incident_data', [])
        
        console_logger.processing(f"Creating demo disruptions for: {demo_id}")
        if use_random_edges:
            console_logger.data(f"  Mode: Random from matched edges")
            console_logger.data(f"  Flow count: {flow_count}, Incident count: {incident_count}")
        else:
            console_logger.data(f"  Mode: Custom locations")
            console_logger.data(f"  Flow items: {len(flow_data)}, Incident items: {len(incident_data)}")
        
        result = create_demo_disruption_files(
            demo_id=demo_id,
            flow_data=flow_data,
            incident_data=incident_data,
            use_random_edges=use_random_edges,
            flow_count=flow_count,
            incident_count=incident_count,
            severity_min=severity_min,
            severity_max=severity_max
        )
        
        if result['success']:
            console_logger.success(f"Demo disruptions created: {result['disruption_dir']}")
            console_logger.data(f"  Generated: {result['flow_count']} flow, {result['incident_count']} incidents")
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        console_logger.error(f"Error creating demo disruptions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/disruptions/<demo_id>', methods=['DELETE'])
def delete_demo_disruptions(demo_id):
    """
    Clean up disruption files for a completed demo.
    
    Returns:
    {
        "success": true,
        "demo_id": "unique-demo-id"
    }
    """
    try:
        if cleanup_demo_disruptions(demo_id):
            return jsonify({'success': True, 'demo_id': demo_id})
        else:
            return jsonify({'success': False, 'error': 'Demo disruptions not found'}), 404
    except Exception as e:
        console_logger.error(f"Error cleaning up demo disruptions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/snap_disruptions', methods=['POST'])
def snap_demo_disruptions():
    """
    Snap disruption locations to road edges without creating files.
    Useful for previewing where disruptions will appear.
    
    Request body:
    {
        "locations": [{"lat": 14.65, "lng": 121.05}, ...]
    }
    
    Returns snapped locations with edge information.
    """
    try:
        data = request.json
        locations = data.get('locations', [])
        
        results = []
        for loc in locations:
            snap = snap_location_to_edge(loc['lat'], loc['lng'])
            snap['original'] = {'lat': loc['lat'], 'lng': loc['lng']}
            results.append(snap)
        
        return jsonify({
            'success': True,
            'snapped': results,
            'count': len(results)
        })
        
    except Exception as e:
        console_logger.error(f"Error snapping demo disruptions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/validate_location', methods=['POST'])
def validate_demo_location():
    """
    Validate if a location is near a road (within specified distance).
    Used for random route generation to ensure points are near roads.
    
    Request body:
    {
        "lat": 14.65,
        "lng": 121.05,
        "max_distance": 100  // meters, default 100
    }
    
    Returns:
    {
        "valid": true/false,
        "snapped_lat": 14.65,
        "snapped_lng": 121.05,
        "road_name": "EDSA",
        "distance": 45.2  // meters to nearest road
    }
    """
    try:
        data = request.json
        lat = data.get('lat')
        lng = data.get('lng')
        max_distance = data.get('max_distance', 100)
        
        if lat is None or lng is None:
            return jsonify({'valid': False, 'error': 'lat and lng are required'}), 400
        
        result = validate_location_near_road(lat, lng, max_distance)
        return jsonify(result)
        
    except Exception as e:
        console_logger.error(f"Error validating location: {e}")
        return jsonify({'valid': False, 'error': str(e)}), 500


@app.route('/api/demo/validate_locations_batch', methods=['POST'])
def validate_locations_batch():
    """
    Validate multiple locations in one request to reduce round trips.
    
    Request body:
    {
        "locations": [{"lat": 14.65, "lng": 121.05}, ...],
        "max_distance": 100
    }
    
    Returns:
    {
        "success": true,
        "results": [{"valid": true, "snapped_lat": ..., ...}, ...]
    }
    """
    try:
        data = request.json
        locations = data.get('locations', [])
        max_distance = data.get('max_distance', 100)
        
        results = []
        for loc in locations:
            lat = loc.get('lat')
            lng = loc.get('lng')
            if lat is not None and lng is not None:
                result = validate_location_near_road(lat, lng, max_distance)
                results.append(result)
            else:
                results.append({'valid': False, 'error': 'Missing coordinates'})
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        console_logger.error(f"Error validating batch locations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/random_road_points', methods=['POST'])
def get_random_road_points():
    """
    Get random valid road points directly from the road network.
    Much faster than generating random lat/lng and validating.
    
    Request body:
    {
        "count": 10,
        "min_lat": 14.5, "max_lat": 14.8,
        "min_lng": 120.9, "max_lng": 121.2
    }
    
    Returns:
    {
        "success": true,
        "points": [{"lat": 14.65, "lng": 121.05, "road_name": "EDSA"}, ...]
    }
    """
    import random
    
    try:
        data = request.json or {}
        count = data.get('count', 10)
        
        # Get QC boundaries
        min_lat = data.get('min_lat', 14.55)
        max_lat = data.get('max_lat', 14.78)
        min_lng = data.get('min_lng', 120.98)
        max_lng = data.get('max_lng', 121.12)
        
        # Get edges from the graph
        edges = get_available_matched_edges()
        all_edges = edges.get('flow_edges', [])
        
        if not all_edges:
            # Fallback: try to get edges from the road network
            return jsonify({'success': False, 'error': 'No road edges available'}), 500
        
        # Filter edges within bounds
        valid_edges = []
        for edge in all_edges:
            try:
                src_lat = float(edge.get('source_lat', 0))
                src_lng = float(edge.get('source_lon', 0))
                if min_lat <= src_lat <= max_lat and min_lng <= src_lng <= max_lng:
                    valid_edges.append({
                        'lat': src_lat,
                        'lng': src_lng,
                        'road_name': edge.get('road_name', 'Unknown Road'),
                        'highway_type': edge.get('highway_type', 'unknown')
                    })
                
                tgt_lat = float(edge.get('target_lat', 0))
                tgt_lng = float(edge.get('target_lon', 0))
                if min_lat <= tgt_lat <= max_lat and min_lng <= tgt_lng <= max_lng:
                    valid_edges.append({
                        'lat': tgt_lat,
                        'lng': tgt_lng,
                        'road_name': edge.get('road_name', 'Unknown Road'),
                        'highway_type': edge.get('highway_type', 'unknown')
                    })
            except (ValueError, TypeError):
                continue
        
        if not valid_edges:
            return jsonify({'success': False, 'error': 'No edges within bounds'}), 500
        
        # Sample unique random points
        sample_size = min(count, len(valid_edges))
        selected = random.sample(valid_edges, sample_size)
        
        # If we need more than available, duplicate with slight variation
        while len(selected) < count:
            base = random.choice(valid_edges)
            selected.append({
                'lat': base['lat'] + random.uniform(-0.001, 0.001),
                'lng': base['lng'] + random.uniform(-0.001, 0.001),
                'road_name': base['road_name'],
                'highway_type': base['highway_type']
            })
        
        return jsonify({
            'success': True,
            'points': selected,
            'count': len(selected)
        })
        
    except Exception as e:
        console_logger.error(f"Error getting random road points: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/random_edges', methods=['POST'])
def get_random_edges():
    """
    Get random road edges for demo disruption preview.
    These are actual road edges from existing matched flow/incident data.
    Includes full road geometry for proper visualization.
    
    Request body:
    {
        "flow_count": 5,
        "incident_count": 3,
        "severity_min": 0,
        "severity_max": 1
    }
    
    Returns:
    {
        "success": true,
        "flow": [...],
        "incidents": [...]
    }
    """
    try:
        data = request.json or {}
        flow_count = data.get('flow_count', 5)
        incident_count = data.get('incident_count', 3)
        severity_min = data.get('severity_min', 0)
        severity_max = data.get('severity_max', 1)
        
        selected = select_random_edges_for_demo(
            flow_count=flow_count,
            incident_count=incident_count,
            severity_min=severity_min,
            severity_max=severity_max
        )
        
        # Load edge geometry lookup
        _, edge_lookup = load_edges_with_cache()
        
        # Format for preview with geometry
        flow_preview = []
        for r in selected['flow_rows']:
            source = int(r.get('source', 0))
            target = int(r.get('target', 0))
            edge_key = (source, target)
            
            # Get geometry from lookup
            edge_data = edge_lookup.get(edge_key, {}) if edge_lookup else {}
            geometry = edge_data.get('geometry', None)
            
            # Fallback to source/target line if no geometry
            if not geometry or len(geometry) < 2:
                geometry = [
                    [float(r['source_lat']), float(r['source_lon'])],
                    [float(r['target_lat']), float(r['target_lon'])]
                ]
            
            # Calculate severity label from jam_factor
            jam_factor = float(r['flow_jam_factor'])
            if jam_factor >= 6.0:
                severity = 'Heavy'
            elif jam_factor >= 3.0:
                severity = 'Medium'
            else:
                severity = 'Light'
            
            flow_preview.append({
                'id_hash': r.get('id_hash', ''),
                'source': source,
                'target': target,
                'source_lat': float(r['source_lat']),
                'source_lon': float(r['source_lon']),
                'target_lat': float(r['target_lat']),
                'target_lon': float(r['target_lon']),
                # 'flow_speed_kph': float(r.get('flow_speed_kph', 30)),
                # 'flow_free_flow_kph': float(r.get('flow_free_flow_kph', 60)),
                # 'flow_jam_factor': jam_factor,
                # 'flow_confidence': float(r.get('flow_confidence', 0.95)),
                # 'flow_traversability': r.get('flow_traversability', 'open'),
                'jam_factor': jam_factor,
                'severity': severity,
                'road_name': r['road_name'],
                'highway_type': r['highway_type'],
                'geometry': geometry,
                'type': 'flow'
            })
        
        incident_preview = []
        for r in selected['incident_rows']:
            source = int(r.get('source', 0))
            target = int(r.get('target', 0))
            edge_key = (source, target)
            
            # Get geometry from lookup
            edge_data = edge_lookup.get(edge_key, {}) if edge_lookup else {}
            geometry = edge_data.get('geometry', None)
            
            # Fallback to source/target line if no geometry
            if not geometry or len(geometry) < 2:
                geometry = [
                    [float(r['source_lat']), float(r['source_lon'])],
                    [float(r['target_lat']), float(r['target_lon'])]
                ]
            
            incident_preview.append({
                'incident_id': r.get('incident_id', ''),
                'source': source,
                'target': target,
                'source_lat': float(r['source_lat']),
                'source_lon': float(r['source_lon']),
                'target_lat': float(r['target_lat']),
                'target_lon': float(r['target_lon']),
                # 'incident_type': r['incident_type'],
                # 'incident_criticality': r['incident_criticality'],
                # 'incident_description': r.get('incident_description', ''),
                # 'incident_road_closed': r.get('incident_road_closed', False),
                'type': r['incident_type'],
                'criticality': r['incident_criticality'],
                'road_closed': r.get('incident_road_closed', False),
                'road_name': r['road_name'],
                'highway_type': r['highway_type'],
                'geometry': geometry,
                'is_incident': True
            })
        
        return jsonify({
            'success': True,
            'flow': flow_preview,
            'incidents': incident_preview,
            'flow_count': len(flow_preview),
            'incident_count': len(incident_preview)
        })
        
    except Exception as e:
        console_logger.error(f"Error getting random edges: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# DEMO CONFIGURATION FILE STORAGE API
# ============================================================================
# Stores demo configurations as JSON files in data/demos/configs/

DEMO_CONFIGS_DIR = Path(Config.DATA_DIR) / 'demos' / 'configs'
DEMO_RESULTS_DIR = Path(Config.DATA_DIR) / 'demos' / 'results'

# Ensure directories exist
DEMO_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
DEMO_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@app.route('/api/demo/configs', methods=['GET'])
def list_demo_configs():
    """
    List all saved demo configurations.
    
    Returns:
    {
        "success": true,
        "configs": [...]
    }
    """
    try:
        configs = []
        for config_file in sorted(DEMO_CONFIGS_DIR.glob('*.json'), reverse=True):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    configs.append(config)
            except Exception as e:
                console_logger.warning(f"Error loading config {config_file}: {e}")
        
        return jsonify({
            'success': True,
            'configs': configs,
            'count': len(configs)
        })
    except Exception as e:
        console_logger.error(f"Error listing configs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Demo config disruption directory path
DEMO_DISRUPTIONS_DIR = DEMO_CONFIGS_DIR / 'disruptions'


def generate_disruption_key() -> str:
    """Generate a unique disruption key (UUID)."""
    import uuid
    return str(uuid.uuid4())[:8]


def get_demo_disruption_path(disruption_key: str) -> Path:
    """Get the path to a demo's disruption folder."""
    return DEMO_DISRUPTIONS_DIR / disruption_key


def save_disruption_set_to_csv(disruption_key: str, set_key: str, disruptions: dict) -> dict:
    """
    Save a disruption set to CSV files compatible with C++ APIs.
    
    Args:
        disruption_key: The unique demo disruption folder key (UUID)
        set_key: The set key (e.g., 'all', 'trial_0', 'route_1', 'trial_0_route_1')
        disruptions: Dict with 'flow' and 'incidents' lists
        
    Returns:
        Dict with paths to created files
    """
    import csv
    from datetime import datetime
    
    # Create folder structure: data/demos/configs/disruptions/{key}/{set_key}/flow/ and incidents/
    base_path = DEMO_DISRUPTIONS_DIR / disruption_key / set_key
    flow_dir = base_path / 'flow'
    incidents_dir = base_path / 'incidents'
    flow_dir.mkdir(parents=True, exist_ok=True)
    incidents_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
    
    flow_file = None
    incident_file = None
    
    # Write flow CSV (same format as HERE API)
    flow_data = disruptions.get('flow', [])
    if flow_data:
        flow_file = flow_dir / f'flow_{timestamp}.csv'
        flow_headers = [
            'id_hash', 'source_lat', 'source_lon', 'target_lat', 'target_lon',
            'source', 'target', 'flow_speed_kph', 'flow_free_flow_kph',
            'flow_jam_factor', 'flow_confidence', 'flow_traversability',
            'highway_type', 'road_name'
        ]
        with open(flow_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=flow_headers, extrasaction='ignore')
            writer.writeheader()
            for row in flow_data:
                writer.writerow(row)
        console_logger.data(f"Saved {len(flow_data)} flow entries to {flow_file}")
    else:
        # Create empty flow file with headers
        flow_file = flow_dir / f'flow_{timestamp}.csv'
        with open(flow_file, 'w', newline='') as f:
            f.write('id_hash,source_lat,source_lon,target_lat,target_lon,source,target,flow_speed_kph,flow_free_flow_kph,flow_jam_factor,flow_confidence,flow_traversability,highway_type,road_name\n')
    
    # Write incident CSV (same format as HERE API)
    incident_data = disruptions.get('incidents', [])
    if incident_data:
        incident_file = incidents_dir / f'incident_{timestamp}.csv'
        incident_headers = [
            'source', 'target', 'source_lat', 'source_lon', 'target_lat', 'target_lon',
            'incident_id', 'incident_type', 'incident_criticality', 'incident_description',
            'incident_road_closed', 'incident_start_time', 'incident_end_time',
            'highway_type', 'road_name'
        ]
        with open(incident_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=incident_headers, extrasaction='ignore')
            writer.writeheader()
            for row in incident_data:
                writer.writerow(row)
        console_logger.data(f"Saved {len(incident_data)} incident entries to {incident_file}")
    else:
        # Create empty incident file with headers
        incident_file = incidents_dir / f'incident_{timestamp}.csv'
        with open(incident_file, 'w', newline='') as f:
            f.write('source,target,source_lat,source_lon,target_lat,target_lon,incident_id,incident_type,incident_criticality,incident_description,incident_road_closed,incident_start_time,incident_end_time,highway_type,road_name\n')
    
    return {
        'flow_file': str(flow_file) if flow_file else None,
        'incident_file': str(incident_file) if incident_file else None,
        'flow_count': len(flow_data),
        'incident_count': len(incident_data),
        'disruption_dir': str(base_path)
    }


@app.route('/api/demo/configs', methods=['POST'])
def save_demo_config():
    """
    Save a new demo configuration.
    
    Disruptions are stored separately in CSV files at:
    data/demos/configs/disruptions/{disruptionKey}/{setKey}/flow/ and incidents/
    
    The config JSON only stores the disruptionKey reference.
    When running demos, the C++ APIs load from these CSV files.
    
    Request body: The config object to save
    
    Returns:
    {
        "success": true,
        "config": {...}
    }
    """
    try:
        config = request.json
        
        # Generate ID if not present
        if not config.get('id'):
            config['id'] = f"demo-{int(time.time() * 1000)}"
        
        config['savedAt'] = datetime.now().isoformat()
        
        # Generate unique disruption key
        disruption_key = config.get('disruptionKey') or generate_disruption_key()
        config['disruptionKey'] = disruption_key
        
        # Extract disruption settings (keep mode, scope, severity settings)
        disruptions_config = config.get('disruptions', {})
        
        # Extract and save disruptionSets to CSV files
        disruption_sets = disruptions_config.pop('disruptionSets', {})
        
        if disruption_sets:
            console_logger.processing(f"Saving {len(disruption_sets)} disruption sets for demo {config['id']}")
            
            saved_sets = {}
            for set_key, set_data in disruption_sets.items():
                # set_data contains: { flow: [], incidents: [], demoId: ..., disruptionDir: ... }
                flow_rows = []
                incident_rows = []
                
                # Extract flow data
                if 'flow' in set_data:
                    for item in set_data['flow']:
                        flow_rows.append({
                            'id_hash': item.get('id_hash', f'demo_{set_key}'),
                            'source_lat': item.get('source_lat'),
                            'source_lon': item.get('source_lon'),
                            'target_lat': item.get('target_lat'),
                            'target_lon': item.get('target_lon'),
                            'source': item.get('source'),
                            'target': item.get('target'),
                            'flow_speed_kph': item.get('flow_speed_kph', 30),
                            'flow_free_flow_kph': item.get('flow_free_flow_kph', 60),
                            'flow_jam_factor': item.get('jam_factor', item.get('flow_jam_factor', 5)),
                            'flow_confidence': item.get('flow_confidence', 0.95),
                            'flow_traversability': item.get('flow_traversability', 'open'),
                            'highway_type': item.get('highway_type', 'primary'),
                            'road_name': item.get('road_name', 'Unknown')
                        })
                
                # Extract incident data
                if 'incidents' in set_data:
                    for item in set_data['incidents']:
                        incident_rows.append({
                            'source': item.get('source'),
                            'target': item.get('target'),
                            'source_lat': item.get('source_lat'),
                            'source_lon': item.get('source_lon'),
                            'target_lat': item.get('target_lat'),
                            'target_lon': item.get('target_lon'),
                            'incident_id': item.get('incident_id', f'demo_{set_key}'),
                            'incident_type': item.get('type', item.get('incident_type', 'construction')),
                            'incident_criticality': item.get('criticality', item.get('incident_criticality', 'major')),
                            'incident_description': item.get('incident_description', item.get('description', '')),
                            'incident_road_closed': item.get('incident_road_closed', False),
                            'incident_start_time': item.get('incident_start_time', ''),
                            'incident_end_time': item.get('incident_end_time', ''),
                            'highway_type': item.get('highway_type', 'primary'),
                            'road_name': item.get('road_name', 'Unknown')
                        })
                
                # Save to CSV
                result = save_disruption_set_to_csv(
                    disruption_key=disruption_key,
                    set_key=set_key,
                    disruptions={'flow': flow_rows, 'incidents': incident_rows}
                )
                
                saved_sets[set_key] = {
                    'disruption_dir': result['disruption_dir'],
                    'flow_count': result['flow_count'],
                    'incident_count': result['incident_count']
                }
            
            # Store summary in config (not the actual data)
            config['disruptions']['savedSets'] = saved_sets
            console_logger.success(f"Saved {len(saved_sets)} disruption sets to {disruption_key}/")
        
        # Remove any remaining large data from disruptions
        config['disruptions'].pop('customItems', None)
        config['disruptions'].pop('previewedDisruptions', None)
        
        # Save config file (without the large disruption data)
        config_file = DEMO_CONFIGS_DIR / f"{config['id']}.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        console_logger.success(f"Saved demo config: {config['id']} (disruptionKey: {disruption_key})")
        
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        console_logger.error(f"Error saving config: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/configs/<config_id>', methods=['GET'])
def get_demo_config(config_id):
    """
    Get a specific demo configuration by ID.
    
    Returns:
    {
        "success": true,
        "config": {...}
    }
    """
    try:
        config_file = DEMO_CONFIGS_DIR / f"{config_id}.json"
        
        if not config_file.exists():
            return jsonify({'success': False, 'error': 'Config not found'}), 404
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        console_logger.error(f"Error getting config {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/configs/<config_id>', methods=['PUT'])
def update_demo_config(config_id):
    """
    Update an existing demo configuration.
    
    Disruptions are stored separately in CSV files at:
    data/demos/configs/disruptions/{disruptionKey}/{setKey}/flow/ and incidents/
    
    Request body: The updated config object
    
    Returns:
    {
        "success": true,
        "config": {...}
    }
    """
    try:
        config = request.json
        config['id'] = config_id
        config['savedAt'] = datetime.now().isoformat()
        
        # Use existing disruption key or generate new one
        disruption_key = config.get('disruptionKey') or generate_disruption_key()
        config['disruptionKey'] = disruption_key
        
        # Extract disruption settings
        disruptions_config = config.get('disruptions', {})
        
        # Extract and save disruptionSets to CSV files
        disruption_sets = disruptions_config.pop('disruptionSets', {})
        
        if disruption_sets:
            console_logger.processing(f"Updating {len(disruption_sets)} disruption sets for demo {config_id}")
            
            saved_sets = {}
            for set_key, set_data in disruption_sets.items():
                flow_rows = []
                incident_rows = []
                
                # Extract flow data
                if 'flow' in set_data:
                    for item in set_data['flow']:
                        flow_rows.append({
                            'id_hash': item.get('id_hash', f'demo_{set_key}'),
                            'source_lat': item.get('source_lat'),
                            'source_lon': item.get('source_lon'),
                            'target_lat': item.get('target_lat'),
                            'target_lon': item.get('target_lon'),
                            'source': item.get('source'),
                            'target': item.get('target'),
                            'flow_speed_kph': item.get('flow_speed_kph', 30),
                            'flow_free_flow_kph': item.get('flow_free_flow_kph', 60),
                            'flow_jam_factor': item.get('jam_factor', item.get('flow_jam_factor', 5)),
                            'flow_confidence': item.get('flow_confidence', 0.95),
                            'flow_traversability': item.get('flow_traversability', 'open'),
                            'highway_type': item.get('highway_type', 'primary'),
                            'road_name': item.get('road_name', 'Unknown')
                        })
                
                # Extract incident data
                if 'incidents' in set_data:
                    for item in set_data['incidents']:
                        incident_rows.append({
                            'source': item.get('source'),
                            'target': item.get('target'),
                            'source_lat': item.get('source_lat'),
                            'source_lon': item.get('source_lon'),
                            'target_lat': item.get('target_lat'),
                            'target_lon': item.get('target_lon'),
                            'incident_id': item.get('incident_id', f'demo_{set_key}'),
                            'incident_type': item.get('type', item.get('incident_type', 'construction')),
                            'incident_criticality': item.get('criticality', item.get('incident_criticality', 'major')),
                            'incident_description': item.get('incident_description', item.get('description', '')),
                            'incident_road_closed': item.get('incident_road_closed', False),
                            'incident_start_time': item.get('incident_start_time', ''),
                            'incident_end_time': item.get('incident_end_time', ''),
                            'highway_type': item.get('highway_type', 'primary'),
                            'road_name': item.get('road_name', 'Unknown')
                        })
                
                # Save to CSV
                result = save_disruption_set_to_csv(
                    disruption_key=disruption_key,
                    set_key=set_key,
                    disruptions={'flow': flow_rows, 'incidents': incident_rows}
                )
                
                saved_sets[set_key] = {
                    'disruption_dir': result['disruption_dir'],
                    'flow_count': result['flow_count'],
                    'incident_count': result['incident_count']
                }
            
            config['disruptions']['savedSets'] = saved_sets
            console_logger.success(f"Updated {len(saved_sets)} disruption sets")
        
        # Remove large data from config
        config['disruptions'].pop('customItems', None)
        config['disruptions'].pop('previewedDisruptions', None)
        
        config_file = DEMO_CONFIGS_DIR / f"{config_id}.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        console_logger.success(f"Updated demo config: {config_id}")
        
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        console_logger.error(f"Error updating config {config_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/configs/<config_id>', methods=['DELETE'])
def delete_demo_config(config_id):
    """
    Delete a demo configuration and its associated disruption folder.
    
    Returns:
    {
        "success": true,
        "config_id": "..."
    }
    """
    try:
        import shutil
        
        config_file = DEMO_CONFIGS_DIR / f"{config_id}.json"
        
        # Load config to get disruption key
        disruption_key = None
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    disruption_key = config.get('disruptionKey')
            except:
                pass
            
            # Delete config file
            config_file.unlink()
            console_logger.info(f"Deleted config file: {config_id}")
        
        # Delete associated disruption folder (new structure)
        if disruption_key:
            disruption_dir = DEMO_DISRUPTIONS_DIR / disruption_key
            if disruption_dir.exists():
                shutil.rmtree(disruption_dir)
                console_logger.info(f"Deleted disruption folder: {disruption_key}")
        
        # Delete associated results folder
        results_dir = DEMO_RESULTS_DIR / config_id
        if results_dir.exists():
            shutil.rmtree(results_dir)
            console_logger.info(f"Deleted results folder: {config_id}")
        
        return jsonify({
            'success': True,
            'config_id': config_id
        })
    except Exception as e:
        console_logger.error(f"Error deleting config {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/disruption-path/<disruption_key>/<set_key>', methods=['GET'])
def get_demo_disruption_path(disruption_key, set_key):
    """
    Get the disruption folder path for a specific demo configuration set.
    This path is used by C++ APIs to load disruption data.
    
    Args:
        disruption_key: The unique disruption folder key (UUID)
        set_key: The set key (e.g., 'set_all', 'set_trial_0', etc.)
    
    Returns:
    {
        "success": true,
        "disruption_dir": "/absolute/path/to/disruptions",
        "flow_dir": "/absolute/path/to/flow",
        "incidents_dir": "/absolute/path/to/incidents"
    }
    """
    try:
        base_path = DEMO_DISRUPTIONS_DIR / disruption_key / set_key
        
        if not base_path.exists():
            return jsonify({
                'success': False, 
                'error': f'Disruption folder not found: {disruption_key}/{set_key}'
            }), 404
        
        return jsonify({
            'success': True,
            'disruption_dir': str(base_path.resolve()),
            'flow_dir': str((base_path / 'flow').resolve()),
            'incidents_dir': str((base_path / 'incidents').resolve())
        })
    except Exception as e:
        console_logger.error(f"Error getting disruption path: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/disruption-data/<disruption_key>/<set_key>', methods=['GET'])
def get_demo_disruption_data(disruption_key, set_key):
    """
    Load disruption data from saved CSV files for map visualization.
    Returns the data in the format expected by showGeneratedDisruptions.
    
    Args:
        disruption_key: The unique disruption folder key (UUID)
        set_key: The set key (e.g., 'set_all', 'set_trial_0', etc.)
    
    Returns:
    {
        "success": true,
        "incidents": [...],
        "flowSegments": [...],
        "disruption_dir": "..."
    }
    """
    try:
        import csv
        
        base_path = DEMO_DISRUPTIONS_DIR / disruption_key / set_key
        
        if not base_path.exists():
            return jsonify({
                'success': False, 
                'error': f'Disruption folder not found: {disruption_key}/{set_key}'
            }), 404
        
        incidents = []
        flow_segments = []
        
        # Load incidents from CSV
        incidents_dir = base_path / 'incidents'
        if incidents_dir.exists():
            for csv_file in incidents_dir.glob('*.csv'):
                try:
                    with open(csv_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Parse coordinates (CSV uses source_lon, target_lon)
                            source_lat = float(row.get('source_lat', 0))
                            source_lng = float(row.get('source_lon', row.get('source_lng', 0)))
                            target_lat = float(row.get('target_lat', source_lat))
                            target_lng = float(row.get('target_lon', row.get('target_lng', source_lng)))
                            
                            # Determine severity
                            severity_value = float(row.get('incident_severity', row.get('severity_value', 0.5)))
                            if severity_value > 0.7:
                                severity = 'Heavy'
                            elif severity_value > 0.4:
                                severity = 'Medium'
                            else:
                                severity = 'Light'
                            
                            incident = {
                                'id': row.get('incident_id', f"inc-{len(incidents)}"),
                                'type': row.get('incident_type', 'Other'),
                                'incident_type': row.get('incident_type', 'Other'),
                                'source_lat': source_lat,
                                'source_lng': source_lng,
                                'target_lat': target_lat,
                                'target_lng': target_lng,
                                'severity': severity,
                                'severity_value': severity_value,
                                'road_name': row.get('road_name', 'Unknown Road'),
                                'description': row.get('incident_description', row.get('description', '')),
                                'criticality': row.get('incident_criticality', 'minor'),
                                'incident_criticality': row.get('incident_criticality', 'minor'),
                                'incident_road_closed': row.get('incident_road_closed', 'False').lower() == 'true',
                                'incident_description': row.get('incident_description', row.get('description', ''))
                            }
                            incidents.append(incident)
                except Exception as e:
                    console_logger.warning(f"Error reading incident file {csv_file}: {e}")
        
        # Load flow segments from CSV
        flow_dir = base_path / 'flow'
        if flow_dir.exists():
            for csv_file in flow_dir.glob('*.csv'):
                try:
                    with open(csv_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            # Parse coordinates (CSV uses source_lon, target_lon)
                            source_lat = float(row.get('source_lat', 0))
                            source_lng = float(row.get('source_lon', row.get('source_lng', 0)))
                            target_lat = float(row.get('target_lat', source_lat))
                            target_lng = float(row.get('target_lon', row.get('target_lng', source_lng)))
                            
                            # Calculate severity from jam factor
                            jam_factor = float(row.get('flow_jam_factor', row.get('jam_factor', 0)))
                            severity_value = min(jam_factor / 10.0, 1.0)  # Normalize to 0-1
                            if severity_value > 0.7:
                                severity = 'Heavy'
                            elif severity_value > 0.4:
                                severity = 'Medium'
                            else:
                                severity = 'Light'
                            
                            flow_segment = {
                                'id': row.get('id_hash', f"flow-{len(flow_segments)}"),
                                'type': 'TrafficFlow',
                                'incident_type': 'Congestion',
                                'source_lat': source_lat,
                                'source_lng': source_lng,
                                'target_lat': target_lat,
                                'target_lng': target_lng,
                                'severity': severity,
                                'severity_value': severity_value,
                                'jam_factor': jam_factor,
                                'speed_kph': float(row.get('flow_speed_kph', row.get('speed_kph', 0))),
                                'free_flow_kph': float(row.get('flow_free_flow_kph', row.get('free_flow_kph', 0))),
                                'road_name': row.get('road_name', 'Unknown Road')
                            }
                            flow_segments.append(flow_segment)
                except Exception as e:
                    console_logger.warning(f"Error reading flow file {csv_file}: {e}")
        
        console_logger.info(f"Loaded {len(incidents)} incidents and {len(flow_segments)} flow segments for {disruption_key}/{set_key}")
        
        return jsonify({
            'success': True,
            'incidents': incidents,
            'flowSegments': flow_segments,
            'disruption_dir': str(base_path.resolve())
        })
    except Exception as e:
        console_logger.error(f"Error loading disruption data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/results/<config_id>', methods=['POST'])
def save_demo_results(config_id):
    """
    Save demo experiment results.
    
    Request body: The results object to save
    
    Returns:
    {
        "success": true,
        "results_file": "..."
    }
    """
    try:
        results = request.json
        
        results_dir = DEMO_RESULTS_DIR / config_id
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        results_file = results_dir / f"results_{timestamp}.json"
        
        results['savedAt'] = datetime.now().isoformat()
        results['configId'] = config_id
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        console_logger.success(f"Saved demo results: {results_file}")
        
        return jsonify({
            'success': True,
            'results_file': str(results_file)
        })
    except Exception as e:
        console_logger.error(f"Error saving results for {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/demo/results/<config_id>', methods=['GET'])
def get_demo_results(config_id):
    """
    Get all results for a demo configuration.
    
    Returns:
    {
        "success": true,
        "results": [...]
    }
    """
    try:
        results_dir = DEMO_RESULTS_DIR / config_id
        
        if not results_dir.exists():
            return jsonify({
                'success': True,
                'results': [],
                'count': 0
            })
        
        results = []
        for results_file in sorted(results_dir.glob('results_*.json'), reverse=True):
            try:
                with open(results_file, 'r') as f:
                    result = json.load(f)
                    results.append(result)
            except Exception as e:
                console_logger.warning(f"Error loading result {results_file}: {e}")
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        console_logger.error(f"Error getting results for {config_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/search_location', methods=['POST'])
def search_location():
    """
    Search for locations within Quezon City using Photon API (OSM alternative to Nominatim)
    Returns list of matching places with coordinates
    """
    import requests
    
    data = request.json
    query = data.get('query', '').strip()
    console_logger.info(f"[SEARCH] Query received: '{query}'")
    
    if not query:
        console_logger.error("[SEARCH] Query is empty")
        return jsonify({
            'success': False,
            'error': 'Search query is required'
        })
    
    try:
        # Quezon City coordinates (approximate center)
        qc_lat = 14.6760
        qc_lng = 121.0437
        
        # Try Photon API first (faster, more reliable than Nominatim)
        photon_url = "https://photon.komoot.io/api"
        params = {
            'q': query,
            'lat': qc_lat,
            'lon': qc_lng,
            'limit': 10,
            'bbox': '121.000,14.500,121.150,14.800'  # Quezon City bounds
        }
        
        headers = {
            'User-Agent': 'REACT-Navigation-App/1.0'
        }
        
        console_logger.info(f"[SEARCH] Trying Photon API: {photon_url}")
        response = requests.get(photon_url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        data_response = response.json()
        results = data_response.get('features', [])
        console_logger.data(f"[SEARCH] Photon returned {len(results)} results")
        
        # Process Photon results
        filtered_results = []
        for result in results:
            try:
                properties = result.get('properties', {})
                geometry = result.get('geometry', {})
                coords = geometry.get('coordinates', [])
                
                if len(coords) < 2:
                    continue
                
                lng = float(coords[0])
                lat = float(coords[1])
                
                # Build location name
                name_parts = []
                if properties.get('name'):
                    name_parts.append(properties['name'])
                if properties.get('city'):
                    name_parts.append(properties['city'])
                if properties.get('state'):
                    name_parts.append(properties['state'])
                
                name = ', '.join(name_parts) if name_parts else 'Unknown Location'
                loc_type = properties.get('osm_type', 'place')
                
                # Double-check if within Quezon City bounds (with 5km tolerance)
                if 14.45 <= lat <= 14.85 and 120.95 <= lng <= 121.20:
                    filtered_results.append({
                        'name': name,
                        'lat': lat,
                        'lng': lng,
                        'type': loc_type,
                        'address': properties
                    })
                    console_logger.data(f"  ✅ Added: {name} ({lat:.4f}, {lng:.4f})")
                else:
                    console_logger.data(f"  ⚠️  Outside bounds: {name} ({lat:.4f}, {lng:.4f})")
            except (ValueError, TypeError, KeyError) as e:
                console_logger.warning(f"  ⚠️  Parse error: {e}")
                continue
        
        console_logger.success(f"[SEARCH] Returning {len(filtered_results)} results from Photon")
        return jsonify({
            'success': True,
            'results': filtered_results,
            'count': len(filtered_results)
        })
        
    except requests.exceptions.Timeout:
        console_logger.warning("[SEARCH] Photon timeout, trying fallback...")
        # Fallback: try Nominatim if Photon fails
        try:
            nominatim_url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': f"{query}, Quezon City",
                'format': 'json',
                'limit': 10,
                'viewbox': '121.000,14.500,121.150,14.800',
                'bounded': 1,
                'addressdetails': 1
            }
            headers = {'User-Agent': 'REACT-Navigation-App/1.0'}
            
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=5)
            response.raise_for_status()
            results = response.json()
            
            filtered_results = []
            for result in results:
                try:
                    lat = float(result.get('lat', 0))
                    lng = float(result.get('lon', 0))
                    name = result.get('display_name', 'Unknown')
                    
                    if 14.45 <= lat <= 14.85 and 120.95 <= lng <= 121.20:
                        filtered_results.append({
                            'name': name,
                            'lat': lat,
                            'lng': lng,
                            'type': result.get('type', 'place'),
                            'address': result.get('address', {})
                        })
                except (ValueError, TypeError):
                    continue
            
            return jsonify({
                'success': True,
                'results': filtered_results,
                'count': len(filtered_results)
            })
        except Exception as e:
            console_logger.error(f"[SEARCH] Nominatim fallback also failed: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Location search unavailable: {str(e)}'
            })
    
    except requests.exceptions.RequestException as e:
        console_logger.error(f"[SEARCH] API request failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Search service error: {str(e)}'
        })
    except Exception as e:
        console_logger.error(f"[SEARCH] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}'
        })

@app.route('/get_all_nodes')
def get_all_nodes():
    """Return all nodes for display on map"""
    try:
        # Load all nodes using config
        nodes_df = pd.read_csv(Config.NODES_CSV)
        
        # Convert to list of dictionaries for JSON
        nodes_list = []
        for _, row in nodes_df.iterrows():
            nodes_list.append({
                'node_id': int(row['node_id']),
                'lat': float(row['latitude']),
                'lng': float(row['longitude'])
            })
        
        return jsonify({
            'success': True,
            'nodes': nodes_list,
            'count': len(nodes_list)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/get_all_edges')
def get_all_edges():
    """Return all edges for display on map"""
    try:
        # Load edges and nodes using config
        edges_df = pd.read_csv(Config.EDGES_CSV)
        nodes_df = pd.read_csv(Config.NODES_CSV)
        
        # Create node lookup for coordinates
        node_lookup = {}
        for _, row in nodes_df.iterrows():
            node_lookup[int(row['node_id'])] = {
                'lat': float(row['latitude']),
                'lng': float(row['longitude'])
            }
        
        # Process edges
        edges_list = []
        skipped_edges = 0
        
        for _, edge in edges_df.iterrows():
            source_id = int(edge['source'])
            target_id = int(edge['target'])
            
            # Check if both nodes exist in our nodes dataset
            if source_id in node_lookup and target_id in node_lookup:
                edges_list.append({
                    'source_id': source_id,
                    'target_id': target_id,
                    'source_lat': node_lookup[source_id]['lat'],
                    'source_lng': node_lookup[source_id]['lng'],
                    'target_lat': node_lookup[target_id]['lat'],
                    'target_lng': node_lookup[target_id]['lng'],
                    'length': float(edge['length']),
                    'name': str(edge['name']) if pd.notna(edge['name']) else 'Unnamed Road',
                    'highway': str(edge['highway']) if pd.notna(edge['highway']) else 'unclassified'
                })
            else:
                skipped_edges += 1
        
        return jsonify({
            'success': True,
            'edges': edges_list,
            'edges_count': len(edges_list),
            'skipped_edges': skipped_edges,
            'total_edges_in_file': len(edges_df)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/get_scenario_data')
def get_scenario_data():
    """Return scenario data with coordinates and traffic conditions"""
    try:
        # Load scenario data with coordinates using config
        scenario_df = pd.read_csv(Config.DISRUPTIONS_CSV)
        
        # Convert to format suitable for visualization
        edges_with_traffic = []
        
        for _, row in scenario_df.iterrows():
            # Support both old column names (speed_kph, freeFlow_kph) and new (flow_speed_kph, flow_free_flow_kph)
            current_speed = float(row.get('flow_speed_kph', row.get('speed_kph', 0.0)))
            free_flow_speed = float(row.get('flow_free_flow_kph', row.get('freeFlow_kph', 50.0)))
            jam_factor = float(row.get('flow_jam_factor', row.get('jamFactor', 0.0)))
            is_closed = bool(row.get('incident_road_closed', row.get('isClosed', False)))
            
            edges_with_traffic.append({
                'source_id': int(row['source']),
                'target_id': int(row['target']),
                'source_lat': float(row['source_lat']),
                'source_lng': float(row['source_lon']),
                'target_lat': float(row['target_lat']),
                'target_lng': float(row['target_lon']),
                'road_name': str(row['road_name']),
                'speed_kph': current_speed,
                'freeFlow_kph': free_flow_speed,
                'jamFactor': jam_factor,
                'isClosed': is_closed,
                'segmentLength': float(row.get('segmentLength', 100.0))
            })
        
        return jsonify({
            'success': True,
            'edges': edges_with_traffic,
            'count': len(edges_with_traffic),
            'description': 'Quezon City traffic scenario with real coordinates and traffic conditions'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/find_nearest_node', methods=['POST'])
def find_nearest_node():
    """
    Find nearest node to clicked coordinates
    
    Enhanced to support one-way street awareness:
    - Pass is_start_point=true for start location selection
    - Pass is_start_point=false for destination selection
    - Omit is_start_point for legacy behavior (no one-way awareness)
    """
    data = request.json
    
    try:
        lat = data['lat']
        lng = data['lng']
        
        # Get optional is_start_point parameter
        is_start_point = data.get('is_start_point', None)
        if is_start_point is not None:
            is_start_point = bool(is_start_point)
        
        # Find nearest node (with or without one-way awareness)
        result = mapper.find_nearest_node(
            lat, lng, 
            max_distance_m=1000,  # Increased range
            is_start_point=is_start_point
        )
        
        # Handle different return formats
        if is_start_point is not None and len(result) == 3:
            node_id, distance, metadata = result
        else:
            node_id, distance = result
            metadata = None
        
        if not node_id:
            error_msg = f'No nodes within 1km. Nearest is {distance:.1f}m away.'
            if metadata:
                error_msg = metadata.get('selection_reason', error_msg)
            
            return jsonify({
                'success': False,
                'error': error_msg
            })
        
        # Get node details using config
        nodes_df = pd.read_csv(Config.NODES_CSV)
        node_data = nodes_df[nodes_df['node_id'] == node_id].iloc[0]
        
        response = {
            'success': True,
            'node_id': int(node_id),
            'lat': float(node_data['latitude']),
            'lng': float(node_data['longitude']),
            'distance_m': round(distance, 1),
            'clicked_lat': lat,
            'clicked_lng': lng
        }
        
        # Add metadata if available (one-way aware selection)
        if metadata:
            response['metadata'] = {
                'accessible': metadata['accessible'],
                'outgoing_edges': metadata['outgoing_count'],
                'incoming_edges': metadata['incoming_count'],
                'selection_reason': metadata['selection_reason'],
                'role': metadata['role']
            }
            
            # Add warning if not accessible
            if not metadata['accessible']:
                response['warning'] = metadata['selection_reason']
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/find_nearest_road_segment', methods=['POST'])
def find_nearest_road_segment():
    """
    Find nearest road segment and project point onto it
    This provides better snap-to-road functionality than find_nearest_node
    """
    data = request.json
    
    try:
        lat = float(data['lat'])
        lng = float(data['lng'])
        max_distance = float(data.get('max_distance', 500))
        
        # Use mapper's snap function
        result = mapper.snap_to_nearest_road(lat, lng, max_distance=max_distance)
        
        if result is None:
            return jsonify({
                'success': False,
                'error': f'No road within {max_distance}m of this location',
                'lat': lat,
                'lng': lng
            })
        
        # Return enhanced result
        return jsonify({
            'success': True,
            'edge': {
                'source': result['edge'][0],
                'target': result['edge'][1]
            },
            'projection_point': result['projection_point'],
            'original_point': result['original_point'],
            'distance_m': round(result['distance_m'], 1),
            'road_name': result['road_name'],
            'segment_length_m': round(result['segment_length_m'], 1),
            'validation': result['validation']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Error finding nearest road segment: {str(e)}"
        })


@app.route('/find_nearest_osm_road', methods=['POST'])
def find_nearest_osm_road():
    """
    Find nearest OSM road using actual road geometries (road-aware snapping).
    
    This endpoint uses the OSM GraphML data to snap points to real road
    geometries rather than just intersection nodes, providing more accurate
    and road-aware location selection.
    
    The system will automatically expand the search radius up to 1000m to
    always find the nearest road (never falls back to node-based selection).
    """
    data = request.json
    
    try:
        lat = float(data['lat'])
        lng = float(data['lng'])
        max_distance = float(data.get('max_distance', 25.0))  # Default 25m initial search
        consider_hierarchy = data.get('consider_hierarchy', True)
        
        # Use mapper's OSM snapping function
        # Note: fallback_to_node parameter is deprecated and ignored
        result = mapper.snap_to_osm_road(
            lat, lng, 
            max_distance_m=max_distance,
            consider_hierarchy=consider_hierarchy
        )
        
        if result is None:
            return jsonify({
                'success': False,
                'error': f'Critical error: Could not find any road even with expanded search',
                'original_point': {'lat': lat, 'lng': lng}
            })
        
        # Prepare metadata without geometry (not JSON serializable)
        metadata = result.get('metadata', {})
        if 'geometry' in metadata:
            del metadata['geometry']
        
        # Return comprehensive result (excluding non-serializable fields)
        return jsonify({
            'success': True,
            'method': result['method'],
            'original_point': result['original_point'],
            'snapped_point': result['snapped_point'],
            'distance_m': round(result['distance_m'], 1),
            'road_name': result['road_name'],
            'highway_type': result['highway_type'],
            'oneway': result['oneway'],
            'osm_nodes': result['osm_nodes'],
            'routing_nodes': result['routing_nodes'],
            'edge_length_m': round(result['edge_length_m'], 1),
            'snap_position': round(result['snap_position'], 3),
            'validation': result['validation'],
            'metadata': metadata
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error finding nearest OSM road: {str(e)}",
            'original_point': {'lat': lat, 'lng': lng}
        })


@app.route('/get_osm_graph_edges', methods=['GET'])
def get_osm_graph_edges():
    """Get all OSM road edges for map visualization"""
    try:
        # Check if OSM road snapper is available
        if not hasattr(mapper, 'osm_snapper') or mapper.osm_snapper is None:
            return jsonify({
                'success': False,
                'error': 'OSM road snapper not initialized'
            })
        
        snapper = mapper.osm_snapper
        edges_data = []
        
        # Get limit from query params (default 500 for performance)
        limit = request.args.get('limit', type=int, default=500)
        max_limit = float('inf')  #2000  # Safety cap
        limit = min(limit, max_limit)
        
        # Extract edge geometries with metadata
        for metadata in snapper.edge_metadata[:limit]:
            try:
                geom = metadata['geometry']
                coords = [(lat, lng) for lng, lat in geom.coords]  # Convert to lat/lng
                
                edges_data.append({
                    'coordinates': coords,
                    'u': int(metadata['u']),
                    'v': int(metadata['v']),
                    'name': metadata.get('name', 'Unnamed Road'),
                    'highway': metadata.get('highway', 'unknown'),
                    'oneway': metadata.get('oneway', 0),
                    'length': round(metadata.get('length', 0), 2)
                })
            except Exception as e:
                # Skip edges with invalid geometry
                continue
        
        return jsonify({
            'success': True,
            'edges': edges_data,
            'count': len(edges_data),
            'total_edges': len(snapper.edge_metadata),
            'message': f'Showing {len(edges_data)} of {len(snapper.edge_metadata)} total edges (limit: {limit})'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error getting OSM graph edges: {str(e)}"
        })


@app.route('/compute_dhc2l_route', methods=['POST'])
def compute_dhc2l_route():
    """Compute optimal route using HC2L (Hierarchical Cut Labelling) algorithm"""
    data = request.json
    
    try:
        if gps_router is None:
            return jsonify({
                'success': False,
                'error': 'HC2L Router not initialized properly'
            })
        
        # Extract pin coordinates (original user click points)
        start_pin_lat = float(data['start_lat'])
        start_pin_lng = float(data['start_lng'])
        dest_pin_lat = float(data['dest_lat'])
        dest_pin_lng = float(data['dest_lng'])
        tau_threshold = float(data['tau_threshold']) if 'tau_threshold' in data else 0.5
        
        # Check if OSM edge-based routing should be used (snap point data)
        start_osm_edge = data.get('start_osm_edge')
        dest_osm_edge = data.get('dest_osm_edge')
        
        # Default to pin coordinates if no snap info
        start_snap_lat = start_pin_lat
        start_snap_lng = start_pin_lng
        dest_snap_lat = dest_pin_lat
        dest_snap_lng = dest_pin_lng
        
        # Default edge information (will be overridden if snap data available)
        start_edge_source = 0
        start_edge_target = 0
        start_edge_oneway = 0
        dest_edge_source = 0
        dest_edge_target = 0
        dest_edge_oneway = 0
        
        # Extract snap point and edge information from OSM snap result
        if start_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in start_osm_edge:
                start_snap_lat = float(start_osm_edge['snapped_point']['lat'])
                start_snap_lng = float(start_osm_edge['snapped_point']['lng'])
            
            # Get edge information (CRITICAL: tells us which road the snap is on)
            if 'osm_nodes' in start_osm_edge and len(start_osm_edge['osm_nodes']) >= 2:
                start_edge_source = int(start_osm_edge['osm_nodes'][0])
                start_edge_target = int(start_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = start_osm_edge.get('oneway', '0')
            try:
                start_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                start_edge_oneway = 0
            
            console_logger.success(f"Start snap: {start_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {start_edge_source}→{start_edge_target}, oneway={start_edge_oneway})")
        
        if dest_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in dest_osm_edge:
                dest_snap_lat = float(dest_osm_edge['snapped_point']['lat'])
                dest_snap_lng = float(dest_osm_edge['snapped_point']['lng'])
            
            # Get edge information
            if 'osm_nodes' in dest_osm_edge and len(dest_osm_edge['osm_nodes']) >= 2:
                dest_edge_source = int(dest_osm_edge['osm_nodes'][0])
                dest_edge_target = int(dest_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = dest_osm_edge.get('oneway', '0')
            try:
                dest_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                dest_edge_oneway = 0
            
            console_logger.success(f"Dest snap: {dest_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {dest_edge_source}→{dest_edge_target}, oneway={dest_edge_oneway})")
        
        # LazyHC2L: Extract optional disruption parameters
        # disruption_files: path to disruption directory (string, not tuple)
        # tau_threshold: threshold for lazy vs immediate update (default 0.5)
        disruption_files = data.get('disruption_files', '')  # Default to empty string, not tuple
        dataset_mode = data.get('dataset_mode', None)  # Get dataset mode from request
        generate_alternatives = data.get('generate_alternatives', True)  # NEW: Control alternative route generation
        
        # If no disruption files specified, use dynamic disruptions based on dataset mode
        if not disruption_files or isinstance(disruption_files, tuple):  # Handle legacy tuple format
            disruption_files = get_dynamic_disruption_file('hc2l', dataset_mode)
        
        # For backward compatibility, accept single disruption_file parameter
        disruption_file = data.get('disruption_file', '')
        if disruption_file and not disruption_files:
            disruption_files = disruption_file
                
        console_logger.processing(f"Computing HC2L route with snap points:")
        console_logger.data(f"  Start: Pin({start_pin_lat}, {start_pin_lng}) → Snap({start_snap_lat}, {start_snap_lng})")
        console_logger.data(f"  Dest:  Pin({dest_pin_lat}, {dest_pin_lng}) → Snap({dest_snap_lat}, {dest_snap_lng})")
        console_logger.data(f"  Dataset mode: {dataset_mode if dataset_mode else 'auto'}")
        console_logger.data(f"  Disruption directory: {disruption_files if disruption_files else '(none)'}")
        console_logger.data(f"  Tau threshold: {tau_threshold}")
        console_logger.data(f"  Generate alternatives: {generate_alternatives}")
        
        # Compute route using HC2L with LazyHC2L parameters
        # Pass disruption directory to C++ - it will find flow/incident CSV files automatically
        start_time = time.time()
        route_result = gps_router.compute_route(
            start_pin_lat, start_pin_lng,
            dest_pin_lat, dest_pin_lng,
            start_snap_lat, start_snap_lng,
            dest_snap_lat, dest_snap_lng,
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway,
            disruption_files, tau_threshold, generate_alternatives  # Pass directory path
        )
        computation_time = time.time() - start_time
        
        if not route_result['success']:
            return jsonify({
                'success': False,
                'error': route_result['error'],
                'debug_info': route_result.get('raw_output', '')
            })
        
        # Get polylines for Google Maps
        polylines = gps_router.get_route_polylines_for_gmaps(route_result)
        
        # Get route summary
        summary = gps_router.get_route_summary(route_result)
        summary['total_computation_time_sec'] = round(computation_time, 3)
        
        # Get the full metrics from C++ output
        cpp_metrics = route_result.get('metrics', {})
        
        # Merge summary into cpp_metrics (keeping all C++ fields, adding Python-calculated fields)
        full_metrics = {**cpp_metrics, **summary}
        
        # Debug: Check HC2L geometry
        hc2l_geometry = route_result.get('route', {}).get('geometry', [])
        console_logger.data(f"HC2L geometry in Flask: {len(hc2l_geometry)} segments")
        if hc2l_geometry:
            console_logger.data(f"HC2L First segment keys: {list(hc2l_geometry[0].keys()) if hc2l_geometry else 'No segments'}")
        
        # Extract disruption_analysis from C++ output
        disruption_analysis = route_result.get('disruption_analysis', {})
        if disruption_analysis:
            console_logger.data(f"Disruption analysis detected: {disruption_analysis.get('route_disruptions', {}).get('total_count', 0)} disruptions")
        
        # Enhance alternative routes with geometry (only if requested)
        if generate_alternatives:
            enhanced_alt_routes = enhance_alternative_routes_with_geometry(route_result.get('alternative_routes', []))
        else:
            enhanced_alt_routes = []
            console_logger.data(f"Alternative routes generation skipped (generate_alternatives=False)")
        
        return jsonify({
            'success': True,
            'route': {
                'polylines': polylines,
                'start_point': {'lat': start_snap_lat, 'lng': start_snap_lng},
                'end_point': {'lat': dest_snap_lat, 'lng': dest_snap_lng},
                'pin_start': {'lat': start_pin_lat, 'lng': start_pin_lng},
                'pin_end': {'lat': dest_pin_lat, 'lng': dest_pin_lng},
                'coordinates': route_result.get('route', {}).get('coordinates', []),
                'path_nodes': route_result.get('route', {}).get('path_nodes', []),
                'road_segments': route_result.get('route', {}).get('road_segments', []),
                'route_summary': route_result.get('route', {}).get('route_summary', ''),
                'turn_by_turn_directions': route_result.get('route', {}).get('turn_by_turn_directions', []),
                'display_format': route_result.get('route', {}).get('display_format', {}),
                'geometry': route_result.get('route', {}).get('geometry', [])  # Edge details with distance, highway type, speeds, traffic status
            },
            'metrics': full_metrics,  # Use full_metrics with all C++ fields
            'disruption_analysis': disruption_analysis,  # Pass disruption analysis from C++ to frontend
            'disruptions_summary': route_result.get('disruptions_summary', {}),  # Also pass disruptions_summary for additional details
            'alternative_routes': enhanced_alt_routes,  # Pass enhanced alternative routes (or empty if not requested)
            'lazy_hc2l': route_result.get('lazy_hc2l', {}),  # Pass LazyHC2L update strategy info
            'disruption_config': route_result.get('disruption_config', {}),  # Pass disruption configuration
            'algorithm': summary.get('algorithm', 'D-HC2L Dynamic'),  # Use algorithm from summary
            'algorithm_base': summary.get('algorithm_base', 'D-HC2L'),
            'routing_mode': summary.get('routing_mode', 'BASE'),
            'update_strategy': summary.get('update_strategy', 'none'),
            'mode_explanation': summary.get('mode_explanation', ''),
            'labels_status': summary.get('labels_status', 'original'),
            'gps_mapping': route_result.get('gps_mapping', {}),
            'snap_edges': route_result.get('snap_edges', {}),
            'raw_output': route_result.get('raw_output', '')
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Route computation error: {str(e)}"
        })


@app.route('/compare_routes', methods=['POST'])
def compare_routes():
    """Compare HC2L base route with disrupted route"""
    data = request.json
    
    try:
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        threshold = float(data.get('threshold', 0.5))
        
        # Use the HC2L router's built-in comparison function
        comparison_result = gps_router.compare_routes(start_lat, start_lng, dest_lat, dest_lng, threshold)

        if not comparison_result['success']:
            return jsonify({
                'success': False,
                'error': comparison_result['error']
            })
        
        # Add straight line for additional comparison
        straight_line = [{
            'path': [
                {'lat': start_lat, 'lng': start_lng},
                {'lat': dest_lat, 'lng': dest_lng}
            ],
            'strokeColor': '#00FF00',  # Green
            'strokeOpacity': 0.5,
            'strokeWeight': 2,
            'geodesic': True
        }]
        
        comparison_result['routes']['straight_line'] = {
            'polylines': straight_line,
            'name': 'Straight Line',
            'color': '#00FF00'
        }
        
        comparison_result['start_point'] = {'lat': start_lat, 'lng': start_lng}
        comparison_result['end_point'] = {'lat': dest_lat, 'lng': dest_lng}
        
        return jsonify(comparison_result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Route comparison error: {str(e)}"
        })


@app.route('/get_active_disruptions')
def get_active_disruptions():
    """
    Get all active disruptions from HERE API data using hash-based matching
    Maps HERE traffic data to actual road network edges using pre-matched edges
    """
    try:
        def edge_value(edge, attr, aliases=None, default=None):
            keys = [attr]
            if aliases:
                keys.extend(aliases)

            if isinstance(edge, dict):
                for key in keys:
                    if key in edge:
                        value = edge.get(key)
                        if value is not None:
                            return value
                return default

            for key in keys:
                if hasattr(edge, key):
                    value = getattr(edge, key)
                    if value is not None:
                        return value
            return default

        def escape_string(value):
            """Ensure a value is a properly escaped string for JSON."""
            if value is None:
                return ''
            s = str(value)
            # Remove control characters that might break JSON parsing
            s = ''.join(char if ord(char) >= 32 or char in '\t\n\r' else '' for char in s)
            return s

        # Use the separated flow and incident services
        from config import Config
        
        disruptions_by_type = {}
        total_disruptions = 0
        matched_edges_count = 0
        
        # Check if recent disruption data exists (similar to /load_disruptions logic)
        import time
        current_time = time.time()
        recent_threshold = 24 * 60 * 60  # 24 hours in seconds

        flow_files = list(Config.FLOW_DIR.glob("flow_*.csv"))
        incident_files = list(Config.INCIDENTS_DIR.glob("incident_*.csv"))

        recent_flow_files = [f for f in flow_files if (current_time - f.stat().st_mtime) < recent_threshold]
        recent_incident_files = [f for f in incident_files if (current_time - f.stat().st_mtime) < recent_threshold]

        use_cached_data = bool(recent_flow_files or recent_incident_files)
        
        if use_cached_data:
            console_logger.info("Using cached disruption data for active disruptions")
            console_logger.data(f"Recent flow files: {[f.name for f in recent_flow_files]}")
            console_logger.data(f"Recent incident files: {[f.name for f in recent_incident_files]}")
        else:
            console_logger.info("No recent disruption data found - fetching fresh data")
        
        # ============================================================
        # FETCH INCIDENTS (primary data source for incident types)
        # ============================================================
        if incident_service:
            if use_cached_data and recent_incident_files:
                # Use cached incident data
                latest_incident_file = max(recent_incident_files, key=lambda f: f.stat().st_mtime)
                try:
                    incidents_df = pd.read_csv(latest_incident_file)
                    incidents = incidents_df.to_dict('records')
                    console_logger.data(f"Loaded {len(incidents)} cached incidents from {latest_incident_file.name}")
                except Exception as e:
                    console_logger.warning(f"Error loading cached incidents: {e} - falling back to API")
                    incidents = incident_service.fetch_incidents_data()
            else:
                # Fetch fresh incident data
                incidents = incident_service.fetch_incidents_data()
            
            console_logger.info(f"Processing {len(incidents)} HERE incidents...")
            
            for incident in incidents:
                try:
                    # Handle both API format (nested) and CSV format (flat)
                    # Check if this is from CSV or from HERE API
                    is_from_csv = 'incident_id' in incident and 'source' in incident
                    
                    if is_from_csv:
                        # CSV format - flat structure
                        incident_type = incident.get('incident_type', 'other').lower()
                        criticality = incident.get('incident_criticality', 'low').lower()
                        road_closed = str(incident.get('incident_road_closed', 'False')).lower() in ('true', '1', 'yes')
                        road_name = incident.get('road_name', 'Unknown Road')
                        description = incident.get('incident_description', '')
                        
                        # For CSV data, create simple edge list instead of re-matching
                        # CSV already has source and target nodes
                        matched_edges = [{
                            'source': int(incident.get('source', 0)),
                            'target': int(incident.get('target', 0)),
                            'source_lat': float(incident.get('source_lat', 0)),
                            'source_lon': float(incident.get('source_lon', 0)),
                            'target_lat': float(incident.get('target_lat', 0)),
                            'target_lon': float(incident.get('target_lon', 0))
                        }]
                    else:
                        # HERE API format - nested structure
                        incident_details = incident.get('incidentDetails', {})
                        incident_type = incident_details.get('type', 'other').lower()
                        criticality = incident_details.get('criticality', 'low').lower()
                        road_closed = incident_details.get('roadClosed', False)
                        road_name = incident_details.get('description', {}).get('value', 'Unknown Road')
                        description = incident_details.get('description', {}).get('value', '')
                        
                        # Match incident to edges using incident matcher
                        matched_edges = incident_service.matcher.match_incident(incident)
                    
                    if not matched_edges:
                        console_logger.warning(f"No edges matched for incident: {incident_type}")
                        continue
                    
                    matched_edges_count += len(matched_edges)
                    
                    # Map HERE incident types to our display types
                    type_map = {
                        'accident': 'Accident',
                        'construction': 'Construction',
                        'congestion': 'Congestion',
                        'disabledvehicle': 'Disabled Vehicle',
                        'masstransit': 'Mass Transit Event',
                        'plannedevent': 'Planned Event',
                        'roadhazard': 'Road Hazard',
                        'roadclosure': 'Road Closure',
                        'weather': 'Weather',
                        'lanerestriction': 'Lane Restriction',
                        'other': 'Other'
                    }
                    
                    # Map HERE criticality to our severity
                    criticality_map = {
                        'low': 'Light',
                        'minor': 'Light',
                        'major': 'Medium',
                        'critical': 'Heavy'
                    }
                    
                    display_type = type_map.get(incident_type, 'Other')
                    severity = criticality_map.get(criticality, 'Light')
                    
                    # Calculate jam factor based on HERE data
                    if road_closed or incident_type == 'roadclosure':
                        jam_factor = 10.0
                    elif criticality == 'critical':
                        jam_factor = 8.0
                    elif criticality == 'major':
                        jam_factor = 6.0
                    elif criticality == 'minor':
                        jam_factor = 4.0
                    else:
                        jam_factor = 2.0
                    
                    # Calculate speed reduction
                    if road_closed or incident_type == 'roadClosure':
                        speed_reduction = 1.0
                        current_speed_kph = 0
                    else:
                        speed_reduction = 1.0 - (jam_factor / 10.0)
                        current_speed_kph = 50 * (1 - speed_reduction)
                    
                    # Create disruption entries for each matched edge (TrafficEdge objects or dicts)
                    for edge in matched_edges:
                        speed_kph = edge_value(edge, 'speed_kph', aliases=['flow_speed_kph'], default=0)
                        free_flow_kph = edge_value(edge, 'freeFlow_kph', aliases=['flow_free_flow_kph'], default=0)
                        jam_factor_value = edge_value(edge, 'jamFactor', aliases=['flow_jam_factor'], default=0)
                        is_closed_value = edge_value(edge, 'isClosed', aliases=['incident_road_closed'], default=False)

                        disruption = {
                            'source_id': int(edge_value(edge, 'source', default=0)),
                            'target_id': int(edge_value(edge, 'target', default=0)),
                            'source_lat': float(edge_value(edge, 'source_lat', default=0)),
                            'source_lng': float(edge_value(edge, 'source_lon', default=0)),
                            'target_lat': float(edge_value(edge, 'target_lat', default=0)),
                            'target_lng': float(edge_value(edge, 'target_lon', default=0)),
                            'road_name': escape_string(road_name or 'Unknown Road'),
                            'incident_type': escape_string(display_type or 'Other'),
                            'incident_criticality': escape_string(criticality.title() if criticality else 'Low'),
                            'incident_description': escape_string(description or ''),
                            'incident_road_closed': bool(road_closed),
                            'incident_start_time': escape_string(incident.get('incident_start_time', '') if is_from_csv else incident_details.get('startTime', '')),
                            'incident_end_time': escape_string(incident.get('incident_end_time', '') if is_from_csv else incident_details.get('endTime', '')),
                            'highway_type': escape_string(incident.get('highway_type', '') if is_from_csv else ''),
                            'here_type': escape_string(incident_type or 'other'),
                            'severity': escape_string(severity or 'Light'),
                            'speed_kph': float(speed_kph or 0),
                            'free_flow_kph': float(free_flow_kph or 0),
                            'jam_factor': float(jam_factor_value or 0),
                            'is_closed': bool(is_closed_value),
                            'slowdown_ratio': float(round(1.0 - speed_reduction, 3))
                        }
                        
                        # Group by incident type
                        if display_type not in disruptions_by_type:
                            disruptions_by_type[display_type] = []
                        disruptions_by_type[display_type].append(disruption)
                        total_disruptions += 1
                    
                    console_logger.success(f"{display_type} ({severity}) matched to {len(matched_edges)} edges")
                    
                except Exception as e:
                    console_logger.warning(f"Error processing incident: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        # ============================================================
        # FETCH FLOW DATA (congestion/traffic conditions)
        # ============================================================
        if flow_service:
            if use_cached_data and recent_flow_files:
                # Use cached flow data
                latest_flow_file = max(recent_flow_files, key=lambda f: f.stat().st_mtime)
                try:
                    flow_df = pd.read_csv(latest_flow_file)
                    flow_data = flow_df.to_dict('records')
                    console_logger.data(f"Loaded {len(flow_data)} cached flow segments from {latest_flow_file.name}")
                except Exception as e:
                    console_logger.warning(f"Error loading cached flow: {e} - falling back to API")
                    flow_data = flow_service.fetch_flow_data()
            else:
                # Fetch fresh flow data
                flow_data = flow_service.fetch_flow_data()
            
            console_logger.info(f"Processing {len(flow_data)} HERE Traffic flow segments...")
            
            for flow in flow_data:
                try:
                    current_flow = flow.get('currentFlow', {})
                    free_flow = flow.get('freeFlow', {})
                    jam_factor = float(current_flow.get('jamFactor', 0.0))
                    speed = float(current_flow.get('speed', 0.0))
                    free_flow_speed = float(free_flow.get('speed', 50.0))
                    confidence = float(current_flow.get('confidence', 0.0))
                    
                    # Skip if no significant congestion
                    if jam_factor < 2.0:
                        continue
                    
                    # Match flow segment to edges using hash-based matcher
                    matched_edges = flow_service.matcher.match_traffic_flow_item(flow)
                    
                    if not matched_edges:
                        continue  # Skip silently for flow - too many segments
                    
                    matched_edges_count += len(matched_edges)
                    
                    # Map jam factor to severity
                    if jam_factor >= 8.0:
                        severity = 'Heavy'
                    elif jam_factor >= 5.0:
                        severity = 'Medium'
                    else:
                        severity = 'Light'
                    
                    # Create disruption entries for each matched edge (TrafficEdge objects)
                    for edge in matched_edges:
                        # Create disruption entry for flow
                        disruption = {
                            'source_id': int(edge.source),
                            'target_id': int(edge.target),
                            'source_lat': float(edge.source_lat),
                            'source_lng': float(edge.source_lon),
                            'target_lat': float(edge.target_lat),
                            'target_lng': float(edge.target_lon),
                            'road_name': escape_string(flow.get('location', {}).get('description', 'Traffic Congestion')),
                            'incident_type': 'Congestion',
                            'severity': escape_string(severity or 'Light'),
                            'speed_kph': float(edge.speed_kph or 0),
                            'free_flow_kph': float(edge.freeFlow_kph or 0),
                            'jam_factor': float(edge.jamFactor or 0),
                            'is_closed': bool(edge.isClosed),
                            'slowdown_ratio': float(round(max(0, 1.0 - (speed / free_flow_speed if free_flow_speed > 0 else 1)), 3)),
                            'confidence': float(confidence or 0),
                            'here_type': 'flow'
                        }
                        
                        # Group congestion separately
                        if 'Congestion' not in disruptions_by_type:
                            disruptions_by_type['Congestion'] = []
                        disruptions_by_type['Congestion'].append(disruption)
                        total_disruptions += 1
                
                except Exception as e:
                    # Silently skip problematic flow items - there are many
                    continue
        
        # Append user-reported disruptions so they behave like HERE incidents
        user_disruptions = get_user_disruptions_for_api()
        for disruption in user_disruptions:
            incident_type = disruption.get('incident_type', 'User Incident')
            if incident_type not in disruptions_by_type:
                disruptions_by_type[incident_type] = []
            disruptions_by_type[incident_type].append(disruption)
            total_disruptions += 1

        # Calculate statistics
        type_counts = {incident_type: len(disruptions) for incident_type, disruptions in disruptions_by_type.items()}
        severity_counts = {'Heavy': 0, 'Medium': 0, 'Light': 0}
        
        # Map criticality to severity for statistics
        criticality_to_severity = {
            'critical': 'Heavy',
            'major': 'Heavy',
            'high': 'Medium',
            'medium': 'Medium',
            'minor': 'Light',
            'low': 'Light'
        }
        
        for disruptions in disruptions_by_type.values():
            for disruption in disruptions:
                # Get severity from either 'severity' field (HERE data) or map from 'incident_criticality' (user incidents)
                if 'severity' in disruption:
                    severity = disruption['severity']
                elif 'incident_criticality' in disruption:
                    severity = criticality_to_severity.get(str(disruption.get('incident_criticality', 'low')).lower(), 'Light')
                else:
                    severity = 'Light'
                
                if severity in severity_counts:
                    severity_counts[severity] += 1
        
        console_logger.info("Summary:")
        console_logger.data(f"Total disruptions: {total_disruptions}")
        console_logger.data(f"Matched edges: {matched_edges_count}")
        console_logger.data(f"By type: {type_counts}")
        console_logger.data(f"By severity: {severity_counts}")
        
        # Ensure all string values are properly encoded for JSON
        import json
        response_data = {
            'success': True,
            'total_disruptions': total_disruptions,
            'matched_edges_count': matched_edges_count,
            'disruptions_by_type': disruptions_by_type,
            'type_counts': type_counts,
            'severity_counts': severity_counts,
            'timestamp': time.time(),
            'note': 'Using HERE API with hash-based edge matching - pre-matched edges from CSV',
            'user_reported_total': len(user_disruptions)
        }
        
        # Validate JSON serialization
        try:
            json.dumps(response_data)
        except Exception as e:
            console_logger.error(f"Error serializing response to JSON: {e}")
            # Sanitize strings to prevent JSON errors
            def sanitize_for_json(obj):
                if isinstance(obj, dict):
                    return {k: sanitize_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [sanitize_for_json(item) for item in obj]
                elif isinstance(obj, str):
                    # Remove control characters that might break JSON
                    return ''.join(char if ord(char) >= 32 or char in '\t\n\r' else '' for char in obj)
                else:
                    return obj
            response_data = sanitize_for_json(response_data)
        
        return jsonify(response_data)
        
    except Exception as e:
        console_logger.error(f"Error in get_active_disruptions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error loading disruptions: {str(e)}"
        })


@app.route('/get_raw_here_traffic')
def get_raw_here_traffic():
    """
    Get raw HERE API traffic data (non-matched to OSM edges)
    Returns original HERE flow segments and incidents with their geometries
    """
    try:
        here_service = flow_service
        
        raw_traffic = {
            'flow_segments': [],
            'incidents': []
        }
        
        # Fetch flow data
        flow_data = flow_service.fetch_flow_data()
        console_logger.info(f"Fetching {len(flow_data)} raw HERE flow segments...")
        
        for flow in flow_data:
            try:
                current_flow = flow.get('currentFlow', {})
                jam_factor = float(current_flow.get('jamFactor', 0.0))
                speed = float(current_flow.get('speed', 0.0))
                free_flow_speed = float(current_flow.get('freeFlowSpeed', 50.0))
                confidence = float(current_flow.get('confidence', 0.0))
                
                # Extract location/shape data
                location = flow.get('location', {})
                shape = location.get('shape', {})
                links = shape.get('links', [])
                
                # Parse coordinates from shape
                coordinates = []
                for link in links:
                    points = link.get('points', [])
                    for point in points:
                        lat = point.get('lat', 0)
                        lng = point.get('lng', 0)
                        if lat and lng:
                            coordinates.append([lat, lng])
                
                if not coordinates:
                    continue
                
                # Map jam factor to severity
                if jam_factor >= 8.0:
                    severity = 'Heavy'
                elif jam_factor >= 5.0:
                    severity = 'Medium'
                else:
                    severity = 'Light'
                
                raw_traffic['flow_segments'].append({
                    'coordinates': coordinates,
                    'jam_factor': jam_factor,
                    'speed_kph': speed * 3.6,  # m/s to km/h
                    'free_flow_kph': free_flow_speed * 3.6,
                    'severity': severity,
                    'confidence': confidence,
                    'type': 'flow',
                    'description': location.get('description', 'Traffic Flow')
                })
                
            except Exception as e:
                continue
        
        # Fetch incidents
        incidents = incident_service.fetch_incidents_data()
        console_logger.info(f"Fetching {len(incidents)} raw HERE incidents...")
        
        for incident in incidents:
            try:
                incident_details = incident.get('incidentDetails', {})
                incident_type = incident_details.get('type', 'other')
                criticality = incident_details.get('criticality', 'low')
                road_closed = incident_details.get('roadClosed', False)
                
                location = incident.get('location', {})
                shape = location.get('shape', {})
                links = shape.get('links', [])
                
                # Parse coordinates from shape
                coordinates = []
                for link in links:
                    points = link.get('points', [])
                    for point in points:
                        lat = point.get('lat', 0)
                        lng = point.get('lng', 0)
                        if lat and lng:
                            coordinates.append([lat, lng])
                
                if not coordinates:
                    continue
                
                # Map criticality to severity
                criticality_map = {
                    'low': 'Light',
                    'minor': 'Light',
                    'major': 'Medium',
                    'critical': 'Heavy'
                }
                
                severity = criticality_map.get(criticality, 'Light')
                
                raw_traffic['incidents'].append({
                    'coordinates': coordinates,
                    'type': incident_type,
                    'severity': severity,
                    'criticality': criticality,
                    'road_closed': road_closed,
                    'description': incident_details.get('description', {}).get('value', 'Incident'),
                    'start_time': incident_details.get('startTime', ''),
                    'end_time': incident_details.get('endTime', '')
                })
                
            except Exception as e:
                continue
        
        console_logger.success(f"Returning {len(raw_traffic['flow_segments'])} flow segments and {len(raw_traffic['incidents'])} incidents")
        
        return jsonify({
            'success': True,
            'data': raw_traffic,
            'total_flow': len(raw_traffic['flow_segments']),
            'total_incidents': len(raw_traffic['incidents'])
        })
        
    except Exception as e:
        console_logger.error(f"Error in get_raw_here_traffic: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error loading raw traffic: {str(e)}"
        })


@app.route('/get_traffic_with_geometry')
def get_traffic_with_geometry():
    """
    Get traffic data with full OSM road geometries (CACHED VERSION)
    Returns matched traffic edges with their LineString geometries from quezon_city_edges.csv
    Uses intelligent caching to avoid reloading data on every request
    """
    try:
        # Load edges with cache (only reloads if file changed)
        edges_df, edge_lookup = load_edges_with_cache()
        
        if edge_lookup is None:
            return jsonify({
                'success': False,
                'error': 'Failed to load OSM edges'
            })
        
        # Load traffic data with cache (only reloads if traffic file changed)
        traffic_segments = load_traffic_with_cache(edge_lookup)
        
        return jsonify({
            'success': True,
            'segments': traffic_segments,
            'total_segments': len(traffic_segments),
            'cached': {
                'edges_loaded_at': _edges_cache['loaded_at'],
                'traffic_loaded_at': _traffic_cache['loaded_at']
            }
        })
        
    except Exception as e:
        console_logger.error(f"Error in get_traffic_with_geometry: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Error loading traffic: {str(e)}"
        })


@app.route('/compute_dhl_route', methods=['POST'])
def compute_dhl_route():
    """Compute optimal route using DHL algorithm"""
    data = request.json
    
    try:
        if dhl_router is None:
            return jsonify({
                'success': False,
                'error': 'DHL Router not initialized properly'
            })
        
        # Extract pin coordinates (original user click points)
        start_pin_lat = float(data['start_lat'])
        start_pin_lng = float(data['start_lng'])
        dest_pin_lat = float(data['dest_lat'])
        dest_pin_lng = float(data['dest_lng'])
        
        # Check if OSM edge-based routing should be used (snap point data)
        start_osm_edge = data.get('start_osm_edge')
        dest_osm_edge = data.get('dest_osm_edge')
        
        # Default to pin coordinates if no snap info
        start_snap_lat = start_pin_lat
        start_snap_lng = start_pin_lng
        dest_snap_lat = dest_pin_lat
        dest_snap_lng = dest_pin_lng
        
        # Default edge information (will be overridden if snap data available)
        start_edge_source = 0
        start_edge_target = 0
        start_edge_oneway = 0
        dest_edge_source = 0
        dest_edge_target = 0
        dest_edge_oneway = 0
        
        # Extract snap point and edge information from OSM snap result
        if start_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in start_osm_edge:
                start_snap_lat = float(start_osm_edge['snapped_point']['lat'])
                start_snap_lng = float(start_osm_edge['snapped_point']['lng'])
            
            # Get edge information (CRITICAL: tells us which road the snap is on)
            if 'osm_nodes' in start_osm_edge and len(start_osm_edge['osm_nodes']) >= 2:
                start_edge_source = int(start_osm_edge['osm_nodes'][0])
                start_edge_target = int(start_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = start_osm_edge.get('oneway', '0')
            try:
                start_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                start_edge_oneway = 0
            
            console_logger.success(f"Start snap (DHL): {start_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {start_edge_source}→{start_edge_target}, oneway={start_edge_oneway})")
        
        if dest_osm_edge:
            # Get snapped coordinates
            if 'snapped_point' in dest_osm_edge:
                dest_snap_lat = float(dest_osm_edge['snapped_point']['lat'])
                dest_snap_lng = float(dest_osm_edge['snapped_point']['lng'])
            
            # Get edge information
            if 'osm_nodes' in dest_osm_edge and len(dest_osm_edge['osm_nodes']) >= 2:
                dest_edge_source = int(dest_osm_edge['osm_nodes'][0])
                dest_edge_target = int(dest_osm_edge['osm_nodes'][1])
            
            # Get one-way property
            oneway_str = dest_osm_edge.get('oneway', '0')
            try:
                dest_edge_oneway = int(oneway_str)
            except (ValueError, TypeError):
                dest_edge_oneway = 0
            
            console_logger.success(f"Dest snap (DHL): {dest_osm_edge.get('road_name', 'Unknown')} " +
                  f"(Edge: {dest_edge_source}→{dest_edge_target}, oneway={dest_edge_oneway})")
        
        # Check if disruptions should be used
        use_disruptions = data.get('use_disruptions', False)
        dataset_mode = data.get('dataset_mode', None)  # Get dataset mode from request
        
        # DHL: Get disruption directory path (string, not tuple)
        # If disruption_files is explicitly provided, use it
        # Otherwise, if use_disruptions is True or dataset_mode is provided, use appropriate files
        disruption_files = data.get('disruption_files', '')  # Default to empty string, not tuple
        
        # For backward compatibility, also check disruption_file (single)
        disruption_file = data.get('disruption_file', '')
        
        # Handle different ways disruptions can be specified
        if not disruption_files or isinstance(disruption_files, tuple):  # Handle legacy tuple format
            # If use_disruptions is True or dataset_mode is set, use appropriate disruption files
            if use_disruptions or dataset_mode:
                # Get the directory path based on dataset mode
                disruption_files = get_dynamic_disruption_file('dhl', dataset_mode)
                
                # If no dynamic files and use_disruptions is True, fall back to static file
                if not disruption_files and use_disruptions:
                    disruption_gr = Config.PROCESSED_DATA_DIR / 'qc_disrupted_scenario_1.gr'
                    if disruption_gr.exists():
                        disruption_files = str(disruption_gr)
                        console_logger.data(f"Using static disruption file: {disruption_files}")
                    else:
                        console_logger.warning("No disruption files found")
                        disruption_files = ''
            else:
                disruption_files = ''
        elif isinstance(disruption_files, str) and disruption_files == 'active_disruptions':
            # Frontend sent 'active_disruptions' - use dynamic disruptions
            disruption_files = get_dynamic_disruption_file('dhl', dataset_mode)
            if not disruption_files:
                # Fall back to static
                disruption_gr = Config.PROCESSED_DATA_DIR / 'qc_disrupted_scenario_1.gr'
                if disruption_gr.exists():
                    disruption_files = str(disruption_gr)
                    console_logger.data(f"📍 Using static disruption file: {disruption_files}")
                else:
                    console_logger.warning(f"⚠️  No disruption files found")
                    disruption_files = ''
        
        # Support legacy single disruption_file parameter
        if disruption_file and not disruption_files:
            disruption_files = disruption_file
        
        tau_threshold = float(data.get('tau_threshold', 0.5))
        generate_alternatives = data.get('generate_alternatives', True)  # Default: True (generate alternatives)
        
        console_logger.processing(f"Computing DHL route with snap points:")
        console_logger.data(f"  Start: Pin({start_pin_lat}, {start_pin_lng}) → Snap({start_snap_lat}, {start_snap_lng})")
        console_logger.data(f"  Dest:  Pin({dest_pin_lat}, {dest_pin_lng}) → Snap({dest_snap_lat}, {dest_snap_lng})")
        console_logger.data(f"  Dataset mode: {dataset_mode if dataset_mode else 'auto'}")
        console_logger.data(f"  Disruption directory: {disruption_files if disruption_files else '(none)'}")
        console_logger.data(f"  Tau threshold: {tau_threshold}")
        console_logger.data(f"  Generate alternatives: {generate_alternatives}")
        
        # Compute route using DHL with disruption parameters
        # Pass disruption directory to C++ - it will find flow/incident CSV files automatically
        start_time = time.time()
        route_result = dhl_router.compute_route(
            start_pin_lat, start_pin_lng,
            dest_pin_lat, dest_pin_lng,
            start_snap_lat, start_snap_lng,
            dest_snap_lat, dest_snap_lng,
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway,
            disruption_files, tau_threshold, generate_alternatives  # Pass directory path
        )
        computation_time = time.time() - start_time
        
        if not route_result['success']:
            return jsonify({
                'success': False,
                'error': route_result['error'],
                'debug_info': route_result.get('raw_output', '')
            })
        
        # Get polylines for Google Maps
        polylines = dhl_router.get_route_polylines_for_gmaps(route_result)
        
        # Get route summary
        summary = dhl_router.get_route_summary(route_result)
        summary['total_computation_time_sec'] = round(computation_time, 3)
        
        # Get the full metrics from C++ output
        cpp_metrics = route_result.get('metrics', {})
        
        # Merge summary into cpp_metrics (keeping all C++ fields, adding Python-calculated fields)
        full_metrics = {**cpp_metrics, **summary}
        
        # Get enhanced road name information using the new methods
        turn_by_turn_directions = dhl_router.get_turn_by_turn_directions(route_result)
        route_summary_text = dhl_router.get_route_summary_text(route_result)
        detailed_route_info = dhl_router.get_detailed_route_info(route_result)
        
        # Extract disruption_analysis from C++ output
        disruption_analysis = route_result.get('disruption_analysis', {})
        if disruption_analysis:
            console_logger.data(f"DHL Disruption analysis detected: {disruption_analysis.get('route_disruptions', {}).get('total_count', 0)} disruptions")
        
        # Enhance alternative routes with geometry (only if requested)
        if generate_alternatives:
            enhanced_alt_routes = enhance_alternative_routes_with_geometry(route_result.get('alternative_routes', []))
        else:
            enhanced_alt_routes = []
            console_logger.data(f"Alternative routes generation skipped (generate_alternatives=False)")
        
        return jsonify({
            'success': True,
            'route': {
                'polylines': polylines,
                'geometry': route_result.get('route', {}).get('geometry', []),  # Add C++ geometry with edge details
                'start_point': {'lat': start_snap_lat, 'lng': start_snap_lng},
                'end_point': {'lat': dest_snap_lat, 'lng': dest_snap_lng},
                'pin_start': {'lat': start_pin_lat, 'lng': start_pin_lng},
                'pin_end': {'lat': dest_pin_lat, 'lng': dest_pin_lng},
                'coordinates': route_result.get('route', {}).get('coordinates', []),
                'path_nodes': route_result.get('route', {}).get('path_nodes', []),
                'road_segments': route_result.get('route', {}).get('road_segments', []),
                'route_summary': route_summary_text, 
                'route_summary_detailed': route_result.get('route', {}).get('route_summary', ''),  # Original trace
                'turn_by_turn_directions': turn_by_turn_directions,
                'display_format': route_result.get('route', {}).get('display_format', {}),
                'detailed_info': detailed_route_info
            },
            'metrics': full_metrics,  # Use full_metrics with all C++ fields
            'disruption_analysis': disruption_analysis,  # Pass disruption analysis from C++ to frontend
            'disruptions_summary': route_result.get('disruptions_summary', {}),  # Also pass disruptions_summary for additional details
            'alternative_routes': enhanced_alt_routes,  # Pass enhanced alternative routes (or empty if not requested)
            'dhl_update_info': route_result.get('dhl_update_info', {}),  # Pass DHL update strategy info
            'disruption_config': route_result.get('disruption_config', {}),  # Pass disruption configuration
            'algorithm': 'DHL (Dual-Hierarchy Labelling)',
            'gps_mapping': route_result.get('gps_mapping', {}),
            'snap_edges': route_result.get('snap_edges', {}),
            'disruptions': route_result.get('disruptions', {}),
            'raw_dhl_output': route_result.get('raw_dhl_output', {})
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"DHL route computation error: {str(e)}"
        })


@app.route('/compare_dhl_routes', methods=['POST'])
def compare_dhl_routes():
    """Compare DHL base route with disrupted route"""
    data = request.json
    
    try:
        if dhl_router is None:
            return jsonify({
                'success': False,
                'error': 'DHL Router not initialized properly'
            })
        
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        
        # Use the DHL router's built-in comparison function
        comparison_result = dhl_router.compare_routes(start_lat, start_lng, dest_lat, dest_lng)
        
        if not comparison_result['success']:
            return jsonify({
                'success': False,
                'error': comparison_result['error']
            })
        
        # Enhance the comparison result with detailed road name information
        if 'routes' in comparison_result:
            for route_type in ['base', 'disrupted']:
                if route_type in comparison_result['routes']:
                    route_data = comparison_result['routes'][route_type]
                    
                    # Create a mock route result to use with our new methods
                    mock_route_result = {
                        'success': True,
                        'route': {
                            'path_nodes': route_data.get('summary', {}).get('path_nodes', []),
                            'road_segments': route_data.get('road_segments', []),
                            'turn_by_turn_directions': route_data.get('turn_by_turn_directions', []),
                            'route_summary': route_data.get('route_summary', ''),
                            'display_format': route_data.get('display_format', {})
                        }
                    }
                    
                    # Add enhanced information if path nodes are available
                    if route_data.get('summary', {}).get('path_nodes'):
                        enhanced_summary = dhl_router.get_route_summary_text(mock_route_result)
                        enhanced_directions = dhl_router.get_turn_by_turn_directions(mock_route_result)
                        enhanced_details = dhl_router.get_detailed_route_info(mock_route_result)
                        
                        # Add enhanced data to the route
                        route_data['enhanced_summary'] = enhanced_summary
                        route_data['enhanced_directions'] = enhanced_directions
                        route_data['enhanced_details'] = enhanced_details
                        
                        console_logger.data(f"🛣️  Enhanced {route_type} route: {enhanced_summary}")
        
        # Add straight line for additional comparison
        straight_line = [{
            'path': [
                {'lat': start_lat, 'lng': start_lng},
                {'lat': dest_lat, 'lng': dest_lng}
            ],
            'strokeColor': '#00FF00',  # Green
            'strokeOpacity': 0.5,
            'strokeWeight': 2,
            'geodesic': True
        }]
        
        comparison_result['routes']['straight_line'] = {
            'polylines': straight_line,
            'name': 'Straight Line',
            'color': '#00FF00'
        }
        
        comparison_result['start_point'] = {'lat': start_lat, 'lng': start_lng}
        comparison_result['end_point'] = {'lat': dest_lat, 'lng': dest_lng}
        
        return jsonify(comparison_result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"DHL route comparison error: {str(e)}"
        })


@app.route('/compare_algorithms', methods=['POST'])
def compare_algorithms():
    """
    DEPRECATED: Compare HC2L and DHL algorithms side by side
    
    This endpoint is deprecated. The new routing flow uses individual algorithm
    endpoints (/compute_gps_hc2l_route and /compute_dhl_route) with proper OSM
    snapping and doesn't require this comparison endpoint.
    
    Kept for backward compatibility but may return errors due to API changes.
    """
    return jsonify({
        'success': False,
        'error': 'This endpoint is deprecated. Please use the individual algorithm endpoints with OSM snapping.',
        'alternative': 'Use /compute_gps_hc2l_route and /compute_dhl_route separately with proper snap point data'
    }), 410  # 410 Gone status code


@app.route('/compare_with_google_maps', methods=['POST'])
def compare_with_google_maps():
    """
    Compare current algorithm route with Google Maps route
    
    IMPORTANT: This function uses the CURRENT ROUTE already calculated on frontend.
    No route recalculation is needed - we just compare the existing route.
    
    Frontend sends:
    - start_lat, start_lng, dest_lat, dest_lng: Origin/destination coordinates
    - algorithm: Algorithm name used (HC2L, DHC2L, DHL, etc)
    - existing_route_geometry: Current route geometry from the calculated route
    
    Steps:
    1. Extract algorithm route coordinates from the passed geometry
    2. Fetch Google Maps route for the same origin/destination
    3. Calculate Fréchet distance and overlap metrics
    4. Return both routes for map display (no recalculation!)
    """
    data = request.json
    
    try:
        # Validate required input parameters
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        algorithm_name = data.get('algorithm', 'Unknown Algorithm')
        
        console_logger.processing(f"\n🗺️  === GOOGLE MAPS COMPARISON (Dynamic) ===")
        console_logger.data(f"Algorithm: {algorithm_name}")
        console_logger.data(f"Route: ({start_lat}, {start_lng}) → ({dest_lat}, {dest_lng})")
        console_logger.data(f"Using existing route data (no recalculation)")
        
        # Validate Google Maps service is initialized
        if not gmaps_service:
            console_logger.error(f"Google Maps service not initialized")
            return jsonify({
                'success': False,
                'error': 'Google Maps service not initialized. Check API key in .env'
            })
        
        # ============================================================
        # STEP 1: Extract algorithm route coordinates from passed geometry
        # ============================================================
        console_logger.processing(f"Step 1: Extract current algorithm route coordinates")
        
        algorithm_coords = []
        existing_geometry = data.get('existing_route_geometry')
        console_logger.data(f"   Received geometry type: {type(existing_geometry)}")
        
        if not existing_geometry:
            console_logger.error(f"   ❌ No route geometry provided")
            return jsonify({
                'success': False,
                'error': 'No route geometry found. Please calculate a route first.'
            })
        
        # Debug: print raw geometry
        console_logger.data(f"   Raw geometry (first 200 chars): {str(existing_geometry)[:200]}")
        
        # Handle different geometry formats from various routing algorithms
        if isinstance(existing_geometry, list):
            # Format 1: Array of segments with coordinates
            for segment in existing_geometry:
                if isinstance(segment, dict):
                    # Format 1a: Direct dict with lat/lng keys (MOST COMMON - DHL format)
                    if 'lat' in segment and 'lng' in segment:
                        try:
                            lat = float(segment['lat'])
                            lng = float(segment['lng'])
                            algorithm_coords.append([lat, lng])
                        except (ValueError, TypeError) as e:
                            console_logger.warning(f"   ⚠️  Skipping invalid lat/lng dict: {segment} - {e}")
                    # Format 1b: Dict with nested coordinates key
                    elif 'coordinates' in segment:
                        coords_list = segment['coordinates']
                        if isinstance(coords_list, list):
                            for coord in coords_list:
                                if isinstance(coord, list) and len(coord) >= 2:
                                    try:
                                        lat = float(coord[1]) if len(coord) > 1 else float(coord[0])
                                        lng = float(coord[0]) if len(coord) > 1 else float(coord[1])
                                        # Swap if detected as [lat, lng] format
                                        if lat > 90 or lat < -90:
                                            lat, lng = lng, lat
                                        algorithm_coords.append([lat, lng])
                                    except (ValueError, IndexError) as e:
                                        console_logger.warning(f"   ⚠️  Skipping invalid coord: {coord} - {e}")
                    # Format 1c: Dict with path key
                    elif 'path' in segment:
                        path = segment['path']
                        if isinstance(path, list):
                            for pt in path:
                                if isinstance(pt, dict) and 'lat' in pt and 'lng' in pt:
                                    algorithm_coords.append([float(pt['lat']), float(pt['lng'])])
                    # Format 1d: Dict with polyline key (Google Maps)
                    elif 'polyline' in segment:
                        # Handle polyline format (Google Maps)
                        try:
                            import polyline
                            decoded = polyline.decode(segment['polyline'])
                            algorithm_coords.extend(decoded)
                        except:
                            pass
                            
                elif isinstance(segment, (list, tuple)) and len(segment) >= 2:
                    # Format 2: Direct coordinate array [lat, lng] or [lng, lat]
                    try:
                        lat = float(segment[0])
                        lng = float(segment[1])
                        # Detect format: if first value > 90, it's probably [lng, lat]
                        if lat > 90 or lat < -90:
                            lat, lng = lng, lat
                        algorithm_coords.append([lat, lng])
                    except (ValueError, TypeError) as e:
                        console_logger.warning(f"   ⚠️  Skipping invalid segment: {segment} - {e}")
        
        # Remove duplicate consecutive points
        if algorithm_coords:
            deduplicated = [algorithm_coords[0]]
            for coord in algorithm_coords[1:]:
                if coord != deduplicated[-1]:
                    deduplicated.append(coord)
            algorithm_coords = deduplicated
            console_logger.success(f"   ✅ Deduped to {len(algorithm_coords)} unique points")
        
        if not algorithm_coords:
            console_logger.error(f"   ❌ Could not extract coordinates from geometry")
            console_logger.data(f"   Geometry structure: {existing_geometry}")
            return jsonify({
                'success': False,
                'error': 'Route geometry format is invalid or empty. Check server logs for details.'
            })
        
        console_logger.success(f"   ✅ Extracted {len(algorithm_coords)} unique points from algorithm route")
        console_logger.data(f"      Start point: [{algorithm_coords[0][0]:.6f}, {algorithm_coords[0][1]:.6f}]")
        console_logger.data(f"      End point: [{algorithm_coords[-1][0]:.6f}, {algorithm_coords[-1][1]:.6f}]")
        
        # ============================================================
        # STEP 2: Fetch Google Maps route using same origin/destination
        # ============================================================
        console_logger.processing(f"\n🌐 Step 2: Fetch Google Maps route")
        
        google_route = gmaps_service.get_directions(start_lat, start_lng, dest_lat, dest_lng)
        
        if not google_route or not google_route.get('success'):
            error_msg = google_route.get('error') if google_route else 'Google Maps API call failed'
            console_logger.error(f"   ❌ Error: {error_msg}")
            return jsonify({
                'success': False,
                'error': f"Failed to fetch Google Maps route: {error_msg}"
            })
        
        google_coords = google_route.get('coordinates', [])
        
        if not google_coords:
            console_logger.error(f"   ❌ Google Maps returned no coordinates")
            return jsonify({
                'success': False,
                'error': 'Google Maps route has no coordinates'
            })
        
        console_logger.success(f"   ✅ Google Maps route fetched: {len(google_coords)} points")
        console_logger.data(f"      Distance: {google_route.get('distance_text', 'N/A')}")
        console_logger.data(f"      Duration: {google_route.get('duration_text', 'N/A')}")
        console_logger.data(f"      Distance (meters): {google_route.get('distance_meters', 'N/A')}")
        
        # ============================================================
        # STEP 3: Calculate comparison metrics
        # ============================================================
        console_logger.processing(f"\n📊 Step 3: Calculate comparison metrics")
        
        # Calculate Fréchet distance (measures max deviation between routes)
        frechet_distance = gmaps_service.compute_frechet_distance(algorithm_coords, google_coords)
        
        # Calculate segment overlap (percentage of matching points)
        segment_overlap = gmaps_service.compute_segment_overlap(algorithm_coords, google_coords)
        
        console_logger.success(f"   ✅ Fréchet distance: {frechet_distance:.2f} meters")
        console_logger.success(f"   ✅ Segment overlap: {segment_overlap:.2f}%")
        
        google_distance_meters = google_route.get('distance_meters', 1)
        frechet_ratio = round((frechet_distance / max(google_distance_meters, 1)) * 100, 2)
        console_logger.success(f"   ✅ Fréchet/Distance ratio: {frechet_ratio}%")
        
        # ============================================================
        # STEP 4: Build response with both routes for map display
        # ============================================================
        console_logger.success(f"\n✅ Comparison complete!")
        
        result = {
            'success': True,
            'algorithm_route': {
                'coordinates': algorithm_coords,
                'name': algorithm_name,
                'point_count': len(algorithm_coords),
                'format': 'Dynamic (current route data)'
            },
            'google_maps_route': {
                'coordinates': google_coords,
                'distance_meters': google_route.get('distance_meters', 0),
                'duration_seconds': google_route.get('duration_seconds', 0),
                'distance_text': google_route.get('distance_text', ''),
                'duration_text': google_route.get('duration_text', ''),
                'point_count': len(google_coords)
            },
            'comparison': {
                'frechet_distance_meters': round(frechet_distance, 2),
                'segment_overlap_percent': round(segment_overlap, 2),
                'algorithm_distance_ratio': frechet_ratio,
                'interpretation': {
                    'frechet_status': 'Excellent' if frechet_distance < 500 else 'Very Good' if frechet_distance < 1000 else 'Good' if frechet_distance < 2000 else 'Fair',
                    'overlap_status': 'Perfect' if segment_overlap >= 90 else 'Very Good' if segment_overlap >= 75 else 'Good' if segment_overlap >= 60 else 'Fair'
                }
            },
            'metadata': {
                'comparison_time': time.time(),
                'algorithm': algorithm_name,
                'origin': {'lat': start_lat, 'lng': start_lng},
                'destination': {'lat': dest_lat, 'lng': dest_lng}
            }
        }
        
        console_logger.data(f"   📊 Fréchet Status: {result['comparison']['interpretation']['frechet_status']}")
        console_logger.data(f"   📊 Overlap Status: {result['comparison']['interpretation']['overlap_status']}")
        
        return jsonify(result)
        
    except KeyError as e:
        error_msg = f"Missing required parameter: {str(e)}"
        console_logger.error(f"\n❌ {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg
        })
    except ValueError as e:
        error_msg = f"Invalid parameter value: {str(e)}"
        console_logger.error(f"\n❌ {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg
        })
    except Exception as e:
        import traceback
        console_logger.error(f"\n❌ Google Maps comparison error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Comparison failed: {str(e)}"
        })


@app.route('/get_google_maps_route', methods=['POST'])
def get_google_maps_route():
    """
    Fetch a Google Maps route for comparison panel
    
    This endpoint is specifically for the algorithm comparison panel.
    It only fetches the Google Maps route without comparison metrics.
    
    Frontend sends:
    - start_lat, start_lng: Origin coordinates
    - dest_lat, dest_lng: Destination coordinates
    
    Returns:
    - Google Maps route data with coordinates, distance, duration
    """
    data = request.json
    
    try:
        # Validate required input parameters
        start_lat = float(data['start_lat'])
        start_lng = float(data['start_lng'])
        dest_lat = float(data['dest_lat'])
        dest_lng = float(data['dest_lng'])
        
        console_logger.processing("Fetching Google Maps route")
        console_logger.data(f"Route: ({start_lat}, {start_lng}) → ({dest_lat}, {dest_lng})")
        
        # Validate Google Maps service is initialized
        if not gmaps_service:
            console_logger.error("Google Maps service not initialized")
            return jsonify({
                'success': False,
                'error': 'Google Maps service not initialized. Check API key in .env'
            })
        
        # Fetch Google Maps route
        google_route = gmaps_service.get_directions(start_lat, start_lng, dest_lat, dest_lng)
        
        if not google_route or not google_route.get('success'):
            error_msg = google_route.get('error') if google_route else 'Google Maps API call failed'
            console_logger.error(f"Error: {error_msg}")
            return jsonify({
                'success': False,
                'error': f"Failed to fetch Google Maps route: {error_msg}"
            })
        
        google_coords = google_route.get('coordinates', [])
        
        if not google_coords:
            console_logger.error("Google Maps returned no coordinates")
            return jsonify({
                'success': False,
                'error': 'Google Maps route has no coordinates'
            })
        
        console_logger.success(f"Google Maps route fetched: {len(google_coords)} points")
        console_logger.data(f"Distance: {google_route.get('distance_meters', 'N/A')} meters")
        console_logger.data(f"Duration: {google_route.get('duration_seconds', 'N/A')} seconds")
        
        # Build response with route data
        result = {
            'success': True,
            'route': {
                'coordinates': google_coords,
                'distance_meters': google_route.get('distance_meters', 0),
                'duration_seconds': google_route.get('duration_seconds', 0),
                'point_count': len(google_coords),
                'summary': google_route.get('summary', ''),
                'bounds': google_route.get('bounds', {})
            },
            'metadata': {
                'fetch_time': time.time(),
                'origin': {'lat': start_lat, 'lng': start_lng},
                'destination': {'lat': dest_lat, 'lng': dest_lng}
            }
        }
        
        return jsonify(result)
        
    except KeyError as e:
        error_msg = f"Missing required parameter: {str(e)}"
        console_logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        })
    except ValueError as e:
        error_msg = f"Invalid parameter value: {str(e)}"
        console_logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg
        })
    except Exception as e:
        import traceback
        console_logger.error(f"Google Maps route fetch error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"Route fetch failed: {str(e)}"
        })


@app.route('/register_active_route', methods=['POST'])
def register_active_route():
    """Register a route for automatic disruption monitoring"""
    try:
        data = request.json
        route_id = data.get('route_id', f"route_{int(time.time())}")
        
        auto_service = get_auto_disruption_service()
        if auto_service:
            auto_service.register_active_route(route_id, {
                'algorithm': data.get('algorithm', 'unknown'),
                'start_lat': data.get('start_lat'),
                'start_lng': data.get('start_lng'),
                'dest_lat': data.get('dest_lat'),
                'dest_lng': data.get('dest_lng'),
                'use_disruptions': data.get('use_disruptions', False)
            })
            return jsonify({
                'success': True,
                'route_id': route_id,
                'message': 'Route registered for monitoring'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Auto-disruption service not available'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/unregister_active_route', methods=['POST'])
def unregister_active_route():
    """Unregister a route from monitoring"""
    try:
        data = request.json
        route_id = data.get('route_id')
        
        auto_service = get_auto_disruption_service()
        if auto_service and route_id:
            auto_service.unregister_route(route_id)
            return jsonify({
                'success': True,
                'message': 'Route unregistered'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid route_id or service unavailable'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/fetch_here_traffic', methods=['POST'])
def fetch_here_traffic():
    """
    Fetch real-time traffic data from HERE API and generate disruption file
    
    Request body:
    {
        "algorithm": "hc2l" or "dhl",  // Optional, defaults to "current"
        "apply_immediately": true,      // Optional, whether to use this as dynamic disruption
        "traffic_mode": "incidents" | "flow" | "both"  // Required: specify data mode
    }
    """
    try:
        data = request.get_json() or {}
        algorithm = data.get('algorithm', 'current')
        apply_immediately = data.get('apply_immediately', True)
        traffic_mode = data.get('traffic_mode', 'both')  # Default to both
        
        # Validate traffic mode
        if traffic_mode not in ['incidents', 'flow', 'both']:
            return jsonify({
                'success': False,
                'error': f"Invalid traffic_mode: {traffic_mode}. Must be 'incidents', 'flow', or 'both'"
            })
        
        # Fetch both flow and incident data (services are independent)
        flow_metadata = flow_service.fetch_and_save()
        incident_metadata = incident_service.fetch_and_save()
        
        total_edges = flow_metadata.get('total_edges', 0) + incident_metadata.get('total_edges', 0)
        
        # Determine output file
        if algorithm in ['hc2l', 'dhl']:
            output_file = Config.DISRUPTIONS_DIR / f"here_traffic_disruptions_{algorithm}.gr"
        else:
            output_file = Config.DISRUPTIONS_DIR / "here_traffic_disruptions_current.gr"
        
        # If apply_immediately, the files are already created
        if apply_immediately and total_edges > 0:
            console_logger.success(f"Data updated: {total_edges} total edges (flow: {flow_metadata.get('total_edges', 0)}, incidents: {incident_metadata.get('total_edges', 0)})")
        
        return jsonify({
            'success': True,
            'edges_affected': total_edges,
            'flow_metadata': flow_metadata,
            'incident_metadata': incident_metadata,
            'output_file': str(output_file)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/get_traffic_status', methods=['GET'])
def get_traffic_status():
    """Get current traffic services status"""
    try:
        return jsonify({
            'success': True,
            'flow_service': {
                'initialized': flow_service is not None,
                'api_key_configured': bool(flow_service.api_key if flow_service else False),
                'bbox': flow_service.bbox if flow_service else None
            },
            'incident_service': {
                'initialized': incident_service is not None,
                'api_key_configured': bool(incident_service.api_key if incident_service else False),
                'bbox': incident_service.bbox if incident_service else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/get_settings', methods=['GET'])
def get_settings():
    """Get all persistent application settings"""
    try:
        settings = get_settings_manager()
        all_settings = settings.get_all()
        
        return jsonify({
            'success': True,
            'settings': all_settings,
            'message': 'Settings loaded successfully'
        })
    except Exception as e:
        console_logger.error(f"Error retrieving settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/reset_settings', methods=['POST'])
def reset_settings():
    """Reset all settings to defaults"""
    try:
        settings = get_settings_manager()
        settings.reset_to_defaults()
        console_logger.warning("All settings reset to defaults")
        
        return jsonify({
            'success': True,
            'settings': settings.get_all(),
            'message': 'Settings reset to defaults'
        })
    except Exception as e:
        console_logger.error(f"Error resetting settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/set_auto_update_interval', methods=['POST'])
def set_auto_update_interval():
    """Set the auto-disruption update interval (1-30 minutes) - SAVED PERSISTENTLY"""
    try:
        payload = request.get_json(silent=True) or {}
        requested_minutes = int(payload.get('interval_minutes', 2))
        interval_minutes = max(1, min(30, requested_minutes))
        auto_service = get_auto_disruption_service()

        if not auto_service:
            return jsonify({'success': False, 'error': 'Auto-disruption service not initialized'}), 503

        actual_seconds = auto_service.set_update_interval(interval_minutes * 60)
        console_logger.success(f"Update interval set to {interval_minutes} minutes (saved persistently)")
        
        return jsonify({
            'success': True,
            'interval_seconds': actual_seconds,
            'interval_minutes': actual_seconds // 60,
            'message': f'Update interval saved: {interval_minutes} minutes (survives page refresh)'
        })

    except Exception as e:
        console_logger.error(f"Error setting update interval: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


if __name__ == '__main__':
    # Print beautiful configuration summary
    console_logger.config(Config.get_config_summary())
    
    console_logger.info("Auto-Disruption Service")
    console_logger.data(f"Update Interval: {auto_service.update_interval} seconds ({auto_service.update_interval // 60} minutes)")
    console_logger.data("Monitoring: Dynamic disruption files (flow + incidents + user_incident)")
    console_logger.data("Auto-recalculation: Enabled for active routes")
    console_logger.data("Settings: Persistent (survives page refresh)")
    
    console_logger.info("Starting Flask Server")
    console_logger.data(f"Environment: {Config.FLASK_ENV}")
    console_logger.data(f"Debug: {Config.FLASK_DEBUG}")
    console_logger.data(f"Address: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    
    # Start Flask server
    app.run(
        debug=Config.FLASK_DEBUG,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        use_reloader=False  # Disable auto-reloader to prevent unwanted restarts
    )
