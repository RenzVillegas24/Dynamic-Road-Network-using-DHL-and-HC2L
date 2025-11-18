"""Helper utilities for managing user-reported disruptions"""

import csv
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from config import Config

USER_DISRUPTION_FIELDNAMES = [
    'report_id',
    'timestamp',
    'source',
    'target',
    'lat',
    'lng',
    'snapped_lat',
    'snapped_lng',
    'road_name',
    'incident_type',
    'severity',
    'speed_kph',
    'freeFlow_kph',
    'jamFactor',
    'isClosed',
    'description'
]


def get_user_disruptions_file() -> Path:
    """Return the CSV path that stores user disruption reports."""
    return Config.DISRUPTIONS_DIR / 'user_reported_disruptions.csv'


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


def normalize_severity(raw_severity: str) -> str:
    """Convert raw severity hints into standardized labels."""
    mapping = {
        'heavy': 'Heavy',
        'medium': 'Medium',
        'moderate': 'Medium',
        'light': 'Light',
        'minor': 'Light'
    }
    if not raw_severity:
        return 'Medium'
    return mapping.get(str(raw_severity).lower(), 'Medium')


def load_user_disruption_rows() -> List[Dict[str, str]]:
    """Load (and self-heal) all user-reported disruption rows."""
    file_path = get_user_disruptions_file()
    if not file_path.exists():
        return []

    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = ensure_user_disruption_fieldnames(reader.fieldnames)
        rows = list(reader)

    updated = False
    for row in rows:
        if not row.get('report_id'):
            row['report_id'] = str(uuid.uuid4())
            updated = True

    if updated:
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return rows


def format_user_disruption_row(row: Dict[str, str]) -> Dict:
    """Convert a CSV row into the disruption payload expected by the frontend."""
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

    lat = to_float(row.get('snapped_lat') or row.get('lat'))
    lng = to_float(row.get('snapped_lng') or row.get('lng'))
    severity = normalize_severity(row.get('severity'))
    speed_kph = to_float(row.get('speed_kph'), 0.0)
    free_flow_kph = to_float(row.get('freeFlow_kph'), 50.0)
    jam_factor = to_float(row.get('jamFactor'), 0.0)
    slowdown_ratio = 0.0
    if free_flow_kph > 0:
        slowdown_ratio = max(0.0, min(1.0, speed_kph / free_flow_kph))

    source_lat = to_float(row.get('source_lat'), lat)
    source_lng = to_float(row.get('source_lon'), lng)
    target_lat = to_float(row.get('target_lat'), lat)
    target_lng = to_float(row.get('target_lon'), lng)

    report_id = row.get('report_id') or f"legacy-{row.get('timestamp', '')}-{row.get('source', '')}-{row.get('target', '')}"

    return {
        'source_id': to_int(row.get('source')),
        'target_id': to_int(row.get('target')),
        'source_lat': source_lat or lat,
        'source_lng': source_lng or lng,
        'target_lat': target_lat or lat,
        'target_lng': target_lng or lng,
        'road_name': row.get('road_name', 'Custom Report'),
        'incident_type': normalize_incident_type(row.get('incident_type')),
        'severity': severity,
        'speed_kph': speed_kph,
        'free_flow_kph': free_flow_kph,
        'jam_factor': jam_factor,
        'slowdown_ratio': slowdown_ratio,
        'is_closed': bool(int(row.get('isClosed', 0))) if row.get('isClosed') not in (None, '') else False,
        'description': row.get('description', 'User provided disruption'),
        'timestamp': row.get('timestamp', '')
    }

