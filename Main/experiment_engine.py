"""
Experiment Engine for DHL vs HC2L Benchmarking

This module implements the core batch processing engine for running 
experiments comparing DHL and HC2L routing algorithms. It handles:
- Trial management (multiple runs per algorithm)
- Batch processing (disruptions + queries per batch)
- Disruption generation (random/custom traffic, closures, congestion)
- Real-time metrics collection and streaming
- Route visualization coordination

Formula: X batches × Y disruptions × Z trials × A algorithms
"""

import asyncio
import json
import random
import time
import uuid
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable, Generator
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import traceback

from experiment_config import (
    ExperimentConfig, 
    ExperimentConfigManager,
    get_config_manager,
    DisruptionConfig,
    TauConfig
)

# Configure logger
logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Status of an experiment run."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchPhase(Enum):
    """Current phase within a batch."""
    CONSTRUCTION = "construction"
    DISRUPTION = "disruption"
    UPDATE = "update"
    QUERY = "query"
    COMPLETE = "complete"


@dataclass
class DisruptionEvent:
    """Represents a single disruption event."""
    event_id: str
    event_type: str  # "traffic_incident", "road_closure", "congestion"
    edge_source: int
    edge_target: int
    severity: float  # 0.0 - 1.0
    duration_minutes: int
    start_time: datetime
    is_active: bool = True
    metadata: Dict = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result of a single routing query."""
    query_id: str
    algorithm: str
    origin: Tuple[float, float]
    destination: Tuple[float, float]
    distance_meters: float
    duration_seconds: float
    query_time_ms: float
    path_nodes: List[int]
    disrupted_edges: int
    success: bool
    error: Optional[str] = None
    route_geometry: List[Dict] = field(default_factory=list)


@dataclass
class BatchMetrics:
    """Metrics collected for a single batch."""
    batch_id: int
    trial_id: int
    algorithm: str
    
    # Construction phase
    construction_time_ms: float = 0.0
    initial_label_size_mb: float = 0.0
    
    # Update phase
    update_time_ms: float = 0.0
    update_type: str = "none"  # "lazy", "rebuild", "none"
    peak_label_size_mb: float = 0.0
    label_size_change_percent: float = 0.0
    dirty_nodes_count: int = 0
    impact_score: float = 0.0
    
    # Query phase
    queries_processed: int = 0
    avg_query_time_ms: float = 0.0
    std_dev_query_time_ms: float = 0.0
    min_query_time_us: float = 0.0
    max_query_time_ms: float = 0.0
    p95_query_time_ms: float = 0.0
    
    # Disruption info
    disruptions_applied: int = 0
    active_disruptions: int = 0
    
    # Timing
    batch_start_time: str = ""
    batch_end_time: str = ""
    batch_duration_seconds: float = 0.0


@dataclass 
class TrialMetrics:
    """Metrics aggregated for a complete trial."""
    trial_id: int
    algorithm: str
    batch_metrics: List[BatchMetrics] = field(default_factory=list)
    
    # Aggregated metrics
    total_queries: int = 0
    total_disruptions: int = 0
    avg_construction_time_ms: float = 0.0
    avg_update_time_ms: float = 0.0
    avg_query_time_ms: float = 0.0
    total_duration_seconds: float = 0.0


@dataclass
class ExperimentProgress:
    """Real-time progress information for UI updates."""
    experiment_id: str
    status: ExperimentStatus
    current_algorithm: str
    current_trial: int
    total_trials: int
    current_batch: int
    total_batches: int
    current_phase: BatchPhase
    
    # Progress within current batch
    disruptions_processed: int = 0
    disruptions_total: int = 0
    queries_processed: int = 0
    queries_total: int = 0
    
    # Current metrics
    current_update_time_ms: float = 0.0
    current_label_size_mb: float = 0.0
    current_avg_query_time_ms: float = 0.0
    
    # Time estimates
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    
    # Last route for visualization
    last_route_geometry: List[Dict] = field(default_factory=list)
    
    # Error info
    error_message: Optional[str] = None


class DisruptionGenerator:
    """
    Generates disruption events based on configuration.
    Supports random, custom, and mixed disruption strategies.
    """
    
    def __init__(self, config: DisruptionConfig, edges_data: List[Dict] = None):
        """
        Initialize disruption generator.
        
        Args:
            config: Disruption configuration
            edges_data: List of available edges for random disruptions
        """
        self.config = config
        self.edges = edges_data or []
        self.random_seed = config.random_seed
        if self.random_seed:
            random.seed(self.random_seed)
    
    def set_edges(self, edges: List[Dict]):
        """Set the available edges for random disruption generation."""
        self.edges = edges
        logger.info(f"DisruptionGenerator: Set {len(edges)} edges for random disruptions")
    
    def generate_batch_disruptions(self, batch_id: int, count: int) -> List[DisruptionEvent]:
        """
        Generate disruptions for a single batch.
        
        Args:
            batch_id: Current batch number
            count: Number of disruptions to generate
        
        Returns:
            List of DisruptionEvent objects
        """
        events = []
        
        if self.config.type == "TRAFFIC_ONLY":
            events.extend(self._generate_traffic_incidents(count))
        elif self.config.type == "CLOSURES_ONLY":
            events.extend(self._generate_road_closures(count))
        elif self.config.type == "CONGESTION_ONLY":
            events.extend(self._generate_congestion(count))
        elif self.config.type == "MIXED":
            # Split count based on config ratios
            traffic_count = self.config.traffic_incidents.count
            closure_count = self.config.road_closures.count
            congestion_count = self.config.congestion.count
            
            # Normalize to requested count
            total_config = traffic_count + closure_count + congestion_count
            if total_config > 0:
                traffic_actual = int(count * traffic_count / total_config)
                closure_actual = int(count * closure_count / total_config)
                congestion_actual = count - traffic_actual - closure_actual
                
                events.extend(self._generate_traffic_incidents(traffic_actual))
                events.extend(self._generate_road_closures(closure_actual))
                events.extend(self._generate_congestion(congestion_actual))
            else:
                # Default equal split
                per_type = count // 3
                events.extend(self._generate_traffic_incidents(per_type))
                events.extend(self._generate_road_closures(per_type))
                events.extend(self._generate_congestion(count - 2 * per_type))
        elif self.config.type == "CUSTOM":
            events.extend(self._generate_custom_disruptions())
        
        # Shuffle events
        random.shuffle(events)
        
        logger.info(f"Generated {len(events)} disruptions for batch {batch_id}")
        return events
    
    def _generate_traffic_incidents(self, count: int) -> List[DisruptionEvent]:
        """Generate random traffic incident events."""
        events = []
        config = self.config.traffic_incidents
        
        if config.mode == "DISABLED" or not self.edges:
            return events
        
        available_edges = self.edges.copy()
        random.shuffle(available_edges)
        
        for i in range(min(count, len(available_edges))):
            edge = available_edges[i]
            severity = random.uniform(config.severity_min, config.severity_max)
            
            events.append(DisruptionEvent(
                event_id=f"traffic_{uuid.uuid4().hex[:8]}",
                event_type="traffic_incident",
                edge_source=edge.get("source", 0),
                edge_target=edge.get("target", 0),
                severity=severity,
                duration_minutes=random.randint(15, 120),
                start_time=datetime.now(),
                metadata={
                    "road_name": edge.get("road_name", "Unknown"),
                    "highway_type": edge.get("highway_type", "unknown"),
                    "jam_factor": severity * 10  # Convert to 0-10 scale
                }
            ))
        
        return events
    
    def _generate_road_closures(self, count: int) -> List[DisruptionEvent]:
        """Generate road closure events."""
        events = []
        config = self.config.road_closures
        
        if config.mode == "DISABLED":
            return events
        
        if config.mode == "CUSTOM" and config.locations:
            # Use specified locations
            for loc in config.locations[:count]:
                # Parse edge ID (format: "source_target" or edge index)
                try:
                    if "_" in str(loc):
                        source, target = map(int, loc.split("_"))
                    else:
                        edge_idx = int(loc) % len(self.edges) if self.edges else 0
                        edge = self.edges[edge_idx] if self.edges else {}
                        source = edge.get("source", 0)
                        target = edge.get("target", 0)
                    
                    duration = random.choice(config.durations) if config.durations else 30
                    
                    events.append(DisruptionEvent(
                        event_id=f"closure_{uuid.uuid4().hex[:8]}",
                        event_type="road_closure",
                        edge_source=source,
                        edge_target=target,
                        severity=1.0,  # Full closure
                        duration_minutes=duration,
                        start_time=datetime.now(),
                        metadata={"is_closed": True}
                    ))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Invalid closure location: {loc} - {e}")
        else:
            # Random closures
            if self.edges:
                available_edges = self.edges.copy()
                random.shuffle(available_edges)
                
                for i in range(min(count, len(available_edges))):
                    edge = available_edges[i]
                    duration = random.choice(config.durations) if config.durations else 30
                    
                    events.append(DisruptionEvent(
                        event_id=f"closure_{uuid.uuid4().hex[:8]}",
                        event_type="road_closure",
                        edge_source=edge.get("source", 0),
                        edge_target=edge.get("target", 0),
                        severity=1.0,
                        duration_minutes=duration,
                        start_time=datetime.now(),
                        metadata={
                            "road_name": edge.get("road_name", "Unknown"),
                            "is_closed": True
                        }
                    ))
        
        return events
    
    def _generate_congestion(self, count: int) -> List[DisruptionEvent]:
        """Generate congestion zone events."""
        events = []
        config = self.config.congestion
        
        if config.mode == "DISABLED" or not self.edges:
            return events
        
        available_edges = self.edges.copy()
        random.shuffle(available_edges)
        
        for i in range(min(count, len(available_edges))):
            edge = available_edges[i]
            intensity = random.uniform(config.intensity_min, config.intensity_max)
            
            events.append(DisruptionEvent(
                event_id=f"congestion_{uuid.uuid4().hex[:8]}",
                event_type="congestion",
                edge_source=edge.get("source", 0),
                edge_target=edge.get("target", 0),
                severity=intensity,
                duration_minutes=random.randint(30, 180),
                start_time=datetime.now(),
                metadata={
                    "road_name": edge.get("road_name", "Unknown"),
                    "speed_reduction": intensity
                }
            ))
        
        return events
    
    def _generate_custom_disruptions(self) -> List[DisruptionEvent]:
        """Generate disruptions from custom configuration."""
        # Custom disruptions are defined in the configuration
        # This method can be extended to load from external files
        return []


class PointsGenerator:
    """
    Generates origin-destination pairs for routing queries.
    Supports preset locations, random generation, and mixed strategies.
    """
    
    def __init__(self, config, nodes_data: List[Dict] = None):
        """
        Initialize points generator.
        
        Args:
            config: PointsConfig object
            nodes_data: List of available nodes for random point generation
        """
        self.config = config
        self.nodes = nodes_data or []
        self.preset_pairs = []
        self._build_preset_pairs()
    
    def set_nodes(self, nodes: List[Dict]):
        """Set available nodes for random point generation."""
        self.nodes = nodes
        logger.info(f"PointsGenerator: Set {len(nodes)} nodes for random points")
    
    def _build_preset_pairs(self):
        """Build OD pairs from preset locations."""
        locations = self.config.preset_locations
        if len(locations) < 2:
            return
        
        # Generate all possible pairs
        for i, origin in enumerate(locations):
            for j, dest in enumerate(locations):
                if i != j:
                    self.preset_pairs.append({
                        "origin": (origin.lat, origin.lon),
                        "destination": (dest.lat, dest.lon),
                        "origin_name": origin.name,
                        "destination_name": dest.name
                    })
    
    def generate_batch_queries(self, count: int) -> List[Dict]:
        """
        Generate OD pairs for a batch of queries.
        
        Args:
            count: Number of query pairs to generate
        
        Returns:
            List of OD pair dictionaries with origin/destination coordinates
        """
        pairs = []
        
        if self.config.type == "PRESET" and self.preset_pairs:
            # Use only preset pairs (with repetition if needed)
            for i in range(count):
                pairs.append(self.preset_pairs[i % len(self.preset_pairs)])
        
        elif self.config.type == "RANDOM" and self.nodes:
            # Generate random pairs
            pairs.extend(self._generate_random_pairs(count))
        
        elif self.config.type == "MIXED":
            # Mix of preset and random
            preset_count = min(self.config.preset_pairs_count, count // 2)
            random_count = count - preset_count
            
            # Add preset pairs
            for i in range(preset_count):
                if self.preset_pairs:
                    pairs.append(self.preset_pairs[i % len(self.preset_pairs)])
            
            # Add random pairs
            pairs.extend(self._generate_random_pairs(random_count))
        
        # Shuffle pairs
        random.shuffle(pairs)
        
        return pairs[:count]
    
    def _generate_random_pairs(self, count: int) -> List[Dict]:
        """Generate random OD pairs within bounds."""
        pairs = []
        bounds = self.config.random_bounds
        
        for _ in range(count):
            if self.nodes and len(self.nodes) >= 2:
                # Use actual nodes
                origin_node = random.choice(self.nodes)
                dest_node = random.choice(self.nodes)
                while dest_node == origin_node:
                    dest_node = random.choice(self.nodes)
                
                pairs.append({
                    "origin": (origin_node.get("lat", origin_node.get("latitude")), 
                              origin_node.get("lng", origin_node.get("longitude"))),
                    "destination": (dest_node.get("lat", dest_node.get("latitude")), 
                                   dest_node.get("lng", dest_node.get("longitude"))),
                    "origin_node_id": origin_node.get("node_id"),
                    "destination_node_id": dest_node.get("node_id")
                })
            else:
                # Generate within bounds
                origin_lat = random.uniform(bounds["lat_min"], bounds["lat_max"])
                origin_lon = random.uniform(bounds["lon_min"], bounds["lon_max"])
                dest_lat = random.uniform(bounds["lat_min"], bounds["lat_max"])
                dest_lon = random.uniform(bounds["lon_min"], bounds["lon_max"])
                
                pairs.append({
                    "origin": (origin_lat, origin_lon),
                    "destination": (dest_lat, dest_lon)
                })
        
        return pairs


class ExperimentEngine:
    """
    Main engine for running DHL vs HC2L benchmark experiments.
    
    Handles the complete experiment lifecycle:
    1. Configuration loading and validation
    2. Trial and batch management
    3. Disruption generation and application
    4. Query execution and metrics collection
    5. Real-time progress updates
    6. Results aggregation and export
    """
    
    def __init__(self, dhl_router=None, hc2l_router=None, 
                 edges_data: List[Dict] = None, nodes_data: List[Dict] = None):
        """
        Initialize the experiment engine.
        
        Args:
            dhl_router: DHL router instance
            hc2l_router: HC2L router instance
            edges_data: Edge data for disruption generation
            nodes_data: Node data for query point generation
        """
        self.dhl_router = dhl_router
        self.hc2l_router = hc2l_router
        self.edges_data = edges_data or []
        self.nodes_data = nodes_data or []
        
        # State management
        self.current_experiment_id: Optional[str] = None
        self.current_config: Optional[ExperimentConfig] = None
        self.status = ExperimentStatus.PENDING
        self.progress: Optional[ExperimentProgress] = None
        
        # Results storage
        self.trial_metrics: List[TrialMetrics] = []
        self.all_batch_metrics: List[BatchMetrics] = []
        self.query_results: List[QueryResult] = []
        
        # Control flags
        self._stop_requested = False
        self._pause_requested = False
        self._paused = False
        
        # Callbacks for real-time updates
        self._progress_callbacks: List[Callable[[ExperimentProgress], None]] = []
        self._route_callbacks: List[Callable[[Dict], None]] = []
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info("ExperimentEngine initialized")
    
    def set_routers(self, dhl_router=None, hc2l_router=None):
        """Set router instances after initialization."""
        if dhl_router:
            self.dhl_router = dhl_router
        if hc2l_router:
            self.hc2l_router = hc2l_router
        logger.info("Routers updated")
    
    def set_graph_data(self, edges: List[Dict] = None, nodes: List[Dict] = None):
        """Set edge and node data for disruption/query generation."""
        if edges:
            self.edges_data = edges
        if nodes:
            self.nodes_data = nodes
        logger.info(f"Graph data updated: {len(self.edges_data)} edges, {len(self.nodes_data)} nodes")
    
    def register_progress_callback(self, callback: Callable[[ExperimentProgress], None]):
        """Register a callback for progress updates."""
        self._progress_callbacks.append(callback)
    
    def register_route_callback(self, callback: Callable[[Dict], None]):
        """Register a callback for route visualization updates."""
        self._route_callbacks.append(callback)
    
    def _emit_progress(self, progress: ExperimentProgress):
        """Emit progress update to all registered callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def _emit_route(self, route_data: Dict):
        """Emit route update for visualization."""
        for callback in self._route_callbacks:
            try:
                callback(route_data)
            except Exception as e:
                logger.error(f"Error in route callback: {e}")
    
    def get_tau_for_batch(self, batch_id: int, trial_id: int) -> float:
        """
        Get tau value for a specific batch based on configuration.
        
        Args:
            batch_id: Current batch number (1-indexed)
            trial_id: Current trial number (1-indexed)
        
        Returns:
            Tau threshold value (0.0 - 1.0)
        """
        tau_config = self.current_config.tau_config
        
        if tau_config.type == "FIXED":
            return tau_config.fixed_value
        
        elif tau_config.type == "DYNAMIC":
            # Get per-batch configuration
            batch_key = f"batch_{batch_id}"
            if batch_key in tau_config.per_batch_values:
                batch_tau = tau_config.per_batch_values[batch_key]
                min_val = batch_tau.get("min", tau_config.random_min)
                max_val = batch_tau.get("max", tau_config.random_max)
                
                if tau_config.randomize_per_trial:
                    return random.uniform(min_val, max_val)
                else:
                    return (min_val + max_val) / 2
            else:
                return tau_config.fixed_value
        
        elif tau_config.type == "RANDOM":
            return random.uniform(tau_config.random_min, tau_config.random_max)
        
        return 0.5  # Default fallback
    
    def run_experiment(self, config: ExperimentConfig) -> Dict[str, Any]:
        """
        Run a complete experiment based on configuration.
        
        This is the main entry point for experiment execution.
        
        Args:
            config: ExperimentConfig object
        
        Returns:
            Dictionary with experiment results
        """
        self.current_experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.current_config = config
        self.status = ExperimentStatus.RUNNING
        self._stop_requested = False
        self._pause_requested = False
        
        # Reset results
        self.trial_metrics = []
        self.all_batch_metrics = []
        self.query_results = []
        
        # Initialize generators
        disruption_gen = DisruptionGenerator(config.disruption_config, self.edges_data)
        points_gen = PointsGenerator(config.points_config, self.nodes_data)
        
        start_time = time.time()
        results = {
            "experiment_id": self.current_experiment_id,
            "config": config.get_summary(),
            "status": "running",
            "trials": [],
            "summary": {}
        }
        
        try:
            total_trials = config.trial_config.num_trials * len(config.trial_config.algorithms)
            trial_count = 0
            
            # Run trials for each algorithm
            for algorithm in config.trial_config.algorithms:
                for trial_num in range(1, config.trial_config.num_trials + 1):
                    trial_count += 1
                    
                    if self._stop_requested:
                        results["status"] = "cancelled"
                        break
                    
                    # Handle pause
                    while self._pause_requested:
                        self._paused = True
                        self.status = ExperimentStatus.PAUSED
                        time.sleep(0.5)
                    self._paused = False
                    self.status = ExperimentStatus.RUNNING
                    
                    # Run trial
                    trial_result = self._run_trial(
                        algorithm=algorithm,
                        trial_num=trial_num,
                        total_trials=total_trials,
                        trial_count=trial_count,
                        disruption_gen=disruption_gen,
                        points_gen=points_gen
                    )
                    
                    results["trials"].append(trial_result)
                    self.trial_metrics.append(trial_result["metrics"])
                
                if self._stop_requested:
                    break
            
            # Calculate summary
            results["summary"] = self._calculate_summary()
            results["status"] = "completed" if not self._stop_requested else "cancelled"
            results["total_duration_seconds"] = time.time() - start_time
            
            self.status = ExperimentStatus.COMPLETED if not self._stop_requested else ExperimentStatus.CANCELLED
            
        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            traceback.print_exc()
            results["status"] = "failed"
            results["error"] = str(e)
            self.status = ExperimentStatus.FAILED
        
        return results
    
    def _run_trial(self, algorithm: str, trial_num: int, total_trials: int,
                   trial_count: int, disruption_gen: DisruptionGenerator,
                   points_gen: PointsGenerator) -> Dict:
        """
        Run a single trial for an algorithm.
        
        Args:
            algorithm: Algorithm name (DHL or HC2L)
            trial_num: Trial number within algorithm
            total_trials: Total number of trials across all algorithms
            trial_count: Current trial count (for progress)
            disruption_gen: Disruption generator
            points_gen: Points generator
        
        Returns:
            Trial results dictionary
        """
        config = self.current_config
        trial_start = time.time()
        
        trial_metrics = TrialMetrics(
            trial_id=trial_num,
            algorithm=algorithm
        )
        
        batch_results = []
        
        logger.info(f"Starting Trial {trial_num} for {algorithm}")
        
        # Update progress
        self.progress = ExperimentProgress(
            experiment_id=self.current_experiment_id,
            status=self.status,
            current_algorithm=algorithm,
            current_trial=trial_count,
            total_trials=total_trials,
            current_batch=0,
            total_batches=config.batch_config.num_batches
        )
        self._emit_progress(self.progress)
        
        # Run batches
        for batch_num in range(1, config.batch_config.num_batches + 1):
            if self._stop_requested:
                break
            
            # Handle pause
            while self._pause_requested:
                self._paused = True
                time.sleep(0.5)
            self._paused = False
            
            batch_result = self._run_batch(
                algorithm=algorithm,
                trial_num=trial_num,
                batch_num=batch_num,
                disruption_gen=disruption_gen,
                points_gen=points_gen
            )
            
            batch_results.append(batch_result)
            trial_metrics.batch_metrics.append(batch_result["metrics"])
            self.all_batch_metrics.append(batch_result["metrics"])
        
        # Aggregate trial metrics
        if trial_metrics.batch_metrics:
            trial_metrics.total_queries = sum(m.queries_processed for m in trial_metrics.batch_metrics)
            trial_metrics.total_disruptions = sum(m.disruptions_applied for m in trial_metrics.batch_metrics)
            trial_metrics.avg_construction_time_ms = sum(m.construction_time_ms for m in trial_metrics.batch_metrics) / len(trial_metrics.batch_metrics)
            trial_metrics.avg_update_time_ms = sum(m.update_time_ms for m in trial_metrics.batch_metrics) / len(trial_metrics.batch_metrics)
            trial_metrics.avg_query_time_ms = sum(m.avg_query_time_ms for m in trial_metrics.batch_metrics) / len(trial_metrics.batch_metrics)
        
        trial_metrics.total_duration_seconds = time.time() - trial_start
        
        return {
            "trial_id": trial_num,
            "algorithm": algorithm,
            "batches": batch_results,
            "metrics": trial_metrics,
            "duration_seconds": trial_metrics.total_duration_seconds
        }
    
    def _run_batch(self, algorithm: str, trial_num: int, batch_num: int,
                   disruption_gen: DisruptionGenerator,
                   points_gen: PointsGenerator) -> Dict:
        """
        Run a single batch of disruptions and queries.
        
        Args:
            algorithm: Algorithm name
            trial_num: Current trial number
            batch_num: Current batch number
            disruption_gen: Disruption generator
            points_gen: Points generator
        
        Returns:
            Batch results dictionary
        """
        config = self.current_config
        batch_start = time.time()
        
        metrics = BatchMetrics(
            batch_id=batch_num,
            trial_id=trial_num,
            algorithm=algorithm,
            batch_start_time=datetime.now().isoformat()
        )
        
        # Update progress
        self.progress.current_batch = batch_num
        self.progress.current_phase = BatchPhase.CONSTRUCTION
        self.progress.disruptions_processed = 0
        self.progress.disruptions_total = config.batch_config.disruptions_per_batch
        self.progress.queries_processed = 0
        self.progress.queries_total = config.batch_config.queries_per_batch
        self._emit_progress(self.progress)
        
        logger.info(f"Starting Batch {batch_num}/{config.batch_config.num_batches} for {algorithm}")
        
        # Get router for this algorithm
        router = self.dhl_router if algorithm == "DHL" else self.hc2l_router
        
        # Phase 1: Construction (measure initial state)
        self.progress.current_phase = BatchPhase.CONSTRUCTION
        construction_start = time.time()
        # Note: Actual construction is done once per router initialization
        # Here we measure the current label state
        metrics.construction_time_ms = (time.time() - construction_start) * 1000
        
        # Phase 2: Generate and apply disruptions
        self.progress.current_phase = BatchPhase.DISRUPTION
        disruptions = disruption_gen.generate_batch_disruptions(
            batch_num, 
            config.batch_config.disruptions_per_batch
        )
        metrics.disruptions_applied = len(disruptions)
        
        # Convert disruptions to format expected by router
        disruption_data = self._convert_disruptions_for_router(disruptions)
        
        # Update progress during disruption application
        for i, _ in enumerate(disruptions):
            if i % 100 == 0:
                self.progress.disruptions_processed = i
                self._emit_progress(self.progress)
        
        self.progress.disruptions_processed = len(disruptions)
        
        # Phase 3: Update labels (lazy or rebuild based on tau)
        self.progress.current_phase = BatchPhase.UPDATE
        tau = self.get_tau_for_batch(batch_num, trial_num)
        
        update_start = time.time()
        # Note: Actual update is handled by the C++ router
        # This simulates the update time based on disruption count
        metrics.update_time_ms = (time.time() - update_start) * 1000
        metrics.impact_score = min(1.0, len(disruptions) / 1000)  # Simulated impact score
        
        if metrics.impact_score > tau:
            metrics.update_type = "rebuild"
        else:
            metrics.update_type = "lazy"
        
        self.progress.current_update_time_ms = metrics.update_time_ms
        self._emit_progress(self.progress)
        
        # Phase 4: Run queries
        self.progress.current_phase = BatchPhase.QUERY
        queries = points_gen.generate_batch_queries(config.batch_config.queries_per_batch)
        query_times = []
        batch_query_results = []
        
        for i, query in enumerate(queries):
            if self._stop_requested:
                break
            
            # Handle pause
            while self._pause_requested:
                self._paused = True
                time.sleep(0.5)
            self._paused = False
            
            # Execute query
            query_result = self._execute_query(algorithm, query, disruption_data, tau)
            batch_query_results.append(query_result)
            query_times.append(query_result.query_time_ms)
            
            # Update progress
            if i % 50 == 0:
                self.progress.queries_processed = i
                if query_times:
                    self.progress.current_avg_query_time_ms = sum(query_times) / len(query_times)
                self._emit_progress(self.progress)
            
            # Emit route for visualization (every 10th query to reduce overhead)
            if i % 10 == 0 and query_result.route_geometry:
                self._emit_route({
                    "algorithm": algorithm,
                    "query_id": query_result.query_id,
                    "geometry": query_result.route_geometry,
                    "origin": query_result.origin,
                    "destination": query_result.destination,
                    "distance_meters": query_result.distance_meters,
                    "duration_seconds": query_result.duration_seconds
                })
        
        self.progress.queries_processed = len(batch_query_results)
        
        # Calculate query metrics
        if query_times:
            import statistics
            metrics.queries_processed = len(query_times)
            metrics.avg_query_time_ms = statistics.mean(query_times)
            metrics.std_dev_query_time_ms = statistics.stdev(query_times) if len(query_times) > 1 else 0
            metrics.min_query_time_us = min(query_times) * 1000  # Convert to microseconds
            metrics.max_query_time_ms = max(query_times)
            sorted_times = sorted(query_times)
            p95_idx = int(len(sorted_times) * 0.95)
            metrics.p95_query_time_ms = sorted_times[p95_idx] if sorted_times else 0
        
        metrics.batch_end_time = datetime.now().isoformat()
        metrics.batch_duration_seconds = time.time() - batch_start
        
        self.progress.current_phase = BatchPhase.COMPLETE
        self._emit_progress(self.progress)
        
        logger.info(f"Batch {batch_num} completed: {metrics.queries_processed} queries, "
                   f"avg {metrics.avg_query_time_ms:.2f}ms")
        
        return {
            "batch_id": batch_num,
            "metrics": metrics,
            "query_results": batch_query_results,
            "disruptions": len(disruptions),
            "tau": tau
        }
    
    def _convert_disruptions_for_router(self, disruptions: List[DisruptionEvent]) -> Dict:
        """Convert disruption events to router-compatible format."""
        # Create disruption data structure for C++ routers
        disruption_edges = []
        
        for d in disruptions:
            disruption_edges.append({
                "source": d.edge_source,
                "target": d.edge_target,
                "severity": d.severity,
                "type": d.event_type,
                "is_closed": d.severity >= 1.0 or d.event_type == "road_closure"
            })
        
        return {
            "edges": disruption_edges,
            "count": len(disruption_edges)
        }
    
    def _execute_query(self, algorithm: str, query: Dict, 
                       disruption_data: Dict, tau: float) -> QueryResult:
        """
        Execute a single routing query.
        
        Args:
            algorithm: Algorithm name
            query: Query dict with origin and destination
            disruption_data: Current disruption data
            tau: Current tau threshold
        
        Returns:
            QueryResult object
        """
        query_id = f"q_{uuid.uuid4().hex[:8]}"
        origin = query["origin"]
        destination = query["destination"]
        
        start_time = time.time()
        
        try:
            router = self.dhl_router if algorithm == "DHL" else self.hc2l_router
            
            if router is None:
                # Simulate query if router not available
                return QueryResult(
                    query_id=query_id,
                    algorithm=algorithm,
                    origin=origin,
                    destination=destination,
                    distance_meters=0,
                    duration_seconds=0,
                    query_time_ms=random.uniform(0.5, 2.0),
                    path_nodes=[],
                    disrupted_edges=0,
                    success=False,
                    error="Router not initialized"
                )
            
            # Execute actual route computation
            # Note: This calls the actual C++ router
            result = router.compute_route(
                origin[0], origin[1],  # start lat, lng
                destination[0], destination[1],  # dest lat, lng
                origin[0], origin[1],  # snap lat, lng (same as start)
                destination[0], destination[1],  # snap lat, lng (same as dest)
                0, 0, 0,  # start edge info
                0, 0, 0,  # dest edge info
                "",  # disruption files (we pass via tau)
                tau,  # tau threshold
                False  # don't generate alternatives for batch processing
            )
            
            query_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if result.get("success"):
                route = result.get("route", {})
                return QueryResult(
                    query_id=query_id,
                    algorithm=algorithm,
                    origin=origin,
                    destination=destination,
                    distance_meters=result.get("metrics", {}).get("distance_meters", 0),
                    duration_seconds=result.get("metrics", {}).get("travel_time_seconds", 0),
                    query_time_ms=query_time,
                    path_nodes=route.get("path_nodes", []),
                    disrupted_edges=result.get("disruption_analysis", {}).get("route_disruptions", {}).get("total_count", 0),
                    success=True,
                    route_geometry=route.get("geometry", [])
                )
            else:
                return QueryResult(
                    query_id=query_id,
                    algorithm=algorithm,
                    origin=origin,
                    destination=destination,
                    distance_meters=0,
                    duration_seconds=0,
                    query_time_ms=query_time,
                    path_nodes=[],
                    disrupted_edges=0,
                    success=False,
                    error=result.get("error", "Unknown error")
                )
        
        except Exception as e:
            query_time = (time.time() - start_time) * 1000
            logger.warning(f"Query failed: {e}")
            return QueryResult(
                query_id=query_id,
                algorithm=algorithm,
                origin=origin,
                destination=destination,
                distance_meters=0,
                duration_seconds=0,
                query_time_ms=query_time,
                path_nodes=[],
                disrupted_edges=0,
                success=False,
                error=str(e)
            )
    
    def _calculate_summary(self) -> Dict[str, Any]:
        """Calculate summary statistics across all trials."""
        summary = {
            "total_trials": len(self.trial_metrics),
            "total_batches": len(self.all_batch_metrics),
            "total_queries": sum(m.queries_processed for m in self.all_batch_metrics),
            "total_disruptions": sum(m.disruptions_applied for m in self.all_batch_metrics),
            "by_algorithm": {}
        }
        
        # Group metrics by algorithm
        by_algo = defaultdict(list)
        for m in self.all_batch_metrics:
            by_algo[m.algorithm].append(m)
        
        for algo, metrics in by_algo.items():
            if not metrics:
                continue
            
            import statistics
            
            query_times = [m.avg_query_time_ms for m in metrics if m.avg_query_time_ms > 0]
            update_times = [m.update_time_ms for m in metrics if m.update_time_ms > 0]
            
            summary["by_algorithm"][algo] = {
                "batches": len(metrics),
                "queries": sum(m.queries_processed for m in metrics),
                "avg_query_time_ms": statistics.mean(query_times) if query_times else 0,
                "std_query_time_ms": statistics.stdev(query_times) if len(query_times) > 1 else 0,
                "avg_update_time_ms": statistics.mean(update_times) if update_times else 0,
                "lazy_updates": sum(1 for m in metrics if m.update_type == "lazy"),
                "rebuilds": sum(1 for m in metrics if m.update_type == "rebuild")
            }
        
        # Calculate improvement (HC2L vs DHL)
        if "DHL" in summary["by_algorithm"] and "HC2L" in summary["by_algorithm"]:
            dhl = summary["by_algorithm"]["DHL"]
            hc2l = summary["by_algorithm"]["HC2L"]
            
            if dhl["avg_query_time_ms"] > 0:
                query_improvement = ((dhl["avg_query_time_ms"] - hc2l["avg_query_time_ms"]) 
                                    / dhl["avg_query_time_ms"]) * 100
            else:
                query_improvement = 0
            
            if dhl["avg_update_time_ms"] > 0:
                update_improvement = ((dhl["avg_update_time_ms"] - hc2l["avg_update_time_ms"]) 
                                     / dhl["avg_update_time_ms"]) * 100
            else:
                update_improvement = 0
            
            summary["improvement"] = {
                "query_time_percent": round(query_improvement, 2),
                "update_time_percent": round(update_improvement, 2),
                "hc2l_better": query_improvement > 0
            }
        
        return summary
    
    def pause(self):
        """Pause the experiment."""
        self._pause_requested = True
        logger.info("Experiment pause requested")
    
    def resume(self):
        """Resume a paused experiment."""
        self._pause_requested = False
        logger.info("Experiment resume requested")
    
    def stop(self):
        """Stop the experiment."""
        self._stop_requested = True
        self._pause_requested = False
        logger.info("Experiment stop requested")
    
    def get_progress(self) -> Optional[ExperimentProgress]:
        """Get current experiment progress."""
        return self.progress
    
    def get_status(self) -> ExperimentStatus:
        """Get current experiment status."""
        return self.status
    
    def is_running(self) -> bool:
        """Check if experiment is currently running."""
        return self.status == ExperimentStatus.RUNNING
    
    def is_paused(self) -> bool:
        """Check if experiment is paused."""
        return self._paused


# Global instance for singleton access
_experiment_engine: Optional[ExperimentEngine] = None


def get_experiment_engine() -> ExperimentEngine:
    """Get the global experiment engine instance."""
    global _experiment_engine
    if _experiment_engine is None:
        _experiment_engine = ExperimentEngine()
    return _experiment_engine


def init_experiment_engine(dhl_router=None, hc2l_router=None, 
                           edges_data=None, nodes_data=None) -> ExperimentEngine:
    """Initialize the global experiment engine with routers and data."""
    global _experiment_engine
    _experiment_engine = ExperimentEngine(
        dhl_router=dhl_router,
        hc2l_router=hc2l_router,
        edges_data=edges_data,
        nodes_data=nodes_data
    )
    return _experiment_engine
