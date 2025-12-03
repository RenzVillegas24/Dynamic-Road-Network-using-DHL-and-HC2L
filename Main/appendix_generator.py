"""
Appendix Table Generator for DHL vs HC2L Benchmarking

This module auto-generates the appendix tables specified in IMPROVED_PROMPT.md:
- Appendix 1.1: Initial Construction Performance
- Appendix 1.2: Dynamic Performance Log (per batch per trial)
- Appendix 1.3: Algorithm Comparison Summary
- Appendix 1.4: Route Similarity Evaluation (vs HERE Maps)

Tables can be exported to CSV, Markdown, and formatted for display.
"""

import csv
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import logging

from metrics_collector import (
    MetricsCollector,
    ConstructionMetrics,
    UpdateMetrics,
    QueryMetrics,
    RouteQualityMetrics
)

# Configure logger
logger = logging.getLogger(__name__)


@dataclass
class AppendixConfig:
    """Configuration for appendix generation."""
    experiment_id: str
    output_dir: Path
    include_markdown: bool = True
    include_csv: bool = True
    include_json: bool = True


class AppendixGenerator:
    """
    Generates formatted appendix tables from collected metrics.
    
    Supports multiple output formats:
    - CSV: For data analysis and spreadsheet import
    - Markdown: For documentation and reports
    - JSON: For programmatic access
    """
    
    def __init__(self, metrics_collector: MetricsCollector, output_dir: Path = None):
        """
        Initialize appendix generator.
        
        Args:
            metrics_collector: MetricsCollector with experiment data
            output_dir: Directory for output files
        """
        self.collector = metrics_collector
        self.output_dir = output_dir or (Path(__file__).parent / "data" / "experiment_results" / 
                                          metrics_collector.experiment_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"AppendixGenerator initialized for: {metrics_collector.experiment_id}")
    
    # =========================================================================
    # Appendix 1.1: Initial Construction Performance
    # =========================================================================
    
    def generate_appendix_1_1(self) -> Dict[str, Any]:
        """
        Generate Appendix 1.1: Initial Construction Performance
        
        Table Structure: 3 trials × 2 algorithms
        Shows construction time per trial with averages and improvement %
        
        Returns:
            Dictionary with table data and statistics
        """
        construction = self.collector.construction_metrics
        
        # Group by algorithm
        by_algo = {}
        for m in construction:
            if m.algorithm not in by_algo:
                by_algo[m.algorithm] = {}
            by_algo[m.algorithm][m.trial_id] = m.construction_time_ms
        
        # Build table data
        table_data = {
            "title": "Appendix 1.1: Initial Construction Performance",
            "description": "Construction time (ms) per trial per algorithm",
            "headers": ["Algorithm"] + [f"Trial {i+1} (ms)" for i in range(max(3, len(construction) // 2))] + ["Average", "Std Dev"],
            "rows": [],
            "summary": {}
        }
        
        algo_averages = {}
        
        for algo in sorted(by_algo.keys()):
            trials = by_algo[algo]
            times = list(trials.values())
            
            avg = statistics.mean(times) if times else 0
            std = statistics.stdev(times) if len(times) > 1 else 0
            algo_averages[algo] = avg
            
            row = [algo]
            for trial_id in sorted(trials.keys()):
                row.append(f"{trials[trial_id]:.1f}")
            row.extend([f"{avg:.1f}", f"{std:.1f}"])
            
            table_data["rows"].append(row)
        
        # Calculate improvement (DHL vs HC2L)
        if "DHL" in algo_averages and "HC2L" in algo_averages:
            dhl_avg = algo_averages["DHL"]
            hc2l_avg = algo_averages["HC2L"]
            improvement = ((dhl_avg - hc2l_avg) / dhl_avg) * 100 if dhl_avg > 0 else 0
            
            table_data["summary"] = {
                "dhl_average_ms": round(dhl_avg, 1),
                "hc2l_average_ms": round(hc2l_avg, 1),
                "improvement_percent": round(improvement, 1),
                "improvement_favorable": improvement > 0,
                "note": f"HC2L is {'faster' if improvement > 0 else 'slower'} by {abs(improvement):.1f}%"
            }
        
        # Export
        self._export_table(table_data, "appendix_1_1_construction_performance")
        
        return table_data
    
    # =========================================================================
    # Appendix 1.2: Dynamic Performance Log
    # =========================================================================
    
    def generate_appendix_1_2(self) -> Dict[str, Any]:
        """
        Generate Appendix 1.2: Dynamic Performance Log
        
        Table Structure: Detailed metrics per batch per trial
        Includes update time, peak memory, query stats
        
        Returns:
            Dictionary with table data
        """
        updates = self.collector.update_metrics
        queries = self.collector.query_metrics
        
        # Create lookup for query metrics
        query_lookup = {}
        for q in queries:
            key = (q.algorithm, q.trial_id, q.batch_id)
            query_lookup[key] = q
        
        table_data = {
            "title": "Appendix 1.2: Dynamic Performance Log",
            "description": "Detailed metrics per batch per trial",
            "headers": [
                "Trial/Batch", "Algorithm", "Update (ms)", "Update Type",
                "Peak (MB)", "Avg Query (ms)", "Std Dev (ms)", "P95 (ms)"
            ],
            "rows": [],
            "summary": {}
        }
        
        for m in sorted(updates, key=lambda x: (x.trial_id, x.batch_id, x.algorithm)):
            # Get corresponding query metrics
            key = (m.algorithm, m.trial_id, m.batch_id)
            q = query_lookup.get(key)
            
            row = [
                f"T{m.trial_id} B{m.batch_id}",
                m.algorithm,
                f"{m.total_update_time_ms:.1f}",
                m.update_type.capitalize(),
                f"{m.peak_label_size_mb:.1f}",
                f"{q.avg_query_time_ms:.2f}" if q else "N/A",
                f"{q.std_dev_query_time_ms:.2f}" if q else "N/A",
                f"{q.p95_query_time_ms:.2f}" if q else "N/A"
            ]
            
            table_data["rows"].append(row)
        
        # Calculate summary statistics
        if updates:
            lazy_count = sum(1 for m in updates if m.update_type == "lazy")
            rebuild_count = sum(1 for m in updates if m.update_type == "rebuild")
            
            table_data["summary"] = {
                "total_batches": len(updates),
                "lazy_updates": lazy_count,
                "threshold_rebuilds": rebuild_count,
                "avg_update_time_ms": round(statistics.mean([m.total_update_time_ms for m in updates]), 1),
                "avg_peak_size_mb": round(statistics.mean([m.peak_label_size_mb for m in updates]), 1)
            }
        
        # Export
        self._export_table(table_data, "appendix_1_2_dynamic_performance_log")
        
        return table_data
    
    # =========================================================================
    # Appendix 1.3: Algorithm Comparison Summary
    # =========================================================================
    
    def generate_appendix_1_3(self) -> Dict[str, Any]:
        """
        Generate Appendix 1.3: Algorithm Comparison Summary
        
        Key Performance Indicators & Improvement %
        
        Returns:
            Dictionary with comparison table data
        """
        # Get summaries for each algorithm
        dhl_summary = self.collector.get_algorithm_summary("DHL")
        hc2l_summary = self.collector.get_algorithm_summary("HC2L")
        
        table_data = {
            "title": "Appendix 1.3: Algorithm Comparison Summary",
            "description": "Key Performance Indicators with improvement percentages",
            "headers": ["Metric", "DHL", "HC2L", "Improvement", "Rating"],
            "rows": [],
            "summary": {},
            "interpretation_guide": {
                "labeling_time": {"excellent": "< 1000 ms", "acceptable": "1000-1500 ms", "poor": "> 1500 ms"},
                "label_size": {"efficient": "< 12 MB", "acceptable": "12-16 MB", "large": "> 16 MB"},
                "query_time": {"fast": "< 1.0 ms", "moderate": "1.0-2.0 ms", "slow": "> 2.0 ms"}
            }
        }
        
        metrics_to_compare = []
        
        # Construction metrics
        if "construction" in dhl_summary and "construction" in hc2l_summary:
            dhl_val = dhl_summary["construction"]["avg_time_ms"]
            hc2l_val = hc2l_summary["construction"]["avg_time_ms"]
            improvement = ((dhl_val - hc2l_val) / dhl_val * 100) if dhl_val > 0 else 0
            rating = self._get_improvement_rating(improvement)
            
            metrics_to_compare.append({
                "metric": "Labeling Time (avg, ms)",
                "dhl": f"{dhl_val:.1f}",
                "hc2l": f"{hc2l_val:.1f}",
                "improvement": f"{improvement:+.1f}%",
                "rating": rating
            })
            
            dhl_size = dhl_summary["construction"]["avg_size_mb"]
            hc2l_size = hc2l_summary["construction"]["avg_size_mb"]
            size_improvement = ((dhl_size - hc2l_size) / dhl_size * 100) if dhl_size > 0 else 0
            
            metrics_to_compare.append({
                "metric": "Label Size (avg, MB)",
                "dhl": f"{dhl_size:.1f}",
                "hc2l": f"{hc2l_size:.1f}",
                "improvement": f"{size_improvement:+.1f}%",
                "rating": self._get_improvement_rating(size_improvement)
            })
        
        # Update metrics
        if "updates" in dhl_summary and "updates" in hc2l_summary:
            dhl_update = dhl_summary["updates"]["avg_update_time_ms"]
            hc2l_update = hc2l_summary["updates"]["avg_update_time_ms"]
            update_improvement = ((dhl_update - hc2l_update) / dhl_update * 100) if dhl_update > 0 else 0
            
            metrics_to_compare.append({
                "metric": "Update Time (avg, ms)",
                "dhl": f"{dhl_update:.1f}",
                "hc2l": f"{hc2l_update:.1f}",
                "improvement": f"{update_improvement:+.1f}%",
                "rating": self._get_improvement_rating(update_improvement)
            })
            
            # Add lazy update time for HC2L only
            hc2l_lazy = hc2l_summary["updates"].get("avg_lazy_time_ms", 0)
            if hc2l_lazy > 0:
                metrics_to_compare.append({
                    "metric": "Lazy Update Time (ms)",
                    "dhl": "N/A",
                    "hc2l": f"{hc2l_lazy:.1f}",
                    "improvement": "HC2L Only",
                    "rating": "✅"
                })
            
            # Rebuild counts
            hc2l_rebuilds = hc2l_summary["updates"].get("rebuild_count", 0)
            hc2l_total = hc2l_summary["updates"].get("total", 1)
            metrics_to_compare.append({
                "metric": "Threshold Rebuilds",
                "dhl": "N/A",
                "hc2l": f"{hc2l_rebuilds} of {hc2l_total}",
                "improvement": "HC2L Only",
                "rating": "✅" if hc2l_rebuilds < hc2l_total / 2 else "⚠️"
            })
        
        # Query metrics
        if "queries" in dhl_summary and "queries" in hc2l_summary:
            dhl_query = dhl_summary["queries"]["avg_query_time_ms"]
            hc2l_query = hc2l_summary["queries"]["avg_query_time_ms"]
            query_improvement = ((dhl_query - hc2l_query) / dhl_query * 100) if dhl_query > 0 else 0
            
            metrics_to_compare.append({
                "metric": "Query Time (avg, ms)",
                "dhl": f"{dhl_query:.2f}",
                "hc2l": f"{hc2l_query:.2f}",
                "improvement": f"{query_improvement:+.1f}%",
                "rating": self._get_improvement_rating(query_improvement)
            })
            
            dhl_p95 = dhl_summary["queries"]["avg_p95_time_ms"]
            hc2l_p95 = hc2l_summary["queries"]["avg_p95_time_ms"]
            p95_improvement = ((dhl_p95 - hc2l_p95) / dhl_p95 * 100) if dhl_p95 > 0 else 0
            
            metrics_to_compare.append({
                "metric": "P95 Query Time (avg, ms)",
                "dhl": f"{dhl_p95:.2f}",
                "hc2l": f"{hc2l_p95:.2f}",
                "improvement": f"{p95_improvement:+.1f}%",
                "rating": self._get_improvement_rating(p95_improvement)
            })
        
        # Build rows
        for m in metrics_to_compare:
            table_data["rows"].append([
                m["metric"], m["dhl"], m["hc2l"], m["improvement"], m["rating"]
            ])
        
        # Overall summary
        positive_improvements = sum(1 for m in metrics_to_compare 
                                   if "+" in m["improvement"] and m["improvement"] != "HC2L Only")
        total_compared = sum(1 for m in metrics_to_compare if m["improvement"] not in ["HC2L Only", "N/A"])
        
        table_data["summary"] = {
            "positive_improvements": positive_improvements,
            "total_metrics": total_compared,
            "hc2l_favorable": positive_improvements > total_compared / 2,
            "conclusion": "HC2L outperforms DHL" if positive_improvements > total_compared / 2 else "DHL outperforms HC2L"
        }
        
        # Export
        self._export_table(table_data, "appendix_1_3_algorithm_summary")
        
        return table_data
    
    def _get_improvement_rating(self, improvement: float) -> str:
        """Get rating symbol based on improvement percentage."""
        if improvement > 5:
            return "✅ Excellent"
        elif improvement > 0:
            return "✅ Good"
        elif improvement > -5:
            return "⚠️ Similar"
        else:
            return "❌ Worse"
    
    # =========================================================================
    # Appendix 1.4: Route Similarity Evaluation
    # =========================================================================
    
    def generate_appendix_1_4(self, sample_size: int = 50) -> Dict[str, Any]:
        """
        Generate Appendix 1.4: Route Similarity Evaluation (vs HERE Maps)
        
        Evaluates route realism using Fréchet distance and travel time deviation
        
        Args:
            sample_size: Number of sample routes to include (from last batch)
        
        Returns:
            Dictionary with route similarity table data
        """
        quality_metrics = self.collector.route_quality_metrics
        
        table_data = {
            "title": "Appendix 1.4: Route Similarity Evaluation (vs HERE Maps)",
            "description": "Route quality metrics compared to HERE baseline",
            "headers": [
                "Trial/Query", "Distance (m)", "Fréchet (m)", "TTD (%)", "Rating"
            ],
            "rows": [],
            "summary": {},
            "rating_guide": {
                "frechet": {"excellent": "< 20m", "good": "20-50m", "fair": "50-100m", "poor": "> 100m"},
                "ttd": {"excellent": "±2%", "good": "±5%", "fair": "±10%", "poor": "> ±10%"}
            }
        }
        
        # Take sample from end of experiment
        sample = quality_metrics[-sample_size:] if len(quality_metrics) > sample_size else quality_metrics
        
        frechet_values = []
        ttd_values = []
        
        for m in sample:
            row = [
                f"T{m.trial_id} #{m.query_id[:8]}",
                f"{m.distance_meters:.0f}",
                f"{m.frechet_distance_meters:.1f}" if m.frechet_distance_meters > 0 else "N/A",
                f"{m.travel_time_deviation_percent:+.1f}%" if m.here_duration_seconds > 0 else "N/A",
                f"{m.frechet_rating} / {m.ttd_rating}" if m.frechet_rating else "N/A"
            ]
            
            table_data["rows"].append(row)
            
            if m.frechet_distance_meters > 0:
                frechet_values.append(m.frechet_distance_meters)
            if m.here_duration_seconds > 0:
                ttd_values.append(abs(m.travel_time_deviation_percent))
        
        # Summary statistics
        if frechet_values:
            avg_frechet = statistics.mean(frechet_values)
            avg_ttd = statistics.mean(ttd_values) if ttd_values else 0
            
            # Determine overall ratings
            if avg_frechet < 20:
                frechet_rating = "Excellent"
            elif avg_frechet < 50:
                frechet_rating = "Good"
            elif avg_frechet < 100:
                frechet_rating = "Fair"
            else:
                frechet_rating = "Poor"
            
            if avg_ttd < 2:
                ttd_rating = "Excellent"
            elif avg_ttd < 5:
                ttd_rating = "Good"
            elif avg_ttd < 10:
                ttd_rating = "Fair"
            else:
                ttd_rating = "Poor"
            
            table_data["summary"] = {
                "sample_size": len(sample),
                "avg_distance_m": round(statistics.mean([m.distance_meters for m in sample]), 0),
                "avg_frechet_m": round(avg_frechet, 1),
                "avg_ttd_percent": round(avg_ttd, 1),
                "frechet_rating": frechet_rating,
                "ttd_rating": ttd_rating,
                "overall_quality": frechet_rating if frechet_rating == ttd_rating else f"{frechet_rating}/{ttd_rating}"
            }
        else:
            table_data["summary"] = {
                "sample_size": len(sample),
                "note": "No HERE comparison data available"
            }
        
        # Export
        self._export_table(table_data, "appendix_1_4_route_similarity")
        
        return table_data
    
    # =========================================================================
    # Combined Generation & Export
    # =========================================================================
    
    def generate_all_appendices(self) -> Dict[str, Any]:
        """
        Generate all appendix tables.
        
        Returns:
            Dictionary with all appendix data
        """
        results = {
            "experiment_id": self.collector.experiment_id,
            "generated_at": datetime.now().isoformat(),
            "appendices": {}
        }
        
        try:
            results["appendices"]["1.1"] = self.generate_appendix_1_1()
        except Exception as e:
            logger.error(f"Error generating Appendix 1.1: {e}")
            results["appendices"]["1.1"] = {"error": str(e)}
        
        try:
            results["appendices"]["1.2"] = self.generate_appendix_1_2()
        except Exception as e:
            logger.error(f"Error generating Appendix 1.2: {e}")
            results["appendices"]["1.2"] = {"error": str(e)}
        
        try:
            results["appendices"]["1.3"] = self.generate_appendix_1_3()
        except Exception as e:
            logger.error(f"Error generating Appendix 1.3: {e}")
            results["appendices"]["1.3"] = {"error": str(e)}
        
        try:
            results["appendices"]["1.4"] = self.generate_appendix_1_4()
        except Exception as e:
            logger.error(f"Error generating Appendix 1.4: {e}")
            results["appendices"]["1.4"] = {"error": str(e)}
        
        # Export combined JSON
        combined_path = self.output_dir / "all_appendices.json"
        with open(combined_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Generated all appendices to: {self.output_dir}")
        
        return results
    
    # =========================================================================
    # Export Helpers
    # =========================================================================
    
    def _export_table(self, table_data: Dict, filename: str):
        """
        Export table data to multiple formats.
        
        Args:
            table_data: Dictionary with table structure
            filename: Base filename (without extension)
        """
        # CSV export
        csv_path = self.output_dir / f"{filename}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(table_data["headers"])
            writer.writerows(table_data["rows"])
        
        # Markdown export
        md_path = self.output_dir / f"{filename}.md"
        self._write_markdown_table(table_data, md_path)
        
        # JSON export
        json_path = self.output_dir / f"{filename}.json"
        with open(json_path, "w") as f:
            json.dump(table_data, f, indent=2, default=str)
        
        logger.debug(f"Exported table: {filename}")
    
    def _write_markdown_table(self, table_data: Dict, path: Path):
        """Write table data as Markdown format."""
        with open(path, "w") as f:
            # Title
            f.write(f"# {table_data['title']}\n\n")
            
            if table_data.get("description"):
                f.write(f"*{table_data['description']}*\n\n")
            
            # Table header
            headers = table_data["headers"]
            f.write("| " + " | ".join(headers) + " |\n")
            f.write("|" + "|".join(["---"] * len(headers)) + "|\n")
            
            # Table rows
            for row in table_data["rows"]:
                f.write("| " + " | ".join(str(cell) for cell in row) + " |\n")
            
            f.write("\n")
            
            # Summary
            if table_data.get("summary"):
                f.write("## Summary\n\n")
                for key, value in table_data["summary"].items():
                    f.write(f"- **{key.replace('_', ' ').title()}:** {value}\n")
            
            # Rating guide
            if table_data.get("rating_guide") or table_data.get("interpretation_guide"):
                guide = table_data.get("rating_guide") or table_data.get("interpretation_guide")
                f.write("\n## Interpretation Guide\n\n")
                for metric, ratings in guide.items():
                    f.write(f"**{metric.replace('_', ' ').title()}:**\n")
                    for rating, threshold in ratings.items():
                        f.write(f"- {rating.title()}: {threshold}\n")
    
    def get_formatted_summary(self) -> str:
        """
        Get a formatted text summary of all appendices.
        
        Returns:
            Formatted string for console/log output
        """
        comparison = self.collector.get_comparison_summary()
        
        lines = [
            "=" * 60,
            "EXPERIMENT RESULTS SUMMARY",
            "=" * 60,
            ""
        ]
        
        # DHL Summary
        if "dhl" in comparison:
            dhl = comparison["dhl"]
            lines.extend([
                "DHL Algorithm:",
                f"  - Trials: {dhl.get('trials', 'N/A')}",
                f"  - Batches: {dhl.get('batches', 'N/A')}"
            ])
            if "construction" in dhl:
                lines.append(f"  - Avg Construction: {dhl['construction']['avg_time_ms']:.1f}ms")
            if "queries" in dhl:
                lines.append(f"  - Avg Query Time: {dhl['queries']['avg_query_time_ms']:.2f}ms")
            lines.append("")
        
        # HC2L Summary
        if "hc2l" in comparison:
            hc2l = comparison["hc2l"]
            lines.extend([
                "HC2L Algorithm:",
                f"  - Trials: {hc2l.get('trials', 'N/A')}",
                f"  - Batches: {hc2l.get('batches', 'N/A')}"
            ])
            if "construction" in hc2l:
                lines.append(f"  - Avg Construction: {hc2l['construction']['avg_time_ms']:.1f}ms")
            if "queries" in hc2l:
                lines.append(f"  - Avg Query Time: {hc2l['queries']['avg_query_time_ms']:.2f}ms")
            if "updates" in hc2l:
                lines.append(f"  - Lazy Updates: {hc2l['updates']['lazy_count']}")
                lines.append(f"  - Rebuilds: {hc2l['updates']['rebuild_count']}")
            lines.append("")
        
        # Improvement Summary
        if "improvement" in comparison:
            imp = comparison["improvement"]
            lines.extend([
                "IMPROVEMENT (HC2L vs DHL):",
                f"  - Query Time: {imp.get('query_time_percent', 0):+.1f}%",
                f"  - Update Time: {imp.get('update_time_percent', 0):+.1f}%",
                f"  - Winner: {'HC2L' if imp.get('hc2l_wins') else 'DHL'}",
                ""
            ])
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Factory function
def create_appendix_generator(metrics_collector: MetricsCollector, 
                              output_dir: Path = None) -> AppendixGenerator:
    """Create an appendix generator instance."""
    return AppendixGenerator(metrics_collector, output_dir)
