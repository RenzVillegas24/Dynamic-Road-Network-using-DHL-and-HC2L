# experiment_runner_backend.py - Server-Side Experiment Runner with Multi-threading and WebSocket
"""
Experiment Runner Backend

Implements server-side experiment execution with:
- Multi-threading (3 threads default, 9 threads advanced)
- WebSocket real-time updates via Flask-SocketIO
- Lazy disruption loading with FIFO cache
- Progress tracking per thread
- Results storage as JSON files

API Endpoints:
    POST   /api/experiment/start           # Start new experiment
    POST   /api/experiment/<id>/pause      # Pause experiment
    POST   /api/experiment/<id>/stop       # Stop experiment
    POST   /api/experiment/<id>/resume     # Resume paused experiment
    GET    /api/experiment/<id>/progress   # Get progress (HTTP fallback)
    GET    /api/experiment/<id>/result     # Get final results
    GET    /api/experiment/preset/list     # List preset experiments
    GET    /api/experiment/preset/metadata # Get preset metadata
    POST   /api/experiment/cleanup         # Clean up temporary experiments

WebSocket Namespace:
    /api/experiment/<id>/status

File Structure:
    Main/data/experiments/
    ├── preset/
    │   ├── ExperimentPreset.json
    │   ├── disruptions/set_batch_*_route_*/
    │   └── results/[experiment_id]/
    └── temporary/
        └── [temp_id]/
            ├── disruptions/set_trial_*_route_*/
            └── results/
"""

import os
import json
import time
import uuid
import shutil
import threading
import traceback
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import OrderedDict
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty as QueueEmpty

from flask import Blueprint, request, jsonify, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room, Namespace

from config import Config
from console_formatter import get_logger

# Import shared road network utilities (no HTTP calls needed)
from road_network_utils import (
    generate_routes_with_snap_data,
    generate_routes_by_distance_category,
    snap_location_to_edge_data,
    get_random_road_points_data
)

# Import road name mapper for getting edge road names
from road_name_mapper import RoadNameMapper

# Import HERE routing service for route similarity
from here_routing_service import HereRoutingService

# Import experiment metrics collector for centralized metrics gathering
from experiment_metrics_collector import (
    ExperimentMetricsCollector,
    create_metrics_collector,
    IncidentSummary,
    AccuracyMetrics,
    RouteMetricsRecord,
    SimilarityRecord,
    get_disruption_level,
    compute_accuracy,
    DEFAULT_TOLERANCE
)


# Get logger instance
logger = get_logger("ExperimentRunner")


# ============================================================================
# EXPERIMENT PRESET DEFINITIONS
# ============================================================================

# Preset Types
PRESET_STANDARD = "standard"  # 3 trials × 3 batches × 1000 routes
PRESET_SCENARIO = "scenario"  # 1 trial × 30 routes × 10 scenarios × 3 severity levels

# Route Distance Categories (in km)
ROUTE_CATEGORIES = {
    "short": {"min": 0, "max": 5.0, "count": 10},      # < 5.0 km
    "medium": {"min": 5.0, "max": 10.0, "count": 10},  # 5.0 – 10.0 km  
    "long": {"min": 10.0, "max": float('inf'), "count": 10}  # > 10.0 km
}

# Disruption Scenarios (DS1-DS10)
DISRUPTION_SCENARIOS = {
    "DS1": {
        "name": "Accident + Congestion + Road Closure",
        "incident_types": ["accident", "roadClosure"],
        "flow_disruption": True,  # Congestion
        "description": "Major accident causing congestion and road closure"
    },
    "DS2": {
        "name": "Construction + Lane Restriction + Congestion",
        "incident_types": ["construction", "laneRestriction"],
        "flow_disruption": True,
        "description": "Construction zone with lane restrictions and traffic backup"
    },
    "DS3": {
        "name": "Accident + Disabled Vehicle + Congestion",
        "incident_types": ["accident", "disabledVehicle"],
        "flow_disruption": True,
        "description": "Accident with disabled vehicle causing congestion"
    },
    "DS4": {
        "name": "Road Closure + Road Hazard + Construction",
        "incident_types": ["roadClosure", "roadHazard", "construction"],
        "flow_disruption": False,
        "description": "Multiple infrastructure-related incidents"
    },
    "DS5": {
        "name": "Congestion + Disabled Vehicle + Lane Restriction",
        "incident_types": ["disabledVehicle", "laneRestriction"],
        "flow_disruption": True,
        "description": "Traffic disruption from disabled vehicle and lane restrictions"
    },
    "DS6": {
        "name": "Accident + Weather + Congestion",
        "incident_types": ["accident", "weather"],
        "flow_disruption": True,
        "description": "Weather-related accident causing congestion"
    },
    "DS7": {
        "name": "Construction + Planned Event + Lane Restriction",
        "incident_types": ["construction", "plannedEvent", "laneRestriction"],
        "flow_disruption": False,
        "description": "Scheduled construction and event causing restrictions"
    },
    "DS8": {
        "name": "Accident + Road Closure + Road Hazard",
        "incident_types": ["accident", "roadClosure", "roadHazard"],
        "flow_disruption": False,
        "description": "Severe accident with road closure and hazards"
    },
    "DS9": {
        "name": "Congestion + Weather + Mass Transit Event",
        "incident_types": ["weather", "massTransit"],
        "flow_disruption": True,
        "description": "Weather affecting traffic and mass transit"
    },
    "DS10": {
        "name": "Accident + Construction + Congestion",
        "incident_types": ["accident", "construction"],
        "flow_disruption": True,
        "description": "Accident at construction zone causing severe congestion"
    }
}

# Severity Levels
SEVERITY_LEVELS = {
    "light": {
        "name": "Light",
        "jam_factor_range": (2.0, 4.0),    # Low congestion
        "severity_range": (0.1, 0.3),       # 10-30% impact
        "closure_probability": 0.0          # No road closures
    },
    "medium": {
        "name": "Medium",
        "jam_factor_range": (4.0, 7.0),    # Moderate congestion
        "severity_range": (0.3, 0.6),       # 30-60% impact
        "closure_probability": 0.1          # 10% chance of closure
    },
    "heavy": {
        "name": "Heavy",
        "jam_factor_range": (7.0, 10.0),   # Severe congestion
        "severity_range": (0.6, 1.0),       # 60-100% impact
        "closure_probability": 0.3          # 30% chance of closure
    }
}

# Preset Configurations
EXPERIMENT_PRESETS = {
    PRESET_STANDARD: {
        "name": "Standard Experiment (3×3×1000)",
        "description": "3 trials × 3 batches × 1000 routes = 9,000 simulations per algorithm",
        "trials": 3,
        "batches_per_trial": 3,
        "routes_per_batch": 1000,
        "total_simulations": 9000,  # per algorithm
        "route_generation": "random",  # Random route generation
        "disruption_generation": "random"  # Random disruption generation
    },
    PRESET_SCENARIO: {
        "name": "Scenario Experiment (10×10×3×3)",
        "description": "3 categories × 10 routes × 10 scenarios × 3 severity levels = 900 simulations per algorithm",
        "trials": 3,              # 3 route categories (short, medium, long) - each handled by a thread
        "batches_per_trial": 30,  # 10 scenarios × 3 severity levels = 30 disruption cases per route
        "routes_per_batch": 10,   # 10 routes per category
        "routes_per_category": 10,  # Routes per category (short/medium/long)
        "scenarios_per_route": 10,  # DS1-DS10
        "severity_levels": 3,       # Light, Medium, Heavy
        "total_simulations": 900,   # 3 × 10 × 10 × 3 per algorithm
        "route_generation": "by_distance",  # Routes categorized by HC2L distance
        "disruption_generation": "scenario"  # Specific scenario-based disruptions
    }
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_route_log_entry(
    api_result: Dict,
    trial_id: int,
    batch_id: int,
    query_id: int,
    disruption_data: Optional[Dict] = None,
    tolerance: float = DEFAULT_TOLERANCE
) -> RouteMetricsRecord:
    """
    Create a complete route log entry with accuracy validation.
    
    Records both accuracy and performance metrics:
    1. Extract distances from API result
    2. Compute accuracy metrics
    3. Extract performance metrics (always recorded)
    
    Args:
        api_result: Result from HC2L/HC2L C++ API call
        trial_id: Current trial number (1-indexed)
        batch_id: Current batch number (1-indexed)
        query_id: Current query/route number (1-indexed)
        disruption_data: Optional disruption data for incident summary
        tolerance: Accuracy tolerance (default 0.10 = 10%)
        
    Returns:
        Complete RouteMetricsRecord with accuracy and performance
    """
    # Initialize record
    record = RouteMetricsRecord(
        trial_id=trial_id,
        batch_id=batch_id,
        query_id=query_id,
        algorithm="HC2L",
        disruption_level=get_disruption_level(batch_id),
        timestamp=datetime.now().isoformat()
    )
    
    # Check for API errors
    if not api_result.get("success", False):
        record.error = api_result.get("error", "Unknown API error")
        return record
    
    # Extract node information
    gps_mapping = api_result.get("gps_mapping", {})
    record.source_node = gps_mapping.get("start_node", 0)
    record.target_node = gps_mapping.get("dest_node", 0)
    
    # Get incident summary
    if disruption_data:
        record.incident_summary = IncidentSummary.from_disruption_data(disruption_data)
    
    # STEP 1: Extract distances for accuracy computation
    metrics = api_result.get("metrics", {})
    
    # HC2L distance: Use calculated_distance_meters (path-based distance)
    dhc2l_distance = float(metrics.get("calculated_distance_meters", 0))
    
    # Dijkstra distance: Use dijkstra_distance_meter (actual Dijkstra shortest path)
    dijkstra_distance = float(metrics.get("dijkstra_distance_meter", 0))
    
    # STEP 2: Compute accuracy metrics
    record.accuracy = compute_accuracy(dhc2l_distance, dijkstra_distance, tolerance)
    
    # STEP 3: Performance recording (always recorded)
    from experiment_metrics_collector import PerformanceMetrics, ConstructionMetrics
    
    summary = api_result.get("summary", {})
    query_phase = api_result.get("query_phase", {})
    update_phase = api_result.get("update_phase", {})
    
    record.performance.query_response_time_ms = float(query_phase.get("query_time_ms", 0) or 
                                                      summary.get("query_time_ms", 0) or 0)
    record.performance.labeling_size_mb = float(summary.get("label_size", 0) or 0)
    record.performance.lazy_update_time_ms = float(update_phase.get("lazy_update_time_ms", 0) or 0)
    record.performance.threshold_rebuild_time_ms = float(update_phase.get("threshold_rebuild_time_ms", 0) or 0)
    record.performance.peak_label_size_mb = float(summary.get("peak_label_size_mb", 
                                                              record.performance.labeling_size_mb) or 0)
    
    # Extract labeling time from construction info or labeling info
    construction_info = api_result.get("construction_info", {})
    labeling_info = metrics.get("labeling_info", {})
    
    if "construction_time_ms" in construction_info:
        record.performance.labeling_time_ms = float(construction_info["construction_time_ms"])
    elif "index_load_time_ms" in labeling_info:
        record.performance.labeling_time_ms = float(labeling_info["index_load_time_ms"])
    elif "construction_time_ms" in labeling_info:
        record.performance.labeling_time_ms = float(labeling_info["construction_time_ms"])
    
    # Extract construction metrics for first route
    if query_id == 1:
        construction_time = float(construction_info.get("construction_time_ms", 0) or 0)
        initial_label_size = float(construction_info.get("label_size_mb", 0) or 
                                  summary.get("label_size", 0) or 0)
        
        record.construction = ConstructionMetrics(
            initial_construction_time_ms=construction_time,
            initial_label_size_mb=initial_label_size
        )
    
    # Extract execution time
    record.execution_time_ms = float(api_result.get("execution_time_ms", 0) or 0)
    
    return record


# ============================================================================
# DATA CLASSES FOR EXPERIMENT STATE
# ============================================================================

@dataclass
class ThreadProgress:
    """Progress tracking for a single thread"""
    thread_id: str
    trial_number: str = "0/0"  # Format: X/Y
    batch_number: str = ""  # Format: X/Y or empty
    route_progress: str = "0/0"  # Format: X/Y
    algorithm: str = ""
    status: str = "not_started"  # running/paused/completed/error
    percentage: float = 0.0
    current_disruption: str = ""
    current_disruption_level: str = ""  # "Light", "Medium", "Heavy" for variety_preset
    current_route_index: int = 0
    total_routes: int = 0
    routes_per_minute: float = 0.0
    estimated_time_remaining: str = ""
    last_result: Dict = field(default_factory=dict)
    update_phase: Dict = field(default_factory=dict)
    query_phase: Dict = field(default_factory=dict)
    results_history: List[Dict] = field(default_factory=list)
    error_message: str = ""
    # Performance stats for current batch
    avg_query_time_ms: float = 0.0
    avg_labeling_time_ms: float = 0.0
    avg_labeling_size_mb: float = 0.0
    successful_routes: int = 0
    failed_routes: int = 0


@dataclass
class ExperimentProgress:
    """Overall experiment progress tracking"""
    experiment_id: str
    experiment_name: str = ""
    status: str = "initializing"  # initializing/running/paused/finalizing/completed/error/stopped
    overall_percentage: float = 0.0
    total_routes: int = 0
    completed_routes: int = 0
    estimated_time_remaining: str = ""
    finalization_phase: str = ""  # Status message during finalization
    finalization_percentage: float = 0.0  # Progress within finalization (0-10% of total)
    start_time: float = 0.0
    end_time: float = 0.0
    thread_count: int = 3
    threads: Dict[str, ThreadProgress] = field(default_factory=dict)
    disruption_display: Dict = field(default_factory=lambda: {
        "show_incidents": True,
        "show_flow": True,
        "current_disruptions": [],
        "total_count": 0
    })
    # HERE comparison thread progress
    here_comparison: Dict = field(default_factory=lambda: {
        "status": "not_started",
        "completed": 0,
        "total": 0,
        "current_route": 0,
        "errors": 0
    })
    error_message: str = ""
    results_path: Optional[Path] = None  # Path for saving progress (not serialized)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert ThreadProgress objects to dicts
        data['threads'] = {k: asdict(v) if hasattr(v, '__dict__') else v 
                          for k, v in self.threads.items()}
        # Remove non-serializable fields
        data.pop('results_path', None)
        return data



# ============================================================================
# DISRUPTION CACHE MANAGER
# ============================================================================

class DisruptionCacheManager:
    """
    Manages lazy loading AND generation of disruption files with FIFO cache eviction.
    
    Features:
    - Lazy loading: Load disruptions only when needed
    - Lazy generation: Generate disruptions on-demand if not exists
    - Chunk-based loading: 100 files per chunk (10 chunks of 100)
    - FIFO eviction: Remove oldest chunks when memory limit reached
    - Pre-loading: Load next chunk at 80% completion of current
    - Progress tracking: Emit WebSocket updates during generation
    """
    
    CHUNK_SIZE = 100  # Disruption files per chunk
    MAX_CHUNKS_PER_THREAD = 10  # Max chunks to keep in memory per thread
    PRELOAD_THRESHOLD = 0.8  # Preload next chunk at 80% completion
    GENERATION_BATCH_SIZE = 10  # Generate disruptions in batches of 10
    
    def __init__(self, base_path: Path, is_preset: bool = True, disruption_mode: str = "preset", disruption_settings: Dict = None):
        self.base_path = base_path
        self.is_preset = is_preset
        self.disruption_mode = disruption_mode  # "preset", "variety_preset", "scenario", or "random"
        self.disruption_settings = disruption_settings or {
            "ratio_flow": 95,
            "ratio_incident": 5,
            "severity_min": 0.1,
            "severity_max": 0.9
        }
        self.cache: OrderedDict[str, Dict] = OrderedDict()  # FIFO cache
        self.loaded_chunks: Dict[str, List[int]] = {}  # Track loaded chunk ranges per thread
        self.generation_status: Dict[str, str] = {}  # Track generation status per disruption set
        self.lock = threading.Lock()
        self.generation_lock = threading.Lock()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "generated": 0,
            "memory_usage_mb": 0
        }
        # Pre-load matched edges for faster disruption generation
        self._matched_edges_cache = None
        
    def _get_matched_edges(self) -> List[Dict]:
        """Get cached matched edges for disruption generation"""
        if self._matched_edges_cache is not None:
            return self._matched_edges_cache
        
        try:
            from road_network_utils import _get_available_matched_edges
            self._matched_edges_cache = _get_available_matched_edges()
            return self._matched_edges_cache
        except Exception as e:
            logger.error(f"Failed to load matched edges: {e}")
            return []
    
    def _get_disruption_level_params(self, batch_idx: int) -> Dict:
        """
        Get disruption parameters based on variety_preset level.
        
        Disruption Levels:
        - Light (batch 0): speed > 20 km/h, jam factor ≤ 3, open roads
        - Medium (batch 1): speed 5-20 km/h, jam factor 4-6, open roads
        - Heavy (batch 2): speed < 5 km/h OR jam factor > 6 OR closed roads
        
        Returns dict with speed_range, jam_factor_range, allow_closure, closure_prob
        """
        if self.disruption_mode == "scenario":
            # Scenario preset mode - determine severity level by batch index
            severity_idx = batch_idx % 3  # 0=light, 1=medium, 2=heavy
            severity_levels = {
                0: {  # Light
                    "speed_min": 30,
                    "speed_max": 60,
                    "jam_factor_min": 0,
                    "jam_factor_max": 2,
                    "allow_closure": False,
                    "closure_prob": 0,
                    "severity_range": (0.1, 0.3)
                },
                1: {  # Medium
                    "speed_min": 15,
                    "speed_max": 30,
                    "jam_factor_min": 2,
                    "jam_factor_max": 5,
                    "allow_closure": False,
                    "closure_prob": 0.1,
                    "severity_range": (0.3, 0.6)
                },
                2: {  # Heavy
                    "speed_min": 5,
                    "speed_max": 15,
                    "jam_factor_min": 5,
                    "jam_factor_max": 10,
                    "allow_closure": True,
                    "closure_prob": 0.3,
                    "severity_range": (0.6, 0.9)
                }
            }
            return severity_levels[severity_idx]
        
        if self.disruption_mode != "variety_preset":
            # Use standard severity range from settings
            severity_min = self.disruption_settings.get("severity_min", 0.1)
            severity_max = self.disruption_settings.get("severity_max", 0.9)
            return {
                "severity_range": (severity_min, severity_max),
                "allow_closure": severity_max > 0.8,
                "closure_prob": 0.1 if severity_max > 0.8 else 0
            }
        
        # Variety preset mode - determine level by batch index
        level = batch_idx % 3  # 0=light, 1=medium, 2=heavy
        
        if level == 0:  # Light
            return {
                "speed_min": 21,
                "speed_max": 60,
                "jam_factor_min": 0,
                "jam_factor_max": 3,
                "allow_closure": False,
                "closure_prob": 0,
                "severity_range": (0.0, 0.3)
            }
        elif level == 1:  # Medium
            return {
                "speed_min": 5,
                "speed_max": 20,
                "jam_factor_min": 4,
                "jam_factor_max": 6,
                "allow_closure": False,
                "closure_prob": 0,
                "severity_range": (0.3, 0.6)
            }
        else:  # Heavy (level == 2)
            return {
                "speed_min": 1,
                "speed_max": 5,
                "jam_factor_min": 6,
                "jam_factor_max": 10,
                "allow_closure": True,
                "closure_prob": 0.3,  # 30% chance of road closure
                "severity_range": (0.6, 1.0)
            }
        
    def get_disruption_path(self, batch_idx: int, route_idx: int) -> Path:
        """Get path to disruption set based on preset/temporary mode and disruption_mode"""
        if self.disruption_mode == "variety_preset":
            # Variety preset: Use light/medium/heavy based on batch index
            level_names = ["light", "medium", "heavy"]
            level = level_names[batch_idx % 3]  # Cycle through levels for batches
            set_name = f"set_{level}_route_{route_idx}"
        elif self.disruption_mode == "scenario":
            # Scenario preset: Format is set_scenario_ds{num}_{severity}_route_{idx}
            # batch_idx encodes: scenario (0-9) * 3 + severity (0=light, 1=medium, 2=heavy)
            scenario_idx = batch_idx // 3
            severity_idx = batch_idx % 3
            scenario_num = scenario_idx + 1  # DS1 to DS10
            severity_names = ["light", "medium", "heavy"]
            severity = severity_names[severity_idx]
            set_name = f"set_scenario_ds{scenario_num}_{severity}_route_{route_idx}"
        elif self.is_preset:
            # Preset format: set_batch_X_route_Y
            set_name = f"set_batch_{batch_idx}_route_{route_idx}"
        else:
            # Temporary format: set_trial_X_route_Y
            set_name = f"set_trial_{batch_idx}_route_{route_idx}"
        return self.base_path / "disruptions" / set_name
    
    def load_disruption(self, batch_idx: int, route_idx: int, thread_id: str) -> Optional[Dict]:
        """
        Load a single disruption set, using cache if available.
        If disruption doesn't exist, generate it on-demand.
        
        Args:
            batch_idx: Batch/Trial index
            route_idx: Route index within batch
            thread_id: Thread requesting the disruption
            
        Returns:
            Dict with flow and incidents data, or None if not found
        """
        cache_key = f"{batch_idx}_{route_idx}"
        
        with self.lock:
            # Check cache first
            if cache_key in self.cache:
                self.stats["hits"] += 1
                # Move to end (most recently used)
                self.cache.move_to_end(cache_key)
                return self.cache[cache_key]
            
            self.stats["misses"] += 1
        
        # Check if disruption path exists
        disruption_path = self.get_disruption_path(batch_idx, route_idx)
        
        if not disruption_path.exists():
            # Generate disruption on-demand
            logger.info(f"Generating disruption on-demand: batch={batch_idx}, route={route_idx}")
            self._generate_single_disruption(batch_idx, route_idx)
        
        # Load from disk
        if not disruption_path.exists():
            logger.warning(f"Failed to generate disruption: {disruption_path}")
            return None
        
        disruption_data = self._load_disruption_files(disruption_path)
        
        # Compute batch-level incident summary
        incident_summary = self._compute_batch_incident_summary(disruption_path)
        disruption_data["incident_summary"] = incident_summary
        
        with self.lock:
            # Add to cache
            self.cache[cache_key] = disruption_data
            
            # Evict if needed (FIFO)
            while len(self.cache) > self.MAX_CHUNKS_PER_THREAD * 10:  # Rough limit
                evicted_key, _ = self.cache.popitem(last=False)
                self.stats["evictions"] += 1
                logger.debug(f"Evicted disruption cache: {evicted_key}")
        
        return disruption_data
    
    def _generate_single_disruption(self, batch_idx: int, route_idx: int):
        """Generate a single disruption set with flow and incident data"""
        import csv
        import random
        from datetime import datetime, timedelta
        
        disruption_path = self.get_disruption_path(batch_idx, route_idx)
        
        with self.generation_lock:
            # Double-check after acquiring lock
            if disruption_path.exists():
                return
            
            flow_dir = disruption_path / "flow"
            incident_dir = disruption_path / "incidents"
            flow_dir.mkdir(parents=True, exist_ok=True)
            incident_dir.mkdir(parents=True, exist_ok=True)
            
            # Get disruption level parameters (variety_preset or standard)
            level_params = self._get_disruption_level_params(batch_idx)
            
            # Get settings
            ratio_flow = self.disruption_settings.get("ratio_flow", 95)
            ratio_incident = self.disruption_settings.get("ratio_incident", 5)
            
            # For scenario mode, check if flow disruption should be generated
            if self.disruption_mode == "scenario":
                scenario_idx = batch_idx // 3
                scenario_id = f"DS{scenario_idx + 1}"
                scenario_def = DISRUPTION_SCENARIOS.get(scenario_id, {})
                has_flow_disruption = scenario_def.get("flow_disruption", False)
                if not has_flow_disruption:
                    # Only generate incidents, no flow disruptions
                    ratio_flow = 0
                    ratio_incident = 100
            
            # Get edges for disruption generation
            edges = self._get_matched_edges()
            if not edges:
                logger.warning("No matched edges available for disruption generation")
                return
            
            # Calculate counts based on ratio (total should be 1000 disruptions per batch)
            total_disruptions = 1000
            total_ratio = ratio_flow + ratio_incident
            flow_count = int((ratio_flow / total_ratio) * total_disruptions)
            incident_count = total_disruptions - flow_count
            
            # Ensure we don't exceed available edges
            available_edges = len(edges)
            if total_disruptions > available_edges:
                logger.warning(f"Requested {total_disruptions} disruptions but only {available_edges} edges available")
                # Scale down proportionally
                scale = available_edges / total_disruptions
                flow_count = int(flow_count * scale)
                incident_count = available_edges - flow_count
            
            timestamp = datetime.now().strftime('%Y%m%dT%H%M%S%f')[:18]
            
            # Generate flow disruptions
            flow_rows = []
            used_edges = set()
            random.shuffle(edges)
            
            for i, edge in enumerate(edges):
                if len(flow_rows) >= flow_count:
                    break
                
                edge_key = (edge.get('source'), edge.get('target'))
                if edge_key in used_edges:
                    continue
                used_edges.add(edge_key)
                
                # Use level_params for variety_preset mode or scenario mode
                if self.disruption_mode == "variety_preset" or self.disruption_mode == "scenario":
                    # Generate speed and jam factor based on level
                    flow_speed = random.uniform(level_params['speed_min'], level_params['speed_max'])
                    jam_factor = random.uniform(level_params['jam_factor_min'], level_params['jam_factor_max'])
                    free_flow_kph = float(edge.get('free_flow_speed', 60))
                else:
                    # Standard mode: use severity range
                    severity_min, severity_max = level_params['severity_range']
                    severity = random.uniform(severity_min, severity_max)
                    jam_factor = severity * 10  # 0-10 scale
                    free_flow_kph = float(edge.get('free_flow_speed', 60))
                    flow_speed = max(5.0, free_flow_kph * (1.0 - (jam_factor / 10.0)))
                
                flow_rows.append({
                    'id_hash': edge.get('id_hash', f'exp_{batch_idx}_{route_idx}_{i}'),
                    'source_lat': edge.get('source_lat'),
                    'source_lon': edge.get('source_lon'),
                    'target_lat': edge.get('target_lat'),
                    'target_lon': edge.get('target_lon'),
                    'source': edge.get('source'),
                    'target': edge.get('target'),
                    'flow_speed_kph': round(flow_speed, 2),
                    'flow_free_flow_kph': round(free_flow_kph, 2),
                    'flow_jam_factor': round(jam_factor, 2),
                    'flow_confidence': round(0.7 + random.uniform(0, 0.25), 2),
                    'flow_traversability': 'open',
                    'highway_type': edge.get('highway_type', 'primary'),
                    'road_name': edge.get('road_name', 'Unknown Road')
                })
            
            # Generate incident disruptions
            incident_rows = []
            
            # Get incident types based on disruption mode
            if self.disruption_mode == "scenario":
                # Get scenario from batch_idx
                scenario_idx = batch_idx // 3
                scenario_id = f"DS{scenario_idx + 1}"
                scenario_def = DISRUPTION_SCENARIOS.get(scenario_id, {})
                incident_types = scenario_def.get("incident_types", ["accident", "roadHazard"])
            else:
                # Standard incident types for non-scenario modes
                incident_types = [
                    "accident", 
                    "construction", 
                    "disabledVehicle", 
                    "massTransit", 
                    "plannedEvent", 
                    "roadHazard", 
                    "weather", 
                    "laneRestriction", 
                    "other",
                ]
            
            for edge in edges:
                if len(incident_rows) >= incident_count:
                    break
                
                edge_key = (edge.get('source'), edge.get('target'))
                if edge_key in used_edges:
                    continue
                used_edges.add(edge_key)
                
                # Determine incident properties based on level_params
                if self.disruption_mode == "variety_preset" or self.disruption_mode == "scenario":
                    severity_min, severity_max = level_params['severity_range']
                    severity = random.uniform(severity_min, severity_max)
                    # Determine if road should be closed
                    road_closed = level_params['allow_closure'] and random.random() < level_params['closure_prob']
                else:
                    severity_min, severity_max = level_params['severity_range']
                    severity = random.uniform(severity_min, severity_max)
                    road_closed = level_params['allow_closure'] and severity > 0.8
                
                # Convert severity to jam_factor (0-10 scale)
                jam_factor = severity * 10
                
                # Determine criticality based on severity
                if severity > 0.7:
                    criticality = 'critical'
                elif severity > 0.4:
                    criticality = 'major'
                else:
                    criticality = 'minor'
                
                # Select incident type based on jam_factor
                # Jam Factor Ranges by Incident Type (matching C++ API and system standard):
                # - roadClosure: 9.5-10.0 (critical - impassable)
                # - accident: 5.0-9.0 (high severity)
                # - roadHazard: 4.0-7.0 (high-medium severity)
                # - construction: 2.5-5.0 (medium severity)
                # - disabledVehicle: 2.0-4.0 (medium-low severity)
                # - laneRestriction: 2.0-4.0 (medium-low severity)
                # - weather: 1.5-4.0 (low-medium severity)
                # - plannedEvent: 1.5-3.0 (low-medium severity)
                # - massTransit: 1.2-2.5 (low severity)
                # - other: 1.3-3.0 (low-medium severity)
                if jam_factor >= 9.5 and criticality == 'major':
                    incident_type = 'roadClosure'
                else:
                    incident_type = random.choice(incident_types)
                
                incident_rows.append({
                    'source': edge.get('source'),
                    'target': edge.get('target'),
                    'source_lat': edge.get('source_lat'),
                    'source_lon': edge.get('source_lon'),
                    'target_lat': edge.get('target_lat'),
                    'target_lon': edge.get('target_lon'),
                    'incident_id': edge.get('id_hash', f'exp_{batch_idx}_{route_idx}_{len(incident_rows)}'),
                    'incident_type': incident_type,
                    'incident_criticality': criticality,
                    'incident_description': f'Experiment incident on {edge.get("road_name", "Unknown Road")}',
                    'incident_road_closed': road_closed,
                    'incident_start_time': datetime.now().isoformat() + 'Z',
                    'incident_end_time': (datetime.now() + timedelta(hours=3)).isoformat() + 'Z',
                    'highway_type': edge.get('highway_type', 'primary'),
                    'road_name': edge.get('road_name', 'Unknown Road')
                })
            
            # Write flow CSV
            flow_file = flow_dir / f'flow_{timestamp}.csv'
            if flow_rows:
                with open(flow_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=flow_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(flow_rows)
            else:
                with open(flow_file, 'w', newline='') as f:
                    f.write('id_hash,source_lat,source_lon,target_lat,target_lon,source,target,flow_speed_kph,flow_free_flow_kph,flow_jam_factor,flow_confidence,flow_traversability,highway_type,road_name\n')
            
            # Write incident CSV
            incident_file = incident_dir / f'incident_{timestamp}.csv'
            if incident_rows:
                with open(incident_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=incident_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(incident_rows)
            else:
                with open(incident_file, 'w', newline='') as f:
                    f.write('source,target,source_lat,source_lon,target_lat,target_lon,incident_id,incident_type,incident_criticality,incident_description,incident_road_closed,incident_start_time,incident_end_time,highway_type,road_name\n')
            
            self.stats["generated"] += 1
            logger.debug(f"Generated disruption set: {disruption_path.name} ({len(flow_rows)} flow, {len(incident_rows)} incidents)")
    
    def generate_chunk(self, batch_idx: int, start_route: int, count: int = None, 
                      progress_callback: Callable = None) -> int:
        """
        Generate a chunk of disruption sets in batch.
        This is used for pre-generating disruptions in 10-chunk batches.
        
        Args:
            batch_idx: Batch/Trial index
            start_route: Starting route index
            count: Number of disruptions to generate (default: CHUNK_SIZE)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Number of disruptions generated
        """
        if count is None:
            count = self.CHUNK_SIZE
        
        generated = 0
        for i in range(count):
            route_idx = start_route + i
            disruption_path = self.get_disruption_path(batch_idx, route_idx)
            
            if not disruption_path.exists():
                self._generate_single_disruption(batch_idx, route_idx)
                generated += 1
            
            if progress_callback and (i + 1) % self.GENERATION_BATCH_SIZE == 0:
                progress_callback(i + 1, count)
        
        logger.info(f"Generated chunk: batch={batch_idx}, routes={start_route}-{start_route + count - 1}, new={generated}")
        return generated
    
    def _load_disruption_files(self, disruption_path: Path) -> Dict:
        """Load flow and incident CSV files from disruption directory"""
        import csv
        
        result = {
            "flow": [],
            "incidents": [],
            "path": str(disruption_path)
        }
        
        flow_dir = disruption_path / "flow"
        incident_dir = disruption_path / "incidents"
        
        # Load flow files
        if flow_dir.exists():
            for flow_file in sorted(flow_dir.glob("flow_*.csv")):
                try:
                    with open(flow_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            result["flow"].append({
                                "source": int(row.get("source", 0)),
                                "target": int(row.get("target", 0)),
                                "source_lat": float(row.get("source_lat", 0)),
                                "source_lon": float(row.get("source_lon", 0)),
                                "target_lat": float(row.get("target_lat", 0)),
                                "target_lon": float(row.get("target_lon", 0)),
                                "jam_factor": float(row.get("flow_jam_factor", 0)),
                                "speed_kph": float(row.get("flow_speed_kph", 0)),
                                "free_flow_kph": float(row.get("flow_free_flow_kph", 60))
                            })
                except Exception as e:
                    logger.error(f"Error loading flow file {flow_file}: {e}")
        
        # Load incident files
        if incident_dir.exists():
            for incident_file in sorted(incident_dir.glob("incident_*.csv")):
                try:
                    with open(incident_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            criticality_map = {"minor": 1, "major": 2, "critical": 3}
                            result["incidents"].append({
                                "source": int(row.get("source", 0)),
                                "target": int(row.get("target", 0)),
                                "source_lat": float(row.get("source_lat", 0)),
                                "source_lon": float(row.get("source_lon", 0)),
                                "target_lat": float(row.get("target_lat", 0)),
                                "target_lon": float(row.get("target_lon", 0)),
                                "incident_type": row.get("incident_type", "unknown"),
                                "criticality": criticality_map.get(row.get("incident_criticality", "minor"), 1),
                                "road_closed": str(row.get("incident_road_closed", "false")).lower() == "true"
                            })
                except Exception as e:
                    logger.error(f"Error loading incident file {incident_file}: {e}")
        
        return result
    
    def _compute_batch_incident_summary(self, disruption_path: Path) -> Dict:
        """
        Analyze disruption files and compute batch-level incident statistics.
        
        Returns dict with incident counts:
        - num_incidents_total: Total number of incidents
        - num_closures: Number of road closures
        - num_slowdowns: Number of slowdown incidents (from flow data)
        - num_accidents: Number of accidents
        - num_construction: Number of construction incidents
        - num_hazards: Number of hazard incidents
        - num_other_incidents: Number of other/unknown incidents
        """
        import csv
        
        summary = {
            "num_incidents_total": 0,
            "num_closures": 0,
            "num_slowdowns": 0,
            "num_accidents": 0,
            "num_construction": 0,
            "num_hazards": 0,
            "num_other_incidents": 0,
            "disruption_level": "unknown",
            "avg_jam_factor": 0.0,
            "num_disrupted_edges": 0
        }
        
        # Determine disruption level from path
        path_str = str(disruption_path)
        if "set_light_" in path_str:
            summary["disruption_level"] = "light"
        elif "set_medium_" in path_str:
            summary["disruption_level"] = "medium"
        elif "set_heavy_" in path_str:
            summary["disruption_level"] = "heavy"
        elif "set_batch_" in path_str:
            # Extract from preset naming
            summary["disruption_level"] = "preset"
        else:
            summary["disruption_level"] = "random"
        
        # Count incidents from incident files
        incident_dir = disruption_path / "incidents"
        if incident_dir.exists():
            for incident_file in sorted(incident_dir.glob("incident_*.csv")):
                try:
                    with open(incident_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            summary["num_incidents_total"] += 1
                            
                            # Categorize by type
                            incident_type = row.get("incident_type", "unknown").lower()
                            if incident_type == "accident":
                                summary["num_accidents"] += 1
                            elif incident_type == "construction":
                                summary["num_construction"] += 1
                            elif incident_type == "hazard":
                                summary["num_hazards"] += 1
                            elif incident_type == "roadclosure":
                                summary["num_closures"] += 1
                            else:
                                summary["num_other_incidents"] += 1
                            
                            # Check for road closure flag
                            road_closed = str(row.get("incident_road_closed", "false")).lower() == "true"
                            if road_closed:
                                summary["num_closures"] += 1  # Count both type and flag
                                
                except Exception as e:
                    logger.error(f"Error reading incident file {incident_file}: {e}")
        
        # Count slowdowns from flow files (jam_factor >= 4 or speed < 20 km/h)
        # Also compute average jam_factor across all disrupted edges
        flow_dir = disruption_path / "flow"
        jam_factor_sum = 0.0
        jam_factor_count = 0
        
        if flow_dir.exists():
            for flow_file in sorted(flow_dir.glob("flow_*.csv")):
                try:
                    with open(flow_file, 'r') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            jam_factor = float(row.get("flow_jam_factor", 0))
                            speed_kph = float(row.get("flow_speed_kph", 60))
                            
                            # Accumulate jam_factor for average
                            if jam_factor > 0:
                                jam_factor_sum += jam_factor
                                jam_factor_count += 1
                                summary["num_disrupted_edges"] += 1
                            
                            # Count as slowdown if significant congestion
                            if jam_factor >= 4 or speed_kph < 20:
                                summary["num_slowdowns"] += 1
                                
                except Exception as e:
                    logger.error(f"Error reading flow file {flow_file}: {e}")
        
        # Calculate average jam_factor
        if jam_factor_count > 0:
            summary["avg_jam_factor"] = round(jam_factor_sum / jam_factor_count, 2)
        
        return summary
    
    def preload_chunk(self, batch_idx: int, start_route: int, thread_id: str):
        """Pre-load a chunk of disruptions asynchronously (generates if needed)"""
        def _load():
            for i in range(self.CHUNK_SIZE):
                route_idx = start_route + i
                self.load_disruption(batch_idx, route_idx, thread_id)
        
        threading.Thread(target=_load, daemon=True).start()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self.lock:
            hit_rate = (self.stats["hits"] / max(1, self.stats["hits"] + self.stats["misses"])) * 100
            return {
                **self.stats,
                "hit_rate_percent": round(hit_rate, 2),
                "cached_items": len(self.cache)
            }
    
    def clear(self):
        """Clear all cached disruptions"""
        with self.lock:
            self.cache.clear()
            self.loaded_chunks.clear()
            self.stats = {"hits": 0, "misses": 0, "evictions": 0, "memory_usage_mb": 0}


# ============================================================================
# EXPERIMENT RUNNER ENGINE
# ============================================================================

class ExperimentRunner:
    """
    Main experiment execution engine with multi-threading support.
    
    Features:
    - Configurable thread count (3 default, 9 advanced)
    - Per-thread progress tracking
    - WebSocket real-time updates
    - Graceful pause/resume/stop
    - Numpy-based metrics collection for efficient computation
    """
    
    def __init__(self, socketio: SocketIO = None):
        self.socketio = socketio
        self.experiments: Dict[str, ExperimentProgress] = {}
        self.experiment_threads: Dict[str, List[threading.Thread]] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.pause_events: Dict[str, threading.Event] = {}
        self.disruption_caches: Dict[str, DisruptionCacheManager] = {}
        
        # Metrics collectors for each experiment (numpy-based)
        self.metrics_collectors: Dict[str, ExperimentMetricsCollector] = {}
        
        # Dijkstra ground truth cache (for accuracy validation)
        # Key: f"{experiment_id}_{batch_idx}_{route_idx}_{disruption_path_hash}"
        # Value: {"distance_km": float, "computed_at": timestamp}
        self.dijkstra_cache: Dict[str, Dict] = {}
        self.dijkstra_cache_lock = threading.Lock()
        
        # Completion locks and tracking
        self.completion_locks: Dict[str, threading.Lock] = {}
        self.completed_threads: Dict[str, set] = {}
        
        # Ensure data directories exist
        self.preset_path = Path(Config.DATA_DIR) / "experiments" / "preset"
        self.temporary_path = Path(Config.DATA_DIR) / "experiments" / "temporary"
        self.preset_path.mkdir(parents=True, exist_ok=True)
        self.temporary_path.mkdir(parents=True, exist_ok=True)
        
        # Auto-create ExperimentPreset.json if it doesn't exist
        self._ensure_preset_config()
        
        # Router references (will be set by init function)
        self.hc2l_router = None
        self.dhl_router = None
        self.node_mapper = None
        
        # Road name mapper for getting edge information
        try:
            self.road_mapper = RoadNameMapper(str(Config.EDGES_CSV))
        except Exception as e:
            logger.warning(f"Failed to initialize RoadNameMapper: {e}")
            self.road_mapper = None
        
        logger.success("ExperimentRunner initialized")
        logger.info(f"Preset path: {self.preset_path}")
        logger.info(f"Temporary path: {self.temporary_path}")
    
    def _ensure_preset_config(self, experiment_id: str = None, route_mode: str = "preset", preset_type: str = None):
        """Ensure preset configuration exists based on route_mode and preset_type"""
        if preset_type == PRESET_SCENARIO:
            self._ensure_scenario_preset_config(experiment_id)
        elif route_mode == "same_batch_preset":
            self._ensure_same_batch_preset_config(experiment_id)
        else:
            self._ensure_different_batch_preset_config(experiment_id)
    
    def _ensure_different_batch_preset_config(self, experiment_id: str = None):
        """Ensure ExperimentPreset.json exists with default configuration and pre-generated routes"""
        preset_file = self.preset_path / "ExperimentPreset.json"
        
        if preset_file.exists():
            logger.info("ExperimentPreset.json already exists")
            # Send loading progress
            if experiment_id:
                self._emit_preset_progress(experiment_id, "loading", "Loading preset configuration...", 25)
                self._emit_preset_progress(experiment_id, "loading_complete", "Preset loaded successfully", 100)
            return
        
        logger.info("Creating default ExperimentPreset.json with 3000 pre-generated routes...")
        
        # Send creating progress
        if experiment_id:
            self._emit_preset_progress(experiment_id, "creating", "Generating preset configuration...", 10)
        
        # Generate 3000 routes with full snap data (1000 per batch × 3 batches)
        routes = self._generate_preset_routes(3000, experiment_id)
        
        if not routes:
            logger.error("Failed to generate preset routes")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "error", "Failed to generate preset routes", 0)
            return
        
        # Create default preset configuration with routes
        default_preset = {
            "id": "default",
            "name": "Default Experiment Preset - Different Routes",
            "description": "Default experiment configuration with 3 trials, 3 batches, 1000 routes per batch (3000 total, different routes)",
            "generation_mode": "different_batch",
            "algorithms": ["DHL", "HC2L"],
            "trial_count": 3,
            "batch_count": 3,
            "routes_per_batch": 1000,
            "total_routes": 3000,
            "routes": routes,  # Pre-generated routes with full snap data
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat()
        }
        
        try:
            with open(preset_file, 'w') as f:
                json.dump(default_preset, f, indent=2)
            logger.success(f"Created default ExperimentPreset.json with {len(routes)} pre-generated routes")
            
            # Send completion progress
            if experiment_id:
                self._emit_preset_progress(experiment_id, "creating_complete", "Preset created successfully", 100)
        except Exception as e:
            logger.error(f"Failed to create ExperimentPreset.json: {e}")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "error", f"Failed to save preset: {str(e)}", 0)
    
    def _ensure_same_batch_preset_config(self, experiment_id: str = None):
        """Ensure ExperimentPresetSameBatch.json exists with 1000 routes to be reused across all batches"""
        preset_file = self.preset_path / "ExperimentPresetSameBatch.json"
        
        if preset_file.exists():
            logger.info("ExperimentPresetSameBatch.json already exists")
            # Send loading progress
            if experiment_id:
                self._emit_preset_progress(experiment_id, "loading", "Loading same batch preset configuration...", 25)
                self._emit_preset_progress(experiment_id, "loading_complete", "Preset loaded successfully", 100)
            return
        
        logger.info("Creating ExperimentPresetSameBatch.json with 1000 pre-generated routes...")
        
        # Send creating progress
        if experiment_id:
            self._emit_preset_progress(experiment_id, "creating", "Generating same batch preset configuration...", 10)
        
        # Generate 1000 routes with full snap data (to be reused across all batches)
        routes = self._generate_preset_routes(1000, experiment_id)
        
        if not routes:
            logger.error("Failed to generate preset routes")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "error", "Failed to generate preset routes", 0)
            return
        
        # Create same batch preset configuration with routes
        same_batch_preset = {
            "id": "same_batch",
            "name": "Same Batch Preset - Reusable Routes",
            "description": "Experiment configuration with same 1000 routes reused across all batches and trials",
            "generation_mode": "same_batch",
            "algorithms": ["DHL", "HC2L"],
            "trial_count": 3,
            "batch_count": 3,
            "routes_per_batch": 1000,
            "total_routes": 1000,  # Only 1000 unique routes
            "routes": routes,  # Pre-generated routes with full snap data
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat()
        }
        
        try:
            with open(preset_file, 'w') as f:
                json.dump(same_batch_preset, f, indent=2)
            logger.success(f"Created ExperimentPresetSameBatch.json with {len(routes)} pre-generated routes (reusable)")
            
            # Send completion progress
            if experiment_id:
                self._emit_preset_progress(experiment_id, "creating_complete", "Same batch preset created successfully", 100)
        except Exception as e:
            logger.error(f"Failed to create ExperimentPresetSameBatch.json: {e}")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "error", f"Failed to save preset: {str(e)}", 0)
    
    def _ensure_scenario_preset_config(self, experiment_id: str = None):
        """
        Ensure ExperimentPresetScenario.json exists with:
        - 30 routes categorized by distance (10 short, 10 medium, 10 long)
        - Pre-defined disruption scenarios (DS1-DS10)
        - 3 severity levels (Light, Medium, Heavy)
        
        Total: 30 routes × 10 scenarios × 3 severities = 900 simulations per algorithm
        """
        preset_file = self.preset_path / "ExperimentPresetScenario.json"
        
        if preset_file.exists():
            logger.info("ExperimentPresetScenario.json already exists")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "loading", "Loading scenario preset...", 25)
                self._emit_preset_progress(experiment_id, "loading_complete", "Scenario preset loaded", 100)
            return
        
        logger.info("Creating ExperimentPresetScenario.json with distance-categorized routes...")
        
        if not self.hc2l_router:
            logger.error("HC2L router not available for distance calculation")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "error", "HC2L router not available", 0)
            return
        
        if experiment_id:
            self._emit_preset_progress(experiment_id, "creating", "Generating distance-categorized routes...", 10)
        
        # Progress callback for WebSocket updates
        def progress_callback(completed, total, category, distance_km):
            if experiment_id:
                progress_pct = 10 + int((completed / total) * 70)  # 10% to 80%
                self._emit_preset_progress(
                    experiment_id, 
                    "creating", 
                    f"Found {category} route ({distance_km:.1f} km) - {completed}/{total}",
                    progress_pct
                )
        
        # Generate routes by distance category
        categorized_routes = generate_routes_by_distance_category(
            categories=ROUTE_CATEGORIES,
            hc2l_router=self.hc2l_router,
            node_mapper=self.node_mapper,
            progress_callback=progress_callback
        )
        
        # Flatten routes into a list with category info
        all_routes = []
        for category, routes in categorized_routes.items():
            for route in routes:
                route["category"] = category
                all_routes.append(route)
        
        if len(all_routes) < 30:
            logger.warning(f"Only generated {len(all_routes)} routes, expected 30")
        
        if experiment_id:
            self._emit_preset_progress(experiment_id, "creating", "Saving scenario preset...", 90)
        
        # Create scenario preset configuration
        scenario_preset = {
            "id": "scenario",
            "name": "Scenario Experiment (10×10×3×3)",
            "description": "3 categories × 10 routes × 10 scenarios × 3 severities = 900 simulations per algorithm",
            "preset_type": PRESET_SCENARIO,
            "generation_mode": "scenario",
            "algorithms": ["DHL", "HC2L"],
            "trials": 3,  # 3 route categories (short, medium, long) - each handled by a thread
            "routes_per_category": 10,
            "scenarios_per_route": 10,
            "severity_levels": 3,
            "total_simulations": 900,  # per algorithm (3 categories × 10 routes × 10 scenarios × 3 severities)
            "route_categories": {
                "short": {"min_km": 0, "max_km": 5.0, "count": len(categorized_routes.get("short", []))},
                "medium": {"min_km": 5.0, "max_km": 10.0, "count": len(categorized_routes.get("medium", []))},
                "long": {"min_km": 10.0, "max_km": None, "count": len(categorized_routes.get("long", []))}  # null for infinity
            },
            "disruption_scenarios": DISRUPTION_SCENARIOS,
            "severity_levels_config": SEVERITY_LEVELS,
            "routes": all_routes,
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat()
        }
        
        try:
            with open(preset_file, 'w') as f:
                json.dump(scenario_preset, f, indent=2)
            
            logger.success(f"Created ExperimentPresetScenario.json with {len(all_routes)} distance-categorized routes")
            
            if experiment_id:
                self._emit_preset_progress(experiment_id, "creating_complete", "Scenario preset created", 100)
        except Exception as e:
            logger.error(f"Failed to create ExperimentPresetScenario.json: {e}")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "error", f"Failed to save: {str(e)}", 0)
    
    def _generate_scenario_disruption(self, route_idx: int, scenario_id: str, severity_level: str, route_data: Dict) -> Path:
        """
        Generate a specific disruption set for a scenario experiment.
        
        Args:
            route_idx: Route index (0-29)
            scenario_id: Scenario ID (DS1-DS10)
            severity_level: Severity level (light, medium, heavy)
            route_data: Route data with start/end coordinates
            
        Returns:
            Path to the generated disruption directory
        """
        import csv
        import random
        from datetime import timedelta
        
        scenario = DISRUPTION_SCENARIOS.get(scenario_id)
        severity = SEVERITY_LEVELS.get(severity_level)
        
        if not scenario or not severity:
            logger.error(f"Invalid scenario {scenario_id} or severity {severity_level}")
            return None
        
        # Create disruption directory with format: set_scenario_ds*_route_*
        # Extract scenario number from DS1, DS2, etc.
        scenario_num = scenario_id.lower().replace('ds', '')
        set_name = f"set_scenario_ds{scenario_num}_{severity_level}_route_{route_idx}"
        disruption_path = self.preset_path / "disruptions" / set_name
        
        if disruption_path.exists():
            return disruption_path
            
        flow_dir = disruption_path / "flow"
        incident_dir = disruption_path / "incidents"
        flow_dir.mkdir(parents=True, exist_ok=True)
        incident_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Get nearby edges for disruption placement
        if not self.road_mapper:
            logger.error("Road mapper not available")
            return None
        
        # Get edges near the route
        start = route_data.get("start", {})
        end = route_data.get("end", {})
        
        # Sample edges from the network for disruption
        edges = self.road_mapper.get_edges_in_area(
            min_lat=min(start.get("pin_lat", 0), end.get("pin_lat", 0)) - 0.05,
            max_lat=max(start.get("pin_lat", 0), end.get("pin_lat", 0)) + 0.05,
            min_lng=min(start.get("pin_lng", 0), end.get("pin_lng", 0)) - 0.05,
            max_lng=max(start.get("pin_lng", 0), end.get("pin_lng", 0)) + 0.05,
            limit=100
        )
        
        if not edges:
            # Fallback to random edges
            from road_network_utils import _get_available_matched_edges
            all_edges = _get_available_matched_edges()
            edges = random.sample(all_edges, min(100, len(all_edges)))
        
        # Generate flow disruptions if scenario has congestion
        flow_rows = []
        if scenario.get("flow_disruption"):
            jam_min, jam_max = severity["jam_factor_range"]
            for edge in edges[:50]:  # Use up to 50 edges for flow
                jam_factor = random.uniform(jam_min, jam_max)
                free_flow = random.uniform(40, 80)  # km/h
                current_speed = free_flow * (1 - jam_factor / 10)  # Reduced speed
                
                flow_rows.append({
                    'id_hash': edge.get('id_hash', f'flow_{len(flow_rows)}'),
                    'source_lat': edge.get('source_lat'),
                    'source_lon': edge.get('source_lon'),
                    'target_lat': edge.get('target_lat'),
                    'target_lon': edge.get('target_lon'),
                    'source': edge.get('source'),
                    'target': edge.get('target'),
                    'flow_speed_kph': max(5, current_speed),
                    'flow_free_flow_kph': free_flow,
                    'flow_jam_factor': jam_factor,
                    'flow_confidence': random.uniform(0.7, 1.0),
                    'flow_traversability': 'open' if jam_factor < 9 else 'closed',
                    'highway_type': edge.get('highway_type', 'primary'),
                    'road_name': edge.get('road_name', 'Unknown Road')
                })
        
        # Generate incident disruptions based on scenario incident types
        incident_rows = []
        incident_types = scenario.get("incident_types", [])
        sev_min, sev_max = severity["severity_range"]
        closure_prob = severity["closure_probability"]
        
        for i, edge in enumerate(edges[50:]):  # Use remaining edges for incidents
            if i >= len(incident_types) * 5:  # Generate ~5 incidents per type
                break
                
            incident_type = incident_types[i % len(incident_types)]
            incident_severity = random.uniform(sev_min, sev_max)
            
            # Determine criticality
            if incident_severity > 0.7:
                criticality = 'critical'
            elif incident_severity > 0.4:
                criticality = 'major'
            else:
                criticality = 'minor'
            
            # Road closure based on probability and severity
            road_closed = random.random() < closure_prob and incident_severity > 0.5
            
            incident_rows.append({
                'source': edge.get('source'),
                'target': edge.get('target'),
                'source_lat': edge.get('source_lat'),
                'source_lon': edge.get('source_lon'),
                'target_lat': edge.get('target_lat'),
                'target_lon': edge.get('target_lon'),
                'incident_id': f'{scenario_id}_{severity_level}_{route_idx}_{i}',
                'incident_type': incident_type,
                'incident_criticality': criticality,
                'incident_description': f'{scenario["name"]} - {severity["name"]} severity',
                'incident_road_closed': road_closed,
                'incident_start_time': datetime.now().isoformat() + 'Z',
                'incident_end_time': (datetime.now() + timedelta(hours=3)).isoformat() + 'Z',
                'highway_type': edge.get('highway_type', 'primary'),
                'road_name': edge.get('road_name', 'Unknown Road')
            })
        
        # Write flow CSV
        flow_file = flow_dir / f'flow_{timestamp}.csv'
        if flow_rows:
            with open(flow_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=flow_rows[0].keys())
                writer.writeheader()
                writer.writerows(flow_rows)
        else:
            with open(flow_file, 'w', newline='') as f:
                f.write('id_hash,source_lat,source_lon,target_lat,target_lon,source,target,flow_speed_kph,flow_free_flow_kph,flow_jam_factor,flow_confidence,flow_traversability,highway_type,road_name\n')
        
        # Write incident CSV
        incident_file = incident_dir / f'incident_{timestamp}.csv'
        if incident_rows:
            with open(incident_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=incident_rows[0].keys())
                writer.writeheader()
                writer.writerows(incident_rows)
        else:
            with open(incident_file, 'w', newline='') as f:
                f.write('source,target,source_lat,source_lon,target_lat,target_lon,incident_id,incident_type,incident_criticality,incident_description,incident_road_closed,incident_start_time,incident_end_time,highway_type,road_name\n')
        
        logger.debug(f"Generated scenario disruption: {set_name}")
        return disruption_path

    def _generate_preset_routes(self, count, experiment_id=None):
        """
        Generate routes with full snap data for C++ API.
        Uses shared road_network_utils for direct data access (no HTTP calls).
        
        Each route contains: pin coords, snap coords, edge source/target, oneway flag
        
        C++ API format:
        <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> 
        <start_edge_source> <start_edge_target> <start_edge_oneway> 
        <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> 
        <dest_edge_source> <dest_edge_target> <dest_edge_oneway>
        """
        try:
            # Progress callback for WebSocket updates
            def progress_callback(done, total):
                logger.info(f"Route generation progress: {done}/{total}")
                if experiment_id:
                    progress_pct = 10 + int((done / total) * 80)  # 10% to 90%
                    self._emit_preset_progress(
                        experiment_id, 
                        "creating", 
                        f"Generating routes ({done}/{total})...", 
                        progress_pct
                    )
            
            # Use shared utility function (direct data access, no HTTP)
            routes = generate_routes_with_snap_data(
                count=count,
                node_mapper=self.node_mapper,
                progress_callback=progress_callback
            )
            return routes
            
        except Exception as e:
            logger.error(f"Error generating preset routes: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _emit_preset_progress(self, experiment_id: str, status: str, message: str, progress: int):
        """Send preset progress update via WebSocket"""
        if not self.socketio:
            return
        
        try:
            self.socketio.emit(
                'preset_progress',
                {
                    'experiment_id': experiment_id,
                    'status': status,
                    'message': message,
                    'progress': progress
                },
                room=experiment_id,
                namespace='/experiment'
            )
        except Exception as e:
            logger.error(f"Failed to emit preset progress: {e}")
    
    def _snap_to_road(self, lat, lng):
        """
        Snap a lat/lng to nearest road and get edge data.
        Uses shared road_network_utils for direct data access (no HTTP calls).
        """
        try:
            # Use shared utility function (direct data access, no HTTP)
            result = snap_location_to_edge_data(
                lat, lng,
                node_mapper=self.node_mapper,
                max_distance=500
            )
            
            if not result.get('success'):
                return None
            
            return {
                'snap_lat': result['snap_lat'],
                'snap_lng': result['snap_lng'],
                'edge_source': result['source'],
                'edge_target': result['target'],
                'edge_oneway': result['oneway']
            }
            
        except Exception as e:
            logger.warning(f"Snap failed for ({lat}, {lng}): {e}")
            return None
    
    def set_routers(self, hc2l_router, dhl_router, node_mapper):
        """Set router references from Flask app initialization"""
        self.hc2l_router = hc2l_router
        self.dhl_router = dhl_router
        self.node_mapper = node_mapper
        logger.success("Routers configured for ExperimentRunner")
    
    # =========================================================================
    # EXPERIMENT LIFECYCLE
    # =========================================================================
    
    def start_experiment(self, config: Dict) -> Dict:
        """
        Start a new experiment run.
        
        Args:
            config: Experiment configuration containing:
                - experiment_id: Optional, generated if not provided
                - is_preset: Whether to use preset or temporary storage
                - thread_count: Number of parallel threads (3 or 9)
                - trials: Number of trials (default 3)
                - batches_per_trial: Batches per trial (default 3)
                - routes_per_batch: Routes per batch (default 1000)
                - algorithms: List of algorithms to test
                - tau_settings: Tau threshold configuration
                - disruption_settings: Disruption generation settings
                
        Returns:
            Dict with success status and experiment_id
        """
        try:
            # Generate experiment ID
            experiment_id = config.get("experiment_id") or f"exp_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            is_preset = config.get("is_preset", True)
            thread_count = config.get("thread_count", 3)
            
            # Validate thread count
            if thread_count not in [3, 9]:
                thread_count = 3
            
            # Initialize progress tracking early (before preset check)
            progress = ExperimentProgress(
                experiment_id=experiment_id,
                experiment_name=config.get("name", f"Experiment {experiment_id}"),
                status="initializing",
                thread_count=thread_count,
                start_time=time.time(),
                total_routes=self._calculate_total_routes(config)
            )
            
            # Initialize thread progress
            for i in range(thread_count):
                thread_id = f"thread_{i}"
                progress.threads[thread_id] = ThreadProgress(thread_id=thread_id)
            
            # Store config for later use
            progress._config = config
            
            self.experiments[experiment_id] = progress
            
            # Return immediately so client can join WebSocket room
            # Preset check will be done asynchronously after client connects
            
            # Determine base path for disruption cache
            base_path = self.preset_path if is_preset else self.temporary_path / experiment_id
            
            # Initialize disruption cache with settings from config
            disruption_mode = config.get("disruption_mode", "preset")
            disruption_settings = config.get("disruption_settings", {
                "ratio_flow": 95,
                "ratio_incident": 5,
                "severity_min": 0.1,
                "severity_max": 0.9
            })
            self.disruption_caches[experiment_id] = DisruptionCacheManager(
                base_path, 
                is_preset=is_preset,
                disruption_mode=disruption_mode,
                disruption_settings=disruption_settings
            )
            
            # Initialize control events
            self.stop_events[experiment_id] = threading.Event()
            self.pause_events[experiment_id] = threading.Event()
            self.pause_events[experiment_id].set()  # Not paused initially
            
            # Initialize completion tracking
            self.completion_locks[experiment_id] = threading.Lock()
            self.completed_threads[experiment_id] = set()
            
            # Note: Metrics collector will be initialized in _start_experiment_work
            # after results_path is determined
            
            logger.success(f"Experiment {experiment_id} initialized, waiting for WebSocket connection")
            
            return {
                "success": True,
                "experiment_id": experiment_id,
                "thread_count": thread_count,
                "total_routes": progress.total_routes
            }
            
        except Exception as e:
            logger.error(f"Failed to start experiment: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }
    
    def _start_experiment_work(self, experiment_id: str):
        """
        Start the actual experiment work after WebSocket is connected.
        This includes preset checking and starting worker threads.
        
        Called from WebSocket on_join handler.
        """
        try:
            if experiment_id not in self.experiments:
                logger.error(f"Experiment {experiment_id} not found")
                return
            
            progress = self.experiments[experiment_id]
            
            # Get the stored config
            if not hasattr(progress, '_config'):
                logger.error(f"No config stored for experiment {experiment_id}")
                return
            
            config = progress._config
            is_preset = config.get("is_preset", True)
            route_mode = config.get("route_mode", "preset")
            preset_type = config.get("preset_type", PRESET_STANDARD)
            
            # Ensure preset configuration exists (with progress tracking)
            if is_preset:
                self._ensure_preset_config(experiment_id, route_mode, preset_type)
                
                # Load routes from appropriate preset file based on preset_type/route_mode
                if preset_type == PRESET_SCENARIO:
                    preset_file = self.preset_path / "ExperimentPresetScenario.json"
                elif route_mode == "same_batch_preset":
                    preset_file = self.preset_path / "ExperimentPresetSameBatch.json"
                else:
                    preset_file = self.preset_path / "ExperimentPreset.json"
                
                if preset_file.exists():
                    try:
                        with open(preset_file, 'r') as f:
                            preset_data = json.load(f)
                            # Merge preset routes into config if not already present
                            if "routes" not in config or not config["routes"]:
                                config["routes"] = preset_data.get("routes", [])
                                config["generation_mode"] = preset_data.get("generation_mode", "different_batch")
                                config["preset_type"] = preset_data.get("preset_type", preset_type)
                                
                                # Load scenario-specific configuration
                                if preset_type == PRESET_SCENARIO:
                                    config["disruption_scenarios"] = preset_data.get("disruption_scenarios", DISRUPTION_SCENARIOS)
                                    config["severity_levels_config"] = preset_data.get("severity_levels_config", SEVERITY_LEVELS)
                                
                                logger.success(f"Loaded {len(config['routes'])} routes from preset (mode: {config['generation_mode']})")
                    except Exception as e:
                        logger.error(f"Failed to load preset routes: {e}")
            
            # Determine base path
            if is_preset:
                base_path = self.preset_path
            else:
                base_path = self.temporary_path / experiment_id
                base_path.mkdir(parents=True, exist_ok=True)
            
            # Create results directory
            results_path = base_path / "results" / experiment_id
            # results_path.mkdir(parents=True, exist_ok=True)
            
            # Store results_path in progress for later access
            progress.results_path = results_path
            
            # Initialize metrics collector with results_path
            trials = config.get("trials", 3)
            batches = config.get("batches_per_trial", 3)
            routes_per_batch = config.get("routes_per_batch", 1000)
            preset_type = config.get("preset_type", PRESET_STANDARD)
            
            self.metrics_collectors[experiment_id] = ExperimentMetricsCollector(
                results_path=results_path,
                trials=trials,
                batches=batches,
                routes_per_batch=routes_per_batch,
                preset_type=preset_type
            )
            logger.info(f"Metrics collector initialized for {experiment_id}: {trials}×{batches}×{routes_per_batch} (preset={preset_type}) → {results_path}")
            
            # # Save initial progress
            # self._save_progress(experiment_id, results_path)
            
            # Start worker threads
            self._start_worker_threads(experiment_id, config, base_path, results_path)
            
            # Update status
            progress.status = "running"
            self._broadcast_progress(experiment_id)
            
            logger.success(f"Experiment work started for {experiment_id}")
            
        except Exception as e:
            logger.error(f"Failed to start experiment work for {experiment_id}: {e}")
            logger.error(traceback.format_exc())
            if experiment_id in self.experiments:
                self.experiments[experiment_id].status = "error"
                self.experiments[experiment_id].error_message = str(e)
                self._broadcast_progress(experiment_id)
    
    def pause_experiment(self, experiment_id: str) -> Dict:
        """Pause a running experiment"""
        if experiment_id not in self.experiments:
            return {"success": False, "error": "Experiment not found"}
        
        progress = self.experiments[experiment_id]
        if progress.status != "running":
            return {"success": False, "error": f"Cannot pause experiment in status: {progress.status}"}
        
        # Clear pause event to pause threads
        if experiment_id in self.pause_events:
            self.pause_events[experiment_id].clear()
        
        progress.status = "paused"
        for thread_id, thread_progress in progress.threads.items():
            if thread_progress.status == "running":
                thread_progress.status = "paused"
        
        self._broadcast_progress(experiment_id)
        logger.info(f"Paused experiment {experiment_id}")
        
        return {"success": True}
    
    def resume_experiment(self, experiment_id: str) -> Dict:
        """Resume a paused experiment"""
        if experiment_id not in self.experiments:
            return {"success": False, "error": "Experiment not found"}
        
        progress = self.experiments[experiment_id]
        if progress.status != "paused":
            return {"success": False, "error": f"Cannot resume experiment in status: {progress.status}"}
        
        # Set pause event to resume threads
        if experiment_id in self.pause_events:
            self.pause_events[experiment_id].set()
        
        progress.status = "running"
        for thread_id, thread_progress in progress.threads.items():
            if thread_progress.status == "paused":
                thread_progress.status = "running"
        
        self._broadcast_progress(experiment_id)
        logger.info(f"Resumed experiment {experiment_id}")
        
        return {"success": True}
    
    def stop_experiment(self, experiment_id: str) -> Dict:
        """Stop a running or paused experiment"""
        if experiment_id not in self.experiments:
            return {"success": False, "error": "Experiment not found"}
        
        progress = self.experiments[experiment_id]
        if progress.status not in ["running", "paused", "finalizing"]:
            return {"success": False, "error": f"Cannot stop experiment in status: {progress.status}"}
        
        # Signal threads to stop
        if experiment_id in self.stop_events:
            self.stop_events[experiment_id].set()
        
        # Also set pause event in case threads are waiting
        if experiment_id in self.pause_events:
            self.pause_events[experiment_id].set()
        
        progress.status = "stopped"
        progress.end_time = time.time()
        
        for thread_id, thread_progress in progress.threads.items():
            if thread_progress.status in ["running", "paused"]:
                thread_progress.status = "stopped"
        
        # Clear disruption cache
        if experiment_id in self.disruption_caches:
            self.disruption_caches[experiment_id].clear()
        
        # Clean up completion tracking
        if experiment_id in self.completion_locks:
            del self.completion_locks[experiment_id]
        if experiment_id in self.completed_threads:
            del self.completed_threads[experiment_id]
        
        self._broadcast_progress(experiment_id)
        logger.info(f"Stopped experiment {experiment_id}")
        
        return {"success": True}
    
    def get_progress(self, experiment_id: str) -> Dict:
        """Get current experiment progress"""
        if experiment_id not in self.experiments:
            return {"success": False, "error": "Experiment not found"}
        
        return {
            "success": True,
            "progress": self.experiments[experiment_id].to_dict()
        }
    
    def get_result(self, experiment_id: str) -> Dict:
        """Get final experiment results.
        
        Strategy:
        1. If a saved JSON file exists for this experiment, return that (most reliable)
        2. Otherwise, compute results from the metrics collector (for in-progress experiments)
        3. Return "success": False if results are not available
        """
        if experiment_id not in self.experiments:
            return {"success": False, "error": "Experiment not found"}
        
        progress = self.experiments[experiment_id]
        
        # ========================================================================
        # Step 1: Try to load from saved JSON file (most reliable)
        # ========================================================================
        try:
            results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
            
            # Look for experiment_results.json in the experiment's folder
            experiment_folder = results_dir / experiment_id
            result_file = experiment_folder / "experiment_results.json"
            
            if result_file.exists():
                try:
                    with open(result_file, 'r') as f:
                        result_data = json.load(f)
                    
                    # Extract metadata for response structure
                    metadata = result_data.get("metadata", {})
                    logger.success(f"Loaded results from saved file: {result_file}")
                    
                    return {
                        "success": True,
                        "experiment_id": experiment_id,
                        "status": "completed",
                        "total_routes": metadata.get("total_routes", 0),
                        "completed_routes": metadata.get("total_routes", 0),
                        "start_time": metadata.get("start_time", 0),
                        "end_time": metadata.get("end_time", 0),
                        "duration_seconds": metadata.get("duration_seconds", 0),
                        "result": result_data  # Return the full saved results object with new structure
                    }
                except Exception as e:
                    logger.error(f"Failed to read result file {result_file}: {e}")
        except Exception as e:
            logger.debug(f"Error searching for saved results: {e}")
        
        # ========================================================================
        # Step 2: Return in-progress status (no compute_results - removed)
        # ========================================================================
        # For in-progress experiments, just return the current status
        # Results will only be available after finalize() is called
        
        return {
            "success": progress.status == "completed",
            "experiment_id": experiment_id,
            "status": progress.status,
            "total_routes": progress.total_routes,
            "completed_routes": progress.completed_routes,
            "start_time": progress.start_time,
            "end_time": progress.end_time,
            "duration_seconds": progress.end_time - progress.start_time if progress.end_time > 0 else 0,
            "result": {},  # Empty for in-progress, full data when loaded from JSON
            "error": "Results not ready yet" if progress.status != "completed" else "Results file not found"
        }
    
    def get_metrics_summary(self, experiment_id: str) -> Dict:
        """Get quick metrics summary for real-time display"""
        if experiment_id not in self.metrics_collectors:
            return {"success": False, "error": "Metrics collector not found"}
        
        try:
            stats = self.metrics_collectors[experiment_id].get_progress_stats()
            return {"success": True, "stats": stats}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # PRESET MANAGEMENT
    # =========================================================================
    
    def list_presets(self) -> Dict:
        """List all preset experiments"""
        presets = []
        
        preset_file = self.preset_path / "ExperimentPreset.json"
        if preset_file.exists():
            try:
                with open(preset_file, 'r') as f:
                    preset_data = json.load(f)
                    presets.append({
                        "id": preset_data.get("id", "default"),
                        "name": preset_data.get("name", "Default Preset"),
                        "description": preset_data.get("description", ""),
                        "trial_count": preset_data.get("trial_count", 3),
                        "batch_count": preset_data.get("batch_count", 3),
                        "created_at": preset_data.get("created_at", ""),
                        "last_modified": preset_data.get("last_modified", "")
                    })
            except Exception as e:
                logger.error(f"Error loading preset file: {e}")
        
        return {"success": True, "presets": presets}
    
    def get_preset_metadata(self) -> Dict:
        """Get metadata for the main preset experiment"""
        preset_file = self.preset_path / "ExperimentPreset.json"
        
        if not preset_file.exists():
            return {"success": False, "error": "No preset found"}
        
        try:
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
            
            # Count disruption sets
            disruptions_path = self.preset_path / "disruptions"
            disruption_count = 0
            if disruptions_path.exists():
                disruption_count = len(list(disruptions_path.glob("set_batch_*")))
            
            return {
                "success": True,
                "metadata": {
                    **preset_data,
                    "disruption_sets_count": disruption_count,
                    "disruptions_generated": disruption_count > 0
                }
            }
        except Exception as e:
            logger.error(f"Error loading preset metadata: {e}")
            return {"success": False, "error": str(e)}
    
    def create_preset(self, config: Dict) -> Dict:
        """Create or update the preset experiment configuration"""
        try:
            preset_data = {
                "id": config.get("id", "default"),
                "name": config.get("name", "Experiment Preset"),
                "description": config.get("description", ""),
                "algorithms": config.get("algorithms", ["DHL", "HC2L"]),
                "trial_count": config.get("trial_count", 3),
                "batch_count": config.get("batch_count", 3),
                "routes_per_batch": config.get("routes_per_batch", 1000),
                "tau_settings": config.get("tau_settings", {
                    "mode": "random",
                    "scope": "per-trial-route",
                    "fixed": 0.5,
                    "random_min": 0.1,
                    "random_max": 0.9
                }),
                "disruption_settings": config.get("disruption_settings", {
                    "ratio_flow": 95,
                    "ratio_incident": 5,
                    "severity_min": 0.1,
                    "severity_max": 0.9
                }),
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat()
            }
            
            preset_file = self.preset_path / "ExperimentPreset.json"
            with open(preset_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            logger.success(f"Created preset: {preset_data['id']}")
            return {"success": True, "preset": preset_data}
            
        except Exception as e:
            logger.error(f"Error creating preset: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    
    def cleanup_temporary(self, experiment_id: str = None) -> Dict:
        """
        Clean up temporary experiment files.
        
        Args:
            experiment_id: Specific experiment to clean up, or None for all
            
        Returns:
            Dict with success status and cleaned items count
        """
        cleaned = 0
        
        try:
            if experiment_id:
                # Clean specific experiment
                exp_path = self.temporary_path / experiment_id
                if exp_path.exists():
                    shutil.rmtree(exp_path)
                    cleaned = 1
                    logger.info(f"Cleaned up temporary experiment: {experiment_id}")
            else:
                # Clean all temporary experiments
                for exp_dir in self.temporary_path.iterdir():
                    if exp_dir.is_dir():
                        shutil.rmtree(exp_dir)
                        cleaned += 1
                logger.info(f"Cleaned up {cleaned} temporary experiments")
            
            return {"success": True, "cleaned_count": cleaned}
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    def _calculate_total_routes(self, config: Dict) -> int:
        """Calculate total number of routes to process"""
        preset_type = config.get("preset_type", PRESET_STANDARD)
        algorithms = config.get("algorithms", ["DHL", "HC2L"])
        
        if preset_type == PRESET_SCENARIO:
            # Scenario mode: 3 categories × 10 routes × 10 scenarios × 3 severities × algorithms
            routes_per_category = config.get("routes_per_category", 10)
            scenarios = 10  # DS1-DS10
            severities = 3  # light, medium, heavy
            categories = 3  # short, medium, long
            return categories * routes_per_category * scenarios * severities * len(algorithms)
        else:
            # Standard mode: trials × batches × routes × algorithms
            trials = config.get("trials", 3)
            batches_per_trial = config.get("batches_per_trial", 3)
            routes_per_batch = config.get("routes_per_batch", 1000)
            return trials * batches_per_trial * routes_per_batch * len(algorithms)
    
    def _start_worker_threads(self, experiment_id: str, config: Dict, 
                              base_path: Path, results_path: Path):
        """Start worker threads for experiment execution"""
        progress = self.experiments[experiment_id]
        thread_count = progress.thread_count
        preset_type = config.get("preset_type", PRESET_STANDARD)
        
        trials = config.get("trials", 3)
        batches_per_trial = config.get("batches_per_trial", 3)
        routes_per_batch = config.get("routes_per_batch", 1000)
        algorithms = config.get("algorithms", ["DHL", "HC2L"])
        
        threads = []
        
        # Scenario mode: 3 threads for 3 route categories (short, medium, long)
        # Each thread runs 10 routes × 10 scenarios × 3 severities = 300 simulations
        if preset_type == PRESET_SCENARIO:
            route_categories = ["short", "medium", "long"]
            for category_idx, category in enumerate(route_categories):
                thread_id = f"thread_{category_idx}"
                thread = threading.Thread(
                    target=self._scenario_worker_thread,
                    args=(experiment_id, thread_id, category_idx, category,
                          config, base_path, results_path),
                    daemon=True,
                    name=f"scenario_{category}_{experiment_id}"
                )
                thread.start()
                threads.append(thread)
                logger.info(f"Started scenario thread for category '{category}' ({thread_id})")
        elif thread_count == 3:
            # Default mode: one thread per trial
            for trial_idx in range(trials):
                thread_id = f"thread_{trial_idx}"
                thread = threading.Thread(
                    target=self._worker_thread,
                    args=(experiment_id, thread_id, trial_idx, None, 
                          config, base_path, results_path),
                    daemon=True
                )
                thread.start()
                threads.append(thread)
        else:
            # Advanced mode: one thread per trial-batch combination
            thread_idx = 0
            for trial_idx in range(trials):
                for batch_idx in range(batches_per_trial):
                    thread_id = f"thread_{thread_idx}"
                    thread = threading.Thread(
                        target=self._worker_thread,
                        args=(experiment_id, thread_id, trial_idx, batch_idx,
                              config, base_path, results_path),
                        daemon=True
                    )
                    thread.start()
                    threads.append(thread)
                    thread_idx += 1
        
        self.experiment_threads[experiment_id] = threads
        
        # Start HERE comparison thread (runs in parallel with worker threads)
        # This compares HERE API routes with HC2L baseline (no disruptions)
        here_thread = threading.Thread(
            target=self._here_comparison_thread,
            args=(experiment_id, config),
            daemon=True,
            name=f"here_comparison_{experiment_id}"
        )
        here_thread.start()
        logger.info(f"Started HERE comparison thread for {experiment_id}")
    
    def _here_comparison_thread(self, experiment_id: str, config: Dict):
        """
        Dedicated thread for HERE vs HC2L route similarity comparison with adaptive rate limiting.
        
        This thread:
        1. Uses the same routes as the experiment (from config)
        2. Computes HC2L routes WITHOUT disruptions
        3. Fetches HERE API routes for the same OD pairs with rate limiting
        4. Calculates Fréchet distance between routes
        5. Records all metrics for the Route Similarity tab
        6. Implements adaptive batching based on API response codes
        
        Args:
            experiment_id: Experiment identifier
            config: Experiment configuration with routes
        """
        try:
            if experiment_id not in self.metrics_collectors:
                logger.error(f"No metrics collector for {experiment_id}")
                return
            
            collector = self.metrics_collectors[experiment_id]
            routes = config.get("routes", [])
            routes_per_batch = config.get("routes_per_batch", 1000)
            preset_type = config.get("preset_type", PRESET_STANDARD)
            
            # For scenario mode, compare ALL routes (30 routes across 3 categories)
            # Each route is compared once (baseline without disruptions)
            if preset_type == PRESET_SCENARIO:
                routes_to_compare = routes  # All 30 routes
                logger.info(f"Scenario mode: Comparing all {len(routes_to_compare)} routes (3 categories × 10 routes)")
            else:
                # Standard mode: Limit to routes_per_batch routes
                routes_to_compare = routes[:routes_per_batch]
            
            total_routes = len(routes_to_compare)
            
            if total_routes == 0:
                logger.warning("No routes available for HERE comparison")
                collector.update_here_comparison_status('completed', 0)
                return
            
            logger.info(f"Starting HERE comparison for {total_routes} routes with rate limiting...")
            collector.update_here_comparison_status('running', total_routes)
            
            # Initialize HERE routing service with rate limiting
            # Configure 10 req/s (HERE Routing API typically allows 10-20 QPS for most plans)
            here_service = HereRoutingService(requests_per_second=10)
            
            # Adaptive batching: Start with batch_size of 10, adjust based on rate limit responses
            batch_size = 10
            completed = 0
            errors = 0
            rate_limit_hits = 0
            consecutive_failures = 0
            max_consecutive_failures = 5
            
            logger.info(f"Using adaptive rate limiting: 10 req/s, batch size: {batch_size}")
            
            # Running metrics accumulators for live display
            hc2l_query_times = []
            hc2l_distances = []
            hc2l_times = []
            here_query_times = []
            here_distances = []
            here_times = []
            frechet_distances = []
            time_deviations = []
            
            for route_idx, route_data in enumerate(routes_to_compare):
                # Check if experiment is still running
                if experiment_id not in self.experiments:
                    logger.info(f"Experiment {experiment_id} stopped, ending HERE comparison")
                    break
                
                if self.stop_events.get(experiment_id, threading.Event()).is_set():
                    logger.info(f"Experiment {experiment_id} stop requested, ending HERE comparison")
                    break
                
                # Wait if paused - this allows pause/resume functionality
                pause_event = self.pause_events.get(experiment_id)
                if pause_event is not None:
                    if not pause_event.is_set():
                        # Update status to paused
                        collector.update_here_comparison_status('paused', total_routes)
                        if experiment_id in self.experiments:
                            self._broadcast_progress(experiment_id)
                        logger.info(f"HERE comparison paused for {experiment_id}, waiting...")
                    pause_event.wait()  # Block until resumed
                    # Check if we should resume running status
                    if experiment_id in self.experiments and collector.here_comparison_progress.get('status') == 'paused':
                        collector.update_here_comparison_status('running', total_routes)
                        if experiment_id in self.experiments:
                            self._broadcast_progress(experiment_id)
                        logger.info(f"HERE comparison resumed for {experiment_id}")
                
                try:
                    # Retry logic: try up to 3 times with 1 second wait between attempts
                    max_retries = 3
                    comparison_result = None
                    last_error = None
                    
                    for attempt in range(max_retries):
                        comparison_result = self._compare_single_route_here_vs_hc2l(
                            route_idx, route_data, here_service, config
                        )
                        
                        # If successful (no error), break out of retry loop
                        if not comparison_result.get('error'):
                            break
                        
                        # If this is a HERE API error and not the last attempt, retry
                        last_error = comparison_result.get('error', '')
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Route {route_idx} attempt {attempt + 1}/{max_retries} failed: {last_error}. "
                                f"Retrying in 1 second..."
                            )
                            time.sleep(1)
                        else:
                            logger.warning(
                                f"Route {route_idx} failed after {max_retries} attempts: {last_error}"
                            )
                    
                    # Check if rate limiting occurred
                    if comparison_result.get('error') and '429' in str(comparison_result.get('error', '')):
                        rate_limit_hits += 1
                        consecutive_failures += 1
                        logger.warning(
                            f"Rate limited on route {route_idx}. "
                            f"Total rate limit hits: {rate_limit_hits}"
                        )
                    elif comparison_result.get('error'):
                        errors += 1
                        consecutive_failures += 1
                        logger.warning(f"Route {route_idx} failed: {comparison_result.get('error')}")
                    else:
                        completed += 1
                        consecutive_failures = 0
                        
                        # Accumulate metrics for running averages display
                        if comparison_result.get('query_time_ms_hc2l', 0) > 0:
                            hc2l_query_times.append(comparison_result['query_time_ms_hc2l'])
                        if comparison_result.get('distance_km_hc2l', 0) > 0:
                            hc2l_distances.append(comparison_result['distance_km_hc2l'])
                        if comparison_result.get('travel_time_min_hc2l', 0) > 0:
                            hc2l_times.append(comparison_result['travel_time_min_hc2l'])
                        if comparison_result.get('query_time_ms_here', 0) > 0:
                            here_query_times.append(comparison_result['query_time_ms_here'])
                        if comparison_result.get('distance_km_here', 0) > 0:
                            here_distances.append(comparison_result['distance_km_here'])
                        if comparison_result.get('travel_time_min_here', 0) > 0:
                            here_times.append(comparison_result['travel_time_min_here'])
                        if comparison_result.get('frechet_distance_m', 0) > 0:
                            frechet_distances.append(comparison_result['frechet_distance_m'])
                        if comparison_result.get('time_deviation_pct') is not None:
                            time_deviations.append(abs(comparison_result['time_deviation_pct']))
                        
                        # Update running metrics in the collector's progress
                        with collector.lock:
                            progress = collector.here_comparison_progress
                            # HC2L metrics
                            if hc2l_query_times:
                                progress['hc2l_avg_query_ms'] = sum(hc2l_query_times) / len(hc2l_query_times)
                            if hc2l_distances:
                                progress['hc2l_avg_distance_km'] = sum(hc2l_distances) / len(hc2l_distances)
                            if hc2l_times:
                                progress['hc2l_avg_time_min'] = sum(hc2l_times) / len(hc2l_times)
                            # HERE metrics
                            if here_query_times:
                                progress['here_avg_query_ms'] = sum(here_query_times) / len(here_query_times)
                            if here_distances:
                                progress['here_avg_distance_km'] = sum(here_distances) / len(here_distances)
                            if here_times:
                                progress['here_avg_time_min'] = sum(here_times) / len(here_times)
                            # Quality metrics
                            if frechet_distances:
                                progress['avg_frechet_m'] = sum(frechet_distances) / len(frechet_distances)
                                progress['last_frechet_m'] = frechet_distances[-1]
                            if time_deviations:
                                progress['avg_time_deviation_pct'] = sum(time_deviations) / len(time_deviations)
                            
                            # Last route details for UI display
                            progress['last_hc2l_dist_km'] = comparison_result.get('distance_km_hc2l', 0)
                            progress['last_here_dist_km'] = comparison_result.get('distance_km_here', 0)
                            progress['last_hc2l_time_min'] = comparison_result.get('travel_time_min_hc2l', 0)
                            progress['last_here_time_min'] = comparison_result.get('travel_time_min_here', 0)
                            progress['last_time_dev_pct'] = comparison_result.get('time_deviation_pct', 0)
                    
                    # Record similarity data (batch=0 for baseline comparison, route_idx is the route)
                    collector.record_similarity(batch=0, route=route_idx, comparison_data=comparison_result)
                    
                    # Adaptive batching: reduce batch size if too many failures
                    if consecutive_failures >= max_consecutive_failures:
                        batch_size = max(5, batch_size // 2)
                        logger.warning(
                            f"Too many consecutive failures ({consecutive_failures}). "
                            f"Reducing batch size to {batch_size}."
                        )
                        consecutive_failures = 0
                    
                    # Intelligent delay between requests
                    if (route_idx + 1) % batch_size == 0:
                        # Longer pause at batch boundaries to give API time to recover
                        batch_pause = 1.0 if rate_limit_hits == 0 else 2.0
                        logger.debug(
                            f"Batch {(route_idx + 1) // batch_size} completed. "
                            f"Pausing {batch_pause}s before next batch..."
                        )
                        time.sleep(batch_pause)
                        
                        # Broadcast progress update
                        if experiment_id in self.experiments:
                            self._broadcast_progress(experiment_id)
                        
                        # Log rate limiter statistics
                        limiter_stats = here_service.get_rate_limiter_stats()
                        cache_stats = here_service.get_cache_stats()
                        logger.info(
                            f"HERE API Stats - "
                            f"Successful: {limiter_stats['successful_requests']}, "
                            f"Rate Limited: {limiter_stats['rate_limited']}, "
                            f"Retried: {limiter_stats['retried']}, "
                            f"Circuit Open: {limiter_stats['circuit_open']}, "
                            f"Cache Usage: {cache_stats['cache_usage_pct']}%"
                        )
                    
                except Exception as e:
                    logger.error(f"Error comparing route {route_idx}: {e}")
                    consecutive_failures += 1
                    errors += 1
                    # Record error case with similarity method
                    collector.record_similarity(batch=0, route=route_idx, comparison_data={
                        'route_idx': route_idx,
                        'source_node': 0,
                        'target_node': 0,
                        'error': str(e)
                    })
            
            # Final statistics
            limiter_stats = here_service.get_rate_limiter_stats()
            cache_stats = here_service.get_cache_stats()
            
            logger.success(
                f"HERE comparison completed: {completed}/{total_routes} routes compared, "
                f"{errors} errors, {rate_limit_hits} rate limit hits"
            )
            logger.info(
                f"Final Rate Limiter Stats - "
                f"Total Requests: {limiter_stats['total_requests']}, "
                f"Successful: {limiter_stats['successful_requests']}, "
                f"Rate Limited (429): {limiter_stats['rate_limited']}, "
                f"Retried: {limiter_stats['retried']}, "
                f"Circuit Breaker Trips: {limiter_stats['circuit_breaker_trips']}"
            )
            logger.info(
                f"Cache Stats - "
                f"Entries: {cache_stats['cache_size']}/{cache_stats['cache_max_size']}, "
                f"Usage: {cache_stats['cache_usage_pct']}%"
            )
            
            collector.update_here_comparison_status('completed', total_routes)
            
        except Exception as e:
            logger.error(f"HERE comparison thread error: {e}")
            logger.error(traceback.format_exc())
            if experiment_id in self.metrics_collectors:
                self.metrics_collectors[experiment_id].update_here_comparison_status('error', 0)
    
    def _compare_single_route_here_vs_hc2l(self, route_idx: int, route_data: Dict,
                                           here_service: HereRoutingService, 
                                           config: Dict) -> Dict:
        """
        Compare a single route between HERE API and HC2L (no disruptions).
        
        Args:
            route_idx: Route index
            route_data: Route data with start/end coordinates
            here_service: HERE routing service instance
            config: Experiment configuration
            
        Returns:
            Dict with all comparison metrics
        """
        result = {
            'route_idx': route_idx,
            'batch': 0,
            'source_node': 0,
            'target_node': 0,
            'start_road_hc2l': 'Unknown',
            'end_road_hc2l': 'Unknown',
            'start_road_here': 'Unknown',
            'end_road_here': 'Unknown',
            'distance_km_hc2l': 0,
            'distance_km_here': 0,
            'travel_time_min_hc2l': 0,
            'travel_time_min_here': 0,
            'query_time_ms_hc2l': 0,
            'query_time_ms_here': 0,
            'frechet_distance_m': 0,
            'fd_rating': 'N/A',
            'time_deviation_pct': 0,
            'ttd_rating': 'N/A',
            'distance_deviation_pct': 0,
            'error': None
        }
        
        try:
            # Extract route coordinates
            start_data = route_data.get('start', {})
            end_data = route_data.get('end', {})
            
            start_lat = start_data.get('pin_lat', start_data.get('snap_lat', start_data.get('lat', 0)))
            start_lng = start_data.get('pin_lng', start_data.get('snap_lng', start_data.get('lng', 0)))
            end_lat = end_data.get('pin_lat', end_data.get('snap_lat', end_data.get('lat', 0)))
            end_lng = end_data.get('pin_lng', end_data.get('snap_lng', end_data.get('lng', 0)))
            
            source_node = start_data.get('edge_source', 0)
            target_node = end_data.get('edge_source', 0)
            
            result['source_node'] = source_node
            result['target_node'] = target_node
            
            # Get road names from road mapper
            if self.road_mapper:
                try:
                    result['start_road_hc2l'] = self.road_mapper.get_road_name(
                        start_data.get('edge_source', 0),
                        start_data.get('edge_target', 0)
                    ) or 'Unknown'
                    result['end_road_hc2l'] = self.road_mapper.get_road_name(
                        end_data.get('edge_source', 0),
                        end_data.get('edge_target', 0)
                    ) or 'Unknown'
                except:
                    pass
            
            # ================================================================
            # Step 1: Call HC2L router WITHOUT disruptions
            # ================================================================
            hc2l_start_time = time.time()
            hc2l_result = None
            hc2l_path = []
            
            if self.hc2l_router:
                hc2l_result = self.hc2l_router.compute_route(
                    start_pin_lat=start_lat,
                    start_pin_lng=start_lng,
                    dest_pin_lat=end_lat,
                    dest_pin_lng=end_lng,
                    start_snap_lat=start_data.get('snap_lat', start_lat),
                    start_snap_lng=start_data.get('snap_lng', start_lng),
                    dest_snap_lat=end_data.get('snap_lat', end_lat),
                    dest_snap_lng=end_data.get('snap_lng', end_lng),
                    start_edge_source=start_data.get('edge_source', 0),
                    start_edge_target=start_data.get('edge_target', 0),
                    start_edge_oneway=start_data.get('edge_oneway', 0),
                    dest_edge_source=end_data.get('edge_source', 0),
                    dest_edge_target=end_data.get('edge_target', 0),
                    dest_edge_oneway=end_data.get('edge_oneway', 0),
                    disruption_file="",  # NO DISRUPTIONS
                    tau_threshold=0.5,
                    generate_alternatives=False,
                    verbose=False
                )
            
            hc2l_query_time = (time.time() - hc2l_start_time) * 1000
            
            if hc2l_result and hc2l_result.get('success'):
                metrics = hc2l_result.get('metrics', {})
                route_info = hc2l_result.get('route', {})
                
                # Get distance in meters and convert to km
                calculated_dist_m = metrics.get('calculated_distance_meters', 0)
                result['distance_km_hc2l'] = calculated_dist_m / 1000 if calculated_dist_m else 0
                
                # Extract travel time
                eta_seconds = metrics.get('eta_seconds', 0)
                result['travel_time_min_hc2l'] = eta_seconds / 60 if eta_seconds else 0
                
                result['query_time_ms_hc2l'] = metrics.get('query_time_ms', hc2l_query_time)
                
                # Extract path coordinates for Fréchet calculation
                geometry = route_info.get('geometry', [])
                for segment in geometry:
                    coords = segment.get('coordinates', [])
                    hc2l_path.extend(coords)
            else:
                result['error'] = 'HC2L routing failed'
                return result
            
            # ================================================================
            # Step 2: Call HERE Routing API
            # ================================================================
            here_start_time = time.time()
            here_result = here_service.get_directions(
                start_lat=start_lat,
                start_lng=start_lng,
                dest_lat=end_lat,
                dest_lng=end_lng,
                traffic_mode='disabled'  # No traffic to match baseline
            )
            here_query_time = (time.time() - here_start_time) * 1000
            
            here_path = []
            
            if here_result and here_result.get('success'):
                result['distance_km_here'] = here_result.get('distance_meters', 0) / 1000
                result['travel_time_min_here'] = here_result.get('duration_seconds', 0) / 60
                result['query_time_ms_here'] = here_query_time
                
                # Extract path coordinates
                here_path = here_result.get('coordinates', [])
            else:
                result['error'] = f"HERE API failed: {here_result.get('error', 'Unknown error')}"
                return result
            
            # ================================================================
            # Step 3: Calculate Fréchet Distance
            # ================================================================
            if hc2l_path and here_path:
                # Convert HERE path format if needed (HERE returns [lat, lng], we need consistency)
                frechet = self._compute_frechet_distance_for_comparison(hc2l_path, here_path)
                result['frechet_distance_m'] = frechet
                
                # Determine FD rating
                if frechet < 100:
                    result['fd_rating'] = 'Excellent'
                elif frechet < 500:
                    result['fd_rating'] = 'Good'
                else:
                    result['fd_rating'] = 'Fair'
            
            # ================================================================
            # Step 4: Calculate Deviation Percentages
            # ================================================================
            # Time deviation - Formula 15: TimeDeviation = ((T_HC2L - T_ref) / T_ref) * 100
            if result['travel_time_min_here'] > 0:
                result['time_deviation_pct'] = (
                    (result['travel_time_min_hc2l'] - result['travel_time_min_here'])
                    / result['travel_time_min_here'] * 100
                )
            
            # TTD rating - based on absolute deviation magnitude
            ttd_magnitude = abs(result['time_deviation_pct'])
            if ttd_magnitude < 5:
                result['ttd_rating'] = 'Excellent'
            elif ttd_magnitude < 15:
                result['ttd_rating'] = 'Good'
            else:
                result['ttd_rating'] = 'Fair'
            
            # Distance deviation - consistent with Travel Time Deviation formula using HERE as reference
            if result['distance_km_here'] > 0:
                result['distance_deviation_pct'] = (
                    (result['distance_km_hc2l'] - result['distance_km_here'])
                    / result['distance_km_here'] * 100
                )
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error in route comparison {route_idx}: {e}")
            return result
    
    def _compute_frechet_distance_for_comparison(self, path1: List, path2: List) -> float:
        """
        Compute Fréchet distance between two paths for HERE vs HC2L comparison.
        
        Args:
            path1: HC2L path coordinates [[lng, lat], ...]
            path2: HERE path coordinates [[lat, lng], ...] (different format!)
            
        Returns:
            Fréchet distance in meters
        """
        if not path1 or not path2:
            return 0
        
        try:
            # Normalize coordinate formats
            # HC2L uses [lng, lat], HERE uses [lat, lng]
            p1 = []
            for coord in path1:
                if len(coord) >= 2:
                    p1.append([coord[1], coord[0]])  # Convert to [lat, lng]
            
            p2 = []
            for coord in path2:
                if len(coord) >= 2:
                    p2.append([coord[0], coord[1]])  # Already [lat, lng]
            
            if not p1 or not p2:
                return 0
            
            # Use optimized Fréchet distance calculation
            p1_arr = np.array(p1, dtype=np.float64)
            p2_arr = np.array(p2, dtype=np.float64)
            
            n, m = len(p1_arr), len(p2_arr)
            
            # Limit size for performance (sample if too large)
            max_points = 100
            if n > max_points:
                indices = np.linspace(0, n - 1, max_points, dtype=int)
                p1_arr = p1_arr[indices]
                n = max_points
            if m > max_points:
                indices = np.linspace(0, m - 1, max_points, dtype=int)
                p2_arr = p2_arr[indices]
                m = max_points
            
            # Haversine distance matrix
            lat1 = p1_arr[:, 0][:, np.newaxis]
            lon1 = p1_arr[:, 1][:, np.newaxis]
            lat2 = p2_arr[:, 0][np.newaxis, :]
            lon2 = p2_arr[:, 1][np.newaxis, :]
            
            R = 6371000  # Earth radius in meters
            phi1 = np.radians(lat1)
            phi2 = np.radians(lat2)
            dphi = np.radians(lat2 - lat1)
            dlambda = np.radians(lon2 - lon1)
            
            a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
            distances = 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            
            # Iterative DP for Fréchet
            ca = np.full((n, m), np.inf, dtype=np.float64)
            ca[0, 0] = distances[0, 0]
            
            for i in range(1, n):
                ca[i, 0] = max(ca[i-1, 0], distances[i, 0])
            for j in range(1, m):
                ca[0, j] = max(ca[0, j-1], distances[0, j])
            
            for i in range(1, n):
                for j in range(1, m):
                    ca[i, j] = max(min(ca[i-1, j], ca[i-1, j-1], ca[i, j-1]), distances[i, j])
            
            return float(ca[n-1, m-1])
            
        except Exception as e:
            logger.warning(f"Fréchet calculation error: {e}")
            return 0
    
    def _worker_thread(self, experiment_id: str, thread_id: str, 
                       trial_idx: int, batch_idx: Optional[int],
                       config: Dict, base_path: Path, results_path: Path):
        """
        Worker thread that processes routes.
        
        Args:
            experiment_id: Experiment identifier
            thread_id: Thread identifier
            trial_idx: Trial index (0-based)
            batch_idx: Batch index (0-based) or None for full trial
            config: Experiment configuration
            base_path: Base path for experiment data
            results_path: Path for saving results
        """
        try:
            progress = self.experiments[experiment_id]
            thread_progress = progress.threads[thread_id]
            
            trials = config.get("trials", 3)
            batches_per_trial = config.get("batches_per_trial", 3)
            routes_per_batch = config.get("routes_per_batch", 1000)
            algorithms = config.get("algorithms", ["DHL", "HC2L"])
            tau_settings = config.get("tau_settings", {})
            
            # Update thread progress
            thread_progress.status = "running"
            thread_progress.trial_number = f"{trial_idx + 1}/{trials}"
            
            if batch_idx is not None:
                # Single batch mode
                thread_progress.batch_number = f"{batch_idx + 1}/{batches_per_trial}"
                batch_range = [batch_idx]
            else:
                # Full trial mode
                batch_range = range(batches_per_trial)
            
            thread_progress.total_routes = len(batch_range) * routes_per_batch * len(algorithms)
            
            # Get disruption cache
            cache = self.disruption_caches.get(experiment_id)
            
            # Process routes
            start_time = time.time()
            completed = 0
            
            for b_idx in batch_range:
                if self.stop_events[experiment_id].is_set():
                    break
                
                if batch_idx is None:
                    thread_progress.batch_number = f"{b_idx + 1}/{batches_per_trial}"
                
                for route_idx in range(routes_per_batch):
                    if self.stop_events[experiment_id].is_set():
                        break
                    
                    # Wait if paused
                    self.pause_events[experiment_id].wait()
                    
                    # Load disruption (lazy)
                    disruption_data = None
                    if cache:
                        disruption_data = cache.load_disruption(b_idx, route_idx, thread_id)
                        
                        # Pre-load next chunk if at threshold
                        if route_idx > 0 and route_idx % 80 == 0:
                            cache.preload_chunk(b_idx, route_idx + 20, thread_id)
                    
                    # Determine disruption level for variety_preset mode
                    config_disruption_mode = config.get("disruption_mode", "preset")
                    if config_disruption_mode == "variety_preset":
                        level_idx = b_idx % 3
                        level_names = ["Light", "Medium", "Heavy"]
                        thread_progress.current_disruption_level = level_names[level_idx]
                        thread_progress.current_disruption = f"set_{level_names[level_idx].lower()}_route_{route_idx}"
                    else:
                        thread_progress.current_disruption_level = ""
                        thread_progress.current_disruption = f"set_batch_{b_idx}_route_{route_idx}"
                    
                    for algorithm in algorithms:
                        if self.stop_events[experiment_id].is_set():
                            break
                        
                        thread_progress.algorithm = algorithm
                        thread_progress.current_route_index = completed
                        thread_progress.route_progress = f"{completed + 1}/{thread_progress.total_routes}"
                        
                        # Execute route computation
                        result = self._execute_route(
                            experiment_id, thread_id, trial_idx, b_idx, route_idx,
                            algorithm, tau_settings, disruption_data, config
                        )
                        
                        # ============================================================
                        # RECORD ALL METRICS (includes accuracy-first gating for HC2L)
                        # ============================================================
                        if experiment_id in self.metrics_collectors:
                            metrics_collector = self.metrics_collectors[experiment_id]
                            
                            # Record route metrics (handles accuracy, performance, construction all in one)
                            record = metrics_collector.record_route_metric(
                                trial=trial_idx,
                                batch=b_idx,
                                route=route_idx,
                                algorithm=algorithm,
                                api_result=result,
                                disruption_data=disruption_data
                            )
                            
                            # # Log accuracy result for HC2L routes
                            # if algorithm.upper() == "HC2L" and record.accuracy:
                            #     if not record.accuracy.is_correct:
                            #         logger.warning(
                            #             f"Route [{trial_idx+1},{b_idx+1},{route_idx+1}] HC2L "
                            #             f"accuracy FAILED: dhc2l={record.accuracy.dhc2l_distance:.1f}m, "
                            #             f"dijkstra={record.accuracy.dijkstra_distance:.1f}m, "
                            #             f"error={record.accuracy.relative_error:.4f} > tolerance={record.accuracy.tolerance}"
                            #         )
                            #     else:
                            #         logger.debug(
                            #             f"Route [{trial_idx+1},{b_idx+1},{route_idx+1}] HC2L "
                            #             f"accuracy OK: error={record.accuracy.relative_error:.4f}"
                            #         )
                        
                        # Update progress
                        completed += 1
                        thread_progress.current_route_index = completed
                        thread_progress.percentage = (completed / thread_progress.total_routes) * 100
                        
                        # Calculate throughput
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            thread_progress.routes_per_minute = (completed / elapsed) * 60
                            remaining_routes = thread_progress.total_routes - completed
                            remaining_time = remaining_routes / (completed / elapsed)
                            thread_progress.estimated_time_remaining = self._format_time(remaining_time)
                        
                        # Get route node information from result (before updating last_result)
                        route_coords = result.get("route_coords", {})
                        start_node = route_coords.get("start_node", 0)
                        end_node = route_coords.get("end_node", 0)
                        start_edge_target = route_coords.get("start_edge_target", 0)
                        end_edge_target = route_coords.get("end_edge_target", 0)
                        
                        # Get road names for start and end nodes
                        start_road_name = "Unknown Road"
                        end_road_name = "Unknown Road"
                        
                        if self.road_mapper:
                            try:
                                start_road_name = self.road_mapper.get_road_name(start_node, start_edge_target)
                                end_road_name = self.road_mapper.get_road_name(end_node, end_edge_target)
                            except Exception as e:
                                logger.debug(f"Error getting road names: {e}")
                        
                        # Update last result with route information
                        last_result = result.get("summary", {})
                        last_result["start_node"] = start_node
                        last_result["end_node"] = end_node
                        last_result["start_road_name"] = start_road_name
                        last_result["end_road_name"] = end_road_name
                        thread_progress.last_result = last_result
                        thread_progress.update_phase = result.get("update_phase", {})
                        
                        # Update query phase with accumulated statistics
                        query_time = result.get("query_phase", {}).get("query_time_ms", 0)
                        label_size = result.get("summary", {}).get("label_size", 0)
                        labeling_time = result.get("summary", {}).get("labeling_time_ms", 0)
                        
                        # Track success/failure
                        accuracy = result.get("accuracy", {})
                        if accuracy.get("is_correct", False):
                            thread_progress.successful_routes += 1
                        else:
                            thread_progress.failed_routes += 1
                        
                        # Update running averages (only for successful routes)
                        if accuracy.get("is_correct", False):
                            current_count = thread_progress.successful_routes
                            if current_count > 0:
                                # Running average update
                                thread_progress.avg_query_time_ms = (
                                    (thread_progress.avg_query_time_ms * (current_count - 1) + query_time) / current_count
                                )
                                thread_progress.avg_labeling_time_ms = (
                                    (thread_progress.avg_labeling_time_ms * (current_count - 1) + labeling_time) / current_count
                                )
                                thread_progress.avg_labeling_size_mb = (
                                    (thread_progress.avg_labeling_size_mb * (current_count - 1) + label_size) / current_count
                                )
                        distance_km = result.get("summary", {}).get("distance_km", 0)
                        actual_eta = result.get("summary", {}).get("actual_eta", "")
                        
                        # Initialize query history if not exists
                        if not hasattr(thread_progress, 'query_times'):
                            thread_progress.query_times = []
                            thread_progress.label_sizes = []
                        
                        # Add to query history
                        thread_progress.query_times.append(query_time)
                        thread_progress.label_sizes.append(label_size)
                        
                        # Calculate statistics from accumulated data
                        if thread_progress.query_times:
                            import statistics
                            thread_progress.query_phase = {
                                "algorithm": algorithm,
                                "query_time_ms": query_time,
                                "avg_query_time_ms": statistics.mean(thread_progress.query_times),
                                "min_query_time_ms": min(thread_progress.query_times),
                                "max_query_time_ms": max(thread_progress.query_times),
                                "std_dev": statistics.stdev(thread_progress.query_times) if len(thread_progress.query_times) > 1 else 0,
                                "p95_latency_ms": sorted(thread_progress.query_times)[int(len(thread_progress.query_times) * 0.95)] if len(thread_progress.query_times) > 1 else query_time,
                                "queries_count": len(thread_progress.query_times)
                            }
                        else:
                            thread_progress.query_phase = result.get("query_phase", {})
                        
                        # Add to history (limit to 5 as requested)
                        # Note: start_node, end_node, start_road_name, end_road_name already obtained above
                        thread_progress.results_history.append({
                            "query_number": completed,
                            "timestamp": datetime.now().isoformat(),
                            "start_node": start_node,
                            "end_node": end_node,
                            "start_road_name": start_road_name,
                            "end_road_name": end_road_name,
                            "algorithm": algorithm,
                            "query_time_ms": query_time,
                            "distance_km": distance_km,
                            "actual_eta": actual_eta
                        })
                        if len(thread_progress.results_history) > 5:
                            thread_progress.results_history.pop(0)
                        
                        # Update overall progress (90% for thread tasks)
                        progress.completed_routes = sum(
                            t.current_route_index for t in progress.threads.values()
                        )
                        # Only 90% of total is for thread completion, 10% for finalization
                        thread_task_percentage = (progress.completed_routes / progress.total_routes) * 90
                        progress.overall_percentage = thread_task_percentage + progress.finalization_percentage
                        
                        # Broadcast update
                        self._broadcast_progress(experiment_id)
            
            # Thread completed - use lock to ensure atomic completion checking
            with self.completion_locks[experiment_id]:
                thread_progress.status = "completed"
                thread_progress.percentage = 100.0
                
                # Mark this thread as completed
                self.completed_threads[experiment_id].add(thread_id)
                
                logger.success(f"Thread {thread_id} completed for experiment {experiment_id} ({len(self.completed_threads[experiment_id])}/{len(progress.threads)} threads done)")
                
                # Check if all threads completed (atomic check)
                all_threads_done = len(self.completed_threads[experiment_id]) == len(progress.threads)
                
                if all_threads_done:
                    logger.info(f"All threads completed for {experiment_id}, finalizing...")
                    
                    # Set status to finalizing (NOT completed yet)
                    progress.status = "finalizing"
                    progress.finalization_phase = "Computing results..."
                    progress.finalization_percentage = 0.0
                    progress.overall_percentage = 90.0  # Thread tasks are 90%, finalization starts at 90%
                    
                    # Broadcast finalizing status immediately
                    self._broadcast_progress(experiment_id)
                    
                    # Save results to preset/results directory
                    # This returns the result file path if successful, None otherwise
                    result_file = self._save_final_results(experiment_id, progress)
                    
                    # Only mark as completed if results file was successfully saved
                    if result_file and result_file.exists():
                        progress.status = "completed"
                        progress.finalization_phase = "Results saved successfully"
                        progress.finalization_percentage = 10.0
                        progress.overall_percentage = 100.0
                        progress.end_time = time.time()
                        logger.success(f"✓ Experiment {experiment_id} completed - results ready at {result_file}")
                    else:
                        # File save failed - mark as error
                        progress.status = "error"
                        progress.finalization_phase = "Failed to save results file"
                        progress.error_message = "Results file could not be saved or verified"
                        progress.end_time = time.time()
                        logger.error(f"✗ Experiment {experiment_id} failed: results file not saved")
                    
                    # Broadcast final status (completed or error)
                    self._broadcast_progress(experiment_id)
                else:
                    # Broadcast progress for this thread completion
                    self._broadcast_progress(experiment_id)
            
        except Exception as e:
            logger.error(f"Error in worker thread {thread_id}: {e}")
            logger.error(traceback.format_exc())
            
            # Mark thread as errored but still count as completed
            with self.completion_locks.get(experiment_id, threading.Lock()):
                if experiment_id in self.experiments:
                    progress = self.experiments[experiment_id]
                    thread_progress = progress.threads.get(thread_id)
                    if thread_progress:
                        thread_progress.status = "error"
                        thread_progress.error_message = str(e)
                    
                    # Mark as completed (even with error) so experiment can finish
                    if experiment_id in self.completed_threads:
                        self.completed_threads[experiment_id].add(thread_id)
                        
                        # Check if all threads are done (including errored ones)
                        all_threads_done = len(self.completed_threads[experiment_id]) == len(progress.threads)
                        if all_threads_done and progress.status == "running":
                            logger.warning(f"All threads completed for {experiment_id} (some with errors), finalizing...")
                            
                            # Set to finalizing before saving
                            progress.status = "finalizing"
                            progress.finalization_phase = "Computing results (with errors)..."
                            progress.finalization_percentage = 0.0
                            progress.overall_percentage = 90.0
                            self._broadcast_progress(experiment_id)
                            
                            # Save results with progress tracking
                            self._save_final_results(experiment_id, progress)
                            
                            # Mark as completed
                            progress.status = "completed"
                            progress.finalization_percentage = 10.0
                            progress.overall_percentage = 100.0
                            progress.end_time = time.time()
                            self._broadcast_progress(experiment_id)
                    
                    self._broadcast_progress(experiment_id)
    
    def _scenario_worker_thread(self, experiment_id: str, thread_id: str,
                                 category_idx: int, category: str,
                                 config: Dict, base_path: Path, results_path: Path):
        """
        Worker thread for scenario mode that processes one route category.
        
        Each thread handles:
        - One route category (short, medium, or long)
        - 10 routes per category
        - 10 disruption scenarios (DS1-DS10) per route
        - 3 severity levels (light, medium, heavy) per scenario
        - Total: 10 × 10 × 3 = 300 simulations per thread
        
        Args:
            experiment_id: Experiment identifier
            thread_id: Thread identifier (thread_0, thread_1, thread_2)
            category_idx: Category index (0=short, 1=medium, 2=long)
            category: Category name ("short", "medium", "long")
            config: Experiment configuration
            base_path: Base path for experiment data
            results_path: Path for saving results
        """
        try:
            progress = self.experiments[experiment_id]
            thread_progress = progress.threads[thread_id]
            
            algorithms = config.get("algorithms", ["DHL", "HC2L"])
            tau_settings = config.get("tau_settings", {})
            routes = config.get("routes", [])
            
            # Filter routes for this category
            category_routes = [r for r in routes if r.get("category") == category]
            
            if not category_routes:
                logger.warning(f"No routes found for category '{category}' in thread {thread_id}")
                thread_progress.status = "error"
                thread_progress.error_message = f"No routes for category '{category}'"
                self._broadcast_progress(experiment_id)
                return
            
            routes_per_category = len(category_routes)
            scenarios = list(DISRUPTION_SCENARIOS.keys())  # DS1 to DS10
            severity_levels = list(SEVERITY_LEVELS.keys())  # light, medium, heavy
            
            # Total simulations for this thread: routes × scenarios × severities × algorithms
            total_simulations = routes_per_category * len(scenarios) * len(severity_levels) * len(algorithms)
            
            # Update thread progress
            thread_progress.status = "running"
            thread_progress.total_routes = total_simulations
            thread_progress.trial_number = f"{category.capitalize()}"  # Use category as trial name
            
            logger.info(f"Thread {thread_id} starting: {routes_per_category} {category} routes × {len(scenarios)} scenarios × {len(severity_levels)} severities × {len(algorithms)} algorithms = {total_simulations} simulations")
            
            # Get disruption cache
            cache = self.disruption_caches.get(experiment_id)
            
            # Process routes
            start_time = time.time()
            completed = 0
            
            for route_idx, route_data in enumerate(category_routes):
                if self.stop_events[experiment_id].is_set():
                    break
                
                thread_progress.batch_number = f"Route {route_idx + 1}/{routes_per_category}"
                
                for scenario_idx, scenario_id in enumerate(scenarios):
                    if self.stop_events[experiment_id].is_set():
                        break
                    
                    scenario_info = DISRUPTION_SCENARIOS[scenario_id]
                    
                    for severity_idx, severity_level in enumerate(severity_levels):
                        if self.stop_events[experiment_id].is_set():
                            break
                        
                        # Wait if paused
                        self.pause_events[experiment_id].wait()
                        
                        # Compute batch_idx for disruption cache: encodes scenario and severity
                        # batch_idx = scenario_idx * 3 + severity_idx
                        batch_idx = scenario_idx * 3 + severity_idx
                        
                        # Load disruption (lazy generation)
                        disruption_data = None
                        if cache:
                            disruption_data = cache.load_disruption(batch_idx, route_idx, thread_id)
                        
                        # Update progress with current scenario info
                        severity_info = SEVERITY_LEVELS[severity_level]
                        thread_progress.current_disruption_level = severity_info["name"]
                        thread_progress.current_disruption = f"{scenario_id}_{severity_level}_route_{route_idx}"
                        
                        for algorithm in algorithms:
                            if self.stop_events[experiment_id].is_set():
                                break
                            
                            thread_progress.algorithm = algorithm
                            thread_progress.current_route_index = completed
                            thread_progress.route_progress = f"{completed + 1}/{total_simulations}"
                            
                            # Execute route computation with scenario-specific route data
                            result = self._execute_route(
                                experiment_id, thread_id, category_idx, batch_idx, route_idx,
                                algorithm, tau_settings, disruption_data, config,
                                route_override=route_data  # Pass specific route data
                            )
                            
                            # Record metrics
                            if experiment_id in self.metrics_collectors:
                                metrics_collector = self.metrics_collectors[experiment_id]
                                
                                # Add scenario metadata to result
                                result["scenario_id"] = scenario_id
                                result["scenario_name"] = scenario_info["name"]
                                result["severity_level"] = severity_level
                                result["route_category"] = category
                                
                                record = metrics_collector.record_route_metric(
                                    trial=category_idx,  # Use category index as trial
                                    batch=batch_idx,
                                    route=route_idx,
                                    algorithm=algorithm,
                                    api_result=result,
                                    disruption_data=disruption_data
                                )
                            
                            # Update progress
                            completed += 1
                            thread_progress.current_route_index = completed
                            thread_progress.percentage = (completed / total_simulations) * 100
                            
                            # Calculate throughput
                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                thread_progress.routes_per_minute = (completed / elapsed) * 60
                                remaining_simulations = total_simulations - completed
                                remaining_time = remaining_simulations / (completed / elapsed)
                                thread_progress.estimated_time_remaining = self._format_time(remaining_time)
                            
                            # Get route node information from result
                            route_coords = result.get("route_coords", {})
                            start_node = route_coords.get("start_node", 0)
                            end_node = route_coords.get("end_node", 0)
                            start_edge_target = route_coords.get("start_edge_target", 0)
                            end_edge_target = route_coords.get("end_edge_target", 0)
                            
                            # Get road names for start and end nodes
                            start_road_name = "Unknown Road"
                            end_road_name = "Unknown Road"
                            
                            if self.road_mapper:
                                try:
                                    start_road_name = self.road_mapper.get_road_name(start_node, start_edge_target)
                                    end_road_name = self.road_mapper.get_road_name(end_node, end_edge_target)
                                except Exception as e:
                                    logger.debug(f"Error getting road names: {e}")
                            
                            # Update query phase with accumulated statistics
                            query_time = result.get("query_phase", {}).get("query_time_ms", 0)
                            label_size = result.get("summary", {}).get("label_size", 0)
                            labeling_time = result.get("summary", {}).get("labeling_time_ms", 0)
                            
                            # Track success/failure
                            accuracy = result.get("accuracy", {})
                            if accuracy.get("is_correct", False):
                                thread_progress.successful_routes += 1
                            else:
                                thread_progress.failed_routes += 1
                            
                            # Update running averages (only for successful routes)
                            if accuracy.get("is_correct", False):
                                current_count = thread_progress.successful_routes
                                if current_count > 0:
                                    thread_progress.avg_query_time_ms = (
                                        (thread_progress.avg_query_time_ms * (current_count - 1) + query_time) / current_count
                                    )
                                    thread_progress.avg_labeling_time_ms = (
                                        (thread_progress.avg_labeling_time_ms * (current_count - 1) + labeling_time) / current_count
                                    )
                                    thread_progress.avg_labeling_size_mb = (
                                        (thread_progress.avg_labeling_size_mb * (current_count - 1) + label_size) / current_count
                                    )
                            
                            distance_km = result.get("summary", {}).get("distance_km", 0)
                            actual_eta = result.get("summary", {}).get("actual_eta", "")
                            
                            # Initialize query history if not exists
                            if not hasattr(thread_progress, 'query_times'):
                                thread_progress.query_times = []
                                thread_progress.label_sizes = []
                            
                            # Add to query history
                            thread_progress.query_times.append(query_time)
                            thread_progress.label_sizes.append(label_size)
                            
                            # Calculate statistics from accumulated data
                            if thread_progress.query_times:
                                import statistics
                                thread_progress.query_phase = {
                                    "algorithm": algorithm,
                                    "query_time_ms": query_time,
                                    "avg_query_time_ms": statistics.mean(thread_progress.query_times),
                                    "min_query_time_ms": min(thread_progress.query_times),
                                    "max_query_time_ms": max(thread_progress.query_times),
                                    "std_dev": statistics.stdev(thread_progress.query_times) if len(thread_progress.query_times) > 1 else 0,
                                    "p95_latency_ms": sorted(thread_progress.query_times)[int(len(thread_progress.query_times) * 0.95)] if len(thread_progress.query_times) > 1 else query_time,
                                    "queries_count": len(thread_progress.query_times)
                                }
                            else:
                                thread_progress.query_phase = result.get("query_phase", {})
                            
                            # Update last result with route information
                            last_result = result.get("summary", {})
                            last_result["start_node"] = start_node
                            last_result["end_node"] = end_node
                            last_result["start_road_name"] = start_road_name
                            last_result["end_road_name"] = end_road_name
                            last_result["scenario"] = scenario_id
                            last_result["severity"] = severity_level
                            last_result["category"] = category
                            thread_progress.last_result = last_result
                            thread_progress.update_phase = result.get("update_phase", {})
                            
                            # Update results history (limit to 5)
                            thread_progress.results_history.append({
                                "query_number": completed,
                                "timestamp": datetime.now().isoformat(),
                                "start_node": start_node,
                                "end_node": end_node,
                                "start_road_name": start_road_name,
                                "end_road_name": end_road_name,
                                "scenario": scenario_id,
                                "severity": severity_level,
                                "category": category,
                                "algorithm": algorithm,
                                "query_time_ms": query_time,
                                "distance_km": distance_km,
                                "actual_eta": actual_eta
                            })
                            if len(thread_progress.results_history) > 5:
                                thread_progress.results_history.pop(0)
                            
                            # Update overall progress
                            progress.completed_routes = sum(
                                t.current_route_index for t in progress.threads.values()
                            )
                            thread_task_percentage = (progress.completed_routes / progress.total_routes) * 90
                            progress.overall_percentage = thread_task_percentage + progress.finalization_percentage
                            
                            # Broadcast update
                            self._broadcast_progress(experiment_id)
            
            # Thread completed - use lock to ensure atomic completion checking
            with self.completion_locks[experiment_id]:
                thread_progress.status = "completed"
                thread_progress.percentage = 100.0
                
                # Mark this thread as completed
                self.completed_threads[experiment_id].add(thread_id)
                
                logger.success(f"Scenario thread {thread_id} ({category}) completed for experiment {experiment_id} ({len(self.completed_threads[experiment_id])}/{len(progress.threads)} threads done)")
                
                # Check if all threads completed (atomic check)
                all_threads_done = len(self.completed_threads[experiment_id]) == len(progress.threads)
                
                if all_threads_done:
                    logger.info(f"All scenario threads completed for {experiment_id}, finalizing...")
                    
                    # Set status to finalizing
                    progress.status = "finalizing"
                    progress.finalization_phase = "Computing results..."
                    progress.finalization_percentage = 0.0
                    progress.overall_percentage = 90.0
                    
                    self._broadcast_progress(experiment_id)
                    
                    # Save results
                    result_file = self._save_final_results(experiment_id, progress)
                    
                    if result_file and result_file.exists():
                        progress.status = "completed"
                        progress.finalization_phase = "Results saved successfully"
                        progress.finalization_percentage = 10.0
                        progress.overall_percentage = 100.0
                        progress.end_time = time.time()
                        logger.success(f"✓ Scenario experiment {experiment_id} completed - results ready at {result_file}")
                    else:
                        progress.status = "error"
                        progress.finalization_phase = "Failed to save results file"
                        progress.error_message = "Results file could not be saved or verified"
                        progress.end_time = time.time()
                        logger.error(f"✗ Scenario experiment {experiment_id} failed: results file not saved")
                    
                    self._broadcast_progress(experiment_id)
                else:
                    self._broadcast_progress(experiment_id)
                    
        except Exception as e:
            logger.error(f"Error in scenario worker thread {thread_id} ({category}): {e}")
            logger.error(traceback.format_exc())
            
            with self.completion_locks.get(experiment_id, threading.Lock()):
                if experiment_id in self.experiments:
                    progress = self.experiments[experiment_id]
                    thread_progress = progress.threads.get(thread_id)
                    if thread_progress:
                        thread_progress.status = "error"
                        thread_progress.error_message = str(e)
                    
                    if experiment_id in self.completed_threads:
                        self.completed_threads[experiment_id].add(thread_id)
                        
                        all_threads_done = len(self.completed_threads[experiment_id]) == len(progress.threads)
                        if all_threads_done and progress.status == "running":
                            logger.warning(f"All scenario threads completed for {experiment_id} (some with errors), finalizing...")
                            
                            progress.status = "finalizing"
                            progress.finalization_phase = "Computing results (with errors)..."
                            progress.finalization_percentage = 0.0
                            progress.overall_percentage = 90.0
                            self._broadcast_progress(experiment_id)
                            
                            self._save_final_results(experiment_id, progress)
                            
                            progress.status = "completed"
                            progress.finalization_percentage = 10.0
                            progress.overall_percentage = 100.0
                            progress.end_time = time.time()
                            self._broadcast_progress(experiment_id)
                    
                    self._broadcast_progress(experiment_id)

    def _compute_dijkstra_ground_truth(self, experiment_id: str, batch_idx: int, 
                                       route_idx: int, route_coords: Dict,
                                       disruption_path: str) -> Optional[float]:
        """
        Compute Dijkstra ground truth distance for accuracy validation.
        Uses C++ path finding with disruptions applied (same as HC2L/HC2L).
        Results are cached to avoid recomputation across trials.
        
        Args:
            experiment_id: Experiment identifier
            batch_idx: Batch index
            route_idx: Route index
            route_coords: Route coordinates dict with start/end snap data
            disruption_path: Path to disruption directory
            
        Returns:
            Ground truth distance in km, or None if computation failed
        """
        import hashlib
        
        # Create cache key based on route and disruption
        disruption_hash = hashlib.md5(disruption_path.encode()).hexdigest()[:8] if disruption_path else "no_disruption"
        cache_key = f"{experiment_id}_{batch_idx}_{route_idx}_{disruption_hash}"
        
        # Check cache first
        with self.dijkstra_cache_lock:
            if cache_key in self.dijkstra_cache:
                cached = self.dijkstra_cache[cache_key]
                # logger.debug(f"Dijkstra cache hit: {cache_key} = {cached['distance_km']} km")
                return cached['distance_km']
        
        # Compute using HC2L router (which uses Dijkstra for path reconstruction)
        # We use HC2L instead of DHL because we need pure distance without label overhead
        try:
            if not self.hc2l_router:
                logger.error("HC2L router not initialized for Dijkstra computation")
                return None
            
            # Call HC2L API to get ground truth distance
            api_result = self.hc2l_router.compute_route(
                start_pin_lat=route_coords["start"]["lat"],
                start_pin_lng=route_coords["start"]["lng"],
                dest_pin_lat=route_coords["end"]["lat"],
                dest_pin_lng=route_coords["end"]["lng"],
                start_snap_lat=route_coords["start"]["snap_lat"],
                start_snap_lng=route_coords["start"]["snap_lng"],
                dest_snap_lat=route_coords["end"]["snap_lat"],
                dest_snap_lng=route_coords["end"]["snap_lng"],
                start_edge_source=route_coords["start"]["edge_source"],
                start_edge_target=route_coords["start"]["edge_target"],
                start_edge_oneway=route_coords["start"]["edge_oneway"],
                dest_edge_source=route_coords["end"]["edge_source"],
                dest_edge_target=route_coords["end"]["edge_target"],
                dest_edge_oneway=route_coords["end"]["edge_oneway"],
                disruption_file=disruption_path,
                tau_threshold=1.0,  # Use tau=1.0 for immediate full update (ground truth)
                generate_alternatives=False,
                verbose=False
            )
            
            if not api_result.get("success", False):
                logger.warning(f"Dijkstra computation failed for route {route_idx}: {api_result.get('error')}")
                return None
            
            # Extract distance from API result
            metrics = api_result.get("metrics", {})
            distance_km = metrics.get("calculated_distance_km", 0)
            
            if not distance_km and metrics.get("calculated_distance_meters"):
                distance_km = metrics.get("calculated_distance_meters") / 1000
            
            if distance_km <= 0:
                logger.warning(f"Invalid Dijkstra distance for route {route_idx}: {distance_km} km")
                return None
            
            # Cache the result
            with self.dijkstra_cache_lock:
                self.dijkstra_cache[cache_key] = {
                    "distance_km": distance_km,
                    "computed_at": time.time()
                }
            
            # logger.debug(f"Dijkstra computed and cached: {cache_key} = {distance_km} km")
            return distance_km
            
        except Exception as e:
            logger.error(f"Error computing Dijkstra ground truth: {e}")
            return None
    
    def _execute_route(self, experiment_id: str, thread_id: str,
                       trial_idx: int, batch_idx: int, route_idx: int,
                       algorithm: str, tau_settings: Dict,
                       disruption_data: Optional[Dict], config: Dict,
                       route_override: Optional[Dict] = None) -> Dict:
        """
        Execute a single route computation.
        
        Args:
            route_override: Optional route data to use instead of config routes
                           (used in scenario mode with pre-defined routes)
        
        Returns:
            Dict containing route result with all metrics
        """
        start_time = time.time()
        
        # Generate tau value based on settings
        tau = self._generate_tau(tau_settings, trial_idx, route_idx)
        
        # Get route coordinates (from override, preset, or generate random)
        if route_override:
            route_coords = self._get_route_coordinates_from_data(route_override)
        else:
            route_coords = self._get_route_coordinates(config, route_idx)
        
        result = {
            "experiment_id": experiment_id,
            "thread_id": thread_id,
            "trial": trial_idx,
            "batch": batch_idx,
            "route": route_idx,
            "algorithm": algorithm,
            "tau": tau,
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "update_phase": {},
            "query_phase": {},
            "route_coords": {
                "start_node": route_coords["start"]["edge_source"],
                "end_node": route_coords["end"]["edge_source"],
                "start_edge_target": route_coords["start"]["edge_target"],
                "end_edge_target": route_coords["end"]["edge_target"]
            },
            "error": None
        }
        
        try:
            # Get disruption path for C++ API
            disruption_path = ""
            if disruption_data:
                disruption_path = disruption_data.get("path", "")
            
            # ========================================================================
            # STEP 1: Execute HC2L/HC2L query
            # ========================================================================
            api_result = None
            if algorithm.upper() == "DHL":
                if self.dhl_router:
                    api_result = self.dhl_router.compute_route(
                        start_pin_lat=route_coords["start"]["lat"],
                        start_pin_lng=route_coords["start"]["lng"],
                        dest_pin_lat=route_coords["end"]["lat"],
                        dest_pin_lng=route_coords["end"]["lng"],
                        start_snap_lat=route_coords["start"]["snap_lat"],
                        start_snap_lng=route_coords["start"]["snap_lng"],
                        dest_snap_lat=route_coords["end"]["snap_lat"],
                        dest_snap_lng=route_coords["end"]["snap_lng"],
                        start_edge_source=route_coords["start"]["edge_source"],
                        start_edge_target=route_coords["start"]["edge_target"],
                        start_edge_oneway=route_coords["start"]["edge_oneway"],
                        dest_edge_source=route_coords["end"]["edge_source"],
                        dest_edge_target=route_coords["end"]["edge_target"],
                        dest_edge_oneway=route_coords["end"]["edge_oneway"],
                        disruption_file=disruption_path,
                        tau_threshold=tau,
                        generate_alternatives=False,
                        verbose=False
                    )
                else:
                    result["error"] = "DHL router not initialized"
                    
            elif algorithm.upper() == "HC2L":
                if self.hc2l_router:
                    api_result = self.hc2l_router.compute_route(
                        start_pin_lat=route_coords["start"]["lat"],
                        start_pin_lng=route_coords["start"]["lng"],
                        dest_pin_lat=route_coords["end"]["lat"],
                        dest_pin_lng=route_coords["end"]["lng"],
                        start_snap_lat=route_coords["start"]["snap_lat"],
                        start_snap_lng=route_coords["start"]["snap_lng"],
                        dest_snap_lat=route_coords["end"]["snap_lat"],
                        dest_snap_lng=route_coords["end"]["snap_lng"],
                        start_edge_source=route_coords["start"]["edge_source"],
                        start_edge_target=route_coords["start"]["edge_target"],
                        start_edge_oneway=route_coords["start"]["edge_oneway"],
                        dest_edge_source=route_coords["end"]["edge_source"],
                        dest_edge_target=route_coords["end"]["edge_target"],
                        dest_edge_oneway=route_coords["end"]["edge_oneway"],
                        disruption_file=disruption_path,
                        tau_threshold=tau,
                        generate_alternatives=False,
                        verbose=False
                    )
                else:
                    result["error"] = "HC2L router not initialized"
            else:
                result["error"] = f"Unknown algorithm: {algorithm}"
            
            # Parse the API result first
            if api_result:
                result = self._parse_api_result(result, api_result, algorithm, tau)
            
            # ========================================================================
            # STEP 2: Compute Dijkstra ground truth for accuracy validation
            # ========================================================================
            if not result.get("error") and api_result and api_result.get("success"):
                dijkstra_distance = self._compute_dijkstra_ground_truth(
                    experiment_id, batch_idx, route_idx, 
                    route_coords, disruption_path
                )
                
                if dijkstra_distance:
                    # Extract HC2L/HC2L distance
                    dhc2l_distance = result["summary"].get("distance_km", 0)
                    
                    # ========================================================================
                    # STEP 3: Compute accuracy metrics
                    # ========================================================================
                    distance_error = dhc2l_distance - dijkstra_distance  # Positive = overestimate, negative = underestimate
                    relative_error = abs(distance_error) / dijkstra_distance if dijkstra_distance > 0 else 1.0
                    is_correct = relative_error <= 0.05  # 5% tolerance
                    
                    # Store accuracy metrics in result
                    result["accuracy"] = {
                        "dijkstra_distance_km": round(dijkstra_distance, 4),
                        "dhc2l_distance_km": round(dhc2l_distance, 4),
                        "distance_error_km": round(distance_error, 4),
                        "relative_error": round(relative_error, 4),
                        "is_correct": is_correct,
                        "tolerance": 0.05
                    }
                    
                    # logger.debug(
                    #     f"Route {route_idx} accuracy: "
                    #     f"HC2L={dhc2l_distance:.3f}km, "
                    #     f"Dijkstra={dijkstra_distance:.3f}km, "
                    #     f"Error={relative_error*100:.2f}%, "
                    #     f"Correct={is_correct}"
                    # )
                else:
                    # If Dijkstra computation failed, mark as incorrect
                    result["accuracy"] = {
                        "dijkstra_distance_km": None,
                        "dhc2l_distance_km": result["summary"].get("distance_km", 0),
                        "distance_error_km": None,
                        "relative_error": None,
                        "is_correct": False,
                        "tolerance": 0.05,
                        "error": "Dijkstra computation failed"
                    }
            else:
                # If HC2L computation failed, mark as incorrect
                result["accuracy"] = {
                    "dijkstra_distance_km": None,
                    "dhc2l_distance_km": None,
                    "distance_error_km": None,
                    "relative_error": None,
                    "is_correct": False,
                    "tolerance": 0.05,
                    "error": result.get("error", "HC2L computation failed")
                }
                
        except Exception as e:
            result["error"] = str(e)
            result["accuracy"] = {
                "dijkstra_distance_km": None,
                "dhc2l_distance_km": None,
                "distance_error_km": None,
                "relative_error": None,
                "is_correct": False,
                "tolerance": 0.05,
                "error": str(e)
            }
            logger.error(f"Error executing route: {e}")
        
        # Calculate total execution time
        result["execution_time_ms"] = (time.time() - start_time) * 1000
        
        return result
    
    def _parse_api_result(self, result: Dict, api_result: Dict, 
                          algorithm: str, tau: float) -> Dict:
        """
        Parse C++ API result into standardized format.
        Based on actual DHL.json and HC2L.json output structure.
        """
        if not api_result.get("success", False):
            result["error"] = api_result.get("error", "Unknown error")
            return result
        
        # Extract data from API response (matches DHL.json and HC2L.json structure)
        metrics = api_result.get("metrics", {})
        route_data = api_result.get("route", {})
        labeling_info = metrics.get("labeling_info", {})
        disruptions_summary = api_result.get("disruptions_summary", {})
        route_disruptions = disruptions_summary.get("route", {})
        
        # Algorithm-specific data
        lazy_hc2l = api_result.get("lazy_hc2l", {})
        dhl_update_info = api_result.get("dhl_update_info", {})
        
        # Calculate distance in km from meters
        calculated_dist_m = metrics.get("calculated_distance_meters", 0)
        distance_km = calculated_dist_m / 1000 if calculated_dist_m else 0
        
        # Extract ETA information
        eta_seconds = metrics.get("eta_seconds", 0)
        eta_formatted = metrics.get("eta_formatted", "")
        if not eta_formatted and eta_seconds:
            eta_formatted = self._format_seconds(eta_seconds)
        
        baseline_eta = ""
        actual_eta = eta_formatted
        time_impact_seconds = route_disruptions.get("total_time_impact_seconds", 0)
        
        # Get baseline and actual ETA from disruptions_summary
        if route_disruptions.get("baseline_eta_seconds"):
            baseline_seconds = route_disruptions.get("baseline_eta_seconds")
            baseline_eta = self._format_seconds(baseline_seconds)
        if route_disruptions.get("actual_eta_seconds"):
            actual_seconds = route_disruptions.get("actual_eta_seconds")
            actual_eta = self._format_seconds(actual_seconds)
        
        # Calculate label size in MB
        label_size_mb = 0
        if labeling_info.get("index_size_mb"):
            label_size_mb = labeling_info.get("index_size_mb")
        elif labeling_info.get("index_size_bytes"):
            label_size_mb = labeling_info.get("index_size_bytes") / (1024 * 1024)
        
        # Extract memory usage information
        memory_usage = metrics.get("memory_usage", {})
        memory_initial_mb = memory_usage.get("initial_mb", 0)
        memory_current_mb = memory_usage.get("current_mb", 0)
        memory_peak_mb = memory_usage.get("peak_mb", 0)
        memory_increase_mb = memory_usage.get("increase_mb", 0)
        
        # Summary
        result["summary"] = {
            "route": "Start → End",
            "algorithm": algorithm,
            "path_length": metrics.get("path_length", 0),  # Number of nodes in path
            "query_time_ms": round(metrics.get("query_time_ms", 0), 3),
            "distance_km": round(distance_km, 2) if distance_km else 0,
            "index_load_time_ms": round(labeling_info.get("index_load_time_ms", 0), 3),
            "baseline_eta": baseline_eta,
            "actual_eta": actual_eta,
            "max_cut_size": labeling_info.get("max_cut_size", 0),
            "time_impact_seconds": round(time_impact_seconds, 1) if time_impact_seconds else 0,
            "non_empty_cuts": labeling_info.get("non_empty_cuts", 0),
            "label_size": round(label_size_mb, 2),  # In MB
            "tau": round(tau, 3),
            "disrupted_edges": route_disruptions.get("total_disrupted_edges", 0),
            "memory_initial_mb": round(memory_initial_mb, 2),
            "memory_current_mb": round(memory_current_mb, 2),
            "memory_peak_mb": round(memory_peak_mb, 2),
            "memory_increase_mb": round(memory_increase_mb, 2),
            # Add missing fields for CSV export
            "eta_seconds": round(eta_seconds, 2) if eta_seconds else 0,
            "labeling_time_ms": round(labeling_info.get("labeling_time_ms", 0), 3)
        }
        
        # Update Phase - extract from lazy_hc2l or dhl_update_info
        if algorithm.upper() == "HC2L":
            update_strategy = lazy_hc2l.get("update_strategy", "N/A")
            lazy_update_time = lazy_hc2l.get("lazy_repair_time_ms", 0)
            nodes_repaired = lazy_hc2l.get("nodes_repaired", 0)
            dirty_nodes = lazy_hc2l.get("dirty_nodes_marked", 0)
            impact_score = lazy_hc2l.get("disruption_impact_score", 0)
            threshold_rebuild_time = lazy_hc2l.get("threshold_rebuild_time_ms", 0)  # Extract from HC2L output
            
            result["update_phase"] = {
                "status": "lazy_repair" if update_strategy == "lazy_marking" else "immediate_update",
                "lazy_update_time_ms": round(lazy_update_time, 3) if lazy_update_time else 0,
                "update_strategy": update_strategy,
                "max_label_size": labeling_info.get("max_label_count_per_node", 0),
                "min_label_size": 0,  # Not provided in API
                "nodes_repaired": nodes_repaired if nodes_repaired is not None else 0,
                "dirty_nodes": dirty_nodes if dirty_nodes is not None else 0,
                "impact_score": round(impact_score, 3) if isinstance(impact_score, (int, float)) else 0,
                "threshold_rebuild_time_ms": round(threshold_rebuild_time, 3) if threshold_rebuild_time else 0
            }
        else:  # DHL
            nodes_updated = dhl_update_info.get("nodes_updated", 0)
            impact_score = dhl_update_info.get("disruption_impact_score", 1.0)
            threshold_rebuild_time = dhl_update_info.get("threshold_rebuild_time_ms", 0)  # Extract from DHL output
            
            result["update_phase"] = {
                "status": "immediate_update",
                "lazy_update_time_ms": 0,  # DHL always does immediate update
                "update_strategy": dhl_update_info.get("update_strategy", "immediate_update"),
                "max_label_size": labeling_info.get("max_label_count_per_node", 0),
                "min_label_size": 0,  # Not provided in API
                "nodes_repaired": nodes_updated if nodes_updated is not None else 0,
                "dirty_nodes": 0,  # DHL doesn't use dirty nodes
                "impact_score": round(impact_score, 3) if isinstance(impact_score, (int, float)) else 1.0,
                "threshold_rebuild_time_ms": round(threshold_rebuild_time, 3) if threshold_rebuild_time else 0
            }
        
        # Query Phase - single query statistics (will be accumulated in thread)
        query_time_ms = metrics.get("query_time_ms", 0)
        result["query_phase"] = {
            "algorithm": algorithm,
            "query_time_ms": round(query_time_ms, 3) if query_time_ms else 0,
            "avg_query_time_ms": round(query_time_ms, 3) if query_time_ms else 0,
            "min_query_time_ms": round(query_time_ms, 3) if query_time_ms else 0,
            "max_query_time_ms": round(query_time_ms, 3) if query_time_ms else 0,
            "std_dev": 0,  # Single query, no deviation
            "p95_latency_ms": round(query_time_ms, 3) if query_time_ms else 0,
            "queries_count": 1
        }
        
        # Construction info - extracted from labeling_info for first route of each trial
        # Use index_load_time_ms (time to load index = construction time for that trial)
        construction_time = labeling_info.get("index_load_time_ms", 0)
        if not construction_time:
            # Fallback to other fields if index_load_time_ms not available
            construction_time = labeling_info.get("construction_time_ms", 0)
            if not construction_time:
                construction_time = labeling_info.get("labeling_time_ms", 0)
        
        result["construction_info"] = {
            "construction_time_ms": construction_time,
            "label_size_mb": label_size_mb,
            "index_load_time_ms": labeling_info.get("index_load_time_ms", 0)
        }
        
        # Extract route path coordinates for Frechet distance calculation
        path_coords = []
        geometry = route_data.get("geometry", [])
        if geometry:
            for segment in geometry:
                coords = segment.get("coordinates", [])
                if coords:
                    path_coords.extend(coords)
        
        result["path_coordinates"] = path_coords
        
        # Store metrics for accuracy computation
        # Extract distance fields needed by metrics collector
        result["metrics"] = {
            "calculated_distance_meters": metrics.get("calculated_distance_meters", 0),
            "dijkstra_distance_meter": metrics.get("dijkstra_distance_meter", 0),
            "path_length": metrics.get("path_length", 0),
            "query_time_ms": metrics.get("query_time_ms", 0),
            "eta_seconds": metrics.get("eta_seconds", 0),
            "labeling_info": labeling_info
        }
        
        # Store GPS mapping for source/target nodes
        result["gps_mapping"] = api_result.get("gps_mapping", {})
        
        # Store success flag
        result["success"] = True

        return result
    
    def _format_seconds(self, seconds: float) -> str:
        """Format seconds into human-readable string (e.g., '5m 30s')"""
        if not seconds:
            return ""
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def _save_final_results(self, experiment_id: str, progress: ExperimentProgress = None) -> Optional[Path]:
        """
        Save final results using the new metrics collector finalize() method.
        Exports all CSVs and generates minimal JSON configuration file.
        
        Reports progress through simplified phases:
        1. Exporting CSV files (0-60%)
        2. Generating JSON results (60-90%)
        3. Finalizing (90-100%)
        
        Returns:
            Path to the saved results folder if successful, None otherwise.
        """
        try:
            logger.info(f"Starting to save final results for {experiment_id}...")
            
            if experiment_id not in self.experiments:
                logger.warning(f"Experiment {experiment_id} not found in experiments dict")
                return None
            
            if progress is None:
                progress = self.experiments[experiment_id]
            
            # Get metrics collector
            if experiment_id not in self.metrics_collectors:
                logger.warning(f"No metrics collector found for {experiment_id}")
                return None
            
            collector = self.metrics_collectors[experiment_id]
            logger.info(f"Metrics collector ready with {collector.trials} trials, {collector.batches} batches")
            
            # Check if scenario mode
            is_scenario = collector.is_scenario_mode
            logger.info(f"Export mode: {'scenario' if is_scenario else 'standard'}")
            
            # ============================================================================
            # Phase 1: Exporting CSV files (0-60%)
            # ============================================================================
            progress.finalization_phase = "Phase 1/3: Exporting CSV files..."
            progress.finalization_percentage = 0.0
            progress.overall_percentage = 90.0
            self._broadcast_progress(experiment_id)
            
            logger.info("Exporting all CSV files...")
            
            csv_files = {}
            
            if is_scenario:
                # Scenario mode: Use scenario-specific export
                progress.finalization_phase = "Phase 1/3: Exporting scenario CSV files..."
                self._broadcast_progress(experiment_id)
                
                csv_files = collector.export_scenario_csvs()
                logger.info(f"✓ Exported scenario CSV files")
                
                # Also export standard files for backward compatibility
                csv_files["summary_standard"] = collector.export_summary_csv()
                csv_files["accuracy_standard"] = collector.export_accuracy_csv()
                csv_files["construction_standard"] = collector.export_construction_csv()
                csv_files["updates_standard"] = collector.export_updates_csv()
                csv_files["performance_standard"] = collector.export_performance_csv()
                csv_files["similarity_standard"] = collector.export_similarity_csv()
                logger.info(f"✓ Exported standard CSV files for backward compatibility")
            else:
                # Standard mode: Export each CSV file individually with progress updates
                csv_exports = [
                    ("summary", "summary_results.csv", 10),
                    ("accuracy", "accuracy_results.csv", 20),
                    ("construction", "construction_results.csv", 30),
                    ("updates", "updates_results.csv", 40),
                    ("performance", "performance_results.csv", 50),
                    ("similarity", "similarity_results.csv", 60)
                ]
                
                for csv_name, csv_filename, percent in csv_exports:
                    progress.finalization_phase = f"Phase 1/3: Exporting {csv_filename}..."
                    progress.finalization_percentage = percent / 10.0  # Scale to 0-10%
                    progress.overall_percentage = 90.0 + (progress.finalization_percentage * 0.6)  # 0-60% of 10%
                    self._broadcast_progress(experiment_id)
                    
                    if csv_name == "summary":
                        csv_files[csv_name] = collector.export_summary_csv()
                    elif csv_name == "accuracy":
                        csv_files[csv_name] = collector.export_accuracy_csv()
                    elif csv_name == "construction":
                        csv_files[csv_name] = collector.export_construction_csv()
                    elif csv_name == "updates":
                        csv_files[csv_name] = collector.export_updates_csv()
                    elif csv_name == "performance":
                        csv_files[csv_name] = collector.export_performance_csv()
                    elif csv_name == "similarity":
                        csv_files[csv_name] = collector.export_similarity_csv()
                    
                    logger.info(f"✓ Exported {csv_filename}")
            
            # ============================================================================
            # Phase 2: Generating JSON results (60-90%)
            # ============================================================================
            progress.finalization_phase = "Phase 2/3: Generating JSON results..."
            progress.finalization_percentage = 6.0
            progress.overall_percentage = 90.0 + (progress.finalization_percentage * 0.1)  # 60% of 10%
            self._broadcast_progress(experiment_id)
            
            # Prepare experiment configuration for JSON
            experiment_config = {
                "experiment_id": experiment_id,
                "experiment_name": progress.experiment_name,
                "trials": collector.trials,
                "batches": collector.batches,
                "routes_per_batch": collector.routes_per_batch,
                "preset_type": "scenario" if is_scenario else "standard",
                "start_time": progress.start_time,
                "end_time": progress.end_time,
                "duration_seconds": progress.end_time - progress.start_time if progress.end_time > 0 else 0,
                "thread_count": progress.thread_count
            }
            
            logger.info("Generating JSON results file...")
            json_path = collector.generate_results_json(experiment_config)
            logger.info(f"✓ Generated JSON results: {json_path}")
            
            # ============================================================================
            # Phase 3: Finalizing (90-100%)
            # ============================================================================
            progress.finalization_phase = "Phase 3/3: Finalizing..."
            progress.finalization_percentage = 9.0
            progress.overall_percentage = 90.0 + (progress.finalization_percentage * 0.1)  # 90% of 10%
            self._broadcast_progress(experiment_id)
            
            # Verify all files were created
            results_folder = collector.results_path
            if not results_folder.exists():
                logger.error(f"Results folder does not exist: {results_folder}")
                return None
            
            # Verify JSON file exists and is readable
            if not json_path.exists():
                logger.error(f"JSON results file does not exist: {json_path}")
                return None
            
            try:
                with open(json_path, 'r') as f:
                    test_data = json.load(f)
                    if not test_data.get("metadata"):
                        logger.error(f"JSON results file is invalid or incomplete: {json_path}")
                        return None
            except Exception as verify_error:
                logger.error(f"Failed to verify JSON results file: {verify_error}")
                return None
            
            # Log summary
            logger.success(f"✓ Saved final results to {results_folder}")
            logger.success(f"  - JSON: {json_path.name}")
            for csv_name, csv_path in csv_files.items():
                logger.success(f"  - CSV ({csv_name}): {csv_path.name}")
            
            return json_path
            
        except Exception as e:
            logger.error(f"Failed to save final results for {experiment_id}: {e}")
            logger.error(traceback.format_exc())
            
            # Update finalization phase with error
            if experiment_id in self.experiments:
                progress_obj = self.experiments[experiment_id]
                progress_obj.finalization_phase = f"Error: {str(e)}"
            
            return None

    
    def _generate_tau(self, tau_settings: Dict, trial_idx: int, route_idx: int) -> float:
        """Generate tau value based on settings"""
        mode = tau_settings.get("mode", "random")
        scope = tau_settings.get("scope", "per-trial-route")
        
        if mode == "fixed":
            return tau_settings.get("fixed", 0.5)
        
        # Random mode
        min_tau = tau_settings.get("random_min", 0.1)
        max_tau = tau_settings.get("random_max", 0.9)
        
        # Use seed based on scope for reproducibility
        import random
        if scope == "all":
            seed = 42
        elif scope == "per-trial":
            seed = trial_idx
        elif scope == "per-route":
            seed = route_idx
        else:  # per-trial-route
            seed = trial_idx * 1000 + route_idx
        
        random.seed(seed)
        return round(random.uniform(min_tau, max_tau), 3)
    
    def _get_route_coordinates(self, config: Dict, route_idx: int) -> Dict:
        """Get route coordinates from preset or generate random"""
        routes = config.get("routes", [])
        generation_mode = config.get("generation_mode", "different_batch")
        
        # For same_batch mode, reuse the same 1000 routes across all batches
        # by wrapping the route index modulo the total available routes
        if generation_mode == "same_batch" and len(routes) > 0:
            actual_route_idx = route_idx % len(routes)
        else:
            actual_route_idx = route_idx
        
        if actual_route_idx < len(routes):
            route = routes[actual_route_idx]
            start_data = route.get("start", {})
            end_data = route.get("end", {})
            
            # Extract edge values for debugging
            start_edge_source = start_data.get("edge_source", 0)
            start_edge_target = start_data.get("edge_target", 0)
            end_edge_source = end_data.get("edge_source", 0)
            end_edge_target = end_data.get("edge_target", 0)
            
            # Log if edges are missing (only for first few routes to avoid spam)
            if actual_route_idx < 5 and (start_edge_source == 0 or end_edge_source == 0):
                logger.warning(f"Route {actual_route_idx}: Missing edge data - start_edge={start_edge_source}, end_edge={end_edge_source}")
                logger.debug(f"Route {actual_route_idx} start_data keys: {list(start_data.keys())}")
                logger.debug(f"Route {actual_route_idx} end_data keys: {list(end_data.keys())}")
            
            # Extract coordinates with proper fallbacks
            # Support both pin_lat/pin_lng and lat/lng formats
            return {
                "start": {
                    "lat": start_data.get("pin_lat", start_data.get("snap_lat", start_data.get("lat", 14.65))),
                    "lng": start_data.get("pin_lng", start_data.get("snap_lng", start_data.get("lng", 121.05))),
                    "snap_lat": start_data.get("snap_lat", start_data.get("pin_lat", start_data.get("lat", 14.65))),
                    "snap_lng": start_data.get("snap_lng", start_data.get("pin_lng", start_data.get("lng", 121.05))),
                    "edge_source": start_edge_source,
                    "edge_target": start_edge_target,
                    "edge_oneway": start_data.get("edge_oneway", 0)
                },
                "end": {
                    "lat": end_data.get("pin_lat", end_data.get("snap_lat", end_data.get("lat", 14.66))),
                    "lng": end_data.get("pin_lng", end_data.get("snap_lng", end_data.get("lng", 121.06))),
                    "snap_lat": end_data.get("snap_lat", end_data.get("pin_lat", end_data.get("lat", 14.66))),
                    "snap_lng": end_data.get("snap_lng", end_data.get("pin_lng", end_data.get("lng", 121.06))),
                    "edge_source": end_edge_source,
                    "edge_target": end_edge_target,
                    "edge_oneway": end_data.get("edge_oneway", 0)
                }
            }
        
        # Generate random coordinates within Quezon City bounds
        import random
        random.seed(route_idx)
        
        return {
            "start": {
                "lat": random.uniform(14.60, 14.72),
                "lng": random.uniform(121.02, 121.10),
                "snap_lat": random.uniform(14.60, 14.72),
                "snap_lng": random.uniform(121.02, 121.10),
                "edge_source": 0,
                "edge_target": 0,
                "edge_oneway": 0
            },
            "end": {
                "lat": random.uniform(14.60, 14.72),
                "lng": random.uniform(121.02, 121.10),
                "snap_lat": random.uniform(14.60, 14.72),
                "snap_lng": random.uniform(121.02, 121.10),
                "edge_source": 0,
                "edge_target": 0,
                "edge_oneway": 0
            }
        }
    
    def _get_route_coordinates_from_data(self, route_data: Dict) -> Dict:
        """
        Extract route coordinates from a pre-defined route data dictionary.
        Used in scenario mode where routes are passed directly.
        
        Args:
            route_data: Route data dictionary with start/end coordinates
            
        Returns:
            Dict with start and end coordinate objects
        """
        start_data = route_data.get("start", {})
        end_data = route_data.get("end", {})
        
        return {
            "start": {
                "lat": start_data.get("pin_lat", start_data.get("snap_lat", start_data.get("lat", 14.65))),
                "lng": start_data.get("pin_lng", start_data.get("snap_lng", start_data.get("lng", 121.05))),
                "snap_lat": start_data.get("snap_lat", start_data.get("pin_lat", start_data.get("lat", 14.65))),
                "snap_lng": start_data.get("snap_lng", start_data.get("pin_lng", start_data.get("lng", 121.05))),
                "edge_source": start_data.get("edge_source", 0),
                "edge_target": start_data.get("edge_target", 0),
                "edge_oneway": start_data.get("edge_oneway", 0)
            },
            "end": {
                "lat": end_data.get("pin_lat", end_data.get("snap_lat", end_data.get("lat", 14.66))),
                "lng": end_data.get("pin_lng", end_data.get("snap_lng", end_data.get("lng", 121.06))),
                "snap_lat": end_data.get("snap_lat", end_data.get("pin_lat", end_data.get("lat", 14.66))),
                "snap_lng": end_data.get("snap_lng", end_data.get("pin_lng", end_data.get("lng", 121.06))),
                "edge_source": end_data.get("edge_source", 0),
                "edge_target": end_data.get("edge_target", 0),
                "edge_oneway": end_data.get("edge_oneway", 0)
            }
        }

    # def _save_progress(self, experiment_id: str, results_path: Path):
    #     """Save progress to progress.json file"""
    #     progress = self.experiments.get(experiment_id)
    #     if not progress:
    #         return
        
    #     progress_file = results_path / "progress.json"
    #     try:
    #         with open(progress_file, 'w') as f:
    #             json.dump(progress.to_dict(), f, indent=2)
    #     except Exception as e:
    #         logger.error(f"Error saving progress: {e}")
    
    # def _save_result(self, experiment_id: str, thread_id: str, 
    #                  result: Dict, results_path: Path):
    #     """Save individual route result to file"""
    #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    #     result_file = results_path / f"result_{thread_id}_{timestamp}.json"
        
    #     try:
    #         with open(result_file, 'w') as f:
    #             json.dump(result, f, indent=2)
    #     except Exception as e:
    #         logger.error(f"Error saving result: {e}")
    
    def _broadcast_progress(self, experiment_id: str):
        """Broadcast progress update via WebSocket and save to file"""
        progress = self.experiments.get(experiment_id)
        if not progress:
            return
        
        # Update HERE comparison progress from metrics collector
        if experiment_id in self.metrics_collectors:
            try:
                here_progress = self.metrics_collectors[experiment_id].get_here_comparison_progress()
                progress.here_comparison = here_progress
            except Exception as e:
                logger.debug(f"Error getting HERE comparison progress: {e}")
        
        # Calculate overall estimated time remaining based on thread progress
        try:
            total_remaining_seconds = 0
            active_threads = 0
            for thread in progress.threads.values():
                if thread.status == "running" and thread.total_routes > 0:
                    completed = thread.current_route_index
                    if completed > 0:
                        elapsed = time.time() - progress.start_time
                        rate = completed / elapsed  # routes per second
                        remaining = thread.total_routes - completed
                        if rate > 0:
                            total_remaining_seconds = max(total_remaining_seconds, remaining / rate)
                            active_threads += 1
            
            if active_threads > 0 and total_remaining_seconds > 0:
                progress.estimated_time_remaining = self._format_time(total_remaining_seconds)
        except Exception as e:
            logger.debug(f"Error calculating overall ETA: {e}")
        
        # # Save progress to file if results_path is available
        # if progress.results_path:
        #     try:
        #         self._save_progress(experiment_id, progress.results_path)
        #     except Exception as e:
        #         logger.error(f"Error saving progress to file: {e}")
        
        # Broadcast via WebSocket
        if not self.socketio:
            return
        
        try:
            self.socketio.emit(
                'progress_update',
                progress.to_dict(),
                room=experiment_id,
                namespace='/experiment'
            )
        except Exception as e:
            logger.error(f"Error broadcasting progress: {e}")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds into human-readable time string"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"


# ============================================================================
# WEBSOCKET NAMESPACE
# ============================================================================

class ExperimentNamespace(Namespace):
    """WebSocket namespace for experiment status updates"""
    
    def __init__(self, experiment_runner: ExperimentRunner):
        super().__init__('/experiment')
        self.experiment_runner = experiment_runner
    
    def on_connect(self):
        """Handle client connection"""
        logger.info("WebSocket client connected to /experiment namespace")
    
    def on_disconnect(self):
        """Handle client disconnection"""
        logger.info("WebSocket client disconnected from /experiment namespace")
    
    def on_join(self, data):
        """Handle client joining an experiment room"""
        experiment_id = data.get('experiment_id')
        if experiment_id:
            join_room(experiment_id)
            logger.info(f"Client joined room: {experiment_id}")
            
            # Check if this is a new experiment that needs to start
            if experiment_id in self.experiment_runner.experiments:
                progress = self.experiment_runner.experiments[experiment_id]
                
                # If experiment is in initializing state, start the actual work now
                if progress.status == "initializing":
                    logger.info(f"Starting experiment work for {experiment_id} after WebSocket connection")
                    # Start the actual experiment work in a separate thread
                    import threading
                    work_thread = threading.Thread(
                        target=self.experiment_runner._start_experiment_work,
                        args=(experiment_id,)
                    )
                    work_thread.daemon = True
                    work_thread.start()
                else:
                    # Send current progress for existing experiment
                    emit('progress_update', progress.to_dict())
    
    def on_leave(self, data):
        """Handle client leaving an experiment room"""
        experiment_id = data.get('experiment_id')
        if experiment_id:
            leave_room(experiment_id)
            logger.info(f"Client left room: {experiment_id}")


# ============================================================================
# FLASK BLUEPRINT
# ============================================================================

experiment_bp = Blueprint('experiment', __name__, url_prefix='/api/experiment')

# Global experiment runner instance (initialized later)
experiment_runner: Optional[ExperimentRunner] = None


def init_experiment_runner(socketio: SocketIO, hc2l_router, dhl_router, node_mapper) -> ExperimentRunner:
    """Initialize the experiment runner with dependencies"""
    global experiment_runner
    
    experiment_runner = ExperimentRunner(socketio)
    experiment_runner.set_routers(hc2l_router, dhl_router, node_mapper)
    
    # Register WebSocket namespace
    socketio.on_namespace(ExperimentNamespace(experiment_runner))
    
    logger.success("Experiment runner initialized with WebSocket support")
    return experiment_runner


@experiment_bp.route('/start', methods=['POST'])
def start_experiment():
    """Start a new experiment"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    config = request.get_json() or {}
    result = experiment_runner.start_experiment(config)
    
    return jsonify(result)


@experiment_bp.route('/<experiment_id>/pause', methods=['POST'])
def pause_experiment(experiment_id):
    """Pause a running experiment"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.pause_experiment(experiment_id)
    return jsonify(result)


@experiment_bp.route('/<experiment_id>/stop', methods=['POST'])
def stop_experiment(experiment_id):
    """Stop a running experiment"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.stop_experiment(experiment_id)
    return jsonify(result)


@experiment_bp.route('/<experiment_id>/resume', methods=['POST'])
def resume_experiment(experiment_id):
    """Resume a paused experiment"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.resume_experiment(experiment_id)
    return jsonify(result)


@experiment_bp.route('/<experiment_id>/progress', methods=['GET'])
def get_progress(experiment_id):
    """Get current experiment progress (HTTP fallback)"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.get_progress(experiment_id)
    return jsonify(result)


@experiment_bp.route('/<experiment_id>/result', methods=['GET'])
def get_result(experiment_id):
    """Get final experiment results"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.get_result(experiment_id)
    return jsonify(result)


@experiment_bp.route('/<experiment_id>/metrics', methods=['GET'])
def get_metrics(experiment_id):
    """Get real-time metrics summary"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.get_metrics_summary(experiment_id)
    return jsonify(result)


@experiment_bp.route('/preset/list', methods=['GET', 'POST'])
def list_presets():
    """List all preset experiments"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.list_presets()
    return jsonify(result)


@experiment_bp.route('/preset/metadata', methods=['GET'])
def get_preset_metadata():
    """Get preset experiment metadata"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    result = experiment_runner.get_preset_metadata()
    return jsonify(result)


@experiment_bp.route('/preset/create', methods=['POST'])
def create_preset():
    """Create or update preset experiment"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    config = request.get_json() or {}
    result = experiment_runner.create_preset(config)
    return jsonify(result)


@experiment_bp.route('/cleanup', methods=['POST'])
def cleanup_temporary():
    """Clean up temporary experiments"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    data = request.get_json() or {}
    experiment_id = data.get('experiment_id')
    
    result = experiment_runner.cleanup_temporary(experiment_id)
    return jsonify(result)


@experiment_bp.route('/results/list', methods=['GET'])
def list_saved_results():
    """List all saved experiment results from new folder structure"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        results_list = []
        
        # NEW: Iterate through experiment folders (e.g., exp_1767755097_234648b9/)
        for exp_folder in results_dir.iterdir():
            if not exp_folder.is_dir():
                continue
                
            # Look for experiment_results.json inside each folder
            result_file = exp_folder / "experiment_results.json"
            
            if not result_file.exists():
                continue
                
            try:
                with open(result_file, 'r') as f:
                    result_data = json.load(f)
                    
                # Extract metadata and summary info from NEW JSON structure
                metadata = result_data.get("metadata", {})
                summary = result_data.get("summary", {})
                config = result_data.get("configuration", {})
                
                results_list.append({
                    "id": exp_folder.name,  # Use folder name as ID (e.g., exp_1767755097_234648b9)
                    "filename": result_file.name,
                    "timestamp": metadata.get("end_time", result_file.stat().st_mtime),
                    "date": metadata.get("end_time_iso", ""),
                    "trials": config.get("trials", 0),
                    "batches": config.get("batches_per_trial", 0),
                    "routes_per_batch": config.get("routes_per_batch", 0),
                    "total_routes": metadata.get("total_routes", 0),
                    "duration_seconds": metadata.get("duration_seconds", 0),
                    "completed": 100.0  # All saved results are completed
                })
            except Exception as e:
                logger.error(f"Error reading result file {result_file}: {e}")
                continue
        
        # Sort by timestamp (newest first)
        results_list.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return jsonify({
            "success": True,
            "results": results_list,
            "count": len(results_list)
        })
    except Exception as e:
        logger.error(f"Error listing saved results: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@experiment_bp.route('/results/<result_id>', methods=['GET'])
def get_saved_result(result_id):
    """Get a specific saved experiment result from new folder structure"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        
        # NEW: Look for experiment_results.json inside the experiment folder
        exp_folder = results_dir / result_id
        result_file = exp_folder / "experiment_results.json"
        
        if not result_file.exists():
            return jsonify({"success": False, "error": f"Result not found: {result_file}"}), 404
        
        with open(result_file, 'r') as f:
            result_data = json.load(f)
        
        return jsonify({
            "success": True,
            "result": result_data
        })
    except Exception as e:
        logger.error(f"Error retrieving saved result {result_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@experiment_bp.route('/results/<result_id>/csv/<csv_type>', methods=['GET'])
def download_result_csv(result_id, csv_type):
    """
    Download a specific CSV file from saved experiment results.
    
    Args:
        result_id: Result folder name (timestamp-based)
        csv_type: One of 'summary', 'accuracy', 'construction', 'updates', 'performance', 'similarity'
    
    Returns:
        CSV file download or error
    """
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    # Map CSV types to filenames
    csv_files = {
        'summary': 'summary_results.csv',
        'accuracy': 'accuracy_results.csv',
        'construction': 'construction_results.csv',
        'updates': 'updates_results.csv',
        'performance': 'performance_results.csv',
        'similarity': 'similarity_results.csv'
    }
    
    if csv_type not in csv_files:
        return jsonify({"success": False, "error": f"Invalid CSV type: {csv_type}"}), 400
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        
        # Try direct result_id as folder name first
        csv_path = results_dir / result_id / csv_files[csv_type]
        
        # If not found, try with .json extension (result_id might be JSON filename)
        if not csv_path.exists():
            # Extract timestamp from result_id if it has .json extension
            result_folder = result_id.replace('.json', '').replace('experiment_', '')
            csv_path = results_dir / result_folder / csv_files[csv_type]
        
        if not csv_path.exists():
            return jsonify({"success": False, "error": f"CSV file not found: {csv_files[csv_type]}"}), 404
        
        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{result_id}_{csv_files[csv_type]}"
        )
    except Exception as e:
        logger.error(f"Error downloading CSV {csv_type} for result {result_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@experiment_bp.route('/results/<result_id>/csv/<csv_type>/export', methods=['GET'])
def export_result_csv(result_id, csv_type):
    """
    Export a specific CSV file or aggregated subset from saved experiment results.
    
    For table_type='all': Downloads a ZIP file containing per-route, per-trial, and per-batch CSVs
    
    Args:
        result_id: Result folder name (timestamp-based)
        csv_type: One of 'summary', 'accuracy', 'construction', 'updates', 'performance', 'similarity'
    
    Query params:
        table_type: Type of export - 'all', 'per-trial', 'per-batch', 'per-route' (default: 'all')
    
    Returns:
        CSV file download or ZIP file with multiple CSVs
    """
    import csv as csv_module
    import io
    import zipfile
    
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    # Get table_type from query parameter
    table_type = request.args.get('table_type', 'all')
    
    # Validate table_type
    valid_table_types = ['all', 'per-trial', 'per-batch', 'per-route']
    if table_type not in valid_table_types:
        return jsonify({"success": False, "error": f"Invalid table_type: {table_type}. Must be one of: {', '.join(valid_table_types)}"}), 400
    
    # Map CSV types to filenames
    csv_files = {
        'summary': 'summary_results.csv',
        'accuracy': 'accuracy_results.csv',
        'construction': 'construction_results.csv',
        'updates': 'updates_results.csv',
        'performance': 'performance_results.csv',
        'similarity': 'similarity_results.csv'
    }
    
    if csv_type not in csv_files:
        return jsonify({"success": False, "error": f"Invalid CSV type: {csv_type}"}), 400
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        
        # Try direct result_id as folder name first
        csv_path = results_dir / result_id / csv_files[csv_type]
        
        # If not found, try with .json extension (result_id might be JSON filename)
        if not csv_path.exists():
            result_folder = result_id.replace('.json', '').replace('experiment_', '')
            csv_path = results_dir / result_folder / csv_files[csv_type]
        
        if not csv_path.exists():
            return jsonify({"success": False, "error": f"CSV file not found: {csv_files[csv_type]}"}), 404
        
        # For 'all': Create ZIP with per-route, per-trial, and per-batch
        if table_type == 'all':
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 1. Add per-route CSV (complete file)
                zip_file.write(csv_path, arcname=f"{csv_type}_per-route.csv")
                
                # 2. Add per-trial CSV (aggregated)
                per_trial_csv = _generate_aggregated_csv(csv_path, 'per-trial', csv_type)
                zip_file.writestr(f"{csv_type}_per-trial.csv", per_trial_csv)
                
                # 3. Add per-batch CSV (aggregated)
                per_batch_csv = _generate_aggregated_csv(csv_path, 'per-batch', csv_type)
                zip_file.writestr(f"{csv_type}_per-batch.csv", per_batch_csv)
            
            zip_buffer.seek(0)
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name=f"{result_id}_{csv_type}_all-tables.zip"
            )
        
        # For 'per-route', return the complete CSV file as-is
        if table_type == 'per-route':
            return send_file(
                csv_path,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f"{result_id}_{csv_type}_per-route.csv"
            )
        
        # For per-trial or per-batch, aggregate the data and return as CSV
        if table_type in ['per-trial', 'per-batch']:
            csv_content = _generate_aggregated_csv(csv_path, table_type, csv_type)
            
            csv_bytes = io.BytesIO(csv_content.encode('utf-8'))
            csv_bytes.seek(0)
            
            return send_file(
                csv_bytes,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f"{result_id}_{csv_type}_{table_type}.csv"
            )
        
    except Exception as e:
        logger.error(f"Error exporting CSV {csv_type} ({table_type}) for result {result_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _generate_aggregated_csv(csv_path, table_type, csv_type):
    """
    Helper function to generate aggregated CSV content (per-trial or per-batch)
    
    Args:
        csv_path: Path to the original CSV file
        table_type: 'per-trial' or 'per-batch'
        csv_type: Type of CSV (summary, accuracy, etc.)
    
    Returns:
        CSV content as string
    """
    import csv as csv_module
    import io
    
    aggregated_rows = []
    headers = []
    
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv_module.DictReader(f)
        headers = reader.fieldnames or []
        all_rows = list(reader)
    
    if table_type == 'per-trial':
        # Aggregate by trial_id
        trial_groups = {}
        for row in all_rows:
            trial_id = row.get('trial_id', 'unknown')
            if trial_id not in trial_groups:
                trial_groups[trial_id] = []
            trial_groups[trial_id].append(row)
        
        # Calculate averages for each trial
        for trial_id, trial_rows in sorted(trial_groups.items(), key=lambda x: str(x[0])):
            aggregated_row = {'trial_id': trial_id}
            
            # Get non-numeric fields from first row
            first_row = trial_rows[0]
            for key in ['algorithm', 'disruption_level', 'disruption_type']:
                if key in first_row:
                    aggregated_row[key] = first_row[key]
            
            # Average numeric fields
            numeric_keys = [k for k in headers if k not in ['trial_id', 'batch_id', 'query_id', 'route_id', 
                                                              'algorithm', 'disruption_level', 'disruption_type',
                                                              'route_index', 'source', 'target']]
            for key in numeric_keys:
                values = []
                for row in trial_rows:
                    try:
                        val = float(row.get(key, 0))
                        values.append(val)
                    except (ValueError, TypeError):
                        pass
                if values:
                    aggregated_row[key] = f"{np.mean(values):.4f}"
                else:
                    aggregated_row[key] = 'N/A'
            
            # Add count
            aggregated_row['count'] = len(trial_rows)
            aggregated_rows.append(aggregated_row)
        
        # Update headers for per-trial
        headers = ['trial_id', 'algorithm', 'disruption_level', 'disruption_type'] + \
                 [k for k in numeric_keys if k in aggregated_rows[0] if aggregated_rows] + ['count']
    
    elif table_type == 'per-batch':
        # Aggregate by batch_id (within each trial)
        batch_groups = {}
        for row in all_rows:
            trial_id = row.get('trial_id', 'unknown')
            batch_id = row.get('batch_id', 'unknown')
            key = f"{trial_id}_{batch_id}"
            if key not in batch_groups:
                batch_groups[key] = []
            batch_groups[key].append(row)
        
        # Calculate averages for each batch
        for key, batch_rows in sorted(batch_groups.items()):
            aggregated_row = {
                'trial_id': batch_rows[0].get('trial_id', 'unknown'),
                'batch_id': batch_rows[0].get('batch_id', 'unknown')
            }
            
            # Get non-numeric fields from first row
            first_row = batch_rows[0]
            for field in ['algorithm', 'disruption_level', 'disruption_type']:
                if field in first_row:
                    aggregated_row[field] = first_row[field]
            
            # Average numeric fields
            numeric_keys = [k for k in headers if k not in ['trial_id', 'batch_id', 'query_id', 'route_id',
                                                              'algorithm', 'disruption_level', 'disruption_type',
                                                              'route_index', 'source', 'target']]
            for key in numeric_keys:
                values = []
                for row in batch_rows:
                    try:
                        val = float(row.get(key, 0))
                        values.append(val)
                    except (ValueError, TypeError):
                        pass
                if values:
                    aggregated_row[key] = f"{np.mean(values):.4f}"
                else:
                    aggregated_row[key] = 'N/A'
            
            # Add count
            aggregated_row['count'] = len(batch_rows)
            aggregated_rows.append(aggregated_row)
        
        # Update headers for per-batch
        headers = ['trial_id', 'batch_id', 'algorithm', 'disruption_level', 'disruption_type'] + \
                 [k for k in numeric_keys if k in aggregated_rows[0] if aggregated_rows] + ['count']
    
    # Generate CSV from aggregated data
    output = io.StringIO()
    writer = csv_module.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(aggregated_rows)
    
    return output.getvalue()




@experiment_bp.route('/results/<result_id>/csv/<csv_type>/data', methods=['GET'])
def get_result_csv_data(result_id, csv_type):
    """
    Get CSV data as JSON for displaying in tables.
    Supports pagination for large datasets.
    
    Args:
        result_id: Result folder name
        csv_type: One of 'summary', 'accuracy', 'construction', 'updates', 'performance', 'similarity'
    
    Query params:
        page: Page number (1-indexed, default 1)
        limit: Records per page (default 50, max 500)
        filter_trial: Filter by trial_id
        filter_batch: Filter by batch_id
        filter_algorithm: Filter by algorithm
    
    Returns:
        JSON with headers, data rows, and pagination info
    """
    import csv as csv_module
    
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    # Map CSV types to filenames
    csv_files = {
        'summary': 'summary_results.csv',
        'accuracy': 'accuracy_results.csv',
        'construction': 'construction_results.csv',
        'updates': 'updates_results.csv',
        'performance': 'performance_results.csv',
        'similarity': 'similarity_results.csv'
    }
    
    if csv_type not in csv_files:
        return jsonify({"success": False, "error": f"Invalid CSV type: {csv_type}"}), 400
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        csv_path = results_dir / result_id / csv_files[csv_type]
        
        if not csv_path.exists():
            return jsonify({"success": False, "error": f"CSV file not found: {csv_files[csv_type]}"}), 404
        
        # Parse query parameters
        page = max(1, int(request.args.get('page', 1)))
        limit = min(500, max(1, int(request.args.get('limit', 50))))
        filter_trial = request.args.get('filter_trial')
        filter_batch = request.args.get('filter_batch')
        filter_algorithm = request.args.get('filter_algorithm')
        
        # Read CSV file
        all_rows = []
        headers = []
        with open(csv_path, 'r', newline='') as f:
            reader = csv_module.DictReader(f)
            headers = reader.fieldnames or []
            for row in reader:
                # Apply filters if specified
                if filter_trial and str(row.get('trial_id', '')) != filter_trial:
                    continue
                if filter_batch and str(row.get('batch_id', '')) != filter_batch:
                    continue
                if filter_algorithm and row.get('algorithm', '').upper() != filter_algorithm.upper():
                    continue
                all_rows.append(row)
        
        # Calculate pagination
        total_rows = len(all_rows)
        total_pages = max(1, (total_rows + limit - 1) // limit)
        start_idx = (page - 1) * limit
        end_idx = min(start_idx + limit, total_rows)
        
        # Get page data
        page_data = all_rows[start_idx:end_idx]
        
        return jsonify({
            "success": True,
            "csv_type": csv_type,
            "headers": headers,
            "data": page_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_rows": total_rows,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting CSV data {csv_type} for result {result_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@experiment_bp.route('/results/<result_id>', methods=['DELETE'])
def delete_saved_result(result_id):
    """Delete a saved experiment result folder and all its contents"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        
        # NEW: Delete the entire experiment folder (includes JSON + all 6 CSVs)
        exp_folder = results_dir / result_id
        
        if not exp_folder.exists():
            return jsonify({"success": False, "error": f"Result folder not found: {result_id}"}), 404
        
        # Delete folder and all contents recursively (shutil already imported at top)
        shutil.rmtree(exp_folder)
        
        logger.info(f"Deleted experiment result folder: {exp_folder}")
        
        return jsonify({
            "success": True,
            "message": f"Result {result_id} deleted successfully (JSON + 6 CSVs)"
        })
    except Exception as e:
        logger.error(f"Error deleting saved result {result_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

