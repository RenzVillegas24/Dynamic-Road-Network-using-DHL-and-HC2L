/**
 * Header Location Pickers Initialization
 * Initializes the start and destination LocationPicker components for the header
 */

// Store references to header pickers globally for external access
window.headerStartPicker = null;
window.headerDestPicker = null;

/**
 * Initialize header location pickers
 * Called after DOM is ready and map is initialized
 */
function initializeHeaderLocationPickers() {
    console.log('🔍 Initializing header location pickers...');
    
    // Wait for map to be available
    if (typeof map === 'undefined' || !map) {
        console.log('⏳ Waiting for map to initialize...');
        setTimeout(initializeHeaderLocationPickers, 100);
        return;
    }
    
    // Initialize Start Location Picker
    const startContainer = document.getElementById('header-start-location-container');
    if (startContainer) {
        window.headerStartPicker = new LocationPicker({
            containerId: 'header-start-location-container',
            variant: 'start',
            placeholder: 'Search start location...',
            osmSnapping: true,
            snapRadius: 25,
            map: map,
            onSelect: handleHeaderStartLocationSelect,
            onClear: handleHeaderStartLocationClear,
            onPinModeStart: () => {
                // Cancel dest picker pin mode if active
                if (window.headerDestPicker && window.headerDestPicker.isPinning) {
                    window.headerDestPicker._deactivatePinMode();
                }
            }
        });
        console.log('✅ Header start location picker initialized');
    } else {
        console.warn('⚠️ Header start location container not found');
    }
    
    // Initialize Destination Location Picker
    const destContainer = document.getElementById('header-dest-location-container');
    if (destContainer) {
        window.headerDestPicker = new LocationPicker({
            containerId: 'header-dest-location-container',
            variant: 'destination',
            placeholder: 'Search destination...',
            osmSnapping: true,
            snapRadius: 25,
            map: map,
            onSelect: handleHeaderDestLocationSelect,
            onClear: handleHeaderDestLocationClear,
            onPinModeStart: () => {
                // Cancel start picker pin mode if active
                if (window.headerStartPicker && window.headerStartPicker.isPinning) {
                    window.headerStartPicker._deactivatePinMode();
                }
            }
        });
        console.log('✅ Header destination location picker initialized');
    } else {
        console.warn('⚠️ Header destination location container not found');
    }
    
    console.log('✅ Header location pickers fully initialized');
}

/**
 * Handle start location selection from header picker
 */
function handleHeaderStartLocationSelect(result) {
    console.log('📍 Header start location selected:', result);
    
    // Clear existing start markers using legacy function if available
    if (typeof clearStartMarkers === 'function') {
        clearStartMarkers();
    }
    
    // Use OSM snapping handler for consistent behavior with rest of app
    if (result.snapData && typeof handleOSMStartLocationPin === 'function') {
        // The picker already created markers, but we need to update the global state
        // Call the legacy handler to maintain compatibility
        const lat = result.actualPin.lat;
        const lng = result.actualPin.lng;
        
        // Store in global state
        window.startLocation = {
            lat: lat,
            lng: lng,
            snapped_lat: result.snappedPin?.lat || lat,
            snapped_lng: result.snappedPin?.lng || lng,
            source_id: result.snapData?.routing_nodes?.[0] || 0,
            target_id: result.snapData?.routing_nodes?.[1] || 0,
            road_name: result.name,
            snap_data: result.snapData
        };
        
        // Update the existing OSM snap markers using the existing system
        // This ensures compatibility with existing route calculation
        handleOSMStartLocationPin(lat, lng);
        
    } else if (result.actualPin) {
        // Fallback - just store the location
        window.startLocation = {
            lat: result.actualPin.lat,
            lng: result.actualPin.lng,
            snapped_lat: result.snappedPin?.lat || result.actualPin.lat,
            snapped_lng: result.snappedPin?.lng || result.actualPin.lng,
            road_name: result.name
        };
    }
    
    // Update input display for legacy compatibility
    const legacyInput = document.getElementById('start-location-input');
    if (legacyInput) {
        legacyInput.value = result.name?.split(',')[0] || '';
    }
}

/**
 * Handle destination location selection from header picker
 */
function handleHeaderDestLocationSelect(result) {
    console.log('📍 Header destination location selected:', result);
    
    // Clear existing dest markers using legacy function if available
    if (typeof clearDestMarkers === 'function') {
        clearDestMarkers();
    }
    
    // Use OSM snapping handler for consistent behavior with rest of app
    if (result.snapData && typeof handleOSMDestLocationPin === 'function') {
        const lat = result.actualPin.lat;
        const lng = result.actualPin.lng;
        
        // Store in global state
        window.destLocation = {
            lat: lat,
            lng: lng,
            snapped_lat: result.snappedPin?.lat || lat,
            snapped_lng: result.snappedPin?.lng || lng,
            source_id: result.snapData?.routing_nodes?.[0] || 0,
            target_id: result.snapData?.routing_nodes?.[1] || 0,
            road_name: result.name,
            snap_data: result.snapData
        };
        
        // Update the existing OSM snap markers using the existing system
        handleOSMDestLocationPin(lat, lng);
        
    } else if (result.actualPin) {
        // Fallback - just store the location
        window.destLocation = {
            lat: result.actualPin.lat,
            lng: result.actualPin.lng,
            snapped_lat: result.snappedPin?.lat || result.actualPin.lat,
            snapped_lng: result.snappedPin?.lng || result.actualPin.lng,
            road_name: result.name
        };
    }
    
    // Update input display for legacy compatibility
    const legacyInput = document.getElementById('dest-location-input');
    if (legacyInput) {
        legacyInput.value = result.name?.split(',')[0] || '';
    }
}

/**
 * Handle start location clear
 */
function handleHeaderStartLocationClear() {
    console.log('🗑️ Header start location cleared');
    
    if (typeof clearStartMarkers === 'function') {
        clearStartMarkers();
    }
    
    window.startLocation = null;
    
    const legacyInput = document.getElementById('start-location-input');
    if (legacyInput) {
        legacyInput.value = '';
    }
}

/**
 * Handle destination location clear
 */
function handleHeaderDestLocationClear() {
    console.log('🗑️ Header destination location cleared');
    
    if (typeof clearDestMarkers === 'function') {
        clearDestMarkers();
    }
    
    window.destLocation = null;
    
    const legacyInput = document.getElementById('dest-location-input');
    if (legacyInput) {
        legacyInput.value = '';
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Delay initialization to ensure map is ready
        setTimeout(initializeHeaderLocationPickers, 500);
    });
} else {
    // DOM already loaded, delay to ensure map is ready
    setTimeout(initializeHeaderLocationPickers, 500);
}

// Export for external usage
window.initializeHeaderLocationPickers = initializeHeaderLocationPickers;
