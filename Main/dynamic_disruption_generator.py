#!/usr/bin/env python3
"""
Dynamic Disruption Generator
Automatically generates and updates disruption scenarios in real-time for both DHL and HC2L algorithms

Features:
- Periodic updates (configurable interval)
- Random disruption patterns (congestion, accidents, closures)
- Time-based intensity variations (rush hour simulation)
- Automatic .gr file generation for C++ routing APIs
- CSV export for analysis

Usage:
    python dynamic_disruption_generator.py --interval 30 --intensity medium
    
    Or run as background service:
    python dynamic_disruption_generator.py --daemon
"""

import sys
import time
import random
import csv
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Add Main directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config

# Disruption types and their characteristics
DISRUPTION_TYPES = {
    "light_congestion": {
        "name": "Light Traffic",
        "weight_multiplier": (1.2, 1.5),  # 20-50% slower
        "probability": 0.4,
        "impact_score": 0.15
    },
    "medium_congestion": {
        "name": "Medium Congestion",
        "weight_multiplier": (1.5, 2.0),  # 50-100% slower
        "probability": 0.3,
        "impact_score": 0.35
    },
    "heavy_jam": {
        "name": "Heavy Traffic Jam",
        "weight_multiplier": (2.0, 3.0),  # 100-200% slower
        "probability": 0.15,
        "impact_score": 0.6
    },
    "accident": {
        "name": "Accident",
        "weight_multiplier": (3.0, 5.0),  # 200-400% slower
        "probability": 0.1,
        "impact_score": 0.75
    },
    "road_closure": {
        "name": "Road Closure",
        "weight_multiplier": (999999, 999999),  # Effectively impassable
        "probability": 0.05,
        "impact_score": 1.0
    }
}

# Time-based intensity multipliers (simulate rush hour)
def get_time_intensity() -> float:
    """Get current time-based intensity multiplier (1.0 = normal, 2.0 = rush hour)"""
    hour = datetime.now().hour
    
    # Morning rush hour (7-9 AM)
    if 7 <= hour < 9:
        return 2.0
    # Evening rush hour (5-7 PM)
    elif 17 <= hour < 19:
        return 2.5
    # Late evening (9 PM - midnight)
    elif 21 <= hour < 24:
        return 0.5
    # Night (midnight - 6 AM)
    elif 0 <= hour < 6:
        return 0.3
    # Normal hours
    else:
        return 1.0


class DynamicDisruptionGenerator:
    """Generate and manage dynamic road disruptions"""
    
    def __init__(self, edges_csv: Path, output_dir: Path, intensity: str = "medium"):
        self.edges_csv = edges_csv
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load edges
        self.edges = self._load_edges()
        print(f"✅ Loaded {len(self.edges)} edges from {edges_csv}")
        
        # Set intensity
        self.intensity_multipliers = {
            "low": 0.5,
            "medium": 1.0,
            "high": 1.5,
            "extreme": 2.0
        }
        self.intensity = self.intensity_multipliers.get(intensity, 1.0)
        print(f"✅ Intensity set to: {intensity} (multiplier: {self.intensity})")
        
        self.current_disruptions = []
        self.generation_count = 0
    
    def _load_edges(self) -> List[Dict]:
        """Load edges from CSV"""
        edges = []
        with open(self.edges_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    edges.append({
                        'source': int(row['source']),
                        'target': int(row['target']),
                        'length': float(row['length']),
                        'name': row.get('name', 'Unknown Road'),
                        'highway': row.get('highway', 'road'),
                        'oneway': int(row.get('oneway', 0))
                    })
                except (ValueError, KeyError) as e:
                    print(f"⚠️  Skipping invalid edge: {e}")
        return edges
    
    def generate_disruptions(self) -> List[Dict]:
        """Generate random disruptions based on current time and intensity"""
        time_multiplier = get_time_intensity()
        effective_intensity = self.intensity * time_multiplier
        
        # Number of disruptions based on intensity
        num_disruptions = int(random.randint(3, 10) * effective_intensity)
        num_disruptions = min(num_disruptions, len(self.edges) // 10)  # Max 10% of edges
        
        disruptions = []
        selected_edges = random.sample(self.edges, num_disruptions)
        
        for edge in selected_edges:
            # Select disruption type
            disruption_type = self._select_disruption_type(effective_intensity)
            type_info = DISRUPTION_TYPES[disruption_type]
            
            # Calculate new weight
            multiplier = random.uniform(*type_info['weight_multiplier'])
            new_weight = int(edge['length'] * multiplier)
            
            disruption = {
                'source': edge['source'],
                'target': edge['target'],
                'original_weight': int(edge['length']),
                'new_weight': new_weight,
                'type': disruption_type,
                'type_name': type_info['name'],
                'road_name': edge['name'],
                'highway': edge['highway'],
                'impact_score': type_info['impact_score'],
                'timestamp': datetime.now().isoformat()
            }
            disruptions.append(disruption)
        
        self.current_disruptions = disruptions
        self.generation_count += 1
        
        print(f"\n🚦 Generated {len(disruptions)} disruptions (Time intensity: {time_multiplier:.1f}x, Effective: {effective_intensity:.1f}x)")
        return disruptions
    
    def _select_disruption_type(self, intensity: float) -> str:
        """Select disruption type based on weighted probabilities and intensity"""
        # Adjust probabilities based on intensity
        adjusted_probs = {}
        for dtype, info in DISRUPTION_TYPES.items():
            base_prob = info['probability']
            # Higher intensity increases probability of severe disruptions
            if info['impact_score'] > 0.5:
                adjusted_probs[dtype] = base_prob * (1 + intensity * 0.3)
            else:
                adjusted_probs[dtype] = base_prob
        
        # Normalize probabilities
        total = sum(adjusted_probs.values())
        normalized = {k: v/total for k, v in adjusted_probs.items()}
        
        # Random selection
        rand = random.random()
        cumulative = 0
        for dtype, prob in normalized.items():
            cumulative += prob
            if rand <= cumulative:
                return dtype
        
        return "light_congestion"  # Fallback
    
    def export_to_gr_file(self, output_path: Path) -> None:
        """Export disruptions to .gr format for C++ routing APIs"""
        if not self.current_disruptions:
            print("⚠️  No disruptions to export")
            return
        
        # Count nodes and edges
        num_nodes = max(
            max(d['source'] for d in self.current_disruptions),
            max(d['target'] for d in self.current_disruptions)
        ) + 100  # Add buffer
        
        num_edges = len(self.current_disruptions)
        
        with open(output_path, 'w') as f:
            # Write header
            f.write(f"c Dynamic disruption scenario - Generated at {datetime.now()}\n")
            f.write(f"c Total disruptions: {num_edges}\n")
            f.write(f"c Generation count: {self.generation_count}\n")
            f.write(f"p sp {num_nodes} {num_edges}\n")
            
            # Write disruptions (edges with new weights)
            for d in self.current_disruptions:
                f.write(f"{d['source']} {d['target']} {d['new_weight']}\n")
        
        print(f"✅ Exported {num_edges} disruptions to {output_path}")
    
    def export_to_csv(self, output_path: Path) -> None:
        """Export disruptions to CSV for analysis"""
        if not self.current_disruptions:
            print("⚠️  No disruptions to export")
            return
        
        fieldnames = ['source', 'target', 'original_weight', 'new_weight', 'type', 
                     'type_name', 'road_name', 'highway', 'impact_score', 'timestamp']
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.current_disruptions)
        
        print(f"✅ Exported disruption details to {output_path}")
    
    def print_summary(self) -> None:
        """Print summary of current disruptions"""
        if not self.current_disruptions:
            return
        
        print("\n📊 Disruption Summary:")
        type_counts = {}
        for d in self.current_disruptions:
            type_name = d['type_name']
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        for type_name, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"   {type_name}: {count}")
        
        avg_impact = sum(d['impact_score'] for d in self.current_disruptions) / len(self.current_disruptions)
        print(f"   Average Impact: {avg_impact:.2f}")


def run_continuous_generation(interval: int = 60, intensity: str = "medium"):
    """Run continuous disruption generation with periodic updates"""
    edges_csv = Config.RAW_DATA_DIR / "quezon_city_edges.csv"
    output_dir = Config.DISRUPTIONS_DIR
    
    if not edges_csv.exists():
        print(f"❌ Edges CSV not found: {edges_csv}")
        return
    
    generator = DynamicDisruptionGenerator(edges_csv, output_dir, intensity)
    
    print("=" * 80)
    print("🔄 Dynamic Disruption Generator - Continuous Mode")
    print("=" * 80)
    print(f"Update Interval: {interval} seconds")
    print(f"Intensity: {intensity}")
    print(f"Output Directory: {output_dir}")
    print("\nPress Ctrl+C to stop\n")
    print("=" * 80)
    
    try:
        iteration = 0
        while True:
            iteration += 1
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"\n[{current_time}] Iteration #{iteration}")
            
            # Generate new disruptions
            disruptions = generator.generate_disruptions()
            
            # Export to .gr files (one for each algorithm)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            gr_file = output_dir / "dynamic_disruptions_current.gr"
            csv_file = output_dir / f"dynamic_disruptions_{timestamp}.csv"
            
            generator.export_to_gr_file(gr_file)
            generator.export_to_csv(csv_file)
            generator.print_summary()
            
            # Create symlinks for both algorithms
            for algo in ['hc2l', 'dhl']:
                algo_gr = output_dir / f"dynamic_disruptions_{algo}.gr"
                if algo_gr.exists():
                    algo_gr.unlink()
                algo_gr.write_text(gr_file.read_text())
                print(f"✅ Updated {algo} disruption file: {algo_gr}")
            
            print(f"\n⏳ Next update in {interval} seconds...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping disruption generator...")
        print(f"Total iterations: {iteration}")
        print("=" * 80)


def run_single_generation(intensity: str = "medium"):
    """Generate disruptions once and exit"""
    edges_csv = Config.RAW_DATA_DIR / "quezon_city_edges.csv"
    output_dir = Config.DISRUPTIONS_DIR
    
    if not edges_csv.exists():
        print(f"❌ Edges CSV not found: {edges_csv}")
        return
    
    generator = DynamicDisruptionGenerator(edges_csv, output_dir, intensity)
    
    print("=" * 80)
    print("🔄 Dynamic Disruption Generator - Single Generation")
    print("=" * 80)
    
    # Generate disruptions
    disruptions = generator.generate_disruptions()
    
    # Export files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    gr_file = output_dir / "dynamic_disruptions_current.gr"
    csv_file = output_dir / f"dynamic_disruptions_{timestamp}.csv"
    
    generator.export_to_gr_file(gr_file)
    generator.export_to_csv(csv_file)
    generator.print_summary()
    
    # Create files for both algorithms
    for algo in ['hc2l', 'dhl']:
        algo_gr = output_dir / f"dynamic_disruptions_{algo}.gr"
        algo_gr.write_text(gr_file.read_text())
        print(f"✅ Created {algo} disruption file: {algo_gr}")
    
    print("\n✅ Single generation complete")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dynamic Disruption Generator for Road Networks")
    parser.add_argument('--interval', type=int, default=60, 
                       help='Update interval in seconds (default: 60)')
    parser.add_argument('--intensity', choices=['low', 'medium', 'high', 'extreme'], 
                       default='medium', help='Disruption intensity level (default: medium)')
    parser.add_argument('--once', action='store_true', 
                       help='Generate once and exit (default: continuous mode)')
    
    args = parser.parse_args()
    
    if args.once:
        run_single_generation(args.intensity)
    else:
        run_continuous_generation(args.interval, args.intensity)
