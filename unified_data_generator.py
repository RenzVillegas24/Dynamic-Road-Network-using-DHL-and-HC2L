#!/usr/bin/env python3
"""
Unified Data Generator - Hash-Based Traffic Matching
=====================================================

Simplified version using pre-matched edges from matched_edges.csv
No runtime geospatial matching - just hash lookup!

Usage:
    python unified_data_generator.py --mode flow
    python unified_data_generator.py --mode both --continuous --interval 60
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add Main directory to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))

from config import Config
from realtime_traffic_service import RealtimeTrafficService

# Load environment
load_dotenv()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Unified traffic data generator with hash-based matching'
    )
    parser.add_argument(
        '--mode', 
        choices=['flow', 'incidents', 'both'], 
        default='flow',
        help='Traffic data mode'
    )
    parser.add_argument(
        '--continuous', 
        action='store_true',
        help='Run continuously with periodic updates'
    )
    parser.add_argument(
        '--interval', 
        type=int, 
        default=60,
        help='Update interval in seconds (for continuous mode)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("Unified Data Generator V2 - Hash-Based Traffic Matching")
    print("="*70)
    print(f"Mode: {args.mode}")
    print(f"Continuous: {args.continuous}")
    if args.continuous:
        print(f"Interval: {args.interval}s")
    print("="*70 + "\n")
    
    # Initialize service
    try:
        service = RealtimeTrafficService()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Make sure HERE_API_KEY is set in your .env file")
        return 1
    
    # Run
    if args.continuous:
        service.run_continuous(mode=args.mode, interval=args.interval)
    else:
        metadata = service.fetch_and_save(mode=args.mode)
        
        print(f"\n✅ Done!")
        print(f"   CSV: {metadata.get('csv_file', 'N/A')}")
        print(f"   GR: {metadata.get('gr_file', 'N/A')}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
