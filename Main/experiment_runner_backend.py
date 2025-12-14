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
from pathlib import Path
from datetime import datetime
from collections import OrderedDict
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty as QueueEmpty

from flask import Blueprint, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, Namespace

from config import Config
from console_formatter import get_logger

# Import shared road network utilities (no HTTP calls needed)
from road_network_utils import (
    generate_routes_with_snap_data,
    snap_location_to_edge_data,
    get_random_road_points_data
)

# Get logger instance
logger = get_logger("ExperimentRunner")

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
    current_route_index: int = 0
    total_routes: int = 0
    routes_per_minute: float = 0.0
    estimated_time_remaining: str = ""
    last_result: Dict = field(default_factory=dict)
    update_phase: Dict = field(default_factory=dict)
    query_phase: Dict = field(default_factory=dict)
    results_history: List[Dict] = field(default_factory=list)
    error_message: str = ""


@dataclass
class ExperimentProgress:
    """Overall experiment progress tracking"""
    experiment_id: str
    experiment_name: str = ""
    status: str = "initializing"  # initializing/running/paused/completed/error/stopped
    overall_percentage: float = 0.0
    total_routes: int = 0
    completed_routes: int = 0
    estimated_time_remaining: str = ""
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
    error_message: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert ThreadProgress objects to dicts
        data['threads'] = {k: asdict(v) if hasattr(v, '__dict__') else v 
                          for k, v in self.threads.items()}
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
    
    def __init__(self, base_path: Path, is_preset: bool = True, disruption_settings: Dict = None):
        self.base_path = base_path
        self.is_preset = is_preset
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
        
    def get_disruption_path(self, batch_idx: int, route_idx: int) -> Path:
        """Get path to disruption set based on preset/temporary mode"""
        if self.is_preset:
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
            
            # Get settings
            ratio_flow = self.disruption_settings.get("ratio_flow", 95)
            ratio_incident = self.disruption_settings.get("ratio_incident", 5)
            severity_min = self.disruption_settings.get("severity_min", 0.1)
            severity_max = self.disruption_settings.get("severity_max", 0.9)
            
            # Get edges for disruption generation
            edges = self._get_matched_edges()
            if not edges:
                logger.warning("No matched edges available for disruption generation")
                return
            
            # Randomly select number of disruptions (5-20)
            total_disruptions = random.randint(5, 20)
            flow_count = int(total_disruptions * ratio_flow / 100)
            incident_count = total_disruptions - flow_count
            
            # Ensure at least 1 of each if ratios allow
            if ratio_flow > 0 and flow_count == 0:
                flow_count = 1
            if ratio_incident > 0 and incident_count == 0:
                incident_count = 1
            
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
                
                severity = random.uniform(severity_min, severity_max)
                jam_factor = severity * 10  # 0-10 scale
                free_flow_kph = float(edge.get('free_flow_speed', 60))
                flow_speed = max(5.0, free_flow_kph * (1.0 - (jam_factor / 10.0)))
                
                flow_rows.append({
                    'id_hash': f'exp_{batch_idx}_{route_idx}_{i}',
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
            incident_types = ['accident', 'construction', 'roadClosure', 'hazard']
            
            for edge in edges:
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
                
                incident_rows.append({
                    'source': edge.get('source'),
                    'target': edge.get('target'),
                    'source_lat': edge.get('source_lat'),
                    'source_lon': edge.get('source_lon'),
                    'target_lat': edge.get('target_lat'),
                    'target_lon': edge.get('target_lon'),
                    'incident_id': f'exp_{batch_idx}_{route_idx}_{len(incident_rows)}',
                    'incident_type': random.choice(incident_types),
                    'incident_criticality': criticality,
                    'incident_description': f'Experiment incident on {edge.get("road_name", "road")}',
                    'incident_road_closed': severity > 0.8,
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
    - Results saved as individual JSON files
    """
    
    def __init__(self, socketio: SocketIO = None):
        self.socketio = socketio
        self.experiments: Dict[str, ExperimentProgress] = {}
        self.experiment_threads: Dict[str, List[threading.Thread]] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.pause_events: Dict[str, threading.Event] = {}
        self.disruption_caches: Dict[str, DisruptionCacheManager] = {}
        
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
        
        logger.success("ExperimentRunner initialized")
        logger.info(f"Preset path: {self.preset_path}")
        logger.info(f"Temporary path: {self.temporary_path}")
    
    def _ensure_preset_config(self):
        """Ensure ExperimentPreset.json exists with default configuration and pre-generated routes"""
        preset_file = self.preset_path / "ExperimentPreset.json"
        
        if preset_file.exists():
            logger.info("ExperimentPreset.json already exists")
            return
        
        logger.info("Creating default ExperimentPreset.json with 3000 pre-generated routes...")
        
        # Generate 3000 routes with full snap data (1000 per batch × 3 batches)
        routes = self._generate_preset_routes(3000)
        
        if not routes:
            logger.error("Failed to generate preset routes")
            return
        
        # Create default preset configuration with routes
        default_preset = {
            "id": "default",
            "name": "Default Experiment Preset",
            "description": "Default experiment configuration with 3 trials, 3 batches, 1000 routes per batch",
            "algorithms": ["DHL", "HC2L"],
            "trial_count": 3,
            "batch_count": 3,
            "routes_per_batch": 1000,
            "routes": routes,  # Pre-generated routes with full snap data
            "tau_settings": {
                "mode": "random",
                "scope": "per-trial-route",
                "fixed": 0.5,
                "random_min": 0.1,
                "random_max": 0.9
            },
            "disruption_settings": {
                "ratio_flow": 95,
                "ratio_incident": 5,
                "severity_min": 0.1,
                "severity_max": 0.9
            },
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat()
        }
        
        try:
            with open(preset_file, 'w') as f:
                json.dump(default_preset, f, indent=2)
            logger.success(f"Created default ExperimentPreset.json with {len(routes)} pre-generated routes")
        except Exception as e:
            logger.error(f"Failed to create ExperimentPreset.json: {e}")
    
    def _generate_preset_routes(self, count):
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
            # Use shared utility function (direct data access, no HTTP)
            routes = generate_routes_with_snap_data(
                count=count,
                node_mapper=self.node_mapper,
                progress_callback=lambda done, total: logger.info(f"Route generation progress: {done}/{total}")
            )
            return routes
            
        except Exception as e:
            logger.error(f"Error generating preset routes: {e}")
            import traceback
            traceback.print_exc()
            return []
    
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
            
            # Determine base path
            if is_preset:
                base_path = self.preset_path
            else:
                base_path = self.temporary_path / experiment_id
                base_path.mkdir(parents=True, exist_ok=True)
            
            # Create results directory
            results_path = base_path / "results" / experiment_id
            results_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize progress tracking
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
            
            self.experiments[experiment_id] = progress
            
            # Initialize disruption cache with settings from config
            disruption_settings = config.get("disruption_settings", {
                "ratio_flow": 95,
                "ratio_incident": 5,
                "severity_min": 0.1,
                "severity_max": 0.9
            })
            self.disruption_caches[experiment_id] = DisruptionCacheManager(
                base_path, 
                is_preset=is_preset,
                disruption_settings=disruption_settings
            )
            
            # Initialize control events
            self.stop_events[experiment_id] = threading.Event()
            self.pause_events[experiment_id] = threading.Event()
            self.pause_events[experiment_id].set()  # Not paused initially
            
            # Save initial progress
            self._save_progress(experiment_id, results_path)
            
            # Start worker threads
            self._start_worker_threads(experiment_id, config, base_path, results_path)
            
            # Update status
            progress.status = "running"
            self._broadcast_progress(experiment_id)
            
            logger.success(f"Started experiment {experiment_id} with {thread_count} threads")
            
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
        if progress.status not in ["running", "paused"]:
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
        """Get final experiment results"""
        if experiment_id not in self.experiments:
            return {"success": False, "error": "Experiment not found"}
        
        progress = self.experiments[experiment_id]
        
        # Load result files
        results = []
        is_preset = experiment_id.startswith("preset_") or not experiment_id.startswith("exp_")
        
        if is_preset:
            results_path = self.preset_path / "results" / experiment_id
        else:
            results_path = self.temporary_path / experiment_id / "results"
        
        if results_path.exists():
            for result_file in sorted(results_path.glob("result_*.json")):
                try:
                    with open(result_file, 'r') as f:
                        results.append(json.load(f))
                except Exception as e:
                    logger.error(f"Error loading result file {result_file}: {e}")
        
        return {
            "success": True,
            "experiment_id": experiment_id,
            "status": progress.status,
            "total_routes": progress.total_routes,
            "completed_routes": progress.completed_routes,
            "results": results
        }
    
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
        trials = config.get("trials", 3)
        batches_per_trial = config.get("batches_per_trial", 3)
        routes_per_batch = config.get("routes_per_batch", 1000)
        algorithms = config.get("algorithms", ["DHL", "HC2L"])
        
        return trials * batches_per_trial * routes_per_batch * len(algorithms)
    
    def _start_worker_threads(self, experiment_id: str, config: Dict, 
                              base_path: Path, results_path: Path):
        """Start worker threads for experiment execution"""
        progress = self.experiments[experiment_id]
        thread_count = progress.thread_count
        
        trials = config.get("trials", 3)
        batches_per_trial = config.get("batches_per_trial", 3)
        routes_per_batch = config.get("routes_per_batch", 1000)
        algorithms = config.get("algorithms", ["DHL", "HC2L"])
        
        threads = []
        
        if thread_count == 3:
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
                        
                        # Save result
                        self._save_result(experiment_id, thread_id, result, results_path)
                        
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
                        
                        # Update last result
                        thread_progress.last_result = result.get("summary", {})
                        thread_progress.update_phase = result.get("update_phase", {})
                        thread_progress.query_phase = result.get("query_phase", {})
                        
                        # Add to history (limit to 10)
                        thread_progress.results_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "route": f"Route {route_idx}",
                            "algorithm": algorithm,
                            "query_time_ms": result.get("query_phase", {}).get("query_time_ms", 0)
                        })
                        if len(thread_progress.results_history) > 10:
                            thread_progress.results_history.pop(0)
                        
                        # Update overall progress
                        progress.completed_routes = sum(
                            t.current_route_index for t in progress.threads.values()
                        )
                        progress.overall_percentage = (progress.completed_routes / progress.total_routes) * 100
                        
                        # Broadcast update
                        self._broadcast_progress(experiment_id)
            
            # Thread completed
            thread_progress.status = "completed"
            thread_progress.percentage = 100.0
            
            # Check if all threads completed
            all_completed = all(
                t.status == "completed" for t in progress.threads.values()
            )
            if all_completed:
                progress.status = "completed"
                progress.end_time = time.time()
            
            self._broadcast_progress(experiment_id)
            logger.success(f"Thread {thread_id} completed for experiment {experiment_id}")
            
        except Exception as e:
            logger.error(f"Error in worker thread {thread_id}: {e}")
            logger.error(traceback.format_exc())
            
            if experiment_id in self.experiments:
                thread_progress = self.experiments[experiment_id].threads.get(thread_id)
                if thread_progress:
                    thread_progress.status = "error"
                    thread_progress.error_message = str(e)
                self._broadcast_progress(experiment_id)
    
    def _execute_route(self, experiment_id: str, thread_id: str,
                       trial_idx: int, batch_idx: int, route_idx: int,
                       algorithm: str, tau_settings: Dict,
                       disruption_data: Optional[Dict], config: Dict) -> Dict:
        """
        Execute a single route computation.
        
        Returns:
            Dict containing route result with all metrics
        """
        start_time = time.time()
        
        # Generate tau value based on settings
        tau = self._generate_tau(tau_settings, trial_idx, route_idx)
        
        # Get route coordinates (from preset or generate random)
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
            "error": None
        }
        
        try:
            # Get disruption path for C++ API
            disruption_path = ""
            if disruption_data:
                disruption_path = disruption_data.get("path", "")
            
            # Call the appropriate router
            if algorithm.upper() == "DHL":
                if self.dhl_router:
                    api_result = self.dhl_router.compute_route(
                        start_pin_lat=route_coords["start"]["lat"],
                        start_pin_lng=route_coords["start"]["lng"],
                        dest_pin_lat=route_coords["end"]["lat"],
                        dest_pin_lng=route_coords["end"]["lng"],
                        start_snap_lat=route_coords["start"]["lat"],
                        start_snap_lng=route_coords["start"]["lng"],
                        dest_snap_lat=route_coords["end"]["lat"],
                        dest_snap_lng=route_coords["end"]["lng"],
                        start_edge_source=route_coords.get("start_edge_source", 0),
                        start_edge_target=route_coords.get("start_edge_target", 0),
                        start_edge_oneway=route_coords.get("start_edge_oneway", 0),
                        dest_edge_source=route_coords.get("dest_edge_source", 0),
                        dest_edge_target=route_coords.get("dest_edge_target", 0),
                        dest_edge_oneway=route_coords.get("dest_edge_oneway", 0),
                        disruption_file=disruption_path,
                        tau_threshold=tau,
                        generate_alternatives=False
                    )
                    result = self._parse_api_result(result, api_result, algorithm, tau)
                else:
                    result["error"] = "DHL router not initialized"
                    
            elif algorithm.upper() == "HC2L":
                if self.hc2l_router:
                    api_result = self.hc2l_router.compute_route(
                        start_pin_lat=route_coords["start"]["lat"],
                        start_pin_lng=route_coords["start"]["lng"],
                        dest_pin_lat=route_coords["end"]["lat"],
                        dest_pin_lng=route_coords["end"]["lng"],
                        start_snap_lat=route_coords["start"]["lat"],
                        start_snap_lng=route_coords["start"]["lng"],
                        dest_snap_lat=route_coords["end"]["lat"],
                        dest_snap_lng=route_coords["end"]["lng"],
                        start_edge_source=route_coords.get("start_edge_source", 0),
                        start_edge_target=route_coords.get("start_edge_target", 0),
                        start_edge_oneway=route_coords.get("start_edge_oneway", 0),
                        dest_edge_source=route_coords.get("dest_edge_source", 0),
                        dest_edge_target=route_coords.get("dest_edge_target", 0),
                        dest_edge_oneway=route_coords.get("dest_edge_oneway", 0),
                        disruption_file=disruption_path,
                        tau_threshold=tau,
                        generate_alternatives=False
                    )
                    result = self._parse_api_result(result, api_result, algorithm, tau)
                else:
                    result["error"] = "HC2L router not initialized"
            else:
                result["error"] = f"Unknown algorithm: {algorithm}"
                
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error executing route: {e}")
        
        # Calculate total execution time
        result["execution_time_ms"] = (time.time() - start_time) * 1000
        
        return result
    
    def _parse_api_result(self, result: Dict, api_result: Dict, 
                          algorithm: str, tau: float) -> Dict:
        """Parse C++ API result into standardized format"""
        if not api_result.get("success", False):
            result["error"] = api_result.get("error", "Unknown error")
            return result
        
        raw_output = api_result.get("raw_dhl_output", api_result.get("raw_hc2l_output", {}))
        route_data = raw_output.get("route", {})
        metrics = raw_output.get("metrics", {})
        update_metrics = raw_output.get("update_metrics", {})
        
        # Summary
        result["summary"] = {
            "route": f"{route_data.get('source_name', 'Start')} → {route_data.get('target_name', 'End')}",
            "algorithm": algorithm,
            "query_time_ms": metrics.get("query_time_ms", 0),
            "distance_km": route_data.get("distance_km", 0),
            "baseline_eta": route_data.get("baseline_eta", ""),
            "actual_eta": route_data.get("actual_eta", ""),
            "time_impact_seconds": route_data.get("time_impact_seconds", 0),
            "label_size": metrics.get("label_size", 0)
        }
        
        # Update Phase
        result["update_phase"] = {
            "status": update_metrics.get("update_type", "N/A"),
            "lazy_update_time_ms": update_metrics.get("lazy_update_time_ms", 0),
            "update_strategy": update_metrics.get("strategy", "N/A"),
            "max_label_size": update_metrics.get("max_label_size", 0),
            "min_label_size": update_metrics.get("min_label_size", 0),
            "nodes_repaired": update_metrics.get("nodes_repaired", "N/A") if algorithm == "HC2L" else "N/A",
            "dirty_nodes": update_metrics.get("dirty_nodes", "N/A") if algorithm == "HC2L" else "N/A",
            "impact_score": update_metrics.get("impact_score", "N/A")
        }
        
        # Query Phase
        result["query_phase"] = {
            "algorithm": algorithm,
            "query_time_ms": metrics.get("query_time_ms", 0),
            "avg_query_time_ms": metrics.get("avg_query_time_ms", 0),
            "min_query_time_ms": metrics.get("min_query_time_ms", 0),
            "max_query_time_ms": metrics.get("max_query_time_ms", 0),
            "std_dev": metrics.get("std_dev", "N/A"),
            "p95_latency_ms": metrics.get("p95_latency_ms", "N/A"),
            "queries_count": metrics.get("queries_count", 1)
        }
        
        return result
    
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
        
        if route_idx < len(routes):
            route = routes[route_idx]
            return {
                "start": route.get("start", {"lat": 14.65, "lng": 121.05}),
                "end": route.get("end", {"lat": 14.66, "lng": 121.06}),
                "start_edge_source": route.get("start_edge_source", 0),
                "start_edge_target": route.get("start_edge_target", 0),
                "start_edge_oneway": route.get("start_edge_oneway", 0),
                "dest_edge_source": route.get("dest_edge_source", 0),
                "dest_edge_target": route.get("dest_edge_target", 0),
                "dest_edge_oneway": route.get("dest_edge_oneway", 0)
            }
        
        # Generate random coordinates within Quezon City bounds
        import random
        random.seed(route_idx)
        
        return {
            "start": {
                "lat": random.uniform(14.60, 14.72),
                "lng": random.uniform(121.02, 121.10)
            },
            "end": {
                "lat": random.uniform(14.60, 14.72),
                "lng": random.uniform(121.02, 121.10)
            }
        }
    
    def _save_progress(self, experiment_id: str, results_path: Path):
        """Save progress to progress.json file"""
        progress = self.experiments.get(experiment_id)
        if not progress:
            return
        
        progress_file = results_path / "progress.json"
        try:
            with open(progress_file, 'w') as f:
                json.dump(progress.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving progress: {e}")
    
    def _save_result(self, experiment_id: str, thread_id: str, 
                     result: Dict, results_path: Path):
        """Save individual route result to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        result_file = results_path / f"result_{thread_id}_{timestamp}.json"
        
        try:
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving result: {e}")
    
    def _broadcast_progress(self, experiment_id: str):
        """Broadcast progress update via WebSocket"""
        if not self.socketio:
            return
        
        progress = self.experiments.get(experiment_id)
        if not progress:
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
            
            # Send current progress
            progress = self.experiment_runner.get_progress(experiment_id)
            if progress.get('success'):
                emit('progress_update', progress['progress'])
    
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
