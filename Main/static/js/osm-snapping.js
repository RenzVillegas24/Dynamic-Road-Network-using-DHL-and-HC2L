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
        `<b>${isStart ? '🟢 Start Location' : '🔴 Destination'}</b><br>` +
        `Clicked Point<br>` +
        `<small>${clickedLat.toFixed(6)}, ${clickedLng.toFixed(6)}</small>`
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
        `<b>${isStart ? '🟢 Start Point' : '🔴 Destination'}</b><br>` +
        `${methodText}<br>` +
        `<b>Road:</b> ${snapData.road_name}<br>` +
        `<b>Type:</b> ${snapData.highway_type}<br>` +
        `${snapData.oneway ? '<b>⚠️ One-way road</b><br>' : ''}` +
        `<b>Distance:</b> ${snapData.distance_m.toFixed(1)}m from click<br>` +
        `${snapData.snap_position ? `<b>Position:</b> ${(snapData.snap_position * 100).toFixed(0)}% along edge<br>` : ''}` +
        `<small>${snappedLat.toFixed(6)}, ${snappedLng.toFixed(6)}</small>`
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
        
        window.osmSnapMarkers[role].connector.bindPopup(
            `<b>Walking Distance</b><br>` +
            `${distance.toFixed(1)}m to road<br>` +
            `<small>From clicked point to ${snapData.road_name}</small>`
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
            
            // Update UI
            const displayText = snapData.method === 'osm_geometry'
                ? `📍 ${snapData.road_name} (${snapData.distance_m.toFixed(0)}m)`
                : `📍 Node ${snapData.routing_nodes[0]} (${snapData.distance_m.toFixed(0)}m)`;
            
            document.getElementById('start-location-text').textContent = displayText;
            document.getElementById('start-location-text').classList.remove('text-slate-500');
            document.getElementById('start-location-text').classList.add('text-slate-900', 'font-semibold');
            
            const message = snapData.method === 'osm_geometry'
                ? `Start set on ${snapData.highway_type} road`
                : 'Start set (fallback to node)';
            
            showUpdateToast(message, 'success');
            
            if (snapData.validation && snapData.validation.warning_level === 'warning') {
                setTimeout(() => {
                    showUpdateToast(snapData.validation.message, 'warning');
                }, 1000);
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
            
            // Update UI
            const displayText = snapData.method === 'osm_geometry'
                ? `📍 ${snapData.road_name} (${snapData.distance_m.toFixed(0)}m)`
                : `📍 Node ${snapData.routing_nodes[0]} (${snapData.distance_m.toFixed(0)}m)`;
            
            document.getElementById('dest-location-text').textContent = displayText;
            document.getElementById('dest-location-text').classList.remove('text-slate-500');
            document.getElementById('dest-location-text').classList.add('text-slate-900', 'font-semibold');
            
            const message = snapData.method === 'osm_geometry'
                ? `Destination set on ${snapData.highway_type} road`
                : 'Destination set (fallback to node)';
            
            showUpdateToast(message, 'success');
            
            if (snapData.validation && snapData.validation.warning_level === 'warning') {
                setTimeout(() => {
                    showUpdateToast(snapData.validation.message, 'warning');
                }, 1000);
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
