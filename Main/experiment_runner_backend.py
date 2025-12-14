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
# EXPERIMENT METRICS COLLECTOR (NUMPY-BASED)
# ============================================================================

class ExperimentMetricsCollector:
    """
    High-performance numpy-based metrics collector for experiment data.
    
    Collects all metrics in memory using numpy arrays for efficient computation.
    Metrics are organized by: trial, batch, route, algorithm
    """
    
    def __init__(self, trials: int = 3, batches: int = 3, routes_per_batch: int = 1000):
        self.trials = trials
        self.batches = batches
        self.routes_per_batch = routes_per_batch
        self.lock = threading.Lock()
        
        # Pre-allocate numpy arrays for each algorithm
        # Shape: (trials, batches, routes_per_batch)
        shape = (trials, batches, routes_per_batch)
        
        # Construction Phase Metrics (per trial per algorithm)
        # Shape: (trials,)
        self.construction_time_dhl = np.zeros(trials, dtype=np.float64)
        self.construction_time_hc2l = np.zeros(trials, dtype=np.float64)
        self.initial_label_size_dhl = np.zeros(trials, dtype=np.float64)
        self.initial_label_size_hc2l = np.zeros(trials, dtype=np.float64)
        
        # Dynamic Update Metrics (per trial, batch) - separate for DHL and HC2L
        # Shape: (trials, batches)
        batch_shape = (trials, batches)
        self.lazy_update_time_dhl = np.zeros(batch_shape, dtype=np.float64)
        self.lazy_update_time_hc2l = np.zeros(batch_shape, dtype=np.float64)
        self.threshold_rebuild_time_dhl = np.zeros(batch_shape, dtype=np.float64)
        self.threshold_rebuild_time_hc2l = np.zeros(batch_shape, dtype=np.float64)
        self.peak_label_size_dhl = np.zeros(batch_shape, dtype=np.float64)
        self.peak_label_size_hc2l = np.zeros(batch_shape, dtype=np.float64)
        self.rebuild_count_dhl = np.zeros(batch_shape, dtype=np.int32)
        self.rebuild_count_hc2l = np.zeros(batch_shape, dtype=np.int32)
        
        # Query Phase Metrics (per trial, batch, route) - separate for DHL and HC2L
        self.query_time_dhl = np.zeros(shape, dtype=np.float64)
        self.query_time_hc2l = np.zeros(shape, dtype=np.float64)
        self.label_size_dhl = np.zeros(shape, dtype=np.float64)
        self.label_size_hc2l = np.zeros(shape, dtype=np.float64)
        
        # Route Similarity Metrics (per trial, batch, route)
        self.distance_km_dhl = np.zeros(shape, dtype=np.float64)
        self.distance_km_hc2l = np.zeros(shape, dtype=np.float64)
        self.travel_time_dhl = np.zeros(shape, dtype=np.float64)  # In seconds
        self.travel_time_hc2l = np.zeros(shape, dtype=np.float64)
        
        # Route geometry for Frechet distance calculation (stored as lists due to variable length)
        self.route_paths_dhl = {}  # Key: (trial, batch, route), Value: list of coords
        self.route_paths_hc2l = {}
        
        # Disruption impact metrics
        self.impact_score_dhl = np.zeros(shape, dtype=np.float64)
        self.impact_score_hc2l = np.zeros(shape, dtype=np.float64)
        self.nodes_updated_dhl = np.zeros(shape, dtype=np.int32)
        self.nodes_updated_hc2l = np.zeros(shape, dtype=np.int32)
        
        # Tau values per route
        self.tau_values = np.zeros(shape, dtype=np.float64)
        
        # Tracking arrays to know what's filled
        self.filled_dhl = np.zeros(shape, dtype=np.bool_)
        self.filled_hc2l = np.zeros(shape, dtype=np.bool_)
        
        # Track initial construction (per trial)
        self.construction_recorded_dhl = np.zeros(trials, dtype=np.bool_)
        self.construction_recorded_hc2l = np.zeros(trials, dtype=np.bool_)
        
        # Accumulation buffers for per-batch statistics
        self._batch_query_times_dhl = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_query_times_hc2l = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_label_sizes_dhl = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_label_sizes_hc2l = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_lazy_times_dhl = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_lazy_times_hc2l = [[[] for _ in range(batches)] for _ in range(trials)]
        
        logger.info(f"ExperimentMetricsCollector initialized: {trials} trials × {batches} batches × {routes_per_batch} routes")
    
    def record_metric(self, trial: int, batch: int, route: int, algorithm: str, 
                      result: Dict):
        """Record a single route result metrics"""
        with self.lock:
            try:
                alg = algorithm.upper()
                summary = result.get("summary", {})
                update_phase = result.get("update_phase", {})
                query_phase = result.get("query_phase", {})
                
                query_time = query_phase.get("query_time_ms", 0)
                # Also try to get query_time from summary if not in query_phase
                if not query_time:
                    query_time = summary.get("query_time_ms", 0)
                
                label_size = summary.get("label_size", 0)
                distance = summary.get("distance_km", 0)
                tau = result.get("tau", 0.5)
                
                # Extract travel time from ETA
                eta_str = summary.get("actual_eta", "")
                travel_time = self._parse_eta_to_seconds(eta_str)
                
                # Update phase metrics
                lazy_time = update_phase.get("lazy_update_time_ms", 0)
                nodes_updated = update_phase.get("nodes_repaired", 0)
                impact_score = update_phase.get("impact_score", 0)
                is_rebuild = update_phase.get("update_strategy", "") == "immediate_update"
                
                # Record construction time from first route of each trial (batch 0, route 0)
                if batch == 0 and route == 0:
                    construction_info = result.get("construction_info", {})
                    construction_time = construction_info.get("construction_time_ms", 0)
                    initial_label_size = construction_info.get("label_size_mb", label_size)
                    
                    # Fall back to update_phase for initial label size if not in construction_info
                    if not initial_label_size:
                        initial_label_size = label_size
                    
                    if alg == "DHL":
                        if not self.construction_recorded_dhl[trial]:
                            self.construction_time_dhl[trial] = construction_time
                            self.initial_label_size_dhl[trial] = initial_label_size
                            self.construction_recorded_dhl[trial] = True
                    else:
                        if not self.construction_recorded_hc2l[trial]:
                            self.construction_time_hc2l[trial] = construction_time
                            self.initial_label_size_hc2l[trial] = initial_label_size
                            self.construction_recorded_hc2l[trial] = True
                
                if alg == "DHL":
                    self.query_time_dhl[trial, batch, route] = query_time
                    self.label_size_dhl[trial, batch, route] = label_size
                    self.distance_km_dhl[trial, batch, route] = distance
                    self.travel_time_dhl[trial, batch, route] = travel_time
                    self.impact_score_dhl[trial, batch, route] = impact_score
                    self.nodes_updated_dhl[trial, batch, route] = nodes_updated
                    self.filled_dhl[trial, batch, route] = True
                    
                    # Track batch-level metrics
                    self._batch_query_times_dhl[trial][batch].append(query_time)
                    self._batch_label_sizes_dhl[trial][batch].append(label_size)
                    self._batch_lazy_times_dhl[trial][batch].append(lazy_time)
                    
                    # Peak label size tracking
                    if label_size > self.peak_label_size_dhl[trial, batch]:
                        self.peak_label_size_dhl[trial, batch] = label_size
                    
                    # Rebuild tracking
                    if is_rebuild:
                        self.rebuild_count_dhl[trial, batch] += 1
                        
                else:  # HC2L
                    self.query_time_hc2l[trial, batch, route] = query_time
                    self.label_size_hc2l[trial, batch, route] = label_size
                    self.distance_km_hc2l[trial, batch, route] = distance
                    self.travel_time_hc2l[trial, batch, route] = travel_time
                    self.impact_score_hc2l[trial, batch, route] = impact_score
                    self.nodes_updated_hc2l[trial, batch, route] = nodes_updated
                    self.filled_hc2l[trial, batch, route] = True
                    
                    # Track batch-level metrics
                    self._batch_query_times_hc2l[trial][batch].append(query_time)
                    self._batch_label_sizes_hc2l[trial][batch].append(label_size)
                    self._batch_lazy_times_hc2l[trial][batch].append(lazy_time)
                    
                    # Peak label size tracking
                    if label_size > self.peak_label_size_hc2l[trial, batch]:
                        self.peak_label_size_hc2l[trial, batch] = label_size
                    
                    # Rebuild tracking
                    if is_rebuild:
                        self.rebuild_count_hc2l[trial, batch] += 1
                
                # Record tau (same for both algorithms)
                self.tau_values[trial, batch, route] = tau
                
            except Exception as e:
                logger.error(f"Error recording metric: {e}")
    
    def record_construction(self, trial: int, algorithm: str, 
                           construction_time_ms: float, label_size_mb: float):
        """Record initial construction phase metrics"""
        with self.lock:
            alg = algorithm.upper()
            if alg == "DHL":
                if not self.construction_recorded_dhl[trial]:
                    self.construction_time_dhl[trial] = construction_time_ms
                    self.initial_label_size_dhl[trial] = label_size_mb
                    self.construction_recorded_dhl[trial] = True
            else:
                if not self.construction_recorded_hc2l[trial]:
                    self.construction_time_hc2l[trial] = construction_time_ms
                    self.initial_label_size_hc2l[trial] = label_size_mb
                    self.construction_recorded_hc2l[trial] = True
    
    def record_route_path(self, trial: int, batch: int, route: int, 
                          algorithm: str, path_coords: List):
        """Record route path for Frechet distance calculation"""
        with self.lock:
            key = (trial, batch, route)
            if algorithm.upper() == "DHL":
                self.route_paths_dhl[key] = path_coords
            else:
                self.route_paths_hc2l[key] = path_coords
    
    def _parse_eta_to_seconds(self, eta_str: str) -> float:
        """Parse ETA string like '5m 30s' to seconds"""
        if not eta_str:
            return 0
        
        try:
            seconds = 0
            parts = eta_str.replace('h', ' h ').replace('m', ' m ').replace('s', ' s ').split()
            
            i = 0
            while i < len(parts):
                if i + 1 < len(parts):
                    val = float(parts[i])
                    unit = parts[i + 1]
                    if unit == 'h':
                        seconds += val * 3600
                    elif unit == 'm':
                        seconds += val * 60
                    elif unit == 's':
                        seconds += val
                    i += 2
                else:
                    break
            return seconds
        except:
            return 0
    
    def compute_results(self) -> Dict:
        """
        Compute all aggregated results for the dashboard.
        Returns a comprehensive dictionary with all metrics organized by section.
        """
        with self.lock:
            results = {
                "total_trials": self.trials,
                "total_batches": self.batches,
                "construction_phase": self._compute_construction_phase(),
                "dynamic_updates": self._compute_dynamic_updates(),
                "query_performance": self._compute_query_performance(),
                "route_similarity": self._compute_route_similarity(),
                "similarity_extra": self._compute_similarity_extra(),
                "graph_data": self._compute_graph_data(),
                "summary": self._compute_summary()
            }
            return results
    
    def _compute_construction_phase(self) -> List[Dict]:
        """Compute Construction Phase (Appendix 1.1) metrics - returns list for frontend"""
        rows = []
        
        for trial in range(self.trials):
            # DHC2L row
            if self.construction_recorded_hc2l[trial]:
                rows.append({
                    "trial": trial + 1,
                    "algorithm": "DHC2L",
                    "initial_construction_time_ms": round(self.construction_time_hc2l[trial], 2),
                    "initial_label_size_mb": round(self.initial_label_size_hc2l[trial], 2)
                })
            
            # DHL row
            if self.construction_recorded_dhl[trial]:
                rows.append({
                    "trial": trial + 1,
                    "algorithm": "DHL",
                    "initial_construction_time_ms": round(self.construction_time_dhl[trial], 2),
                    "initial_label_size_mb": round(self.initial_label_size_dhl[trial], 2)
                })
        
        return rows
    
    def _compute_dynamic_updates(self) -> List[Dict]:
        """Compute Dynamic Updates (Appendix 1.2) metrics - returns flat list for frontend"""
        rows = []
        
        # Track metrics for computing averages
        trial_averages = {}  # trial -> {algorithm -> metrics}
        batch_averages = {}  # batch -> {algorithm -> metrics}
        overall_averages = {"DHL": [], "DHC2L": []}
        
        for trial in range(self.trials):
            if trial not in trial_averages:
                trial_averages[trial] = {"DHL": [], "DHC2L": []}
                
            for batch in range(self.batches):
                if batch not in batch_averages:
                    batch_averages[batch] = {"DHL": [], "DHC2L": []}
                
                # Get per-batch data for DHL
                dhl_query_times = self._batch_query_times_dhl[trial][batch]
                dhl_lazy_times = self._batch_lazy_times_dhl[trial][batch]
                
                if dhl_query_times:
                    dhl_avg_query = np.mean(dhl_query_times)
                    dhl_min_query = np.min(dhl_query_times)
                    dhl_max_query = np.max(dhl_query_times)
                    dhl_avg_lazy = np.mean(dhl_lazy_times) if dhl_lazy_times else 0
                    dhl_peak_label = self.peak_label_size_dhl[trial, batch]
                    dhl_rebuild_time = self.threshold_rebuild_time_dhl[trial, batch]
                    
                    initial_label = self.initial_label_size_dhl[trial] if self.construction_recorded_dhl[trial] else 1
                    label_change_pct = ((dhl_peak_label - initial_label) / initial_label * 100) if initial_label > 0 else 0
                    
                    row_data = {
                        "batch": batch + 1,
                        "trial": trial + 1,
                        "algorithm": "DHL",
                        "disruption_level": round(len(dhl_query_times) / self.routes_per_batch, 2) if self.routes_per_batch > 0 else 0,
                        "lazy_update_time_ms": round(dhl_avg_lazy, 3),
                        "threshold_rebuild_time_ms": round(dhl_rebuild_time, 3),
                        "peak_label_size_mb": round(dhl_peak_label, 2),
                        "label_size_change_pct": round(label_change_pct, 1),
                        "query_avg_ms": round(dhl_avg_query, 3),
                        "query_min_ms": round(dhl_min_query, 3),
                        "query_max_ms": round(dhl_max_query, 3)
                    }
                    
                    rows.append(row_data)
                    trial_averages[trial]["DHL"].append(row_data)
                    batch_averages[batch]["DHL"].append(row_data)
                    overall_averages["DHL"].append(row_data)
                
                # Get per-batch data for HC2L
                hc2l_query_times = self._batch_query_times_hc2l[trial][batch]
                hc2l_lazy_times = self._batch_lazy_times_hc2l[trial][batch]
                
                if hc2l_query_times:
                    hc2l_avg_query = np.mean(hc2l_query_times)
                    hc2l_min_query = np.min(hc2l_query_times)
                    hc2l_max_query = np.max(hc2l_query_times)
                    hc2l_avg_lazy = np.mean(hc2l_lazy_times) if hc2l_lazy_times else 0
                    hc2l_peak_label = self.peak_label_size_hc2l[trial, batch]
                    hc2l_rebuild_time = self.threshold_rebuild_time_hc2l[trial, batch]
                    
                    initial_label = self.initial_label_size_hc2l[trial] if self.construction_recorded_hc2l[trial] else 1
                    label_change_pct = ((hc2l_peak_label - initial_label) / initial_label * 100) if initial_label > 0 else 0
                    
                    row_data = {
                        "batch": batch + 1,
                        "trial": trial + 1,
                        "algorithm": "DHC2L",
                        "disruption_level": round(len(hc2l_query_times) / self.routes_per_batch, 2) if self.routes_per_batch > 0 else 0,
                        "lazy_update_time_ms": round(hc2l_avg_lazy, 3),
                        "threshold_rebuild_time_ms": round(hc2l_rebuild_time, 3),
                        "peak_label_size_mb": round(hc2l_peak_label, 2),
                        "label_size_change_pct": round(label_change_pct, 1),
                        "query_avg_ms": round(hc2l_avg_query, 3),
                        "query_min_ms": round(hc2l_min_query, 3),
                        "query_max_ms": round(hc2l_max_query, 3)
                    }
                    
                    rows.append(row_data)
                    trial_averages[trial]["DHC2L"].append(row_data)
                    batch_averages[batch]["DHC2L"].append(row_data)
                    overall_averages["DHC2L"].append(row_data)
        
        # Compute and append averages
        def compute_avg(data_list):
            if not data_list:
                return None
            return {
                "lazy_update_time_ms": round(float(np.mean([d["lazy_update_time_ms"] for d in data_list])), 3),
                "threshold_rebuild_time_ms": round(float(np.mean([d["threshold_rebuild_time_ms"] for d in data_list])), 3),
                "peak_label_size_mb": round(float(np.mean([d["peak_label_size_mb"] for d in data_list])), 2),
                "label_size_change_pct": round(float(np.mean([d["label_size_change_pct"] for d in data_list])), 1),
                "query_avg_ms": round(float(np.mean([d["query_avg_ms"] for d in data_list])), 3),
                "query_min_ms": round(float(np.mean([d["query_min_ms"] for d in data_list])), 3),
                "query_max_ms": round(float(np.mean([d["query_max_ms"] for d in data_list])), 3)
            }
        
        # Add per-batch averages
        for batch in range(self.batches):
            for algorithm in ["DHL", "DHC2L"]:
                avg_data = compute_avg(batch_averages[batch][algorithm])
                if avg_data:
                    rows.append({
                        "batch": batch + 1,
                        "trial": "Average",
                        "algorithm": algorithm,
                        "disruption_level": "-",
                        **avg_data
                    })
        
        # Add per-trial averages
        for trial in range(self.trials):
            for algorithm in ["DHL", "DHC2L"]:
                avg_data = compute_avg(trial_averages[trial][algorithm])
                if avg_data:
                    rows.append({
                        "batch": "Average",
                        "trial": trial + 1,
                        "algorithm": algorithm,
                        "disruption_level": "-",
                        **avg_data
                    })
        
        # Add overall averages
        for algorithm in ["DHL", "DHC2L"]:
            avg_data = compute_avg(overall_averages[algorithm])
            if avg_data:
                rows.append({
                    "batch": "Average",
                    "trial": "Overall",
                    "algorithm": algorithm,
                    "disruption_level": "-",
                    **avg_data
                })
        
        return rows
    
    def _compute_query_performance(self) -> List[Dict]:
        """Compute Query Performance (Appendix 1.3) comparison metrics - returns list for frontend"""
        # Aggregate across all trials
        dhl_metrics = {
            "initial_labeling_time_ms": [],
            "avg_query_time_ms": [],
            "label_size_mb": [],
            "peak_label_size_mb": [],
            "lazy_update_time_ms": [],
            "threshold_rebuild_time_ms": [],
            "total_rebuilds": 0
        }
        
        hc2l_metrics = {
            "initial_labeling_time_ms": [],
            "avg_query_time_ms": [],
            "label_size_mb": [],
            "peak_label_size_mb": [],
            "lazy_update_time_ms": [],
            "threshold_rebuild_time_ms": [],
            "total_rebuilds": 0
        }
        
        for trial in range(self.trials):
            # Construction time
            if self.construction_recorded_dhl[trial]:
                dhl_metrics["initial_labeling_time_ms"].append(self.construction_time_dhl[trial])
            if self.construction_recorded_hc2l[trial]:
                hc2l_metrics["initial_labeling_time_ms"].append(self.construction_time_hc2l[trial])
            
            # Per-trial query times (flatten all batches/routes)
            dhl_mask = self.filled_dhl[trial, :, :]
            hc2l_mask = self.filled_hc2l[trial, :, :]
            
            if np.any(dhl_mask):
                dhl_metrics["avg_query_time_ms"].append(np.mean(self.query_time_dhl[trial, :, :][dhl_mask]))
                dhl_metrics["label_size_mb"].append(np.mean(self.label_size_dhl[trial, :, :][dhl_mask]))
                dhl_metrics["peak_label_size_mb"].append(np.max(self.peak_label_size_dhl[trial, :]))
                
                # Lazy update times
                all_lazy = []
                for b in range(self.batches):
                    all_lazy.extend(self._batch_lazy_times_dhl[trial][b])
                if all_lazy:
                    dhl_metrics["lazy_update_time_ms"].append(np.mean(all_lazy))
                
                dhl_metrics["threshold_rebuild_time_ms"].append(np.mean(self.threshold_rebuild_time_dhl[trial, :]))
                dhl_metrics["total_rebuilds"] += int(np.sum(self.rebuild_count_dhl[trial, :]))
            
            if np.any(hc2l_mask):
                hc2l_metrics["avg_query_time_ms"].append(np.mean(self.query_time_hc2l[trial, :, :][hc2l_mask]))
                hc2l_metrics["label_size_mb"].append(np.mean(self.label_size_hc2l[trial, :, :][hc2l_mask]))
                hc2l_metrics["peak_label_size_mb"].append(np.max(self.peak_label_size_hc2l[trial, :]))
                
                # Lazy update times
                all_lazy = []
                for b in range(self.batches):
                    all_lazy.extend(self._batch_lazy_times_hc2l[trial][b])
                if all_lazy:
                    hc2l_metrics["lazy_update_time_ms"].append(np.mean(all_lazy))
                
                hc2l_metrics["threshold_rebuild_time_ms"].append(np.mean(self.threshold_rebuild_time_hc2l[trial, :]))
                hc2l_metrics["total_rebuilds"] += int(np.sum(self.rebuild_count_hc2l[trial, :]))
        
        # Calculate averages
        def safe_mean(arr):
            return round(float(np.mean(arr)), 3) if arr else 0.0
        
        dhl_avg = {k: safe_mean(v) if isinstance(v, list) else v for k, v in dhl_metrics.items()}
        hc2l_avg = {k: safe_mean(v) if isinstance(v, list) else v for k, v in hc2l_metrics.items()}
        
        # Build comparison list with metric name mapping for display
        metric_display_names = {
            "initial_labeling_time_ms": "Initial Labeling Time",
            "avg_query_time_ms": "Avg Query Time",
            "label_size_mb": "Avg Label Size",
            "peak_label_size_mb": "Peak Label Size",
            "lazy_update_time_ms": "Lazy Update Time",
            "threshold_rebuild_time_ms": "Threshold Rebuild Time",
            "total_rebuilds": "Total Rebuilds"
        }
        
        metric_units = {
            "initial_labeling_time_ms": "ms",
            "avg_query_time_ms": "ms",
            "label_size_mb": "MB",
            "peak_label_size_mb": "MB",
            "lazy_update_time_ms": "ms",
            "threshold_rebuild_time_ms": "ms",
            "total_rebuilds": ""
        }
        
        comparison = []
        for metric in ["initial_labeling_time_ms", "avg_query_time_ms", "label_size_mb", 
                       "peak_label_size_mb", "lazy_update_time_ms", "threshold_rebuild_time_ms", "total_rebuilds"]:
            dhl_val = dhl_avg[metric]
            hc2l_val = hc2l_avg[metric]
            
            improvement = 0
            if dhl_val > 0:
                improvement = round((dhl_val - hc2l_val) / dhl_val * 100, 1)
            
            comparison.append({
                "metric": metric_display_names.get(metric, metric),
                "dhl_value": dhl_val,
                "dhc2l_value": hc2l_val,
                "improvement_pct": improvement,
                "unit": metric_units.get(metric, "")
            })
        
        return comparison
    
    def _compute_route_similarity(self) -> List[Dict]:
        """Compute Route Similarity (Appendix 1.4) metrics - returns list for frontend"""
        rows = []
        
        # Sample up to 10 routes for display
        sample_count = 0
        max_samples = 10
        
        for trial in range(self.trials):
            if sample_count >= max_samples:
                break
            for batch in range(self.batches):
                if sample_count >= max_samples:
                    break
                for route in range(min(5, self.routes_per_batch)):  # First 5 routes per batch
                    if sample_count >= max_samples:
                        break
                    
                    if self.filled_dhl[trial, batch, route] and self.filled_hc2l[trial, batch, route]:
                        dhl_dist = self.distance_km_dhl[trial, batch, route]
                        hc2l_dist = self.distance_km_hc2l[trial, batch, route]
                        dhl_time = self.travel_time_dhl[trial, batch, route]
                        hc2l_time = self.travel_time_hc2l[trial, batch, route]
                        
                        # Frechet distance calculation using recorded path coordinates
                        key = (trial, batch, route)
                        frechet_distance = 0
                        if key in self.route_paths_dhl and key in self.route_paths_hc2l:
                            frechet_distance = self._compute_frechet_distance(
                                self.route_paths_dhl[key], 
                                self.route_paths_hc2l[key]
                            )
                        else:
                            # If paths not recorded, estimate based on distance difference
                            # This is a fallback - in ideal case both paths should be recorded
                            frechet_distance = abs(dhl_dist - hc2l_dist) * 1000  # Convert km to meters approximation
                        
                        # Calculate time deviation properly
                        # Use the travel times in seconds for comparison
                        if dhl_time > 0 and hc2l_time > 0:
                            avg_time = (dhl_time + hc2l_time) / 2
                            time_deviation = abs(dhl_time - hc2l_time) / avg_time * 100 if avg_time > 0 else 0
                        else:
                            time_deviation = 0
                        
                        # Rating based on Frechet distance
                        if frechet_distance < 200:
                            fd_rating = "Excellent"
                        elif frechet_distance < 400:
                            fd_rating = "Good"
                        else:
                            fd_rating = "Fair"
                        
                        # Rating based on travel time deviation
                        if time_deviation < 5:
                            ttd_rating = "Excellent"
                        elif time_deviation < 10:
                            ttd_rating = "Good"
                        else:
                            ttd_rating = "Fair"
                        
                        rows.append({
                            "od_pair": "S → D",
                            "distance_km": round((dhl_dist + hc2l_dist) / 2, 2),
                            "travel_time_min": round((dhl_time + hc2l_time) / 2 / 60, 2) if (dhl_time + hc2l_time) > 0 else 0,
                            "frechet_distance_m": round(frechet_distance, 2),
                            "fd_rating": fd_rating,
                            "travel_time_deviation_pct": round(time_deviation, 2),
                            "ttd_rating": ttd_rating
                        })
                        sample_count += 1
        
        # Calculate averages
        if rows:
            avg_row = {
                "od_pair": "Average",
                "distance_km": round(float(np.mean([r["distance_km"] for r in rows])), 2),
                "travel_time_min": round(float(np.mean([r["travel_time_min"] for r in rows])), 2),
                "frechet_distance_m": round(float(np.mean([r["frechet_distance_m"] for r in rows])), 2),
                "fd_rating": "-",
                "travel_time_deviation_pct": round(float(np.mean([r["travel_time_deviation_pct"] for r in rows])), 2),
                "ttd_rating": "-"
            }
            rows.append(avg_row)
        
        return rows
    
    def _compute_frechet_distance(self, path1: List, path2: List) -> float:
        """Compute discrete Frechet distance between two paths in meters"""
        if not path1 or not path2:
            return 0
        
        try:
            # Convert to numpy arrays
            p1 = np.array(path1)
            p2 = np.array(path2)
            
            # Haversine distance function
            def haversine(lon1, lat1, lon2, lat2):
                R = 6371000  # Earth radius in meters
                phi1, phi2 = np.radians(lat1), np.radians(lat2)
                dphi = np.radians(lat2 - lat1)
                dlambda = np.radians(lon2 - lon1)
                
                a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
                return 2 * R * np.arcsin(np.sqrt(a))
            
            n, m = len(p1), len(p2)
            ca = np.full((n, m), -1.0)
            
            def c(i, j):
                if ca[i, j] > -1:
                    return ca[i, j]
                
                d = haversine(p1[i][0], p1[i][1], p2[j][0], p2[j][1])
                
                if i == 0 and j == 0:
                    ca[i, j] = d
                elif i > 0 and j == 0:
                    ca[i, j] = max(c(i-1, 0), d)
                elif i == 0 and j > 0:
                    ca[i, j] = max(c(0, j-1), d)
                else:
                    ca[i, j] = max(min(c(i-1, j), c(i-1, j-1), c(i, j-1)), d)
                
                return ca[i, j]
            
            return c(n-1, m-1)
        except:
            return 0
    
    def _compute_summary(self) -> Dict:
        """Compute overall summary statistics"""
        total_dhl = np.sum(self.filled_dhl)
        total_hc2l = np.sum(self.filled_hc2l)
        
        return {
            "total_trials": self.trials,
            "total_batches": self.batches,
            "routes_per_batch": self.routes_per_batch,
            "completed_dhl": int(total_dhl),
            "completed_hc2l": int(total_hc2l),
            "total_expected": self.trials * self.batches * self.routes_per_batch * 2,
            "completion_pct": round((total_dhl + total_hc2l) / (self.trials * self.batches * self.routes_per_batch * 2) * 100, 2)
        }
    
    def _compute_similarity_extra(self) -> Dict:
        """Compute additional similarity metrics"""
        path_overlaps = []
        distance_deviations = []
        alternative_route_count = 0
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                for route in range(self.routes_per_batch):
                    if self.filled_dhl[trial, batch, route] and self.filled_hc2l[trial, batch, route]:
                        # Distance deviation
                        dhl_dist = self.distance_km_dhl[trial, batch, route]
                        hc2l_dist = self.distance_km_hc2l[trial, batch, route]
                        if dhl_dist > 0:
                            deviation = abs(dhl_dist - hc2l_dist) / dhl_dist * 100
                            distance_deviations.append(deviation)
                        
                        # Check if routes are significantly different (alternative routes)
                        key = (trial, batch, route)
                        if key in self.route_paths_dhl and key in self.route_paths_hc2l:
                            # If Frechet distance is large, consider it an alternative route
                            frechet = self._compute_frechet_distance(
                                self.route_paths_dhl[key], 
                                self.route_paths_hc2l[key]
                            )
                            if frechet > 500:  # More than 500m difference
                                alternative_route_count += 1
                            
                            # Estimate path overlap (simplified)
                            # Paths with low Frechet distance have high overlap
                            if frechet < 200:
                                overlap = 95  # High overlap
                            elif frechet < 400:
                                overlap = 70  # Medium overlap
                            else:
                                overlap = 40  # Low overlap
                            path_overlaps.append(overlap)
        
        return {
            "path_overlap_pct": round(float(np.mean(path_overlaps)), 1) if path_overlaps else 0,
            "distance_deviation_pct": round(float(np.mean(distance_deviations)), 1) if distance_deviations else 0,
            "alternative_route_count": alternative_route_count
        }
    
    def _compute_graph_data(self) -> Dict:
        """Compute comprehensive data for graph visualizations"""
        graph_data = {
            "time_series": {},
            "algorithm_comparison": {},
            "per_trial": {},
            "rebuild_analysis": {},
            "label_size_trend": {}
        }
        
        # =====================================================================
        # TIME SERIES DATA - Query time and update time over batches
        # =====================================================================
        for algorithm in ["DHL", "HC2L"]:
            is_dhl = (algorithm == "DHL")
            query_data = self.query_time_dhl if is_dhl else self.query_time_hc2l
            lazy_data = self.lazy_update_time_dhl if is_dhl else self.lazy_update_time_hc2l
            rebuild_data = self.threshold_rebuild_time_dhl if is_dhl else self.threshold_rebuild_time_hc2l
            filled = self.filled_dhl if is_dhl else self.filled_hc2l
            
            batch_labels = []
            query_times = []
            update_times = []
            rebuild_times = []
            
            for trial in range(self.trials):
                for batch in range(self.batches):
                    batch_label = f"T{trial+1}B{batch+1}"
                    batch_labels.append(batch_label)
                    
                    # Average query time for this batch
                    mask = filled[trial, batch, :]
                    if np.any(mask):
                        avg_query = float(np.mean(query_data[trial, batch, :][mask]))
                        query_times.append(round(avg_query, 3))
                    else:
                        query_times.append(0)
                    
                    # Average lazy update time
                    key = "lazy_times_dhl" if is_dhl else "lazy_times_hc2l"
                    if trial < len(self._batch_lazy_times_dhl if is_dhl else self._batch_lazy_times_hc2l):
                        batch_lazy = (self._batch_lazy_times_dhl if is_dhl else self._batch_lazy_times_hc2l)[trial][batch]
                        if batch_lazy:
                            update_times.append(round(float(np.mean(batch_lazy)), 3))
                        else:
                            update_times.append(0)
                    else:
                        update_times.append(0)
                    
                    # Threshold rebuild time
                    rebuild_times.append(round(float(rebuild_data[trial, batch]), 3))
            
            graph_data["time_series"][algorithm] = {
                "batch_labels": batch_labels,
                "query_times": query_times,
                "update_times": update_times,
                "rebuild_times": rebuild_times
            }
        
        # =====================================================================
        # ALGORITHM COMPARISON - Average metrics across all trials
        # =====================================================================
        dhl_avg_query = []
        hc2l_avg_query = []
        dhl_avg_label = []
        hc2l_avg_label = []
        
        for trial in range(self.trials):
            dhl_mask = self.filled_dhl[trial, :, :]
            hc2l_mask = self.filled_hc2l[trial, :, :]
            
            if np.any(dhl_mask):
                dhl_avg_query.append(float(np.mean(self.query_time_dhl[trial, :, :][dhl_mask])))
                dhl_avg_label.append(float(np.mean(self.label_size_dhl[trial, :, :][dhl_mask])))
            
            if np.any(hc2l_mask):
                hc2l_avg_query.append(float(np.mean(self.query_time_hc2l[trial, :, :][hc2l_mask])))
                hc2l_avg_label.append(float(np.mean(self.label_size_hc2l[trial, :, :][hc2l_mask])))
        
        graph_data["algorithm_comparison"] = {
            "avg_query_time": {
                "DHL": round(float(np.mean(dhl_avg_query)), 3) if dhl_avg_query else 0,
                "HC2L": round(float(np.mean(hc2l_avg_query)), 3) if hc2l_avg_query else 0
            },
            "avg_label_size": {
                "DHL": round(float(np.mean(dhl_avg_label)), 3) if dhl_avg_label else 0,
                "HC2L": round(float(np.mean(hc2l_avg_label)), 3) if hc2l_avg_label else 0
            }
        }
        
        # =====================================================================
        # PER-TRIAL BREAKDOWN
        # =====================================================================
        trial_labels = [f"Trial {i+1}" for i in range(self.trials)]
        dhl_trial_query = []
        hc2l_trial_query = []
        dhl_trial_update = []
        hc2l_trial_update = []
        
        for trial in range(self.trials):
            # Query times
            dhl_mask = self.filled_dhl[trial, :, :]
            hc2l_mask = self.filled_hc2l[trial, :, :]
            
            if np.any(dhl_mask):
                dhl_trial_query.append(round(float(np.mean(self.query_time_dhl[trial, :, :][dhl_mask])), 3))
            else:
                dhl_trial_query.append(0)
            
            if np.any(hc2l_mask):
                hc2l_trial_query.append(round(float(np.mean(self.query_time_hc2l[trial, :, :][hc2l_mask])), 3))
            else:
                hc2l_trial_query.append(0)
            
            # Update times (lazy + rebuild)
            dhl_lazy_all = []
            hc2l_lazy_all = []
            for batch in range(self.batches):
                dhl_lazy_all.extend(self._batch_lazy_times_dhl[trial][batch])
                hc2l_lazy_all.extend(self._batch_lazy_times_hc2l[trial][batch])
            
            dhl_trial_update.append(round(float(np.mean(dhl_lazy_all)), 3) if dhl_lazy_all else 0)
            hc2l_trial_update.append(round(float(np.mean(hc2l_lazy_all)), 3) if hc2l_lazy_all else 0)
        
        graph_data["per_trial"] = {
            "trial_labels": trial_labels,
            "DHL_query": dhl_trial_query,
            "HC2L_query": hc2l_trial_query,
            "DHL_update": dhl_trial_update,
            "HC2L_update": hc2l_trial_update
        }
        
        # =====================================================================
        # REBUILD ANALYSIS - Threshold rebuild times and counts
        # =====================================================================
        dhl_rebuild_times = []
        hc2l_rebuild_times = []
        dhl_rebuild_counts = []
        hc2l_rebuild_counts = []
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                dhl_rebuild_times.append(float(self.threshold_rebuild_time_dhl[trial, batch]))
                hc2l_rebuild_times.append(float(self.threshold_rebuild_time_hc2l[trial, batch]))
                dhl_rebuild_counts.append(int(self.rebuild_count_dhl[trial, batch]))
                hc2l_rebuild_counts.append(int(self.rebuild_count_hc2l[trial, batch]))
        
        graph_data["rebuild_analysis"] = {
            "DHL_rebuild_times": [round(t, 3) for t in dhl_rebuild_times],
            "HC2L_rebuild_times": [round(t, 3) for t in hc2l_rebuild_times],
            "DHL_rebuild_counts": dhl_rebuild_counts,
            "HC2L_rebuild_counts": hc2l_rebuild_counts,
            "total_DHL_rebuilds": sum(dhl_rebuild_counts),
            "total_HC2L_rebuilds": sum(hc2l_rebuild_counts)
        }
        
        # =====================================================================
        # LABEL SIZE TREND - How label sizes change over batches
        # =====================================================================
        dhl_label_trend = []
        hc2l_label_trend = []
        batch_labels = []
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                batch_labels.append(f"T{trial+1}B{batch+1}")
                
                # Average label size for this batch
                dhl_mask = self.filled_dhl[trial, batch, :]
                hc2l_mask = self.filled_hc2l[trial, batch, :]
                
                if np.any(dhl_mask):
                    dhl_label_trend.append(round(float(np.mean(self.label_size_dhl[trial, batch, :][dhl_mask])), 3))
                else:
                    dhl_label_trend.append(0)
                
                if np.any(hc2l_mask):
                    hc2l_label_trend.append(round(float(np.mean(self.label_size_hc2l[trial, batch, :][hc2l_mask])), 3))
                else:
                    hc2l_label_trend.append(0)
        
        graph_data["label_size_trend"] = {
            "batch_labels": batch_labels,
            "DHL_labels": dhl_label_trend,
            "HC2L_labels": hc2l_label_trend
        }
        
        return graph_data
    
    def get_progress_stats(self) -> Dict:
        """Get current progress statistics for real-time display"""
        with self.lock:
            return {
                "completed_dhl": int(np.sum(self.filled_dhl)),
                "completed_hc2l": int(np.sum(self.filled_hc2l)),
                "latest_query_time_dhl": float(np.max(self.query_time_dhl[self.filled_dhl])) if np.any(self.filled_dhl) else 0,
                "latest_query_time_hc2l": float(np.max(self.query_time_hc2l[self.filled_hc2l])) if np.any(self.filled_hc2l) else 0
            }


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
    
    def _ensure_preset_config(self, experiment_id: str = None):
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
            
            # Send completion progress
            if experiment_id:
                self._emit_preset_progress(experiment_id, "creating_complete", "Preset created successfully", 100)
        except Exception as e:
            logger.error(f"Failed to create ExperimentPreset.json: {e}")
            if experiment_id:
                self._emit_preset_progress(experiment_id, "error", f"Failed to save preset: {str(e)}", 0)
    
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
            
            # Initialize metrics collector (numpy-based)
            trials = config.get("trials", 3)
            batches = config.get("batches_per_trial", 3)
            routes_per_batch = config.get("routes_per_batch", 1000)
            self.metrics_collectors[experiment_id] = ExperimentMetricsCollector(
                trials=trials,
                batches=batches,
                routes_per_batch=routes_per_batch
            )
            logger.info(f"Metrics collector initialized for {experiment_id}: {trials}×{batches}×{routes_per_batch}")
            
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
            
            # Ensure preset configuration exists (with progress tracking)
            if is_preset:
                self._ensure_preset_config(experiment_id)
                
                # Load routes from ExperimentPreset.json
                preset_file = self.preset_path / "ExperimentPreset.json"
                if preset_file.exists():
                    try:
                        with open(preset_file, 'r') as f:
                            preset_data = json.load(f)
                            # Merge preset routes into config if not already present
                            if "routes" not in config or not config["routes"]:
                                config["routes"] = preset_data.get("routes", [])
                                logger.success(f"Loaded {len(config['routes'])} routes from preset")
                            # Also merge other preset settings if not provided
                            if "tau_settings" not in config:
                                config["tau_settings"] = preset_data.get("tau_settings", {})
                            if "disruption_settings" not in config:
                                config["disruption_settings"] = preset_data.get("disruption_settings", {})
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
            results_path.mkdir(parents=True, exist_ok=True)
            
            # Store results_path in progress for later access
            progress.results_path = results_path
            
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
        """Get final experiment results computed from numpy metrics collector"""
        if experiment_id not in self.experiments:
            return {"success": False, "error": "Experiment not found"}
        
        progress = self.experiments[experiment_id]
        
        # Compute results from metrics collector
        computed_results = {}
        if experiment_id in self.metrics_collectors:
            try:
                computed_results = self.metrics_collectors[experiment_id].compute_results()
                logger.info(f"Computed results for {experiment_id}: {computed_results.get('summary', {})}")
            except Exception as e:
                logger.error(f"Error computing results: {e}")
                logger.error(traceback.format_exc())
        
        return {
            "success": True,
            "experiment_id": experiment_id,
            "status": progress.status,
            "total_routes": progress.total_routes,
            "completed_routes": progress.completed_routes,
            "start_time": progress.start_time,
            "end_time": progress.end_time,
            "duration_seconds": progress.end_time - progress.start_time if progress.end_time > 0 else 0,
            "result": computed_results  # Changed from "results" to "result" for frontend compatibility
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
                        
                        # Record metrics to numpy collector (instead of saving file)
                        if experiment_id in self.metrics_collectors:
                            self.metrics_collectors[experiment_id].record_metric(
                                trial_idx, b_idx, route_idx, algorithm, result
                            )
                            
                            # Record route path coordinates for Frechet distance calculation
                            path_coords = result.get("path_coordinates", [])
                            if path_coords:
                                self.metrics_collectors[experiment_id].record_route_path(
                                    trial_idx, b_idx, route_idx, algorithm, path_coords
                                )
                        
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
                        
                        # Update query phase with accumulated statistics
                        query_time = result.get("query_phase", {}).get("query_time_ms", 0)
                        label_size = result.get("summary", {}).get("label_size", 0)
                        
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
                        
                        # Add to history (limit to 10)
                        thread_progress.results_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "route": f"Route {route_idx}",
                            "algorithm": algorithm,
                            "query_time_ms": query_time
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
                
                # Save results to preset/results directory
                self._save_final_results(experiment_id)
            
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
        
        # Calculate distance in km
        distance_km = metrics.get("calculated_distance_km", 0)
        if not distance_km and metrics.get("calculated_distance_meters"):
            distance_km = metrics.get("calculated_distance_meters") / 1000
        
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
        
        # Summary
        result["summary"] = {
            "route": "Start → End",
            "algorithm": algorithm,
            "query_time_ms": round(metrics.get("query_time_ms", 0), 3),
            "distance_km": round(distance_km, 2) if distance_km else 0,
            "baseline_eta": baseline_eta,
            "actual_eta": actual_eta,
            "time_impact_seconds": round(time_impact_seconds, 1) if time_impact_seconds else 0,
            "label_size": round(label_size_mb, 2),  # In MB
            "tau": round(tau, 3),
            "disrupted_edges": route_disruptions.get("total_disrupted_edges", 0)
        }
        
        # Update Phase - extract from lazy_hc2l or dhl_update_info
        if algorithm.upper() == "HC2L":
            update_strategy = lazy_hc2l.get("update_strategy", "N/A")
            lazy_update_time = lazy_hc2l.get("lazy_repair_time_ms", 0)
            nodes_repaired = lazy_hc2l.get("nodes_repaired", 0)
            dirty_nodes = lazy_hc2l.get("dirty_nodes_marked", 0)
            impact_score = lazy_hc2l.get("disruption_impact_score", 0)
            
            result["update_phase"] = {
                "status": "lazy_repair" if update_strategy == "lazy_marking" else "immediate_update",
                "lazy_update_time_ms": round(lazy_update_time, 3) if lazy_update_time else 0,
                "update_strategy": update_strategy,
                "max_label_size": labeling_info.get("max_label_count_per_node", 0),
                "min_label_size": 0,  # Not provided in API
                "nodes_repaired": nodes_repaired if nodes_repaired is not None else 0,
                "dirty_nodes": dirty_nodes if dirty_nodes is not None else 0,
                "impact_score": round(impact_score, 3) if isinstance(impact_score, (int, float)) else 0
            }
        else:  # DHL
            nodes_updated = dhl_update_info.get("nodes_updated", 0)
            impact_score = dhl_update_info.get("disruption_impact_score", 1.0)
            
            result["update_phase"] = {
                "status": "immediate_update",
                "lazy_update_time_ms": 0,  # DHL always does immediate update
                "update_strategy": dhl_update_info.get("update_strategy", "immediate_update"),
                "max_label_size": labeling_info.get("max_label_count_per_node", 0),
                "min_label_size": 0,  # Not provided in API
                "nodes_repaired": nodes_updated if nodes_updated is not None else 0,
                "dirty_nodes": 0,  # DHL doesn't use dirty nodes
                "impact_score": round(impact_score, 3) if isinstance(impact_score, (int, float)) else 1.0
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
        construction_time = labeling_info.get("construction_time_ms", 0)
        if not construction_time:
            construction_time = labeling_info.get("labeling_time_ms", 0)
        
        result["construction_info"] = {
            "construction_time_ms": construction_time,
            "label_size_mb": label_size_mb
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
    
    def _save_final_results(self, experiment_id: str):
        """Save final results to preset/results directory when experiment completes"""
        try:
            if experiment_id not in self.experiments:
                return
            
            progress = self.experiments[experiment_id]
            
            # Get metrics collector
            if experiment_id not in self.metrics_collectors:
                logger.warning(f"No metrics collector found for {experiment_id}")
                return
            
            collector = self.metrics_collectors[experiment_id]
            
            # Compute all results
            results = collector.compute_results()
            
            # Add experiment metadata
            results["experiment_id"] = experiment_id
            results["timestamp"] = datetime.now().isoformat()
            results["start_time"] = progress.start_time if progress.start_time else time.time()
            results["end_time"] = progress.end_time if progress.end_time else time.time()
            results["duration_seconds"] = (progress.end_time - progress.start_time) if (progress.end_time and progress.start_time) else 0
            results["status"] = progress.status
            results["total_routes"] = progress.total_routes
            results["completed_routes"] = progress.completed_routes
            
            # Save to preset/results directory
            results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = results_dir / f"experiment_{timestamp_str}.json"
            
            with open(result_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.success(f"Saved final results to {result_file}")
            
        except Exception as e:
            logger.error(f"Failed to save final results for {experiment_id}: {e}")
            logger.error(traceback.format_exc())
    
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
            start_data = route.get("start", {})
            end_data = route.get("end", {})
            
            # Extract edge values for debugging
            start_edge_source = start_data.get("edge_source", 0)
            start_edge_target = start_data.get("edge_target", 0)
            end_edge_source = end_data.get("edge_source", 0)
            end_edge_target = end_data.get("edge_target", 0)
            
            # Log if edges are missing (only for first few routes to avoid spam)
            if route_idx < 5 and (start_edge_source == 0 or end_edge_source == 0):
                logger.warning(f"Route {route_idx}: Missing edge data - start_edge={start_edge_source}, end_edge={end_edge_source}")
                logger.debug(f"Route {route_idx} start_data keys: {list(start_data.keys())}")
                logger.debug(f"Route {route_idx} end_data keys: {list(end_data.keys())}")
            
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
    """List all saved experiment results"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        results_list = []
        for result_file in results_dir.glob("*.json"):
            try:
                with open(result_file, 'r') as f:
                    result_data = json.load(f)
                    
                    # Extract summary info
                    summary = result_data.get("summary", {})
                    
                    results_list.append({
                        "id": result_file.stem,
                        "filename": result_file.name,
                        "timestamp": result_file.stat().st_mtime,
                        "trials": summary.get("total_trials", 0),
                        "batches": summary.get("total_batches", 0),
                        "routes_per_batch": summary.get("routes_per_batch", 0),
                        "completed": summary.get("completion_pct", 0)
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
    """Get a specific saved experiment result"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        result_file = results_dir / f"{result_id}.json"
        
        if not result_file.exists():
            return jsonify({"success": False, "error": "Result not found"}), 404
        
        with open(result_file, 'r') as f:
            result_data = json.load(f)
        
        return jsonify({
            "success": True,
            "result": result_data
        })
    except Exception as e:
        logger.error(f"Error retrieving saved result {result_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@experiment_bp.route('/results/<result_id>', methods=['DELETE'])
def delete_saved_result(result_id):
    """Delete a saved experiment result"""
    if not experiment_runner:
        return jsonify({"success": False, "error": "Experiment runner not initialized"}), 500
    
    try:
        results_dir = Path(Config.EXPERIMENT_DATA_DIR) / "preset" / "results"
        result_file = results_dir / f"{result_id}.json"
        
        if not result_file.exists():
            return jsonify({"success": False, "error": "Result not found"}), 404
        
        result_file.unlink()
        
        return jsonify({
            "success": True,
            "message": "Result deleted successfully"
        })
    except Exception as e:
        logger.error(f"Error deleting saved result {result_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

