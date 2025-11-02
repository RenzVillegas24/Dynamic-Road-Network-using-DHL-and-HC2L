// search-and-drag.js - Draggable markers functionality (search moved to location-combobox.js)
// Pin button handlers are now in location-combobox.js

// Initialize event handlers when DOM is ready
function initializeSearchAndDragHandlers() {
  console.log('🎯 Initializing drag handlers...');
  console.log('✅ All drag handlers initialized (pin handlers in location-combobox.js)');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeSearchAndDragHandlers);
} else {
  // DOM already loaded
  initializeSearchAndDragHandlers();
}

// Make markers draggable with optimized route reloading
function makeMarkerDraggable(marker, type) {
  if (!marker || !marker.dragging) return;
  
  marker.dragging.enable();
  
  // Store original disruption state
  let wasUsingDisruptions = false;
  
  // Add hover effect
  marker.on('mouseover', function() {
    marker.setOpacity(0.7);
  });
  
  marker.on('mouseout', function() {
    marker.setOpacity(1.0);
  });
  
  // Handle drag start
  marker.on('dragstart', function() {
    // Fade route polylines
    if (routePolylines && routePolylines.length > 0) {
      routePolylines.forEach(polyline => {
        if (polyline && map) {
          polyline.setStyle({ opacity: 0.3 });
        }
      });
    }
    
    // Store disruption state and temporarily disable
    if (window.currentAlgorithm) {
      wasUsingDisruptions = window.currentAlgorithm.includes('disrupted');
    }
    
    console.log(`📍 Started dragging ${type} marker (disruptions: ${wasUsingDisruptions})`);
  });
  
  // Handle drag end
  marker.on('dragend', async function(event) {
    const newLat = event.target.getLatLng().lat;
    const newLng = event.target.getLatLng().lng;
    
    console.log(`📍 ${type} marker dragged to:`, newLat, newLng);
    
    try {
      // Update location based on type using existing OSM snapping
      if (type === 'start') {
        await handleOSMStartLocationPin(newLat, newLng);
        // Re-enable dragging after update
        if (window.startMarker) makeMarkerDraggable(window.startMarker, 'start');
      } else if (type === 'dest') {
        await handleOSMDestLocationPin(newLat, newLng);
        // Re-enable dragging after update
        if (window.destMarker) makeMarkerDraggable(window.destMarker, 'dest');
      }
      
      // Restore route polylines opacity
      if (routePolylines && routePolylines.length > 0) {
        routePolylines.forEach(polyline => {
          if (polyline && map) {
            polyline.setStyle({ opacity: 0.8 });
          }
        });
      }
      
      showUpdateToast(`${type === 'start' ? 'Start' : 'Destination'} location updated`, 'success');
      
      // Auto-recalculate route if both locations are set
      if (window.startLocation && window.destLocation) {
        console.log(`🔄 Auto-recalculating route after drag`);
        
        // Trigger route recalculation by clicking Go button
        // This reuses existing logic and respects current algorithm selection
        setTimeout(() => {
          const goButton = document.getElementById('go-button');
          if (goButton && !goButton.disabled) {
            goButton.click();
          } else {
            showUpdateToast('Click "Go" to calculate route', 'info');
          }
        }, 500); // Small delay to ensure marker update is complete
      }
      
    } catch (error) {
      console.error(`Error updating ${type} location:`, error);
      showUpdateToast(`Error updating ${type} location`, 'warning');
      
      // Restore opacity even on error
      if (routePolylines && routePolylines.length > 0) {
        routePolylines.forEach(polyline => {
          if (polyline && map) {
            polyline.setStyle({ opacity: 0.8 });
          }
        });
      }
    }
  });
}

// Wrap existing handleOSMStartLocationPin to add draggable support
(function() {
  const originalHandleOSMStart = window.handleOSMStartLocationPin;
  
  window.handleOSMStartLocationPin = async function(lat, lng, name = null) {
    // Call original function
    await originalHandleOSMStart(lat, lng);
    
    // Make the marker draggable
    if (window.startMarker) {
      makeMarkerDraggable(window.startMarker, 'start');
    }
    
    // Update input box with name if provided
    if (name) {
      const shortName = name.split(',')[0].substring(0, 40);
      
      // Update the input box with the selected location
      const startInput = document.getElementById('start-location-input');
      if (startInput) {
        startInput.value = shortName;
        console.log(`✅ Updated start-location-input to: ${shortName}`);
      }
    }
  };
})();

// Wrap existing handleOSMDestLocationPin to add draggable support
(function() {
  const originalHandleOSMDest = window.handleOSMDestLocationPin;
  
  window.handleOSMDestLocationPin = async function(lat, lng, name = null) {
    // Call original function
    await originalHandleOSMDest(lat, lng);
    
    // Make the marker draggable
    if (window.destMarker) {
      makeMarkerDraggable(window.destMarker, 'dest');
    }
    
    // Update input box with name if provided
    if (name) {
      const shortName = name.split(',')[0].substring(0, 40);
      
      // Also update the input box with the selected location
      const destInput = document.getElementById('dest-location-input');
      if (destInput) {
        destInput.value = shortName;
        console.log(`✅ Updated dest-location-input to: ${shortName}`);
      }
    }
  };
})();

console.log('✅ Search and drag functionality loaded');
