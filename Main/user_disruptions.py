"""Helper utilities for managing user-reported disruptions"""

import csv
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from config import Config

USER_DISRUPTION_FIELDNAMES = [
    'source',
    'target',
    'source_lat',
    'source_lon',
    'target_lat',
    'target_lon',
    'incident_id',
    'incident_type',
    'incident_criticality',
    'incident_description',
    'incident_road_closed',
    'incident_start_time',
    'incident_end_time',
    'highway_type',
    'road_name'
]


def get_user_disruptions_file() -> Path:
    """Return the LATEST timestamped user_incident CSV file (or path for new one)."""
    user_incident_dir = Config.DISRUPTIONS_DIR / 'user_incident'
    user_incident_dir.mkdir(parents=True, exist_ok=True)
    
    # Find latest user_incident_*.csv file
    try:
        user_files = sorted(user_incident_dir.glob("user_incident_*.csv"), reverse=True)
        if user_files:
            return user_files[0]  # Return latest
    except Exception:
        pass
    
    # No files exist - return path for new file
    from datetime import datetime
    timestamp_str = datetime.now().strftime("%Y%m%dT%H%M%S%f")[:17]
    return user_incident_dir / f"user_incident_{timestamp_str}.csv"


def cleanup_old_user_incidents(max_files: int = 10):
    """Remove old user_incident files, keeping only the latest N files"""
    user_incident_dir = Config.DISRUPTIONS_DIR / 'user_incident'
    if not user_incident_dir.exists():
        return
    
    try:
        user_files = sorted(user_incident_dir.glob("user_incident_*.csv"), reverse=True)
        
        # Keep only the latest max_files
        if len(user_files) > max_files:
            files_to_remove = user_files[max_files:]
            for old_file in files_to_remove:
                try:
                    old_file.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def ensure_user_disruption_fieldnames(fieldnames: Optional[List[str]] = None) -> List[str]:
    """Ensure the CSV header contains all known disruption fields."""
    if not fieldnames:
        return list(USER_DISRUPTION_FIELDNAMES)
    updated = list(fieldnames)
    for field in USER_DISRUPTION_FIELDNAMES:
        if field not in updated:
            updated.append(field)
    return updated


def normalize_incident_type(raw_type: str) -> str:
    """Normalize raw incident type strings for display."""
    if not raw_type:
        return 'User Incident'
    label = str(raw_type).replace('-', ' ').replace('_', ' ').strip()
    if not label:
        return 'User Incident'
    return label.title()

def load_user_disruption_rows() -> List[Dict[str, str]]:
    """Load all user-reported disruption rows from latest timestamped file."""
    file_path = get_user_disruptions_file()
    
    if not file_path.exists():
        return []

    try:
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            fieldnames = ensure_user_disruption_fieldnames(reader.fieldnames)
            rows = list(reader)
    except Exception:
        return []

    # Generate incident_id if missing
    updated = False
    for row in rows:
        if not row.get('incident_id'):
            row['incident_id'] = str(uuid.uuid4())[:8]
            updated = True

    if updated:
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except Exception:
            pass

    return rows


def format_user_disruption_row(row: Dict[str, str]) -> Dict:
    """Convert a CSV row into the disruption payload expected by the frontend (incident format only)."""
    def to_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def to_int(value, default=0):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def to_bool(value):
        """Convert string to boolean."""
        return str(value).lower() in ('true', '1', 'yes')

    source_lat = to_float(row.get('source_lat'))
    source_lon = to_float(row.get('source_lon'))
    target_lat = to_float(row.get('target_lat'))
    target_lon = to_float(row.get('target_lon'))
    
    incident_id = row.get('incident_id') or f"user-{row.get('source', '')}-{row.get('target', '')}"
    criticality = row.get('incident_criticality', 'minor').lower()
    is_closed = to_bool(row.get('incident_road_closed', 'false'))
    
    # Map criticality to severity for display
    severity_map = {
        'critical': 'Heavy',
        'major': 'Heavy',
        'high': 'Medium',
        'medium': 'Medium',
        'minor': 'Light',
        'low': 'Light'
    }
    severity = severity_map.get(criticality, 'Light')

    return {
        'incident_id': incident_id,
        'source_id': to_int(row.get('source')),
        'target_id': to_int(row.get('target')),
        'source_lat': source_lat,
        'source_lng': source_lon,
        'target_lat': target_lat,
        'target_lng': target_lon,
        'road_name': row.get('road_name', 'Custom Report'),
        'incident_type': normalize_incident_type(row.get('incident_type')),
        'incident_criticality': criticality,
        'incident_description': row.get('incident_description', ''),
        'incident_road_closed': is_closed,
        'incident_start_time': row.get('incident_start_time', ''),
        'incident_end_time': row.get('incident_end_time', ''),
        'highway_type': row.get('highway_type', 'unknown')
    }

