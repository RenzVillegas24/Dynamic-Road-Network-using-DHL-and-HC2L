#!/usr/bin/env python3
"""
Unified Data Generator - Separated Flow and Incident Services
==============================================================

Generates separate flow and incident CSV files using pre-matched edges.
Flow data uses hash-based matching (flow_service.py)
Incident data uses spatial matching (incident_service.py)

Usage:
    python unified_data_generator.py --mode flow
    python unified_data_generator.py --mode incidents
    python unified_data_generator.py --mode both
    
Note: --continuous mode removed (use manual refresh in UI)
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Add Main directory to path
SCRIPT_DIR = Path(__file__).parent
MAIN_DIR = SCRIPT_DIR / "Main"
sys.path.insert(0, str(MAIN_DIR))

from config import Config
from flow_service import FlowService
from incident_service import IncidentService
from console_formatter import get_logger

# Load environment
load_dotenv()

# Get logger instance
logger = get_logger("UnifiedDataGenerator")


def check_and_generate_graph():
    """Check if OSM graph files exist, generate if needed"""
    required_files = [
        Config.EDGES_CSV,
        Config.NODES_CSV,
        Config.PROCESSED_DATA_DIR / "quezon_city.graph"
    ]
    
    missing_files = [f for f in required_files if not f.exists()]
    
    if missing_files:
        logger.warning("OSM GRAPH FILES MISSING")
        logger.info("Missing files:")
        for f in missing_files:
            logger.error_validation(f"Missing: {f}")
        
        response = input("Would you like to download and generate the OSM graph now? (Y/n): ").strip().lower()
        
        if response in ['', 'y', 'yes']:
            logger.processing("Starting OSM graph generation...")
            logger.info("This will download OpenStreetMap data for Quezon City.")
            logger.time("This may take 5-10 minutes depending on your internet connection.")
            
            try:
                # Run osm_graph_generator.py
                generator_script = SCRIPT_DIR / "osm_graph_generator.py"
                
                if not generator_script.exists():
                    logger.error(f"Generator script not found: {generator_script}")
                    return False
                
                # Use conda python if available
                if (SCRIPT_DIR / ".conda" / "bin" / "python").exists():
                    python_cmd = str(SCRIPT_DIR / ".conda" / "bin" / "python")
                else:
                    python_cmd = sys.executable
                
                result = subprocess.run(
                    [python_cmd, str(generator_script)],
                    cwd=str(SCRIPT_DIR),
                    check=True
                )
                
                if result.returncode == 0:
                    logger.success("Graph generation completed successfully!")
                    return True
                else:
                    logger.error(f"Graph generation failed with code {result.returncode}")
                    return False
                    
            except subprocess.CalledProcessError as e:
                logger.error(f"Error generating graph: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            logger.error("Cannot proceed without OSM graph files.")
            logger.info("To generate manually, run: python osm_graph_generator.py")
            return False
    
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Unified traffic data generator with separated flow and incident services'
    )
    parser.add_argument(
        '--mode', 
        choices=['flow', 'incidents', 'both'], 
        default='both',
        help='Traffic data mode: flow, incidents, or both (default: both)'
    )
    
    args = parser.parse_args()
    
    # First, check if OSM graph exists
    logger.processing("Checking for required OSM graph files...")
    if not check_and_generate_graph():
        logger.error("Exiting: OSM graph files are required")
        return 1
    
    logger.info(f"Mode: {args.mode}")
    logger.config(f"Output directories:")
    logger.info(f"  Flow data: {Config.FLOW_DIR}")
    logger.info(f"  Incident data: {Config.INCIDENTS_DIR}")
    
    try:
        # Generate flow data if requested
        if args.mode in ['flow', 'both']:
            logger.data("Generating flow data...")
            flow_service = FlowService()
            flow_metadata = flow_service.fetch_and_save()
            logger.success("Flow data completed")
            logger.info(f"   CSV: {flow_metadata.get('csv_file', 'N/A')}")
            logger.info(f"   Edges: {flow_metadata.get('total_edges', 0)}")
        
        # Generate incident data if requested
        if args.mode in ['incidents', 'both']:
            logger.incident("Generating incident data...")
            incident_service = IncidentService()
            incident_metadata = incident_service.fetch_and_save()
            logger.success("Incident data completed")
            logger.info(f"   CSV: {incident_metadata.get('csv_file', 'N/A')}")
            logger.info(f"   Matched: {incident_metadata.get('total_matched', 0)}")
        
        logger.success("Data generation completed!")
        logger.info("Use UI refresh button for updates (no auto-refresh)")
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("Make sure HERE_API_KEY is set in your .env file")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
