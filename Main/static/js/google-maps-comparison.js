/**
 * Google Maps Route Comparison Integration
 * Fetches routes from Google Maps and displays comparison metrics
 */

// Global variable to store Google Maps route layer
let googleMapsRouteLayer = null;

/**
 * Compare current route with Google Maps
 */
async function compareWithGoogleMaps() {
    try {
        // Get current route parameters from SNAPPED markers (road coordinates)
        let startLat, startLng, destLat, destLng;
        
        // CRITICAL: Use OSM snap markers to get accurate road coordinates
        if (window.osmSnapMarkers && window.osmSnapMarkers.start && window.osmSnapMarkers.start.snapped) {
            const startPos = window.osmSnapMarkers.start.snapped.getLatLng();
            startLat = startPos.lat;
            startLng = startPos.lng;
            console.log('✅ Using start snap coordinates:', startLat, startLng);
        }
        
        if (window.osmSnapMarkers && window.osmSnapMarkers.dest && window.osmSnapMarkers.dest.snapped) {
            const destPos = window.osmSnapMarkers.dest.snapped.getLatLng();
            destLat = destPos.lat;
            destLng = destPos.lng;
            console.log('✅ Using dest snap coordinates:', destLat, destLng);
        }
        
        // Fallback to input boxes if snap markers not available
        if (!startLat || !destLat) {
            console.warn('⚠️ Snap markers not available, falling back to input boxes');
            const startInput = document.getElementById('start-location-input').value;
            const destInput = document.getElementById('dest-location-input').value;
            
            if (startInput && startInput.includes(',')) {
                const parts = startInput.split(',');
                startLat = parseFloat(parts[0]);
                startLng = parseFloat(parts[1]);
            }
            
            if (destInput && destInput.includes(',')) {
                const parts = destInput.split(',');
                destLat = parseFloat(parts[0]);
                destLng = parseFloat(parts[1]);
            }
        }
        
        if (isNaN(startLat) || isNaN(startLng) || isNaN(destLat) || isNaN(destLng)) {
            showUpdateToast('Please calculate a route first', 'warning');
            console.error('Invalid coordinates:', { startLat, startLng, destLat, destLng });
            return;
        }
        
        // Get algorithm from current route data instead of radio button
        let algorithm = 'lazy-hc2l'; // Default
        
        if (window.currentRouteData && window.currentRouteData.metrics && window.currentRouteData.metrics.algorithm) {
            const algoName = window.currentRouteData.metrics.algorithm.toLowerCase();
            if (algoName.includes('dhl')) {
                algorithm = 'dhl';
            } else if (algoName.includes('hc2l') || algoName.includes('lazy')) {
                algorithm = 'lazy-hc2l';
            }
        }
        
        console.log('Using algorithm from current route:', algorithm);
        const useDisruptions = algorithm.includes('disrupted');
        const threshold = parseFloat(document.getElementById('threshold-value')?.textContent || '0.5');
        
        console.log('🗺️  Comparing with Google Maps...');
        console.log('  Algorithm:', algorithm);
        console.log('  Use disruptions:', useDisruptions);
        
        // Extract OSM snap data if available (required for HC2L)
        let startOsmEdge = null;
        let destOsmEdge = null;
        
        if (window.osmSnapMarkers) {
            if (window.osmSnapMarkers.start && window.osmSnapMarkers.start.edgeData) {
                startOsmEdge = window.osmSnapMarkers.start.edgeData;
                console.log('  Start snap data:', startOsmEdge.road_name || 'Unknown');
            }
            if (window.osmSnapMarkers.dest && window.osmSnapMarkers.dest.edgeData) {
                destOsmEdge = window.osmSnapMarkers.dest.edgeData;
                console.log('  Dest snap data:', destOsmEdge.road_name || 'Unknown');
            }
        }
        
        // Show loading state
        showUpdateToast('Fetching Google Maps route...', 'info');
        
        // Build request payload
        const payload = {
            start_lat: startLat,
            start_lng: startLng,
            dest_lat: destLat,
            dest_lng: destLng,
            algorithm: algorithm,
            use_disruptions: useDisruptions,
            threshold: threshold
        };
        
        // Add OSM snap data if available (required for HC2L routing)
        if (startOsmEdge) {
            payload.start_osm_edge = startOsmEdge;
        }
        if (destOsmEdge) {
            payload.dest_osm_edge = destOsmEdge;
        }
        
        // Call backend API
        const response = await fetch('/compare_with_google_maps', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showUpdateToast(`Google Maps comparison failed: ${data.error}`, 'error');
            console.error('❌ Google Maps comparison error:', data.error);
            return;
        }
        
        console.log('✅ Google Maps comparison successful');
        console.log('  Fréchet distance:', data.comparison.frechet_distance_meters, 'm');
        console.log('  Segment overlap:', data.comparison.segment_overlap_percent, '%');
        
        // Display Google Maps route on map
        displayGoogleMapsRoute(data.google_maps_route);
        
        // Update metrics display
        updateGoogleMapsMetrics(data.comparison);
        
        // Add comparison to CSV export buffer
        if (typeof addComparisonToExport === 'function') {
            addComparisonToExport(data);
        }
        
        // Show success message
        showUpdateToast(
            `Google Maps comparison complete! Overlap: ${data.comparison.segment_overlap_percent.toFixed(1)}%`,
            'success'
        );
        
    } catch (error) {
        console.error('❌ Error comparing with Google Maps:', error);
        showUpdateToast('Failed to compare with Google Maps', 'error');
    }
}

/**
 * Display Google Maps route on the map
 */
function displayGoogleMapsRoute(googleMapsRoute) {
    try {
        // Remove existing Google Maps route layer
        if (googleMapsRouteLayer) {
            map.removeLayer(googleMapsRouteLayer);
            googleMapsRouteLayer = null;
        }
        
        if (!googleMapsRoute || !googleMapsRoute.coordinates) {
            console.warn('No Google Maps route to display');
            return;
        }
        
        // Convert coordinates to Leaflet format
        const latLngs = googleMapsRoute.coordinates.map(coord => [coord[0], coord[1]]);
        
        // Create polyline for Google Maps route (orange color)
        googleMapsRouteLayer = L.polyline(latLngs, {
            color: '#FF8C00',  // Dark orange
            weight: 5,
            opacity: 0.7,
            dashArray: '10, 10',  // Dashed line to distinguish from algorithm routes
            className: 'google-maps-route'
        }).addTo(map);
        
        // Add popup with route info
        const popupContent = `
            <div class="p-3 min-w-[240px]">
                <div class="font-bold text-xl mb-3 text-orange-600 flex items-center">
                    <span class="mr-2">🗺️</span> Google Maps Route
                </div>
                <div class="bg-gradient-to-r from-orange-50 to-amber-50 px-3 py-2 rounded-lg border border-orange-200 mb-2">
                    <div class="text-xs text-orange-700 font-semibold uppercase tracking-wide">Alternative Route</div>
                </div>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between items-center">
                        <span class="font-semibold text-slate-700">📏 Distance:</span>
                        <span class="text-emerald-600 font-bold text-lg">${(googleMapsRoute.distance_meters / 1000).toFixed(2)} km</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="font-semibold text-slate-700">⏱️ Duration:</span>
                        <span class="text-blue-600 font-bold text-lg">${Math.round(googleMapsRoute.duration_seconds / 60)} min</span>
                    </div>
                </div>
            </div>
        `;
        
        googleMapsRouteLayer.bindPopup(popupContent);
        
        console.log('✅ Google Maps route displayed on map');
        console.log('  Points:', latLngs.length);
        console.log('  Distance:', googleMapsRoute.distance_meters, 'm');
        
    } catch (error) {
        console.error('❌ Error displaying Google Maps route:', error);
    }
}

/**
 * Update Google Maps comparison metrics in the UI
 */
function updateGoogleMapsMetrics(comparison) {
    try {
        // Show the metrics container
        const metricsContainer = document.getElementById('google-maps-metrics-container');
        if (metricsContainer) {
            metricsContainer.style.display = 'block';
        }
        
        // Update Fréchet distance
        const frechetElement = document.getElementById('frechet-distance-value');
        if (frechetElement) {
            frechetElement.textContent = `${comparison.frechet_distance_meters.toFixed(1)} m`;
        }
        
        // Update segment overlap
        const overlapElement = document.getElementById('segment-overlap-value');
        if (overlapElement) {
            overlapElement.textContent = `${comparison.segment_overlap_percent.toFixed(1)}%`;
        }
        
        console.log('✅ Google Maps metrics updated in UI');
        
    } catch (error) {
        console.error('❌ Error updating Google Maps metrics:', error);
    }
}

/**
 * Clear Google Maps route from map
 */
function clearGoogleMapsRoute() {
    try {
        // Remove Google Maps route layer
        if (googleMapsRouteLayer) {
            map.removeLayer(googleMapsRouteLayer);
            googleMapsRouteLayer = null;
            console.log('✅ Google Maps route cleared');
        }
        
        // Hide metrics container
        const metricsContainer = document.getElementById('google-maps-metrics-container');
        if (metricsContainer) {
            metricsContainer.style.display = 'none';
        }
        
        // Reset metric values
        const frechetElement = document.getElementById('frechet-distance-value');
        if (frechetElement) {
            frechetElement.textContent = '-- m';
        }
        
        const overlapElement = document.getElementById('segment-overlap-value');
        if (overlapElement) {
            overlapElement.textContent = '--%';
        }
        
        // Reset toggle button state if it exists
        if (typeof showCurrentRouteOnlyActive !== 'undefined' && showCurrentRouteOnlyActive) {
            // Reset the toggle state
            showCurrentRouteOnlyActive = false;
            
            // Reset button appearance
            const button = document.getElementById('show-current-route-only-btn');
            if (button) {
                const buttonText = button.querySelector('span');
                if (buttonText) {
                    buttonText.textContent = 'Current Route Only';
                }
                
                const iconDiv = button.querySelector('div');
                if (iconDiv) {
                    iconDiv.classList.remove('from-green-500', 'to-emerald-600');
                    iconDiv.classList.add('from-blue-500', 'to-indigo-600');
                }
            }
        }
    } catch (error) {
        console.error('❌ Error clearing Google Maps route:', error);
    }
}

/**
 * Auto-compare with Google Maps after route calculation
 * This function is called automatically when a route is calculated
 */
function autoCompareWithGoogleMaps(routeData) {
    // Only auto-compare if user wants it (you can add a checkbox for this)
    const autoCompareEnabled = true;  // Can be controlled by UI checkbox
    
    if (autoCompareEnabled && routeData && routeData.success) {
        // Wait a bit to let the route render first
        setTimeout(() => {
            console.log('🔄 Auto-comparing with Google Maps...');
            compareWithGoogleMaps();
        }, 1000);
    }
}

// Expose functions globally
window.compareWithGoogleMaps = compareWithGoogleMaps;
window.displayGoogleMapsRoute = displayGoogleMapsRoute;
window.clearGoogleMapsRoute = clearGoogleMapsRoute;
window.autoCompareWithGoogleMaps = autoCompareWithGoogleMaps;

/**
 * Toggle visibility of current algorithm route only
 * When activated, hides Google Maps route overlay and shows only the current algorithm route
 */
let showCurrentRouteOnlyActive = false; // Track toggle state

function toggleCurrentRouteOnly() {
    const button = document.getElementById('show-current-route-only-btn');
    
    if (!button) {
        console.warn('Show Current Route Only button not found');
        return;
    }
    
    showCurrentRouteOnlyActive = !showCurrentRouteOnlyActive;
    
    if (showCurrentRouteOnlyActive) {
        // Hide Google Maps route overlay
        if (googleMapsRouteLayer && map) {
            map.removeLayer(googleMapsRouteLayer);
            console.log('✅ Hidden Google Maps route overlay');
        }
        
        // Update button text to indicate current state
        const buttonText = button.querySelector('span');
        if (buttonText) {
            buttonText.textContent = 'Show All Routes';
        }
        
        // Change button color to indicate active state
        const iconDiv = button.querySelector('div');
        if (iconDiv) {
            iconDiv.classList.remove('from-blue-500', 'to-indigo-600');
            iconDiv.classList.add('from-green-500', 'to-emerald-600');
        }
        
        console.log('✅ Showing current route only');
    } else {
        // Restore Google Maps route overlay
        if (googleMapsRouteLayer && map) {
            googleMapsRouteLayer.addTo(map);
            console.log('✅ Restored Google Maps route overlay');
        }
        
        // Update button text back to original
        const buttonText = button.querySelector('span');
        if (buttonText) {
            buttonText.textContent = 'Current Route Only';
        }
        
        // Change button color back to original
        const iconDiv = button.querySelector('div');
        if (iconDiv) {
            iconDiv.classList.remove('from-green-500', 'to-emerald-600');
            iconDiv.classList.add('from-blue-500', 'to-indigo-600');
        }
        
        console.log('✅ Showing all routes');
    }
}

window.toggleCurrentRouteOnly = toggleCurrentRouteOnly;

console.log('✅ Google Maps comparison module loaded');
