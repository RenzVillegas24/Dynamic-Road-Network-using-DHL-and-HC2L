// auto-route-updater.js - Automatic route recalculation on disruption updates

let currentRouteId = null;
let currentDisruptionHash = null;
let pollingInterval = null;
const POLL_INTERVAL_MS = 60000; // Poll every 60 seconds

/**
 * Start monitoring for disruption updates and auto-recalculate route
 */
function startAutoRouteUpdates(routeData) {
  console.log('🔄 Starting automatic route updates...');
  
  // Generate unique route ID
  currentRouteId = `route_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
  // Register route with backend
  fetch('/register_active_route', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      route_id: currentRouteId,
      algorithm: routeData.algorithm || 'unknown',
      start_lat: routeData.start_lat,
      start_lng: routeData.start_lng,
      dest_lat: routeData.dest_lat,
      dest_lng: routeData.dest_lng,
      use_disruptions: routeData.use_disruptions || false
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log(`✅ Route registered: ${currentRouteId}`);
      
      // Start polling for updates
      startDisruptionPolling();
    } else {
      console.error('❌ Failed to register route:', data.error);
    }
  })
  .catch(error => {
    console.error('Error registering route:', error);
  });
}

/**
 * Stop monitoring for disruption updates
 */
function stopAutoRouteUpdates() {
  console.log('🛑 Stopping automatic route updates...');
  
  // Stop polling
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
  
  // Unregister route
  if (currentRouteId) {
    fetch('/unregister_active_route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        route_id: currentRouteId
      })
    })
    .then(response => response.json())
    .then(data => {
      console.log('✅ Route unregistered');
    })
    .catch(error => {
      console.error('Error unregistering route:', error);
    });
    
    currentRouteId = null;
  }
  
  currentDisruptionHash = null;
}

/**
 * Start polling for disruption file changes
 */
function startDisruptionPolling() {
  // Clear any existing interval
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }
  
  // Initial check
  checkDisruptionUpdates();
  
  // Set up periodic polling
  pollingInterval = setInterval(() => {
    checkDisruptionUpdates();
  }, POLL_INTERVAL_MS);
  
  console.log(`🔄 Polling started (every ${POLL_INTERVAL_MS / 1000}s)`);
}

/**
 * Check if disruption files have been updated
 */
function checkDisruptionUpdates() {
  fetch('/check_disruption_updates')
    .then(response => response.json())
    .then(data => {
      if (data.success && data.hash) {
        // Check if hash has changed
        if (currentDisruptionHash === null) {
          // First time - just store the hash
          currentDisruptionHash = data.hash;
          console.log('📋 Initial disruption hash:', data.hash.substring(0, 8));
        } else if (currentDisruptionHash !== data.hash) {
          // Hash changed - disruptions updated!
          console.log('🚦 Disruption update detected!');
          console.log('   Old hash:', currentDisruptionHash.substring(0, 8));
          console.log('   New hash:', data.hash.substring(0, 8));
          
          currentDisruptionHash = data.hash;
          
          // Show notification
          showUpdateToast('Disruptions updated - Recalculating route...', 'info');
          
          // Trigger route recalculation
          triggerRouteRecalculation();
        } else {
          console.log('✓ No disruption changes detected');
        }
      }
    })
    .catch(error => {
      console.error('Error checking disruption updates:', error);
    });
}

/**
 * Trigger automatic route recalculation
 */
function triggerRouteRecalculation() {
  console.log('🔄 Auto-recalculating route...');
  
  // Check which algorithm is currently selected
  const selectedAlgo = document.querySelector('input[name="algo-dataset"]:checked');
  
  if (!selectedAlgo) {
    console.error('No algorithm selected');
    return;
  }
  
  const algoValue = selectedAlgo.value;
  const useDisruptions = algoValue.includes('disrupted');
  
  // Check if we have start and destination locations
  if (!window.startLocation || !window.destLocation) {
    console.warn('⚠️  Cannot recalculate - missing start or destination');
    return;
  }
  
  // Trigger the route recalculation using global function
  const goButton = document.getElementById('go-button');
  if (goButton && !goButton.disabled) {
    console.log('🎯 Triggering route recalculation via global function');
    handleGoButtonClick();
    
    // Visual feedback
    goButton.classList.add('animate-pulse');
    setTimeout(() => {
      goButton.classList.remove('animate-pulse');
    }, 2000);
  } else {
    console.warn('⚠️  Go button not available');
  }
}

/**
 * Initialize auto-route updater when route is calculated
 */
function initializeAutoRouteUpdater() {
  console.log('🔧 Auto-route updater module loaded');
  
  // Listen for route calculations
  // This should be called after a successful route calculation
  window.addEventListener('routeCalculated', (event) => {
    const routeData = event.detail;
    console.log('📍 Route calculated, starting auto-updates');
    startAutoRouteUpdates(routeData);
  });
  
  // Stop updates when page is about to unload
  window.addEventListener('beforeunload', () => {
    stopAutoRouteUpdates();
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeAutoRouteUpdater);
} else {
  initializeAutoRouteUpdater();
}

// Expose functions to global scope
window.startAutoRouteUpdates = startAutoRouteUpdates;
window.stopAutoRouteUpdates = stopAutoRouteUpdates;
window.triggerRouteRecalculation = triggerRouteRecalculation;

console.log('✅ Auto-route updater module initialized');
