# experiment_metrics_collector.py - Centralized Experiment Metrics Collection and Logging
"""
Experiment Metrics Collector Module

Centralized module for handling all experiment metrics gathering and logging.
Separates data collection from experiment execution for cleaner architecture.

Key Features:
- Per-route logging with strict CSV headers
- Accuracy-first gating (performance metrics only if accuracy passes)
- Pre-computed CSV files for each GUI tab
- Minimal JSON configuration file
- Thread-safe metric recording

CSV Export Files (created in results folder):
- summary_results.csv        - Incident summary per trial/batch
- accuracy_results.csv       - HC2L accuracy vs Dijkstra  
- construction_results.csv   - Initial construction performance
- updates_results.csv        - Dynamic update performance
- performance_results.csv    - Combined DHL vs HC2L performance
- similarity_results.csv     - HERE vs HC2L route comparison

CSV Headers are STRICTLY enforced and MUST NOT be changed.
"""

import os
import csv
import json
import time
import threading
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from console_formatter import get_logger

# Get logger instance
logger = get_logger("MetricsCollector")

# Default accuracy tolerance: 10%
DEFAULT_TOLERANCE = 0.10


# ============================================================================
# ALGORITHM NAME NORMALIZATION
# ============================================================================

def normalize_algorithm_name(algorithm: str) -> str:
    """
    Normalize algorithm name to canonical form.
    
    The experiment runner uses "HC2L" but we standardize to "HC2L" internally
    for consistent data tracking.
    
    Args:
        algorithm: Algorithm name (case insensitive)
        
    Returns:
        Normalized algorithm name: "DHL" or "HC2L"
    """
    alg = algorithm.upper().strip()
    # HC2L and HC2L are the same algorithm - normalize to HC2L
    if alg in ("HC2L", "HC2L", "DHCL2", "HC2L2"):
        return "HC2L"
    elif alg in ("DHL", "D-HL"):
        return "DHL"
    else:
        return alg


def is_hc2l_algorithm(algorithm: str) -> bool:
    """
    Check if the algorithm is HC2L/HC2L.
    
    Args:
        algorithm: Algorithm name (case insensitive)
        
    Returns:
        True if algorithm is HC2L/HC2L variant
    """
    normalized = normalize_algorithm_name(algorithm)
    return normalized == "HC2L"


# ============================================================================
# CSV HEADERS - STRICTLY ENFORCED, DO NOT CHANGE
# ============================================================================

# 7.1 Summary Tab - Summary Results Log
CSV_HEADERS_SUMMARY = [
    "trial_id", "batch_id", "disruption_level",
    "num_accident", "num_construction", "num_congestion", 
    "num_disabled_vehicle", "num_mass_transit_event", "num_planned_event",
    "num_road_hazard", "num_road_closure", "num_weather",
    "num_lane_restriction", "num_other"
]

# 7.2 Accuracy Tab - Accuracy Results Log (HC2L only)
CSV_HEADERS_ACCURACY = [
    "trial_id", "batch_id", "disruption_level", 
    "source_node", "target_node", "query_id",
    "dhc2l_distance", "dijkstra_distance", 
    "distance_error", "relative_error", "is_correct"
]

# 6.1 Construction Tab - Initial Construction Performance
CSV_HEADERS_CONSTRUCTION = [
    "trial_id", "batch_id", "disruption_level",
    "source_node", "target_node", "query_id", "is_correct",
    "algorithm",
    "initial_construction_time_ms", "initial_label_size_mb"
]

# 6.2 Updates Tab - Dynamic Performance Log
CSV_HEADERS_UPDATES = [
    "trial_id", "batch_id", "disruption_level",
    "source_node", "target_node", "query_id",
    "label_size_change_pct", "lazy_update_time_ms", "peak_label_size_mb",
    "query_response_time_ms", "threshold_rebuild_time_ms"
]

# 6.3 Performance Tab - Combined DHL vs HC2L Performance Summary
CSV_HEADERS_PERFORMANCE = [
    "trial_id", "batch_id", "disruption_level",
    "source_node", "target_node", "query_id",
    "algorithm", "initial_labeling_time_ms", "query_time_ms", 
    "label_size_mb", "peak_label_size_mb", "lazy_update_time_ms", 
    "threshold_rebuild_time_ms", "total_rebuilds"
]

# 6.4 Similarity Tab - HERE vs HC2L Route Comparison
CSV_HEADERS_SIMILARITY = [
    "batch_id", "route_id", "disruption_level",
    "source_node", "target_node", "od_pair",
    "dhc2l_distance_km", "here_distance_km", "distance_deviation_pct",
    "dhc2l_travel_time_min", "here_travel_time_min", "time_deviation_pct",
    "dhc2l_start_road", "dhc2l_end_road", "here_start_road", "here_end_road",
    "frechet_distance_m", "fd_rating", "ttd_rating"
]

# ============================================================================
# SCENARIO PRESET CSV HEADERS (for 1 route × 10 scenarios × 3 severities × 3 categories)
# These replace trial-based headers with route_category and scenario_id
# ============================================================================

# Scenario Summary - Incidents per route category/scenario
CSV_HEADERS_SCENARIO_SUMMARY = [
    "route_category", "route_id", "scenario_id", "severity_level",
    "num_accident", "num_construction", "num_congestion", 
    "num_disabled_vehicle", "num_mass_transit_event", "num_planned_event",
    "num_road_hazard", "num_road_closure", "num_weather",
    "num_lane_restriction", "num_other"
]

# Scenario Accuracy - per simulation accuracy
CSV_HEADERS_SCENARIO_ACCURACY = [
    "route_category", "route_id", "scenario_id", "severity_level",
    "source_node", "target_node", "route_distance_km",
    "dhc2l_distance", "dijkstra_distance", 
    "distance_error", "relative_error", "is_correct"
]

# Scenario Performance - per simulation performance
CSV_HEADERS_SCENARIO_PERFORMANCE = [
    "route_category", "route_id", "scenario_id", "severity_level",
    "source_node", "target_node", "route_distance_km",
    "algorithm", "initial_labeling_time_ms", "query_time_ms", 
    "label_size_mb", "peak_label_size_mb", "lazy_update_time_ms", 
    "threshold_rebuild_time_ms", "total_rebuilds"
]

# Scenario Construction - per route construction performance (all route data)
CSV_HEADERS_SCENARIO_CONSTRUCTION = [
    "route_id", "route_category", "scenario_id", "severity_level",
    "algorithm", "construction_time_ms", "initial_label_size_mb"
]

# Scenario Updates - per route update performance (all route data)
CSV_HEADERS_SCENARIO_UPDATES = [
    "route_id", "route_category", "scenario_id", "severity_level",
    "algorithm", "lazy_update_time_ms",
    "peak_label_size_mb", "label_size_change_pct", "query_avg_ms"
]

# Scenario Comprehensive - All simulation data in a single row per route/scenario/severity
CSV_HEADERS_SCENARIO_COMPREHENSIVE = [
    # Route identification
    "route_id",
    "route_start_lat", "route_start_lon",
    "route_end_lat", "route_end_lon",
    "route_start_edge_source", "route_start_edge_target",
    "route_end_edge_source", "route_end_edge_target",
    "route_start_name", "route_end_name",
    "route_length_category",
    # Disruption scenario
    "disruption_scenario_id", "disruption_scenario_name",
    "disruption_severity_level",
    # Incident counts
    "disruption_num_road_closure", "disruption_num_road_hazard",
    "disruption_num_construction", "disruption_num_congestion",
    "disruption_num_disabled_vehicle", "disruption_num_mass_transit_event",
    "disruption_num_planned_event", "disruption_num_weather",
    "disruption_num_lane_restriction", "disruption_num_other",
    "disruption_num_accident",
    # Algorithm performance
    "algorithm_labeling_time_ms", "algorithm_label_size_mb",
    "algorithm_hc2l_query_response_time_ms", "algorithm_dhl_query_response_time_ms",
    "algorithm_here_query_response_time_ms",
    "algorithm_here_travel_time_sec", "algorithm_dhc2l_travel_time_sec",
    "algorithm_dhl_travel_time_sec",
    "algorithm_here_distance_km", "algorithm_dhc2l_distance_km",
    "algorithm_dhl_distance_km",
    "algorithm_frechet_distance_km",
    "algorithm_is_correct"
]

# Standard Comprehensive - All simulation data in a single row per route/trial/batch
CSV_HEADERS_STANDARD_COMPREHENSIVE = [
    # Route identification
    "route_id", "route_trial", "route_batch",
    "route_start_lat", "route_start_lon",
    "route_end_lat", "route_end_lon",
    "route_start_edge_source", "route_start_edge_target",
    "route_end_edge_source", "route_end_edge_target",
    "route_start_name", "route_end_name",
    # Disruption level
    "disruption_level",
    # Incident counts
    "disruption_num_road_closure", "disruption_num_road_hazard",
    "disruption_num_construction", "disruption_num_congestion",
    "disruption_num_disabled_vehicle", "disruption_num_mass_transit_event",
    "disruption_num_planned_event", "disruption_num_weather",
    "disruption_num_lane_restriction", "disruption_num_other",
    "disruption_num_accident",
    # Algorithm performance
    "algorithm_labeling_time_ms", "algorithm_label_size_mb",
    "algorithm_hc2l_query_response_time_ms", "algorithm_dhl_query_response_time_ms",
    "algorithm_here_query_response_time_ms",
    "algorithm_here_travel_time_sec", "algorithm_dhc2l_travel_time_sec",
    "algorithm_dhl_travel_time_sec",
    "algorithm_here_distance_km", "algorithm_dhc2l_distance_km",
    "algorithm_dhl_distance_km",
    "algorithm_frechet_distance_km",
    "algorithm_is_correct"
]

# ============================================================================
# LABELING TAB CSV HEADERS - Disruption Node Labeling Accuracy
# ============================================================================

# Labeling Results - Per-route labeling accuracy metrics
CSV_HEADERS_LABELING_RESULTS = [
    "route_id", "route_category", "scenario_id", "severity_level",
    "algorithm",
    "total_disrupted_edges", "total_disrupted_nodes",
    "dirty_nodes_marked", "nodes_repaired",
    "labeling_accuracy_pct"
]

# Injected Disruptions - Ground truth (what was injected)
CSV_HEADERS_INJECTED_DISRUPTIONS = [
    "route_id", "route_category", "scenario_id", "severity_level",
    "edge_source", "edge_target",
    "incident_type", "incident_criticality", "jam_factor",
    "road_name"
]

# System Labels - What the system detected/labeled
CSV_HEADERS_SYSTEM_LABELS = [
    "route_id", "route_category", "scenario_id", "severity_level",
    "algorithm",
    "edge_source", "edge_target",
    "detected_label", "is_road_closed",
    "was_detected"
]


class DisruptionLevel(Enum):
    """Disruption level categories"""
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


def get_disruption_level(batch_id: int) -> str:
    """
    Map batch ID to disruption level.
    
    Per specification:
        Batch 1 → Light
        Batch 2 → Medium  
        Batch 3 → Heavy
    
    Args:
        batch_id: 1-indexed batch number
        
    Returns:
        Disruption level string
    """
    mapping = {1: "light", 2: "medium", 3: "heavy"}
    return mapping.get(batch_id, "light")


# ============================================================================
# DATA CLASSES FOR METRICS
# ============================================================================

@dataclass
class IncidentSummary:
    """
    Batch-level incident summary for traceability.
    All incident counts are aggregated at the batch level.
    
    Valid incident types:
    - accident, construction, disabledVehicle, massTransit, plannedEvent
    - roadHazard, weather, laneRestriction, roadClosure, other
    - congestion (from flow disruptions)
    """
    num_incidents_total: int = 0
    num_accident: int = 0
    num_construction: int = 0
    num_disabled_vehicle: int = 0
    num_mass_transit_event: int = 0
    num_planned_event: int = 0
    num_road_hazard: int = 0
    num_road_closure: int = 0
    num_weather: int = 0
    num_lane_restriction: int = 0
    num_congestion: int = 0
    num_other: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_disruption_data(cls, disruption_data: Optional[Dict]) -> "IncidentSummary":
        """Create IncidentSummary from disruption data dictionary"""
        if not disruption_data:
            return cls()
        
        summary = cls()
        
        # Count flow disruptions as congestion incidents
        # Flow disruptions represent traffic slowdowns/congestion
        flow_disruptions = disruption_data.get("flow", [])
        summary.num_congestion = len(flow_disruptions)
        summary.num_incidents_total += summary.num_congestion
        
        # Count explicit incident types
        # Valid incident types:
        # - accident, construction, disabledVehicle, massTransit, plannedEvent
        # - roadHazard, weather, laneRestriction, other, roadClosure
        incidents = disruption_data.get("incidents", [])
        for incident in incidents:
            incident_type = incident.get("incident_type", "").lower()
            summary.num_incidents_total += 1
            
            if "roadclosure" in incident_type or "closure" in incident_type:
                summary.num_road_closure += 1
            elif "accident" in incident_type:
                summary.num_accident += 1
            elif "construction" in incident_type:
                summary.num_construction += 1
            elif "disabledvehicle" in incident_type or "disabled" in incident_type:
                summary.num_disabled_vehicle += 1
            elif "masstransit" in incident_type or "transit" in incident_type:
                summary.num_mass_transit_event += 1
            elif "plannedevent" in incident_type or "planned" in incident_type or "event" in incident_type:
                summary.num_planned_event += 1
            elif "roadhazard" in incident_type or "hazard" in incident_type:
                summary.num_road_hazard += 1
            elif "weather" in incident_type:
                summary.num_weather += 1
            elif "lanerestriction" in incident_type or ("lane" in incident_type and "restriction" in incident_type):
                summary.num_lane_restriction += 1
            else:
                summary.num_other += 1
        
        return summary


@dataclass
class AccuracyMetrics:
    """
    Per-route accuracy metrics.
    Accuracy = correctness of query output (HC2L vs Dijkstra distance).
    """
    dhc2l_distance: float = 0.0
    dijkstra_distance: float = 0.0
    distance_error: float = 0.0
    relative_error: float = 0.0
    is_correct: bool = False
    tolerance: float = DEFAULT_TOLERANCE
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def compute(dhc2l_distance: float, dijkstra_distance: float, 
                tolerance: float = DEFAULT_TOLERANCE,
                query_time_ms: float = None) -> "AccuracyMetrics":
        """
        Compute accuracy metrics from distances.
        
        Args:
            dhc2l_distance: Distance from HC2L/DHL algorithm (in meters)
            dijkstra_distance: Distance from Dijkstra (in meters)
            tolerance: Tolerance for relative error
            query_time_ms: Query response time in milliseconds (optional)
                          If provided and distance is 0, check if it's a failed query
        
        Returns:
            AccuracyMetrics instance with is_correct flag
        """
        # Check for zero-result failure: if distance and time are both 0, 
        # this indicates a failed query/experiment
        if dhc2l_distance == 0 and query_time_ms is not None and query_time_ms == 0:
            return AccuracyMetrics(
                dhc2l_distance=0.0,
                dijkstra_distance=dijkstra_distance,
                distance_error=-dijkstra_distance,
                relative_error=float('inf') if dijkstra_distance > 0 else 0.0,
                is_correct=False,  # Failed experiment
                tolerance=tolerance
            )
        
        if dijkstra_distance <= 0:
            return AccuracyMetrics(
                dhc2l_distance=dhc2l_distance,
                dijkstra_distance=dijkstra_distance,
                distance_error=dhc2l_distance,
                relative_error=float('inf') if dhc2l_distance > 0 else 0.0,
                is_correct=dhc2l_distance == 0,
                tolerance=tolerance
            )
        
        distance_error = dhc2l_distance - dijkstra_distance
        relative_error = abs(distance_error) / dijkstra_distance
        is_correct = relative_error <= tolerance
        
        return AccuracyMetrics(
            dhc2l_distance=dhc2l_distance,
            dijkstra_distance=dijkstra_distance,
            distance_error=distance_error,
            relative_error=relative_error,
            is_correct=is_correct,
            tolerance=tolerance
        )


@dataclass
class PerformanceMetrics:
    """
    Performance metrics (CONDITIONALLY recorded based on accuracy).
    All fields remain None if is_correct == FALSE.
    """
    query_response_time_ms: Optional[float] = None
    labeling_time_ms: Optional[float] = None
    labeling_size_mb: Optional[float] = None
    lazy_update_time_ms: Optional[float] = None
    threshold_rebuild_time_ms: Optional[float] = None
    peak_label_size_mb: Optional[float] = None
    total_rebuilds: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def clear(self):
        """Clear all metrics (used when accuracy fails)"""
        self.query_response_time_ms = None
        self.labeling_time_ms = None
        self.labeling_size_mb = None
        self.lazy_update_time_ms = None
        self.threshold_rebuild_time_ms = None
        self.peak_label_size_mb = None


@dataclass
class ConstructionMetrics:
    """Initial construction phase metrics"""
    initial_construction_time_ms: float = 0.0
    initial_label_size_mb: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SimilarityMetrics:
    """HERE vs HC2L route comparison metrics"""
    dhc2l_distance_km: float = 0.0
    here_distance_km: float = 0.0
    distance_deviation_pct: float = 0.0
    dhc2l_travel_time_min: float = 0.0
    here_travel_time_min: float = 0.0
    time_deviation_pct: float = 0.0
    dhc2l_start_road: str = ""
    dhc2l_end_road: str = ""
    here_start_road: str = ""
    here_end_road: str = ""
    frechet_distance_m: float = 0.0
    fd_rating: str = "N/A"
    ttd_rating: str = "N/A"
    here_query_time_ms: float = 0.0  # HERE API query response time
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RouteMetricsRecord:
    """
    Complete per-route metrics record for all logging purposes.
    Each route produces ONE instance of this record.
    """
    # Identifiers
    trial_id: int = 0
    batch_id: int = 0
    query_id: int = 0
    source_node: int = 0
    target_node: int = 0
    algorithm: str = "HC2L"
    
    # Disruption context
    disruption_level: str = "light"
    incident_summary: IncidentSummary = field(default_factory=IncidentSummary)
    
    # Accuracy metrics (ALWAYS recorded)
    accuracy: AccuracyMetrics = field(default_factory=AccuracyMetrics)
    
    # Performance metrics (CONDITIONALLY recorded)
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    
    # Construction metrics (per trial)
    construction: ConstructionMetrics = field(default_factory=ConstructionMetrics)
    
    # Update metrics
    label_size_change_pct: float = 0.0
    
    # Metadata
    timestamp: str = ""
    error: Optional[str] = None
    
    def to_summary_row(self) -> Dict:
        """Convert to summary CSV row"""
        return {
            "trial_id": self.trial_id,
            "batch_id": self.batch_id,
            "disruption_level": self.disruption_level,
            "num_accident": self.incident_summary.num_accident,
            "num_construction": self.incident_summary.num_construction,
            "num_congestion": self.incident_summary.num_congestion,
            "num_disabled_vehicle": self.incident_summary.num_disabled_vehicle,
            "num_mass_transit_event": self.incident_summary.num_mass_transit_event,
            "num_planned_event": self.incident_summary.num_planned_event,
            "num_road_hazard": self.incident_summary.num_road_hazard,
            "num_road_closure": self.incident_summary.num_road_closure,
            "num_weather": self.incident_summary.num_weather,
            "num_lane_restriction": self.incident_summary.num_lane_restriction,
            "num_other": self.incident_summary.num_other
        }
    
    def to_accuracy_row(self) -> Dict:
        """Convert to accuracy CSV row (HC2L only)"""
        return {
            "trial_id": self.trial_id,
            "batch_id": self.batch_id,
            "disruption_level": self.disruption_level,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "query_id": self.query_id,
            "dhc2l_distance": self.accuracy.dhc2l_distance,
            "dijkstra_distance": self.accuracy.dijkstra_distance,
            "distance_error": self.accuracy.distance_error,
            "relative_error": self.accuracy.relative_error,
            "is_correct": self.accuracy.is_correct
        }
    
    def to_construction_row(self) -> Dict:
        """Convert to construction CSV row"""
        return {
            "trial_id": self.trial_id,
            "batch_id": self.batch_id,
            "disruption_level": self.disruption_level,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "query_id": self.query_id,
            "is_correct": self.accuracy.is_correct,
            "initial_construction_time_ms": self.construction.initial_construction_time_ms,
            "initial_label_size_mb": self.construction.initial_label_size_mb
        }
    
    def to_updates_row(self) -> Dict:
        """Convert to updates CSV row"""
        return {
            "trial_id": self.trial_id,
            "batch_id": self.batch_id,
            "disruption_level": self.disruption_level,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "query_id": self.query_id,
            "label_size_change_pct": self.label_size_change_pct,
            "lazy_update_time_ms": self.performance.lazy_update_time_ms,
            "peak_label_size_mb": self.performance.peak_label_size_mb,
            "query_response_time_ms": self.performance.query_response_time_ms,
            "threshold_rebuild_time_ms": self.performance.threshold_rebuild_time_ms
        }
    
    def to_performance_row(self) -> Dict:
        """Convert to performance CSV row"""
        return {
            "trial_id": self.trial_id,
            "batch_id": self.batch_id,
            "disruption_level": self.disruption_level,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "query_id": self.query_id,
            "algorithm": self.algorithm,
            "initial_labeling_time_ms": self.performance.labeling_time_ms,
            "query_time_ms": self.performance.query_response_time_ms,
            "label_size_mb": self.performance.labeling_size_mb,
            "peak_label_size_mb": self.performance.peak_label_size_mb,
            "lazy_update_time_ms": self.performance.lazy_update_time_ms,
            "threshold_rebuild_time_ms": self.performance.threshold_rebuild_time_ms,
            "total_rebuilds": self.performance.total_rebuilds
        }


@dataclass  
class SimilarityRecord:
    """Complete similarity record for HERE vs HC2L comparison"""
    batch_id: int = 0
    route_id: int = 0
    disruption_level: str = "light"
    source_node: int = 0
    target_node: int = 0
    od_pair: str = ""
    similarity: SimilarityMetrics = field(default_factory=SimilarityMetrics)
    
    def to_similarity_row(self) -> Dict:
        """Convert to similarity CSV row"""
        return {
            "batch_id": self.batch_id,
            "route_id": self.route_id,
            "disruption_level": self.disruption_level,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "od_pair": self.od_pair,
            "dhc2l_distance_km": self.similarity.dhc2l_distance_km,
            "here_distance_km": self.similarity.here_distance_km,
            "distance_deviation_pct": self.similarity.distance_deviation_pct,
            "dhc2l_travel_time_min": self.similarity.dhc2l_travel_time_min,
            "here_travel_time_min": self.similarity.here_travel_time_min,
            "time_deviation_pct": self.similarity.time_deviation_pct,
            "dhc2l_start_road": self.similarity.dhc2l_start_road,
            "dhc2l_end_road": self.similarity.dhc2l_end_road,
            "here_start_road": self.similarity.here_start_road,
            "here_end_road": self.similarity.here_end_road,
            "frechet_distance_m": self.similarity.frechet_distance_m,
            "fd_rating": self.similarity.fd_rating,
            "ttd_rating": self.similarity.ttd_rating
        }


# ============================================================================
# EXPERIMENT METRICS COLLECTOR CLASS
# ============================================================================

class ExperimentMetricsCollector:
    """
    Centralized metrics collector for experiment data.
    
    Features:
    - Thread-safe recording of all metrics
    - Pre-computed CSV exports for each GUI tab
    - Accuracy-first gating for performance metrics
    - Minimal JSON configuration output
    - Scenario mode support (1 route × 10 scenarios × 3 severities × 3 categories)
    """
    
    def __init__(self, 
                 results_path: Path,
                 trials: int = 3, 
                 batches: int = 3, 
                 routes_per_batch: int = 1000,
                 tolerance: float = DEFAULT_TOLERANCE,
                 preset_type: str = "standard"):
        """
        Initialize the metrics collector.
        
        Args:
            results_path: Path to results folder for saving CSV/JSON files
            trials: Number of trials in experiment
            batches: Number of batches per trial  
            routes_per_batch: Number of routes per batch
            tolerance: Accuracy tolerance threshold (default 5%)
            preset_type: "standard" or "scenario" for different output formats
        """
        self.results_path = Path(results_path)
        self.trials = trials
        self.batches = batches
        self.routes_per_batch = routes_per_batch
        self.tolerance = tolerance
        self.preset_type = preset_type
        self.is_scenario_mode = preset_type == "scenario"
        
        # Scenario-specific settings
        if self.is_scenario_mode:
            self.route_categories = ["short", "medium", "long"]
            self.routes_per_category = 10
            self.scenarios = ["DS1", "DS2", "DS3", "DS4", "DS5", "DS6", "DS7", "DS8", "DS9", "DS10"]
            self.severity_levels = ["light", "medium", "heavy"]
            self.total_simulations = 900  # 3 categories × 10 routes × 10 scenarios × 3 severities
        
        # Create results directory
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        # Thread-safe locks
        self.lock = threading.Lock()
        self.csv_lock = threading.Lock()
        
        # Scenario metrics storage
        self.scenario_records: List[Dict] = []  # For scenario mode
        
        # ====================================================================
        # METRICS STORAGE - Lists for CSV export
        # ====================================================================
        
        # Per-route metrics records (DHL and HC2L)
        self.route_records_dhl: List[RouteMetricsRecord] = []
        self.route_records_dhc2l: List[RouteMetricsRecord] = []
        
        # Similarity records (HERE vs HC2L)
        self.similarity_records: List[SimilarityRecord] = []
        
        # ====================================================================
        # LABELING ACCURACY STORAGE - For Labeling Tab
        # ====================================================================
        # Per-route labeling accuracy records
        self.labeling_records: List[Dict] = []
        # Ground truth - injected disruption edges
        self.injected_disruptions: List[Dict] = []
        # System detected labels
        self.system_labels: List[Dict] = []
        
        # Incident summaries per batch (trial -> batch -> IncidentSummary)
        self.incident_summaries: Dict[Tuple[int, int], IncidentSummary] = {}
        
        # Construction metrics per trial per algorithm
        self.construction_dhl: Dict[int, ConstructionMetrics] = {}
        self.construction_dhc2l: Dict[int, ConstructionMetrics] = {}
        
        # ====================================================================
        # NUMPY ARRAYS FOR EFFICIENT COMPUTATION
        # ====================================================================
        shape = (trials, batches, routes_per_batch)
        batch_shape = (trials, batches)
        
        # Query times
        self.query_time_dhl = np.zeros(shape, dtype=np.float64)
        self.query_time_dhc2l = np.zeros(shape, dtype=np.float64)
        
        # Label sizes
        self.label_size_dhl = np.zeros(shape, dtype=np.float64)
        self.label_size_dhc2l = np.zeros(shape, dtype=np.float64)
        
        # Peak label sizes per batch
        self.peak_label_size_dhl = np.zeros(batch_shape, dtype=np.float64)
        self.peak_label_size_dhc2l = np.zeros(batch_shape, dtype=np.float64)
        
        # Lazy update times per batch
        self.lazy_update_time_dhl = np.zeros(batch_shape, dtype=np.float64)
        self.lazy_update_time_dhc2l = np.zeros(batch_shape, dtype=np.float64)
        
        # Threshold rebuild times per batch
        self.threshold_rebuild_time_dhl = np.zeros(batch_shape, dtype=np.float64)
        self.threshold_rebuild_time_dhc2l = np.zeros(batch_shape, dtype=np.float64)
        
        # Rebuild counts per batch
        self.rebuild_count_dhl = np.zeros(batch_shape, dtype=np.int32)
        self.rebuild_count_dhc2l = np.zeros(batch_shape, dtype=np.int32)
        
        # Accuracy metrics (HC2L only)
        self.dhc2l_distance = np.zeros(shape, dtype=np.float64)
        self.dijkstra_distance = np.zeros(shape, dtype=np.float64)
        self.distance_error = np.zeros(shape, dtype=np.float64)
        self.relative_error = np.zeros(shape, dtype=np.float64)
        self.is_correct = np.zeros(shape, dtype=np.bool_)
        
        # Filled tracking
        self.filled_dhl = np.zeros(shape, dtype=np.bool_)
        self.filled_dhc2l = np.zeros(shape, dtype=np.bool_)
        
        # Initial label sizes per trial
        self.initial_label_size_dhl = np.zeros(trials, dtype=np.float64)
        self.initial_label_size_dhc2l = np.zeros(trials, dtype=np.float64)
        
        # Construction times per trial
        self.construction_time_dhl = np.zeros(trials, dtype=np.float64)
        self.construction_time_dhc2l = np.zeros(trials, dtype=np.float64)
        
        # Construction recorded flags
        self.construction_recorded_dhl = np.zeros(trials, dtype=np.bool_)
        self.construction_recorded_dhc2l = np.zeros(trials, dtype=np.bool_)
        
        # ====================================================================
        # BATCH ACCUMULATION BUFFERS
        # ====================================================================
        self._batch_query_times_dhl = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_query_times_dhc2l = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_lazy_times_dhl = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_lazy_times_dhc2l = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_label_sizes_dhl = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_label_sizes_dhc2l = [[[] for _ in range(batches)] for _ in range(trials)]
        
        # ====================================================================
        # GRAPH DATA STORAGE
        # ====================================================================
        self._batch_jam_factors = [[[] for _ in range(batches)] for _ in range(trials)]
        self._batch_error_rates = [[[] for _ in range(batches)] for _ in range(trials)]
        
        # HERE comparison progress
        self.here_comparison_progress = {
            'completed': 0,
            'total': routes_per_batch,
            'status': 'not_started',
            'current_route': 0,
            'errors': 0,
            'start_time': None
        }
        
        logger.info(f"MetricsCollector initialized: {trials} trials × {batches} batches × {routes_per_batch} routes")
        logger.info(f"Results path: {self.results_path}")
    
    # ========================================================================
    # RECORDING METHODS
    # ========================================================================
    
    def record_route_metric(self, 
                           trial: int, 
                           batch: int, 
                           route: int,
                           algorithm: str,
                           api_result: Dict,
                           disruption_data: Optional[Dict] = None) -> RouteMetricsRecord:
        """
        Record metrics for a single route execution.
        
        Implements accuracy validation for both DHL and DHC2L:
        1. Extract algorithm distance from API result
        2. Extract Dijkstra reference distance
        3. Compute accuracy metrics (both algorithms)
        4. Extract and record performance metrics (always recorded)
        
        For scenario mode, also stores in scenario_records list.
        
        Args:
            trial: Trial index (0-based)
            batch: Batch index (0-based)
            route: Route index (0-based)
            algorithm: "DHL" or "HC2L"
            api_result: Result from C++ API call
            disruption_data: Optional disruption data for incident summary
            
        Returns:
            Complete RouteMetricsRecord with accuracy and performance
        """
        with self.lock:
            try:
                # Check if scenario mode and extract scenario metadata from api_result
                is_scenario = self.is_scenario_mode
                scenario_metadata = None
                if is_scenario:
                    scenario_metadata = {
                        "route_category": api_result.get("route_category", "unknown"),
                        "scenario_id": api_result.get("scenario_id", "unknown"),
                        "severity_level": api_result.get("severity_level", "unknown"),
                        "route_id": route + 1
                    }
                
                # Normalize algorithm name - accept both "HC2L" and "HC2L"
                alg = normalize_algorithm_name(algorithm)
                is_hc2l = is_hc2l_algorithm(algorithm)
                
                # Create record
                record = RouteMetricsRecord(
                    trial_id=trial + 1,  # 1-indexed for logging
                    batch_id=batch + 1,
                    query_id=route + 1,
                    algorithm=alg,
                    disruption_level=get_disruption_level(batch + 1),
                    timestamp=datetime.now().isoformat()
                )
                
                # Extract node information
                gps_mapping = api_result.get("gps_mapping", {})
                record.source_node = gps_mapping.get("start_node", 0)
                record.target_node = gps_mapping.get("dest_node", 0)
                
                # Get incident summary from disruption data or cache
                batch_key = (trial, batch)
                if batch_key in self.incident_summaries:
                    record.incident_summary = self.incident_summaries[batch_key]
                elif disruption_data:
                    record.incident_summary = IncidentSummary.from_disruption_data(disruption_data)
                    self.incident_summaries[batch_key] = record.incident_summary
                
                # ============================================================
                # STEP 1: ACCURACY COMPUTATION (both DHL and DHC2L)
                # ============================================================
                metrics = api_result.get("metrics", {})
                
                # Extract query time early for accuracy validation
                summary = api_result.get("summary", {})
                query_phase = api_result.get("query_phase", {})
                query_time = float(query_phase.get("query_time_ms", 0) or 
                                  summary.get("query_time_ms", 0) or 0)
                
                if is_hc2l:
                    # HC2L/DHC2L: Extract distances from API result
                    dhc2l_dist = float(metrics.get("calculated_distance_meters", 0))
                    dijkstra_dist = float(metrics.get("dijkstra_distance_meter", 0))
                    
                    record.accuracy = AccuracyMetrics.compute(
                        dhc2l_dist, dijkstra_dist, self.tolerance, query_time
                    )
                    
                    # Store in numpy arrays
                    self.dhc2l_distance[trial, batch, route] = dhc2l_dist
                    self.dijkstra_distance[trial, batch, route] = dijkstra_dist
                    self.distance_error[trial, batch, route] = record.accuracy.distance_error
                    self.relative_error[trial, batch, route] = record.accuracy.relative_error
                    self.is_correct[trial, batch, route] = record.accuracy.is_correct
                else:
                    # DHL: Extract DHL distance and compute Dijkstra reference
                    dhl_dist = float(metrics.get("calculated_distance_meters", 0))
                    dijkstra_dist = float(metrics.get("dijkstra_distance_meter", 0))
                    
                    record.accuracy = AccuracyMetrics.compute(
                        dhl_dist, dijkstra_dist, self.tolerance, query_time
                    )
                    
                    # Store in numpy arrays
                    self.dhc2l_distance[trial, batch, route] = dhl_dist  # Reuse array for DHL
                    self.dijkstra_distance[trial, batch, route] = dijkstra_dist
                    self.distance_error[trial, batch, route] = record.accuracy.distance_error
                    self.relative_error[trial, batch, route] = record.accuracy.relative_error
                    self.is_correct[trial, batch, route] = record.accuracy.is_correct
                
                # ============================================================
                # STEP 2: PERFORMANCE EXTRACTION (ALWAYS for both algorithms)
                # ============================================================
                update_phase = api_result.get("update_phase", {})
                label_size = float(summary.get("label_size", 0) or 0)
                lazy_time = float(update_phase.get("lazy_update_time_ms", 0) or 0)
                threshold_rebuild = float(update_phase.get("threshold_rebuild_time_ms", 0) or 0)
                is_rebuild = update_phase.get("update_strategy", "") == "immediate_update"
                
                # Always record performance metrics for both DHL and HC2L
                # Performance data is independent of accuracy validation
                record.performance = PerformanceMetrics(
                    query_response_time_ms=query_time,
                    labeling_time_ms=self._extract_labeling_time(api_result),
                    labeling_size_mb=label_size,
                    lazy_update_time_ms=lazy_time,
                    threshold_rebuild_time_ms=threshold_rebuild,
                    peak_label_size_mb=float(summary.get("peak_label_size_mb", label_size) or label_size)
                )
                
                # ============================================================
                # STEP 3: STORE IN NUMPY ARRAYS
                # ============================================================
                if is_hc2l:
                    self.query_time_dhc2l[trial, batch, route] = query_time
                    self.label_size_dhc2l[trial, batch, route] = label_size
                    self.filled_dhc2l[trial, batch, route] = True
                    
                    # Batch accumulators
                    self._batch_query_times_dhc2l[trial][batch].append(query_time)
                    self._batch_lazy_times_dhc2l[trial][batch].append(lazy_time)
                    self._batch_label_sizes_dhc2l[trial][batch].append(label_size)
                    
                    # Peak label size tracking
                    if label_size > self.peak_label_size_dhc2l[trial, batch]:
                        self.peak_label_size_dhc2l[trial, batch] = label_size
                    
                    # Rebuild tracking
                    if route == 0 and threshold_rebuild > 0:
                        self.threshold_rebuild_time_dhc2l[trial, batch] = threshold_rebuild
                    if is_rebuild:
                        self.rebuild_count_dhc2l[trial, batch] += 1
                    
                    # Store record
                    self.route_records_dhc2l.append(record)
                else:
                    self.query_time_dhl[trial, batch, route] = query_time
                    self.label_size_dhl[trial, batch, route] = label_size
                    self.filled_dhl[trial, batch, route] = True
                    
                    # Batch accumulators
                    self._batch_query_times_dhl[trial][batch].append(query_time)
                    self._batch_lazy_times_dhl[trial][batch].append(lazy_time)
                    self._batch_label_sizes_dhl[trial][batch].append(label_size)
                    
                    # Peak label size tracking
                    if label_size > self.peak_label_size_dhl[trial, batch]:
                        self.peak_label_size_dhl[trial, batch] = label_size
                    
                    # Rebuild tracking
                    if route == 0 and threshold_rebuild > 0:
                        self.threshold_rebuild_time_dhl[trial, batch] = threshold_rebuild
                    if is_rebuild:
                        self.rebuild_count_dhl[trial, batch] += 1
                    
                    # Store record
                    self.route_records_dhl.append(record)
                
                # ============================================================
                # STEP 4: RECORD CONSTRUCTION (first route of trial)
                # ============================================================
                if batch == 0 and route == 0:
                    self._record_construction_from_result(trial, alg, api_result, record)
                
                # ============================================================
                # STEP 5: SCENARIO MODE - Store in scenario_records for BOTH algorithms
                # ============================================================
                if is_scenario and scenario_metadata:
                    # Extract travel time (ETA) from metrics
                    eta_seconds = float(metrics.get("eta_seconds", 0) or 0)
                    
                    # Record BOTH DHL and HC2L in scenario mode
                    scenario_record = {
                        "algorithm": alg,  # "DHL" or "HC2L"
                        "route_category": scenario_metadata["route_category"],
                        "route_id": scenario_metadata["route_id"],
                        "scenario_id": scenario_metadata["scenario_id"],
                        "scenario_name": api_result.get("scenario_name", ""),
                        "severity_level": scenario_metadata["severity_level"],
                        "source_node": record.source_node,
                        "target_node": record.target_node,
                        "route_distance_km": api_result.get("route_distance_km", 0),
                        "dhc2l_distance": record.accuracy.dhc2l_distance if record.accuracy else 0,
                        "dijkstra_distance": record.accuracy.dijkstra_distance if record.accuracy else 0,
                        "distance_error": record.accuracy.distance_error if record.accuracy else 0,
                        "relative_error": record.accuracy.relative_error if record.accuracy else 0,
                        "is_correct": record.accuracy.is_correct if record.accuracy else False,
                        "query_time_ms": record.performance.query_response_time_ms if record.performance else 0,
                        "label_size_mb": record.performance.labeling_size_mb if record.performance else 0,
                        "labeling_time_ms": record.performance.labeling_time_ms if record.performance else 0,
                        "lazy_update_time_ms": record.performance.lazy_update_time_ms if record.performance else 0,
                        "peak_label_size_mb": record.performance.peak_label_size_mb if record.performance else 0,
                        # Travel time from ETA calculation
                        "travel_time_sec": eta_seconds,
                        # Route info for comprehensive CSV
                        "route_info": api_result.get("route_info", {}),
                    }
                    
                    # Add incident counts from disruption_data
                    if record.incident_summary:
                        scenario_record.update({
                            "num_accident": record.incident_summary.num_accident,
                            "num_construction": record.incident_summary.num_construction,
                            "num_congestion": record.incident_summary.num_congestion,
                            "num_disabled_vehicle": record.incident_summary.num_disabled_vehicle,
                            "num_mass_transit_event": record.incident_summary.num_mass_transit_event,
                            "num_planned_event": record.incident_summary.num_planned_event,
                            "num_road_hazard": record.incident_summary.num_road_hazard,
                            "num_road_closure": record.incident_summary.num_road_closure,
                            "num_weather": record.incident_summary.num_weather,
                            "num_lane_restriction": record.incident_summary.num_lane_restriction,
                            "num_other": record.incident_summary.num_other,
                        })
                    
                    self.scenario_records.append(scenario_record)
                
                return record
                
            except Exception as e:
                logger.error(f"Error recording route metric: {e}")
                return RouteMetricsRecord(error=str(e))
    
    def _record_construction_from_result(self, trial: int, algorithm: str, 
                                         api_result: Dict, record: RouteMetricsRecord):
        """Extract and record construction metrics from first route result"""
        construction_info = api_result.get("construction_info", {})
        construction_time = float(construction_info.get("construction_time_ms", 0) or 0)
        initial_label_size = float(construction_info.get("label_size_mb", 0) or 
                                  api_result.get("summary", {}).get("label_size", 0) or 0)
        
        record.construction = ConstructionMetrics(
            initial_construction_time_ms=construction_time,
            initial_label_size_mb=initial_label_size
        )
        
        # Use normalized algorithm check
        is_hc2l = is_hc2l_algorithm(algorithm)
        
        if not is_hc2l:  # DHL
            if not self.construction_recorded_dhl[trial]:
                self.construction_time_dhl[trial] = construction_time
                self.initial_label_size_dhl[trial] = initial_label_size
                self.construction_recorded_dhl[trial] = True
                self.construction_dhl[trial] = record.construction
        else:  # HC2L/HC2L
            if not self.construction_recorded_dhc2l[trial]:
                self.construction_time_dhc2l[trial] = construction_time
                self.initial_label_size_dhc2l[trial] = initial_label_size
                self.construction_recorded_dhc2l[trial] = True
                self.construction_dhc2l[trial] = record.construction
    
    def record_incident_summary(self, trial: int, batch: int, 
                                incident_summary: IncidentSummary):
        """Record batch-level incident summary"""
        with self.lock:
            self.incident_summaries[(trial, batch)] = incident_summary
    
    def record_similarity(self, 
                         batch: int,
                         route: int,
                         comparison_data: Dict) -> SimilarityRecord:
        """
        Record HERE vs HC2L similarity comparison.
        
        Args:
            batch: Batch index (0-based)
            route: Route index (0-based)
            comparison_data: Dict with all comparison metrics
            
        Returns:
            SimilarityRecord
        """
        with self.lock:
            try:
                record = SimilarityRecord(
                    batch_id=batch + 1,
                    route_id=route + 1,
                    disruption_level=get_disruption_level(batch + 1),
                    source_node=comparison_data.get('source_node', 0),
                    target_node=comparison_data.get('target_node', 0),
                    od_pair=f"{comparison_data.get('source_node', 'S')} → {comparison_data.get('target_node', 'D')}",
                    similarity=SimilarityMetrics(
                        dhc2l_distance_km=float(comparison_data.get('distance_km_hc2l', 0)),
                        here_distance_km=float(comparison_data.get('distance_km_here', 0)),
                        distance_deviation_pct=float(comparison_data.get('distance_deviation_pct', 0)),
                        dhc2l_travel_time_min=float(comparison_data.get('travel_time_min_hc2l', 0)),
                        here_travel_time_min=float(comparison_data.get('travel_time_min_here', 0)),
                        time_deviation_pct=float(comparison_data.get('time_deviation_pct', 0)),
                        dhc2l_start_road=comparison_data.get('start_road_hc2l', ''),
                        dhc2l_end_road=comparison_data.get('end_road_hc2l', ''),
                        here_start_road=comparison_data.get('start_road_here', ''),
                        here_end_road=comparison_data.get('end_road_here', ''),
                        frechet_distance_m=float(comparison_data.get('frechet_distance_m', 0)),
                        fd_rating=comparison_data.get('fd_rating', 'N/A'),
                        ttd_rating=comparison_data.get('ttd_rating', 'N/A'),
                        here_query_time_ms=float(comparison_data.get('query_time_ms_here', 0))
                    )
                )
                
                self.similarity_records.append(record)
                
                # Update progress
                self.here_comparison_progress['completed'] = len(self.similarity_records)
                self.here_comparison_progress['current_route'] = route
                if comparison_data.get('error'):
                    self.here_comparison_progress['errors'] += 1
                
                return record
                
            except Exception as e:
                logger.error(f"Error recording similarity: {e}")
                return SimilarityRecord()
    
    def record_labeling_data(self,
                             route_id: int,
                             route_category: str,
                             scenario_id: str,
                             severity_level: str,
                             algorithm: str,
                             disruption_edges: List[Dict],
                             lazy_hc2l_info: Dict = None,
                             dhl_update_info: Dict = None):
        """
        Record labeling accuracy data for a route.
        
        Tracks:
        - Injected disruptions (ground truth - edges that were disrupted)
        - System labels (what the algorithm detected/labeled)
        - Per-route labeling accuracy metrics
        
        Args:
            route_id: Route identifier
            route_category: "short", "medium", or "long"
            scenario_id: Scenario identifier (e.g., "DS1")
            severity_level: "light", "medium", or "heavy"
            algorithm: "HC2L" or "DHL"
            disruption_edges: List of dicts with edge disruption data
                              Each dict has: source, target, incident_type, criticality, jam_factor, road_name
            lazy_hc2l_info: HC2L algorithm output with dirty_nodes_marked, nodes_repaired
            dhl_update_info: DHL algorithm output with nodes_updated
        """
        with self.lock:
            try:
                # Count total disrupted edges and nodes
                total_disrupted_edges = len(disruption_edges)
                # Each edge affects 2 nodes (source and target)
                unique_nodes = set()
                for edge in disruption_edges:
                    unique_nodes.add(edge.get('source'))
                    unique_nodes.add(edge.get('target'))
                total_disrupted_nodes = len(unique_nodes)
                
                # Extract system detection metrics based on algorithm
                dirty_nodes_marked = 0
                nodes_repaired = 0
                
                if algorithm.upper() == "HC2L" and lazy_hc2l_info:
                    dirty_nodes_marked = lazy_hc2l_info.get("dirty_nodes_marked", 0)
                    nodes_repaired = lazy_hc2l_info.get("nodes_repaired", 0)
                elif algorithm.upper() == "DHL" and dhl_update_info:
                    nodes_repaired = dhl_update_info.get("nodes_updated", 0)
                    dirty_nodes_marked = nodes_repaired  # DHL doesn't use dirty marking
                
                # Calculate labeling accuracy
                # Accuracy = min(1.0, nodes_repaired / total_disrupted_nodes) * 100
                # If no nodes were disrupted, accuracy is 100%
                if total_disrupted_nodes > 0:
                    labeling_accuracy_pct = min(1.0, nodes_repaired / total_disrupted_nodes) * 100
                else:
                    labeling_accuracy_pct = 100.0
                
                # Record per-route labeling result
                labeling_record = {
                    "route_id": route_id,
                    "route_category": route_category,
                    "scenario_id": scenario_id,
                    "severity_level": severity_level,
                    "algorithm": algorithm.upper(),
                    "total_disrupted_edges": total_disrupted_edges,
                    "total_disrupted_nodes": total_disrupted_nodes,
                    "dirty_nodes_marked": dirty_nodes_marked,
                    "nodes_repaired": nodes_repaired,
                    "labeling_accuracy_pct": round(labeling_accuracy_pct, 2)
                }
                self.labeling_records.append(labeling_record)
                
                # Record injected disruptions (ground truth)
                for edge in disruption_edges:
                    injected_record = {
                        "route_id": route_id,
                        "route_category": route_category,
                        "scenario_id": scenario_id,
                        "severity_level": severity_level,
                        "edge_source": edge.get('source', 0),
                        "edge_target": edge.get('target', 0),
                        "incident_type": edge.get('incident_type', 'unknown'),
                        "incident_criticality": edge.get('incident_criticality', 'minor'),
                        "jam_factor": edge.get('jam_factor', 0.0),
                        "road_name": edge.get('road_name', 'Unknown Road')
                    }
                    self.injected_disruptions.append(injected_record)
                    
                    # Record system labels for each edge
                    # Since we know disruptions were applied, the system should have detected them
                    system_record = {
                        "route_id": route_id,
                        "route_category": route_category,
                        "scenario_id": scenario_id,
                        "severity_level": severity_level,
                        "algorithm": algorithm.upper(),
                        "edge_source": edge.get('source', 0),
                        "edge_target": edge.get('target', 0),
                        "detected_label": edge.get('incident_type', 'unknown'),
                        "is_road_closed": edge.get('incident_road_closed', False),
                        "was_detected": True  # Edges were processed, so they were detected
                    }
                    self.system_labels.append(system_record)
                
                logger.debug(f"Recorded labeling data: route={route_id}, edges={total_disrupted_edges}, nodes={total_disrupted_nodes}, accuracy={labeling_accuracy_pct:.1f}%")
                
            except Exception as e:
                logger.error(f"Error recording labeling data: {e}")
    
    def record_jam_factor(self, trial: int, batch: int, jam_factor: float):
        """Record jam factor for graph data"""
        with self.lock:
            self._batch_jam_factors[trial][batch].append(jam_factor)
    
    def record_error_rate(self, trial: int, batch: int, error_rate: float):
        """Record error rate for graph data"""
        with self.lock:
            self._batch_error_rates[trial][batch].append(error_rate)
    
    def _extract_labeling_time(self, api_result: Dict) -> Optional[float]:
        """Extract labeling time from API result"""
        metrics = api_result.get("metrics", {})
        labeling_info = metrics.get("labeling_info", {})
        
        if "index_load_time_ms" in labeling_info:
            return float(labeling_info["index_load_time_ms"])
        if "construction_time_ms" in labeling_info:
            return float(labeling_info["construction_time_ms"])
        
        construction_info = api_result.get("construction_info", {})
        if "construction_time_ms" in construction_info:
            return float(construction_info["construction_time_ms"])
        
        return None
    
    # ========================================================================
    # CSV EXPORT METHODS
    # ========================================================================
    
    def export_summary_csv(self) -> Path:
        """
        Export Summary Results Log CSV (7.1).
        Aggregates incident counts per trial, batch.
        """
        csv_path = self.results_path / "summary_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SUMMARY)
                writer.writeheader()
                
                # Aggregate from all records
                batch_summaries = {}
                
                # Process HC2L records (primary source for accuracy data)
                for record in self.route_records_dhc2l:
                    key = (record.trial_id, record.batch_id)
                    if key not in batch_summaries:
                        batch_summaries[key] = record.to_summary_row()
                
                # Fill in any missing batches from cached incident summaries
                for (trial, batch), summary in self.incident_summaries.items():
                    key = (trial + 1, batch + 1)
                    if key not in batch_summaries:
                        batch_summaries[key] = {
                            "trial_id": trial + 1,
                            "batch_id": batch + 1,
                            "disruption_level": get_disruption_level(batch + 1),
                            **{k: v for k, v in summary.to_dict().items() 
                               if k != "num_incidents_total"}
                        }
                
                # Write sorted rows
                for key in sorted(batch_summaries.keys()):
                    writer.writerow(batch_summaries[key])
        
        logger.info(f"Exported summary CSV: {csv_path}")
        return csv_path
    
    def export_accuracy_csv(self) -> Path:
        """
        Export Accuracy Results Log CSV (7.2).
        HC2L only - per route accuracy metrics.
        """
        csv_path = self.results_path / "accuracy_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_ACCURACY)
                writer.writeheader()
                
                for record in self.route_records_dhc2l:
                    writer.writerow(record.to_accuracy_row())
        
        logger.info(f"Exported accuracy CSV: {csv_path} ({len(self.route_records_dhc2l)} rows)")
        return csv_path
    
    def export_construction_csv(self) -> Path:
        """
        Export Construction Performance CSV (6.1).
        Initial construction times and label sizes per route.
        """
        csv_path = self.results_path / "construction_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_CONSTRUCTION)
                writer.writeheader()
                
                # Write HC2L construction records
                for record in self.route_records_dhc2l:
                    row = record.to_construction_row()
                    row["algorithm"] = "HC2L"
                    # Use per-trial construction times
                    trial_idx = record.trial_id - 1
                    if trial_idx in self.construction_dhc2l:
                        row["initial_construction_time_ms"] = self.construction_dhc2l[trial_idx].initial_construction_time_ms
                        row["initial_label_size_mb"] = self.construction_dhc2l[trial_idx].initial_label_size_mb
                    writer.writerow(row)
                
                # Write DHL construction records  
                for record in self.route_records_dhl:
                    row = record.to_construction_row()
                    row["algorithm"] = "DHL"
                    trial_idx = record.trial_id - 1
                    if trial_idx in self.construction_dhl:
                        row["initial_construction_time_ms"] = self.construction_dhl[trial_idx].initial_construction_time_ms
                        row["initial_label_size_mb"] = self.construction_dhl[trial_idx].initial_label_size_mb
                    writer.writerow(row)
        
        total_rows = len(self.route_records_dhc2l) + len(self.route_records_dhl)
        logger.info(f"Exported construction CSV: {csv_path} ({total_rows} rows)")
        return csv_path
    
    def export_updates_csv(self) -> Path:
        """
        Export Dynamic Updates CSV (6.2).
        Lazy update times, peak label sizes, query response times.
        """
        csv_path = self.results_path / "updates_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_UPDATES)
                writer.writeheader()
                
                # Write HC2L update records
                for record in self.route_records_dhc2l:
                    row = record.to_updates_row()
                    # Compute label size change percentage
                    trial_idx = record.trial_id - 1
                    if trial_idx in self.construction_dhc2l:
                        initial = self.construction_dhc2l[trial_idx].initial_label_size_mb
                        if initial > 0 and record.performance.peak_label_size_mb:
                            change_pct = ((record.performance.peak_label_size_mb - initial) / initial) * 100
                            row["label_size_change_pct"] = round(change_pct, 2)
                    writer.writerow(row)
                
                # Write DHL update records
                for record in self.route_records_dhl:
                    row = record.to_updates_row()
                    trial_idx = record.trial_id - 1
                    if trial_idx in self.construction_dhl:
                        initial = self.construction_dhl[trial_idx].initial_label_size_mb
                        if initial > 0 and record.performance.peak_label_size_mb:
                            change_pct = ((record.performance.peak_label_size_mb - initial) / initial) * 100
                            row["label_size_change_pct"] = round(change_pct, 2)
                    writer.writerow(row)
        
        total_rows = len(self.route_records_dhc2l) + len(self.route_records_dhl)
        logger.info(f"Exported updates CSV: {csv_path} ({total_rows} rows)")
        return csv_path
    
    def export_performance_csv(self) -> Path:
        """
        Export Performance Summary CSV (6.3).
        Combined DHL vs HC2L performance comparison.
        """
        csv_path = self.results_path / "performance_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_PERFORMANCE)
                writer.writeheader()
                
                # Write HC2L performance records
                for record in self.route_records_dhc2l:
                    row = record.to_performance_row()
                    trial_idx = record.trial_id - 1
                    batch_idx = record.batch_id - 1
                    row["total_rebuilds"] = int(self.rebuild_count_dhc2l[trial_idx, batch_idx])
                    writer.writerow(row)
                
                # Write DHL performance records
                for record in self.route_records_dhl:
                    row = record.to_performance_row()
                    trial_idx = record.trial_id - 1
                    batch_idx = record.batch_id - 1
                    row["total_rebuilds"] = int(self.rebuild_count_dhl[trial_idx, batch_idx])
                    writer.writerow(row)
        
        total_rows = len(self.route_records_dhc2l) + len(self.route_records_dhl)
        logger.info(f"Exported performance CSV: {csv_path} ({total_rows} rows)")
        return csv_path
    
    def export_similarity_csv(self) -> Path:
        """
        Export Similarity CSV (6.4).
        HERE vs HC2L route comparison.
        """
        csv_path = self.results_path / "similarity_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SIMILARITY)
                writer.writeheader()
                
                for record in self.similarity_records:
                    writer.writerow(record.to_similarity_row())
        
        logger.info(f"Exported similarity CSV: {csv_path} ({len(self.similarity_records)} rows)")
        return csv_path
    
    def export_standard_comprehensive_csv(self) -> Path:
        """
        Export Standard Comprehensive CSV.
        Aggregates DHL and HC2L data into single rows per route/trial/batch.
        
        For standard preset: Uses route_trial and route_batch instead of scenario fields.
        Each row contains metrics from both DHL and HC2L algorithms, plus HERE comparison data.
        """
        csv_path = self.results_path / "comprehensive_results.csv"
        
        with self.csv_lock:
            # Build lookup from similarity_records for HERE data
            # Key: (trial, batch, route) -> {here_travel_time_sec, here_distance_km, frechet_distance_km}
            similarity_by_route = {}
            for sim_record in self.similarity_records:
                key = (sim_record.batch_id, sim_record.route_id)
                similarity_by_route[key] = {
                    "here_travel_time_sec": sim_record.similarity.here_travel_time_min * 60,
                    "here_distance_km": sim_record.similarity.here_distance_km,
                    "frechet_distance_km": sim_record.similarity.frechet_distance_m / 1000,
                }
            
            # Group records by (trial_id, batch_id, query_id) - merge DHL and HC2L
            grouped_records = {}
            
            # Add HC2L records
            for record in self.route_records_dhc2l:
                key = (record.trial_id, record.batch_id, record.query_id)
                if key not in grouped_records:
                    grouped_records[key] = {"DHL": None, "HC2L": None, "record": None}
                grouped_records[key]["HC2L"] = record
                grouped_records[key]["record"] = record  # Use for common data
            
            # Add DHL records
            for record in self.route_records_dhl:
                key = (record.trial_id, record.batch_id, record.query_id)
                if key not in grouped_records:
                    grouped_records[key] = {"DHL": None, "HC2L": None, "record": None}
                grouped_records[key]["DHL"] = record
                if not grouped_records[key]["record"]:
                    grouped_records[key]["record"] = record
            
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_STANDARD_COMPREHENSIVE)
                writer.writeheader()
                
                for key, algo_records in grouped_records.items():
                    trial_id, batch_id, query_id = key
                    
                    hc2l_record = algo_records.get("HC2L")
                    dhl_record = algo_records.get("DHL")
                    primary_record = algo_records.get("record")
                    
                    if not primary_record:
                        continue
                    
                    # Look up HERE data from similarity_records
                    sim_key = (batch_id, query_id)
                    sim_data = similarity_by_route.get(sim_key, {})
                    
                    # Get HERE values from similarity data
                    here_travel_time_sec = sim_data.get("here_travel_time_sec", 0)
                    here_distance_km = sim_data.get("here_distance_km", 0)
                    frechet_distance_km = sim_data.get("frechet_distance_km", 0)
                    
                    # Get HC2L values
                    hc2l_distance_km = 0
                    hc2l_travel_time_sec = 0
                    hc2l_query_time_ms = 0
                    if hc2l_record and hc2l_record.accuracy:
                        hc2l_distance_km = hc2l_record.accuracy.dhc2l_distance / 1000
                    if hc2l_record and hc2l_record.performance:
                        hc2l_query_time_ms = hc2l_record.performance.query_response_time_ms
                    
                    # Get DHL values
                    dhl_distance_km = 0
                    dhl_travel_time_sec = 0
                    dhl_query_time_ms = 0
                    if dhl_record and dhl_record.accuracy:
                        dhl_distance_km = dhl_record.accuracy.dhc2l_distance / 1000
                    if dhl_record and dhl_record.performance:
                        dhl_query_time_ms = dhl_record.performance.query_response_time_ms
                    
                    # Get incident summary
                    incident_summary = primary_record.incident_summary
                    
                    # Accuracy from HC2L only
                    is_correct = hc2l_record.accuracy.is_correct if (hc2l_record and hc2l_record.accuracy) else False
                    
                    # CRITICAL: Check if both HC2L and DHL returned 0 distance and 0 time
                    # This indicates a failed experiment and should override is_correct
                    hc2l_failed = (hc2l_distance_km == 0 and hc2l_travel_time_sec == 0)
                    dhl_failed = (dhl_distance_km == 0 and dhl_travel_time_sec == 0)
                    
                    if hc2l_failed and dhl_failed:
                        # Both algorithms failed - mark as incorrect
                        is_correct = False
                        logger.debug(
                            f"Standard experiment failed: Trial {trial_id}, Batch {batch_id}, "
                            f"Query {query_id} - Both HC2L and DHL returned 0 distance and 0 time"
                        )
                    
                    # Average labeling time
                    hc2l_labeling = hc2l_record.performance.labeling_time_ms if (hc2l_record and hc2l_record.performance) else 0
                    dhl_labeling = dhl_record.performance.labeling_time_ms if (dhl_record and dhl_record.performance) else 0
                    avg_labeling_time_ms = (hc2l_labeling + dhl_labeling) / 2 if (hc2l_labeling + dhl_labeling) > 0 else 0
                    
                    hc2l_label_size = hc2l_record.performance.labeling_size_mb if (hc2l_record and hc2l_record.performance) else 0
                    dhl_label_size = dhl_record.performance.labeling_size_mb if (dhl_record and dhl_record.performance) else 0
                    avg_label_size_mb = (hc2l_label_size + dhl_label_size) / 2 if (hc2l_label_size + dhl_label_size) > 0 else 0
                    
                    writer.writerow({
                        # Route identification
                        "route_id": query_id,
                        "route_trial": trial_id,
                        "route_batch": batch_id,
                        "route_start_lat": 0,  # Not available in standard mode RouteMetricsRecord
                        "route_start_lon": 0,
                        "route_end_lat": 0,
                        "route_end_lon": 0,
                        "route_start_edge_source": primary_record.source_node,
                        "route_start_edge_target": 0,
                        "route_end_edge_source": primary_record.target_node,
                        "route_end_edge_target": 0,
                        "route_start_name": "",
                        "route_end_name": "",
                        
                        # Disruption level
                        "disruption_level": primary_record.disruption_level,
                        
                        # Incident counts
                        "disruption_num_road_closure": incident_summary.num_road_closure if incident_summary else 0,
                        "disruption_num_road_hazard": incident_summary.num_road_hazard if incident_summary else 0,
                        "disruption_num_construction": incident_summary.num_construction if incident_summary else 0,
                        "disruption_num_congestion": incident_summary.num_congestion if incident_summary else 0,
                        "disruption_num_disabled_vehicle": incident_summary.num_disabled_vehicle if incident_summary else 0,
                        "disruption_num_mass_transit_event": incident_summary.num_mass_transit_event if incident_summary else 0,
                        "disruption_num_planned_event": incident_summary.num_planned_event if incident_summary else 0,
                        "disruption_num_weather": incident_summary.num_weather if incident_summary else 0,
                        "disruption_num_lane_restriction": incident_summary.num_lane_restriction if incident_summary else 0,
                        "disruption_num_other": incident_summary.num_other if incident_summary else 0,
                        "disruption_num_accident": incident_summary.num_accident if incident_summary else 0,
                        
                        # Algorithm performance
                        "algorithm_labeling_time_ms": round(avg_labeling_time_ms, 2),
                        "algorithm_label_size_mb": round(avg_label_size_mb, 5),
                        "algorithm_hc2l_query_response_time_ms": round(hc2l_query_time_ms, 3),
                        "algorithm_dhl_query_response_time_ms": round(dhl_query_time_ms, 3),
                        "algorithm_here_query_response_time_ms": 0,
                        
                        # Travel times
                        "algorithm_here_travel_time_sec": round(here_travel_time_sec, 2),
                        "algorithm_dhc2l_travel_time_sec": round(hc2l_travel_time_sec, 2),
                        "algorithm_dhl_travel_time_sec": round(dhl_travel_time_sec, 2),
                        
                        # Distances
                        "algorithm_here_distance_km": round(here_distance_km, 3),
                        "algorithm_dhc2l_distance_km": round(hc2l_distance_km, 3),
                        "algorithm_dhl_distance_km": round(dhl_distance_km, 3),
                        
                        # Quality metrics
                        "algorithm_frechet_distance_km": round(frechet_distance_km, 3),
                        "algorithm_is_correct": is_correct,
                    })
            
            total_rows = len(grouped_records)
            logger.info(f"Exported standard comprehensive CSV: {csv_path} ({total_rows} rows)")
            return csv_path
    
    def export_all_csvs(self) -> Dict[str, Path]:
        """
        Export all CSV files for GUI tabs.
        
        Returns:
            Dict mapping tab name to CSV file path
        """
        logger.info("Exporting all CSV files...")
        
        csv_paths = {
            "summary": self.export_summary_csv(),
            "accuracy": self.export_accuracy_csv(),
            "construction": self.export_construction_csv(),
            "updates": self.export_updates_csv(),
            "performance": self.export_performance_csv(),
            "similarity": self.export_similarity_csv(),
            "comprehensive": self.export_standard_comprehensive_csv()
        }
        
        logger.info(f"All CSVs exported to: {self.results_path}")
        return csv_paths
    
    # ========================================================================
    # JSON RESULTS GENERATION
    # ========================================================================
    
    def generate_results_json(self, experiment_config: Optional[Dict] = None) -> Path:
        """
        Generate comprehensive JSON results file with pre-calculated aggregations.
        All per-trial and per-batch averages are computed in backend.
        For scenario mode, outputs scenario-specific aggregations.
        
        Args:
            experiment_config: Optional experiment configuration to include
            
        Returns:
            Path to generated JSON file
        """
        json_path = self.results_path / "experiment_results.json"
        
        config = experiment_config or self._get_default_config()
        
        # Add preset_type to config if not present
        if "preset_type" not in config:
            config["preset_type"] = self.preset_type
        
        if self.is_scenario_mode:
            # Scenario mode JSON structure
            results = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "version": "3.0",
                    "format": "scenario_aggregations",
                    "preset_type": "scenario"
                },
                "configuration": config,
                "summary": self._compute_scenario_summary(),
                "accuracy_stats": self._compute_accuracy_stats(),
                "performance_stats": self._compute_performance_stats(),
                "aggregated_data": {
                    "summary": self._compute_scenario_summary_aggregations(),
                    "accuracy": self._compute_scenario_accuracy_aggregations(),
                    "construction": self._compute_scenario_construction_aggregations(),
                    "updates": self._compute_scenario_updates_aggregations(),
                    "performance": self._compute_scenario_performance_aggregations(),
                    "labeling": self._compute_scenario_labeling_aggregations()
                },
                "graph_data": self._compute_graph_data(),
                "csv_files": {
                    "summary": "summary_results.csv",
                    "accuracy": "accuracy_results.csv",
                    "construction": "construction_results.csv",
                    "updates": "updates_results.csv",
                    "performance": "performance_results.csv",
                    "similarity": "similarity_results.csv",
                    "comprehensive": "comprehensive_results.csv",
                    "labeling": "labeling_results.csv",
                    "injected_disruptions": "injected_disruptions.csv",
                    "system_labels": "system_labels.csv"
                }
            }
        else:
            # Standard mode JSON structure
            results = {
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "version": "3.0",
                    "format": "pre_calculated_aggregations",
                    "preset_type": "standard"
                },
                "configuration": config,
                "summary": self._compute_summary(),
                "accuracy_stats": self._compute_accuracy_stats(),
                "performance_stats": self._compute_performance_stats(),
                "aggregated_data": {
                    "summary": self._compute_summary_aggregations(),
                    "accuracy": self._compute_accuracy_aggregations(),
                    "construction": self._compute_construction_aggregations(),
                    "updates": self._compute_updates_aggregations(),
                    "performance": self._compute_performance_aggregations()
                },
                "graph_data": self._compute_graph_data(),
                "csv_files": {
                    "summary": "summary_results.csv",
                    "accuracy": "accuracy_results.csv",
                    "construction": "construction_results.csv",
                    "updates": "updates_results.csv",
                    "performance": "performance_results.csv",
                    "similarity": "similarity_results.csv",
                    "comprehensive": "comprehensive_results.csv"
                }
            }
        
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Generated results JSON: {json_path}")
        return json_path
    
    def _get_default_config(self) -> Dict:
        """Get default configuration dictionary"""
        return {
            "trials": self.trials,
            "batches": self.batches,
            "routes_per_batch": self.routes_per_batch,
            "tolerance": self.tolerance,
            "algorithms": ["DHL", "HC2L"],
            "preset_type": self.preset_type
        }
    
    def _compute_scenario_summary(self) -> Dict:
        """Compute summary statistics for scenario mode"""
        with self.lock:
            total_completed = len(self.scenario_records)
            total_expected = self.total_simulations if self.is_scenario_mode else 900
            
            # Count by category
            category_counts = {"short": 0, "medium": 0, "long": 0}
            for record in self.scenario_records:
                cat = record.get("route_category", "unknown")
                if cat in category_counts:
                    category_counts[cat] += 1
            
            return {
                "preset_type": "scenario",
                "route_categories": 3,
                "routes_per_category": self.routes_per_category if self.is_scenario_mode else 10,
                "total_scenarios": 10,
                "severity_levels": 3,
                "total_simulations": total_expected,
                "completed_simulations": total_completed,
                "completion_pct": round(total_completed / total_expected * 100, 2) if total_expected > 0 else 0,
                "category_counts": category_counts,
                "total_similarity_comparisons": len(self.similarity_records)
            }
    
    def _compute_scenario_summary_aggregations(self) -> Dict:
        """Compute scenario-specific aggregations for the summary tab (separated by algorithm)"""
        with self.lock:
            # Aggregate by route category and algorithm
            per_category = []
            for category in ["short", "medium", "long"]:
                for algorithm in ["DHL", "HC2L"]:
                    cat_records = [r for r in self.scenario_records 
                                   if r.get("route_category") == category and r.get("algorithm") == algorithm]
                    if cat_records:
                        incident_counts = {
                            "accident": sum(r.get("num_accident", 0) for r in cat_records),
                            "construction": sum(r.get("num_construction", 0) for r in cat_records),
                            "congestion": sum(r.get("num_congestion", 0) for r in cat_records),
                            "disabled_vehicle": sum(r.get("num_disabled_vehicle", 0) for r in cat_records),
                            "mass_transit": sum(r.get("num_mass_transit_event", 0) for r in cat_records),
                            "planned_event": sum(r.get("num_planned_event", 0) for r in cat_records),
                            "road_hazard": sum(r.get("num_road_hazard", 0) for r in cat_records),
                            "road_closure": sum(r.get("num_road_closure", 0) for r in cat_records),
                            "weather": sum(r.get("num_weather", 0) for r in cat_records),
                            "lane_restriction": sum(r.get("num_lane_restriction", 0) for r in cat_records),
                            "other": sum(r.get("num_other", 0) for r in cat_records),
                        }
                        per_category.append({
                            "category": category,
                            "algorithm": algorithm,
                            "simulations": len(cat_records),
                            **incident_counts,
                            "total": sum(incident_counts.values())
                        })
            
            # Aggregate by scenario ID and algorithm
            per_scenario = []
            for scenario in self.scenarios if self.is_scenario_mode else [f"DS{i}" for i in range(1, 11)]:
                for algorithm in ["DHL", "HC2L"]:
                    sc_records = [r for r in self.scenario_records 
                                  if r.get("scenario_id") == scenario and r.get("algorithm") == algorithm]
                    if sc_records:
                        incident_counts = {
                            "accident": sum(r.get("num_accident", 0) for r in sc_records),
                            "construction": sum(r.get("num_construction", 0) for r in sc_records),
                            "congestion": sum(r.get("num_congestion", 0) for r in sc_records),
                            "disabled_vehicle": sum(r.get("num_disabled_vehicle", 0) for r in sc_records),
                            "mass_transit": sum(r.get("num_mass_transit_event", 0) for r in sc_records),
                            "planned_event": sum(r.get("num_planned_event", 0) for r in sc_records),
                            "road_hazard": sum(r.get("num_road_hazard", 0) for r in sc_records),
                            "road_closure": sum(r.get("num_road_closure", 0) for r in sc_records),
                            "weather": sum(r.get("num_weather", 0) for r in sc_records),
                            "lane_restriction": sum(r.get("num_lane_restriction", 0) for r in sc_records),
                            "other": sum(r.get("num_other", 0) for r in sc_records),
                        }
                        per_scenario.append({
                            "scenario": scenario,
                            "algorithm": algorithm,
                            "simulations": len(sc_records),
                            **incident_counts,
                            "total": sum(incident_counts.values())
                        })
            
            # Aggregate by severity level and algorithm
            per_severity = []
            for severity in ["light", "medium", "heavy"]:
                for algorithm in ["DHL", "HC2L"]:
                    sev_records = [r for r in self.scenario_records 
                                   if r.get("severity_level") == severity and r.get("algorithm") == algorithm]
                    if sev_records:
                        avg_query_time = sum((r.get("query_time_ms") or 0) for r in sev_records) / len(sev_records)
                        incident_counts = {
                            "accident": sum((r.get("num_accident") or 0) for r in sev_records),
                            "construction": sum((r.get("num_construction") or 0) for r in sev_records),
                            "congestion": sum((r.get("num_congestion") or 0) for r in sev_records),
                            "disabled_vehicle": sum((r.get("num_disabled_vehicle") or 0) for r in sev_records),
                            "mass_transit": sum((r.get("num_mass_transit_event") or 0) for r in sev_records),
                            "planned_event": sum((r.get("num_planned_event") or 0) for r in sev_records),
                            "road_hazard": sum((r.get("num_road_hazard") or 0) for r in sev_records),
                            "road_closure": sum((r.get("num_road_closure") or 0) for r in sev_records),
                            "weather": sum((r.get("num_weather") or 0) for r in sev_records),
                            "lane_restriction": sum((r.get("num_lane_restriction") or 0) for r in sev_records),
                            "other": sum((r.get("num_other") or 0) for r in sev_records),
                        }
                        per_severity.append({
                            "severity": severity,
                            "algorithm": algorithm,
                            "simulations": len(sev_records),
                            "avg_query_time_ms": round(avg_query_time, 3),
                            **incident_counts,
                            "total": sum(incident_counts.values())
                        })
            
            # Algorithm averages
            averages = []
            for algorithm in ["DHL", "HC2L"]:
                algo_records = [r for r in self.scenario_records if r.get("algorithm") == algorithm]
                if algo_records:
                    incident_counts = {
                        "accident": sum((r.get("num_accident") or 0) for r in algo_records),
                        "construction": sum((r.get("num_construction") or 0) for r in algo_records),
                        "congestion": sum((r.get("num_congestion") or 0) for r in algo_records),
                        "disabled_vehicle": sum((r.get("num_disabled_vehicle") or 0) for r in algo_records),
                        "mass_transit": sum((r.get("num_mass_transit_event") or 0) for r in algo_records),
                        "planned_event": sum((r.get("num_planned_event") or 0) for r in algo_records),
                        "road_hazard": sum((r.get("num_road_hazard") or 0) for r in algo_records),
                        "road_closure": sum((r.get("num_road_closure") or 0) for r in algo_records),
                        "weather": sum((r.get("num_weather") or 0) for r in algo_records),
                        "lane_restriction": sum((r.get("num_lane_restriction") or 0) for r in algo_records),
                        "other": sum((r.get("num_other") or 0) for r in algo_records),
                    }
                    averages.append({
                        "algorithm": algorithm,
                        "total_simulations": len(algo_records),
                        "avg_query_time_ms": round(sum((r.get("query_time_ms") or 0) for r in algo_records) / len(algo_records), 3),
                        **incident_counts,
                        "total_incidents": sum(incident_counts.values())
                    })
            
            return {
                "per_category": per_category,
                "per_scenario": per_scenario,
                "per_severity": per_severity,
                "averages": averages
            }
    
    def _compute_scenario_accuracy_aggregations(self) -> Dict:
        """Compute accuracy aggregations for scenario mode (HC2L only - DHL doesn't have accuracy validation)"""
        with self.lock:
            # Filter for HC2L records only - DHL doesn't compute accuracy
            hc2l_records = [r for r in self.scenario_records if r.get("algorithm") == "HC2L"]
            
            # By category (HC2L only)
            per_category = []
            for category in ["short", "medium", "long"]:
                cat_records = [r for r in hc2l_records if r.get("route_category") == category]
                if cat_records:
                    correct = sum(1 for r in cat_records if r.get("is_correct", False))
                    avg_error = sum((r.get("relative_error") or 0) for r in cat_records) / len(cat_records)
                    per_category.append({
                        "category": category,
                        "total": len(cat_records),
                        "correct": correct,
                        "accuracy_rate": round(correct / len(cat_records), 4) if len(cat_records) > 0 else 0,
                        "avg_relative_error": round(avg_error, 6)
                    })
            
            # By scenario (HC2L only)
            per_scenario = []
            for scenario in self.scenarios if self.is_scenario_mode else [f"DS{i}" for i in range(1, 11)]:
                sc_records = [r for r in hc2l_records if r.get("scenario_id") == scenario]
                if sc_records:
                    correct = sum(1 for r in sc_records if r.get("is_correct", False))
                    avg_error = sum((r.get("relative_error") or 0) for r in sc_records) / len(sc_records)
                    per_scenario.append({
                        "scenario": scenario,
                        "total": len(sc_records),
                        "correct": correct,
                        "accuracy_rate": round(correct / len(sc_records), 4) if len(sc_records) > 0 else 0,
                        "avg_relative_error": round(avg_error, 6)
                    })
            
            # By severity level (HC2L only)
            per_severity = []
            for severity in ["light", "medium", "heavy"]:
                sev_records = [r for r in hc2l_records if r.get("severity_level") == severity]
                if sev_records:
                    correct = sum(1 for r in sev_records if r.get("is_correct", False))
                    avg_error = sum((r.get("relative_error") or 0) for r in sev_records) / len(sev_records)
                    per_severity.append({
                        "severity": severity,
                        "total": len(sev_records),
                        "correct": correct,
                        "accuracy_rate": round(correct / len(sev_records), 4) if len(sev_records) > 0 else 0,
                        "avg_relative_error": round(avg_error, 6)
                    })
            
            # Algorithm averages (HC2L only for accuracy)
            averages = []
            if hc2l_records:
                total_correct = sum(1 for r in hc2l_records if r.get("is_correct", False))
                avg_error = sum((r.get("relative_error") or 0) for r in hc2l_records) / len(hc2l_records)
                averages.append({
                    "algorithm": "HC2L",
                    "total_simulations": len(hc2l_records),
                    "total_correct": total_correct,
                    "accuracy_rate": round(total_correct / len(hc2l_records), 4) if len(hc2l_records) > 0 else 0,
                    "avg_relative_error": round(avg_error, 6)
                })
            
            return {
                "per_category": per_category,
                "per_scenario": per_scenario,
                "per_severity": per_severity,
                "averages": averages
            }
    
    def _compute_scenario_labeling_aggregations(self) -> Dict:
        """
        Compute labeling accuracy aggregations for scenario mode.
        
        Returns aggregations by:
        - per_category: Labeling accuracy by route length category
        - per_scenario: Labeling accuracy by disruption scenario
        - per_severity: Labeling accuracy by severity level
        - averages: Overall algorithm averages
        """
        with self.lock:
            # By category (includes both algorithms)
            per_category = []
            for category in ["short", "medium", "long"]:
                for algorithm in ["DHL", "HC2L"]:
                    cat_records = [r for r in self.labeling_records 
                                   if r.get("route_category") == category and r.get("algorithm") == algorithm]
                    if cat_records:
                        avg_accuracy = sum(r.get("labeling_accuracy_pct", 0) for r in cat_records) / len(cat_records)
                        total_edges = sum(r.get("total_disrupted_edges", 0) for r in cat_records)
                        total_nodes = sum(r.get("total_disrupted_nodes", 0) for r in cat_records)
                        total_dirty = sum(r.get("dirty_nodes_marked", 0) for r in cat_records)
                        total_repaired = sum(r.get("nodes_repaired", 0) for r in cat_records)
                        per_category.append({
                            "category": category,
                            "algorithm": algorithm,
                            "simulations": len(cat_records),
                            "total_disrupted_edges": total_edges,
                            "total_disrupted_nodes": total_nodes,
                            "dirty_nodes_marked": total_dirty,
                            "nodes_repaired": total_repaired,
                            "avg_labeling_accuracy_pct": round(avg_accuracy, 2)
                        })
            
            # By scenario (includes both algorithms)
            per_scenario = []
            scenarios = self.scenarios if self.is_scenario_mode else [f"DS{i}" for i in range(1, 11)]
            for scenario in scenarios:
                for algorithm in ["DHL", "HC2L"]:
                    sc_records = [r for r in self.labeling_records 
                                  if r.get("scenario_id") == scenario and r.get("algorithm") == algorithm]
                    if sc_records:
                        avg_accuracy = sum(r.get("labeling_accuracy_pct", 0) for r in sc_records) / len(sc_records)
                        total_edges = sum(r.get("total_disrupted_edges", 0) for r in sc_records)
                        total_nodes = sum(r.get("total_disrupted_nodes", 0) for r in sc_records)
                        total_dirty = sum(r.get("dirty_nodes_marked", 0) for r in sc_records)
                        total_repaired = sum(r.get("nodes_repaired", 0) for r in sc_records)
                        per_scenario.append({
                            "scenario": scenario,
                            "algorithm": algorithm,
                            "simulations": len(sc_records),
                            "total_disrupted_edges": total_edges,
                            "total_disrupted_nodes": total_nodes,
                            "dirty_nodes_marked": total_dirty,
                            "nodes_repaired": total_repaired,
                            "avg_labeling_accuracy_pct": round(avg_accuracy, 2)
                        })
            
            # By severity level (includes both algorithms)
            per_severity = []
            for severity in ["light", "medium", "heavy"]:
                for algorithm in ["DHL", "HC2L"]:
                    sev_records = [r for r in self.labeling_records 
                                   if r.get("severity_level") == severity and r.get("algorithm") == algorithm]
                    if sev_records:
                        avg_accuracy = sum(r.get("labeling_accuracy_pct", 0) for r in sev_records) / len(sev_records)
                        total_edges = sum(r.get("total_disrupted_edges", 0) for r in sev_records)
                        total_nodes = sum(r.get("total_disrupted_nodes", 0) for r in sev_records)
                        total_dirty = sum(r.get("dirty_nodes_marked", 0) for r in sev_records)
                        total_repaired = sum(r.get("nodes_repaired", 0) for r in sev_records)
                        per_severity.append({
                            "severity": severity,
                            "algorithm": algorithm,
                            "simulations": len(sev_records),
                            "total_disrupted_edges": total_edges,
                            "total_disrupted_nodes": total_nodes,
                            "dirty_nodes_marked": total_dirty,
                            "nodes_repaired": total_repaired,
                            "avg_labeling_accuracy_pct": round(avg_accuracy, 2)
                        })
            
            # Algorithm averages
            averages = []
            for algorithm in ["DHL", "HC2L"]:
                alg_records = [r for r in self.labeling_records if r.get("algorithm") == algorithm]
                if alg_records:
                    avg_accuracy = sum(r.get("labeling_accuracy_pct", 0) for r in alg_records) / len(alg_records)
                    total_edges = sum(r.get("total_disrupted_edges", 0) for r in alg_records)
                    total_nodes = sum(r.get("total_disrupted_nodes", 0) for r in alg_records)
                    total_dirty = sum(r.get("dirty_nodes_marked", 0) for r in alg_records)
                    total_repaired = sum(r.get("nodes_repaired", 0) for r in alg_records)
                    averages.append({
                        "algorithm": algorithm,
                        "total_simulations": len(alg_records),
                        "total_disrupted_edges": total_edges,
                        "total_disrupted_nodes": total_nodes,
                        "dirty_nodes_marked": total_dirty,
                        "nodes_repaired": total_repaired,
                        "avg_labeling_accuracy_pct": round(avg_accuracy, 2)
                    })
            
            return {
                "per_category": per_category,
                "per_scenario": per_scenario,
                "per_severity": per_severity,
                "averages": averages
            }
    
    def _compute_scenario_performance_aggregations(self) -> Dict:
        """Compute performance aggregations for scenario mode (separated by algorithm)"""
        with self.lock:
            # By category and algorithm
            per_category = []
            for category in ["short", "medium", "long"]:
                for algorithm in ["DHL", "HC2L"]:
                    cat_records = [r for r in self.scenario_records 
                                   if r.get("route_category") == category and r.get("algorithm") == algorithm]
                    if cat_records:
                        avg_query = sum((r.get("query_time_ms") or 0) for r in cat_records) / len(cat_records)
                        avg_label = sum((r.get("label_size_mb") or 0) for r in cat_records) / len(cat_records)
                        avg_peak_label = sum((r.get("peak_label_size_mb") or 0) for r in cat_records) / len(cat_records)
                        avg_lazy_update = sum((r.get("lazy_update_time_ms") or 0) for r in cat_records) / len(cat_records)
                        avg_distance = sum((r.get("route_distance_km") or 0) for r in cat_records) / len(cat_records)
                        per_category.append({
                            "category": category,
                            "algorithm": algorithm,
                            "simulations": len(cat_records),
                            "avg_distance_km": round(avg_distance, 2),
                            "avg_query_time_ms": round(avg_query, 3),
                            "avg_label_size_mb": round(avg_label, 4),
                            "avg_peak_label_size_mb": round(avg_peak_label, 4),
                            "avg_lazy_update_time_ms": round(avg_lazy_update, 3)
                        })
            
            # By severity and algorithm
            per_severity = []
            for severity in ["light", "medium", "heavy"]:
                for algorithm in ["DHL", "HC2L"]:
                    sev_records = [r for r in self.scenario_records 
                                   if r.get("severity_level") == severity and r.get("algorithm") == algorithm]
                    if sev_records:
                        avg_query = sum((r.get("query_time_ms") or 0) for r in sev_records) / len(sev_records)
                        avg_label = sum((r.get("label_size_mb") or 0) for r in sev_records) / len(sev_records)
                        avg_peak_label = sum((r.get("peak_label_size_mb") or 0) for r in sev_records) / len(sev_records)
                        avg_lazy_update = sum((r.get("lazy_update_time_ms") or 0) for r in sev_records) / len(sev_records)
                        per_severity.append({
                            "severity": severity,
                            "algorithm": algorithm,
                            "simulations": len(sev_records),
                            "avg_query_time_ms": round(avg_query, 3),
                            "avg_label_size_mb": round(avg_label, 4),
                            "avg_peak_label_size_mb": round(avg_peak_label, 4),
                            "avg_lazy_update_time_ms": round(avg_lazy_update, 3)
                        })
            
            # By scenario and algorithm
            per_scenario = []
            for scenario in self.scenarios if self.is_scenario_mode else [f"DS{i}" for i in range(1, 11)]:
                for algorithm in ["DHL", "HC2L"]:
                    sc_records = [r for r in self.scenario_records 
                                  if r.get("scenario_id") == scenario and r.get("algorithm") == algorithm]
                    if sc_records:
                        avg_query = sum((r.get("query_time_ms") or 0) for r in sc_records) / len(sc_records)
                        avg_label = sum((r.get("label_size_mb") or 0) for r in sc_records) / len(sc_records)
                        avg_peak_label = sum((r.get("peak_label_size_mb") or 0) for r in sc_records) / len(sc_records)
                        avg_lazy_update = sum((r.get("lazy_update_time_ms") or 0) for r in sc_records) / len(sc_records)
                        per_scenario.append({
                            "scenario": scenario,
                            "algorithm": algorithm,
                            "simulations": len(sc_records),
                            "avg_query_time_ms": round(avg_query, 3),
                            "avg_label_size_mb": round(avg_label, 4),
                            "avg_peak_label_size_mb": round(avg_peak_label, 4),
                            "avg_lazy_update_time_ms": round(avg_lazy_update, 3)
                        })
            
            # Algorithm averages (DHL and HC2L)
            averages = []
            for algorithm in ["DHL", "HC2L"]:
                algo_records = [r for r in self.scenario_records if r.get("algorithm") == algorithm]
                if algo_records:
                    avg_query = sum((r.get("query_time_ms") or 0) for r in algo_records) / len(algo_records)
                    avg_label = sum((r.get("label_size_mb") or 0) for r in algo_records) / len(algo_records)
                    avg_peak_label = sum((r.get("peak_label_size_mb") or 0) for r in algo_records) / len(algo_records)
                    avg_lazy_update = sum((r.get("lazy_update_time_ms") or 0) for r in algo_records) / len(algo_records)
                    avg_distance = sum((r.get("route_distance_km") or 0) for r in algo_records) / len(algo_records)
                    averages.append({
                        "algorithm": algorithm,
                        "total_simulations": len(algo_records),
                        "avg_query_time_ms": round(avg_query, 3),
                        "avg_label_size_mb": round(avg_label, 4),
                        "avg_peak_label_size_mb": round(avg_peak_label, 4),
                        "avg_lazy_update_time_ms": round(avg_lazy_update, 3),
                        "avg_distance_km": round(avg_distance, 2)
                    })
            
            return {
                "per_category": per_category,
                "per_severity": per_severity,
                "per_scenario": per_scenario,
                "averages": averages
            }
    
    def _compute_scenario_construction_aggregations(self) -> Dict:
        """Pre-calculate construction aggregations for scenario mode (by category)"""
        # Map trial index to category name
        categories = ["short", "medium", "long"]
        per_category_dhl = []
        per_category_hc2l = []
        
        for trial in range(min(self.trials, 3)):  # Max 3 categories
            category = categories[trial] if trial < len(categories) else f"Category {trial + 1}"
            
            if self.construction_recorded_dhl[trial]:
                per_category_dhl.append({
                    "category": category,
                    "algorithm": "DHL",
                    "construction_time_ms": round(float(self.construction_time_dhl[trial]), 2),
                    "initial_label_size_mb": round(float(self.initial_label_size_dhl[trial]), 5)
                })
            
            if self.construction_recorded_dhc2l[trial]:
                per_category_hc2l.append({
                    "category": category,
                    "algorithm": "HC2L",
                    "construction_time_ms": round(float(self.construction_time_dhc2l[trial]), 2),
                    "initial_label_size_mb": round(float(self.initial_label_size_dhc2l[trial]), 5)
                })
        
        # Compute overall averages per algorithm
        avg_dhl = {
            "algorithm": "DHL",
            "avg_construction_time_ms": round(float(np.mean([d["construction_time_ms"] for d in per_category_dhl])), 2) if per_category_dhl else 0,
            "avg_label_size_mb": round(float(np.mean([d["initial_label_size_mb"] for d in per_category_dhl])), 5) if per_category_dhl else 0
        }
        
        avg_hc2l = {
            "algorithm": "HC2L",
            "avg_construction_time_ms": round(float(np.mean([d["construction_time_ms"] for d in per_category_hc2l])), 2) if per_category_hc2l else 0,
            "avg_label_size_mb": round(float(np.mean([d["initial_label_size_mb"] for d in per_category_hc2l])), 5) if per_category_hc2l else 0
        }
        
        # Per-scenario construction data (separated by algorithm)
        per_scenario = []
        for scenario in self.scenarios if self.is_scenario_mode else [f"DS{i}" for i in range(1, 11)]:
            for algorithm in ["DHL", "HC2L"]:
                sc_records = [r for r in self.scenario_records 
                              if r.get("scenario_id") == scenario and r.get("algorithm") == algorithm]
                if sc_records:
                    avg_construction = sum((r.get("labeling_time_ms") or 0) for r in sc_records) / len(sc_records)
                    avg_label_size = sum((r.get("label_size_mb") or 0) for r in sc_records) / len(sc_records)
                    per_scenario.append({
                        "scenario": scenario,
                        "algorithm": algorithm,
                        "simulations": len(sc_records),
                        "avg_construction_time_ms": round(avg_construction, 2),
                        "avg_label_size_mb": round(avg_label_size, 5)
                    })
        
        # Per-severity construction data (separated by algorithm)
        per_severity = []
        for severity in ["light", "medium", "heavy"]:
            for algorithm in ["DHL", "HC2L"]:
                sev_records = [r for r in self.scenario_records 
                               if r.get("severity_level") == severity and r.get("algorithm") == algorithm]
                if sev_records:
                    avg_construction = sum((r.get("labeling_time_ms") or 0) for r in sev_records) / len(sev_records)
                    avg_label_size = sum((r.get("label_size_mb") or 0) for r in sev_records) / len(sev_records)
                    per_severity.append({
                        "severity": severity,
                        "algorithm": algorithm,
                        "simulations": len(sev_records),
                        "avg_construction_time_ms": round(avg_construction, 2),
                        "avg_label_size_mb": round(avg_label_size, 5)
                    })
        
        return {
            "per_category": per_category_dhl + per_category_hc2l,
            "per_scenario": per_scenario,
            "per_severity": per_severity,
            "averages": [avg_dhl, avg_hc2l]
        }
    
    def _compute_scenario_updates_aggregations(self) -> Dict:
        """Pre-calculate updates aggregations for scenario mode (by category and scenario)"""
        categories = ["short", "medium", "long"]
        per_category = []
        per_scenario = []
        
        # Per-category data
        for trial in range(min(self.trials, 3)):  # Max 3 categories
            category = categories[trial] if trial < len(categories) else f"Category {trial + 1}"
            
            # Aggregate across all batches (scenarios) for this category (trial)
            dhc2l_lazy_times = []
            dhc2l_query_times = []
            dhl_lazy_times = []
            dhl_query_times = []
            peak_label_dhc2l = 0
            peak_label_dhl = 0
            initial_label_dhc2l = float(self.initial_label_size_dhc2l[trial])
            initial_label_dhl = float(self.initial_label_size_dhl[trial])
            
            for batch in range(self.batches):
                dhc2l_lazy_times.extend(self._batch_lazy_times_dhc2l[trial][batch])
                dhc2l_query_times.extend(self._batch_query_times_dhc2l[trial][batch])
                dhl_lazy_times.extend(self._batch_lazy_times_dhl[trial][batch])
                dhl_query_times.extend(self._batch_query_times_dhl[trial][batch])
                peak_label_dhc2l = max(peak_label_dhc2l, float(self.peak_label_size_dhc2l[trial, batch]))
                peak_label_dhl = max(peak_label_dhl, float(self.peak_label_size_dhl[trial, batch]))
            
            # HC2L entry for this category
            if dhc2l_query_times:
                label_change_pct = ((peak_label_dhc2l - initial_label_dhc2l) / initial_label_dhc2l * 100) if initial_label_dhc2l > 0 else 0
                per_category.append({
                    "category": category,
                    "algorithm": "HC2L",
                    "lazy_update_time_ms": round(float(np.mean(dhc2l_lazy_times)), 3) if dhc2l_lazy_times else 0,
                    "peak_label_size_mb": round(peak_label_dhc2l, 5),
                    "label_size_change_pct": round(label_change_pct, 1),
                    "query_avg_ms": round(float(np.mean(dhc2l_query_times)), 3)
                })
            
            # DHL entry for this category
            if dhl_query_times:
                label_change_pct = ((peak_label_dhl - initial_label_dhl) / initial_label_dhl * 100) if initial_label_dhl > 0 else 0
                per_category.append({
                    "category": category,
                    "algorithm": "DHL",
                    "lazy_update_time_ms": round(float(np.mean(dhl_lazy_times)), 3) if dhl_lazy_times else 0,
                    "peak_label_size_mb": round(peak_label_dhl, 5),
                    "label_size_change_pct": round(label_change_pct, 1),
                    "query_avg_ms": round(float(np.mean(dhl_query_times)), 3)
                })
        
        # Per-scenario data (aggregate by scenario across all categories)
        scenarios = self.scenarios if self.is_scenario_mode else [f"DS{i}" for i in range(1, 11)]
        for scenario_idx, scenario in enumerate(scenarios):
            # Each scenario runs across all categories (trials)
            # Scenarios repeat every 10 batches (10 scenarios × 3 severities = 30 batches)
            dhc2l_query_times = []
            dhl_query_times = []
            
            for trial in range(min(self.trials, 3)):
                for batch in range(self.batches):
                    # Determine which scenario this batch represents
                    # batch = (severity * 10) + scenario_index, or similar mapping
                    batch_scenario_idx = batch % 10
                    if batch_scenario_idx == scenario_idx:
                        dhc2l_query_times.extend(self._batch_query_times_dhc2l[trial][batch])
                        dhl_query_times.extend(self._batch_query_times_dhl[trial][batch])
            
            if dhc2l_query_times:
                per_scenario.append({
                    "scenario": scenario,
                    "algorithm": "HC2L",
                    "simulations": len(dhc2l_query_times),
                    "query_avg_ms": round(float(np.mean(dhc2l_query_times)), 3)
                })
            
            if dhl_query_times:
                per_scenario.append({
                    "scenario": scenario,
                    "algorithm": "DHL",
                    "simulations": len(dhl_query_times),
                    "query_avg_ms": round(float(np.mean(dhl_query_times)), 3)
                })
        
        # Per-severity data (aggregate by severity across all categories, separated by algorithm)
        per_severity = []
        for severity in ["light", "medium", "heavy"]:
            for algorithm in ["DHL", "HC2L"]:
                sev_records = [r for r in self.scenario_records 
                               if r.get("severity_level") == severity and r.get("algorithm") == algorithm]
                if sev_records:
                    avg_lazy_time = sum((r.get("lazy_update_time_ms") or 0) for r in sev_records) / len(sev_records)
                    avg_query_time = sum((r.get("query_time_ms") or 0) for r in sev_records) / len(sev_records)
                    avg_label_size = sum((r.get("label_size_mb") or 0) for r in sev_records) / len(sev_records)
                    per_severity.append({
                        "severity": severity,
                        "algorithm": algorithm,
                        "simulations": len(sev_records),
                        "avg_lazy_update_time_ms": round(avg_lazy_time, 3),
                        "avg_query_time_ms": round(avg_query_time, 3),
                        "avg_label_size_mb": round(avg_label_size, 5)
                    })
        
        # Algorithm averages (DHL and HC2L)
        averages = []
        for algorithm in ["DHL", "HC2L"]:
            algo_records = [r for r in self.scenario_records if r.get("algorithm") == algorithm]
            if algo_records:
                avg_lazy_time = sum((r.get("lazy_update_time_ms") or 0) for r in algo_records) / len(algo_records)
                avg_query_time = sum((r.get("query_time_ms") or 0) for r in algo_records) / len(algo_records)
                avg_label_size = sum((r.get("label_size_mb") or 0) for r in algo_records) / len(algo_records)
                averages.append({
                    "algorithm": algorithm,
                    "total_simulations": len(algo_records),
                    "avg_lazy_update_time_ms": round(avg_lazy_time, 3),
                    "avg_query_time_ms": round(avg_query_time, 3),
                    "avg_label_size_mb": round(avg_label_size, 5)
                })
        
        return {
            "per_category": per_category,
            "per_scenario": per_scenario,
            "per_severity": per_severity,
            "averages": averages
        }
    
    def record_scenario_metric(self, 
                               route_category: str,
                               route_id: int,
                               scenario_id: str,
                               severity_level: str,
                               api_result: Dict,
                               route_distance_km: float = 0.0,
                               disruption_data: Optional[Dict] = None) -> Dict:
        """
        Record metrics for a single scenario simulation.
        
        Args:
            route_category: "short", "medium", or "long"
            route_id: Route ID within category (1-10)
            scenario_id: Scenario ID (DS1-DS10)
            severity_level: "light", "medium", or "heavy"
            api_result: Result from C++ API call
            route_distance_km: Pre-computed route distance
            disruption_data: Optional disruption data for incident summary
            
        Returns:
            Complete scenario record dictionary
        """
        with self.lock:
            try:
                # Extract metrics from API result
                metrics = api_result.get("metrics", {})
                summary = api_result.get("summary", {})
                query_phase = api_result.get("query_phase", {})
                gps_mapping = api_result.get("gps_mapping", {})
                
                # Compute accuracy
                dhc2l_dist = float(metrics.get("calculated_distance_meters", 0))
                dijkstra_dist = float(metrics.get("dijkstra_distance_meter", 0))
                distance_error = dhc2l_dist - dijkstra_dist if dijkstra_dist > 0 else 0
                relative_error = abs(distance_error) / dijkstra_dist if dijkstra_dist > 0 else 0
                is_correct = relative_error <= self.tolerance
                
                # Get incident counts from disruption data
                incident_summary = IncidentSummary.from_disruption_data(disruption_data) if disruption_data else IncidentSummary()
                
                record = {
                    "route_category": route_category,
                    "route_id": route_id,
                    "scenario_id": scenario_id,
                    "severity_level": severity_level,
                    "source_node": gps_mapping.get("start_node", 0),
                    "target_node": gps_mapping.get("dest_node", 0),
                    "route_distance_km": route_distance_km,
                    "dhc2l_distance": dhc2l_dist,
                    "dijkstra_distance": dijkstra_dist,
                    "distance_error": distance_error,
                    "relative_error": relative_error,
                    "is_correct": is_correct,
                    "query_time_ms": float(query_phase.get("query_time_ms", 0) or summary.get("query_time_ms", 0) or 0),
                    "label_size_mb": float(summary.get("label_size", 0) or 0),
                    "num_accident": incident_summary.num_accident,
                    "num_construction": incident_summary.num_construction,
                    "num_congestion": incident_summary.num_congestion,
                    "num_road_closure": incident_summary.num_road_closure,
                    "num_other": incident_summary.num_other,
                    "timestamp": datetime.now().isoformat()
                }
                
                self.scenario_records.append(record)
                return record
                
            except Exception as e:
                logger.error(f"Error recording scenario metric: {e}")
                return {"error": str(e)}
    
    def export_scenario_summary_csv(self) -> Path:
        """
        Export Scenario Summary Results CSV.
        Per-simulation incident counts with scenario metadata.
        """
        csv_path = self.results_path / "summary_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SCENARIO_SUMMARY)
                writer.writeheader()
                for record in self.scenario_records:
                    writer.writerow({
                        "route_category": record.get("route_category"),
                        "route_id": record.get("route_id"),
                        "scenario_id": record.get("scenario_id"),
                        "severity_level": record.get("severity_level"),
                        "num_accident": record.get("num_accident", 0),
                        "num_construction": record.get("num_construction", 0),
                        "num_congestion": record.get("num_congestion", 0),
                        "num_disabled_vehicle": record.get("num_disabled_vehicle", 0),
                        "num_mass_transit_event": record.get("num_mass_transit_event", 0),
                        "num_planned_event": record.get("num_planned_event", 0),
                        "num_road_hazard": record.get("num_road_hazard", 0),
                        "num_road_closure": record.get("num_road_closure", 0),
                        "num_weather": record.get("num_weather", 0),
                        "num_lane_restriction": record.get("num_lane_restriction", 0),
                        "num_other": record.get("num_other", 0),
                    })
        
        logger.info(f"Exported scenario summary CSV: {csv_path} ({len(self.scenario_records)} rows)")
        return csv_path
    
    def export_scenario_accuracy_csv(self) -> Path:
        """
        Export Scenario Accuracy Results CSV.
        Per-simulation accuracy metrics with scenario metadata.
        """
        csv_path = self.results_path / "accuracy_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SCENARIO_ACCURACY)
                writer.writeheader()
                for record in self.scenario_records:
                    writer.writerow({
                        "route_category": record.get("route_category"),
                        "route_id": record.get("route_id"),
                        "scenario_id": record.get("scenario_id"),
                        "severity_level": record.get("severity_level"),
                        "source_node": record.get("source_node"),
                        "target_node": record.get("target_node"),
                        "route_distance_km": record.get("route_distance_km", 0),
                        "dhc2l_distance": record.get("dhc2l_distance", 0),
                        "dijkstra_distance": record.get("dijkstra_distance", 0),
                        "distance_error": record.get("distance_error", 0),
                        "relative_error": record.get("relative_error", 0),
                        "is_correct": record.get("is_correct", False),
                    })
        
        logger.info(f"Exported scenario accuracy CSV: {csv_path} ({len(self.scenario_records)} rows)")
        return csv_path
    
    def export_scenario_performance_csv(self) -> Path:
        """
        Export Scenario Performance Results CSV.
        Per-simulation performance metrics with scenario metadata.
        """
        csv_path = self.results_path / "performance_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SCENARIO_PERFORMANCE)
                writer.writeheader()
                for record in self.scenario_records:
                    writer.writerow({
                        "route_category": record.get("route_category"),
                        "route_id": record.get("route_id"),
                        "scenario_id": record.get("scenario_id"),
                        "severity_level": record.get("severity_level"),
                        "source_node": record.get("source_node"),
                        "target_node": record.get("target_node"),
                        "route_distance_km": record.get("route_distance_km", 0),
                        "algorithm": "HC2L",
                        "initial_labeling_time_ms": 0,  # Not tracked per simulation
                        "query_time_ms": record.get("query_time_ms", 0),
                        "label_size_mb": record.get("label_size_mb", 0),
                        "peak_label_size_mb": record.get("label_size_mb", 0),
                        "lazy_update_time_ms": 0,
                        "threshold_rebuild_time_ms": 0,
                        "total_rebuilds": 0,
                    })
        
        logger.info(f"Exported scenario performance CSV: {csv_path} ({len(self.scenario_records)} rows)")
        return csv_path
    
    def export_scenario_construction_csv(self) -> Path:
        """
        Export Scenario Construction CSV.
        Per route construction data (all route data, not just averages).
        """
        csv_path = self.results_path / "construction_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SCENARIO_CONSTRUCTION)
                writer.writeheader()
                
                # Write all scenario records with construction data
                for record in self.scenario_records:
                    writer.writerow({
                        "route_id": record.get("route_id", 0),
                        "route_category": record.get("route_category", ""),
                        "scenario_id": record.get("scenario_id", ""),
                        "severity_level": record.get("severity_level", ""),
                        "algorithm": record.get("algorithm", ""),
                        "construction_time_ms": record.get("initial_construction_time_ms", 0),
                        "initial_label_size_mb": record.get("initial_label_size_mb", 0),
                    })
        
        total_rows = len(self.scenario_records)
        logger.info(f"Exported scenario construction CSV: {csv_path} ({total_rows} rows)")
        return csv_path
    
    def export_scenario_updates_csv(self) -> Path:
        """
        Export Scenario Updates CSV.
        Per route update data (all route data, not just averages).
        """
        csv_path = self.results_path / "updates_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SCENARIO_UPDATES)
                writer.writeheader()
                
                # Write all scenario records with update data
                for record in self.scenario_records:
                    # Compute label size change percentage
                    initial_size = record.get("initial_label_size_mb", 0)
                    peak_size = record.get("peak_label_size_mb", 0)
                    change_pct = 0
                    if initial_size > 0:
                        change_pct = ((peak_size - initial_size) / initial_size) * 100
                    
                    writer.writerow({
                        "route_id": record.get("route_id", 0),
                        "route_category": record.get("route_category", ""),
                        "scenario_id": record.get("scenario_id", ""),
                        "severity_level": record.get("severity_level", ""),
                        "algorithm": record.get("algorithm", ""),
                        "lazy_update_time_ms": record.get("lazy_update_time_ms", 0),
                        "peak_label_size_mb": peak_size,
                        "label_size_change_pct": round(change_pct, 2),
                        "query_avg_ms": record.get("query_time_ms", 0),
                    })
        
        total_rows = len(self.scenario_records)
        logger.info(f"Exported scenario updates CSV: {csv_path} ({total_rows} rows)")
        return csv_path
    
    def export_scenario_comprehensive_csv(self) -> Path:
        """
        Export Scenario Comprehensive CSV.
        Aggregates DHL and HC2L data into single rows per route/scenario/severity.
        
        Output: 900 rows (3 categories × 10 routes × 10 scenarios × 3 severities)
        Each row contains metrics from both DHL and HC2L algorithms, plus HERE comparison data.
        
        Uses similarity_records for HERE travel time, HERE distance, and Frechet distance
        since these values are from HC2L vs HERE comparisons (baseline without disruptions).
        
        Note: similarity_records use global route_id (1-30) while scenario_records use
        local route_id (1-10) per category. We must map (category, local_id) to global_id:
          - short: global_id = local_id (1-10)
          - medium: global_id = local_id + 10 (11-20)
          - long: global_id = local_id + 20 (21-30)
        """
        csv_path = self.results_path / "comprehensive_results.csv"
        
        with self.csv_lock:
            # Build lookup from similarity_records for HERE data
            # Key: global_route_id -> {here_travel_time_sec, here_distance_km, frechet_distance_km}
            similarity_by_route = {}
            for sim_record in self.similarity_records:
                route_id = sim_record.route_id  # This is global route_id (1-30)
                similarity_by_route[route_id] = {
                    "here_travel_time_sec": sim_record.similarity.here_travel_time_min * 60,  # Convert min to sec
                    "here_distance_km": sim_record.similarity.here_distance_km,
                    "frechet_distance_km": sim_record.similarity.frechet_distance_m / 1000,  # Convert m to km
                }
            
            # Category offset mapping for converting local route_id to global route_id
            category_offsets = {"short": 0, "medium": 10, "long": 20}
            
            # Group scenario_records by (route_category, route_id, scenario_id, severity_level)
            grouped_records = {}
            for record in self.scenario_records:
                key = (
                    record.get("route_category", ""),
                    record.get("route_id", 0),
                    record.get("scenario_id", ""),
                    record.get("severity_level", "")
                )
                if key not in grouped_records:
                    grouped_records[key] = {"DHL": None, "HC2L": None}
                
                algorithm = record.get("algorithm", "HC2L")
                grouped_records[key][algorithm] = record
            
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SCENARIO_COMPREHENSIVE)
                writer.writeheader()
                
                for key, algo_records in grouped_records.items():
                    route_category, route_id, scenario_id, severity_level = key
                    
                    # Get records for each algorithm
                    hc2l_record = algo_records.get("HC2L") or {}
                    dhl_record = algo_records.get("DHL") or {}
                    
                    # Compute global route_id for similarity lookup
                    # local route_id (1-10) + category offset = global route_id (1-30)
                    offset = category_offsets.get(route_category, 0)
                    global_route_id = route_id + offset
                    
                    # Look up HERE data from similarity_records using global route_id
                    sim_data = similarity_by_route.get(global_route_id, {})
                    
                    # Use HC2L record as primary for route_info (both should have same route)
                    primary_record = hc2l_record if hc2l_record else dhl_record
                    route_info = primary_record.get("route_info", {}) if primary_record else {}
                    
                    # Get HERE values from similarity data
                    here_travel_time_sec = sim_data.get("here_travel_time_sec", 0)
                    here_distance_km = sim_data.get("here_distance_km", 0)
                    frechet_distance_km = sim_data.get("frechet_distance_km", 0)
                    
                    # Get HERE query time from similarity record (stored in milliseconds)
                    # Find the matching similarity record to get HERE query time
                    here_query_time_ms = 0
                    for sim_record in self.similarity_records:
                        if sim_record.route_id == global_route_id:
                            here_query_time_ms = float(sim_record.similarity.here_query_time_ms or 0)
                            break
                    
                    # Get HC2L values from scenario record (thread run data)
                    hc2l_distance_m = float(hc2l_record.get("dhc2l_distance", 0) or 0) if hc2l_record else 0
                    hc2l_distance_km = hc2l_distance_m / 1000 if hc2l_distance_m > 0 else 0
                    # Travel time from thread run (eta_seconds stored as travel_time_sec)
                    hc2l_travel_time_sec = float(hc2l_record.get("travel_time_sec", 0) or 0) if hc2l_record else 0
                    hc2l_query_time_ms = float(hc2l_record.get("query_time_ms", 0) or 0) if hc2l_record else 0
                    
                    # Get DHL values from scenario record (thread run data)
                    dhl_distance_m = float(dhl_record.get("dhc2l_distance", 0) or 0) if dhl_record else 0
                    dhl_distance_km = dhl_distance_m / 1000 if dhl_distance_m > 0 else 0
                    # Travel time from thread run (eta_seconds stored as travel_time_sec)
                    dhl_travel_time_sec = float(dhl_record.get("travel_time_sec", 0) or 0) if dhl_record else 0
                    dhl_query_time_ms = float(dhl_record.get("query_time_ms", 0) or 0) if dhl_record else 0
                    
                    # Get incident counts (same for both algorithms, use any available)
                    incident_record = hc2l_record if hc2l_record else dhl_record
                    
                    # Accuracy from HC2L only (DHL doesn't compute accuracy against Dijkstra)
                    is_correct = hc2l_record.get("is_correct", False) if hc2l_record else False
                    
                    # CRITICAL: Check if both HC2L and DHL returned 0 distance and 0 time
                    # This indicates a failed experiment and should override is_correct
                    hc2l_failed = (hc2l_distance_m == 0 and hc2l_travel_time_sec == 0)
                    dhl_failed = (dhl_distance_m == 0 and dhl_travel_time_sec == 0)
                    
                    if hc2l_failed and dhl_failed:
                        # Both algorithms failed - mark as incorrect
                        is_correct = False
                        logger.debug(
                            f"ExperimentPreset failed: Route {route_id}, Scenario {scenario_id}, "
                            f"Severity {severity_level} - Both HC2L and DHL returned 0 distance and 0 time"
                        )
                    
                    # Average labeling time from both algorithms
                    hc2l_labeling = float(hc2l_record.get("labeling_time_ms", 0) or 0) if hc2l_record else 0
                    dhl_labeling = float(dhl_record.get("labeling_time_ms", 0) or 0) if dhl_record else 0
                    avg_labeling_time_ms = (hc2l_labeling + dhl_labeling) / 2 if (hc2l_labeling + dhl_labeling) > 0 else 0
                    
                    hc2l_label_size = float(hc2l_record.get("label_size_mb", 0) or 0) if hc2l_record else 0
                    dhl_label_size = float(dhl_record.get("label_size_mb", 0) or 0) if dhl_record else 0
                    avg_label_size_mb = (hc2l_label_size + dhl_label_size) / 2 if (hc2l_label_size + dhl_label_size) > 0 else 0
                    
                    # HERE doesn't provide query time in experiments - set to 0
                    here_query_time_ms = 0
                    
                    writer.writerow({
                        # Route identification
                        "route_id": route_id,
                        "route_start_lat": route_info.get("start_lat", 0),
                        "route_start_lon": route_info.get("start_lon", 0),
                        "route_end_lat": route_info.get("end_lat", 0),
                        "route_end_lon": route_info.get("end_lon", 0),
                        "route_start_edge_source": route_info.get("start_edge_source", 0),
                        "route_start_edge_target": route_info.get("start_edge_target", 0),
                        "route_end_edge_source": route_info.get("end_edge_source", 0),
                        "route_end_edge_target": route_info.get("end_edge_target", 0),
                        "route_start_name": route_info.get("start_name", ""),
                        "route_end_name": route_info.get("end_name", ""),
                        "route_length_category": route_category,
                        
                        # Disruption scenario
                        "disruption_scenario_id": scenario_id,
                        "disruption_scenario_name": (hc2l_record or dhl_record or {}).get("scenario_name", ""),
                        "disruption_severity_level": severity_level,
                        
                        # Incident counts (from either record)
                        "disruption_num_road_closure": (incident_record or {}).get("num_road_closure", 0),
                        "disruption_num_road_hazard": (incident_record or {}).get("num_road_hazard", 0),
                        "disruption_num_construction": (incident_record or {}).get("num_construction", 0),
                        "disruption_num_congestion": (incident_record or {}).get("num_congestion", 0),
                        "disruption_num_disabled_vehicle": (incident_record or {}).get("num_disabled_vehicle", 0),
                        "disruption_num_mass_transit_event": (incident_record or {}).get("num_mass_transit_event", 0),
                        "disruption_num_planned_event": (incident_record or {}).get("num_planned_event", 0),
                        "disruption_num_weather": (incident_record or {}).get("num_weather", 0),
                        "disruption_num_lane_restriction": (incident_record or {}).get("num_lane_restriction", 0),
                        "disruption_num_other": (incident_record or {}).get("num_other", 0),
                        "disruption_num_accident": (incident_record or {}).get("num_accident", 0),
                        
                        # Algorithm performance (averaged from both)
                        "algorithm_labeling_time_ms": round(avg_labeling_time_ms, 2),
                        "algorithm_label_size_mb": round(avg_label_size_mb, 5),
                        # Split query times for each algorithm
                        "algorithm_hc2l_query_response_time_ms": round(hc2l_query_time_ms, 3),
                        "algorithm_dhl_query_response_time_ms": round(dhl_query_time_ms, 3),
                        "algorithm_here_query_response_time_ms": round(here_query_time_ms, 3),
                        
                        # Travel times (from thread runs)
                        "algorithm_here_travel_time_sec": round(here_travel_time_sec, 2),
                        "algorithm_dhc2l_travel_time_sec": round(hc2l_travel_time_sec, 2),
                        "algorithm_dhl_travel_time_sec": round(dhl_travel_time_sec, 2),
                        
                        # Distances
                        "algorithm_here_distance_km": round(here_distance_km, 3),
                        "algorithm_dhc2l_distance_km": round(hc2l_distance_km, 3),
                        "algorithm_dhl_distance_km": round(dhl_distance_km, 3),
                        
                        # Quality metrics
                        "algorithm_frechet_distance_km": round(frechet_distance_km, 3),
                        "algorithm_is_correct": is_correct,
                    })
            
            total_rows = len(grouped_records)
            logger.info(f"Exported scenario comprehensive CSV: {csv_path} ({total_rows} rows)")
            return csv_path
    
    def export_labeling_results_csv(self) -> Path:
        """
        Export Labeling Results CSV - Per-route labeling accuracy metrics.
        
        Returns:
            Path to the exported CSV file
        """
        csv_path = self.results_path / "labeling_results.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_LABELING_RESULTS)
                writer.writeheader()
                
                for record in self.labeling_records:
                    writer.writerow(record)
            
            logger.info(f"Exported labeling results CSV: {csv_path} ({len(self.labeling_records)} rows)")
            return csv_path
    
    def export_injected_disruptions_csv(self) -> Path:
        """
        Export Injected Disruptions CSV - Ground truth of what was injected.
        
        Returns:
            Path to the exported CSV file
        """
        csv_path = self.results_path / "injected_disruptions.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_INJECTED_DISRUPTIONS)
                writer.writeheader()
                
                for record in self.injected_disruptions:
                    writer.writerow(record)
            
            logger.info(f"Exported injected disruptions CSV: {csv_path} ({len(self.injected_disruptions)} rows)")
            return csv_path
    
    def export_system_labels_csv(self) -> Path:
        """
        Export System Labels CSV - What the system detected/labeled.
        
        Returns:
            Path to the exported CSV file
        """
        csv_path = self.results_path / "system_labels.csv"
        
        with self.csv_lock:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS_SYSTEM_LABELS)
                writer.writeheader()
                
                for record in self.system_labels:
                    writer.writerow(record)
            
            logger.info(f"Exported system labels CSV: {csv_path} ({len(self.system_labels)} rows)")
            return csv_path
    
    def export_scenario_csvs(self) -> Dict[str, Path]:
        """
        Export all scenario-specific CSV files.
        Calls individual export methods for each CSV type.
        
        Returns:
            Dict mapping tab name to CSV file path
        """
        logger.info("Exporting all scenario CSV files...")
        
        csv_paths = {
            "summary": self.export_scenario_summary_csv(),
            "accuracy": self.export_scenario_accuracy_csv(),
            "performance": self.export_scenario_performance_csv(),
            "construction": self.export_scenario_construction_csv(),
            "updates": self.export_scenario_updates_csv(),
            "similarity": self.export_similarity_csv(),  # Similarity uses standard export
            "comprehensive": self.export_scenario_comprehensive_csv(),
            # Labeling tab CSVs
            "labeling": self.export_labeling_results_csv(),
            "injected_disruptions": self.export_injected_disruptions_csv(),
            "system_labels": self.export_system_labels_csv()
        }
        
        logger.info(f"All scenario CSVs exported to: {self.results_path}")
        return csv_paths
    
    def _compute_summary(self) -> Dict:
        """Compute overall summary statistics"""
        with self.lock:
            total_dhl = int(np.sum(self.filled_dhl))
            total_dhc2l = int(np.sum(self.filled_dhc2l))
            total_expected = self.trials * self.batches * self.routes_per_batch
            
            return {
                "total_trials": self.trials,
                "total_batches": self.batches,
                "routes_per_batch": self.routes_per_batch,
                "completed_dhl": total_dhl,
                "completed_dhc2l": total_dhc2l,
                "total_expected_per_algorithm": total_expected,
                "completion_pct_dhl": round(total_dhl / total_expected * 100, 2) if total_expected > 0 else 0,
                "completion_pct_dhc2l": round(total_dhc2l / total_expected * 100, 2) if total_expected > 0 else 0,
                "total_similarity_comparisons": len(self.similarity_records)
            }
    
    def _compute_accuracy_stats(self) -> Dict:
        """Compute accuracy statistics (HC2L only)"""
        with self.lock:
            mask = self.filled_dhc2l
            total_routes = int(np.sum(mask))
            
            if total_routes == 0:
                return {
                    "total_routes": 0,
                    "correct_routes": 0,
                    "incorrect_routes": 0,
                    "accuracy_rate": 0.0,
                    "avg_relative_error": 0.0,
                    "max_relative_error": 0.0,
                    "tolerance": self.tolerance
                }
            
            correct_routes = int(np.sum(self.is_correct[mask]))
            
            return {
                "total_routes": total_routes,
                "correct_routes": correct_routes,
                "incorrect_routes": total_routes - correct_routes,
                "accuracy_rate": round(correct_routes / total_routes, 4),
                "avg_relative_error": round(float(np.mean(self.relative_error[mask])), 6),
                "max_relative_error": round(float(np.max(self.relative_error[mask])), 6),
                "tolerance": self.tolerance,
                "per_batch": self._compute_accuracy_per_batch()
            }
    
    def _compute_accuracy_per_batch(self) -> List[Dict]:
        """Compute accuracy statistics per batch"""
        results = []
        for batch in range(self.batches):
            batch_mask = self.filled_dhc2l[:, batch, :]
            total = int(np.sum(batch_mask))
            
            if total > 0:
                correct = int(np.sum(self.is_correct[:, batch, :][batch_mask]))
                results.append({
                    "batch_id": batch + 1,
                    "disruption_level": get_disruption_level(batch + 1),
                    "total_routes": total,
                    "correct_routes": correct,
                    "accuracy_rate": round(correct / total, 4),
                    "avg_relative_error": round(float(np.mean(self.relative_error[:, batch, :][batch_mask])), 6)
                })
        return results
    
    def _compute_performance_stats(self) -> Dict:
        """Compute performance comparison statistics"""
        with self.lock:
            dhl_stats = self._compute_algorithm_stats("DHL")
            dhc2l_stats = self._compute_algorithm_stats("HC2L")
            
            # Compute improvements (positive = HC2L faster/smaller)
            improvements = {}
            for metric in ["avg_query_time_ms", "avg_label_size_mb", "avg_lazy_update_time_ms"]:
                dhl_val = dhl_stats.get(metric, 0)
                dhc2l_val = dhc2l_stats.get(metric, 0)
                if dhl_val > 0:
                    improvements[metric] = round((dhl_val - dhc2l_val) / dhl_val * 100, 2)
                else:
                    improvements[metric] = 0
            
            return {
                "dhl": dhl_stats,
                "dhc2l": dhc2l_stats,
                "improvements_pct": improvements
            }
    
    def _compute_algorithm_stats(self, algorithm: str) -> Dict:
        """Compute stats for a single algorithm"""
        # Use normalized algorithm check (not is_hc2l means it's DHL)
        is_dhl = not is_hc2l_algorithm(algorithm)
        mask = self.filled_dhl if is_dhl else self.filled_dhc2l
        query_times = self.query_time_dhl if is_dhl else self.query_time_dhc2l
        label_sizes = self.label_size_dhl if is_dhl else self.label_size_dhc2l
        construction_times = self.construction_time_dhl if is_dhl else self.construction_time_dhc2l
        initial_sizes = self.initial_label_size_dhl if is_dhl else self.initial_label_size_dhc2l
        peak_sizes = self.peak_label_size_dhl if is_dhl else self.peak_label_size_dhc2l
        rebuild_counts = self.rebuild_count_dhl if is_dhl else self.rebuild_count_dhc2l
        
        total = int(np.sum(mask))
        if total == 0:
            return {
                "total_routes": 0,
                "avg_query_time_ms": 0,
                "avg_label_size_mb": 0,
                "avg_construction_time_ms": 0,
                "avg_initial_label_size_mb": 0,
                "avg_lazy_update_time_ms": 0,
                "total_rebuilds": 0
            }
        
        # Compute lazy update time average from batch buffers
        lazy_buffers = self._batch_lazy_times_dhl if is_dhl else self._batch_lazy_times_dhc2l
        all_lazy_times = []
        for trial in range(self.trials):
            for batch in range(self.batches):
                all_lazy_times.extend(lazy_buffers[trial][batch])
        avg_lazy = np.mean(all_lazy_times) if all_lazy_times else 0
        
        return {
            "total_routes": total,
            "avg_query_time_ms": round(float(np.mean(query_times[mask])), 3),
            "min_query_time_ms": round(float(np.min(query_times[mask])), 3),
            "max_query_time_ms": round(float(np.max(query_times[mask])), 3),
            "avg_label_size_mb": round(float(np.mean(label_sizes[mask])), 5),
            "avg_construction_time_ms": round(float(np.mean(construction_times[construction_times > 0])), 3) 
                if np.any(construction_times > 0) else 0,
            "avg_initial_label_size_mb": round(float(np.mean(initial_sizes[initial_sizes > 0])), 5)
                if np.any(initial_sizes > 0) else 0,
            "avg_peak_label_size_mb": round(float(np.mean(peak_sizes)), 5),
            "avg_lazy_update_time_ms": round(float(avg_lazy), 3),
            "total_rebuilds": int(np.sum(rebuild_counts))
        }
    
    def finalize(self, experiment_config: Optional[Dict] = None) -> Dict[str, Path]:
        """
        Finalize experiment: export all CSVs and generate JSON.
        
        Args:
            experiment_config: Optional experiment configuration
            
        Returns:
            Dict with paths to all generated files
        """
        logger.info("Finalizing experiment results...")
        
        # Export CSVs based on mode
        if self.is_scenario_mode:
            csv_paths = self.export_scenario_csvs()
        else:
            csv_paths = self.export_all_csvs()
        
        # Generate JSON
        json_path = self.generate_results_json(experiment_config)
        
        result_paths = {
            **csv_paths,
            "json": json_path,
            "results_folder": self.results_path
        }
        
        logger.info(f"Experiment finalized. Results in: {self.results_path}")
        return result_paths
    
    # ========================================================================
    # PRE-CALCULATED AGGREGATIONS FOR FRONTEND
    # ========================================================================
    
    def _compute_summary_aggregations(self) -> Dict:
        """Pre-calculate summary aggregations (incident data) per trial and per batch"""
        per_trial = []
        per_batch = []
        
        # Per-trial data (each trial-batch combination)
        for trial in range(self.trials):
            for batch in range(self.batches):
                # Find matching incident summary (incident_summaries uses 0-based keys from record_route_metric)
                batch_key = (trial, batch)  # 0-based to match how they're stored
                if batch_key in self.incident_summaries:
                    summary = self.incident_summaries[batch_key]
                    per_trial.append({
                        "trial": trial + 1,
                        "batch": batch + 1,
                        "level": get_disruption_level(batch + 1),
                        "accident": summary.num_accident,
                        "construction": summary.num_construction,
                        "congestion": summary.num_congestion,
                        "disabled_vehicle": summary.num_disabled_vehicle,
                        "mass_transit": summary.num_mass_transit_event,
                        "planned_event": summary.num_planned_event,
                        "road_hazard": summary.num_road_hazard,
                        "road_closure": summary.num_road_closure,
                        "weather": summary.num_weather,
                        "lane_restriction": summary.num_lane_restriction,
                        "other": summary.num_other,
                        "total": (summary.num_accident + summary.num_construction + 
                                 summary.num_congestion + summary.num_disabled_vehicle +
                                 summary.num_mass_transit_event + summary.num_planned_event +
                                 summary.num_road_hazard + summary.num_road_closure +
                                 summary.num_weather + summary.num_lane_restriction +
                                 summary.num_other)
                    })
        
        # Per-batch averages (average across trials for each batch)
        for batch in range(self.batches):
            # Get all summaries for this batch from the dictionary (0-based keys)
            batch_summaries = [summary for (trial_id, batch_id), summary in self.incident_summaries.items() 
                              if batch_id == batch]  # 0-based comparison
            if batch_summaries:
                avg_accident = np.mean([s.num_accident for s in batch_summaries])
                avg_construction = np.mean([s.num_construction for s in batch_summaries])
                avg_congestion = np.mean([s.num_congestion for s in batch_summaries])
                avg_disabled_vehicle = np.mean([s.num_disabled_vehicle for s in batch_summaries])
                avg_mass_transit = np.mean([s.num_mass_transit_event for s in batch_summaries])
                avg_planned_event = np.mean([s.num_planned_event for s in batch_summaries])
                avg_road_hazard = np.mean([s.num_road_hazard for s in batch_summaries])
                avg_road_closure = np.mean([s.num_road_closure for s in batch_summaries])
                avg_weather = np.mean([s.num_weather for s in batch_summaries])
                avg_lane_restriction = np.mean([s.num_lane_restriction for s in batch_summaries])
                avg_other = np.mean([s.num_other for s in batch_summaries])
                avg_total = np.mean([
                    s.num_accident + s.num_construction + s.num_congestion +
                    s.num_disabled_vehicle + s.num_mass_transit_event + s.num_planned_event +
                    s.num_road_hazard + s.num_road_closure + s.num_weather +
                    s.num_lane_restriction + s.num_other
                    for s in batch_summaries
                ])
                
                per_batch.append({
                    "batch": batch + 1,
                    "level": get_disruption_level(batch + 1),
                    "accident": round(float(avg_accident), 1),
                    "construction": round(float(avg_construction), 1),
                    "congestion": round(float(avg_congestion), 1),
                    "disabled_vehicle": round(float(avg_disabled_vehicle), 1),
                    "mass_transit": round(float(avg_mass_transit), 1),
                    "planned_event": round(float(avg_planned_event), 1),
                    "road_hazard": round(float(avg_road_hazard), 1),
                    "road_closure": round(float(avg_road_closure), 1),
                    "weather": round(float(avg_weather), 1),
                    "lane_restriction": round(float(avg_lane_restriction), 1),
                    "other": round(float(avg_other), 1),
                    "total": round(float(avg_total), 1)
                })
        
        return {"per_trial": per_trial, "per_batch": per_batch}
    
    def _compute_accuracy_aggregations(self) -> Dict:
        """Pre-calculate accuracy aggregations per trial and per batch"""
        per_trial = []
        per_batch = []
        
        # Per-trial data (each trial-batch combination)
        for trial in range(self.trials):
            for batch in range(self.batches):
                mask = self.filled_dhc2l[trial, batch, :]
                total = int(np.sum(mask))
                
                if total > 0:
                    correct = int(np.sum(self.is_correct[trial, batch, :][mask]))
                    incorrect = total - correct
                    avg_error = float(np.mean(self.relative_error[trial, batch, :][mask]))
                    
                    per_trial.append({
                        "trial": trial + 1,
                        "batch": batch + 1,
                        "level": get_disruption_level(batch + 1),
                        "total": total,
                        "correct": correct,
                        "incorrect": incorrect,
                        "accuracy_rate": round(correct / total, 4),
                        "avg_error": round(avg_error, 6)
                    })
        
        # Per-batch averages (average across trials for each batch)
        for batch in range(self.batches):
            batch_data = [d for d in per_trial if d["batch"] == batch + 1]
            if batch_data:
                avg_total = np.mean([d["total"] for d in batch_data])
                avg_correct = np.mean([d["correct"] for d in batch_data])
                avg_incorrect = np.mean([d["incorrect"] for d in batch_data])
                avg_accuracy = np.mean([d["accuracy_rate"] for d in batch_data])
                avg_error = np.mean([d["avg_error"] for d in batch_data])
                
                per_batch.append({
                    "batch": batch + 1,
                    "level": get_disruption_level(batch + 1),
                    "total": round(float(avg_total), 1),
                    "correct": round(float(avg_correct), 1),
                    "incorrect": round(float(avg_incorrect), 1),
                    "accuracy_rate": round(float(avg_accuracy), 4),
                    "avg_error": round(float(avg_error), 6)
                })
        
        return {"per_trial": per_trial, "per_batch": per_batch}
    
    def _compute_construction_aggregations(self) -> Dict:
        """Pre-calculate construction aggregations per trial"""
        per_trial_dhl = []
        per_trial_hc2l = []
        
        for trial in range(self.trials):
            if self.construction_recorded_dhl[trial]:
                per_trial_dhl.append({
                    "trial": trial + 1,
                    "algorithm": "DHL",
                    "construction_time_ms": round(float(self.construction_time_dhl[trial]), 2),
                    "initial_label_size_mb": round(float(self.initial_label_size_dhl[trial]), 5)
                })
            
            if self.construction_recorded_dhc2l[trial]:
                per_trial_hc2l.append({
                    "trial": trial + 1,
                    "algorithm": "HC2L",
                    "construction_time_ms": round(float(self.construction_time_dhc2l[trial]), 2),
                    "initial_label_size_mb": round(float(self.initial_label_size_dhc2l[trial]), 5)
                })
        
        # Compute averages per algorithm (batch doesn't apply to initial construction)
        avg_dhl = {
            "batch": 1,  # Construction happens at batch 1
            "algorithm": "DHL",
            "avg_construction_time_ms": round(float(np.mean([d["construction_time_ms"] for d in per_trial_dhl])), 2) if per_trial_dhl else 0,
            "avg_label_size_mb": round(float(np.mean([d["initial_label_size_mb"] for d in per_trial_dhl])), 5) if per_trial_dhl else 0
        }
        
        avg_hc2l = {
            "batch": 1,  # Construction happens at batch 1
            "algorithm": "HC2L",
            "avg_construction_time_ms": round(float(np.mean([d["construction_time_ms"] for d in per_trial_hc2l])), 2) if per_trial_hc2l else 0,
            "avg_label_size_mb": round(float(np.mean([d["initial_label_size_mb"] for d in per_trial_hc2l])), 5) if per_trial_hc2l else 0
        }
        
        return {
            "per_trial": per_trial_dhl + per_trial_hc2l,
            "per_batch": [avg_dhl, avg_hc2l]
        }
    
    def _compute_updates_aggregations(self) -> Dict:
        """Pre-calculate updates aggregations per trial and per batch"""
        per_trial = []
        per_batch = []
        
        # Per-trial data (each trial-batch-algorithm combination)
        for trial in range(self.trials):
            for batch in range(self.batches):
                disruption_level = get_disruption_level(batch + 1)
                
                # HC2L data
                dhc2l_query_times = self._batch_query_times_dhc2l[trial][batch]
                if dhc2l_query_times:
                    dhc2l_lazy_times = self._batch_lazy_times_dhc2l[trial][batch]
                    initial_label = float(self.initial_label_size_dhc2l[trial])
                    peak_label = float(self.peak_label_size_dhc2l[trial, batch])
                    label_change_pct = ((peak_label - initial_label) / initial_label * 100) if initial_label > 0 else 0
                    
                    per_trial.append({
                        "trial": trial + 1,
                        "batch": batch + 1,
                        "algorithm": "HC2L",
                        "level": disruption_level,
                        "lazy_update_time_ms": round(float(np.mean(dhc2l_lazy_times)), 3) if dhc2l_lazy_times else 0,
                        "threshold_rebuild_time_ms": round(float(self.threshold_rebuild_time_dhc2l[trial, batch]), 3),
                        "peak_label_size_mb": round(peak_label, 5),
                        "label_size_change_pct": round(label_change_pct, 1),
                        "query_avg_ms": round(float(np.mean(dhc2l_query_times)), 3)
                    })
                
                # DHL data
                dhl_query_times = self._batch_query_times_dhl[trial][batch]
                if dhl_query_times:
                    dhl_lazy_times = self._batch_lazy_times_dhl[trial][batch]
                    initial_label = float(self.initial_label_size_dhl[trial])
                    peak_label = float(self.peak_label_size_dhl[trial, batch])
                    label_change_pct = ((peak_label - initial_label) / initial_label * 100) if initial_label > 0 else 0
                    
                    per_trial.append({
                        "trial": trial + 1,
                        "batch": batch + 1,
                        "algorithm": "DHL",
                        "level": disruption_level,
                        "lazy_update_time_ms": round(float(np.mean(dhl_lazy_times)), 3) if dhl_lazy_times else 0,
                        "threshold_rebuild_time_ms": round(float(self.threshold_rebuild_time_dhl[trial, batch]), 3),
                        "peak_label_size_mb": round(peak_label, 5),
                        "label_size_change_pct": round(label_change_pct, 1),
                        "query_avg_ms": round(float(np.mean(dhl_query_times)), 3)
                    })
        
        # Per-batch averages (average across trials for each batch-algorithm combination)
        for batch in range(self.batches):
            for algorithm in ["DHL", "HC2L"]:
                batch_data = [d for d in per_trial if d["batch"] == batch + 1 and d["algorithm"] == algorithm]
                if batch_data:
                    per_batch.append({
                        "batch": batch + 1,
                        "algorithm": algorithm,
                        "level": get_disruption_level(batch + 1),
                        "lazy_update_time_ms": round(float(np.mean([d["lazy_update_time_ms"] for d in batch_data])), 3),
                        "threshold_rebuild_time_ms": round(float(np.mean([d["threshold_rebuild_time_ms"] for d in batch_data])), 3),
                        "peak_label_size_mb": round(float(np.mean([d["peak_label_size_mb"] for d in batch_data])), 5),
                        "label_size_change_pct": round(float(np.mean([d["label_size_change_pct"] for d in batch_data])), 1),
                        "query_avg_ms": round(float(np.mean([d["query_avg_ms"] for d in batch_data])), 3)
                    })
        
        return {"per_trial": per_trial, "per_batch": per_batch}
    
    def _compute_performance_aggregations(self) -> Dict:
        """Pre-calculate performance aggregations per trial and per batch"""
        per_trial = []
        per_batch = []
        
        # Per-trial data (each trial-batch-algorithm combination)
        for trial in range(self.trials):
            for batch in range(self.batches):
                for algorithm in ["DHL", "HC2L"]:
                    is_dhl = algorithm == "DHL"
                    mask = self.filled_dhl[trial, batch, :] if is_dhl else self.filled_dhc2l[trial, batch, :]
                    
                    if np.any(mask):
                        query_times = self.query_time_dhl if is_dhl else self.query_time_dhc2l
                        label_sizes = self.label_size_dhl if is_dhl else self.label_size_dhc2l
                        peak_sizes = self.peak_label_size_dhl if is_dhl else self.peak_label_size_dhc2l
                        lazy_times = self._batch_lazy_times_dhl[trial][batch] if is_dhl else self._batch_lazy_times_dhc2l[trial][batch]
                        
                        per_trial.append({
                            "trial": trial + 1,
                            "batch": batch + 1,
                            "algorithm": algorithm,
                            "level": get_disruption_level(batch + 1),
                            "avg_query_time_ms": round(float(np.mean(query_times[trial, batch, :][mask])), 3),
                            "avg_label_size_mb": round(float(np.mean(label_sizes[trial, batch, :][mask])), 5),
                            "peak_label_size_mb": round(float(peak_sizes[trial, batch]), 5),
                            "avg_lazy_update_time_ms": round(float(np.mean(lazy_times)), 3) if lazy_times else 0
                        })
        
        # Per-batch averages (average across trials for each batch-algorithm combination)
        for batch in range(self.batches):
            for algorithm in ["DHL", "HC2L"]:
                batch_data = [d for d in per_trial if d["batch"] == batch + 1 and d["algorithm"] == algorithm]
                if batch_data:
                    per_batch.append({
                        "batch": batch + 1,
                        "algorithm": algorithm,
                        "level": get_disruption_level(batch + 1),
                        "avg_query_time_ms": round(float(np.mean([d["avg_query_time_ms"] for d in batch_data])), 3),
                        "avg_label_size_mb": round(float(np.mean([d["avg_label_size_mb"] for d in batch_data])), 5),
                        "peak_label_size_mb": round(float(np.mean([d["peak_label_size_mb"] for d in batch_data])), 5),
                        "avg_lazy_update_time_ms": round(float(np.mean([d["avg_lazy_update_time_ms"] for d in batch_data])), 3)
                    })
        
        return {"per_trial": per_trial, "per_batch": per_batch}
    
    # ========================================================================
    # GRAPH DATA COMPUTATION
    # ========================================================================
    
    def _compute_graph_data(self) -> Dict:
        """
        Compute comprehensive data for graph visualizations.
        Simplified and focused on most important metrics.
        """
        with self.lock:
            graph_data = {
                "per_batch_comparison": self._compute_per_batch_comparison(),
                "per_trial_comparison": self._compute_per_trial_comparison(),
                "jam_factor": self._compute_jam_factor_data(),
                "error_rate": self._compute_error_rate_data(),
                "rebuild_analysis": self._compute_rebuild_analysis()
            }
            return graph_data
    
    
    def _compute_per_batch_comparison(self) -> Dict:
        """Compute per-batch comparison (averaged across all trials)"""
        batch_labels = [f"Batch {i+1}<br>({get_disruption_level(i+1)})" for i in range(self.batches)]
        
        dhl_query = []
        hc2l_query = []
        dhl_label = []
        hc2l_label = []
        hc2l_error = []
        
        for batch in range(self.batches):
            # DHL stats averaged across all trials for this batch
            dhl_mask = self.filled_dhl[:, batch, :]
            if np.any(dhl_mask):
                dhl_query.append(round(float(np.mean(self.query_time_dhl[:, batch, :][dhl_mask])), 3))
                dhl_label.append(round(float(np.mean(self.label_size_dhl[:, batch, :][dhl_mask])), 5))
            else:
                dhl_query.append(0)
                dhl_label.append(0)
            
            # HC2L stats averaged across all trials for this batch
            hc2l_mask = self.filled_dhc2l[:, batch, :]
            if np.any(hc2l_mask):
                hc2l_query.append(round(float(np.mean(self.query_time_dhc2l[:, batch, :][hc2l_mask])), 3))
                hc2l_label.append(round(float(np.mean(self.label_size_dhc2l[:, batch, :][hc2l_mask])), 5))
                # Error rate
                total = np.sum(hc2l_mask)
                incorrect = total - np.sum(self.is_correct[:, batch, :][hc2l_mask])
                hc2l_error.append(round(float(incorrect / total * 100), 2) if total > 0 else 0)
            else:
                hc2l_query.append(0)
                hc2l_label.append(0)
                hc2l_error.append(0)
        
        return {
            "labels": batch_labels,
            "DHL": {
                "query_time_ms": dhl_query,
                "label_size_mb": dhl_label
            },
            "HC2L": {
                "query_time_ms": hc2l_query,
                "label_size_mb": hc2l_label,
                "error_rate_pct": hc2l_error
            }
        }
    
    def _compute_per_trial_comparison(self) -> Dict:
        """Compute per-trial comparison (averaged across all batches)"""
        trial_labels = [f"Trial {i+1}" for i in range(self.trials)]
        
        dhl_query = []
        hc2l_query = []
        dhl_label = []
        hc2l_label = []
        
        for trial in range(self.trials):
            # DHL stats averaged across all batches for this trial
            dhl_mask = self.filled_dhl[trial, :, :]
            if np.any(dhl_mask):
                dhl_query.append(round(float(np.mean(self.query_time_dhl[trial, :, :][dhl_mask])), 3))
                dhl_label.append(round(float(np.mean(self.label_size_dhl[trial, :, :][dhl_mask])), 5))
            else:
                dhl_query.append(0)
                dhl_label.append(0)
            
            # HC2L stats averaged across all batches for this trial
            hc2l_mask = self.filled_dhc2l[trial, :, :]
            if np.any(hc2l_mask):
                hc2l_query.append(round(float(np.mean(self.query_time_dhc2l[trial, :, :][hc2l_mask])), 3))
                hc2l_label.append(round(float(np.mean(self.label_size_dhc2l[trial, :, :][hc2l_mask])), 5))
            else:
                hc2l_query.append(0)
                hc2l_label.append(0)
        
        return {
            "labels": trial_labels,
            "DHL": {
                "query_time_ms": dhl_query,
                "label_size_mb": dhl_label
            },
            "HC2L": {
                "query_time_ms": hc2l_query,
                "label_size_mb": hc2l_label
            }
        }
    
    def _compute_jam_factor_data(self) -> Dict:
        """Compute jam factor data per batch (averaged across trials)"""
        batch_labels = [f"Batch {i+1}<br>({get_disruption_level(i+1)})" for i in range(self.batches)]
        avg_jam_factors = []
        
        for batch in range(self.batches):
            # Collect jam factors from all trials for this batch
            batch_jam_factors = []
            for trial in range(self.trials):
                batch_jam_factors.extend(self._batch_jam_factors[trial][batch])
            
            if batch_jam_factors:
                avg_jam_factors.append(round(float(np.mean(batch_jam_factors)), 2))
            else:
                avg_jam_factors.append(0.0)
        
        # Per-level summary
        per_level = {}
        for batch in range(min(self.batches, 3)):
            level = get_disruption_level(batch + 1)
            level_factors = []
            for trial in range(self.trials):
                level_factors.extend(self._batch_jam_factors[trial][batch])
            per_level[level] = round(float(np.mean(level_factors)), 2) if level_factors else 0.0
        
        return {
            "labels": batch_labels,
            "values": avg_jam_factors,
            "per_level": per_level
        }
    
    def _compute_error_rate_data(self) -> Dict:
        """Compute HC2L error rate per batch (averaged across trials)"""
        batch_labels = [f"Batch {i+1}<br>({get_disruption_level(i+1)})" for i in range(self.batches)]
        error_rates = []
        
        for batch in range(self.batches):
            # Average error rate across all trials for this batch
            batch_error_rates = []
            for trial in range(self.trials):
                mask = self.filled_dhc2l[trial, batch, :]
                if np.any(mask):
                    total = np.sum(mask)
                    incorrect = total - np.sum(self.is_correct[trial, batch, :][mask])
                    batch_error_rates.append(incorrect / total * 100)
            
            if batch_error_rates:
                error_rates.append(round(float(np.mean(batch_error_rates)), 2))
            else:
                error_rates.append(0.0)
        
        # Per-level summary
        per_level = {}
        for batch in range(min(self.batches, 3)):
            level = get_disruption_level(batch + 1)
            per_level[level] = error_rates[batch] if batch < len(error_rates) else 0.0
        
        return {
            "labels": batch_labels,
            "values": error_rates,
            "per_level": per_level,
            "tolerance_pct": self.tolerance * 100
        }
    
    def _compute_rebuild_analysis(self) -> Dict:
        """Compute rebuild analysis data"""
        dhl_rebuild_times = []
        dhc2l_rebuild_times = []
        dhl_rebuild_counts = []
        dhc2l_rebuild_counts = []
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                dhl_rebuild_times.append(float(self.threshold_rebuild_time_dhl[trial, batch]))
                dhc2l_rebuild_times.append(float(self.threshold_rebuild_time_dhc2l[trial, batch]))
                dhl_rebuild_counts.append(int(self.rebuild_count_dhl[trial, batch]))
                dhc2l_rebuild_counts.append(int(self.rebuild_count_dhc2l[trial, batch]))
        
        return {
            "DHL_rebuild_times": [round(t, 3) for t in dhl_rebuild_times],
            "HC2L_rebuild_times": [round(t, 3) for t in dhc2l_rebuild_times],
            "DHL_rebuild_counts": dhl_rebuild_counts,
            "HC2L_rebuild_counts": dhc2l_rebuild_counts,
            "total_DHL_rebuilds": sum(dhl_rebuild_counts),
            "total_HC2L_rebuilds": sum(dhc2l_rebuild_counts)
        }
    
    # ========================================================================
    # PROGRESS TRACKING AND UTILITY METHODS
    # ========================================================================
    
    def get_progress_stats(self) -> Dict:
        """Get current progress statistics for real-time display"""
        with self.lock:
            dhl_completed = int(np.sum(self.filled_dhl))
            dhc2l_completed = int(np.sum(self.filled_dhc2l))
            
            return {
                "completed_dhl": dhl_completed,
                "completed_dhc2l": dhc2l_completed,
                "total_expected": self.trials * self.batches * self.routes_per_batch,
                "latest_query_time_dhl": round(float(np.max(self.query_time_dhl[self.filled_dhl])), 3) 
                    if np.any(self.filled_dhl) else 0,
                "latest_query_time_dhc2l": round(float(np.max(self.query_time_dhc2l[self.filled_dhc2l])), 3) 
                    if np.any(self.filled_dhc2l) else 0,
                "accuracy_rate": self._get_current_accuracy_rate(),
                "similarity_completed": len(self.similarity_records)
            }
    
    def _get_current_accuracy_rate(self) -> float:
        """Get current accuracy rate (HC2L only)"""
        mask = self.filled_dhc2l
        total = np.sum(mask)
        if total == 0:
            return 0.0
        correct = np.sum(self.is_correct[mask])
        return round(float(correct / total), 4)
    
    def get_here_comparison_progress(self) -> Dict:
        """Get HERE comparison progress with computed ETA"""
        with self.lock:
            progress = self.here_comparison_progress.copy()
            
            # Compute ETA
            if progress['status'] == 'running' and progress.get('start_time'):
                completed = progress['completed']
                total = progress['total']
                elapsed = time.time() - progress['start_time']
                
                if completed > 0 and total > completed:
                    rate = completed / elapsed
                    remaining = total - completed
                    eta_seconds = remaining / rate
                    
                    if eta_seconds >= 3600:
                        hours = int(eta_seconds // 3600)
                        mins = int((eta_seconds % 3600) // 60)
                        progress['eta'] = f"{hours}h {mins}m"
                    elif eta_seconds >= 60:
                        mins = int(eta_seconds // 60)
                        secs = int(eta_seconds % 60)
                        progress['eta'] = f"{mins}m {secs}s"
                    else:
                        progress['eta'] = f"{int(eta_seconds)}s"
                else:
                    progress['eta'] = 'Calculating...'
            
            # Add running statistics
            if self.similarity_records:
                valid_records = [r for r in self.similarity_records]
                if valid_records:
                    progress['avg_frechet_m'] = round(float(np.mean([
                        r.similarity.frechet_distance_m for r in valid_records])), 1)
                    progress['avg_time_deviation_pct'] = round(float(np.mean([
                        r.similarity.time_deviation_pct for r in valid_records])), 1)
            
            return progress
    
    def update_here_comparison_status(self, status: str, total: int = None):
        """Update HERE comparison status"""
        with self.lock:
            self.here_comparison_progress['status'] = status
            if total is not None:
                self.here_comparison_progress['total'] = total
            if status == 'running' and not self.here_comparison_progress.get('start_time'):
                self.here_comparison_progress['start_time'] = time.time()
    
    def get_batch_stats(self, trial: int, batch: int) -> Dict:
        """Get statistics for a specific trial/batch combination"""
        with self.lock:
            dhl_mask = self.filled_dhl[trial, batch, :]
            dhc2l_mask = self.filled_dhc2l[trial, batch, :]
            
            result = {
                "trial": trial + 1,
                "batch": batch + 1,
                "disruption_level": get_disruption_level(batch + 1),
                "dhl_routes": int(np.sum(dhl_mask)),
                "dhc2l_routes": int(np.sum(dhc2l_mask))
            }
            
            if np.any(dhl_mask):
                result["dhl_avg_query_time"] = round(float(np.mean(self.query_time_dhl[trial, batch, :][dhl_mask])), 3)
            
            if np.any(dhc2l_mask):
                result["dhc2l_avg_query_time"] = round(float(np.mean(self.query_time_dhc2l[trial, batch, :][dhc2l_mask])), 3)
                result["dhc2l_accuracy_rate"] = round(float(np.sum(self.is_correct[trial, batch, :][dhc2l_mask]) / 
                                                           np.sum(dhc2l_mask)), 4)
            
            return result
    
    def get_construction_summary(self) -> List[Dict]:
        """Get construction phase summary for GUI table"""
        rows = []
        
        for trial in range(self.trials):
            # HC2L row
            if self.construction_recorded_dhc2l[trial]:
                rows.append({
                    "trial": trial + 1,
                    "algorithm": "HC2L",
                    "initial_construction_time_ms": round(float(self.construction_time_dhc2l[trial]), 2),
                    "initial_label_size_mb": round(float(self.initial_label_size_dhc2l[trial]), 5)
                })
            
            # DHL row
            if self.construction_recorded_dhl[trial]:
                rows.append({
                    "trial": trial + 1,
                    "algorithm": "DHL",
                    "initial_construction_time_ms": round(float(self.construction_time_dhl[trial]), 2),
                    "initial_label_size_mb": round(float(self.initial_label_size_dhl[trial]), 5)
                })
        
        return rows
    
    def get_updates_summary(self) -> List[Dict]:
        """Get dynamic updates summary for GUI table"""
        rows = []
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                disruption_level = get_disruption_level(batch + 1)
                
                # HC2L data
                dhc2l_query_times = self._batch_query_times_dhc2l[trial][batch]
                if dhc2l_query_times:
                    dhc2l_lazy_times = self._batch_lazy_times_dhc2l[trial][batch]
                    initial_label = float(self.initial_label_size_dhc2l[trial])
                    peak_label = float(self.peak_label_size_dhc2l[trial, batch])
                    label_change_pct = ((peak_label - initial_label) / initial_label * 100) if initial_label > 0 else 0
                    
                    rows.append({
                        "trial": trial + 1,
                        "batch": batch + 1,
                        "algorithm": "HC2L",
                        "disruption_level": disruption_level,
                        "lazy_update_time_ms": round(float(np.mean(dhc2l_lazy_times)), 3) if dhc2l_lazy_times else 0,
                        "threshold_rebuild_time_ms": round(float(self.threshold_rebuild_time_dhc2l[trial, batch]), 3),
                        "peak_label_size_mb": round(peak_label, 5),
                        "label_size_change_pct": round(label_change_pct, 1),
                        "query_avg_ms": round(float(np.mean(dhc2l_query_times)), 3)
                    })
                
                # DHL data
                dhl_query_times = self._batch_query_times_dhl[trial][batch]
                if dhl_query_times:
                    dhl_lazy_times = self._batch_lazy_times_dhl[trial][batch]
                    initial_label = float(self.initial_label_size_dhl[trial])
                    peak_label = float(self.peak_label_size_dhl[trial, batch])
                    label_change_pct = ((peak_label - initial_label) / initial_label * 100) if initial_label > 0 else 0
                    
                    rows.append({
                        "trial": trial + 1,
                        "batch": batch + 1,
                        "algorithm": "DHL",
                        "disruption_level": disruption_level,
                        "lazy_update_time_ms": round(float(np.mean(dhl_lazy_times)), 3) if dhl_lazy_times else 0,
                        "threshold_rebuild_time_ms": round(float(self.threshold_rebuild_time_dhl[trial, batch]), 3),
                        "peak_label_size_mb": round(peak_label, 5),
                        "label_size_change_pct": round(label_change_pct, 1),
                        "query_avg_ms": round(float(np.mean(dhl_query_times)), 3)
                    })
        
        return rows
    
    def get_similarity_summary(self) -> Dict:
        """Get similarity comparison summary statistics"""
        with self.lock:
            if not self.similarity_records:
                return {
                    "total_routes_compared": 0,
                    "avg_frechet_distance_m": 0,
                    "excellent_pct": 0,
                    "good_pct": 0,
                    "fair_pct": 0,
                    "avg_time_deviation_pct": 0,
                    "avg_distance_deviation_pct": 0
                }
            
            total = len(self.similarity_records)
            
            frechet_distances = [r.similarity.frechet_distance_m for r in self.similarity_records]
            time_deviations = [r.similarity.time_deviation_pct for r in self.similarity_records]
            distance_deviations = [r.similarity.distance_deviation_pct for r in self.similarity_records]
            fd_ratings = [r.similarity.fd_rating for r in self.similarity_records]
            
            excellent_count = sum(1 for r in fd_ratings if r == 'Excellent')
            good_count = sum(1 for r in fd_ratings if r == 'Good')
            fair_count = sum(1 for r in fd_ratings if r == 'Fair')
            
            return {
                "total_routes_compared": total,
                "avg_frechet_distance_m": round(float(np.mean(frechet_distances)), 1),
                "excellent_pct": round(excellent_count / total * 100, 1),
                "good_pct": round(good_count / total * 100, 1),
                "fair_pct": round(fair_count / total * 100, 1),
                "avg_time_deviation_pct": round(float(np.mean(time_deviations)), 1),
                "avg_distance_deviation_pct": round(float(np.mean(distance_deviations)), 1),
                "errors_count": self.here_comparison_progress.get('errors', 0)
            }
    
    def reset(self):
        """Reset all metrics for a new experiment"""
        with self.lock:
            # Clear record lists
            self.route_records_dhl.clear()
            self.route_records_dhc2l.clear()
            self.similarity_records.clear()
            self.incident_summaries.clear()
            self.construction_dhl.clear()
            self.construction_dhc2l.clear()
            
            # Reset numpy arrays
            shape = (self.trials, self.batches, self.routes_per_batch)
            batch_shape = (self.trials, self.batches)
            
            self.query_time_dhl.fill(0)
            self.query_time_dhc2l.fill(0)
            self.label_size_dhl.fill(0)
            self.label_size_dhc2l.fill(0)
            self.peak_label_size_dhl.fill(0)
            self.peak_label_size_dhc2l.fill(0)
            self.lazy_update_time_dhl.fill(0)
            self.lazy_update_time_dhc2l.fill(0)
            self.threshold_rebuild_time_dhl.fill(0)
            self.threshold_rebuild_time_dhc2l.fill(0)
            self.rebuild_count_dhl.fill(0)
            self.rebuild_count_dhc2l.fill(0)
            self.dhc2l_distance.fill(0)
            self.dijkstra_distance.fill(0)
            self.distance_error.fill(0)
            self.relative_error.fill(0)
            self.is_correct.fill(False)
            self.filled_dhl.fill(False)
            self.filled_dhc2l.fill(False)
            self.initial_label_size_dhl.fill(0)
            self.initial_label_size_dhc2l.fill(0)
            self.construction_time_dhl.fill(0)
            self.construction_time_dhc2l.fill(0)
            self.construction_recorded_dhl.fill(False)
            self.construction_recorded_dhc2l.fill(False)
            
            # Reset batch buffers
            for trial in range(self.trials):
                for batch in range(self.batches):
                    self._batch_query_times_dhl[trial][batch].clear()
                    self._batch_query_times_dhc2l[trial][batch].clear()
                    self._batch_lazy_times_dhl[trial][batch].clear()
                    self._batch_lazy_times_dhc2l[trial][batch].clear()
                    self._batch_label_sizes_dhl[trial][batch].clear()
                    self._batch_label_sizes_dhc2l[trial][batch].clear()
                    self._batch_jam_factors[trial][batch].clear()
                    self._batch_error_rates[trial][batch].clear()
            
            # Reset HERE comparison progress
            self.here_comparison_progress = {
                'completed': 0,
                'total': self.routes_per_batch,
                'status': 'not_started',
                'current_route': 0,
                'errors': 0,
                'start_time': None
            }
            
            logger.info("MetricsCollector reset complete")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_metrics_collector(results_path: Path, 
                             trials: int = 3, 
                             batches: int = 3,
                             routes_per_batch: int = 1000) -> ExperimentMetricsCollector:
    """
    Factory function to create a new metrics collector.
    
    Args:
        results_path: Path to results folder
        trials: Number of trials
        batches: Number of batches per trial
        routes_per_batch: Number of routes per batch
        
    Returns:
        Configured ExperimentMetricsCollector instance
    """
    return ExperimentMetricsCollector(
        results_path=results_path,
        trials=trials,
        batches=batches,
        routes_per_batch=routes_per_batch
    )


def compute_accuracy(dhc2l_distance: float, 
                    dijkstra_distance: float,
                    tolerance: float = DEFAULT_TOLERANCE,
                    query_time_ms: float = None) -> AccuracyMetrics:
    """
    Convenience function to compute accuracy metrics.
    
    Args:
        dhc2l_distance: Distance from HC2L algorithm
        dijkstra_distance: Distance from Dijkstra reference
        tolerance: Accuracy tolerance (default 5%)
        query_time_ms: Query response time in milliseconds (optional)
        
    Returns:
        AccuracyMetrics instance
    """
    return AccuracyMetrics.compute(dhc2l_distance, dijkstra_distance, tolerance, query_time_ms)
