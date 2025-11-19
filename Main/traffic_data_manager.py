from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import Config
from user_disruptions import (
    load_user_disruption_rows,
    normalize_incident_type,
    normalize_severity
)

CRITICALITY_RANK = {
    'critical': 4,
    'severe': 3,
    'major': 2,
    'minor': 1
}

DATASET_MODES = ('none', 'flow', 'incidents', 'both')
DEFAULT_DATASET_MODE = 'both'


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = '') -> str:
    return str(value).strip() if value not in (None, '', [], {}) else default


def _bool_from_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() not in ('', '0', 'false', 'none')
    return False


def _build_flow_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'source': _safe_int(row.get('source')),
        'target': _safe_int(row.get('target')),
        'source_lat': _safe_float(row.get('source_lat')),
        'source_lon': _safe_float(row.get('source_lon')),
        'target_lat': _safe_float(row.get('target_lat')),
        'target_lon': _safe_float(row.get('target_lon')),
        'road_name': _safe_str(row.get('road_name')),
        'highway_type': _safe_str(row.get('highway_type'), 'unknown'),
        'flow_speed_kph': _safe_float(row.get('flow_speed_kph')),
        'flow_free_flow_kph': _safe_float(row.get('flow_free_flow_kph')),
        'flow_jam_factor': _safe_float(row.get('flow_jam_factor') or row.get('jamFactor')),
        'flow_confidence': _safe_float(row.get('flow_confidence')),
        'flow_traversability': _safe_str(row.get('flow_traversability'), 'open'),
        'speed_kph': _safe_float(row.get('flow_speed_kph')),
        'freeFlow_kph': _safe_float(row.get('flow_free_flow_kph')),
        'jamFactor': _safe_float(row.get('flow_jam_factor') or row.get('jamFactor')),
        'jam_factor': _safe_float(row.get('flow_jam_factor') or row.get('jamFactor')),
        'isClosed': False,
        'incident_id': '',
        'incident_type': '',
        'incident_criticality': '',
        'incident_description': '',
        'incident_road_closed': False,
        'incident_start_time': '',
        'incident_end_time': ''
    }


def _build_incident_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'source': _safe_int(row.get('source')),
        'target': _safe_int(row.get('target')),
        'source_lat': _safe_float(row.get('source_lat')),
        'source_lon': _safe_float(row.get('source_lon')),
        'target_lat': _safe_float(row.get('target_lat')),
        'target_lon': _safe_float(row.get('target_lon')),
        'road_name': _safe_str(row.get('road_name')),
        'highway_type': _safe_str(row.get('highway_type'), 'unknown'),
        'flow_speed_kph': 0.0,
        'flow_free_flow_kph': 0.0,
        'flow_jam_factor': 0.0,
        'flow_confidence': 0.0,
        'flow_traversability': 'open',
        'speed_kph': 0.0,
        'freeFlow_kph': 0.0,
        'jamFactor': 0.0,
        'jam_factor': 0.0,
        'isClosed': _bool_from_value(row.get('incident_road_closed')),
        'incident_id': _safe_str(row.get('incident_id')),
        'incident_type': _safe_str(row.get('incident_type')),
        'incident_criticality': _safe_str(row.get('incident_criticality')),
        'incident_description': _safe_str(row.get('incident_description')),
        'incident_road_closed': _bool_from_value(row.get('incident_road_closed')),
        'incident_start_time': _safe_str(row.get('incident_start_time')),
        'incident_end_time': _safe_str(row.get('incident_end_time'))
    }


def _pick_coord(flow_entry: Optional[Dict[str, Any]], incident_entry: Optional[Dict[str, Any]], key: str) -> float:
    for entry in (flow_entry, incident_entry):
        if entry and entry.get(key) not in (None, ''):
            return float(entry.get(key))
    return 0.0


def normalize_dataset_mode(mode: Optional[str]) -> str:
    if not mode:
        return DEFAULT_DATASET_MODE
    candidate = str(mode).lower()
    return candidate if candidate in DATASET_MODES else DEFAULT_DATASET_MODE


def _find_latest_csv(directory: Path, prefix: str) -> Optional[Path]:
    files = sorted(directory.glob(f"{prefix}_*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read_csv_safely(csv_path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(csv_path)
    except Exception as exc:
        print(f"   ⚠️  Failed to read CSV {csv_path.name}: {exc}")
        return pd.DataFrame()


def _csv_metadata(path: Path, source: str, row_count: int) -> Dict[str, Any]:
    try:
        stats = path.stat()
    except OSError:
        stats = None
    metadata: Dict[str, Any] = {
        'source': source,
        'path': str(path),
        'name': path.name,
        'rows': row_count
    }
    if stats:
        metadata['timestamp'] = stats.st_mtime
        metadata['size'] = stats.st_size
    return metadata


def get_latest_flow_csv() -> Optional[Path]:
    return _find_latest_csv(Config.FLOW_DIR, 'flow')


def get_latest_incident_csv() -> Optional[Path]:
    return _find_latest_csv(Config.INCIDENTS_DIR, 'incident')


def build_dataset_dataframe(mode: Optional[str] = None, include_user_disruptions: bool = True) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    normalized_mode = normalize_dataset_mode(mode)
    metadata: Dict[str, Any] = {
        'mode': normalized_mode,
        'csv_sources': [],
        'user_disruption_count': 0,
        'rows_before_user_disruptions': 0,
        'rows_after_user_disruptions': 0
    }

    base_df = pd.DataFrame()
    flow_df: Optional[pd.DataFrame] = None
    incident_df: Optional[pd.DataFrame] = None

    if normalized_mode in ('flow', 'both'):
        flow_path = get_latest_flow_csv()
        if flow_path:
            flow_df = _read_csv_safely(flow_path)
            metadata['csv_sources'].append(_csv_metadata(flow_path, 'flow', len(flow_df)))

    if normalized_mode in ('incidents', 'both'):
        incident_path = get_latest_incident_csv()
        if incident_path:
            incident_df = _read_csv_safely(incident_path)
            metadata['csv_sources'].append(_csv_metadata(incident_path, 'incident', len(incident_df)))

    if normalized_mode == 'flow':
        base_df = flow_df.copy() if flow_df is not None else pd.DataFrame()
    elif normalized_mode == 'incidents':
        base_df = incident_df.copy() if incident_df is not None else pd.DataFrame()
    elif normalized_mode == 'both':
        base_df = combine_flow_and_incident_data(flow_df or pd.DataFrame(), incident_df or pd.DataFrame())
    else:
        base_df = pd.DataFrame()

    base_df = base_df.copy()
    metadata['rows_before_user_disruptions'] = len(base_df)

    if include_user_disruptions:
        user_rows = load_user_disruption_rows()
        metadata['user_disruption_count'] = len(user_rows)
        if user_rows:
            base_df = merge_user_disruptions_dataframe(base_df, user_rows)
            metadata['rows_after_user_disruptions'] = len(base_df)
        else:
            metadata['rows_after_user_disruptions'] = len(base_df)
    else:
        metadata['rows_after_user_disruptions'] = len(base_df)

    metadata['total_rows'] = len(base_df)
    return base_df, metadata


def regenerate_dataset_gr(mode: Optional[str] = None, include_user_disruptions: bool = True) -> Dict[str, Any]:
    df, metadata = build_dataset_dataframe(mode, include_user_disruptions)
    metadata['last_generated'] = datetime.now().isoformat()
    metadata['gr_file'] = None
    metadata['success'] = False

    if df.empty or metadata['mode'] == 'none':
        return metadata

    generated = write_traffic_gr_from_dataframe(df, metadata['mode'])
    if generated:
        metadata['gr_file'] = str(generated)
        metadata['success'] = True
        metadata['total_rows'] = len(df)

    return metadata


def combine_flow_and_incident_data(flow_df: pd.DataFrame, incident_df: pd.DataFrame) -> pd.DataFrame:
    """Combine separate flow and incident DataFrames into a unified table."""
    if (flow_df is None or flow_df.empty) and (incident_df is None or incident_df.empty):
        return pd.DataFrame()

    flow_entries: Dict[tuple[int, int], Dict[str, Any]] = {}
    if flow_df is not None:
        for row in flow_df.to_dict('records'):
            key = (_safe_int(row.get('source')), _safe_int(row.get('target')))
            jam_value = _safe_float(row.get('flow_jam_factor') or row.get('jamFactor'))
            existing = flow_entries.get(key)
            if not existing or jam_value > existing.get('flow_jam_factor', 0.0):
                flow_entries[key] = _build_flow_entry(row)

    incident_entries: Dict[tuple[int, int], Dict[str, Any]] = {}
    incident_rank: Dict[tuple[int, int], int] = {}
    if incident_df is not None:
        for row in incident_df.to_dict('records'):
            key = (_safe_int(row.get('source')), _safe_int(row.get('target')))
            criticality = str(row.get('incident_criticality', '')).lower()
            rank = CRITICALITY_RANK.get(criticality, 0)
            existing_rank = incident_rank.get(key, 0)
            if rank >= existing_rank:
                incident_entries[key] = _build_incident_entry(row)
                incident_rank[key] = rank

    all_keys = set(flow_entries.keys()) | set(incident_entries.keys())
    merged_rows = []

    for key in sorted(all_keys):
        flow_entry = flow_entries.get(key)
        incident_entry = incident_entries.get(key)
        merged_rows.append({
            'source': key[0],
            'target': key[1],
            'source_lat': _pick_coord(flow_entry, incident_entry, 'source_lat'),
            'source_lon': _pick_coord(flow_entry, incident_entry, 'source_lon'),
            'target_lat': _pick_coord(flow_entry, incident_entry, 'target_lat'),
            'target_lon': _pick_coord(flow_entry, incident_entry, 'target_lon'),
            'road_name': _safe_str(
                (flow_entry or {}).get('road_name') or (incident_entry or {}).get('road_name'),
                'Unknown Road'
            ),
            'highway_type': _safe_str(
                (flow_entry or {}).get('highway_type') or (incident_entry or {}).get('highway_type'),
                'unknown'
            ),
            'flow_speed_kph': _safe_float((flow_entry or {}).get('flow_speed_kph')),
            'flow_free_flow_kph': _safe_float((flow_entry or {}).get('flow_free_flow_kph')),
            'flow_jam_factor': _safe_float((flow_entry or {}).get('flow_jam_factor')),
            'flow_confidence': _safe_float((flow_entry or {}).get('flow_confidence')),
            'flow_traversability': _safe_str((flow_entry or {}).get('flow_traversability'), 'open'),
            'speed_kph': _safe_float((flow_entry or {}).get('speed_kph')),
            'freeFlow_kph': _safe_float((flow_entry or {}).get('freeFlow_kph')),
            'jamFactor': _safe_float((flow_entry or {}).get('jamFactor')),
            'jam_factor': _safe_float((flow_entry or {}).get('jam_factor')),
            'isClosed': _bool_from_value((incident_entry or {}).get('isClosed')),
            'incident_id': _safe_str((incident_entry or {}).get('incident_id')),
            'incident_type': _safe_str((incident_entry or {}).get('incident_type')),
            'incident_criticality': _safe_str((incident_entry or {}).get('incident_criticality')),
            'incident_description': _safe_str((incident_entry or {}).get('incident_description')),
            'incident_road_closed': _bool_from_value((incident_entry or {}).get('incident_road_closed')),
            'incident_start_time': _safe_str((incident_entry or {}).get('incident_start_time')),
            'incident_end_time': _safe_str((incident_entry or {}).get('incident_end_time'))
        })

    if not merged_rows:
        return pd.DataFrame()

    return pd.DataFrame(merged_rows)


def build_user_disruption_dataframe(user_rows: List[Dict[str, Any]], target_type: str = 'flow') -> pd.DataFrame:
    """
    Convert user-reported disruption rows into a traffic DataFrame.
    
    CRITICAL: This function MUST match the EXACT column format from the respective services:
    - flow_service.py: Creates 14-column flow CSV
    - incident_service.py: Creates 15-column incident CSV
    
    Column consistency is ESSENTIAL to prevent pandas concat() from adding unwanted columns.
    
    Args:
        user_rows: List of user disruption dictionaries
        target_type: 'flow' or 'incident' - determines which columns to include
    
    Returns:
        DataFrame with EXACT columns matching flow_service.py or incident_service.py
    """
    if not user_rows:
        return pd.DataFrame()

    records = []
    for row in user_rows:
        source = _safe_int(row.get('source'))
        target = _safe_int(row.get('target'))
        if source == 0 and target == 0:
            continue
        
        speed = _safe_float(row.get('speed_kph'))
        free_flow = _safe_float(row.get('freeFlow_kph'), 50.0)
        jam_factor = _safe_float(row.get('jamFactor'))
        severity = normalize_severity(row.get('severity'))
        incident_type = normalize_incident_type(row.get('incident_type'))
        
        if target_type == 'flow':
            # MUST match flow_service.py exactly: 14 columns
            # id_hash,source_lat,source_lon,target_lat,target_lon,source,target,
            # flow_speed_kph,flow_free_flow_kph,flow_jam_factor,flow_confidence,
            # flow_traversability,highway_type,road_name
            record = {
                'id_hash': f'user_{source}_{target}',
                'source_lat': _safe_float(row.get('snapped_lat') or row.get('lat')),
                'source_lon': _safe_float(row.get('snapped_lng') or row.get('lng')),
                'target_lat': _safe_float(row.get('target_lat') or row.get('lat')),
                'target_lon': _safe_float(row.get('target_lon') or row.get('lng')),
                'source': source,
                'target': target,
                'flow_speed_kph': speed,
                'flow_free_flow_kph': free_flow,
                'flow_jam_factor': jam_factor,
                'flow_confidence': 0.95,
                'flow_traversability': 'closed' if _bool_from_value(row.get('isClosed')) else 'open',
                'highway_type': _safe_str(row.get('highway_type', 'unknown')),
                'road_name': _safe_str(row.get('road_name', 'User Reported Location'))
            }
        else:  # target_type == 'incident'
            # MUST match incident_service.py exactly: 15 columns
            # source,target,source_lat,source_lon,target_lat,target_lon,
            # incident_id,incident_type,incident_criticality,incident_description,
            # incident_road_closed,incident_start_time,incident_end_time,
            # highway_type,road_name
            record = {
                'source': source,
                'target': target,
                'source_lat': _safe_float(row.get('snapped_lat') or row.get('lat')),
                'source_lon': _safe_float(row.get('snapped_lng') or row.get('lng')),
                'target_lat': _safe_float(row.get('target_lat') or row.get('lat')),
                'target_lon': _safe_float(row.get('target_lon') or row.get('lng')),
                'incident_id': f'user_{source}_{target}',
                'incident_type': incident_type,
                'incident_criticality': severity,
                'incident_description': _safe_str(row.get('description')),
                'incident_road_closed': _bool_from_value(row.get('isClosed')),
                'incident_start_time': '',  # User disruptions don't have timestamps
                'incident_end_time': '',    # User disruptions don't have timestamps
                'highway_type': _safe_str(row.get('highway_type', 'unknown')),
                'road_name': _safe_str(row.get('road_name', 'User Reported Location'))
            }
        
        records.append(record)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def merge_user_disruptions_dataframe(base_df: pd.DataFrame, user_rows: List[Dict[str, Any]], target_type: str = 'flow') -> pd.DataFrame:
    """
    Append user disruptions to a base traffic DataFrame, maintaining column integrity.
    
    Args:
        base_df: The base traffic DataFrame (flow or incident CSV)
        user_rows: List of user disruption records
        target_type: 'flow' or 'incident' - specifies which columns to use
    
    Returns:
        Combined DataFrame with duplicate handling
    """
    user_df = build_user_disruption_dataframe(user_rows, target_type=target_type)
    if user_df.empty:
        return base_df or pd.DataFrame()

    if base_df is None or base_df.empty:
        return user_df

    combined = pd.concat([base_df, user_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=['source', 'target'], keep='last')
    return combined


def cleanup_old_gr_files(mode: str, max_files: int = 10, output_dir: Path = Config.DISRUPTIONS_DIR):
    """Remove older .gr files for a mode, keeping the latest N"""
    pattern = f'traffic_*_{mode}.gr'
    files = sorted(output_dir.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    for old_file in files[max_files:]:
        try:
            old_file.unlink()
        except Exception:
            pass


def write_traffic_gr_from_dataframe(df: pd.DataFrame, mode: str, output_dir: Path = Config.DISRUPTIONS_DIR) -> Optional[Path]:
    """Export traffic DataFrame to enhanced .gr format for routing."""
    if df is None or df.empty:
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_gr_files(mode, output_dir=output_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'traffic_{timestamp}_{mode}.gr'
    filepath = output_dir / filename

    nodes = set(df['source'].tolist() + df['target'].tolist())
    num_nodes = max(nodes) if nodes else 0
    num_edges = len(df)

    with open(filepath, 'w') as f:
        f.write('c Traffic data from HERE API - ENHANCED FORMAT\n')
        f.write(f'c Mode: {mode}\n')
        f.write(f'c Timestamp: {datetime.now().isoformat()}\n')
        f.write(f'c Edges: {num_edges}\n')
        f.write('c Format: a source target weight jam_factor current_speed free_flow_speed impact_score confidence highway is_closed type\n')
        f.write(f'p sp {num_nodes} {num_edges}\n')

        for _, row in df.iterrows():
            source = _safe_int(row.get('source'))
            target = _safe_int(row.get('target'))
            jam_factor = _safe_float(row.get('flow_jam_factor', row.get('jamFactor', 0.0)))
            speed_kph = _safe_float(row.get('flow_speed_kph', row.get('speed_kph', 0.0)))
            free_flow_kph = _safe_float(row.get('flow_free_flow_kph', row.get('freeFlow_kph', 0.0)))
            if free_flow_kph <= 0:
                highway = str(row.get('highway_type', 'unknown')).lower()
                if 'motorway' in highway:
                    free_flow_kph = 110.0
                elif 'trunk' in highway:
                    free_flow_kph = 90.0
                elif 'primary' in highway:
                    free_flow_kph = 70.0
                elif 'secondary' in highway:
                    free_flow_kph = 60.0
                elif 'tertiary' in highway:
                    free_flow_kph = 50.0
                elif 'residential' in highway:
                    free_flow_kph = 40.0
                else:
                    free_flow_kph = 50.0
            if speed_kph <= 0.0:
                if jam_factor > 0.0:
                    speed_kph = free_flow_kph * (1.0 - min(1.0, jam_factor / 10.0) * 0.9)
                else:
                    speed_kph = free_flow_kph
            speed_kph = min(speed_kph, free_flow_kph)

            is_closed = _bool_from_value(row.get('incident_road_closed') or row.get('isClosed'))
            criticality = str(row.get('incident_criticality', '')).lower()
            if criticality:
                criticality_boost = {
                    'critical': 9.0,
                    'severe': 7.0,
                    'major': 5.0,
                    'minor': 2.0
                }
                incident_boost = criticality_boost.get(criticality, 0.0)
                jam_factor = max(jam_factor, incident_boost)

            if is_closed:
                weight = 999999
                incident_type = 'closure'
            elif free_flow_kph > 0 and speed_kph > 0:
                base_weight = 1000
                time_multiplier = free_flow_kph / speed_kph
                weight = int(base_weight * time_multiplier)
                if jam_factor >= 8.0:
                    incident_type = 'accident'
                elif jam_factor >= 5.0:
                    incident_type = 'congestion'
                else:
                    incident_type = 'flow'
            else:
                weight = int(1000 * (1.0 + jam_factor / 10.0))
                incident_type = 'flow'

            if is_closed:
                impact_score = 1.0
            else:
                speed_ratio = speed_kph / free_flow_kph if free_flow_kph > 0 else 1.0
                impact_score = round(max(0.0, min(1.0, 1.0 - speed_ratio)), 3)

            confidence = 0.9
            highway_field = str(row.get('highway_type', 'unknown')).replace(' ', '_')

            f.write(
                f"a {source} {target} {weight} {jam_factor:.2f} {speed_kph:.2f} {free_flow_kph:.2f} {impact_score:.3f} {confidence:.2f} {highway_field} {1 if is_closed else 0} {incident_type}\n"
            )

    symlink = output_dir / f'current_traffic_{mode}.gr'
    if symlink.exists() or symlink.is_symlink():
        try:
            symlink.unlink()
        except Exception:
            pass
    symlink.symlink_to(filepath.name)

    return filepath


def get_latest_traffic_gr(mode: str, output_dir: Path = Config.DISRUPTIONS_DIR) -> Optional[Path]:
    symlink = output_dir / f'current_traffic_{mode}.gr'
    if symlink.exists():
        try:
            target = symlink.resolve()
            if target.exists():
                return target
        except OSError:
            pass

    pattern = f'traffic_*_{mode}.gr'
    files = sorted(output_dir.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


def generate_disruption_gr_file(disruption_type: str, csv_file: str) -> Optional[Path]:
    """
    Generate a .gr (graph) file from a disruption CSV file.
    
    Converts CSV disruption data to a format suitable for the C++ routing engines
    (DHL and HC2L).
    
    Args:
        disruption_type: 'flow' or 'incident'
        csv_file: Path to the CSV file to convert
        
    Returns:
        Path to the generated .gr file, or None if conversion failed
    """
    try:
        if not csv_file or not Path(csv_file).exists():
            print(f"   ⚠️  CSV file not found: {csv_file}")
            return None
        
        csv_path = Path(csv_file)
        
        # Determine output directory and filename
        if disruption_type == 'flow':
            output_dir = Config.DISRUPTIONS_DIR / 'flow'
            prefix = 'flow'
        elif disruption_type == 'incident':
            output_dir = Config.DISRUPTIONS_DIR / 'incidents'
            prefix = 'incident'
        else:
            print(f"   ⚠️  Unknown disruption type: {disruption_type}")
            return None
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped output filename
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        output_file = output_dir / f'{prefix}_{timestamp}.gr'
        
        # Read CSV and build .gr format
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            print(f"   ⚠️  Failed to read CSV: {e}")
            return None
        
        if df.empty:
            print(f"   ⚠️  CSV file is empty: {csv_file}")
            return None
        
        # Write .gr file with disruption data
        with open(output_file, 'w') as f:
            f.write(f"# {disruption_type.upper()} disruptions\n")
            f.write(f"# Generated: {timestamp}\n")
            f.write(f"# Rows: {len(df)}\n")
            f.write("# Format: source target jam_factor speed_kph road_name\n")
            f.write("#\n")
            
            # Convert each row to a disruption entry
            for idx, row in df.iterrows():
                try:
                    source = int(row.get('source', 0))
                    target = int(row.get('target', 0))
                    
                    # Get jam factor (use flow_jam_factor or jamFactor for backward compatibility)
                    jam_factor = float(row.get('flow_jam_factor', row.get('jamFactor', 0.0)))
                    
                    # Get speed (use flow_speed_kph or speed_kph)
                    speed = float(row.get('flow_speed_kph', row.get('speed_kph', 0.0)))
                    
                    # Get road name
                    road_name = str(row.get('road_name', 'Unknown')).replace(' ', '_')
                    
                    # Skip invalid entries
                    if source == 0 or target == 0:
                        continue
                    
                    # Write entry: source target jam_factor speed road_name
                    f.write(f"{source} {target} {jam_factor:.2f} {speed:.2f} {road_name}\n")
                
                except (ValueError, TypeError) as e:
                    print(f"   ⚠️  Skipping row {idx}: {e}")
                    continue
        
        print(f"   ✅ Generated {disruption_type} .gr file: {output_file.name} ({len(df)} disruptions)")
        
        # Clean up old .gr files (keep only 5 most recent)
        old_files = sorted(output_dir.glob(f'{prefix}_*.gr'), reverse=True)[5:]
        for old_file in old_files:
            try:
                old_file.unlink()
                print(f"   🗑️  Removed old {disruption_type} .gr file: {old_file.name}")
            except Exception as e:
                print(f"   ⚠️  Failed to remove {old_file.name}: {e}")
        
        return output_file
        
    except Exception as e:
        print(f"   ❌ Error generating {disruption_type} .gr file: {e}")
        import traceback
        traceback.print_exc()
        return None
