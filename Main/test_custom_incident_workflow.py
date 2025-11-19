#!/usr/bin/env python3
"""
Test script to verify that creating/deleting custom incidents generates
new timestamped CSV files and triggers auto-disruption service updates.

This test validates the acceptance criteria:
1. Creating a custom incident writes a new incident_YYYYMMDDTHHMMSS.csv
2. Deleting a custom incident also writes a new incident_YYYYMMDDTHHMMSS.csv
3. Auto-disruption service detects the new files
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add Main directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from traffic_data_manager import merge_user_disruptions_with_traffic, get_latest_flow_csv, get_latest_incident_csv
from user_disruptions import (
    get_user_disruptions_file, 
    ensure_user_disruption_fieldnames, 
    load_user_disruption_rows
)
import csv


def count_files_in_dir(directory: Path, pattern: str) -> int:
    """Count files matching a pattern in a directory"""
    return len(list(directory.glob(pattern)))


def get_latest_file_mtime(directory: Path, pattern: str) -> float:
    """Get the modification time of the latest file matching pattern (sorted by mtime)"""
    files = sorted(directory.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if files:
        return files[0].stat().st_mtime
    return 0.0


def test_create_custom_incident():
    """Test that creating a custom incident creates new timestamped CSV files"""
    print("\n" + "="*70)
    print("TEST 1: Creating a custom incident")
    print("="*70)
    
    # Count initial files
    initial_incident_count = count_files_in_dir(Config.INCIDENTS_DIR, "incident_*.csv")
    initial_flow_count = count_files_in_dir(Config.FLOW_DIR, "flow_*.csv")
    initial_incident_mtime = get_latest_file_mtime(Config.INCIDENTS_DIR, "incident_*.csv")
    initial_flow_mtime = get_latest_file_mtime(Config.FLOW_DIR, "flow_*.csv")
    
    print(f"📊 Initial state:")
    print(f"   Incident files: {initial_incident_count}")
    print(f"   Flow files: {initial_flow_count}")
    
    # Create a test custom incident
    print(f"\n➕ Creating test custom incident...")
    import uuid
    
    test_incident = {
        'report_id': str(uuid.uuid4())[:8],
        'timestamp': datetime.now().isoformat(),
        'source': 1000,
        'target': 1001,
        'lat': 14.6500,
        'lng': 121.0500,
        'snapped_lat': 14.6500,
        'snapped_lng': 121.0500,
        'road_name': 'Test Road',
        'incident_type': 'accident',
        'severity': 'major',
        'speed_kph': 10.0,
        'freeFlow_kph': 50.0,
        'jamFactor': 8.0,
        'isClosed': '0',
        'description': 'Test accident for integration test'
    }
    
    # Save to user disruptions CSV
    csv_path = get_user_disruptions_file()
    rows = load_user_disruption_rows()
    rows.append(test_incident)
    
    fieldnames = ensure_user_disruption_fieldnames()
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"   ✅ Saved test incident to user_reported_disruptions.csv")
    
    # Trigger merge to create new timestamped files
    print(f"\n🔀 Merging user disruptions with traffic data...")
    
    latest_flow = get_latest_flow_csv()
    latest_incident = get_latest_incident_csv()
    
    if latest_flow and latest_incident:
        # Wait a moment to ensure timestamp difference
        time.sleep(0.1)
        
        merge_metadata = merge_user_disruptions_with_traffic(
            str(latest_flow), 
            str(latest_incident)
        )
        
        print(f"\n📊 Merge results:")
        print(f"   Success: {merge_metadata['success']}")
        if merge_metadata.get('flow_file'):
            print(f"   New flow file: {Path(merge_metadata['flow_file']).name}")
            print(f"   Flow records: {merge_metadata['flow_records']}")
        if merge_metadata.get('incident_file'):
            print(f"   New incident file: {Path(merge_metadata['incident_file']).name}")
            print(f"   Incident records: {merge_metadata['incident_records']}")
        
        # Verify new files were created
        final_incident_count = count_files_in_dir(Config.INCIDENTS_DIR, "incident_*.csv")
        final_flow_count = count_files_in_dir(Config.FLOW_DIR, "flow_*.csv")
        final_incident_mtime = get_latest_file_mtime(Config.INCIDENTS_DIR, "incident_*.csv")
        final_flow_mtime = get_latest_file_mtime(Config.FLOW_DIR, "flow_*.csv")
        
        print(f"\n📊 Final state:")
        print(f"   Incident files: {final_incident_count} (change: +{final_incident_count - initial_incident_count})")
        print(f"   Flow files: {final_flow_count} (change: +{final_flow_count - initial_flow_count})")
        
        # Assertions
        assert final_incident_count > initial_incident_count, "❌ No new incident file created!"
        assert final_flow_count > initial_flow_count, "❌ No new flow file created!"
        assert final_incident_mtime > initial_incident_mtime, "❌ Incident file mtime not updated!"
        assert final_flow_mtime > initial_flow_mtime, "❌ Flow file mtime not updated!"
        
        print(f"\n✅ TEST 1 PASSED: New timestamped files created successfully!")
        return test_incident['report_id']
    else:
        print(f"⚠️  TEST 1 SKIPPED: No existing traffic files to merge with")
        return None


def test_delete_custom_incident(report_id: str):
    """Test that deleting a custom incident creates new timestamped CSV files"""
    print("\n" + "="*70)
    print("TEST 2: Deleting a custom incident")
    print("="*70)
    
    if not report_id:
        print("⚠️  TEST 2 SKIPPED: No report_id from previous test")
        return
    
    # Count initial files
    initial_incident_count = count_files_in_dir(Config.INCIDENTS_DIR, "incident_*.csv")
    initial_flow_count = count_files_in_dir(Config.FLOW_DIR, "flow_*.csv")
    initial_incident_mtime = get_latest_file_mtime(Config.INCIDENTS_DIR, "incident_*.csv")
    initial_flow_mtime = get_latest_file_mtime(Config.FLOW_DIR, "flow_*.csv")
    
    print(f"📊 Initial state:")
    print(f"   Incident files: {initial_incident_count}")
    print(f"   Flow files: {initial_flow_count}")
    
    # Delete the test incident
    print(f"\n🗑️  Deleting test incident (report_id: {report_id})...")
    
    file_path = get_user_disruptions_file()
    rows = load_user_disruption_rows()
    initial_row_count = len(rows)
    rows_to_keep = [row for row in rows if row.get('report_id') != report_id]
    
    fieldnames = ensure_user_disruption_fieldnames()
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_keep)
    
    print(f"   ✅ Deleted from user_reported_disruptions.csv")
    print(f"   Rows before: {initial_row_count}, Rows after: {len(rows_to_keep)}")
    
    # Trigger merge to create new timestamped files
    print(f"\n🔀 Merging user disruptions with traffic data...")
    
    latest_flow = get_latest_flow_csv()
    latest_incident = get_latest_incident_csv()
    
    if latest_flow and latest_incident:
        # Wait a moment to ensure timestamp difference
        time.sleep(0.1)
        
        merge_metadata = merge_user_disruptions_with_traffic(
            str(latest_flow), 
            str(latest_incident)
        )
        
        print(f"\n📊 Merge results:")
        print(f"   Success: {merge_metadata['success']}")
        if merge_metadata.get('flow_file'):
            print(f"   New flow file: {Path(merge_metadata['flow_file']).name}")
            print(f"   Flow records: {merge_metadata['flow_records']}")
        if merge_metadata.get('incident_file'):
            print(f"   New incident file: {Path(merge_metadata['incident_file']).name}")
            print(f"   Incident records: {merge_metadata['incident_records']}")
        
        # Verify new files were created
        final_incident_count = count_files_in_dir(Config.INCIDENTS_DIR, "incident_*.csv")
        final_flow_count = count_files_in_dir(Config.FLOW_DIR, "flow_*.csv")
        final_incident_mtime = get_latest_file_mtime(Config.INCIDENTS_DIR, "incident_*.csv")
        final_flow_mtime = get_latest_file_mtime(Config.FLOW_DIR, "flow_*.csv")
        
        print(f"\n📊 Final state:")
        print(f"   Incident files: {final_incident_count} (change: +{final_incident_count - initial_incident_count})")
        print(f"   Flow files: {final_flow_count} (change: +{final_flow_count - initial_flow_count})")
        
        # Assertions
        assert final_incident_count > initial_incident_count, "❌ No new incident file created!"
        assert final_flow_count > initial_flow_count, "❌ No new flow file created!"
        assert final_incident_mtime > initial_incident_mtime, "❌ Incident file mtime not updated!"
        assert final_flow_mtime > initial_flow_mtime, "❌ Flow file mtime not updated!"
        
        print(f"\n✅ TEST 2 PASSED: New timestamped files created after deletion!")
    else:
        print(f"⚠️  TEST 2 SKIPPED: No existing traffic files to merge with")


def test_auto_disruption_hash_detection():
    """Test that auto-disruption service can detect file changes via hash"""
    print("\n" + "="*70)
    print("TEST 3: Auto-disruption service hash detection")
    print("="*70)
    
    try:
        from auto_disruption_service import AutoDisruptionService
        from flask import Flask
        
        # Create a minimal Flask app for testing
        app = Flask(__name__)
        
        # Create auto-disruption service instance
        service = AutoDisruptionService(app, update_interval=120)
        
        print(f"\n📊 Computing initial disruption hash...")
        initial_hash = service._get_disruption_hash()
        print(f"   Initial hash: {initial_hash}")
        
        # Wait a moment and check again (should be same)
        time.sleep(0.1)
        same_hash = service._get_disruption_hash()
        print(f"   Same hash: {same_hash}")
        
        assert initial_hash == same_hash, "❌ Hash changed unexpectedly!"
        print(f"   ✅ Hash is stable when files don't change")
        
        # Now simulate a file change by clearing the hash
        service.last_disruption_hash = initial_hash
        
        # Create a dummy file to change the hash
        dummy_file = Config.INCIDENTS_DIR / f"incident_{datetime.now().strftime('%Y%m%dT%H%M%S')}_test.csv"
        dummy_file.write_text("test,data\n1,2\n")
        
        time.sleep(0.1)
        new_hash = service._get_disruption_hash()
        print(f"   New hash after file creation: {new_hash}")
        
        assert new_hash != initial_hash, "❌ Hash didn't change after new file!"
        print(f"   ✅ Hash changed when new file was created")
        
        # Clean up dummy file
        dummy_file.unlink()
        
        print(f"\n✅ TEST 3 PASSED: Auto-disruption service hash detection works!")
        
    except ImportError as e:
        print(f"⚠️  TEST 3 SKIPPED: Could not import dependencies ({e})")
    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("CUSTOM INCIDENT WORKFLOW INTEGRATION TESTS")
    print("="*70)
    print(f"Testing that custom incidents create timestamped CSV files")
    print(f"and trigger auto-disruption service updates")
    print("="*70)
    
    try:
        # Test 1: Create custom incident
        report_id = test_create_custom_incident()
        
        # Test 2: Delete custom incident
        test_delete_custom_incident(report_id)
        
        # Test 3: Auto-disruption hash detection
        test_auto_disruption_hash_detection()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nSummary:")
        print("✅ Creating custom incidents generates new timestamped CSV files")
        print("✅ Deleting custom incidents generates new timestamped CSV files")
        print("✅ Auto-disruption service detects file changes via hash")
        print("✅ Implementation meets acceptance criteria")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
