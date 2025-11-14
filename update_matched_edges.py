#!/usr/bin/env python3
"""
Update matched_edges.csv to use Sequential IDs
================================================

This script converts the matched_edges.csv file from using OSM IDs
to using Sequential IDs, making it compatible with the C++ routing algorithms.

The original matched_edges.csv uses OSM IDs (e.g., 12067461, 5352181469).
The updated version will use Sequential IDs (1, 2, 3, ...) that match
the node_id column in quezon_city_nodes.csv.

Usage:
    python update_matched_edges.py
"""

import sys
import pandas as pd
from pathlib import Path

# Add Main directory to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))

from config import Config


def load_osm_to_seq_mapping(edges_csv: Path) -> dict:
    """Load OSM ID to Sequential ID mapping from edges CSV"""
    print(f"📂 Loading OSM->Sequential ID mapping from {edges_csv}...")
    
    osm_to_seq = {}
    
    if not edges_csv.exists():
        print(f"❌ Error: {edges_csv} not found")
        print("   Please run: python osm_graph_generator.py first")
        return osm_to_seq
    
    df = pd.read_csv(edges_csv)
    
    # Check if required columns exist
    required_cols = ['osm_source', 'osm_target', 'source', 'target']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        print(f"❌ Error: Missing columns in {edges_csv}: {missing_cols}")
        print("   Please regenerate the OSM graph with updated osm_graph_generator.py")
        return osm_to_seq
    
    # Extract mappings
    for _, row in df.iterrows():
        osm_source = int(row['osm_source'])
        seq_source = int(row['source'])
        osm_to_seq[osm_source] = seq_source
        
        osm_target = int(row['osm_target'])
        seq_target = int(row['target'])
        osm_to_seq[osm_target] = seq_target
    
    print(f"   ✅ Loaded {len(osm_to_seq)} OSM->Sequential ID mappings")
    return osm_to_seq


def update_matched_edges(matched_edges_csv: Path, osm_to_seq: dict) -> bool:
    """Update matched_edges.csv to use sequential IDs"""
    print(f"\n📝 Updating {matched_edges_csv}...")
    
    if not matched_edges_csv.exists():
        print(f"❌ Error: {matched_edges_csv} not found")
        return False
    
    # Read original file
    df = pd.read_csv(matched_edges_csv)
    print(f"   📊 Original: {len(df)} edges")
    
    # Convert OSM IDs to Sequential IDs
    mapped_count = 0
    unmapped_count = 0
    
    new_sources = []
    new_targets = []
    
    for _, row in df.iterrows():
        osm_source = int(row['source'])
        osm_target = int(row['target'])
        
        if osm_source in osm_to_seq and osm_target in osm_to_seq:
            new_sources.append(osm_to_seq[osm_source])
            new_targets.append(osm_to_seq[osm_target])
            mapped_count += 1
        else:
            # Keep original if mapping not found (will cause issues later)
            new_sources.append(osm_source)
            new_targets.append(osm_target)
            unmapped_count += 1
            if unmapped_count <= 5:
                print(f"   ⚠️  Warning: Could not map OSM IDs {osm_source}->{osm_target}")
    
    # Update DataFrame
    df['source'] = new_sources
    df['target'] = new_targets
    
    # Create backup of original
    backup_path = matched_edges_csv.with_suffix('.csv.backup')
    if not backup_path.exists():
        print(f"   💾 Creating backup: {backup_path}")
        import shutil
        shutil.copy2(matched_edges_csv, backup_path)
    
    # Save updated file
    df.to_csv(matched_edges_csv, index=False)
    
    print(f"   ✅ Updated: {mapped_count} edges mapped, {unmapped_count} unmapped")
    print(f"   💾 Saved: {matched_edges_csv}")
    
    # Show sample
    print(f"\n   📋 Sample of updated data:")
    print(df[['id_hash', 'source', 'target', 'source_lat', 'source_lon']].head(3).to_string(index=False))
    
    return True


def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("Update matched_edges.csv to use Sequential IDs")
    print("="*70 + "\n")
    
    # Paths
    edges_csv = Config.EDGES_CSV
    matched_edges_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
    
    print(f"Input files:")
    print(f"  📄 OSM Edges: {edges_csv}")
    print(f"  📄 Matched Edges: {matched_edges_csv}")
    print()
    
    # Step 1: Load OSM->Sequential ID mapping
    osm_to_seq = load_osm_to_seq_mapping(edges_csv)
    
    if not osm_to_seq:
        print("\n❌ Failed to load OSM->Sequential ID mapping")
        print("\nPlease ensure:")
        print("  1. Run: python osm_graph_generator.py")
        print("  2. Check that quezon_city_edges.csv has both osm_source/osm_target and source/target columns")
        return 1
    
    # Step 2: Update matched_edges.csv
    success = update_matched_edges(matched_edges_csv, osm_to_seq)
    
    if success:
        print("\n" + "="*70)
        print("✅ SUCCESS!")
        print("="*70)
        print()
        print("matched_edges.csv has been updated to use Sequential IDs.")
        print("The traffic matching system will now use IDs compatible with C++ routing.")
        print()
        print("Next steps:")
        print("  1. Run: python unified_data_generator.py --mode both")
        print("  2. Verify that traffic .gr files use sequential IDs (1, 2, 3...)")
        print()
    else:
        print("\n❌ Failed to update matched_edges.csv")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
