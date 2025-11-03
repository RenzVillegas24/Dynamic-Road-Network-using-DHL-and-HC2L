/**
 * OSM Road Geometry Snapping Module
 * 
 * Provides road-aware point snapping using actual OSM road geometries
 * instead of just intersection nodes. Creates visual markers showing
 * clicked point, snapped road point, and walking paths.
 */

// Global storage for snap markers and lines
window.osmSnapMarkers = {
    start: {
        clicked: null,
        snapped: null,
        connector: null,
        data: null
    },
    dest: {
        clicked: null,
        snapped: null,
        connector: null,
        data: null
    }
};

/**
 * Snap a point to the nearest OSM road using actual road geometries
 * 
 * The system will automatically expand the search radius up to 1000m
 * to always find the nearest road (never falls back to node-based selection).
 * 
 * @param {number} lat - Latitude of clicked point
 * @param {number} lng - Longitude of clicked point
 * @param {string} role - 'start' or 'dest'
 * @param {number} maxDistance - Initial maximum snapping distance in meters (default: 25)
 * @returns {Promise<object|null>} Snap result or null
 */
async function snapToOSMRoad(lat, lng, role = 'start', maxDistance = 25) {
    try {
        const response = await fetch('/find_nearest_osm_road', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lat: lat,
                lng: lng,
                max_distance: maxDistance,
                consider_hierarchy: true
                // Note: fallback_to_node removed - system always finds nearest road
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            console.warn(`OSM snapping failed for ${role}:`, data.error);
            return null;
        }
        
        // Check if search was expanded
        if (data.metadata && data.metadata.warning) {
            console.log(`⚠️  ${data.metadata.warning}`);
        }
        
        console.log(`✅ OSM snapping success for ${role}:`, {
            method: data.method,
            road: data.road_name,
            highway: data.highway_type,
            distance: data.distance_m,
            snap_position: data.snap_position
        });
        
        return data;
        
    } catch (error) {
        console.error(`Error in OSM snapping for ${role}:`, error);
        return null;
    }
}

/**
 * Create visual markers for OSM road snapping
 * 
 * @param {number} clickedLat - Latitude of clicked point
 * @param {number} clickedLng - Longitude of clicked point
 * @param {object} snapData - Snap result from snapToOSMRoad
 * @param {string} role - 'start' or 'dest'
 */
function createOSMSnapMarkers(clickedLat, clickedLng, snapData, role) {
    // Clear existing markers for this role
    clearOSMSnapMarkers(role);
    
    const isStart = role === 'start';
    const color = isStart ? '#4CAF50' : '#F44336'; // Green for start, red for dest
    const colorName = isStart ? 'green' : 'red';
    const markerIconUrl = isStart 
        ? 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png'
        : 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png';
    
    // 1. Marker at clicked location (semi-transparent)
    const clickedIcon = L.icon({
        iconUrl: markerIconUrl,
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
        iconSize: [20, 33],
        iconAnchor: [10, 33],
        popupAnchor: [0, -28],
        shadowSize: [33, 33]
    });
    
    window.osmSnapMarkers[role].clicked = L.marker([clickedLat, clickedLng], {
        icon: clickedIcon,
        title: `${isStart ? 'Start' : 'Destination'} (Clicked)`,
        opacity: 0.4,
        zIndexOffset: 1
    }).addTo(map);
    
    window.osmSnapMarkers[role].clicked.bindPopup(
        `<div class="p-2 min-w-[220px]">` +
        `<div class="font-bold text-lg mb-2 ${isStart ? 'text-green-700' : 'text-red-700'}">${isStart ? '🟢 Start Location' : '🔴 Destination'}</div>` +
        `<div class="text-sm text-slate-600 mb-1">📍 Clicked Point</div>` +
        `<div class="text-xs text-slate-500 font-mono bg-slate-50 px-2 py-1 rounded">${clickedLat.toFixed(6)}, ${clickedLng.toFixed(6)}</div>` +
        `</div>`
    );
    
    // 2. Marker at snapped road location (solid)
    const snappedIcon = L.divIcon({
        className: 'osm-snap-marker',
        html: `<div style="background: ${color}; border: 3px solid white; border-radius: 50%; width: 18px; height: 18px; box-shadow: 0 3px 6px rgba(0,0,0,0.5);"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
    });
    
    const snappedLat = snapData.snapped_point.lat;
    const snappedLng = snapData.snapped_point.lng;
    
    window.osmSnapMarkers[role].snapped = L.marker([snappedLat, snappedLng], {
        icon: snappedIcon,
        title: `${isStart ? 'Start' : 'Destination'} on Road`,
        zIndexOffset: 10
    }).addTo(map);
    
    const methodText = snapData.method === 'osm_geometry' 
        ? 'Snapped to OSM Road Geometry' 
        : 'Fallback to Nearest Node';
    
    window.osmSnapMarkers[role].snapped.bindPopup(
        `<div class="p-3 min-w-[280px]">` +
        `<div class="font-bold text-xl mb-3 ${isStart ? 'text-green-700' : 'text-red-700'} flex items-center">` +
        `<span class="mr-2">${isStart ? '🟢' : '🔴'}</span> ${isStart ? 'Start Point' : 'Destination'}` +
        `</div>` +
        `<div class="bg-gradient-to-r from-blue-50 to-indigo-50 px-3 py-2 rounded-lg mb-2 border border-blue-200">` +
        `<div class="text-xs text-blue-600 font-semibold uppercase tracking-wide mb-1">${methodText}</div>` +
        `</div>` +
        `<div class="space-y-2 text-sm">` +
        `<div class="flex items-start"><span class="font-semibold text-slate-700 w-20">🛣️ Road:</span><span class="text-slate-900 flex-1">${snapData.road_name}</span></div>` +
        `<div class="flex items-start"><span class="font-semibold text-slate-700 w-20">🏷️ Type:</span><span class="text-slate-600">${snapData.highway_type}</span></div>` +
        `${snapData.oneway ? '<div class="bg-yellow-50 border border-yellow-300 px-2 py-1 rounded text-yellow-800 font-semibold text-xs">⚠️ One-way road</div>' : ''}` +
        `<div class="flex items-start"><span class="font-semibold text-slate-700 w-20">📏 Distance:</span><span class="text-emerald-600 font-bold">${snapData.distance_m.toFixed(1)}m</span> <span class="text-slate-500 text-xs ml-1">from click</span></div>` +
        `${snapData.snap_position ? `<div class="flex items-start"><span class="font-semibold text-slate-700 w-20">📍 Position:</span><span class="text-blue-600">${(snapData.snap_position * 100).toFixed(0)}%</span> <span class="text-slate-500 text-xs ml-1">along edge</span></div>` : ''}` +
        `<div class="text-xs text-slate-400 font-mono bg-slate-50 px-2 py-1 rounded mt-2">${snappedLat.toFixed(6)}, ${snappedLng.toFixed(6)}</div>` +
        `</div>` +
        `</div>`
    );
    
    // 3. Dashed connector line (walking path)
    const distance = snapData.distance_m;
    if (distance > 3) { // Only show if meaningful distance
        window.osmSnapMarkers[role].connector = L.polyline([
            [clickedLat, clickedLng],
            [snappedLat, snappedLng]
        ], {
            color: '#757575',
            weight: 2,
            dashArray: '8, 12',
            opacity: 0.7,
            zIndexOffset: 0
        }).addTo(map);
        
        // Add popup for detailed info
        window.osmSnapMarkers[role].connector.bindPopup(
            `<div class="p-2 min-w-[200px]">` +
            `<div class="font-bold text-lg mb-2 text-slate-700">🚶 Walking Distance</div>` +
            `<div class="text-2xl font-bold text-emerald-600 mb-1">${distance.toFixed(1)}m</div>` +
            `<div class="text-xs text-slate-500">From clicked point to<br/><span class="font-semibold text-slate-700">${snapData.road_name}</span></div>` +
            `</div>`
        );
        
        // Add permanent tooltip showing distance
        window.osmSnapMarkers[role].connector.bindTooltip(
            `🚶 ${distance.toFixed(0)}m walk`,
            {
                permanent: true,
                direction: 'center',
                className: 'walking-distance-label',
                opacity: 0.9
            }
        );
    }
    
    // Store snap data
    window.osmSnapMarkers[role].data = snapData;
    
    console.log(`✅ Created OSM snap markers for ${role}`);
}

/**
 * Clear OSM snap markers for a specific role
 * 
 * @param {string} role - 'start' or 'dest'
 */
function clearOSMSnapMarkers(role) {
    if (!window.osmSnapMarkers[role]) return;
    
    ['clicked', 'snapped', 'connector'].forEach(type => {
        if (window.osmSnapMarkers[role][type] && map) {
            map.removeLayer(window.osmSnapMarkers[role][type]);
            window.osmSnapMarkers[role][type] = null;
        }
    });
    
    window.osmSnapMarkers[role].data = null;
}

/**
 * Clear all OSM snap markers
 */
function clearAllOSMSnapMarkers() {
    clearOSMSnapMarkers('start');
    clearOSMSnapMarkers('dest');
    console.log('✅ Cleared all OSM snap markers');
}

/**
 * Get location data for routing (uses snapped point)
 * 
 * @param {string} role - 'start' or 'dest'
 * @returns {object|null} Location data with snapped coordinates
 */
function getOSMSnappedLocation(role) {
    const snapData = window.osmSnapMarkers[role]?.data;
    if (!snapData) return null;
    
    return {
        lat: snapData.snapped_point.lat,
        lng: snapData.snapped_point.lng,
        original_lat: snapData.original_point.lat,
        original_lng: snapData.original_point.lng,
        snap_distance_m: snapData.distance_m,
        road_name: snapData.road_name,
        highway_type: snapData.highway_type,
        routing_nodes: snapData.routing_nodes,
        method: snapData.method,
        validation: snapData.validation
    };
}

/**
 * Enhanced start location pin handler with OSM road snapping
 */
async function handleOSMStartLocationPin(lat, lng) {
    try {
        // Attempt OSM road snapping
        const snapData = await snapToOSMRoad(lat, lng, 'start', 25);
        
        if (snapData) {
            // Create visual markers
            createOSMSnapMarkers(lat, lng, snapData, 'start');
            
            // Store location data
            window.startLocation = getOSMSnappedLocation('start');
            
            // Update UI - update input box with location name
            const displayText = snapData.method === 'osm_geometry'
                ? `📍 ${snapData.road_name} (${snapData.distance_m.toFixed(0)}m)`
                : `📍 Node ${snapData.routing_nodes[0]} (${snapData.distance_m.toFixed(0)}m)`;
            
            const startInput = document.getElementById('start-location-input');
            if (startInput) {
              startInput.value = snapData.road_name || `Node ${snapData.routing_nodes[0]}`;
              console.log(`✅ Updated start-location-input to: ${startInput.value}`);
            }
            
            const message = snapData.method === 'osm_geometry'
                ? `Start set on ${snapData.highway_type} road`
                : 'Start set (fallback to node)';
            
            showUpdateToast(message, 'success');
            
            if (snapData.validation && snapData.validation.warning_level === 'warning') {
                setTimeout(() => {
                    showUpdateToast(snapData.validation.message, 'warning');
                }, 1000);
            }
            
            // Auto-trigger routing if both start and dest are set
            if (window.startLocation && window.destLocation) {
                console.log('🚀 Both locations set - auto-triggering route computation');
                setTimeout(() => {
                    if (typeof computeRouteBasedOnSelection === 'function') {
                        computeRouteBasedOnSelection();
                    } else {
                        console.warn('computeRouteBasedOnSelection function not found');
                    }
                }, 500); // Small delay to ensure markers are visible
            }
        } else {
            // Fallback to original node-based handler
            console.warn('OSM snapping failed, using fallback');
            await handleStartLocationPin(lat, lng);
        }
        
    } catch (error) {
        console.error('Error in OSM start location pin:', error);
        showUpdateToast('Error setting start location', 'warning');
    }
    
    pinningMode = null;
    map.getContainer().style.cursor = 'default';
}

/**
 * Enhanced destination location pin handler with OSM road snapping
 */
async function handleOSMDestLocationPin(lat, lng) {
    try {
        // Attempt OSM road snapping
        const snapData = await snapToOSMRoad(lat, lng, 'dest', 25);
        
        if (snapData) {
            // Create visual markers
            createOSMSnapMarkers(lat, lng, snapData, 'dest');
            
            // Store location data
            window.destLocation = getOSMSnappedLocation('dest');
            
            // Update UI - update input box with location name
            const displayText = snapData.method === 'osm_geometry'
                ? `📍 ${snapData.road_name} (${snapData.distance_m.toFixed(0)}m)`
                : `📍 Node ${snapData.routing_nodes[0]} (${snapData.distance_m.toFixed(0)}m)`;
            
            const destInput = document.getElementById('dest-location-input');
            if (destInput) {
              destInput.value = snapData.road_name || `Node ${snapData.routing_nodes[0]}`;
              console.log(`✅ Updated dest-location-input to: ${destInput.value}`);
            }
            
            const message = snapData.method === 'osm_geometry'
                ? `Destination set on ${snapData.highway_type} road`
                : 'Destination set (fallback to node)';
            
            showUpdateToast(message, 'success');
            
            if (snapData.validation && snapData.validation.warning_level === 'warning') {
                setTimeout(() => {
                    showUpdateToast(snapData.validation.message, 'warning');
                }, 1000);
            }
            
            // Auto-trigger routing if both start and dest are set
            if (window.startLocation && window.destLocation) {
                console.log('🚀 Both locations set - auto-triggering route computation');
                setTimeout(() => {
                    if (typeof computeRouteBasedOnSelection === 'function') {
                        computeRouteBasedOnSelection();
                    } else {
                        console.warn('computeRouteBasedOnSelection function not found');
                    }
                }, 500); // Small delay to ensure markers are visible
            }
        } else {
            // Fallback to original node-based handler
            console.warn('OSM snapping failed, using fallback');
            await handleDestLocationPin(lat, lng);
        }
        
    } catch (error) {
        console.error('Error in OSM dest location pin:', error);
        showUpdateToast('Error setting destination', 'warning');
    }
    
    pinningMode = null;
    map.getContainer().style.cursor = 'default';
}

console.log('✅ OSM Road Snapping module loaded');
