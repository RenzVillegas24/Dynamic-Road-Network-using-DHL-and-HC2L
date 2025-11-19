/**
 * Disruption Update Monitor
 * 
 * Polls the backend to detect when disruption files are updated
 * and notifies the user + triggers route recalculation if needed
 */

let lastDisruptionHash = null;
let disruptionCheckInterval = null;
let isUpdating = false;

// Configuration
const DISRUPTION_CHECK_INTERVAL = 5000; // Check every 5 seconds
const ENABLE_AUTO_ROUTE_UPDATE = true; // Auto-recalculate route when disruptions change

/**
 * Start monitoring for disruption updates
 */
function startDisruptionMonitoring() {
  console.log('[Disruption Monitor] Starting...');
  
  // Initial hash fetch
  fetchCurrentDisruptionHash();
  
  // Start polling
  if (!disruptionCheckInterval) {
    disruptionCheckInterval = setInterval(checkForDisruptionUpdates, DISRUPTION_CHECK_INTERVAL);
    console.log(`[Disruption Monitor] Polling every ${DISRUPTION_CHECK_INTERVAL/1000}s`);
  }
}

/**
 * Stop monitoring for disruption updates
 */
function stopDisruptionMonitoring() {
  if (disruptionCheckInterval) {
    clearInterval(disruptionCheckInterval);
    disruptionCheckInterval = null;
    console.log('[Disruption Monitor] Stopped');
  }
}

/**
 * Fetch the current disruption hash (initial baseline)
 */
async function fetchCurrentDisruptionHash() {
  try {
    const response = await fetch('/get_auto_update_status');
    const data = await response.json();
    
    if (data.success) {
      lastDisruptionHash = data.disruption_hash;
      console.log('[Disruption Monitor] Initial hash:', lastDisruptionHash);
    }
  } catch (error) {
    console.error('[Disruption Monitor] Error fetching initial hash:', error);
  }
}

/**
 * Check if disruptions have been updated
 */
async function checkForDisruptionUpdates() {
  // Skip if already processing an update
  if (isUpdating) {
    return;
  }
  
  try {
    const params = new URLSearchParams();
    if (lastDisruptionHash) {
      params.append('last_hash', lastDisruptionHash);
    }
    
    const response = await fetch(`/check_disruption_updates?${params}`);
    const data = await response.json();
    
    if (!data.success) {
      console.error('[Disruption Monitor] Check failed:', data.error);
      return;
    }
    
    // Update hash
    lastDisruptionHash = data.current_hash;
    
    // If disruptions were updated, notify and recalculate
    if (data.updated) {
      console.log('[Disruption Monitor] Disruptions changed!');
      handleDisruptionUpdate(data);
    }
    
  } catch (error) {
    console.error('[Disruption Monitor] Error checking for updates:', error);
  }
}

/**
 * Handle disruption update notification and route recalculation
 */
async function handleDisruptionUpdate(updateData) {
  isUpdating = true;
  
  try {
    // Show notification to user
    if (updateData.message) {
      showUpdateToast(updateData.message, updateData.notification_type || 'info');
      console.log('[Disruption Monitor] Notification shown:', updateData.message);
    }
    
    // Reload traffic overlay if visible
    if (typeof loadTrafficOverlay === 'function' && document.getElementById('trafficToggle')?.checked) {
      console.log('[Disruption Monitor] Reloading traffic overlay...');
      await loadTrafficOverlay();
    }
    
    // Reload incident markers if visible
    if (typeof loadIncidentMarkers === 'function' && document.getElementById('incidentToggle')?.checked) {
      console.log('[Disruption Monitor] Reloading incident markers...');
      await loadIncidentMarkers();
    }
    
    // Auto-recalculate route if enabled and route exists
    if (ENABLE_AUTO_ROUTE_UPDATE && window.currentRouteData) {
      console.log('[Disruption Monitor] Recalculating route with new disruptions...');
      showUpdateToast('🔄 Recalculating route with updated traffic data...', 'info');
      
      try {
        // Get the stored route data
        const routeData = window.currentRouteData;
        
        // Get algorithm from currently selected radio button
        // First priority: UI selection (what user currently selected)
        let algorithm = 'hc2l'; // Default fallback
        
        // Try using getSelectedAlgorithm() function if available (most reliable)
        if (typeof getSelectedAlgorithm === 'function') {
          algorithm = getSelectedAlgorithm();
          console.log('[Disruption Monitor] Algorithm from getSelectedAlgorithm():', algorithm);
        } else {
          // Fallback: Direct radio button selection
          const selectedAlgo = document.querySelector('input[name="algorithm"]:checked');
          if (selectedAlgo && selectedAlgo.value) {
            algorithm = selectedAlgo.value.toLowerCase();
            console.log('[Disruption Monitor] Algorithm from UI radio button:', algorithm);
          } else {
            // Last resort: Use stored algorithm from route data
            const storedAlgo = routeData?.metrics?.algorithm || routeData?.algorithm || 'hc2l';
            algorithm = (storedAlgo.toLowerCase().includes('dhl') || storedAlgo.includes('DHL')) ? 'dhl' : 'hc2l';
            console.log('[Disruption Monitor] Using stored algorithm:', algorithm, '(from:', storedAlgo, ')');
          }
        }
        
        console.log('[Disruption Monitor] Route algorithm (normalized):', algorithm);
        console.log('[Disruption Monitor] Start:', routeData.input?.start_snap_lat, routeData.input?.start_snap_lng);
        console.log('[Disruption Monitor] Destination:', routeData.input?.dest_snap_lat, routeData.input?.dest_snap_lng);
        
        // Clear previous routes
        if (typeof clearRoutes === 'function') {
          clearRoutes();
        }
        
        // Recalculate route based on algorithm
        let newRouteData = null;
        
        // Make direct API call instead of using frontend functions
        // This ensures we have all the required snap point data
        try {
          const startSnap = window.osmSnapMarkers?.start?.data;
          const destSnap = window.osmSnapMarkers?.dest?.data;
          
          if (!startSnap || !destSnap) {
            console.error('[Disruption Monitor] Missing snap point data:', { startSnap, destSnap });
            showUpdateToast('⚠️ Error: Missing snap point data for route recalculation', 'warning');
            return;
          }
          
          console.log('[Disruption Monitor] Using snap points for recalculation:', {
            start: { lat: startSnap.latitude, lng: startSnap.longitude, edge: startSnap.edge_id },
            dest: { lat: destSnap.latitude, lng: destSnap.longitude, edge: destSnap.edge_id }
          });
          
          if (algorithm === 'dhl') {
            console.log('[Disruption Monitor] Recalculating DHL route with disruptions...');
            const response = await fetch('/compute_dhl_route', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                start_pin_lat: routeData.input?.start_snap_lat || startSnap.latitude,
                start_pin_lng: routeData.input?.start_snap_lng || startSnap.longitude,
                dest_pin_lat: routeData.input?.dest_snap_lat || destSnap.latitude,
                dest_pin_lng: routeData.input?.dest_snap_lng || destSnap.longitude,
                start_snap_lat: startSnap.latitude,
                start_snap_lng: startSnap.longitude,
                dest_snap_lat: destSnap.latitude,
                dest_snap_lng: destSnap.longitude,
                start_edge_source: startSnap.edge_source || 0,
                start_edge_target: startSnap.edge_target || 0,
                start_edge_oneway: startSnap.oneway || 0,
                dest_edge_source: destSnap.edge_source || 0,
                dest_edge_target: destSnap.edge_target || 0,
                dest_edge_oneway: destSnap.oneway || 0,
                use_disruptions: true,
                tau_threshold: 0.5,
                generate_alternatives: false
              })
            });
            
            if (response.ok) {
              newRouteData = await response.json();
              if (newRouteData.success && typeof displayDHLRoute === 'function') {
                displayDHLRoute(newRouteData);
                console.log('[Disruption Monitor] DHL route recalculated successfully');
              }
            }
          } else if (algorithm === 'hc2l') {
            console.log('[Disruption Monitor] Recalculating HC2L route with disruptions...');
            const threshold = routeData.metrics?.tau_threshold || 0.5;
            const response = await fetch('/compute_dhc2l_route', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                start_pin_lat: routeData.input?.start_snap_lat || startSnap.latitude,
                start_pin_lng: routeData.input?.start_snap_lng || startSnap.longitude,
                dest_pin_lat: routeData.input?.dest_snap_lat || destSnap.latitude,
                dest_pin_lng: routeData.input?.dest_snap_lng || destSnap.longitude,
                start_snap_lat: startSnap.latitude,
                start_snap_lng: startSnap.longitude,
                dest_snap_lat: destSnap.latitude,
                dest_snap_lng: destSnap.longitude,
                start_edge_source: startSnap.edge_source || 0,
                start_edge_target: startSnap.edge_target || 0,
                start_edge_oneway: startSnap.oneway || 0,
                dest_edge_source: destSnap.edge_source || 0,
                dest_edge_target: destSnap.edge_target || 0,
                dest_edge_oneway: destSnap.oneway || 0,
                use_disruptions: true,
                tau_threshold: threshold,
                generate_alternatives: false
              })
            });
            
            if (response.ok) {
              newRouteData = await response.json();
              if (newRouteData.success && typeof displayDHC2LRoute === 'function') {
                displayDHC2LRoute(newRouteData);
                console.log('[Disruption Monitor] HC2L route recalculated successfully');
              }
            }
          } else {
            console.error('[Disruption Monitor] Unknown algorithm:', algorithm);
          }
        } catch (apiError) {
          console.error('[Disruption Monitor] API call error:', apiError);
          throw apiError;
        }
        
        if (newRouteData) {
          // Update stored route data with new metrics
          window.currentRouteData = newRouteData;
          
          // Update UI panels
          if (typeof updateRouteMetrics === 'function') {
            updateRouteMetrics(newRouteData);
          }
          if (typeof updateAdminPerformanceMetrics === 'function') {
            updateAdminPerformanceMetrics(newRouteData);
          }
          if (typeof updateCurrentPathPanel === 'function') {
            updateCurrentPathPanel(newRouteData);
          }
          
          showUpdateToast('✅ Route updated with latest disruptions', 'success');
        } else {
          showUpdateToast('⚠️ Route recalculation failed', 'warning');
        }
        
      } catch (routeError) {
        console.error('[Disruption Monitor] Route recalculation error:', routeError);
        showUpdateToast('⚠️ Error recalculating route: ' + routeError.message, 'warning');
      }
    }
    
  } catch (error) {
    console.error('[Disruption Monitor] Error handling update:', error);
    showUpdateToast('⚠️ Error updating route after disruption change', 'warning');
  } finally {
    isUpdating = false;
  }
}

/**
 * Manual trigger for disruption check (for testing or manual refresh)
 */
function manualDisruptionCheck() {
  console.log('[Disruption Monitor] Manual check triggered');
  checkForDisruptionUpdates();
}

// Auto-start monitoring when page loads
document.addEventListener('DOMContentLoaded', () => {
  console.log('[Disruption Monitor] Page loaded, starting monitoring...');
  startDisruptionMonitoring();
});

// Stop monitoring when page unloads
window.addEventListener('beforeunload', () => {
  stopDisruptionMonitoring();
});

// Export functions for external use
window.disruptionMonitor = {
  start: startDisruptionMonitoring,
  stop: stopDisruptionMonitoring,
  check: manualDisruptionCheck,
  isMonitoring: () => disruptionCheckInterval !== null,
  isUpdating: () => isUpdating
};

console.log('[Disruption Monitor] Module loaded');
