// Algorithm Comparison Panel Functions
// Handles side-by-side comparison of Google Maps, HERE API, DHL, and HC2L routing algorithms

// Color scheme for algorithms
const ALGORITHM_COLORS = {
    google: {
        primary: '#FF6B00',
        bg: '#FFF4ED',
        border: '#FF6B00',
        name: 'Google Maps'
    },
    here: {
        primary: '#14B8A6',
        bg: '#F0FDFA',
        border: '#14B8A6',
        name: 'HERE API'
    },
    dhl: {
        primary: '#8B5CF6',
        bg: '#F5F3FF',
        border: '#8B5CF6',
        name: 'DHL'
    },
    hc2l: {
        primary: '#3B82F6',
        bg: '#EFF6FF',
        border: '#3B82F6',
        name: 'HC2L'
    }
};

// Store comparison results
window.comparisonResults = {
    google: null,
    here: null,
    dhl: null,
    hc2l: null
};

// Open comparison panel and auto-run comparison
async function openComparisonPanel() {
    const panel = document.getElementById('algorithm-comparison-panel');
    if (panel) {
        panel.classList.remove('translate-x-full');
        console.log('✅ Algorithm Comparison Panel opened');

        // Check if start and destination are set
        if (window.startLocation && window.destLocation) {
            // Auto-run comparison with all algorithms by default
            document.getElementById('compare-google').checked = true;
            document.getElementById('compare-here').checked = true;
            document.getElementById('compare-dhl').checked = true;
            document.getElementById('compare-hc2l').checked = true;

            // Small delay for panel animation
            setTimeout(() => {
                showUpdateToast('Running comparison...', 'info');
                runComparison();
            }, 300);
        } else {
            showUpdateToast('Please set start and destination first', 'warning');
        }
    }
}

// Close comparison panel
async function closeComparisonPanel() {
    const panel = document.getElementById('algorithm-comparison-panel');
    if (panel) {
        panel.classList.add('translate-x-full');
        console.log('✅ Algorithm Comparison Panel closed');
        
        // Clear comparison route overlays from map
        clearComparisonRoutes();
        toggleRouteFinderUI(false);

        await new Promise(resolve => setTimeout(resolve, 100));
        await handleGoButtonClick(false);
    }
}

// Clear comparison routes from map
function clearComparisonRoutes() {
    // Remove comparison route polylines
    if (window.comparisonPolylines) {
        window.comparisonPolylines.forEach(polyline => {
            if (polyline && map) {
                map.removeLayer(polyline);
            }
        });
        window.comparisonPolylines = [];
    }
    console.log('🧹 Comparison routes cleared from map');
}

function compareChanged() {
    runComparison();
}

// on enter make the hovered element only this route wull be visible
function compareEntered(event) {
    const target = event.target;
    let hoveredAlgo = null;
    
    // Find the label element (could be target or ancestor)
    const label = target.closest('label');
    if (!label) return;
    
    // Determine which algorithm based on the input id inside the label
    const input = label.querySelector('input[type="checkbox"]');
    if (input) {
        if (input.id === 'compare-google') hoveredAlgo = 'google';
        else if (input.id === 'compare-here') hoveredAlgo = 'here';
        else if (input.id === 'compare-dhl') hoveredAlgo = 'dhl';
        else if (input.id === 'compare-hc2l') hoveredAlgo = 'hc2l';
    }
    
    if (!hoveredAlgo || !window.comparisonPolylines || window.comparisonPolylines.length === 0) return;
    
    // Check if the hovered algorithm actually has a route
    const hasHoveredRoute = window.comparisonPolylines.some(polyline => polyline._algorithm === hoveredAlgo);
    if (!hasHoveredRoute) return;
    
    // Set opacity: hovered route visible (1.0), others transparent (0.3)
    window.comparisonPolylines.forEach((polyline) => {
        if (polyline && polyline.setStyle) {
            polyline.setStyle({
                opacity: polyline._algorithm === hoveredAlgo ? 1.0 : 0.3
            });
        }
    });
}

// on leave reset all routes to visible
function compareLeft() {
    if (!window.comparisonPolylines || window.comparisonPolylines.length === 0) return;
    
    // Reset all routes to full opacity
    window.comparisonPolylines.forEach((polyline) => {
        if (polyline && polyline.setStyle) {
            polyline.setStyle({
                opacity: 1.0
            });
        }
    });
}

// Run algorithm comparison
async function runComparison() {
    console.log('🚀 Running algorithm comparison...');

    // Check if start and destination are set
    if (!window.startLocation || !window.destLocation) {
        showUpdateToast('Please set start and destination first', 'warning');
        return;
    }

    // Get selected algorithms
    const compareGoogle = document.getElementById('compare-google')?.checked;
    const compareHere = document.getElementById('compare-here')?.checked;
    const compareDHL = document.getElementById('compare-dhl')?.checked;
    const compareHC2L = document.getElementById('compare-hc2l')?.checked;

    if (!compareGoogle && !compareHere && !compareDHL && !compareHC2L) {
        showUpdateToast('Please select at least one algorithm', 'warning');
        return;
    }

    // Get current selections (dataset mode, threshold)
    const selections = getCurrentSelections();
    const useDisruptions = selections.dataset_mode !== 'none';

    // Show loading state
    showUpdateToast('Computing routes for comparison...', 'info');

    // Clear previous comparison results
    window.comparisonResults = { google: null, here: null, dhl: null, hc2l: null };
    clearComparisonRoutes();

    // Compute routes in parallel (with is_comparison_mode=true to skip alternatives)
    const promises = [];

    if (compareGoogle) {
        promises.push(
            computeGoogleMapsRoute()
                .then(result => {
                    window.comparisonResults.google = result;
                    console.log('✅ Google Maps route computed');
                })
                .catch(err => {
                    console.error('❌ Google Maps route failed:', err);
                    window.comparisonResults.google = { error: err.message };
                })
        );
    }

    if (compareHere) {
        promises.push(
            computeHereRoute()
                .then(result => {
                    window.comparisonResults.here = result;
                    console.log('✅ HERE API route computed');
                })
                .catch(err => {
                    console.error('❌ HERE API route failed:', err);
                    window.comparisonResults.here = { error: err.message };
                })
        );
    }

    if (compareDHL) {
        promises.push(
            computeDHLRoute(useDisruptions, true) // true = is_comparison_mode (no alternatives)
                .then(result => {
                    window.comparisonResults.dhl = result;
                    console.log('✅ DHL route computed');
                })
                .catch(err => {
                    console.error('❌ DHL route failed:', err);
                    window.comparisonResults.dhl = { error: err.message };
                })
        );
    }

    if (compareHC2L) {
        promises.push(
            computeDHC2LRoute(useDisruptions, selections.threshold, true) // true = is_comparison_mode
                .then(result => {
                    window.comparisonResults.hc2l = result;
                    console.log('✅ HC2L route computed');
                })
                .catch(err => {
                    console.error('❌ HC2L route failed:', err);
                    window.comparisonResults.hc2l = { error: err.message };
                })
        );
    }

    // Wait for all computations to complete
    await Promise.all(promises);

    // Display results
    displayComparisonResults();

    showUpdateToast('Comparison complete', 'success');
}

// Display comparison results
function displayComparisonResults() {
    console.log('📊 Displaying comparison results');

    // Calculate comparison metrics between algorithms
    calculateComparisonMetrics();

    // Show metrics container
    const metricsContainer = document.getElementById('comparison-metrics-container');
    if (metricsContainer) {
        metricsContainer.classList.remove('hidden');
    }

    // Build comparison table
    buildComparisonTable();

    // Display routes on map
    displayComparisonRoutesOnMap();

    // Show route details
    buildRouteDetails();
}

// Calculate Fréchet Distance and Segment Overlap between algorithms
function calculateComparisonMetrics() {
    // Extract coordinates from all routes
    const routes = {
        google: extractCoordinates(window.comparisonResults.google),
        here: extractCoordinates(window.comparisonResults.here),
        dhl: extractCoordinates(window.comparisonResults.dhl),
        hc2l: extractCoordinates(window.comparisonResults.hc2l)
    };

    // Initialize comparison metrics storage
    if (!window.comparisonMetrics) {
        window.comparisonMetrics = {};
    }

    // Calculate Fréchet Distance and Overlap between all pairs
    const algorithmPairs = [
        ['google', 'here'],
        ['google', 'dhl'],
        ['google', 'hc2l'],
        ['here', 'dhl'],
        ['here', 'hc2l'],
        ['dhl', 'hc2l']
    ];

    algorithmPairs.forEach(([algo1, algo2]) => {
        if (routes[algo1] && routes[algo2] && routes[algo1].length > 0 && routes[algo2].length > 0) {
            const key = `${algo1}_${algo2}`;
            window.comparisonMetrics[key] = {
                frechet_distance: calculateFrechetDistance(routes[algo1], routes[algo2]),
                segment_overlap: calculateSegmentOverlap(routes[algo1], routes[algo2])
            };
            console.log(`📏 ${algo1} vs ${algo2}: Fréchet=${window.comparisonMetrics[key].frechet_distance.toFixed(2)}m, Overlap=${window.comparisonMetrics[key].segment_overlap.toFixed(1)}%`);
        }
    });
}

// Extract coordinates from a route result
function extractCoordinates(result) {
    if (!result || !result.success || !result.route) return [];

    let coordinates = [];
    const route = result.route;

    if (route.polylines && route.polylines.length > 0) {
        route.polylines.forEach(segment => {
            if (Array.isArray(segment)) {
                coordinates.push(...segment);
            } else if (segment.path) {
                coordinates.push(...segment.path.map(p => [p.lat, p.lng]));
            } else if (segment.lat !== undefined && segment.lng !== undefined) {
                coordinates.push([segment.lat, segment.lng]);
            }
        });
    } else if (route.coordinates && route.coordinates.length > 0) {
        if (route.coordinates[0] && typeof route.coordinates[0] === 'object') {
            if (Array.isArray(route.coordinates[0])) {
                coordinates = route.coordinates;
            } else {
                coordinates = route.coordinates.map(c => [c.lat, c.lng]);
            }
        }
    }

    return coordinates;
}

// Calculate Fréchet Distance (simplified discrete Fréchet distance)
function calculateFrechetDistance(path1, path2) {
    if (path1.length === 0 || path2.length === 0) return 0;

    // Simplified Hausdorff distance as approximation of Fréchet
    let maxDistance = 0;

    // Forward direction: max distance from path1 points to path2
    for (let i = 0; i < path1.length; i++) {
        let minDistance = Infinity;
        for (let j = 0; j < path2.length; j++) {
            const dist = haversineDistance(path1[i], path2[j]);
            minDistance = Math.min(minDistance, dist);
        }
        maxDistance = Math.max(maxDistance, minDistance);
    }

    // Backward direction: max distance from path2 points to path1
    for (let i = 0; i < path2.length; i++) {
        let minDistance = Infinity;
        for (let j = 0; j < path1.length; j++) {
            const dist = haversineDistance(path2[i], path1[j]);
            minDistance = Math.min(minDistance, dist);
        }
        maxDistance = Math.max(maxDistance, minDistance);
    }

    return maxDistance;
}

// Calculate Segment Overlap (percentage of matching segments)
function calculateSegmentOverlap(path1, path2, threshold = 50) {
    if (path1.length === 0) return 0;

    let overlappingPoints = 0;

    // Check each point in path1 against path2
    for (let i = 0; i < path1.length; i++) {
        for (let j = 0; j < path2.length; j++) {
            const dist = haversineDistance(path1[i], path2[j]);
            if (dist <= threshold) {
                overlappingPoints++;
                break;
            }
        }
    }

    return (overlappingPoints / path1.length) * 100;
}

// Haversine formula to calculate distance between two lat/lng points
function haversineDistance(coord1, coord2) {
    const lat1 = coord1[0] * Math.PI / 180;
    const lat2 = coord2[0] * Math.PI / 180;
    const deltaLat = (coord2[0] - coord1[0]) * Math.PI / 180;
    const deltaLng = (coord2[1] - coord1[1]) * Math.PI / 180;

    const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
        Math.cos(lat1) * Math.cos(lat2) *
        Math.sin(deltaLng / 2) * Math.sin(deltaLng / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const R = 6371000; // Earth radius in meters

    return R * c;
}

// Build metrics comparison table
function buildComparisonTable() {
    const tableContainer = document.getElementById('comparison-metrics-table');
    if (!tableContainer) return;

    const algorithms = [];
    if (window.comparisonResults.google) algorithms.push('google');
    if (window.comparisonResults.here) algorithms.push('here');
    if (window.comparisonResults.dhl) algorithms.push('dhl');
    if (window.comparisonResults.hc2l) algorithms.push('hc2l');

    if (algorithms.length === 0) {
        tableContainer.innerHTML = '<p class="text-slate-500 text-center py-4">No results to display</p>';
        return;
    }

    // Metrics to compare
    const metrics = [
        { key: 'distance', label: 'Distance', format: (v) => v ? `${v.toFixed(2)} km` : 'N/A' },
        { key: 'duration', label: 'Duration', format: (v) => v ? `${(v / 60).toFixed(1)} min` : 'N/A' },
        { key: 'query_time_ms', label: 'Query Time', format: (v) => v !== undefined ? `${v.toFixed(1)} ms` : 'N/A' },
        { key: 'segments', label: 'Route Segments', format: (v) => v || 'N/A' }
    ];

    let tableHTML = '<table class="w-full text-sm"><thead><tr class="border-b-2 border-slate-300">';
    tableHTML += '<th class="text-left py-2 px-3 font-bold text-slate-700">Metric</th>';

    // Algorithm headers with colors
    algorithms.forEach(algo => {
        const color = ALGORITHM_COLORS[algo];
        tableHTML += `<th class="text-center py-2 px-3 font-bold" style="color: ${color.primary}">${color.name}</th>`;
    });

    tableHTML += '</tr></thead><tbody>';

    // Metric rows
    metrics.forEach(metric => {
        tableHTML += '<tr class="border-b border-slate-200">';
        tableHTML += `<td class="py-2 px-3 font-medium text-slate-700">${metric.label}</td>`;

        algorithms.forEach(algo => {
            const result = window.comparisonResults[algo];
            let value = 'N/A';

            if (result && result.success) {
                let rawValue;

                // Handle different metric structures for different algorithms
                if (metric.key === 'distance') {
                    // Google Maps: result.route.distance
                    // DHL/HC2L: result.metrics.calculated_distance_meters (convert to km)
                    if (result.route?.distance) {
                        rawValue = result.route.distance;
                    } else if (result.metrics?.calculated_distance_meters) {
                        rawValue = result.metrics.calculated_distance_meters / 1000; // Convert meters to km
                    }
                } else if (metric.key === 'duration') {
                    // Google Maps: result.route.duration (seconds)
                    // DHL/HC2L: result.metrics.eta_seconds
                    rawValue = result.route?.duration || result.metrics?.eta_seconds;
                } else if (metric.key === 'query_time_ms') {
                    // DHL/HC2L: result.metrics.query_time_ms
                    // Google Maps: not applicable
                    rawValue = result.metrics?.query_time_ms;
                } else if (metric.key === 'segments') {
                    // Google Maps: result.metrics.segments or result.route.point_count
                    // DHL/HC2L: result.route.path_nodes.length or result.metrics.nodes_on_path
                    rawValue = result.metrics?.segments ||
                        result.route?.path_nodes?.length ||
                        result.metrics?.nodes_on_path;
                }

                value = metric.format(rawValue);
            } else if (result && result.error) {
                value = '<span class="text-red-600 text-xs">Error</span>';
            }

            const color = ALGORITHM_COLORS[algo];
            tableHTML += `<td class="py-2 px-3 text-center font-semibold" style="color: ${color.primary}">${value}</td>`;
        });

        tableHTML += '</tr>';
    });

    tableHTML += '</tbody></table>';

    // Add comparison metrics (Fréchet Distance and Segment Overlap)
    if (window.comparisonMetrics && Object.keys(window.comparisonMetrics).length > 0) {
        tableHTML += '<div class="mt-6 border-t-2 border-slate-300 pt-4">';
        tableHTML += '<h4 class="font-bold text-slate-700 mb-3">Route Comparison Metrics</h4>';
        tableHTML += '<table class="w-full text-sm"><thead><tr class="border-b-2 border-slate-300">';
        tableHTML += '<th class="text-left py-2 px-3 font-bold text-slate-700">Comparison</th>';
        tableHTML += '<th class="text-center py-2 px-3 font-bold text-slate-700">Fréchet Distance</th>';
        tableHTML += '<th class="text-center py-2 px-3 font-bold text-slate-700">Segment Overlap</th>';
        tableHTML += '</tr></thead><tbody>';

        // Display comparison for each pair
        Object.entries(window.comparisonMetrics).forEach(([key, metrics]) => {
            const [algo1, algo2] = key.split('_');
            const color1 = ALGORITHM_COLORS[algo1];
            const color2 = ALGORITHM_COLORS[algo2];

            tableHTML += '<tr class="border-b border-slate-200">';
            tableHTML += `<td class="py-2 px-3 font-medium"><span style="color: ${color1.primary}">●</span> ${color1.name} vs <span style="color: ${color2.primary}">●</span> ${color2.name}</td>`;
            tableHTML += `<td class="py-2 px-3 text-center font-semibold">${metrics.frechet_distance.toFixed(0)} m</td>`;
            tableHTML += `<td class="py-2 px-3 text-center font-semibold">${metrics.segment_overlap.toFixed(1)}%</td>`;
            tableHTML += '</tr>';
        });

        tableHTML += '</tbody></table>';
        tableHTML += '</div>';
    }

    tableContainer.innerHTML = tableHTML;
}

// Display comparison routes on map with proper colors
function displayComparisonRoutesOnMap() {
    console.log('🗺️ Displaying comparison routes on map');

    // Initialize polylines array
    window.comparisonPolylines = window.comparisonPolylines || [];

    // Clear previous comparison routes
    clearComparisonRoutes();

    // Draw each algorithm's route with its color
    const algorithms = ['google', 'here', 'dhl', 'hc2l'];

    algorithms.forEach(algo => {
        const result = window.comparisonResults[algo];
        console.log(`🔍 Processing ${algo} route:`, result);
        
        if (!result || !result.success || !result.route) {
            console.warn(`⚠️ Skipping ${algo} - missing result, success, or route`);
            return;
        }

        const color = ALGORITHM_COLORS[algo];
        const route = result.route;
        
        console.log(`🔍 ${algo} route data:`, {
            polylines: route.polylines?.length,
            coordinates: route.coordinates?.length,
            firstCoord: route.coordinates?.[0],
            polylineFirstCoord: route.polylines?.[0]?.[0]
        });

        // Extract coordinates
        let coordinates = [];
        if (route.polylines && route.polylines.length > 0) {
            // Combine all polyline segments
            route.polylines.forEach(segment => {
                if (Array.isArray(segment)) {
                    // Google Maps format: [[lat, lng], [lat, lng], ...]
                    coordinates.push(...segment);
                } else if (segment.path) {
                    // DHL/HC2L format with path property
                    coordinates.push(...segment.path.map(p => [p.lat, p.lng]));
                } else if (segment.lat !== undefined && segment.lng !== undefined) {
                    // Single coordinate object
                    coordinates.push([segment.lat, segment.lng]);
                }
            });
        } else if (route.coordinates && route.coordinates.length > 0) {
            // Direct coordinates array
            if (route.coordinates[0] && typeof route.coordinates[0] === 'object') {
                if (Array.isArray(route.coordinates[0])) {
                    // Already in [[lat, lng]] format (Google Maps)
                    coordinates = route.coordinates;
                } else {
                    // Convert from [{lat, lng}] format
                    coordinates = route.coordinates.map(c => [c.lat, c.lng]);
                }
            }
        }
        
        console.log(`🔍 ${algo} extracted ${coordinates.length} coordinates:`, {
            first: coordinates[0],
            last: coordinates[coordinates.length - 1]
        });

        if (coordinates.length === 0) {
            console.warn(`No coordinates for ${algo} route`);
            return;
        }

        // Create polyline with algorithm color
        const polyline = L.polyline(coordinates, {
            color: color.primary,
            weight: 5,
            opacity: 1.0,
            zIndex: algo === 'google' ? 100 : (algo === 'dhl' ? 101 : 102) // HC2L on top
        }).addTo(map);

        // Add algorithm identifier to polyline
        polyline._algorithm = algo;

        // Add popup with correct metrics
        let distance = 0;
        let duration = 0;

        // Extract distance
        if (route.distance) {
            distance = route.distance;
        } else if (result.metrics?.calculated_distance_meters) {
            distance = result.metrics.calculated_distance_meters / 1000; // Convert meters to km
        }

        // Extract duration
        duration = route.duration || result.metrics?.eta_seconds || 0;

        polyline.bindPopup(`
            <div class="p-2">
                <h3 class="font-bold text-sm" style="color: ${color.primary}">${color.name}</h3>
                <p class="text-xs">Distance: ${distance.toFixed(2)} km</p>
                <p class="text-xs">Duration: ${(duration / 60).toFixed(1)} min</p>
            </div>
        `);

        window.comparisonPolylines.push(polyline);

        console.log(`✅ ${color.name} route displayed on map`);
    });

    // Fit map to show all routes
    if (window.comparisonPolylines.length > 0) {
        const group = L.featureGroup(window.comparisonPolylines);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

// Build route details sections
function buildRouteDetails() {
    const detailsContainer = document.getElementById('comparison-route-details');
    if (!detailsContainer) return;

    detailsContainer.classList.remove('hidden');
    detailsContainer.innerHTML = '';

    const algorithms = [];
    if (window.comparisonResults.google) algorithms.push('google');
    if (window.comparisonResults.here) algorithms.push('here');
    if (window.comparisonResults.dhl) algorithms.push('dhl');
    if (window.comparisonResults.hc2l) algorithms.push('hc2l');

    algorithms.forEach(algo => {
        const result = window.comparisonResults[algo];
        if (!result || !result.success) return;

        const color = ALGORITHM_COLORS[algo];

        const detailCard = document.createElement('div');
        detailCard.className = `rounded-2xl p-4 border-2 shadow-sm`;
        detailCard.style.backgroundColor = color.bg;
        detailCard.style.borderColor = color.border;

        let detailHTML = `
            <div class="flex items-center justify-between cursor-pointer" onclick="toggleRouteDetail('${algo}')">
                <h4 class="font-bold text-lg" style="color: ${color.primary}">${color.name} Route Details</h4>
                <svg id="${algo}-detail-chevron" class="w-5 h-5 transition-transform" style="color: ${color.primary}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                </svg>
            </div>
            <div id="${algo}-detail-content" class="hidden mt-3 space-y-2">
                <div class="text-sm">
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Total Distance:</span>
                        <span class="font-bold">${(() => {
                if (result.route?.distance) return result.route.distance.toFixed(2);
                if (result.metrics?.calculated_distance_meters) return (result.metrics.calculated_distance_meters / 1000).toFixed(2);
                return '0.00';
            })()
            } km</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Total Duration:</span>
                        <span class="font-bold">${(() => {
                const seconds = result.route?.duration || result.metrics?.eta_seconds || 0;
                return (seconds / 60).toFixed(1);
            })()
            } min</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Route Segments:</span>
                        <span class="font-bold">${result.route?.path_nodes?.length || result.metrics?.nodes_on_path || result.route?.segments || 'N/A'
            }</span>
                    </div>
        `;

        // Add algorithm-specific details
        if (algo === 'hc2l' && result.metrics) {
            detailHTML += `
                <div class="border-t border-slate-300 mt-3 pt-3 space-y-2">
                    <div class="text-xs font-bold text-slate-600 mb-2">HC2L Algorithm Details</div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Query Time:</span>
                        <span class="font-bold">${result.metrics.query_time_ms?.toFixed(1) || 'N/A'} ms</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Updated Labels:</span>
                        <span class="font-bold">${result.metrics.updated_labels || 'N/A'}</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">ETA (Traffic):</span>
                        <span class="font-bold">${result.metrics.eta_formatted || 'N/A'}</span>
                    </div>
                    ${result.metrics.labeling_info ? `
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Index Height:</span>
                        <span class="font-bold">${result.metrics.labeling_info.height || 'N/A'}</span>
                    </div>
                    ` : ''}
                </div>
            `;
        } else if (algo === 'dhl' && result.metrics) {
            detailHTML += `
                <div class="border-t border-slate-300 mt-3 pt-3 space-y-2">
                    <div class="text-xs font-bold text-slate-600 mb-2">DHL Algorithm Details</div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Query Time:</span>
                        <span class="font-bold">${result.metrics.query_time_ms?.toFixed(1) || 'N/A'} ms</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Labeling Mode:</span>
                        <span class="font-bold">${result.metrics.routing_mode || 'DHL'}</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Hop-links Examined:</span>
                        <span class="font-bold">${result.metrics.hoplinks_examined || 'N/A'}</span>
                    </div>
                    ${result.metrics.index_height ? `
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Index Height:</span>
                        <span class="font-bold">${result.metrics.index_height}</span>
                    </div>
                    ` : ''}
                </div>
            `;
        } else if (algo === 'google' && result.metrics) {
            detailHTML += `
                <div class="border-t border-slate-300 mt-3 pt-3 space-y-2">
                    <div class="text-xs font-bold text-slate-600 mb-2">Google Maps Details</div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Query Time:</span>
                        <span class="font-bold">${result.metrics.query_time_ms?.toFixed(1) || 'N/A'} ms</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Route Confidence:</span>
                        <span class="font-bold">100%</span>
                    </div>
                </div>
            `;
        } else if (algo === 'here' && result.metrics) {
            detailHTML += `
                <div class="border-t border-slate-300 mt-3 pt-3 space-y-2">
                    <div class="text-xs font-bold text-slate-600 mb-2">HERE API Details</div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Query Time:</span>
                        <span class="font-bold">${result.metrics.query_time_ms?.toFixed(1) || 'N/A'} ms</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Traffic Mode:</span>
                        <span class="font-bold">${result.route?.traffic_mode || 'enabled'}</span>
                    </div>
                    <div class="flex justify-between py-1">
                        <span class="text-slate-600">Route Sections:</span>
                        <span class="font-bold">${result.route?.sections || 'N/A'}</span>
                    </div>
                </div>
            `;
        }

        detailHTML += `
                </div>
            </div>
        `;

        detailCard.innerHTML = detailHTML;
        detailsContainer.appendChild(detailCard);
    });
}

// Toggle route detail expansion
function toggleRouteDetail(algo) {
    const content = document.getElementById(`${algo}-detail-content`);
    const chevron = document.getElementById(`${algo}-detail-chevron`);

    if (content && chevron) {
        content.classList.toggle('hidden');
        chevron.style.transform = content.classList.contains('hidden') ? 'rotate(0deg)' : 'rotate(180deg)';
    }
}

// Compute Google Maps route (wrapper)
async function computeGoogleMapsRoute() {
    // This will use the existing Google Maps comparison function
    // but return it in a structured format for comparison

    if (!window.startLocation || !window.destLocation) {
        throw new Error('Start and destination required');
    }

    try {
        const startTime = performance.now(); // Track query time

        const response = await fetch('/get_google_maps_route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_lat: window.startLocation.lat,
                start_lng: window.startLocation.lng,
                dest_lat: window.destLocation.lat,
                dest_lng: window.destLocation.lng
            })
        });

        const queryTime = performance.now() - startTime; // Calculate query time

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Google Maps route failed');
        }

        // Extract route data from the new endpoint format
        const routeData = data.route || {};
        const distanceKm = (routeData.distance_meters || 0) / 1000;

        return {
            success: true,
            route: {
                distance: distanceKm,
                duration: routeData.duration_seconds || 0,
                polylines: routeData.coordinates ? [routeData.coordinates] : [],
                coordinates: routeData.coordinates || []
            },
            metrics: {
                distance: distanceKm,
                duration: routeData.duration_seconds || 0,
                segments: routeData.point_count || 0,
                query_time_ms: queryTime
            }
        };
    } catch (error) {
        console.error('Google Maps route error:', error);
        throw error;
    }
}

// Compute HERE API route (wrapper)
async function computeHereRoute() {
    // Fetch route from HERE Routing API
    // Returns structured format for comparison

    if (!window.startLocation || !window.destLocation) {
        throw new Error('Start and destination required');
    }

    try {
        const startTime = performance.now(); // Track query time

        console.log('📍 HERE API Request:', {
            start: window.startLocation,
            dest: window.destLocation
        });

        const response = await fetch('/get_here_route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_lat: window.startLocation.lat,
                start_lng: window.startLocation.lng,
                dest_lat: window.destLocation.lat,
                dest_lng: window.destLocation.lng,
                traffic_mode: 'enabled'  // Use real-time traffic
            })
        });

        const queryTime = performance.now() - startTime; // Calculate query time

        const data = await response.json();
        
        console.log('📍 HERE API Response:', data);

        if (!data.success) {
            throw new Error(data.error || 'HERE API route failed');
        }

        // Extract route data from endpoint format
        const routeData = data.route || {};
        const distanceKm = (routeData.distance_meters || 0) / 1000;
        
        console.log('📍 HERE Route Data:', {
            coordCount: routeData.coordinates?.length,
            firstCoord: routeData.coordinates?.[0],
            lastCoord: routeData.coordinates?.[routeData.coordinates?.length - 1],
            distance: distanceKm
        });

        return {
            success: true,
            route: {
                distance: distanceKm,
                duration: routeData.duration_seconds || 0,
                polylines: routeData.coordinates ? [routeData.coordinates] : [],
                coordinates: routeData.coordinates || [],
                traffic_mode: routeData.traffic_mode || 'enabled',
                sections: routeData.sections || 0
            },
            metrics: {
                distance: distanceKm,
                duration: routeData.duration_seconds || 0,
                segments: routeData.point_count || 0,
                query_time_ms: queryTime
            }
        };
    } catch (error) {
        console.error('HERE API route error:', error);
        throw error;
    }
}

console.log('✅ Algorithm Comparison module loaded');
