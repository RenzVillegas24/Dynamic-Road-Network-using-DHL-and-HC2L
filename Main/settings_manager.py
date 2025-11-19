"""
Persistent Settings Manager
============================

Manages application settings that survive across server restarts and page refreshes.
Stores settings in a JSON file in the data directory.

Settings managed:
- auto_update_interval: Minutes between auto-disruption updates (1-30)
- traffic_mode: Current traffic data mode (none/flow/incidents/both)
- routing_algorithm: Default routing algorithm (hc2l/dhl)
"""

import json
from console_formatter import get_logger, ConsoleFormatter
from pathlib import Path
from typing import Any, Dict, Optional
from threading import Lock

logger = get_logger("SettingsManager")

class SettingsManager:
    """Manages persistent application settings"""
    
    # Default settings
    DEFAULTS = {
        'auto_update_interval': 2,  # minutes (default: 2 minutes = 120 seconds)
        'traffic_mode': 'both',  # flow/incidents/both/none
        'routing_algorithm': 'hc2l',  # hc2l or dhl
        'enable_alternatives': True,
        'tau_threshold': 0.5,
    }
    
    def __init__(self, settings_file: Path = None):
        """
        Initialize settings manager
        
        Args:
            settings_file: Path to settings JSON file (default: Main/data/settings.json)
        """
        if settings_file is None:
            from config import Config
            settings_file = Config.DATA_DIR / 'settings.json'
        
        self.settings_file = Path(settings_file)
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        
        # Load or create settings
        self._load_settings()
        logger.success(f"SettingsManager initialized: {self.settings_file}")
    
    def _load_settings(self):
        """Load settings from file or create with defaults"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    self.settings = json.load(f)
                logger.file_op(f"Loaded settings from {self.settings_file.name}")
            else:
                self.settings = self.DEFAULTS.copy()
                self._save_settings()
                logger.info(f"✨ Created new settings file with defaults")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.settings = self.DEFAULTS.copy()
    
    def _save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        with self._lock:
            return self.settings.get(key, default or self.DEFAULTS.get(key))
    
    def set(self, key: str, value: Any):
        """
        Set a setting value
        
        Args:
            key: Setting key
            value: Setting value
        """
        with self._lock:
            self.settings[key] = value
            self._save_settings()
            logger.cache(f"Setting saved: {key} = {value}")
    
    def update(self, updates: Dict[str, Any]):
        """
        Update multiple settings at once
        
        Args:
            updates: Dictionary of settings to update
        """
        with self._lock:
            self.settings.update(updates)
            self._save_settings()
            logger.cache(f"Settings updated: {list(updates.keys())}")
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings"""
        with self._lock:
            return self.settings.copy()
    
    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        with self._lock:
            self.settings = self.DEFAULTS.copy()
            self._save_settings()
            logger.processing("Settings reset to defaults")


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def init_settings_manager(settings_file: Path = None) -> SettingsManager:
    """Initialize global settings manager"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager(settings_file)
    return _settings_manager


def get_settings_manager() -> SettingsManager:
    """Get global settings manager instance"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
