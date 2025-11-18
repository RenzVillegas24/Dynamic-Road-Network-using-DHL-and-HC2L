"""
Automatic Disruption Update Service for Active Routes
Runs as a background thread to fetch traffic data from HERE API 
every 60 seconds (1 minute) and triggers route recalculation when 
changes are detected
"""

import threading
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import logging

from traffic_data_manager import (
    merge_user_disruptions_with_traffic
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoDisruptionService:
    """
    Background service that automatically updates disruptions
    by fetching traffic data from HERE API and triggers route 
    recalculation for active routes
    """
    
    def __init__(self, app, update_interval: int = 120):
        """
        Initialize the auto-disruption service
        
        Args:
            app: Flask app instance
            update_interval: Seconds between updates (default: 120 - 2 minutes)
        """
        self.app = app
        self.update_interval = update_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Track active routes
        self.active_routes: Dict[str, Any] = {}
        self.last_disruption_hash = None
        self.last_fetch_time = None  # Track when we last fetched data
        
        # Initialize services once
        try:
            from flow_service import FlowService
            from incident_service import IncidentService
            self.flow_service = FlowService()
            self.incident_service = IncidentService()
            logger.info("✅ Flow and Incident services initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing services: {e}")
            self.flow_service = None
            self.incident_service = None
        
        logger.info(f"AutoDisruptionService initialized (interval: {update_interval}s) - NO AUTO-FETCH")
    
    def start(self):
        """Start the background service"""
        if self.running:
            logger.warning("Service already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("✅ Auto-disruption service started")
    
    def stop(self):
        """Stop the background service"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🛑 Auto-disruption service stopped")
    
    def register_active_route(self, route_id: str, route_data: Dict[str, Any]):
        """
        Register an active route for monitoring
        
        Args:
            route_id: Unique identifier for the route
            route_data: Route parameters (start, dest, algorithm, etc.)
        """
        self.active_routes[route_id] = {
            'data': route_data,
            'registered_at': datetime.now().isoformat(),
            'last_update': None
        }
        logger.info(f"📍 Route registered: {route_id} ({route_data.get('algorithm', 'unknown')})")
    
    def unregister_route(self, route_id: str):
        """Remove a route from monitoring"""
        if route_id in self.active_routes:
            del self.active_routes[route_id]
            logger.info(f"❌ Route unregistered: {route_id}")
    
    def clear_all_routes(self):
        """Clear all active routes"""
        count = len(self.active_routes)
        self.active_routes.clear()
        logger.info(f"🗑️  Cleared {count} active route(s)")
    
    def set_update_interval(self, interval_seconds: int):
        """
        Update the fetch interval (must be between 60 and 1800 seconds)
        
        Args:
            interval_seconds: New interval in seconds (1-30 minutes)
        """
        # Clamp to 60-1800 seconds (1-30 minutes)
        interval_seconds = max(60, min(1800, interval_seconds))
        self.update_interval = interval_seconds
        logger.info(f"⏱️  Update interval changed to {interval_seconds}s ({interval_seconds//60} minutes)")
        return interval_seconds
    
    def should_fetch_now(self) -> bool:
        """Check if enough time has passed to fetch new data based on latest disruption file timestamp"""
        try:
            from config import Config
            import re
            
            # Check flow and incident directories for latest files
            flow_dir = Config.FLOW_DIR
            incidents_dir = Config.INCIDENTS_DIR
            
            latest_timestamp = None
            
            # Check flow directory
            if flow_dir.exists():
                try:
                    flow_files = sorted(flow_dir.glob("flow_*.csv"))
                    if flow_files:
                        latest_flow = flow_files[-1]
                        # Parse timestamp from filename (format: flow_YYYYMMDDTHHMMSS.csv)
                        match = re.search(r'flow_(\d{8}T\d{6})\.csv', latest_flow.name)
                        if match:
                            timestamp_str = match.group(1)
                            # Convert YYYYMMDDTHHMMSS to datetime
                            dt = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
                            file_timestamp = dt.timestamp()
                            if latest_timestamp is None or file_timestamp > latest_timestamp:
                                latest_timestamp = file_timestamp
                except Exception as e:
                    logger.debug(f"Error parsing flow file timestamp: {e}")
            
            # Check incidents directory
            if incidents_dir.exists():
                try:
                    incident_files = sorted(incidents_dir.glob("incident_*.csv"))
                    if incident_files:
                        latest_incident = incident_files[-1]
                        # Parse timestamp from filename (format: incident_YYYYMMDDTHHMMSS.csv)
                        match = re.search(r'incident_(\d{8}T\d{6})\.csv', latest_incident.name)
                        if match:
                            timestamp_str = match.group(1)
                            # Convert YYYYMMDDTHHMMSS to datetime
                            dt = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
                            file_timestamp = dt.timestamp()
                            if latest_timestamp is None or file_timestamp > latest_timestamp:
                                latest_timestamp = file_timestamp
                except Exception as e:
                    logger.debug(f"Error parsing incident file timestamp: {e}")
            
            # If no disruption files exist, we should fetch
            if latest_timestamp is None:
                logger.debug("No disruption files found - should fetch")
                return True
            
            # Check if enough time has passed since the latest file
            current_time = time.time()
            time_since_last_file = current_time - latest_timestamp
            should_fetch = time_since_last_file >= self.update_interval
            
            if should_fetch:
                logger.debug(f"✅ Fetch allowed: {time_since_last_file:.0f}s since latest file >= {self.update_interval}s")
            else:
                remaining = self.update_interval - time_since_last_file
                logger.debug(f"⏳ Fetch blocked: {remaining:.0f}s remaining until next fetch")
            
            return should_fetch
            
        except Exception as e:
            logger.error(f"Error in should_fetch_now: {e}")
            # On error, default to fetching to be safe
            return True
    
    def get_last_fetch_time(self) -> Optional[str]:
        """Get the last time data was fetched based on latest disruption file (ISO format)"""
        try:
            from config import Config
            import re
            
            flow_dir = Config.FLOW_DIR
            incidents_dir = Config.INCIDENTS_DIR
            
            latest_timestamp = None
            
            # Check flow directory
            if flow_dir.exists():
                flow_files = sorted(flow_dir.glob("flow_*.csv"))
                if flow_files:
                    latest_flow = flow_files[-1]
                    match = re.search(r'flow_(\d{8}T\d{6})\.csv', latest_flow.name)
                    if match:
                        timestamp_str = match.group(1)
                        dt = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
                        file_timestamp = dt.timestamp()
                        if latest_timestamp is None or file_timestamp > latest_timestamp:
                            latest_timestamp = file_timestamp
            
            # Check incidents directory
            if incidents_dir.exists():
                incident_files = sorted(incidents_dir.glob("incident_*.csv"))
                if incident_files:
                    latest_incident = incident_files[-1]
                    match = re.search(r'incident_(\d{8}T\d{6})\.csv', latest_incident.name)
                    if match:
                        timestamp_str = match.group(1)
                        dt = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
                        file_timestamp = dt.timestamp()
                        if latest_timestamp is None or file_timestamp > latest_timestamp:
                            latest_timestamp = file_timestamp
            
            if latest_timestamp is None:
                return None
            return datetime.fromtimestamp(latest_timestamp).isoformat()
            
        except Exception as e:
            logger.error(f"Error getting last fetch time: {e}")
            return None
    
    def get_next_fetch_time(self) -> Optional[str]:
        """Get when the next fetch will be allowed based on latest disruption file (ISO format)"""
        try:
            from config import Config
            import re
            
            flow_dir = Config.FLOW_DIR
            incidents_dir = Config.INCIDENTS_DIR
            
            latest_timestamp = None
            
            # Check flow directory
            if flow_dir.exists():
                flow_files = sorted(flow_dir.glob("flow_*.csv"))
                if flow_files:
                    latest_flow = flow_files[-1]
                    match = re.search(r'flow_(\d{8}T\d{6})\.csv', latest_flow.name)
                    if match:
                        timestamp_str = match.group(1)
                        dt = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
                        file_timestamp = dt.timestamp()
                        if latest_timestamp is None or file_timestamp > latest_timestamp:
                            latest_timestamp = file_timestamp
            
            # Check incidents directory
            if incidents_dir.exists():
                incident_files = sorted(incidents_dir.glob("incident_*.csv"))
                if incident_files:
                    latest_incident = incident_files[-1]
                    match = re.search(r'incident_(\d{8}T\d{6})\.csv', latest_incident.name)
                    if match:
                        timestamp_str = match.group(1)
                        dt = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
                        file_timestamp = dt.timestamp()
                        if latest_timestamp is None or file_timestamp > latest_timestamp:
                            latest_timestamp = file_timestamp
            
            if latest_timestamp is None:
                return None
            
            next_time = latest_timestamp + self.update_interval
            return datetime.fromtimestamp(next_time).isoformat()
            
        except Exception as e:
            logger.error(f"Error getting next fetch time: {e}")
            return None
    
    def _get_disruption_hash(self) -> Optional[str]:
        """Get hash of current traffic files to detect changes"""
        try:
            from config import Config
            import hashlib
            
            # Check flow and incident directories for latest files
            flow_dir = Config.FLOW_DIR
            incidents_dir = Config.INCIDENTS_DIR
            
            combined_content = ""
            
            # Check flow directory
            if flow_dir.exists():
                try:
                    # Get the most recent flow file
                    flow_files = sorted(flow_dir.glob("flow_*.csv"))
                    if flow_files:
                        latest_flow = flow_files[-1]
                        mtime = latest_flow.stat().st_mtime
                        combined_content += f"flow:{mtime}:"
                except Exception as e:
                    logger.debug(f"Error reading flow directory: {e}")
            
            # Check incidents directory
            if incidents_dir.exists():
                try:
                    # Get the most recent incident file
                    incident_files = sorted(incidents_dir.glob("incident_*.csv"))
                    if incident_files:
                        latest_incident = incident_files[-1]
                        mtime = latest_incident.stat().st_mtime
                        combined_content += f"incident:{mtime}:"
                except Exception as e:
                    logger.debug(f"Error reading incidents directory: {e}")
            
            if combined_content:
                return hashlib.md5(combined_content.encode()).hexdigest()
            return None
            
        except Exception as e:
            logger.error(f"Error computing disruption hash: {e}")
            return None
    
    def _trigger_route_recalculation(self, route_id: str, route_info: Dict[str, Any]):
        """
        Trigger route recalculation via Flask socketio or similar mechanism
        In this implementation, we'll use Flask's app context to emit events
        """
        try:
            from flask_socketio import emit
            
            with self.app.app_context():
                # Emit event to frontend to recalculate route
                emit('disruption_update', {
                    'route_id': route_id,
                    'message': 'Disruptions updated - route recalculation needed',
                    'timestamp': datetime.now().isoformat(),
                    'route_data': route_info['data']
                }, broadcast=True, namespace='/')
                
                logger.info(f"🔄 Triggered recalculation for route: {route_id}")
                
        except ImportError:
            # Fallback: just log if socketio not available
            logger.info(f"🔄 Disruption change detected for route: {route_id}")
            logger.info("   (Install flask-socketio for real-time updates)")
        except Exception as e:
            logger.error(f"Error triggering recalculation: {e}")
    
    def _fetch_traffic_data(self):
        """Fetch latest traffic data from both flow and incident services"""
        try:
            if not self.flow_service or not self.incident_service:
                logger.error("❌ Services not initialized")
                return False
            
            logger.info("🌐 Fetching latest traffic data from HERE API...")
            
            # Fetch and save flow data
            flow_metadata = self.flow_service.fetch_and_save()
            logger.info(f"✅ Flow data updated: {flow_metadata.get('total_edges', 0)} edges")
            
            # Fetch and save incident data
            incident_metadata = self.incident_service.fetch_and_save()
            logger.info(f"✅ Incident data updated: {incident_metadata.get('total_matched', 0)} incidents matched")
            
            # Merge user disruptions into both CSV sources
            merge_user_disruptions_with_traffic(
                flow_metadata.get('csv_file'),
                incident_metadata.get('csv_file')
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error fetching traffic data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _run_loop(self):
        """Main service loop - fetches traffic data only when update_interval has passed since last disruption file"""
        logger.info("🔄 Auto-disruption service loop started")
        logger.info(f"   ⏰ Will fetch traffic data every {self.update_interval} seconds")
        logger.info(f"   � Based on latest disruption file timestamps")
        
        while self.running:
            try:
                # Check if we should fetch new traffic data based on file timestamps
                should_fetch = self.should_fetch_now()
                
                if should_fetch:
                    logger.info(f"   ✅ Time to fetch - checking disruption files...")
                    # Fetch latest traffic data from HERE API
                    fetch_success = self._fetch_traffic_data()
                    
                    if fetch_success:
                        # Update last_fetch_time for compatibility (though we don't use it anymore)
                        self.last_fetch_time = time.time()
                        
                        # Check if there are active routes
                        if self.active_routes:
                            # Get new disruption hash after fetch
                            current_hash = self._get_disruption_hash()
                            
                            if current_hash and current_hash != self.last_disruption_hash:
                                if self.last_disruption_hash is not None:  # Skip first time
                                    logger.info(f"🚦 Traffic data changed - triggering route updates")
                                    
                                    # Trigger recalculation for all active routes
                                    for route_id, route_info in list(self.active_routes.items()):
                                        self._trigger_route_recalculation(route_id, route_info)
                                        route_info['last_update'] = datetime.now().isoformat()
                                
                                self.last_disruption_hash = current_hash
                else:
                    # Log current status occasionally (not every 10 seconds to avoid spam)
                    pass  # should_fetch_now() already logs debug info
                
                # Sleep for a short interval to keep the loop responsive (check every 10 seconds)
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in auto-disruption loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(30)  # Wait before retry
        
        logger.info("🛑 Auto-disruption service loop stopped")


# Global service instance
auto_disruption_service: Optional[AutoDisruptionService] = None


def init_auto_disruption_service(app, update_interval: int = 120):
    """
    Initialize and start the auto-disruption service
    
    Args:
        app: Flask app instance
        update_interval: Seconds between checks (default: 120 - 2 minutes)
    """
    global auto_disruption_service
    
    if auto_disruption_service is None:
        auto_disruption_service = AutoDisruptionService(app, update_interval)
        auto_disruption_service.start()
        logger.info(f"✅ Auto-disruption service initialized (interval: {update_interval}s)")
    
    return auto_disruption_service


def get_auto_disruption_service() -> Optional[AutoDisruptionService]:
    """Get the global auto-disruption service instance"""
    return auto_disruption_service


def shutdown_auto_disruption_service():
    """Shutdown the auto-disruption service"""
    global auto_disruption_service
    
    if auto_disruption_service:
        auto_disruption_service.stop()
        auto_disruption_service = None
        logger.info("🛑 Auto-disruption service shutdown complete")
