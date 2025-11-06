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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoDisruptionService:
    """
    Background service that automatically updates disruptions
    by fetching traffic data from HERE API and triggers route 
    recalculation for active routes
    """
    
    def __init__(self, app, update_interval: int = 60):
        """
        Initialize the auto-disruption service
        
        Args:
            app: Flask app instance
            update_interval: Seconds between updates (default: 60 - 1 minute)
        """
        self.app = app
        self.update_interval = update_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Track active routes
        self.active_routes: Dict[str, Any] = {}
        self.last_disruption_hash = None
        
        logger.info(f"AutoDisruptionService initialized (interval: {update_interval}s)")
    
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
    
    def _get_disruption_hash(self) -> Optional[str]:
        """Get hash of current traffic files to detect changes"""
        try:
            from config import Config
            import hashlib
            
            # Check new hash-based traffic files (symlinks always point to latest)
            files_to_check = [
                Config.DISRUPTIONS_DIR / "current_traffic_flow.gr",
                Config.DISRUPTIONS_DIR / "current_traffic_incidents.gr",
                Config.DISRUPTIONS_DIR / "current_traffic_both.gr",
                Config.DISRUPTIONS_DIR / "current_traffic_flow.csv",
                Config.DISRUPTIONS_DIR / "current_traffic_both.csv"
            ]
            
            combined_content = ""
            for file_path in files_to_check:
                if file_path.exists():
                    try:
                        # For symlinks, get the actual file modification time
                        real_path = file_path.resolve()
                        mtime = real_path.stat().st_mtime
                        combined_content += f"{file_path.name}:{mtime}:"
                    except Exception as e:
                        logger.debug(f"Error reading {file_path}: {e}")
            
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
        """Fetch latest traffic data using the traffic service"""
        try:
            from realtime_traffic_service import RealtimeTrafficService
            
            # Initialize traffic service
            traffic_service = RealtimeTrafficService()
            
            # Fetch and save traffic data
            logger.info("🌐 Fetching latest traffic data from HERE API...")
            metadata = traffic_service.fetch_and_save(mode='both')
            
            logger.info(f"✅ Traffic update complete: {metadata.get('total_edges', 0)} edges affected")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error fetching traffic data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _run_loop(self):
        """Main service loop - automatically fetches traffic data every update_interval"""
        logger.info("🔄 Auto-disruption service loop started (AUTO-FETCH ENABLED)")
        logger.info(f"   Fetching traffic data every {self.update_interval} seconds")
        
        while self.running:
            try:
                # Fetch latest traffic data from HERE API
                fetch_success = self._fetch_traffic_data()
                
                if fetch_success:
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
                
                # Sleep for the configured interval
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in auto-disruption loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(30)  # Wait before retry
        
        logger.info("🛑 Auto-disruption service loop stopped")


# Global service instance
auto_disruption_service: Optional[AutoDisruptionService] = None


def init_auto_disruption_service(app, update_interval: int = 60):
    """
    Initialize and start the auto-disruption service
    
    Args:
        app: Flask app instance
        update_interval: Seconds between checks (default: 60 - 1 minute)
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
