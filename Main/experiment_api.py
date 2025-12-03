"""
Experiment Automation API Endpoints

This module provides Flask API endpoints for the experiment automation system:
- Configuration management (CRUD operations)
- Wizard step validation
- Experiment execution control (start, pause, stop)
- Real-time progress streaming
- Results and metrics export

All endpoints are prefixed with /api/experiment/
"""

import json
import threading
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from pathlib import Path
from typing import Dict, Any, Optional, Generator

# Import experiment system modules
from experiment_config import (
    ExperimentConfig,
    ExperimentConfigManager,
    get_config_manager,
    ConfigValidationError,
    TrialConfig,
    BatchConfig,
    DisruptionConfig,
    TauConfig,
    PointsConfig,
    TrafficIncidentConfig,
    RoadClosureConfig,
    CongestionConfig,
    LocationPoint
)

from experiment_engine import (
    ExperimentEngine,
    ExperimentStatus,
    ExperimentProgress,
    get_experiment_engine,
    init_experiment_engine
)

from metrics_collector import (
    MetricsCollector,
    init_metrics_collector,
    get_metrics_collector
)

from appendix_generator import (
    AppendixGenerator,
    create_appendix_generator
)

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Create Blueprint
experiment_bp = Blueprint('experiment', __name__, url_prefix='/api/experiment')

# Global experiment state
_current_experiment_thread: Optional[threading.Thread] = None
_experiment_results: Dict[str, Any] = {}


# =============================================================================
# Configuration Management Endpoints
# =============================================================================

@experiment_bp.route('/configs', methods=['GET'])
def list_configs():
    """
    List all available experiment configurations.
    
    Returns:
        List of configuration summaries with metadata
    """
    try:
        manager = get_config_manager()
        configs = manager.list_configs()
        
        return jsonify({
            'success': True,
            'configs': configs,
            'count': len(configs)
        })
    except Exception as e:
        logger.error(f"Error listing configs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/configs/<filename>', methods=['GET'])
def get_config(filename: str):
    """
    Get a specific configuration by filename.
    
    Args:
        filename: Configuration filename (with or without .json)
    
    Returns:
        Full configuration object
    """
    try:
        manager = get_config_manager()
        config = manager.load_config(filename)
        
        return jsonify({
            'success': True,
            'config': manager._config_to_dict(config),
            'summary': config.get_summary()
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'Configuration not found: {filename}'
        }), 404
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/configs', methods=['POST'])
def save_config():
    """
    Save a new experiment configuration.
    
    Request Body:
        JSON configuration object
    
    Returns:
        Saved configuration with filepath
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No configuration data provided'
            }), 400
        
        manager = get_config_manager()
        config = manager._dict_to_config(data)
        
        # Validate
        is_valid, errors = manager.validate_config(config)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Configuration validation failed',
                'validation_errors': errors
            }), 400
        
        # Save
        filepath = manager.save_config(config)
        
        return jsonify({
            'success': True,
            'message': f'Configuration saved successfully',
            'filepath': str(filepath),
            'config_id': config.config_id,
            'summary': config.get_summary()
        })
    except ConfigValidationError as e:
        return jsonify({
            'success': False,
            'error': e.message,
            'validation_errors': e.errors
        }), 400
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/configs/<filename>', methods=['DELETE'])
def delete_config(filename: str):
    """
    Delete an experiment configuration.
    
    Args:
        filename: Configuration filename
    
    Returns:
        Success status
    """
    try:
        manager = get_config_manager()
        deleted = manager.delete_config(filename)
        
        if deleted:
            return jsonify({
                'success': True,
                'message': f'Configuration deleted: {filename}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Configuration not found: {filename}'
            }), 404
    except Exception as e:
        logger.error(f"Error deleting config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/configs/<filename>/duplicate', methods=['POST'])
def duplicate_config(filename: str):
    """
    Duplicate an existing configuration with a new name.
    
    Args:
        filename: Source configuration filename
    
    Request Body:
        {"new_name": "optional new experiment name"}
    
    Returns:
        New configuration summary
    """
    try:
        data = request.get_json() or {}
        new_name = data.get('new_name')
        
        manager = get_config_manager()
        new_config = manager.duplicate_config(filename, new_name)
        filepath = manager.save_config(new_config)
        
        return jsonify({
            'success': True,
            'message': 'Configuration duplicated',
            'filepath': str(filepath),
            'config_id': new_config.config_id,
            'summary': new_config.get_summary()
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': f'Source configuration not found: {filename}'
        }), 404
    except Exception as e:
        logger.error(f"Error duplicating config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/configs/default', methods=['GET'])
def get_default_config():
    """
    Get a new configuration with default values.
    
    Returns:
        Default configuration object
    """
    try:
        manager = get_config_manager()
        config = manager.create_default_config()
        
        return jsonify({
            'success': True,
            'config': manager._config_to_dict(config),
            'summary': config.get_summary()
        })
    except Exception as e:
        logger.error(f"Error creating default config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Wizard Validation Endpoints
# =============================================================================

@experiment_bp.route('/validate/locations', methods=['POST'])
def validate_locations():
    """
    Validate Step 1: Locations Configuration.
    
    Request Body:
        points_config object
    
    Returns:
        Validation result with any errors
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'valid': False,
                'errors': ['No data provided']
            }), 400
        
        errors = []
        warnings = []
        
        # Validate bounds
        bounds = data.get('random_bounds', {})
        lat_min = bounds.get('lat_min', 0)
        lat_max = bounds.get('lat_max', 0)
        lon_min = bounds.get('lon_min', 0)
        lon_max = bounds.get('lon_max', 0)
        
        if lat_min >= lat_max:
            errors.append("Latitude min must be less than max")
        if lon_min >= lon_max:
            errors.append("Longitude min must be less than max")
        
        # Validate QC bounds
        if lat_min < 14.5 or lat_max > 14.9:
            warnings.append("Latitude bounds extend beyond typical Quezon City area")
        if lon_min < 120.9 or lon_max > 121.2:
            warnings.append("Longitude bounds extend beyond typical Quezon City area")
        
        # Validate counts
        preset_count = data.get('preset_pairs_count', 0)
        random_count = data.get('random_pairs_count', 0)
        
        if preset_count + random_count < 10:
            errors.append("At least 10 total query pairs required")
        if preset_count + random_count > 10000:
            warnings.append("Large query count (>10000) may impact performance")
        
        return jsonify({
            'success': True,
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_queries': preset_count + random_count
        })
    except Exception as e:
        logger.error(f"Error validating locations: {e}")
        return jsonify({
            'success': False,
            'valid': False,
            'errors': [str(e)]
        }), 500


@experiment_bp.route('/validate/disruptions', methods=['POST'])
def validate_disruptions():
    """
    Validate Step 2: Traffic & Disruptions Configuration.
    
    Request Body:
        disruption_config object
    
    Returns:
        Validation result
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'valid': False,
                'errors': ['No data provided']
            }), 400
        
        errors = []
        warnings = []
        
        # Validate type
        valid_types = ["TRAFFIC_ONLY", "CLOSURES_ONLY", "CONGESTION_ONLY", "MIXED", "CUSTOM"]
        disruption_type = data.get('type', '')
        if disruption_type not in valid_types:
            errors.append(f"Invalid disruption type: {disruption_type}")
        
        # Validate traffic incidents
        traffic = data.get('traffic_incidents', {})
        if traffic.get('mode') == 'RANDOM':
            count = traffic.get('count', 0)
            if count < 0:
                errors.append("Traffic incident count cannot be negative")
            if count > 5000:
                warnings.append("High traffic incident count may slow down experiments")
            
            severity_min = traffic.get('severity_min', 0)
            severity_max = traffic.get('severity_max', 1)
            if severity_min >= severity_max:
                errors.append("Severity min must be less than max")
            if severity_min < 0 or severity_max > 1:
                errors.append("Severity must be between 0 and 1")
        
        # Validate congestion
        congestion = data.get('congestion', {})
        if congestion.get('mode') == 'RANDOM':
            intensity_min = congestion.get('intensity_min', 0)
            intensity_max = congestion.get('intensity_max', 1)
            if intensity_min >= intensity_max:
                errors.append("Intensity min must be less than max")
            if intensity_min < 0 or intensity_max > 1:
                errors.append("Intensity must be between 0 and 1")
        
        return jsonify({
            'success': True,
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        })
    except Exception as e:
        logger.error(f"Error validating disruptions: {e}")
        return jsonify({
            'success': False,
            'valid': False,
            'errors': [str(e)]
        }), 500


@experiment_bp.route('/validate/parameters', methods=['POST'])
def validate_parameters():
    """
    Validate Step 3: Algorithm & Parameters Configuration.
    
    Request Body:
        trial_config, batch_config, tau_config objects
    
    Returns:
        Validation result with calculated totals
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'valid': False,
                'errors': ['No data provided']
            }), 400
        
        errors = []
        warnings = []
        
        # Validate trial config
        trial = data.get('trial_config', {})
        num_trials = trial.get('num_trials', 0)
        algorithms = trial.get('algorithms', [])
        
        if num_trials < 1 or num_trials > 10:
            errors.append("Number of trials must be between 1 and 10")
        
        valid_algorithms = ["DHL", "HC2L", "D-HC2L", "D-DHL"]
        for algo in algorithms:
            if algo not in valid_algorithms:
                errors.append(f"Invalid algorithm: {algo}")
        
        if len(algorithms) < 1:
            errors.append("At least one algorithm must be selected")
        
        # Validate batch config
        batch = data.get('batch_config', {})
        num_batches = batch.get('num_batches', 0)
        disruptions_per_batch = batch.get('disruptions_per_batch', 0)
        queries_per_batch = batch.get('queries_per_batch', 0)
        
        if num_batches < 1 or num_batches > 10:
            errors.append("Number of batches must be between 1 and 10")
        
        if disruptions_per_batch < 100 or disruptions_per_batch > 5000:
            errors.append("Disruptions per batch must be between 100 and 5000")
        
        if queries_per_batch < 100 or queries_per_batch > 5000:
            errors.append("Queries per batch must be between 100 and 5000")
        
        # Validate tau config
        tau = data.get('tau_config', {})
        tau_type = tau.get('type', 'FIXED')
        
        if tau_type == "FIXED":
            fixed_value = tau.get('fixed_value', 0.5)
            if fixed_value < 0 or fixed_value > 1:
                errors.append("Fixed tau value must be between 0 and 1")
        elif tau_type in ["DYNAMIC", "RANDOM"]:
            random_min = tau.get('random_min', 0)
            random_max = tau.get('random_max', 1)
            if random_min >= random_max:
                errors.append("Tau random_min must be less than random_max")
            if random_min < 0 or random_max > 1:
                errors.append("Tau range must be between 0 and 1")
        
        # Calculate totals
        num_algorithms = len(algorithms) if algorithms else 2
        total_disruptions = num_batches * disruptions_per_batch * num_trials * num_algorithms
        total_queries = num_batches * queries_per_batch * num_trials * num_algorithms
        total_batches = num_batches * num_trials * num_algorithms
        
        # Estimate duration (rough estimate: 10ms per query + 100ms per disruption batch)
        estimated_seconds = (total_queries * 0.01) + (total_batches * 10)
        estimated_minutes = estimated_seconds / 60
        
        if estimated_minutes > 60:
            warnings.append(f"Estimated duration is over 1 hour ({estimated_minutes:.0f} minutes)")
        
        return jsonify({
            'success': True,
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'totals': {
                'total_disruptions': total_disruptions,
                'total_queries': total_queries,
                'total_batches': total_batches,
                'estimated_duration_minutes': round(estimated_minutes, 1)
            }
        })
    except Exception as e:
        logger.error(f"Error validating parameters: {e}")
        return jsonify({
            'success': False,
            'valid': False,
            'errors': [str(e)]
        }), 500


@experiment_bp.route('/validate/full', methods=['POST'])
def validate_full_config():
    """
    Validate a complete experiment configuration.
    
    Request Body:
        Full experiment configuration object
    
    Returns:
        Complete validation result
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'valid': False,
                'errors': ['No configuration provided']
            }), 400
        
        manager = get_config_manager()
        config = manager._dict_to_config(data)
        is_valid, errors = manager.validate_config(config)
        
        return jsonify({
            'success': True,
            'valid': is_valid,
            'errors': errors,
            'summary': config.get_summary() if is_valid else None
        })
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return jsonify({
            'success': False,
            'valid': False,
            'errors': [str(e)]
        }), 500


# =============================================================================
# Experiment Execution Endpoints
# =============================================================================

@experiment_bp.route('/start', methods=['POST'])
def start_experiment():
    """
    Start an experiment run.
    
    Request Body:
        Either a config filename or full configuration object
        {"config_file": "filename.json"} or {"config": {...}}
    
    Returns:
        Experiment ID and initial status
    """
    global _current_experiment_thread, _experiment_results
    
    try:
        engine = get_experiment_engine()
        
        # Check if experiment already running
        if engine.is_running():
            return jsonify({
                'success': False,
                'error': 'An experiment is already running. Stop it first or wait for completion.'
            }), 409
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No configuration provided'
            }), 400
        
        # Load configuration
        manager = get_config_manager()
        
        if 'config_file' in data:
            config = manager.load_config(data['config_file'])
        elif 'config' in data:
            config = manager._dict_to_config(data['config'])
        else:
            return jsonify({
                'success': False,
                'error': 'Provide either config_file or config'
            }), 400
        
        # Validate configuration
        is_valid, errors = manager.validate_config(config)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid configuration',
                'validation_errors': errors
            }), 400
        
        # Initialize metrics collector
        experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        init_metrics_collector(experiment_id)
        
        # Start experiment in background thread
        def run_experiment():
            global _experiment_results
            try:
                results = engine.run_experiment(config)
                _experiment_results[experiment_id] = results
                
                # Generate appendices
                collector = get_metrics_collector()
                if collector:
                    generator = create_appendix_generator(collector)
                    appendices = generator.generate_all_appendices()
                    _experiment_results[experiment_id]['appendices'] = appendices
            except Exception as e:
                logger.error(f"Experiment failed: {e}")
                _experiment_results[experiment_id] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        _current_experiment_thread = threading.Thread(target=run_experiment, daemon=True)
        _current_experiment_thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Experiment started',
            'experiment_id': experiment_id,
            'config_summary': config.get_summary()
        })
    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'error': f'Configuration file not found: {e}'
        }), 404
    except Exception as e:
        logger.error(f"Error starting experiment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/status', methods=['GET'])
def get_experiment_status():
    """
    Get current experiment status and progress.
    
    Returns:
        Current status, progress metrics, and any results
    """
    try:
        engine = get_experiment_engine()
        progress = engine.get_progress()
        
        response = {
            'success': True,
            'status': engine.get_status().value,
            'is_running': engine.is_running(),
            'is_paused': engine.is_paused()
        }
        
        if progress:
            response['progress'] = {
                'experiment_id': progress.experiment_id,
                'current_algorithm': progress.current_algorithm,
                'current_trial': progress.current_trial,
                'total_trials': progress.total_trials,
                'current_batch': progress.current_batch,
                'total_batches': progress.total_batches,
                'current_phase': progress.current_phase.value,
                'disruptions_processed': progress.disruptions_processed,
                'disruptions_total': progress.disruptions_total,
                'queries_processed': progress.queries_processed,
                'queries_total': progress.queries_total,
                'current_update_time_ms': progress.current_update_time_ms,
                'current_label_size_mb': progress.current_label_size_mb,
                'current_avg_query_time_ms': progress.current_avg_query_time_ms,
                'elapsed_seconds': progress.elapsed_seconds,
                'estimated_remaining_seconds': progress.estimated_remaining_seconds
            }
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/pause', methods=['POST'])
def pause_experiment():
    """
    Pause the current experiment.
    
    Returns:
        New status
    """
    try:
        engine = get_experiment_engine()
        
        if not engine.is_running():
            return jsonify({
                'success': False,
                'error': 'No experiment is currently running'
            }), 400
        
        engine.pause()
        
        return jsonify({
            'success': True,
            'message': 'Experiment pause requested',
            'status': engine.get_status().value
        })
    except Exception as e:
        logger.error(f"Error pausing experiment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/resume', methods=['POST'])
def resume_experiment():
    """
    Resume a paused experiment.
    
    Returns:
        New status
    """
    try:
        engine = get_experiment_engine()
        
        if not engine.is_paused():
            return jsonify({
                'success': False,
                'error': 'Experiment is not paused'
            }), 400
        
        engine.resume()
        
        return jsonify({
            'success': True,
            'message': 'Experiment resumed',
            'status': engine.get_status().value
        })
    except Exception as e:
        logger.error(f"Error resuming experiment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/stop', methods=['POST'])
def stop_experiment():
    """
    Stop the current experiment.
    
    Returns:
        Final status and partial results
    """
    try:
        engine = get_experiment_engine()
        
        if not engine.is_running() and not engine.is_paused():
            return jsonify({
                'success': False,
                'error': 'No experiment is currently running'
            }), 400
        
        engine.stop()
        
        return jsonify({
            'success': True,
            'message': 'Experiment stop requested',
            'status': engine.get_status().value
        })
    except Exception as e:
        logger.error(f"Error stopping experiment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Results & Export Endpoints
# =============================================================================

@experiment_bp.route('/results/<experiment_id>', methods=['GET'])
def get_experiment_results(experiment_id: str):
    """
    Get results for a specific experiment.
    
    Args:
        experiment_id: Experiment ID
    
    Returns:
        Full experiment results
    """
    try:
        if experiment_id in _experiment_results:
            return jsonify({
                'success': True,
                'results': _experiment_results[experiment_id]
            })
        else:
            # Try to load from file
            results_dir = Path(__file__).parent / "data" / "experiment_results" / experiment_id
            summary_path = results_dir / "summary.json"
            
            if summary_path.exists():
                with open(summary_path) as f:
                    summary = json.load(f)
                return jsonify({
                    'success': True,
                    'results': summary
                })
            
            return jsonify({
                'success': False,
                'error': f'Experiment not found: {experiment_id}'
            }), 404
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/results/<experiment_id>/export', methods=['GET'])
def export_results(experiment_id: str):
    """
    Export experiment results to files.
    
    Args:
        experiment_id: Experiment ID
    
    Query Params:
        format: csv, json, or all (default: all)
    
    Returns:
        List of exported file paths
    """
    try:
        collector = get_metrics_collector()
        
        if collector is None or collector.experiment_id != experiment_id:
            return jsonify({
                'success': False,
                'error': 'Metrics not available for this experiment'
            }), 404
        
        exports = collector.export_to_csv()
        
        return jsonify({
            'success': True,
            'message': 'Results exported',
            'files': {k: str(v) for k, v in exports.items()}
        })
    except Exception as e:
        logger.error(f"Error exporting results: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@experiment_bp.route('/results/<experiment_id>/appendices', methods=['GET'])
def get_appendices(experiment_id: str):
    """
    Get generated appendix tables.
    
    Args:
        experiment_id: Experiment ID
    
    Returns:
        All appendix data
    """
    try:
        # Check in-memory results first
        if experiment_id in _experiment_results:
            results = _experiment_results[experiment_id]
            if 'appendices' in results:
                return jsonify({
                    'success': True,
                    'appendices': results['appendices']
                })
        
        # Try to load from file
        results_dir = Path(__file__).parent / "data" / "experiment_results" / experiment_id
        appendix_path = results_dir / "all_appendices.json"
        
        if appendix_path.exists():
            with open(appendix_path) as f:
                appendices = json.load(f)
            return jsonify({
                'success': True,
                'appendices': appendices
            })
        
        return jsonify({
            'success': False,
            'error': 'Appendices not found for this experiment'
        }), 404
    except Exception as e:
        logger.error(f"Error getting appendices: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Real-Time Progress Stream (Server-Sent Events)
# =============================================================================

@experiment_bp.route('/progress/stream')
def progress_stream():
    """
    Stream real-time experiment progress using Server-Sent Events.
    
    Returns:
        SSE stream of progress updates
    """
    def generate() -> Generator[str, None, None]:
        engine = get_experiment_engine()
        last_update = 0
        
        while True:
            try:
                current_time = time.time()
                
                # Send update every 500ms
                if current_time - last_update >= 0.5:
                    progress = engine.get_progress()
                    status = engine.get_status()
                    
                    data = {
                        'status': status.value,
                        'is_running': engine.is_running(),
                        'timestamp': current_time
                    }
                    
                    if progress:
                        data['progress'] = {
                            'experiment_id': progress.experiment_id,
                            'current_algorithm': progress.current_algorithm,
                            'current_trial': progress.current_trial,
                            'total_trials': progress.total_trials,
                            'current_batch': progress.current_batch,
                            'total_batches': progress.total_batches,
                            'current_phase': progress.current_phase.value,
                            'disruptions_processed': progress.disruptions_processed,
                            'disruptions_total': progress.disruptions_total,
                            'queries_processed': progress.queries_processed,
                            'queries_total': progress.queries_total,
                            'current_update_time_ms': round(progress.current_update_time_ms, 2),
                            'current_avg_query_time_ms': round(progress.current_avg_query_time_ms, 3)
                        }
                        
                        if progress.last_route_geometry:
                            data['last_route'] = {
                                'geometry': progress.last_route_geometry[:10]  # Limit for performance
                            }
                    
                    yield f"data: {json.dumps(data)}\n\n"
                    last_update = current_time
                
                # Stop streaming if experiment completed
                if status in [ExperimentStatus.COMPLETED, 
                             ExperimentStatus.FAILED, 
                             ExperimentStatus.CANCELLED]:
                    yield f"data: {json.dumps({'status': status.value, 'complete': True})}\n\n"
                    break
                
                time.sleep(0.1)
                
            except GeneratorExit:
                break
            except Exception as e:
                logger.error(f"Error in progress stream: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                break
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# =============================================================================
# Utility Endpoints
# =============================================================================

@experiment_bp.route('/preset-locations', methods=['GET'])
def get_preset_locations():
    """
    Get available preset location sets for the wizard.
    
    Returns:
        List of preset location sets
    """
    # Predefined important locations in Quezon City
    preset_locations = {
        "qc_landmarks": {
            "name": "QC Major Landmarks",
            "locations": [
                {"name": "Quezon Memorial Circle", "lat": 14.6515, "lon": 121.0494},
                {"name": "Eastwood City", "lat": 14.6095, "lon": 121.0809},
                {"name": "Trinoma Mall", "lat": 14.6527, "lon": 121.0354},
                {"name": "SM North EDSA", "lat": 14.6567, "lon": 121.0294},
                {"name": "UP Diliman", "lat": 14.6538, "lon": 121.0685},
                {"name": "Ateneo de Manila", "lat": 14.6399, "lon": 121.0788},
                {"name": "Cubao Gateway", "lat": 14.6182, "lon": 121.0553},
                {"name": "Camp Crame", "lat": 14.6070, "lon": 121.0471}
            ]
        },
        "qc_intersections": {
            "name": "Major Intersections",
            "locations": [
                {"name": "EDSA-Aurora", "lat": 14.6148, "lon": 121.0518},
                {"name": "EDSA-Timog", "lat": 14.6330, "lon": 121.0349},
                {"name": "Commonwealth-Tandang Sora", "lat": 14.6769, "lon": 121.0494},
                {"name": "Katipunan-Aurora", "lat": 14.6289, "lon": 121.0736},
                {"name": "C5-Katipunan", "lat": 14.6321, "lon": 121.0794}
            ]
        },
        "qc_districts": {
            "name": "District Centers",
            "locations": [
                {"name": "District 1 (Project 6)", "lat": 14.6449, "lon": 121.0225},
                {"name": "District 2 (Novaliches)", "lat": 14.7012, "lon": 121.0457},
                {"name": "District 3 (Fairview)", "lat": 14.7132, "lon": 121.0714},
                {"name": "District 4 (Cubao)", "lat": 14.6193, "lon": 121.0558},
                {"name": "District 5 (Bagumbayan)", "lat": 14.6024, "lon": 121.0616},
                {"name": "District 6 (Batasan)", "lat": 14.6790, "lon": 121.0859}
            ]
        }
    }
    
    return jsonify({
        'success': True,
        'preset_sets': preset_locations
    })


@experiment_bp.route('/estimate-duration', methods=['POST'])
def estimate_duration():
    """
    Estimate experiment duration based on configuration.
    
    Request Body:
        Configuration parameters
    
    Returns:
        Estimated duration and resource requirements
    """
    try:
        data = request.get_json()
        
        num_trials = data.get('num_trials', 3)
        num_batches = data.get('num_batches', 3)
        num_algorithms = len(data.get('algorithms', ['DHL', 'HC2L']))
        disruptions_per_batch = data.get('disruptions_per_batch', 1000)
        queries_per_batch = data.get('queries_per_batch', 1000)
        
        # Calculate totals
        total_batches = num_trials * num_batches * num_algorithms
        total_queries = total_batches * queries_per_batch
        total_disruptions = total_batches * disruptions_per_batch
        
        # Estimate time (based on typical performance)
        # Query: ~1-2ms average
        # Disruption processing: ~0.5ms each
        # Batch overhead: ~5s
        estimated_query_time = total_queries * 0.002  # seconds
        estimated_disruption_time = total_disruptions * 0.0005  # seconds
        estimated_overhead = total_batches * 5  # seconds
        
        total_seconds = estimated_query_time + estimated_disruption_time + estimated_overhead
        total_minutes = total_seconds / 60
        
        # Resource estimates
        memory_mb = 256 + (num_algorithms * 100)  # Base + per algorithm
        disk_mb = total_queries * 0.001 + total_disruptions * 0.0001  # Results storage
        
        return jsonify({
            'success': True,
            'totals': {
                'batches': total_batches,
                'queries': total_queries,
                'disruptions': total_disruptions
            },
            'estimates': {
                'duration_seconds': round(total_seconds, 0),
                'duration_minutes': round(total_minutes, 1),
                'duration_formatted': f"{int(total_minutes // 60)}h {int(total_minutes % 60)}m" if total_minutes > 60 else f"{int(total_minutes)}m"
            },
            'resources': {
                'memory_mb': round(memory_mb, 0),
                'disk_mb': round(disk_mb, 1),
                'cpu_recommended': 4
            }
        })
    except Exception as e:
        logger.error(f"Error estimating duration: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def register_experiment_endpoints(app):
    """
    Register experiment API endpoints with the Flask app.
    
    Args:
        app: Flask application instance
    """
    app.register_blueprint(experiment_bp)
    logger.info("Experiment API endpoints registered")


# For direct import
__all__ = ['experiment_bp', 'register_experiment_endpoints']
