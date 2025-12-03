"""
Experiment Configuration System for DHL vs HC2L Benchmarking

This module handles loading, saving, and validating experiment configurations
for batch processing experiments. Configs are stored as JSON files in
/Main/configs/experiments/

Configuration Structure:
- Trial configuration (algorithms, count)
- Batch configuration (batches per trial, disruptions per batch)
- Disruption configuration (random/custom, types, severity)
- Tau configuration (fixed/dynamic/random)
- Points configuration (preset/random/mixed locations)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
import uuid
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Default config directory
CONFIG_DIR = Path(__file__).parent / "configs" / "experiments"


@dataclass
class TrafficIncidentConfig:
    """Configuration for random traffic incidents."""
    mode: str = "RANDOM"  # RANDOM or DISABLED
    count: int = 500
    severity_min: float = 0.2
    severity_max: float = 0.9


@dataclass
class RoadClosureConfig:
    """Configuration for road closures (random or custom locations)."""
    mode: str = "RANDOM"  # RANDOM, CUSTOM, or DISABLED
    count: int = 100  # For RANDOM mode
    locations: List[str] = field(default_factory=list)  # For CUSTOM mode (edge IDs)
    durations: List[int] = field(default_factory=lambda: [30, 45, 60])  # Duration in minutes


@dataclass
class CongestionConfig:
    """Configuration for congestion zones."""
    mode: str = "RANDOM"  # RANDOM or DISABLED
    count: int = 500
    intensity_min: float = 0.3
    intensity_max: float = 0.8


@dataclass
class DisruptionConfig:
    """Complete disruption configuration."""
    type: str = "MIXED"  # TRAFFIC_ONLY, CLOSURES_ONLY, CONGESTION_ONLY, MIXED, CUSTOM
    traffic_incidents: TrafficIncidentConfig = field(default_factory=TrafficIncidentConfig)
    road_closures: RoadClosureConfig = field(default_factory=RoadClosureConfig)
    congestion: CongestionConfig = field(default_factory=CongestionConfig)
    random_seed: Optional[int] = None  # For reproducibility


@dataclass
class TauConfig:
    """Tau (threshold) configuration for lazy updates."""
    type: str = "FIXED"  # FIXED, DYNAMIC, RANDOM
    fixed_value: float = 0.5
    per_batch_values: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # For DYNAMIC: {"batch_1": {"min": 0.3, "max": 0.5}, ...}
    random_min: float = 0.3
    random_max: float = 0.7
    randomize_per_trial: bool = True


@dataclass
class LocationPoint:
    """A single location point."""
    name: str
    lat: float
    lon: float
    is_preset: bool = True


@dataclass
class PointsConfig:
    """Configuration for origin-destination points."""
    type: str = "MIXED"  # PRESET, RANDOM, MIXED
    preset_pairs_count: int = 500
    random_pairs_count: int = 500
    preset_locations: List[LocationPoint] = field(default_factory=list)
    random_bounds: Dict[str, float] = field(default_factory=lambda: {
        "lat_min": 14.57,
        "lat_max": 14.78,
        "lon_min": 120.98,
        "lon_max": 121.12
    })


@dataclass
class TrialConfig:
    """Trial configuration."""
    num_trials: int = 3
    algorithms: List[str] = field(default_factory=lambda: ["DHL", "HC2L"])


@dataclass
class BatchConfig:
    """Batch configuration."""
    num_batches: int = 3
    disruptions_per_batch: int = 1000
    queries_per_batch: int = 1000


@dataclass
class ExperimentConfig:
    """Complete experiment configuration."""
    experiment_name: str = "Unnamed_Experiment"
    description: str = ""
    created_at: str = ""
    last_modified: str = ""
    config_id: str = ""
    
    trial_config: TrialConfig = field(default_factory=TrialConfig)
    batch_config: BatchConfig = field(default_factory=BatchConfig)
    disruption_config: DisruptionConfig = field(default_factory=DisruptionConfig)
    tau_config: TauConfig = field(default_factory=TauConfig)
    points_config: PointsConfig = field(default_factory=PointsConfig)
    
    # Calculated properties (not stored, computed on load)
    _total_disruptions: int = field(default=0, init=False, repr=False)
    _total_queries: int = field(default=0, init=False, repr=False)
    
    def __post_init__(self):
        if not self.config_id:
            self.config_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.last_modified = datetime.now().isoformat()
        self._calculate_totals()
    
    def _calculate_totals(self):
        """Calculate total disruptions and queries based on config."""
        # Total = batches × disruptions_per_batch × trials × algorithms
        num_algorithms = len(self.trial_config.algorithms)
        self._total_disruptions = (
            self.batch_config.num_batches * 
            self.batch_config.disruptions_per_batch * 
            self.trial_config.num_trials * 
            num_algorithms
        )
        self._total_queries = (
            self.batch_config.num_batches * 
            self.batch_config.queries_per_batch * 
            self.trial_config.num_trials * 
            num_algorithms
        )
    
    @property
    def total_disruptions(self) -> int:
        return self._total_disruptions
    
    @property
    def total_queries(self) -> int:
        return self._total_queries
    
    @property
    def total_batches(self) -> int:
        return (
            self.batch_config.num_batches * 
            self.trial_config.num_trials * 
            len(self.trial_config.algorithms)
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the experiment configuration."""
        return {
            "experiment_name": self.experiment_name,
            "description": self.description,
            "config_id": self.config_id,
            "trials": self.trial_config.num_trials,
            "algorithms": self.trial_config.algorithms,
            "batches_per_trial": self.batch_config.num_batches,
            "disruptions_per_batch": self.batch_config.disruptions_per_batch,
            "queries_per_batch": self.batch_config.queries_per_batch,
            "total_disruptions": self.total_disruptions,
            "total_queries": self.total_queries,
            "total_batches": self.total_batches,
            "disruption_type": self.disruption_config.type,
            "tau_type": self.tau_config.type,
            "tau_value": self.tau_config.fixed_value if self.tau_config.type == "FIXED" else "variable",
            "points_type": self.points_config.type,
            "created_at": self.created_at,
            "last_modified": self.last_modified
        }


class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""
    def __init__(self, message: str, errors: List[str] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


class ExperimentConfigManager:
    """
    Manages experiment configurations - loading, saving, validation.
    """
    
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ExperimentConfigManager initialized with dir: {self.config_dir}")
    
    def _dict_to_config(self, data: Dict) -> ExperimentConfig:
        """Convert a dictionary to an ExperimentConfig object."""
        # Handle nested dataclasses
        trial_config = TrialConfig(**data.get("trial_config", {}))
        batch_config = BatchConfig(**data.get("batch_config", {}))
        
        # Disruption config with nested objects
        disruption_data = data.get("disruption_config", {})
        traffic_incidents = TrafficIncidentConfig(
            **disruption_data.get("traffic_incidents", disruption_data.get("options", {}).get("traffic_incidents", {}))
        ) if "traffic_incidents" in disruption_data or "options" in disruption_data else TrafficIncidentConfig()
        
        road_closures = RoadClosureConfig(
            **disruption_data.get("road_closures", disruption_data.get("options", {}).get("road_closures", {}))
        ) if "road_closures" in disruption_data or "options" in disruption_data else RoadClosureConfig()
        
        congestion = CongestionConfig(
            **disruption_data.get("congestion", disruption_data.get("options", {}).get("congestion_zones", {}))
        ) if "congestion" in disruption_data or "options" in disruption_data else CongestionConfig()
        
        disruption_config = DisruptionConfig(
            type=disruption_data.get("type", "MIXED"),
            traffic_incidents=traffic_incidents,
            road_closures=road_closures,
            congestion=congestion,
            random_seed=disruption_data.get("random_seed")
        )
        
        # Tau config
        tau_data = data.get("tau_config", {})
        tau_type = tau_data.get("type", "FIXED")
        
        # Handle both flat and nested tau config formats
        options = tau_data.get("options", {})
        tau_config = TauConfig(
            type=tau_type,
            fixed_value=tau_data.get("fixed_value", tau_data.get("value", 0.5)),
            per_batch_values=options.get("values", tau_data.get("per_batch_values", {})),
            random_min=options.get("random_min", tau_data.get("random_min", 0.3)),
            random_max=options.get("random_max", tau_data.get("random_max", 0.7)),
            randomize_per_trial=options.get("randomize_per_trial", tau_data.get("randomize_per_trial", True))
        )
        
        # Points config
        points_data = data.get("points_config", {})
        points_options = points_data.get("options", {})
        preset_locations = []
        for loc in points_options.get("preset_locations", points_data.get("preset_locations", [])):
            if isinstance(loc, dict):
                preset_locations.append(LocationPoint(
                    name=loc.get("name", ""),
                    lat=loc.get("lat", 0),
                    lon=loc.get("lon", loc.get("lng", 0)),
                    is_preset=loc.get("is_preset", True)
                ))
        
        points_config = PointsConfig(
            type=points_data.get("type", "MIXED"),
            preset_pairs_count=points_options.get("preset_pairs", points_data.get("preset_pairs_count", 500)),
            random_pairs_count=points_options.get("random_pairs", points_data.get("random_pairs_count", 500)),
            preset_locations=preset_locations,
            random_bounds=points_options.get("random_bounds", points_data.get("random_bounds", {}))
        )
        
        return ExperimentConfig(
            experiment_name=data.get("experiment_name", "Unnamed_Experiment"),
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            last_modified=data.get("last_modified", ""),
            config_id=data.get("config_id", ""),
            trial_config=trial_config,
            batch_config=batch_config,
            disruption_config=disruption_config,
            tau_config=tau_config,
            points_config=points_config
        )
    
    def _config_to_dict(self, config: ExperimentConfig) -> Dict:
        """Convert an ExperimentConfig object to a dictionary for JSON storage."""
        # Convert location points
        preset_locs = [
            {"name": loc.name, "lat": loc.lat, "lon": loc.lon, "is_preset": loc.is_preset}
            for loc in config.points_config.preset_locations
        ]
        
        return {
            "experiment_name": config.experiment_name,
            "description": config.description,
            "created_at": config.created_at,
            "last_modified": datetime.now().isoformat(),
            "config_id": config.config_id,
            "trial_config": {
                "num_trials": config.trial_config.num_trials,
                "algorithms": config.trial_config.algorithms
            },
            "batch_config": {
                "num_batches": config.batch_config.num_batches,
                "disruptions_per_batch": config.batch_config.disruptions_per_batch,
                "queries_per_batch": config.batch_config.queries_per_batch
            },
            "disruption_config": {
                "type": config.disruption_config.type,
                "traffic_incidents": {
                    "mode": config.disruption_config.traffic_incidents.mode,
                    "count": config.disruption_config.traffic_incidents.count,
                    "severity_min": config.disruption_config.traffic_incidents.severity_min,
                    "severity_max": config.disruption_config.traffic_incidents.severity_max
                },
                "road_closures": {
                    "mode": config.disruption_config.road_closures.mode,
                    "count": config.disruption_config.road_closures.count,
                    "locations": config.disruption_config.road_closures.locations,
                    "durations": config.disruption_config.road_closures.durations
                },
                "congestion": {
                    "mode": config.disruption_config.congestion.mode,
                    "count": config.disruption_config.congestion.count,
                    "intensity_min": config.disruption_config.congestion.intensity_min,
                    "intensity_max": config.disruption_config.congestion.intensity_max
                },
                "random_seed": config.disruption_config.random_seed
            },
            "tau_config": {
                "type": config.tau_config.type,
                "fixed_value": config.tau_config.fixed_value,
                "per_batch_values": config.tau_config.per_batch_values,
                "random_min": config.tau_config.random_min,
                "random_max": config.tau_config.random_max,
                "randomize_per_trial": config.tau_config.randomize_per_trial
            },
            "points_config": {
                "type": config.points_config.type,
                "preset_pairs_count": config.points_config.preset_pairs_count,
                "random_pairs_count": config.points_config.random_pairs_count,
                "preset_locations": preset_locs,
                "random_bounds": config.points_config.random_bounds
            }
        }
    
    def validate_config(self, config: ExperimentConfig) -> Tuple[bool, List[str]]:
        """
        Validate an experiment configuration.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Validate trial config
        if config.trial_config.num_trials < 1 or config.trial_config.num_trials > 10:
            errors.append("Number of trials must be between 1 and 10")
        
        valid_algorithms = ["DHL", "HC2L", "D-HC2L", "D-DHL"]
        for algo in config.trial_config.algorithms:
            if algo not in valid_algorithms:
                errors.append(f"Invalid algorithm: {algo}. Must be one of {valid_algorithms}")
        
        if len(config.trial_config.algorithms) < 1:
            errors.append("At least one algorithm must be selected")
        
        # Validate batch config
        if config.batch_config.num_batches < 1 or config.batch_config.num_batches > 10:
            errors.append("Number of batches must be between 1 and 10")
        
        if config.batch_config.disruptions_per_batch < 100 or config.batch_config.disruptions_per_batch > 5000:
            errors.append("Disruptions per batch must be between 100 and 5000")
        
        if config.batch_config.queries_per_batch < 100 or config.batch_config.queries_per_batch > 5000:
            errors.append("Queries per batch must be between 100 and 5000")
        
        # Validate tau config
        if config.tau_config.type == "FIXED":
            if config.tau_config.fixed_value < 0.0 or config.tau_config.fixed_value > 1.0:
                errors.append("Fixed tau value must be between 0.0 and 1.0")
        
        if config.tau_config.type in ["DYNAMIC", "RANDOM"]:
            if config.tau_config.random_min >= config.tau_config.random_max:
                errors.append("Tau random_min must be less than random_max")
            if config.tau_config.random_min < 0.0 or config.tau_config.random_max > 1.0:
                errors.append("Tau random range must be between 0.0 and 1.0")
        
        # Validate points config
        bounds = config.points_config.random_bounds
        if bounds.get("lat_min", 0) >= bounds.get("lat_max", 0):
            errors.append("Latitude min must be less than lat max")
        if bounds.get("lon_min", 0) >= bounds.get("lon_max", 0):
            errors.append("Longitude min must be less than lon max")
        
        # Validate QC bounds (approximate Quezon City area)
        if bounds.get("lat_min", 0) < 14.5 or bounds.get("lat_max", 0) > 14.9:
            errors.append("Latitude bounds must be within Quezon City area (14.5 - 14.9)")
        if bounds.get("lon_min", 0) < 120.9 or bounds.get("lon_max", 0) > 121.2:
            errors.append("Longitude bounds must be within Quezon City area (120.9 - 121.2)")
        
        # Validate disruption config
        valid_disruption_types = ["TRAFFIC_ONLY", "CLOSURES_ONLY", "CONGESTION_ONLY", "MIXED", "CUSTOM"]
        if config.disruption_config.type not in valid_disruption_types:
            errors.append(f"Invalid disruption type: {config.disruption_config.type}")
        
        return len(errors) == 0, errors
    
    def save_config(self, config: ExperimentConfig, filename: str = None) -> Path:
        """
        Save configuration to JSON file.
        
        Args:
            config: ExperimentConfig object to save
            filename: Optional filename (without extension). If not provided,
                      generates from experiment_name.
        
        Returns:
            Path to saved config file
        """
        # Validate before saving
        is_valid, errors = self.validate_config(config)
        if not is_valid:
            raise ConfigValidationError(f"Invalid configuration: {errors}", errors)
        
        # Generate filename
        if filename is None:
            # Sanitize experiment name for filename
            safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in config.experiment_name)
            filename = f"{safe_name}_{config.config_id}"
        
        filepath = self.config_dir / f"{filename}.json"
        
        # Convert to dict and save
        config_dict = self._config_to_dict(config)
        
        with open(filepath, "w") as f:
            json.dump(config_dict, f, indent=2)
        
        logger.info(f"Saved experiment config to: {filepath}")
        return filepath
    
    def load_config(self, filename: str) -> ExperimentConfig:
        """
        Load configuration from JSON file.
        
        Args:
            filename: Filename (with or without .json extension)
        
        Returns:
            ExperimentConfig object
        """
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")
        
        with open(filepath, "r") as f:
            data = json.load(f)
        
        config = self._dict_to_config(data)
        
        # Validate loaded config
        is_valid, errors = self.validate_config(config)
        if not is_valid:
            logger.warning(f"Loaded config has validation issues: {errors}")
        
        logger.info(f"Loaded experiment config from: {filepath}")
        return config
    
    def load_config_by_id(self, config_id: str) -> Optional[ExperimentConfig]:
        """Load configuration by its unique config_id."""
        for filepath in self.config_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    if data.get("config_id") == config_id:
                        return self._dict_to_config(data)
            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")
                continue
        return None
    
    def list_configs(self) -> List[Dict[str, Any]]:
        """
        List all available configurations with summaries.
        
        Returns:
            List of config summaries
        """
        configs = []
        
        for filepath in sorted(self.config_dir.glob("*.json"), reverse=True):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    config = self._dict_to_config(data)
                    summary = config.get_summary()
                    summary["filename"] = filepath.name
                    summary["filepath"] = str(filepath)
                    configs.append(summary)
            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")
                configs.append({
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "error": str(e),
                    "experiment_name": filepath.stem
                })
        
        return configs
    
    def delete_config(self, filename: str) -> bool:
        """
        Delete a configuration file.
        
        Args:
            filename: Filename (with or without .json extension)
        
        Returns:
            True if deleted, False if not found
        """
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        
        filepath = self.config_dir / filename
        
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted config: {filepath}")
            return True
        return False
    
    def duplicate_config(self, filename: str, new_name: str = None) -> ExperimentConfig:
        """
        Duplicate an existing configuration with a new ID.
        
        Args:
            filename: Source config filename
            new_name: Optional new experiment name
        
        Returns:
            New ExperimentConfig object
        """
        original = self.load_config(filename)
        
        # Create new config with new ID
        new_config = ExperimentConfig(
            experiment_name=new_name or f"{original.experiment_name}_copy",
            description=f"Copy of {original.experiment_name}",
            trial_config=original.trial_config,
            batch_config=original.batch_config,
            disruption_config=original.disruption_config,
            tau_config=original.tau_config,
            points_config=original.points_config
        )
        
        return new_config
    
    def create_default_config(self, name: str = "Default_Experiment") -> ExperimentConfig:
        """Create a new configuration with default values."""
        return ExperimentConfig(
            experiment_name=name,
            description="Default experiment configuration for DHL vs HC2L benchmark",
            trial_config=TrialConfig(num_trials=3, algorithms=["DHL", "HC2L"]),
            batch_config=BatchConfig(num_batches=3, disruptions_per_batch=1000, queries_per_batch=1000),
            disruption_config=DisruptionConfig(type="MIXED"),
            tau_config=TauConfig(type="FIXED", fixed_value=0.5),
            points_config=PointsConfig(type="MIXED", preset_pairs_count=500, random_pairs_count=500)
        )


# Create a global instance for easy access
config_manager = ExperimentConfigManager()


def get_config_manager() -> ExperimentConfigManager:
    """Get the global config manager instance."""
    return config_manager
