#!/usr/bin/env python3
"""
Enrich matched_edges.csv with road_name and highway_type
============================================================

This script adds road_name and highway_type columns directly to matched_edges.csv
to ensure all edges have road information, eliminating lookup failures.

This is a CRITICAL FIX because:
1. Some edges in matched_edges.csv don't have matches in quezon_city_edges.csv
2. Direct columns eliminate lookup overhead
3. Ensures 100% of flow/incident data has road info

Usage:
    python enrich_matched_edges.py
"""

import sys
import pandas as pd
from pathlib import Path

# Add Main directory to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))

from config import Config
from console_formatter import get_logger

# Initialize logger
logger = get_logger("EnrichMatchedEdges")

def enrich_matched_edges():
    """
    Enrich matched_edges.csv with road_name and highway_type
    """
    logger.processing("Enriching matched_edges.csv with road information")
    
    # Load edges CSV
    edges_csv = Config.EDGES_CSV
    logger.file_op(f"Loading edges from {edges_csv}...")
    edges_df = pd.read_csv(edges_csv)
    
    # Create lookup dictionary using sequential IDs (source, target) as keys
    edge_lookup = {}
    for _, row in edges_df.iterrows():
        key = (int(row['source']), int(row['target']))
        edge_lookup[key] = {
            'road_name': str(row.get('road_name', '')).strip(),
            'highway_type': str(row.get('highway_type', 'unknown')).strip()
        }
    
    logger.data(f"Loaded {len(edge_lookup)} edges for lookup")
    
    # Load matched_edges CSV
    matched_edges_csv = Config.MAIN_DIR / "here_osm" / "matched_edges.csv"
    logger.file_op(f"Loading matched edges from {matched_edges_csv}...")
    matched_df = pd.read_csv(matched_edges_csv)
    
    # Add new columns
    matched_df['road_name'] = ''
    matched_df['highway_type'] = ''
    
    # Fill in road info
    found_count = 0
    missing_count = 0
    
    for idx, row in matched_df.iterrows():
        source = int(row['source'])
        target = int(row['target'])
        key = (source, target)
        
        if key in edge_lookup:
            matched_df.at[idx, 'road_name'] = edge_lookup[key]['road_name']
            matched_df.at[idx, 'highway_type'] = edge_lookup[key]['highway_type']
            found_count += 1
        else:
            missing_count += 1
    
    logger.data(f"Matched {found_count} edges with road info")
    logger.warning(f"Missing road info for {missing_count} edges")
    
    # Reorder columns to put new ones after coordinates
    cols = matched_df.columns.tolist()
    # Remove new columns from end
    if 'road_name' in cols:
        cols.remove('road_name')
    if 'highway_type' in cols:
        cols.remove('highway_type')
    # Insert after target_lon
    insert_idx = cols.index('target_lon') + 1
    cols.insert(insert_idx, 'road_name')
    cols.insert(insert_idx + 1, 'highway_type')
    matched_df = matched_df[cols]
    
    # Save backup
    backup_csv = matched_edges_csv.with_stem(f"{matched_edges_csv.stem}_backup")
    logger.file_op(f"Creating backup: {backup_csv.name}")
    pd.read_csv(matched_edges_csv).to_csv(backup_csv, index=False)
    
    # Save enriched CSV
    logger.file_op(f"Saving enriched matched_edges.csv...")
    matched_df.to_csv(matched_edges_csv, index=False)
    
    logger.success(f"Enriched {len(matched_df)} edges in matched_edges.csv")
    logger.success(f"Columns: {', '.join(matched_df.columns.tolist())}")
    
    # Display sample
    print("\nSample of enriched data:")
    print(matched_df[['id_hash', 'source', 'target', 'road_name', 'highway_type']].head(20))
    
    return matched_df


if __name__ == '__main__':
    try:
        enrich_matched_edges()
        logger.success("Done! matched_edges.csv has been enriched with road information")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
