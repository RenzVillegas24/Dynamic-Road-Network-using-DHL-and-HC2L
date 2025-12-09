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
    console.log('\n🗺️  === GOOGLE MAPS COMPARISON STARTED ===');
    
    try {
        // Check if a route has been calculated
        // Try both window.currentRouteData and global currentRouteData
        const routeData = window.currentRouteData || currentRouteData;
        
        if (!routeData) {
            showUpdateToast('Please calculate a route first', 'warning');
            console.warn('⚠️ No route data available');
            return;
        }
        
        console.log('✅ Route data found:', {
            hasMetrics: !!routeData.metrics,
            hasRoute: !!routeData.route,
            hasGeometry: !!(routeData.route && routeData.route.geometry),
            hasCoordinates: !!(routeData.route && routeData.route.coordinates),
            hasPolylines: !!(routeData.route && routeData.route.polylines),
            routeKeys: routeData.route ? Object.keys(routeData.route) : [],
            inputKeys: routeData.input ? Object.keys(routeData.input) : []
        });
        
        // Use existing route data from our system
        console.log('📊 Route data full structure:', routeData);
        
        // Extract coordinates from the existing route
        let startLat, startLng, destLat, destLng;
        
        if (routeData.input && routeData.input.start_snap_lat) {
            startLat = routeData.input.start_snap_lat;
            startLng = routeData.input.start_snap_lng;
            console.log('✅ Using start snap coordinates from route data:', startLat, startLng);
        }
        
        if (routeData.input && routeData.input.dest_snap_lat) {
            destLat = routeData.input.dest_snap_lat;
            destLng = routeData.input.dest_snap_lng;
            console.log('✅ Using dest snap coordinates from route data:', destLat, destLng);
        }
        
        // Fallback to OSM snap markers if available
        if (!startLat && window.osmSnapMarkers && window.osmSnapMarkers.start && window.osmSnapMarkers.start.snapped) {
            const startPos = window.osmSnapMarkers.start.snapped.getLatLng();
            startLat = startPos.lat;
            startLng = startPos.lng;
            console.log('✅ Using start snap coordinates from markers:', startLat, startLng);
        }
        
        if (!destLat && window.osmSnapMarkers && window.osmSnapMarkers.dest && window.osmSnapMarkers.dest.snapped) {
            const destPos = window.osmSnapMarkers.dest.snapped.getLatLng();
            destLat = destPos.lat;
            destLng = destPos.lng;
            console.log('✅ Using dest snap coordinates from markers:', destLat, destLng);
        }
        
        // Fallback to input boxes if snap markers not available
        if (!startLat || !destLat) {
            console.warn('⚠️ Snap coordinates not available, falling back to input boxes');
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
            showUpdateToast('Invalid route coordinates', 'error');
            console.error('Invalid coordinates:', { startLat, startLng, destLat, destLng });
            return;
        }
        
        console.log('📍 Coordinates ready:', { startLat, startLng, destLat, destLng });
        
        // Show loading state
        showUpdateToast('Fetching Google Maps route for comparison...', 'info');
        console.log('📡 Extracting route geometry for backend...');
        
        // Build request payload for backend to fetch Google Maps and calculate metrics
        // Extract route geometry from different possible route structures
        let routeGeometry = null;
        
        console.log('🔍 Attempting to extract geometry from routeData.route:', routeData.route);
        
        // Try different geometry structures
        if (routeData.route && routeData.route.geometry) {
            routeGeometry = routeData.route.geometry;
            console.log('✅ Found geometry in routeData.route.geometry, length:', routeGeometry?.length);
        } else if (routeData.route && routeData.route.coordinates) {
            // Some routes store coordinates directly instead of geometry
            // Send as flat array, backend will handle it
            routeGeometry = routeData.route.coordinates;
            console.log('✅ Found coordinates in routeData.route.coordinates, length:', routeGeometry?.length);
        } else if (routeData.route && routeData.route.polylines) {
            // DHL format might use polylines
            routeGeometry = routeData.route.polylines;
            console.log('✅ Found polylines in routeData.route.polylines, length:', routeGeometry?.length);
        } else if (Array.isArray(routeData.route)) {
            // Route might be an array of segments directly
            routeGeometry = routeData.route;
            console.log('✅ Route is array of segments, length:', routeGeometry?.length);
        }
        
        if (!routeGeometry || (Array.isArray(routeGeometry) && routeGeometry.length === 0)) {
            console.error('❌ Route geometry is null or empty after extraction');
            console.error('Available route properties:', routeData.route ? Object.keys(routeData.route) : 'no route');
            showUpdateToast('Route geometry is empty. Try calculating the route again.', 'error');
            return;
        }
        
        const payload = {
            start_lat: startLat,
            start_lng: startLng,
            dest_lat: destLat,
            dest_lng: destLng,
            algorithm: routeData.metrics && routeData.metrics.algorithm ? routeData.metrics.algorithm : 'Unknown',
            // Send existing route geometry for comparison - send as-is, backend handles format
            existing_route_geometry: routeGeometry
        };
        
        console.log('📊 Payload prepared:', {
            coordinates: `(${startLat}, ${startLng}) → (${destLat}, ${destLng})`,
            algorithm: payload.algorithm,
            hasGeometry: !!payload.existing_route_geometry,
            geometryType: Array.isArray(routeGeometry) ? 'array' : typeof routeGeometry,
            geometryLength: Array.isArray(routeGeometry) ? routeGeometry.length : 'N/A'
        });
        
        // Call backend API for final comparison metrics
        console.log('📡 Sending comparison request to backend...');
        showUpdateToast('Calculating Fréchet distance and overlap metrics...', 'info');
        
        const response = await fetch('/compare_with_google_maps', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        console.log('📥 Response received');
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ HTTP Error:', response.status, errorText);
            showUpdateToast(`Server error: ${response.status}`, 'error');
            return;
        }
        
        const data = await response.json();
        console.log('📊 Response data:', {
            success: data.success,
            hasComparison: !!data.comparison,
            hasGoogleRoute: !!data.google_maps_route
        });
        
        if (!data.success) {
            const errorMsg = data.error || 'Unknown error';
            showUpdateToast(`Comparison failed: ${errorMsg}`, 'error');
            console.error('❌ Google Maps comparison error:', errorMsg);
            console.error('Full error response:', data);
            return;
        }
        
        // Validate response data
        if (!data.comparison) {
            showUpdateToast('Invalid response: missing comparison data', 'error');
            console.error('❌ Response missing comparison data:', data);
            return;
        }
        
        if (!data.google_maps_route) {
            showUpdateToast('Invalid response: missing Google Maps route', 'error');
            console.error('❌ Response missing Google Maps route:', data);
            return;
        }
        
        console.log('✅ Google Maps comparison successful!');
        console.log('  Fréchet distance:', data.comparison.frechet_distance_meters, 'm');
        console.log('  Segment overlap:', data.comparison.segment_overlap_percent, '%');
        console.log('  Google route points:', data.google_maps_route.coordinates ? data.google_maps_route.coordinates.length : 0);
        
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
            `Comparison complete! Fréchet: ${data.comparison.frechet_distance_meters.toFixed(1)}m, Overlap: ${data.comparison.segment_overlap_percent.toFixed(1)}%`,
            'success'
        );
        
    } catch (error) {
        console.error('❌ Error comparing with Google Maps:', error);
        console.error('Error stack:', error.stack);
        showUpdateToast(`Comparison error: ${error.message}`, 'error');
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
        // Hide the compare button when showing metrics
        const compareButtonContainer = document.getElementById('current-path-google-compare-btn-container');
        if (compareButtonContainer) {
            compareButtonContainer.style.display = 'none';
        }
        
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
        
        // Update status interpretation
        const statusElement = document.getElementById('frechet-status-value');
        if (statusElement && comparison.interpretation) {
            const frechetStatus = comparison.interpretation.frechet_status || '--';
            const overlapStatus = comparison.interpretation.overlap_status || '--';
            statusElement.textContent = `${frechetStatus} / ${overlapStatus}`;
            
            // Color code based on status
            statusElement.classList.remove('text-red-700', 'text-yellow-700', 'text-emerald-700', 'text-blue-700');
            if (frechetStatus === 'Excellent' || overlapStatus === 'Perfect') {
                statusElement.classList.add('text-emerald-700');
            } else if (frechetStatus === 'Very Good' || overlapStatus === 'Very Good') {
                statusElement.classList.add('text-blue-700');
            } else if (frechetStatus === 'Fair' || overlapStatus === 'Fair') {
                statusElement.classList.add('text-yellow-700');
            } else {
                statusElement.classList.add('text-red-700');
            }
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


console.log('✅ Google Maps comparison module loaded');
