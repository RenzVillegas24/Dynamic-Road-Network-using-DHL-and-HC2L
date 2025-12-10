/**
 * Report Panel Location Picker Initialization
 * Initializes the LocationPicker component for the report disruption panel
 */

// Store reference to report picker globally for external access
window.reportLocationPicker = null;

/**
 * Initialize report panel location picker
 * Called after DOM is ready and map is initialized
 */
function initializeReportLocationPicker() {
    console.log('🔍 Initializing report panel location picker...');
    
    // Wait for map to be available
    if (typeof map === 'undefined' || !map) {
        console.log('⏳ Waiting for map to initialize...');
        setTimeout(initializeReportLocationPicker, 100);
        return;
    }
    
    // Wait for LocationPicker class to be available
    if (typeof LocationPicker === 'undefined') {
        console.log('⏳ Waiting for LocationPicker class...');
        setTimeout(initializeReportLocationPicker, 100);
        return;
    }
    
    // Initialize Report Location Picker
    const reportContainer = document.getElementById('report-location-container');
    if (reportContainer) {
        window.reportLocationPicker = new LocationPicker({
            containerId: 'report-location-container',
            variant: 'normal',  // Purple/blue for report
            placeholder: 'Search or pin incident location...',
            osmSnapping: true,
            snapRadius: 25,
            showCoordinates: true,
            map: map,
            onSelect: handleReportLocationSelect,
            onClear: handleReportLocationClear,
            onPinModeStart: () => {
                // Cancel other picker pin modes if active
                if (window.headerStartPicker && window.headerStartPicker.isPinning) {
                    window.headerStartPicker._deactivatePinMode();
                }
                if (window.headerDestPicker && window.headerDestPicker.isPinning) {
                    window.headerDestPicker._deactivatePinMode();
                }
            }
        });
        console.log('✅ Report location picker initialized');
    } else {
        console.warn('⚠️ Report location container not found');
    }
    
    console.log('✅ Report panel location picker fully initialized');
}

/**
 * Handle report location selection from picker
 */
function handleReportLocationSelect(result) {
    console.log('📍 Report location selected:', result);
    
    // Store in global state (compatible with existing form submission)
    window.reportLocation = {
        lat: result.actualPin.lat,
        lng: result.actualPin.lng,
        snapped_lat: result.snappedPin?.lat || result.actualPin.lat,
        snapped_lng: result.snappedPin?.lng || result.actualPin.lng,
        source_id: result.snapData?.routing_nodes?.[0] || 0,
        target_id: result.snapData?.routing_nodes?.[1] || 0,
        road_name: result.name,
        highway_type: result.snapData?.highway_type || 'residential',
        distance_m: result.snapData?.distance_m || 0,
        snap_data: result.snapData
    };
    
    // Update the coordinates display
    const coordsElement = document.getElementById('disruption-coords');
    if (coordsElement && result.snappedPin) {
        coordsElement.textContent = `📍 ${result.snappedPin.lat.toFixed(6)}, ${result.snappedPin.lng.toFixed(6)}`;
        coordsElement.classList.remove('hidden');
    }
    
    // Legacy compatibility: update pin-disruption-text if it exists
    const pinText = document.getElementById('pin-disruption-text');
    if (pinText) {
        pinText.textContent = result.name || 'Location pinned';
    }
}

/**
 * Handle report location clear
 */
function handleReportLocationClear() {
    console.log('🗑️ Report location cleared');
    
    // Clear global state
    window.reportLocation = null;
    
    // Clear report markers (legacy compatibility)
    if (typeof clearReportMarkers === 'function') {
        clearReportMarkers();
    }
    
    // Hide coordinates display
    const coordsElement = document.getElementById('disruption-coords');
    if (coordsElement) {
        coordsElement.classList.add('hidden');
        coordsElement.textContent = '';
    }
    
    // Reset pin text (legacy compatibility)
    const pinText = document.getElementById('pin-disruption-text');
    if (pinText) {
        pinText.textContent = 'Click to pin location on map';
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Delay initialization to ensure map and LocationPicker are ready
        setTimeout(initializeReportLocationPicker, 500);
    });
} else {
    // DOM already loaded, delay to ensure dependencies are ready
    setTimeout(initializeReportLocationPicker, 500);
}

// Export for external usage
window.initializeReportLocationPicker = initializeReportLocationPicker;
