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
                tolerance: float = DEFAULT_TOLERANCE) -> "AccuracyMetrics":
        """Compute accuracy metrics from distances"""
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
    """
    
    def __init__(self, 
                 results_path: Path,
                 trials: int = 3, 
                 batches: int = 3, 
                 routes_per_batch: int = 1000,
                 tolerance: float = DEFAULT_TOLERANCE):
        """
        Initialize the metrics collector.
        
        Args:
            results_path: Path to results folder for saving CSV/JSON files
            trials: Number of trials in experiment
            batches: Number of batches per trial  
            routes_per_batch: Number of routes per batch
            tolerance: Accuracy tolerance threshold (default 5%)
        """
        self.results_path = Path(results_path)
        self.trials = trials
        self.batches = batches
        self.routes_per_batch = routes_per_batch
        self.tolerance = tolerance
        
        # Create results directory
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        # Thread-safe locks
        self.lock = threading.Lock()
        self.csv_lock = threading.Lock()
        
        # ====================================================================
        # METRICS STORAGE - Lists for CSV export
        # ====================================================================
        
        # Per-route metrics records (DHL and HC2L)
        self.route_records_dhl: List[RouteMetricsRecord] = []
        self.route_records_dhc2l: List[RouteMetricsRecord] = []
        
        # Similarity records (HERE vs HC2L)
        self.similarity_records: List[SimilarityRecord] = []
        
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
                
                if is_hc2l:
                    # HC2L/DHC2L: Extract distances from API result
                    dhc2l_dist = float(metrics.get("calculated_distance_meters", 0))
                    dijkstra_dist = float(metrics.get("dijkstra_distance_meter", 0))
                    
                    record.accuracy = AccuracyMetrics.compute(
                        dhc2l_dist, dijkstra_dist, self.tolerance
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
                        dhl_dist, dijkstra_dist, self.tolerance
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
                summary = api_result.get("summary", {})
                query_phase = api_result.get("query_phase", {})
                update_phase = api_result.get("update_phase", {})
                
                query_time = float(query_phase.get("query_time_ms", 0) or 
                                  summary.get("query_time_ms", 0) or 0)
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
                        ttd_rating=comparison_data.get('ttd_rating', 'N/A')
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
            "similarity": self.export_similarity_csv()
        }
        
        logger.info(f"All CSVs exported to: {self.results_path}")
        return csv_paths
    
    # ========================================================================
    # JSON RESULTS GENERATION
    # ========================================================================
    
    def generate_results_json(self, experiment_config: Optional[Dict] = None) -> Path:
        """
        Generate minimal JSON results file with configuration and summary statistics.
        Detailed data is in CSV files.
        
        Args:
            experiment_config: Optional experiment configuration to include
            
        Returns:
            Path to generated JSON file
        """
        json_path = self.results_path / "experiment_results.json"
        
        results = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "version": "2.0",
                "format": "minimal_json_with_csv"
            },
            "configuration": experiment_config or self._get_default_config(),
            "summary": self._compute_summary(),
            "accuracy_stats": self._compute_accuracy_stats(),
            "performance_stats": self._compute_performance_stats(),
            "graph_data": self._compute_graph_data(),
            "csv_files": {
                "summary": "summary_results.csv",
                "accuracy": "accuracy_results.csv",
                "construction": "construction_results.csv",
                "updates": "updates_results.csv",
                "performance": "performance_results.csv",
                "similarity": "similarity_results.csv"
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
            "algorithms": ["DHL", "HC2L"]
        }
    
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
        
        # Export all CSVs
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
    # GRAPH DATA COMPUTATION
    # ========================================================================
    
    def _compute_graph_data(self) -> Dict:
        """
        Compute comprehensive data for graph visualizations.
        Includes jam factor, error rate, query time, and label size charts.
        """
        with self.lock:
            graph_data = {
                "time_series": self._compute_time_series(),
                "algorithm_comparison": self._compute_algorithm_comparison(),
                "per_trial": self._compute_per_trial_data(),
                "per_batch": self._compute_per_batch_data(),
                "jam_factor_chart": self._compute_jam_factor_chart(),
                "error_rate_chart": self._compute_error_rate_chart(),
                "label_size_trend": self._compute_label_size_trend(),
                "rebuild_analysis": self._compute_rebuild_analysis()
            }
            return graph_data
    
    def _compute_time_series(self) -> Dict:
        """Compute time series data for query and update times"""
        result = {}
        
        for algorithm in ["DHL", "HC2L"]:
            # Use normalized check for algorithm type
            is_dhl = not is_hc2l_algorithm(algorithm)
            query_data = self.query_time_dhl if is_dhl else self.query_time_dhc2l
            rebuild_data = self.threshold_rebuild_time_dhl if is_dhl else self.threshold_rebuild_time_dhc2l
            filled = self.filled_dhl if is_dhl else self.filled_dhc2l
            lazy_buffers = self._batch_lazy_times_dhl if is_dhl else self._batch_lazy_times_dhc2l
            
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
                    batch_lazy = lazy_buffers[trial][batch]
                    if batch_lazy:
                        update_times.append(round(float(np.mean(batch_lazy)), 3))
                    else:
                        update_times.append(0)
                    
                    # Threshold rebuild time
                    rebuild_times.append(round(float(rebuild_data[trial, batch]), 3))
            
            result[algorithm] = {
                "batch_labels": batch_labels,
                "query_times": query_times,
                "update_times": update_times,
                "rebuild_times": rebuild_times
            }
        
        return result
    
    def _compute_algorithm_comparison(self) -> Dict:
        """Compute algorithm comparison averages"""
        dhl_avg_query = []
        dhc2l_avg_query = []
        dhl_avg_label = []
        dhc2l_avg_label = []
        
        for trial in range(self.trials):
            dhl_mask = self.filled_dhl[trial, :, :]
            dhc2l_mask = self.filled_dhc2l[trial, :, :]
            
            if np.any(dhl_mask):
                dhl_avg_query.append(float(np.mean(self.query_time_dhl[trial, :, :][dhl_mask])))
                dhl_avg_label.append(float(np.mean(self.label_size_dhl[trial, :, :][dhl_mask])))
            
            if np.any(dhc2l_mask):
                dhc2l_avg_query.append(float(np.mean(self.query_time_dhc2l[trial, :, :][dhc2l_mask])))
                dhc2l_avg_label.append(float(np.mean(self.label_size_dhc2l[trial, :, :][dhc2l_mask])))
        
        return {
            "avg_query_time": {
                "DHL": round(float(np.mean(dhl_avg_query)), 3) if dhl_avg_query else 0,
                "HC2L": round(float(np.mean(dhc2l_avg_query)), 3) if dhc2l_avg_query else 0
            },
            "avg_label_size": {
                "DHL": round(float(np.mean(dhl_avg_label)), 5) if dhl_avg_label else 0,
                "HC2L": round(float(np.mean(dhc2l_avg_label)), 5) if dhc2l_avg_label else 0
            }
        }
    
    def _compute_per_trial_data(self) -> Dict:
        """Compute per-trial breakdown"""
        trial_labels = [f"Trial {i+1}" for i in range(self.trials)]
        dhl_trial_query = []
        dhc2l_trial_query = []
        dhl_trial_update = []
        dhc2l_trial_update = []
        
        for trial in range(self.trials):
            dhl_mask = self.filled_dhl[trial, :, :]
            dhc2l_mask = self.filled_dhc2l[trial, :, :]
            
            if np.any(dhl_mask):
                dhl_trial_query.append(round(float(np.mean(self.query_time_dhl[trial, :, :][dhl_mask])), 3))
            else:
                dhl_trial_query.append(0)
            
            if np.any(dhc2l_mask):
                dhc2l_trial_query.append(round(float(np.mean(self.query_time_dhc2l[trial, :, :][dhc2l_mask])), 3))
            else:
                dhc2l_trial_query.append(0)
            
            # Update times
            dhl_lazy_all = []
            dhc2l_lazy_all = []
            for batch in range(self.batches):
                dhl_lazy_all.extend(self._batch_lazy_times_dhl[trial][batch])
                dhc2l_lazy_all.extend(self._batch_lazy_times_dhc2l[trial][batch])
            
            dhl_trial_update.append(round(float(np.mean(dhl_lazy_all)), 3) if dhl_lazy_all else 0)
            dhc2l_trial_update.append(round(float(np.mean(dhc2l_lazy_all)), 3) if dhc2l_lazy_all else 0)
        
        return {
            "trial_labels": trial_labels,
            "DHL_query": dhl_trial_query,
            "HC2L_query": dhc2l_trial_query,
            "DHL_update": dhl_trial_update,
            "HC2L_update": dhc2l_trial_update
        }
    
    def _compute_per_batch_data(self) -> Dict:
        """Compute per-batch averages across trials"""
        batch_labels = [f"Batch {i+1} ({get_disruption_level(i+1)})" for i in range(self.batches)]
        
        dhl_batch_query = []
        dhc2l_batch_query = []
        dhl_batch_label = []
        dhc2l_batch_label = []
        dhl_batch_error = []
        dhc2l_batch_error = []
        
        for batch in range(self.batches):
            # DHL stats for this batch
            dhl_mask = self.filled_dhl[:, batch, :]
            if np.any(dhl_mask):
                dhl_batch_query.append(round(float(np.mean(self.query_time_dhl[:, batch, :][dhl_mask])), 3))
                dhl_batch_label.append(round(float(np.mean(self.label_size_dhl[:, batch, :][dhl_mask])), 5))
            else:
                dhl_batch_query.append(0)
                dhl_batch_label.append(0)
            dhl_batch_error.append(0)  # DHL doesn't have accuracy metrics
            
            # HC2L stats for this batch
            dhc2l_mask = self.filled_dhc2l[:, batch, :]
            if np.any(dhc2l_mask):
                dhc2l_batch_query.append(round(float(np.mean(self.query_time_dhc2l[:, batch, :][dhc2l_mask])), 3))
                dhc2l_batch_label.append(round(float(np.mean(self.label_size_dhc2l[:, batch, :][dhc2l_mask])), 5))
                # Error rate = percentage of incorrect routes
                total = np.sum(dhc2l_mask)
                incorrect = total - np.sum(self.is_correct[:, batch, :][dhc2l_mask])
                dhc2l_batch_error.append(round(float(incorrect / total * 100), 2) if total > 0 else 0)
            else:
                dhc2l_batch_query.append(0)
                dhc2l_batch_label.append(0)
                dhc2l_batch_error.append(0)
        
        return {
            "batch_labels": batch_labels,
            "DHL_query": dhl_batch_query,
            "HC2L_query": dhc2l_batch_query,
            "DHL_label_size": dhl_batch_label,
            "HC2L_label_size": dhc2l_batch_label,
            "HC2L_error_rate": dhc2l_batch_error
        }
    
    def _compute_jam_factor_chart(self) -> Dict:
        """Compute jam factor chart data per batch"""
        batch_labels = []
        avg_jam_factors = []
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                batch_labels.append(f"T{trial+1}B{batch+1}")
                
                jam_factors = self._batch_jam_factors[trial][batch]
                if jam_factors:
                    avg_jam_factors.append(round(float(np.mean(jam_factors)), 2))
                else:
                    avg_jam_factors.append(0)
        
        # Compute per-disruption-level averages (FIX: handle empty arrays properly)
        per_level = {}
        if self.batches >= 3:
            # Light (batch 0)
            light_factors = [jf for t in range(self.trials) for jf in self._batch_jam_factors[t][0]]
            per_level["light"] = round(float(np.mean(light_factors)), 2) if light_factors else 0.0
            
            # Medium (batch 1)
            medium_factors = [jf for t in range(self.trials) for jf in self._batch_jam_factors[t][1]]
            per_level["medium"] = round(float(np.mean(medium_factors)), 2) if medium_factors else 0.0
            
            # Heavy (batch 2)
            heavy_factors = [jf for t in range(self.trials) for jf in self._batch_jam_factors[t][2]]
            per_level["heavy"] = round(float(np.mean(heavy_factors)), 2) if heavy_factors else 0.0
        
        return {
            "batch_labels": batch_labels,
            "avg_jam_factors": avg_jam_factors,
            "per_disruption_level": per_level
        }
    
    def _compute_error_rate_chart(self) -> Dict:
        """Compute error rate chart data per batch (HC2L only)"""
        batch_labels = []
        error_rates = []
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                batch_labels.append(f"T{trial+1}B{batch+1}")
                
                # Compute error rate for this trial/batch
                mask = self.filled_dhc2l[trial, batch, :]
                if np.any(mask):
                    total = np.sum(mask)
                    incorrect = total - np.sum(self.is_correct[trial, batch, :][mask])
                    error_rates.append(round(float(incorrect / total * 100), 2))
                else:
                    error_rates.append(0)
        
        # Per disruption level averages
        per_level = {}
        for batch in range(min(self.batches, 3)):
            level = get_disruption_level(batch + 1)
            level_rates = []
            for trial in range(self.trials):
                mask = self.filled_dhc2l[trial, batch, :]
                if np.any(mask):
                    total = np.sum(mask)
                    incorrect = total - np.sum(self.is_correct[trial, batch, :][mask])
                    level_rates.append(incorrect / total * 100)
            per_level[level] = round(float(np.mean(level_rates)), 2) if level_rates else 0
        
        return {
            "batch_labels": batch_labels,
            "error_rates": error_rates,
            "per_disruption_level": per_level
        }
    
    def _compute_label_size_trend(self) -> Dict:
        """Compute label size trend over batches"""
        dhl_label_trend = []
        dhc2l_label_trend = []
        batch_labels = []
        
        for trial in range(self.trials):
            for batch in range(self.batches):
                batch_labels.append(f"T{trial+1}B{batch+1}")
                
                dhl_mask = self.filled_dhl[trial, batch, :]
                dhc2l_mask = self.filled_dhc2l[trial, batch, :]
                
                if np.any(dhl_mask):
                    dhl_label_trend.append(round(float(np.mean(self.label_size_dhl[trial, batch, :][dhl_mask])), 5))
                else:
                    dhl_label_trend.append(0)
                
                if np.any(dhc2l_mask):
                    dhc2l_label_trend.append(round(float(np.mean(self.label_size_dhc2l[trial, batch, :][dhc2l_mask])), 5))
                else:
                    dhc2l_label_trend.append(0)
        
        return {
            "batch_labels": batch_labels,
            "DHL_labels": dhl_label_trend,
            "HC2L_labels": dhc2l_label_trend
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
                    tolerance: float = DEFAULT_TOLERANCE) -> AccuracyMetrics:
    """
    Convenience function to compute accuracy metrics.
    
    Args:
        dhc2l_distance: Distance from HC2L algorithm
        dijkstra_distance: Distance from Dijkstra reference
        tolerance: Accuracy tolerance (default 5%)
        
    Returns:
        AccuracyMetrics instance
    """
    return AccuracyMetrics.compute(dhc2l_distance, dijkstra_distance, tolerance)
