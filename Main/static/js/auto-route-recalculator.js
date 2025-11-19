/**
 * Auto Route Recalculator
 * 
 * Automatically recalculates route when disruptions are updated
 * (triggered after incident add/remove or disruption reload)
 * 
 * This replaces the polling-based disruption monitor
 * Routes are recalculated on-demand when disruptions change
 */

/**
 * Trigger automatic route recalculation
 * Called by frontend incident handlers after disruption file creation
 */
async function triggerAutoRouteRecalculation() {
  // Check if we have an active route
  if (!window.currentRouteData) {
    console.log('[AutoRouteRecalculator] No active route, skipping recalculation');
    return;
  }

  // Check if we have snap points
  if (!window.osmSnapMarkers?.start?.data || !window.osmSnapMarkers?.dest?.data) {
    console.log('[AutoRouteRecalculator] Missing snap point data, skipping recalculation');
    return;
  }

  try {
    console.log('[AutoRouteRecalculator] Triggering automatic route recalculation...');
    
    // Get stored route data
    const routeData = window.currentRouteData;
    const startSnap = window.osmSnapMarkers.start.data;
    const destSnap = window.osmSnapMarkers.dest.data;
    
    // Get current algorithm selection
    let algorithm = 'hc2l'; // Default
    if (typeof getSelectedAlgorithm === 'function') {
      algorithm = getSelectedAlgorithm();
    } else {
      const selectedAlgo = document.querySelector('input[name="algorithm"]:checked');
      if (selectedAlgo) {
        algorithm = selectedAlgo.value.toLowerCase();
      }
    }
    
    // Get dataset mode
    const datasetRadio = document.querySelector('input[name="dataset"]:checked');
    const datasetMode = datasetRadio ? datasetRadio.value : 'none';
    const useDisruptions = datasetMode !== 'none';
    
    // Get threshold for HC2L
    let threshold = 0.5;
    const thresholdInput = document.getElementById('threshold-input');
    if (thresholdInput) {
      threshold = parseFloat(thresholdInput.value);
    }
    
    // Get generate_alternatives flag from "Show Alternative Routes" toggle
    let generateAlternatives = false;
    const showAltRoutesToggle = document.getElementById('show-alternative-routes');
    if (showAltRoutesToggle) {
      generateAlternatives = showAltRoutesToggle.checked;
    }
    
    // Prepare request body matching the route computation API
    const requestBody = {
      start_lat: startSnap.latitude || window.startLocation?.lat,
      start_lng: startSnap.longitude || window.startLocation?.lng,
      dest_lat: destSnap.latitude || window.destLocation?.lat,
      dest_lng: destSnap.longitude || window.destLocation?.lng,
      algorithm: algorithm,
      use_disruptions: useDisruptions,
      dataset_mode: datasetMode,
      tau_threshold: threshold,
      generate_alternatives: generateAlternatives,
      // Add OSM edge data for routing
      start_osm_edge: {
        routing_nodes: startSnap.routing_nodes,
        osm_nodes: startSnap.osm_nodes,
        snap_position: startSnap.snap_position,
        road_name: startSnap.road_name,
        oneway: startSnap.oneway
      },
      dest_osm_edge: {
        routing_nodes: destSnap.routing_nodes,
        osm_nodes: destSnap.osm_nodes,
        snap_position: destSnap.snap_position,
        road_name: destSnap.road_name,
        oneway: destSnap.oneway
      }
    };
    
    console.log('[AutoRouteRecalculator] Request body:', requestBody);
    
    // Call backend endpoint
    const response = await fetch('/trigger_route_recalculation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('[AutoRouteRecalculator] HTTP error:', response.status, errorText);
      showUpdateToast(`⚠️ Auto route update failed: HTTP ${response.status}`, 'warning');
      return;
    }
    
    const newRouteData = await response.json();
    
    if (!newRouteData.success) {
      console.error('[AutoRouteRecalculator] Backend error:', newRouteData.error);
      showUpdateToast(`⚠️ Auto route update failed: ${newRouteData.error}`, 'warning');
      return;
    }
    
    console.log('[AutoRouteRecalculator] Route recalculated successfully');
    
    // Update the stored route data
    window.currentRouteData = newRouteData;
    
    // Display the updated route on map
    if (algorithm === 'dhl' && typeof displayDHLRoute === 'function') {
      displayDHLRoute(newRouteData);
      console.log('[AutoRouteRecalculator] DHL route displayed');
    } else if (algorithm === 'hc2l' && typeof displayDHC2LRoute === 'function') {
      displayDHC2LRoute(newRouteData);
      console.log('[AutoRouteRecalculator] HC2L route displayed');
    }
    
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
    
  } catch (error) {
    console.error('[AutoRouteRecalculator] Error:', error);
    showUpdateToast(`⚠️ Error updating route: ${error.message}`, 'warning');
  }
}

// Export for external use
window.triggerAutoRouteRecalculation = triggerAutoRouteRecalculation;

console.log('[AutoRouteRecalculator] Module loaded');
