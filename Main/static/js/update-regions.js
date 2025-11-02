/**
 * Visual Update Region Overlay Module
 * Shows affected regions visually on the map:
 * - Green overlay for Lazy HC2L (incremental updates)
 * - Yellow/Orange overlay for DHL (global rebuild updates)
 */

// Global storage for update region layers
window.updateRegionLayers = {
    lazy: null,      // Green overlay for lazy updates
    immediate: null  // Yellow overlay for immediate updates
};

/**
 * Show update region overlay based on algorithm and update strategy
 * @param {Object} routeData - Route calculation response
 */
function showUpdateRegion(routeData) {
    // Clear existing overlays first
    clearUpdateRegions();
    
    if (!routeData || !routeData.success) {
        return;
    }
    
    const algorithm = routeData.algorithm || routeData.metrics?.algorithm || '';
    const metrics = routeData.metrics || {};
    
    // Determine update strategy
    let updateStrategy = 'none';
    let affectedNodes = [];
    let center = null;
    let radius = 500; // Default radius in meters
    
    if (algorithm.includes('HC2L') || algorithm.includes('D-HC2L')) {
        // LazyHC2L has update strategy info
        const lazyInfo = routeData.lazy_hc2l || {};
        updateStrategy = lazyInfo.update_strategy || 'none';
        
        if (updateStrategy === 'lazy_mark') {
            // Get dirty nodes marked for lazy update
            const dirtyNodesCount = lazyInfo.dirty_nodes_marked || 0;
            if (dirtyNodesCount > 0) {
                // Show green overlay for lazy update region
                showLazyUpdateRegion(routeData);
            }
        } else if (updateStrategy === 'immediate_update') {
            // Show yellow overlay for immediate update region
            showImmediateUpdateRegion(routeData, 'hc2l');
        }
    } else if (algorithm.includes('DHL')) {
        // DHL always does immediate update
        const dhlInfo = routeData.dhl_update_info || {};
        updateStrategy = dhlInfo.update_strategy || 'none';
        
        if (updateStrategy === 'immediate_update') {
            // Show orange overlay for DHL global rebuild
            showImmediateUpdateRegion(routeData, 'dhl');
        }
    }
    
    console.log('📍 Update region overlay:', updateStrategy, 'for', algorithm);
}

/**
 * Show green overlay for Lazy HC2L incremental updates
 * @param {Object} routeData - Route data with lazy update info
 */
function showLazyUpdateRegion(routeData) {
    const lazyInfo = routeData.lazy_hc2l || {};
    const route = routeData.route || {};
    
    // Get disruption location or use route center
    const disruptions = window.currentDisruptions || [];
    
    if (disruptions.length > 0) {
        // Show overlay around each disruption
        disruptions.forEach(disruption => {
            if (disruption.marker) {
                const latlng = disruption.marker.getLatLng();
                
                // Create green circle overlay
                const circle = L.circle([latlng.lat, latlng.lng], {
                    color: '#10b981',        // Emerald green border
                    fillColor: '#34d399',    // Lighter green fill
                    fillOpacity: 0.15,
                    weight: 3,
                    radius: 300,             // 300m radius for lazy update region
                    dashArray: '10, 5',
                    className: 'lazy-update-region'
                }).addTo(map);
                
                circle.bindPopup(
                    `<div class="p-3 min-w-[240px]">` +
                    `<div class="font-bold text-lg mb-2 text-emerald-700 flex items-center">` +
                    `<span class="mr-2">🟢</span> Lazy Update Region` +
                    `</div>` +
                    `<div class="bg-gradient-to-r from-green-50 to-emerald-50 px-3 py-2 rounded-lg border border-green-200 mb-2">` +
                    `<div class="text-xs text-green-700 font-semibold">Incremental Update Strategy</div>` +
                    `</div>` +
                    `<div class="space-y-2 text-sm">` +
                    `<div class="flex justify-between">` +
                    `<span class="text-slate-600">Strategy:</span>` +
                    `<span class="text-emerald-600 font-bold">Lazy Mark</span>` +
                    `</div>` +
                    `<div class="flex justify-between">` +
                    `<span class="text-slate-600">Dirty Nodes:</span>` +
                    `<span class="text-blue-600 font-bold">${lazyInfo.dirty_nodes_marked || 0}</span>` +
                    `</div>` +
                    `<div class="flex justify-between">` +
                    `<span class="text-slate-600">Radius:</span>` +
                    `<span class="text-slate-700">300m</span>` +
                    `</div>` +
                    `<div class="text-xs text-slate-500 mt-2 italic">` +
                    `Labels marked as stale, will be repaired when queried` +
                    `</div>` +
                    `</div>` +
                    `</div>`
                );
                
                // Store reference
                if (!window.updateRegionLayers.lazy) {
                    window.updateRegionLayers.lazy = [];
                }
                window.updateRegionLayers.lazy.push(circle);
            }
        });
    }
    
    console.log('✅ Lazy update region overlay shown (green)');
}

/**
 * Show yellow/orange overlay for immediate updates
 * @param {Object} routeData - Route data
 * @param {string} algorithmType - 'hc2l' or 'dhl'
 */
function showImmediateUpdateRegion(routeData, algorithmType) {
    const disruptions = window.currentDisruptions || [];
    
    // Color scheme based on algorithm
    const color = algorithmType === 'dhl' ? '#f97316' : '#eab308'; // Orange for DHL, Yellow for HC2L
    const fillColor = algorithmType === 'dhl' ? '#fb923c' : '#fde047';
    const label = algorithmType === 'dhl' ? 'DHL Global Rebuild' : 'HC2L Immediate Update';
    
    if (disruptions.length > 0) {
        disruptions.forEach(disruption => {
            if (disruption.marker) {
                const latlng = disruption.marker.getLatLng();
                
                // Create yellow/orange circle overlay
                const circle = L.circle([latlng.lat, latlng.lng], {
                    color: color,
                    fillColor: fillColor,
                    fillOpacity: 0.2,
                    weight: 3,
                    radius: 500,  // 500m radius for immediate update (larger impact)
                    dashArray: '5, 10',
                    className: 'immediate-update-region'
                }).addTo(map);
                
                const updateInfo = algorithmType === 'dhl' 
                    ? routeData.dhl_update_info 
                    : routeData.lazy_hc2l;
                
                circle.bindPopup(
                    `<div class="p-3 min-w-[240px]">` +
                    `<div class="font-bold text-lg mb-2" style="color: ${color};">` +
                    `<span class="mr-2">${algorithmType === 'dhl' ? '🟠' : '🟡'}</span> ${label}` +
                    `</div>` +
                    `<div class="bg-gradient-to-r px-3 py-2 rounded-lg border mb-2" style="background: linear-gradient(to right, ${fillColor}20, ${fillColor}30); border-color: ${color}40;">` +
                    `<div class="text-xs font-semibold" style="color: ${color};">Immediate Recomputation</div>` +
                    `</div>` +
                    `<div class="space-y-2 text-sm">` +
                    `<div class="flex justify-between">` +
                    `<span class="text-slate-600">Strategy:</span>` +
                    `<span class="font-bold" style="color: ${color};">Immediate Update</span>` +
                    `</div>` +
                    `<div class="flex justify-between">` +
                    `<span class="text-slate-600">Nodes Updated:</span>` +
                    `<span class="text-blue-600 font-bold">${updateInfo?.nodes_updated || updateInfo?.dirty_nodes_marked || 0}</span>` +
                    `</div>` +
                    `<div class="flex justify-between">` +
                    `<span class="text-slate-600">Radius:</span>` +
                    `<span class="text-slate-700">500m</span>` +
                    `</div>` +
                    `<div class="text-xs text-slate-500 mt-2 italic">` +
                    `${algorithmType === 'dhl' ? 'Labels rebuilt globally for entire network' : 'Labels recomputed immediately for affected region'}` +
                    `</div>` +
                    `</div>` +
                    `</div>`
                );
                
                // Store reference
                if (!window.updateRegionLayers.immediate) {
                    window.updateRegionLayers.immediate = [];
                }
                window.updateRegionLayers.immediate.push(circle);
            }
        });
    }
    
    console.log(`✅ Immediate update region overlay shown (${algorithmType === 'dhl' ? 'orange' : 'yellow'})`);
}

/**
 * Clear all update region overlays
 */
function clearUpdateRegions() {
    // Clear lazy update regions (green)
    if (window.updateRegionLayers.lazy) {
        if (Array.isArray(window.updateRegionLayers.lazy)) {
            window.updateRegionLayers.lazy.forEach(layer => {
                if (map.hasLayer(layer)) {
                    map.removeLayer(layer);
                }
            });
        } else if (map.hasLayer(window.updateRegionLayers.lazy)) {
            map.removeLayer(window.updateRegionLayers.lazy);
        }
        window.updateRegionLayers.lazy = null;
    }
    
    // Clear immediate update regions (yellow/orange)
    if (window.updateRegionLayers.immediate) {
        if (Array.isArray(window.updateRegionLayers.immediate)) {
            window.updateRegionLayers.immediate.forEach(layer => {
                if (map.hasLayer(layer)) {
                    map.removeLayer(layer);
                }
            });
        } else if (map.hasLayer(window.updateRegionLayers.immediate)) {
            map.removeLayer(window.updateRegionLayers.immediate);
        }
        window.updateRegionLayers.immediate = null;
    }
    
    console.log('🗑️  Update region overlays cleared');
}

// Expose functions globally
window.showUpdateRegion = showUpdateRegion;
window.clearUpdateRegions = clearUpdateRegions;

console.log('✅ Update regions module loaded');
