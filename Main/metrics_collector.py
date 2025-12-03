"""
Metrics Collector System for DHL vs HC2L Benchmarking

This module handles comprehensive metrics collection during experiment execution:
- Construction phase metrics (build time, initial size)
- Update phase metrics (lazy/rebuild time, memory)
- Query phase metrics (latency, throughput)
- Route quality metrics (distance, duration, disrupted edges)

Metrics are collected in real-time and can be exported to CSV.
"""

import time
import tracemalloc
import statistics
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Export directory
EXPORT_DIR = Path(__file__).parent / "data" / "experiment_results"


@dataclass
class ConstructionMetrics:
    """Metrics captured during initial label construction."""
    algorithm: str
    trial_id: int
    
    construction_time_ms: float = 0.0
    initial_label_size_mb: float = 0.0
    graph_construction_time_ms: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    hub_count: int = 0
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class UpdateMetrics:
    """Metrics captured during label updates."""
    algorithm: str
    trial_id: int
    batch_id: int
    
    # Update timing
    lazy_update_time_ms: float = 0.0
    threshold_rebuild_time_ms: float = 0.0
    total_update_time_ms: float = 0.0
    update_type: str = "none"  # "lazy", "rebuild", "none"
    
    # Memory
    peak_label_size_mb: float = 0.0
    label_size_before_mb: float = 0.0
    label_size_after_mb: float = 0.0
    label_size_change_percent: float = 0.0
    
    # Impact analysis
    dirty_nodes_count: int = 0
    impact_score: float = 0.0
    tau_threshold: float = 0.5
    threshold_exceeded: bool = False
    
    # Disruption info
    disruptions_applied: int = 0
    affected_edges: int = 0
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class QueryMetrics:
    """Metrics captured during query execution."""
    algorithm: str
    trial_id: int
    batch_id: int
    
    # Aggregate stats
    queries_processed: int = 0
    queries_successful: int = 0
    queries_failed: int = 0
    
    # Timing stats (all in ms unless specified)
    avg_query_time_ms: float = 0.0
    std_dev_query_time_ms: float = 0.0
    min_query_time_us: float = 0.0  # microseconds
    max_query_time_ms: float = 0.0
    p50_query_time_ms: float = 0.0  # median
    p90_query_time_ms: float = 0.0
    p95_query_time_ms: float = 0.0
    p99_query_time_ms: float = 0.0
    
    # Throughput
    queries_per_second: float = 0.0
    total_query_duration_ms: float = 0.0
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RouteQualityMetrics:
    """Metrics for evaluating route quality."""
    query_id: str
    algorithm: str
    trial_id: int
    batch_id: int
    
    # Route characteristics
    distance_meters: float = 0.0
    duration_seconds: float = 0.0
    num_steps: int = 0
    num_edges: int = 0
    
    # Disruption impact
    disrupted_edges: int = 0
    time_impact_seconds: float = 0.0  # Delay vs baseline
    detour_distance_meters: float = 0.0
    
    # Comparison with HERE (if available)
    here_distance_meters: float = 0.0
    here_duration_seconds: float = 0.0
    frechet_distance_meters: float = 0.0
    travel_time_deviation_percent: float = 0.0
    segment_overlap_percent: float = 0.0
    
    # Quality rating
    frechet_rating: str = ""  # Excellent, Good, Fair, Poor
    ttd_rating: str = ""  # Excellent, Good, Fair, Poor
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MetricsCollector:
    """
    Comprehensive metrics collection and aggregation for experiments.
    
    Collects metrics in three phases:
    1. Construction: Initial label build time and size
    2. Update: Lazy update or rebuild time and memory
    3. Query: Query latency statistics
    
    Also tracks route quality metrics for realism evaluation.
    """
    
    def __init__(self, experiment_id: str = None):
        """
        Initialize metrics collector.
        
        Args:
            experiment_id: Unique identifier for this experiment run
        """
        self.experiment_id = experiment_id or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Metric storage
        self.construction_metrics: List[ConstructionMetrics] = []
        self.update_metrics: List[UpdateMetrics] = []
        self.query_metrics: List[QueryMetrics] = []
        self.route_quality_metrics: List[RouteQualityMetrics] = []
        
        # Per-batch query times for detailed analysis
        self._batch_query_times: Dict[str, List[float]] = defaultdict(list)
        
        # Memory tracking
        self._memory_tracking_enabled = False
        self._baseline_memory_mb = 0.0
        
        # Export directory
        self.export_dir = EXPORT_DIR / self.experiment_id
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"MetricsCollector initialized for experiment: {self.experiment_id}")
    
    # =========================================================================
    # Construction Phase
    # =========================================================================
    
    def start_construction_timing(self, algorithm: str, trial_id: int) -> Dict:
        """Start timing for construction phase."""
        return {
            "algorithm": algorithm,
            "trial_id": trial_id,
            "start_time": time.perf_counter(),
            "start_memory": self._get_current_memory_mb()
        }
    
    def end_construction_timing(self, context: Dict, 
                                 node_count: int = 0, 
                                 edge_count: int = 0,
                                 hub_count: int = 0) -> ConstructionMetrics:
        """
        End construction timing and record metrics.
        
        Args:
            context: Context from start_construction_timing
            node_count: Number of nodes in graph
            edge_count: Number of edges in graph
            hub_count: Number of hub nodes
        
        Returns:
            ConstructionMetrics object
        """
        end_time = time.perf_counter()
        end_memory = self._get_current_memory_mb()
        
        metrics = ConstructionMetrics(
            algorithm=context["algorithm"],
            trial_id=context["trial_id"],
            construction_time_ms=(end_time - context["start_time"]) * 1000,
            initial_label_size_mb=end_memory - context["start_memory"],
            node_count=node_count,
            edge_count=edge_count,
            hub_count=hub_count
        )
        
        self.construction_metrics.append(metrics)
        logger.info(f"Construction completed: {metrics.construction_time_ms:.2f}ms, "
                   f"{metrics.initial_label_size_mb:.2f}MB")
        
        return metrics
    
    # =========================================================================
    # Update Phase
    # =========================================================================
    
    def start_update_timing(self, algorithm: str, trial_id: int, batch_id: int,
                            tau_threshold: float = 0.5) -> Dict:
        """Start timing for update phase."""
        return {
            "algorithm": algorithm,
            "trial_id": trial_id,
            "batch_id": batch_id,
            "tau_threshold": tau_threshold,
            "start_time": time.perf_counter(),
            "start_memory": self._get_current_memory_mb()
        }
    
    def end_update_timing(self, context: Dict,
                          update_type: str,
                          dirty_nodes: int = 0,
                          impact_score: float = 0.0,
                          disruptions_applied: int = 0,
                          affected_edges: int = 0) -> UpdateMetrics:
        """
        End update timing and record metrics.
        
        Args:
            context: Context from start_update_timing
            update_type: "lazy" or "rebuild"
            dirty_nodes: Number of nodes marked dirty
            impact_score: Calculated impact score (0-1)
            disruptions_applied: Number of disruptions in this batch
            affected_edges: Number of edges affected
        
        Returns:
            UpdateMetrics object
        """
        end_time = time.perf_counter()
        end_memory = self._get_current_memory_mb()
        
        update_time_ms = (end_time - context["start_time"]) * 1000
        
        metrics = UpdateMetrics(
            algorithm=context["algorithm"],
            trial_id=context["trial_id"],
            batch_id=context["batch_id"],
            lazy_update_time_ms=update_time_ms if update_type == "lazy" else 0,
            threshold_rebuild_time_ms=update_time_ms if update_type == "rebuild" else 0,
            total_update_time_ms=update_time_ms,
            update_type=update_type,
            peak_label_size_mb=max(context["start_memory"], end_memory),
            label_size_before_mb=context["start_memory"],
            label_size_after_mb=end_memory,
            label_size_change_percent=((end_memory - context["start_memory"]) / 
                                        max(context["start_memory"], 0.001)) * 100,
            dirty_nodes_count=dirty_nodes,
            impact_score=impact_score,
            tau_threshold=context["tau_threshold"],
            threshold_exceeded=impact_score > context["tau_threshold"],
            disruptions_applied=disruptions_applied,
            affected_edges=affected_edges
        )
        
        self.update_metrics.append(metrics)
        logger.info(f"Update completed ({update_type}): {update_time_ms:.2f}ms, "
                   f"impact={impact_score:.3f}, dirty={dirty_nodes}")
        
        return metrics
    
    # =========================================================================
    # Query Phase
    # =========================================================================
    
    def record_query_time(self, algorithm: str, trial_id: int, batch_id: int,
                          query_time_ms: float, success: bool = True):
        """
        Record a single query execution time.
        
        Args:
            algorithm: Algorithm name
            trial_id: Trial number
            batch_id: Batch number
            query_time_ms: Query execution time in milliseconds
            success: Whether query was successful
        """
        key = f"{algorithm}_{trial_id}_{batch_id}"
        if success:
            self._batch_query_times[key].append(query_time_ms)
    
    def finalize_batch_queries(self, algorithm: str, trial_id: int, batch_id: int,
                               queries_failed: int = 0) -> QueryMetrics:
        """
        Finalize and compute aggregate query metrics for a batch.
        
        Args:
            algorithm: Algorithm name
            trial_id: Trial number
            batch_id: Batch number
            queries_failed: Number of failed queries
        
        Returns:
            QueryMetrics object with aggregate statistics
        """
        key = f"{algorithm}_{trial_id}_{batch_id}"
        times = self._batch_query_times.get(key, [])
        
        if not times:
            metrics = QueryMetrics(
                algorithm=algorithm,
                trial_id=trial_id,
                batch_id=batch_id,
                queries_processed=queries_failed,
                queries_failed=queries_failed
            )
            self.query_metrics.append(metrics)
            return metrics
        
        sorted_times = sorted(times)
        n = len(times)
        
        metrics = QueryMetrics(
            algorithm=algorithm,
            trial_id=trial_id,
            batch_id=batch_id,
            queries_processed=n + queries_failed,
            queries_successful=n,
            queries_failed=queries_failed,
            avg_query_time_ms=statistics.mean(times),
            std_dev_query_time_ms=statistics.stdev(times) if n > 1 else 0,
            min_query_time_us=min(times) * 1000,  # Convert to microseconds
            max_query_time_ms=max(times),
            p50_query_time_ms=sorted_times[n // 2],
            p90_query_time_ms=sorted_times[int(n * 0.9)],
            p95_query_time_ms=sorted_times[int(n * 0.95)],
            p99_query_time_ms=sorted_times[int(n * 0.99)] if n > 100 else sorted_times[-1],
            total_query_duration_ms=sum(times),
            queries_per_second=n / (sum(times) / 1000) if sum(times) > 0 else 0
        )
        
        self.query_metrics.append(metrics)
        
        # Clear batch data
        del self._batch_query_times[key]
        
        logger.info(f"Batch queries finalized: {n} queries, avg={metrics.avg_query_time_ms:.2f}ms, "
                   f"p95={metrics.p95_query_time_ms:.2f}ms")
        
        return metrics
    
    # =========================================================================
    # Route Quality
    # =========================================================================
    
    def record_route_quality(self, 
                             query_id: str,
                             algorithm: str,
                             trial_id: int,
                             batch_id: int,
                             distance_meters: float,
                             duration_seconds: float,
                             num_steps: int = 0,
                             num_edges: int = 0,
                             disrupted_edges: int = 0,
                             time_impact_seconds: float = 0,
                             here_distance: float = 0,
                             here_duration: float = 0,
                             frechet_distance: float = 0,
                             segment_overlap: float = 0) -> RouteQualityMetrics:
        """
        Record route quality metrics for a single query.
        
        Args:
            query_id: Unique query identifier
            algorithm: Algorithm name
            trial_id: Trial number
            batch_id: Batch number
            distance_meters: Route distance
            duration_seconds: Route duration
            num_steps: Number of turn-by-turn steps
            num_edges: Number of edges in route
            disrupted_edges: Number of disrupted edges on route
            time_impact_seconds: Time delay due to disruptions
            here_distance: HERE baseline distance (if available)
            here_duration: HERE baseline duration (if available)
            frechet_distance: Fréchet distance to HERE route
            segment_overlap: Segment overlap percentage with HERE
        
        Returns:
            RouteQualityMetrics object
        """
        # Calculate deviation and ratings
        ttd = 0.0
        if here_duration > 0:
            ttd = ((duration_seconds - here_duration) / here_duration) * 100
        
        # Fréchet distance rating
        if frechet_distance < 20:
            frechet_rating = "Excellent"
        elif frechet_distance < 50:
            frechet_rating = "Good"
        elif frechet_distance < 100:
            frechet_rating = "Fair"
        else:
            frechet_rating = "Poor"
        
        # Travel time deviation rating
        if abs(ttd) < 2:
            ttd_rating = "Excellent"
        elif abs(ttd) < 5:
            ttd_rating = "Good"
        elif abs(ttd) < 10:
            ttd_rating = "Fair"
        else:
            ttd_rating = "Poor"
        
        metrics = RouteQualityMetrics(
            query_id=query_id,
            algorithm=algorithm,
            trial_id=trial_id,
            batch_id=batch_id,
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
            num_steps=num_steps,
            num_edges=num_edges,
            disrupted_edges=disrupted_edges,
            time_impact_seconds=time_impact_seconds,
            here_distance_meters=here_distance,
            here_duration_seconds=here_duration,
            frechet_distance_meters=frechet_distance,
            travel_time_deviation_percent=ttd,
            segment_overlap_percent=segment_overlap,
            frechet_rating=frechet_rating,
            ttd_rating=ttd_rating
        )
        
        self.route_quality_metrics.append(metrics)
        return metrics
    
    # =========================================================================
    # Memory Tracking
    # =========================================================================
    
    def start_memory_tracking(self):
        """Start memory tracking using tracemalloc."""
        try:
            tracemalloc.start()
            self._memory_tracking_enabled = True
            snapshot = tracemalloc.take_snapshot()
            self._baseline_memory_mb = sum(stat.size for stat in snapshot.statistics("lineno")) / (1024 * 1024)
            logger.info(f"Memory tracking started, baseline: {self._baseline_memory_mb:.2f}MB")
        except Exception as e:
            logger.warning(f"Could not start memory tracking: {e}")
            self._memory_tracking_enabled = False
    
    def stop_memory_tracking(self):
        """Stop memory tracking."""
        if self._memory_tracking_enabled:
            tracemalloc.stop()
            self._memory_tracking_enabled = False
            logger.info("Memory tracking stopped")
    
    def _get_current_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        if self._memory_tracking_enabled:
            try:
                snapshot = tracemalloc.take_snapshot()
                total = sum(stat.size for stat in snapshot.statistics("lineno"))
                return total / (1024 * 1024)
            except Exception:
                pass
        
        # Fallback: use process memory
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0
    
    # =========================================================================
    # Aggregation & Summary
    # =========================================================================
    
    def get_algorithm_summary(self, algorithm: str) -> Dict[str, Any]:
        """
        Get aggregated summary for a specific algorithm.
        
        Args:
            algorithm: Algorithm name
        
        Returns:
            Dictionary with summary statistics
        """
        # Filter metrics by algorithm
        construction = [m for m in self.construction_metrics if m.algorithm == algorithm]
        updates = [m for m in self.update_metrics if m.algorithm == algorithm]
        queries = [m for m in self.query_metrics if m.algorithm == algorithm]
        
        summary = {
            "algorithm": algorithm,
            "trials": len(construction),
            "batches": len(updates)
        }
        
        if construction:
            summary["construction"] = {
                "avg_time_ms": statistics.mean([m.construction_time_ms for m in construction]),
                "avg_size_mb": statistics.mean([m.initial_label_size_mb for m in construction])
            }
        
        if updates:
            lazy_updates = [m for m in updates if m.update_type == "lazy"]
            rebuilds = [m for m in updates if m.update_type == "rebuild"]
            
            summary["updates"] = {
                "total": len(updates),
                "lazy_count": len(lazy_updates),
                "rebuild_count": len(rebuilds),
                "avg_update_time_ms": statistics.mean([m.total_update_time_ms for m in updates]),
                "avg_lazy_time_ms": statistics.mean([m.lazy_update_time_ms for m in lazy_updates]) if lazy_updates else 0,
                "avg_rebuild_time_ms": statistics.mean([m.threshold_rebuild_time_ms for m in rebuilds]) if rebuilds else 0,
                "avg_peak_size_mb": statistics.mean([m.peak_label_size_mb for m in updates])
            }
        
        if queries:
            all_avgs = [m.avg_query_time_ms for m in queries if m.avg_query_time_ms > 0]
            all_p95s = [m.p95_query_time_ms for m in queries if m.p95_query_time_ms > 0]
            
            summary["queries"] = {
                "total_processed": sum(m.queries_processed for m in queries),
                "total_successful": sum(m.queries_successful for m in queries),
                "avg_query_time_ms": statistics.mean(all_avgs) if all_avgs else 0,
                "avg_p95_time_ms": statistics.mean(all_p95s) if all_p95s else 0,
                "avg_queries_per_second": statistics.mean([m.queries_per_second for m in queries if m.queries_per_second > 0]) if queries else 0
            }
        
        return summary
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """
        Get comparison summary between DHL and HC2L.
        
        Returns:
            Dictionary with comparison metrics and improvement percentages
        """
        dhl_summary = self.get_algorithm_summary("DHL")
        hc2l_summary = self.get_algorithm_summary("HC2L")
        
        comparison = {
            "dhl": dhl_summary,
            "hc2l": hc2l_summary,
            "improvement": {}
        }
        
        # Calculate improvements (positive = HC2L is better)
        if "construction" in dhl_summary and "construction" in hc2l_summary:
            dhl_time = dhl_summary["construction"]["avg_time_ms"]
            hc2l_time = hc2l_summary["construction"]["avg_time_ms"]
            if dhl_time > 0:
                comparison["improvement"]["construction_time_percent"] = \
                    round(((dhl_time - hc2l_time) / dhl_time) * 100, 2)
        
        if "updates" in dhl_summary and "updates" in hc2l_summary:
            dhl_time = dhl_summary["updates"]["avg_update_time_ms"]
            hc2l_time = hc2l_summary["updates"]["avg_update_time_ms"]
            if dhl_time > 0:
                comparison["improvement"]["update_time_percent"] = \
                    round(((dhl_time - hc2l_time) / dhl_time) * 100, 2)
        
        if "queries" in dhl_summary and "queries" in hc2l_summary:
            dhl_time = dhl_summary["queries"]["avg_query_time_ms"]
            hc2l_time = hc2l_summary["queries"]["avg_query_time_ms"]
            if dhl_time > 0:
                comparison["improvement"]["query_time_percent"] = \
                    round(((dhl_time - hc2l_time) / dhl_time) * 100, 2)
        
        # Determine overall winner
        if comparison["improvement"]:
            positive_improvements = sum(1 for v in comparison["improvement"].values() if v > 0)
            comparison["improvement"]["hc2l_wins"] = positive_improvements > len(comparison["improvement"]) / 2
        
        return comparison
    
    # =========================================================================
    # Export Functions
    # =========================================================================
    
    def export_to_csv(self, include_raw: bool = True) -> Dict[str, Path]:
        """
        Export all metrics to CSV files.
        
        Args:
            include_raw: Include raw query times (can be large)
        
        Returns:
            Dictionary mapping metric type to file path
        """
        exports = {}
        
        # Export construction metrics
        if self.construction_metrics:
            path = self.export_dir / "construction_metrics.csv"
            self._export_dataclass_list(self.construction_metrics, path)
            exports["construction"] = path
        
        # Export update metrics
        if self.update_metrics:
            path = self.export_dir / "update_metrics.csv"
            self._export_dataclass_list(self.update_metrics, path)
            exports["update"] = path
        
        # Export query metrics
        if self.query_metrics:
            path = self.export_dir / "query_metrics.csv"
            self._export_dataclass_list(self.query_metrics, path)
            exports["query"] = path
        
        # Export route quality metrics
        if self.route_quality_metrics:
            path = self.export_dir / "route_quality_metrics.csv"
            self._export_dataclass_list(self.route_quality_metrics, path)
            exports["route_quality"] = path
        
        # Export unified run_metrics.csv
        path = self.export_dir / "run_metrics.csv"
        self._export_unified_metrics(path)
        exports["run_metrics"] = path
        
        # Export summary
        summary_path = self.export_dir / "summary.json"
        summary = self.get_comparison_summary()
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        exports["summary"] = summary_path
        
        logger.info(f"Exported metrics to: {self.export_dir}")
        return exports
    
    def _export_dataclass_list(self, data: List, path: Path):
        """Export a list of dataclass objects to CSV."""
        if not data:
            return
        
        fieldnames = list(asdict(data[0]).keys())
        
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in data:
                writer.writerow(asdict(item))
    
    def _export_unified_metrics(self, path: Path):
        """Export unified metrics in the format specified in IMPROVED_PROMPT.md."""
        rows = []
        
        # Add construction metrics
        for m in self.construction_metrics:
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": 0,
                "phase": "CONSTRUCTION",
                "metric_name": "labeling_time",
                "value": m.construction_time_ms,
                "unit": "ms",
                "timestamp": m.timestamp
            })
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": 0,
                "phase": "CONSTRUCTION",
                "metric_name": "label_size",
                "value": m.initial_label_size_mb,
                "unit": "MB",
                "timestamp": m.timestamp
            })
        
        # Add update metrics
        for m in self.update_metrics:
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": m.batch_id,
                "phase": "UPDATE",
                "metric_name": f"{m.update_type}_update_time",
                "value": m.total_update_time_ms,
                "unit": "ms",
                "timestamp": m.timestamp
            })
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": m.batch_id,
                "phase": "UPDATE",
                "metric_name": "peak_label_size",
                "value": m.peak_label_size_mb,
                "unit": "MB",
                "timestamp": m.timestamp
            })
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": m.batch_id,
                "phase": "UPDATE",
                "metric_name": "impact_score",
                "value": m.impact_score,
                "unit": "ratio",
                "timestamp": m.timestamp
            })
        
        # Add query metrics
        for m in self.query_metrics:
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": m.batch_id,
                "phase": "QUERY",
                "metric_name": "avg_query_time",
                "value": m.avg_query_time_ms,
                "unit": "ms",
                "timestamp": m.timestamp
            })
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": m.batch_id,
                "phase": "QUERY",
                "metric_name": "query_std_dev",
                "value": m.std_dev_query_time_ms,
                "unit": "ms",
                "timestamp": m.timestamp
            })
            rows.append({
                "trial_id": m.trial_id,
                "algorithm": m.algorithm,
                "batch_id": m.batch_id,
                "phase": "QUERY",
                "metric_name": "p95_query_time",
                "value": m.p95_query_time_ms,
                "unit": "ms",
                "timestamp": m.timestamp
            })
        
        # Write to CSV
        if rows:
            fieldnames = ["trial_id", "algorithm", "batch_id", "phase", 
                         "metric_name", "value", "unit", "timestamp"]
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
    
    def get_performance_interpretation(self, metric_name: str, value: float) -> str:
        """
        Get interpretation label for a metric value.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
        
        Returns:
            Interpretation string (Excellent, Acceptable, Poor)
        """
        thresholds = {
            "labeling_time": [(1000, "Excellent"), (1500, "Acceptable"), (float("inf"), "Poor")],
            "label_size": [(12, "Efficient"), (16, "Acceptable"), (float("inf"), "Large")],
            "avg_query_time": [(1.0, "Fast"), (2.0, "Moderate"), (float("inf"), "Slow")],
            "frechet_distance": [(20, "Excellent"), (50, "Good"), (100, "Fair"), (float("inf"), "Poor")],
            "ttd": [(2, "Excellent"), (5, "Good"), (10, "Fair"), (float("inf"), "Poor")]
        }
        
        if metric_name not in thresholds:
            return "Unknown"
        
        for threshold, label in thresholds[metric_name]:
            if value < threshold:
                return label
        
        return thresholds[metric_name][-1][1]


# Global instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get the global metrics collector instance."""
    return _metrics_collector


def init_metrics_collector(experiment_id: str = None) -> MetricsCollector:
    """Initialize a new global metrics collector."""
    global _metrics_collector
    _metrics_collector = MetricsCollector(experiment_id)
    return _metrics_collector
