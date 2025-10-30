"""
Configuration Management for Dynamic Road Network Application

This module provides centralized configuration management for:
- File paths and directories
- Algorithm executables
- Environment variables
- API keys and sensitive data

Usage:
    from config import Config
    
    # Access configuration
    api_key = Config.GOOGLE_MAPS_API_KEY
    dhl_exec = Config.DHL_EXECUTABLE
    nodes_csv = Config.NODES_CSV
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Centralized configuration for the Dynamic Road Network application"""
    
    # ========================================================================
    # DIRECTORY PATHS
    # ========================================================================
    
    # Base directories
    PROJECT_ROOT = Path(__file__).parent.parent.absolute()
    MAIN_DIR = Path(__file__).parent.absolute()
    
    # Algorithm source directories
    DHL_SRC_DIR = PROJECT_ROOT / 'DualHierarchyLabelling'
    HC2L_SRC_DIR = PROJECT_ROOT / 'HighCardinalityTwoLevel'
    
    # Data directories (all data should be in Main/data/)
    DATA_DIR = MAIN_DIR / 'data'
    RAW_DATA_DIR = DATA_DIR / 'raw'
    PROCESSED_DATA_DIR = DATA_DIR / 'processed'
    DISRUPTIONS_DIR = DATA_DIR / 'disruptions'
    
    # Build directories for executables
    BUILD_DIR = MAIN_DIR / 'build'
    DHL_BUILD_DIR = BUILD_DIR / 'dhl'
    HC2L_BUILD_DIR = BUILD_DIR / 'hc2l'
    
    # Template and static directories
    TEMPLATES_DIR = MAIN_DIR / 'templates'
    STATIC_DIR = MAIN_DIR / 'static'
    
    # ========================================================================
    # DATA FILES
    # ========================================================================
    
    # Graph data files (CSV format)
    NODES_CSV = RAW_DATA_DIR / 'quezon_city_nodes.csv'
    EDGES_CSV = RAW_DATA_DIR / 'quezon_city_edges.csv'
    
    # Disruption scenario files
    DISRUPTIONS_CSV = DISRUPTIONS_DIR / 'qc_scenario_for_cpp_1.csv'
    
    # Node ID mapping
    NODE_MAPPING_CSV = PROCESSED_DATA_DIR / 'node_id_mapping.csv'
    
    # Processed graph files (binary format for C++ algorithms)
    DHL_GRAPH_FILE = PROCESSED_DATA_DIR / 'quezon_city.graph'
    DHL_INDEX_FILE = PROCESSED_DATA_DIR / 'quezon_city.dhl.index'
    HC2L_GRAPH_FILE = PROCESSED_DATA_DIR / 'quezon_city.graph'
    HC2L_INDEX_FILE = PROCESSED_DATA_DIR / 'quezon_city.hc2l.index'
    
    # ========================================================================
    # ALGORITHM EXECUTABLES
    # ========================================================================
    
    @staticmethod
    def _find_executable(name: str, search_paths: list) -> Path:
        """
        Find an executable in multiple possible locations
        
        Args:
            name: Name of the executable
            search_paths: List of paths to search
            
        Returns:
            Path to the executable if found, None otherwise
        """
        for path in search_paths:
            if isinstance(path, str):
                path = Path(path)
            if path.exists() and path.is_file():
                return path.absolute()
        return None
    
    @classmethod
    def get_dhl_executable(cls) -> Path:
        """
        Get path to DHL routing executable
        
        Priority:
        1. Environment variable DHL_EXECUTABLE
        2. Main/build/dhl/dhl_routing_api
        3. DualHierarchyLabelling/build/dhl_routing_api
        4. DualHierarchyLabelling/dhl_routing_api
        
        Returns:
            Path to DHL executable
            
        Raises:
            FileNotFoundError: If executable cannot be found
        """
        # Check environment variable first
        env_path = os.getenv('DHL_EXECUTABLE')
        if env_path and Path(env_path).exists():
            return Path(env_path).absolute()
        
        # Search in standard locations
        search_paths = [
            cls.DHL_BUILD_DIR / 'dhl_routing_api',
            cls.DHL_SRC_DIR / 'build' / 'dhl_routing_api',
            cls.DHL_SRC_DIR / 'dhl_routing_api',
            cls.MAIN_DIR / 'dhl_routing_api',
        ]
        
        found = cls._find_executable('dhl_routing_api', search_paths)
        if found:
            return found
        
        # Return the preferred path for error message
        raise FileNotFoundError(
            f"DHL executable not found. Please build it and place in one of:\n" +
            '\n'.join(f"  - {p}" for p in search_paths)
        )
    
    @classmethod
    def get_hc2l_executable(cls) -> Path:
        """
        Get path to HC2L routing executable
        
        Priority:
        1. Environment variable HC2L_EXECUTABLE
        2. Main/build/hc2l/hc2l_routing_api
        3. HighCardinalityTwoLevel/build/hc2l_routing_api
        4. HighCardinalityTwoLevel/hc2l_routing_api
        
        Returns:
            Path to HC2L executable
            
        Raises:
            FileNotFoundError: If executable cannot be found
        """
        # Check environment variable first
        env_path = os.getenv('HC2L_EXECUTABLE')
        if env_path and Path(env_path).exists():
            return Path(env_path).absolute()
        
        # Search in standard locations
        search_paths = [
            cls.HC2L_BUILD_DIR / 'hc2l_routing_api',
            cls.HC2L_SRC_DIR / 'build' / 'hc2l_routing_api',
            cls.HC2L_SRC_DIR / 'hc2l_routing_api',
            cls.MAIN_DIR / 'hc2l_routing_api',
        ]
        
        found = cls._find_executable('hc2l_routing_api', search_paths)
        if found:
            return found
        
        # Return the preferred path for error message
        raise FileNotFoundError(
            f"HC2L executable not found. Please build it and place in one of:\n" +
            '\n'.join(f"  - {p}" for p in search_paths)
        )
    
    # ========================================================================
    # API KEYS AND SENSITIVE DATA
    # ========================================================================
    
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
    
    # ========================================================================
    # FLASK CONFIGURATION
    # ========================================================================
    
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
    
    # ========================================================================
    # LOGGING CONFIGURATION
    # ========================================================================
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # ========================================================================
    # ALGORITHM PARAMETERS
    # ========================================================================
    
    # Default tau threshold for HC2L
    DEFAULT_TAU_THRESHOLD = 0.5
    
    # Maximum distance for nearest node search (meters)
    MAX_NEAREST_NODE_DISTANCE = 1000
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    @classmethod
    def ensure_directories(cls):
        """Create all necessary directories if they don't exist"""
        directories = [
            cls.DATA_DIR,
            cls.RAW_DATA_DIR,
            cls.PROCESSED_DATA_DIR,
            cls.DISRUPTIONS_DIR,
            cls.BUILD_DIR,
            cls.DHL_BUILD_DIR,
            cls.HC2L_BUILD_DIR,
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate_data_files(cls) -> dict:
        """
        Validate that required data files exist
        
        Returns:
            Dictionary with validation results
        """
        results = {
            'nodes_csv': cls.NODES_CSV.exists(),
            'edges_csv': cls.EDGES_CSV.exists(),
            'disruptions_csv': cls.DISRUPTIONS_CSV.exists(),
        }
        
        results['all_valid'] = all(results.values())
        return results
    
    @classmethod
    def get_config_summary(cls) -> str:
        """
        Get a summary of the current configuration
        
        Returns:
            Formatted string with configuration summary
        """
        summary = []
        summary.append("=" * 60)
        summary.append("Dynamic Road Network - Configuration Summary")
        summary.append("=" * 60)
        summary.append("")
        
        summary.append("DIRECTORIES:")
        summary.append(f"  Project Root:  {cls.PROJECT_ROOT}")
        summary.append(f"  Main Dir:      {cls.MAIN_DIR}")
        summary.append(f"  Data Dir:      {cls.DATA_DIR}")
        summary.append(f"  Build Dir:     {cls.BUILD_DIR}")
        summary.append("")
        
        summary.append("DATA FILES:")
        summary.append(f"  Nodes CSV:     {cls.NODES_CSV} {'✓' if cls.NODES_CSV.exists() else '✗'}")
        summary.append(f"  Edges CSV:     {cls.EDGES_CSV} {'✓' if cls.EDGES_CSV.exists() else '✗'}")
        summary.append(f"  Disruptions:   {cls.DISRUPTIONS_CSV} {'✓' if cls.DISRUPTIONS_CSV.exists() else '✗'}")
        summary.append("")
        
        summary.append("EXECUTABLES:")
        try:
            dhl_exec = cls.get_dhl_executable()
            summary.append(f"  DHL:           {dhl_exec} ✓")
        except FileNotFoundError as e:
            summary.append(f"  DHL:           Not found ✗")
        
        try:
            hc2l_exec = cls.get_hc2l_executable()
            summary.append(f"  HC2L:          {hc2l_exec} ✓")
        except FileNotFoundError as e:
            summary.append(f"  HC2L:          Not found ✗")
        summary.append("")
        
        summary.append("API KEYS:")
        summary.append(f"  Google Maps:   {'Set ✓' if cls.GOOGLE_MAPS_API_KEY else 'Not set ✗'}")
        summary.append("")
        
        summary.append("FLASK:")
        summary.append(f"  Environment:   {cls.FLASK_ENV}")
        summary.append(f"  Debug:         {cls.FLASK_DEBUG}")
        summary.append(f"  Host:Port:     {cls.FLASK_HOST}:{cls.FLASK_PORT}")
        summary.append("")
        
        summary.append("=" * 60)
        
        return '\n'.join(summary)


# Create directories on import
Config.ensure_directories()


if __name__ == '__main__':
    # Print configuration summary when run directly
    print(Config.get_config_summary())
    
    # Validate data files
    print("\nData File Validation:")
    validation = Config.validate_data_files()
    for key, value in validation.items():
        if key != 'all_valid':
            status = '✓' if value else '✗'
            print(f"  {key}: {status}")
    
    if validation['all_valid']:
        print("\n✓ All data files are present")
    else:
        print("\n✗ Some data files are missing")
