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
    // Show toast notification that we're updating
    showUpdateToast('🔄 Updating graph with new disruptions...', 'info');
    console.log('[Disruption Monitor] Starting graph update...');
    
    // Clear any cached incident data to force fresh fetch
    if (typeof window.clearCachedIncidentPayload === 'function') {
      window.clearCachedIncidentPayload();
      console.log('[Disruption Monitor] Cleared cached incident data');
    }
    
    // Clear cached traffic data to force fresh fetch
    if (typeof window.clearTrafficCache === 'function') {
      window.clearTrafficCache();
      console.log('[Disruption Monitor] Cleared cached traffic data');
    }
    
    // Reload traffic/flow overlay if visible (Show Flow Overlay toggle)
    const showTrafficOverlay = document.getElementById('show-traffic-overlay');
    if (showTrafficOverlay?.checked) {
      console.log('[Disruption Monitor] Reloading traffic overlay...');
      if (typeof window.handleTrafficOverlayToggle === 'function') {
        // Turn off and back on to refresh
        await window.handleTrafficOverlayToggle(false, { silent: true });
        await window.handleTrafficOverlayToggle(true, { silent: true });
        console.log('[Disruption Monitor] Traffic overlay refreshed');
      } else if (typeof applyTrafficOverlay === 'function') {
        const trafficRouteOnly = document.getElementById('traffic-route-only');
        const routeOnly = trafficRouteOnly ? trafficRouteOnly.checked : false;
        await applyTrafficOverlay('both', routeOnly);
        console.log('[Disruption Monitor] Traffic overlay reapplied');
      }
    }
    
    // Reload incident markers if visible (Show Active Incidents toggle)
    const showActiveIncidents = document.getElementById('show-active-incidents');
    if (showActiveIncidents?.checked) {
      console.log('[Disruption Monitor] Reloading incident markers...');
      if (typeof window.handleActiveIncidentsToggle === 'function') {
        // Turn off and back on to refresh with fresh data
        await window.handleActiveIncidentsToggle(false, { silent: true });
        await window.handleActiveIncidentsToggle(true, { silent: true });
        console.log('[Disruption Monitor] Incident markers refreshed');
      } else if (typeof showAllDisruptionsOnMap === 'function') {
        // Fallback: Fetch and display incidents manually
        try {
          const response = await fetch('/get_active_disruptions');
          const data = await response.json();
          if (data.success) {
            if (typeof clearDisruptionMarkers === 'function') {
              clearDisruptionMarkers();
            }
            showAllDisruptionsOnMap(data);
            console.log('[Disruption Monitor] Incident markers refreshed via API');
          }
        } catch (err) {
          console.error('[Disruption Monitor] Error refreshing incidents:', err);
        }
      }
    }
    
    // Show success notification
    if (updateData.message) {
      showUpdateToast(updateData.message, updateData.notification_type || 'info');
      console.log('[Disruption Monitor] Notification shown:', updateData.message);
    } else {
      showUpdateToast('✅ Graph updated with new disruptions', 'success');
    }
    
    // Auto-recalculate route if enabled and route exists
    if (ENABLE_AUTO_ROUTE_UPDATE && window.currentRouteData) {
      console.log('[Disruption Monitor] Triggering automatic route recalculation...');
      
      // Use the dedicated auto-route-recalculator if available
      if (typeof window.triggerAutoRouteRecalculation === 'function') {
        try {
          await window.triggerAutoRouteRecalculation();
        } catch (routeError) {
          console.error('[Disruption Monitor] Route recalculation error:', routeError);
          showUpdateToast('⚠️ Error recalculating route: ' + routeError.message, 'warning');
        }
      } else {
        console.warn('[Disruption Monitor] triggerAutoRouteRecalculation not available');
        showUpdateToast('⚠️ Route auto-update module not loaded', 'warning');
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
