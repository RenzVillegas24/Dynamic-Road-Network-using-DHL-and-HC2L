/**
 * Custom Demo Creator Module
 * Highly customizable demo creation with location selection and traffic simulation
 */

// Demo creator state
const DemoCreator = {
    currentDemo: null,
    savedDemos: [],
    isCreating: false,
    currentStep: 'locations', // 'locations', 'traffic', 'sequence', 'review'
    demoConfig: {
        name: '',
        description: '',
        locations: {
            waypoints: [],  // Array of {name, lat, lng, type: 'start'|'waypoint'|'end'}
        },
        traffic: {
            enabled: false,
            mode: 'both', // 'none', 'both', 'custom'
            customSegments: [] // Custom traffic disruptions
        },
        sequence: {
            algorithm: 'hc2l', // 'hc2l', 'dhl', 'both'
            tauValues: [0.5],
            compareAlgorithms: false,
            showMetrics: true,
            autoPlay: true,
            stepDelay: 2000 // ms between steps
        },
        advanced: {
            snapToRoads: true,
            showUpdateRegions: true,
            enableLogging: true,
            compareWithGoogle: false
        }
    }
};

/**
 * Open custom demo creator panel
 */
function openDemoCreator() {
    const panel = document.getElementById('demo-creator-panel');
    if (panel) {
        panel.classList.remove('translate-x-full');
        resetDemoCreator();
        logInfo('Custom demo creator opened');
    }
}

/**
 * Close custom demo creator panel
 */
function closeDemoCreator() {
    const panel = document.getElementById('demo-creator-panel');
    if (panel) {
        panel.classList.add('translate-x-full');
    }
}

/**
 * Reset demo creator to initial state
 */
function resetDemoCreator() {
    DemoCreator.currentStep = 'locations';
    DemoCreator.demoConfig = {
        name: '',
        description: '',
        locations: { waypoints: [] },
        traffic: { enabled: false, mode: 'both', customSegments: [] },
        sequence: {
            algorithm: 'hc2l',
            tauValues: [0.5],
            compareAlgorithms: false,
            showMetrics: true,
            autoPlay: true,
            stepDelay: 2000
        },
        advanced: {
            snapToRoads: true,
            showUpdateRegions: true,
            enableLogging: true,
            compareWithGoogle: false
        }
    };
    updateDemoCreatorUI();
}

/**
 * Update demo creator UI based on current step
 */
function updateDemoCreatorUI() {
    // Update step indicators
    const steps = ['locations', 'traffic', 'sequence', 'review'];
    steps.forEach((step, index) => {
        const indicator = document.getElementById(`step-indicator-${step}`);
        if (indicator) {
            if (step === DemoCreator.currentStep) {
                indicator.classList.add('bg-blue-600', 'text-white');
                indicator.classList.remove('bg-gray-300', 'text-gray-600');
            } else if (steps.indexOf(step) < steps.indexOf(DemoCreator.currentStep)) {
                indicator.classList.add('bg-green-600', 'text-white');
                indicator.classList.remove('bg-gray-300', 'text-gray-600', 'bg-blue-600');
            } else {
                indicator.classList.add('bg-gray-300', 'text-gray-600');
                indicator.classList.remove('bg-blue-600', 'text-white', 'bg-green-600');
            }
        }
    });
    
    // Show/hide step content
    steps.forEach(step => {
        const content = document.getElementById(`demo-step-${step}`);
        if (content) {
            if (step === DemoCreator.currentStep) {
                content.classList.remove('hidden');
            } else {
                content.classList.add('hidden');
            }
        }
    });
    
    // Update waypoints list
    updateWaypointsList();
    
    // Update traffic segments list
    updateTrafficSegmentsList();
    
    // Update review summary
    if (DemoCreator.currentStep === 'review') {
        updateReviewSummary();
    }
}

/**
 * Navigate to next step
 */
function demoCreatorNextStep() {
    const steps = ['locations', 'traffic', 'sequence', 'review'];
    const currentIndex = steps.indexOf(DemoCreator.currentStep);
    
    if (currentIndex < steps.length - 1) {
        // Validate current step before proceeding
        if (validateCurrentStep()) {
            DemoCreator.currentStep = steps[currentIndex + 1];
            updateDemoCreatorUI();
            logInfo(`Advanced to demo step: ${DemoCreator.currentStep}`);
        }
    }
}

/**
 * Navigate to previous step
 */
function demoCreatorPrevStep() {
    const steps = ['locations', 'traffic', 'sequence', 'review'];
    const currentIndex = steps.indexOf(DemoCreator.currentStep);
    
    if (currentIndex > 0) {
        DemoCreator.currentStep = steps[currentIndex - 1];
        updateDemoCreatorUI();
    }
}

/**
 * Validate current step
 */
function validateCurrentStep() {
    const config = DemoCreator.demoConfig;
    
    switch (DemoCreator.currentStep) {
        case 'locations':
            if (config.locations.waypoints.length < 2) {
                logWarning('Please add at least 2 waypoints (start and end)');
                showUpdateToast('Add at least 2 waypoints', 'warning');
                return false;
            }
            break;
        case 'traffic':
            // Traffic is optional, always valid
            break;
        case 'sequence':
            if (config.sequence.tauValues.length === 0) {
                logWarning('Please add at least one τ value');
                showUpdateToast('Add at least one τ value', 'warning');
                return false;
            }
            break;
    }
    
    return true;
}

/**
 * Add waypoint by clicking on map
 */
let addingWaypoint = false;
function addWaypointFromMap() {
    addingWaypoint = true;
    map.getContainer().style.cursor = 'crosshair';
    showUpdateToast('Click on map to add waypoint', 'info');
    logInfo('Waypoint selection mode activated');
    
    // Add one-time click handler
    const clickHandler = (e) => {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        
        // Determine waypoint type
        let type = 'waypoint';
        if (DemoCreator.demoConfig.locations.waypoints.length === 0) {
            type = 'start';
        }
        
        // Add waypoint
        addWaypoint(lat, lng, `Waypoint ${DemoCreator.demoConfig.locations.waypoints.length + 1}`, type);
        
        // Reset
        addingWaypoint = false;
        map.getContainer().style.cursor = '';
        map.off('click', clickHandler);
    };
    
    map.once('click', clickHandler);
}

/**
 * Add waypoint to demo configuration
 */
function addWaypoint(lat, lng, name, type = 'waypoint') {
    const waypoint = {
        id: `wp-${Date.now()}`,
        name,
        lat,
        lng,
        type
    };
    
    DemoCreator.demoConfig.locations.waypoints.push(waypoint);
    updateWaypointsList();
    logSuccess(`Added waypoint: ${name} (${type})`, { lat, lng });
    
    // Add marker to map
    addWaypointMarker(waypoint);
}

/**
 * Add waypoint marker to map
 */
function addWaypointMarker(waypoint) {
    const iconColor = waypoint.type === 'start' ? 'green' : 
                     waypoint.type === 'end' ? 'red' : 'blue';
    
    const icon = L.icon({
        iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${iconColor}.png`,
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -34],
        shadowSize: [41, 41]
    });
    
    const marker = L.marker([waypoint.lat, waypoint.lng], { icon })
        .bindPopup(`<b>${waypoint.name}</b><br>Type: ${waypoint.type}`)
        .addTo(map);
    
    // Store marker reference
    if (!DemoCreator.waypointMarkers) {
        DemoCreator.waypointMarkers = {};
    }
    DemoCreator.waypointMarkers[waypoint.id] = marker;
}

/**
 * Remove waypoint
 */
function removeWaypoint(waypointId) {
    const index = DemoCreator.demoConfig.locations.waypoints.findIndex(wp => wp.id === waypointId);
    if (index !== -1) {
        const waypoint = DemoCreator.demoConfig.locations.waypoints[index];
        DemoCreator.demoConfig.locations.waypoints.splice(index, 1);
        
        // Remove marker
        if (DemoCreator.waypointMarkers && DemoCreator.waypointMarkers[waypointId]) {
            map.removeLayer(DemoCreator.waypointMarkers[waypointId]);
            delete DemoCreator.waypointMarkers[waypointId];
        }
        
        updateWaypointsList();
        logInfo(`Removed waypoint: ${waypoint.name}`);
    }
}

/**
 * Mark last waypoint as end
 */
function markLastWaypointAsEnd() {
    const waypoints = DemoCreator.demoConfig.locations.waypoints;
    if (waypoints.length > 0) {
        waypoints[waypoints.length - 1].type = 'end';
        updateWaypointsList();
        logSuccess('Last waypoint marked as destination');
    }
}

/**
 * Update waypoints list UI
 */
function updateWaypointsList() {
    const container = document.getElementById('waypoints-list');
    if (!container) return;
    
    const waypoints = DemoCreator.demoConfig.locations.waypoints;
    
    if (waypoints.length === 0) {
        container.innerHTML = `
            <div class="text-center py-8 text-gray-400">
                <svg class="w-16 h-16 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path>
                </svg>
                <p class="text-sm">No waypoints added yet</p>
                <p class="text-xs mt-1">Click "Add on Map" to begin</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = waypoints.map((wp, index) => {
        const typeColor = wp.type === 'start' ? 'bg-green-100 text-green-700' :
                         wp.type === 'end' ? 'bg-red-100 text-red-700' :
                         'bg-blue-100 text-blue-700';
        
        return `
            <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                <span class="text-2xl">${wp.type === 'start' ? '🟢' : wp.type === 'end' ? '🔴' : '🔵'}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-semibold text-gray-800 truncate">${wp.name}</div>
                    <div class="text-xs text-gray-500">
                        ${wp.lat.toFixed(5)}, ${wp.lng.toFixed(5)}
                    </div>
                    <span class="inline-block text-xs px-2 py-0.5 rounded ${typeColor} font-medium mt-1">
                        ${wp.type}
                    </span>
                </div>
                <button onclick="removeWaypoint('${wp.id}')" 
                        class="p-2 hover:bg-red-100 rounded-lg transition-colors">
                    <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                </button>
            </div>
        `;
    }).join('');
}

/**
 * Add custom traffic segment
 */
let addingTrafficSegment = false;
function addTrafficSegmentFromMap() {
    addingTrafficSegment = true;
    map.getContainer().style.cursor = 'crosshair';
    showUpdateToast('Click on map to add traffic segment', 'info');
    logInfo('Traffic segment selection mode activated');
    
    // Add one-time click handler
    const clickHandler = async (e) => {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;
        
        // Snap to nearest road
        try {
            const response = await fetch('/find_nearest_osm_road', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat, lng })
            });
            
            const data = await response.json();
            
            if (data.success) {
                const segment = {
                    id: `ts-${Date.now()}`,
                    road_name: data.road_name || 'Unknown Road',
                    lat: data.snapped_point.lat,
                    lng: data.snapped_point.lng,
                    source: data.routing_nodes[0],
                    target: data.routing_nodes[1],
                    speed_kph: 30,
                    jam_factor: 5.0,
                    is_closed: false,
                    severity: 'medium'
                };
                
                DemoCreator.demoConfig.traffic.customSegments.push(segment);
                updateTrafficSegmentsList();
                logSuccess(`Added traffic segment on ${segment.road_name}`);
            } else {
                logWarning('Could not snap to road');
                showUpdateToast('Could not snap to road', 'warning');
            }
        } catch (error) {
            logError('Error adding traffic segment', { error: error.message });
        }
        
        // Reset
        addingTrafficSegment = false;
        map.getContainer().style.cursor = '';
        map.off('click', clickHandler);
    };
    
    map.once('click', clickHandler);
}

/**
 * Update traffic segments list UI
 */
function updateTrafficSegmentsList() {
    const container = document.getElementById('traffic-segments-list');
    if (!container) return;
    
    const segments = DemoCreator.demoConfig.traffic.customSegments;
    
    if (segments.length === 0) {
        container.innerHTML = `
            <div class="text-center py-6 text-gray-400">
                <p class="text-sm">No custom traffic segments</p>
                <p class="text-xs mt-1">Add segments to simulate specific congestion</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = segments.map(segment => {
        const severityColors = {
            light: 'bg-yellow-100 text-yellow-700',
            medium: 'bg-orange-100 text-orange-700',
            heavy: 'bg-red-100 text-red-700'
        };
        
        return `
            <div class="p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div class="flex items-center justify-between mb-2">
                    <span class="font-semibold text-gray-800">${segment.road_name}</span>
                    <button onclick="removeTrafficSegment('${segment.id}')" 
                            class="p-1 hover:bg-red-100 rounded transition-colors">
                        <svg class="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                  d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                <div class="grid grid-cols-2 gap-2 text-xs">
                    <div>
                        <span class="text-gray-600">Speed:</span>
                        <span class="font-semibold ml-1">${segment.speed_kph} km/h</span>
                    </div>
                    <div>
                        <span class="text-gray-600">Jam Factor:</span>
                        <span class="font-semibold ml-1">${segment.jam_factor}</span>
                    </div>
                </div>
                <span class="inline-block text-xs px-2 py-0.5 rounded ${severityColors[segment.severity]} font-medium mt-2">
                    ${segment.severity}
                </span>
            </div>
        `;
    }).join('');
}

/**
 * Remove traffic segment
 */
function removeTrafficSegment(segmentId) {
    const index = DemoCreator.demoConfig.traffic.customSegments.findIndex(s => s.id === segmentId);
    if (index !== -1) {
        DemoCreator.demoConfig.traffic.customSegments.splice(index, 1);
        updateTrafficSegmentsList();
        logInfo('Removed traffic segment');
    }
}

/**
 * Update review summary
 */
function updateReviewSummary() {
    const summary = document.getElementById('demo-review-summary');
    if (!summary) return;
    
    const config = DemoCreator.demoConfig;
    const waypointsCount = config.locations.waypoints.length;
    const trafficCount = config.traffic.customSegments.length;
    const tauCount = config.sequence.tauValues.length;
    
    summary.innerHTML = `
        <div class="space-y-4">
            <div>
                <h4 class="font-bold text-gray-800 mb-2">📍 Locations</h4>
                <p class="text-sm text-gray-600">${waypointsCount} waypoints configured</p>
            </div>
            
            <div>
                <h4 class="font-bold text-gray-800 mb-2">🚦 Traffic</h4>
                <p class="text-sm text-gray-600">
                    ${config.traffic.enabled ? `Enabled (${config.traffic.mode})` : 'Disabled'}
                    ${trafficCount > 0 ? `<br>${trafficCount} custom segments` : ''}
                </p>
            </div>
            
            <div>
                <h4 class="font-bold text-gray-800 mb-2">⚙️ Sequence</h4>
                <p class="text-sm text-gray-600">
                    Algorithm: ${config.sequence.algorithm.toUpperCase()}<br>
                    τ values: ${config.sequence.tauValues.join(', ')}<br>
                    Compare algorithms: ${config.sequence.compareAlgorithms ? 'Yes' : 'No'}
                </p>
            </div>
        </div>
    `;
}

/**
 * Save demo configuration
 */
function saveDemoConfig() {
    const name = document.getElementById('demo-name-input')?.value || `Demo ${Date.now()}`;
    const description = document.getElementById('demo-description-input')?.value || '';
    
    DemoCreator.demoConfig.name = name;
    DemoCreator.demoConfig.description = description;
    
    DemoCreator.savedDemos.push({ ...DemoCreator.demoConfig, savedAt: new Date() });
    
    // Save to localStorage
    localStorage.setItem('savedDemos', JSON.stringify(DemoCreator.savedDemos));
    
    logSuccess(`Demo configuration saved: ${name}`);
    showUpdateToast('Demo saved successfully', 'success');
}

/**
 * Run created demo
 */
async function runCreatedDemo() {
    logInfo('Starting custom demo execution');
    showUpdateToast('🎬 Running custom demo...', 'info');
    
    const config = DemoCreator.demoConfig;
    
    try {
        // Step 1: Set locations
        for (let i = 0; i < config.locations.waypoints.length; i++) {
            const waypoint = config.locations.waypoints[i];
            logInfo(`Setting waypoint ${i + 1}: ${waypoint.name}`);
            
            if (waypoint.type === 'start') {
                await handleOSMStartLocationPin(waypoint.lat, waypoint.lng);
            } else if (waypoint.type === 'end') {
                await handleOSMDestLocationPin(waypoint.lat, waypoint.lng);
            }
            
            await new Promise(resolve => setTimeout(resolve, config.sequence.stepDelay));
        }
        
        // Step 2: Apply traffic if enabled
        if (config.traffic.enabled) {
            logInfo('Applying traffic configuration');
            // Set traffic mode
            const trafficRadio = document.querySelector(`input[value="${config.traffic.mode}"]`);
            if (trafficRadio) {
                trafficRadio.checked = true;
                trafficRadio.dispatchEvent(new Event('change'));
            }
            
            await new Promise(resolve => setTimeout(resolve, config.sequence.stepDelay));
        }
        
        // Step 3: Run route calculations
        for (const tau of config.sequence.tauValues) {
            logInfo(`Calculating route with τ = ${tau}`);
            
            const thresholdInput = document.getElementById('threshold-input');
            if (thresholdInput) {
                thresholdInput.value = tau;
                thresholdInput.dispatchEvent(new Event('input'));
            }
            
            await computeRouteBasedOnSelection();
            await new Promise(resolve => setTimeout(resolve, config.sequence.stepDelay));
        }
        
        // Step 4: Algorithm comparison if enabled
        if (config.sequence.compareAlgorithms) {
            logInfo('Running algorithm comparison');
            const bothRadio = document.querySelector('input[value="both"]');
            if (bothRadio) {
                bothRadio.checked = true;
                bothRadio.dispatchEvent(new Event('change'));
            }
            
            await computeRouteBasedOnSelection();
        }
        
        logSuccess('Custom demo completed successfully');
        showUpdateToast('✅ Demo complete!', 'success');
        
    } catch (error) {
        logError('Demo execution failed', { error: error.message });
        showUpdateToast('Demo failed', 'error');
    }
}

// Expose functions globally
window.DemoCreator = DemoCreator;
window.openDemoCreator = openDemoCreator;
window.closeDemoCreator = closeDemoCreator;
window.resetDemoCreator = resetDemoCreator;
window.demoCreatorNextStep = demoCreatorNextStep;
window.demoCreatorPrevStep = demoCreatorPrevStep;
window.addWaypointFromMap = addWaypointFromMap;
window.removeWaypoint = removeWaypoint;
window.markLastWaypointAsEnd = markLastWaypointAsEnd;
window.addTrafficSegmentFromMap = addTrafficSegmentFromMap;
window.removeTrafficSegment = removeTrafficSegment;
window.saveDemoConfig = saveDemoConfig;
window.runCreatedDemo = runCreatedDemo;

console.log('✅ Custom demo creator module loaded');
