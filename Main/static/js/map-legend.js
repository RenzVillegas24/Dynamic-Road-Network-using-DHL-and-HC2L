/**
 * Map Legend Module
 * Displays comprehensive legend for all map elements
 * Required colors: Blue (Lazy HC2L), Purple (DHL), Orange (Google Maps),
 * Red (Disruptions), Green (Lazy update), Yellow (DHL update)
 */

// Global legend control
window.legendControl = null;

/**
 * Create and add map legend to the map
 */
function createMapLegend() {
    // Remove existing legend if any
    if (window.legendControl && map.hasLayer(window.legendControl)) {
        map.removeControl(window.legendControl);
    }
    
    // Create custom Leaflet control
    const legend = L.control({ position: 'bottomright' });
    
    legend.onAdd = function(map) {
        const div = L.DomUtil.create('div', '');
        
        div.innerHTML = `
            <div class="bg-white/85 backdrop-blur-lg rounded-lg shadow-2xl pt-4 pr-4 pl-4 border-2 border-slate-300 transition-all duration-300" style="min-width: 280px; padding-bottom: 0;">
                <!-- Header -->
                <div class="flex items-center justify-between mb-3">
                    <h3 class="font-bold text-slate-800 text-lg flex items-center">
                        <svg class="w-5 h-5 mr-2 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                        </svg>
                        Map Legend
                    </h3>
                    <button id="legend-toggle" class="text-slate-500 hover:text-slate-700 transition-colors">
                        <svg id="legend-collapse-icon" class="w-5 h-5 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>
                </div>
                
                <!-- Legend Content -->
                <div id="legend-content" class="space-y-3 transition-all duration-300 max-h-96 overflow-hidden opacity-0" style="max-height: 0;">
                    <!-- Routes Section -->
                    <div class="space-y-2">
                        <div class="text-xs font-bold text-slate-600 uppercase tracking-wide mb-2">Routes</div>
                        
                        <!-- 1. Blue - Lazy HC2L Route -->
                        <div class="flex items-center space-x-3 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                            <div class="w-8 h-1 bg-blue-600 rounded-full shadow-sm"></div>
                            <span class="text-sm text-slate-700 flex-1">Lazy HC2L Route</span>
                            <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-semibold">1</span>
                        </div>
                        
                        <!-- 2. Purple - DHL Route -->
                        <div class="flex items-center space-x-3 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                            <div class="w-8 h-1 bg-purple-600 rounded-full shadow-sm"></div>
                            <span class="text-sm text-slate-700 flex-1">DHL Route</span>
                            <span class="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-semibold">2</span>
                        </div>
                        
                        <!-- 3. Orange - Google Maps Route -->
                        <div class="flex items-center space-x-3 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                            <div class="w-8 h-1 border-2 border-orange-600 rounded-full shadow-sm" style="border-style: dashed;"></div>
                            <span class="text-sm text-slate-700 flex-1">Google Maps</span>
                            <span class="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-semibold">3</span>
                        </div>
                    </div>
                    
                    <!-- Divider -->
                    <div class="border-t border-slate-200"></div>
                    
                    <!-- Disruptions & Markers Section -->
                    <div class="space-y-2">
                        <div class="text-xs font-bold text-slate-600 uppercase tracking-wide mb-2">Markers</div>
                        
                        <!-- 4. Red - Disruptions -->
                        <div class="flex items-center space-x-3 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                            <div class="w-4 h-4 bg-red-600 rounded-full shadow-md border-2 border-white"></div>
                            <span class="text-sm text-slate-700 flex-1">Disruptions</span>
                            <span class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-semibold">4</span>
                        </div>
                        
                        <!-- Start/Destination Markers -->
                        <div class="flex items-center space-x-3 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                            <div class="flex space-x-1">
                                <div class="w-3 h-3 bg-green-600 rounded-full shadow-sm border border-white"></div>
                                <div class="w-3 h-3 bg-red-600 rounded-full shadow-sm border border-white"></div>
                            </div>
                            <span class="text-sm text-slate-700 flex-1">Start / Destination</span>
                        </div>
                    </div>
                    
                    <!-- Divider -->
                    <div class="border-t border-slate-200"></div>
                    
                    <!-- Update Regions Section -->
                    <div class="space-y-2">
                        <div class="text-xs font-bold text-slate-600 uppercase tracking-wide mb-2">Update Regions</div>
                        
                        <!-- 5. Green - Lazy Update Region -->
                        <div class="flex items-center space-x-3 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                            <div class="w-6 h-6 rounded-full border-2 border-emerald-600 bg-emerald-600/20" style="border-style: dashed;"></div>
                            <span class="text-sm text-slate-700 flex-1">Lazy Update (300m)</span>
                            <span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-semibold">5</span>
                        </div>
                        
                        <!-- 6. Yellow/Orange - DHL Update Region -->
                        <div class="flex items-center space-x-3 py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                            <div class="w-6 h-6 rounded-full border-2 border-orange-600 bg-orange-600/20" style="border-style: dashed;"></div>
                            <span class="text-sm text-slate-700 flex-1">Immediate Update (500m)</span>
                            <span class="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-semibold">6</span>
                        </div>
                    </div>
                    
                    <!-- Info Footer -->
                    <div class="mt-4 pt-3 border-t border-slate-200">
                        <div class="text-xs text-slate-500 italic">
                            <span class="font-semibold text-slate-600">Tip:</span> Click on any route or marker for details
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Prevent map interactions when clicking legend
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);
        
        return div;
    };
    
    legend.addTo(map);
    window.legendControl = legend;
    
    // Add toggle functionality
    setTimeout(() => {
        const toggleBtn = document.getElementById('legend-toggle');
        const content = document.getElementById('legend-content');
        const icon = document.getElementById('legend-collapse-icon');
        const container = content.closest('.bg-white\\/85');
        const header = container.querySelector('.flex.items-center.justify-between');
        
        if (toggleBtn && content && icon) {
            toggleBtn.addEventListener('click', () => {
                const isCollapsed = content.style.maxHeight === '0px' || content.style.maxHeight === '';
                
                if (isCollapsed) {
                    // Expand
                    content.style.maxHeight = '24rem'; // max-h-96 = 24rem
                    content.style.opacity = '1';
                    icon.style.transform = 'rotate(0deg)';
                    // Restore normal padding
                    if (container) {
                        container.style.paddingBottom = '1rem';
                    }
                    if (header) {
                        header.classList.add('pb-3');
                    }
                } else {
                    // Collapse
                    content.style.maxHeight = '0';
                    content.style.opacity = '0';
                    icon.style.transform = 'rotate(-90deg)';
                    // Remove all bottom padding when collapsed
                    if (container) {
                        container.style.paddingBottom = '0';
                    }
                    if (header) {
                        header.classList.remove('pb-3');
                        header.style.paddingBottom = '0';
                    }
                }
            });
        }
    }, 100);
    
    console.log('✅ Map legend created with all 6 required colors');
}

/**
 * Update legend visibility based on current state
 */
function updateLegendHighlights(activeElements) {
    // Could add visual highlighting for active elements
    // For now, legend shows all possible elements
    console.log('📍 Legend updated for active elements:', activeElements);
}

// Initialize legend when map is ready
function initLegendWhenReady() {
    console.log('🔍 Checking if map is ready for legend...');
    
    if (typeof map !== 'undefined' && map) {
        console.log('✅ Map found, creating legend');
        createMapLegend();
    } else {
        console.log('⏳ Map not ready yet, will retry...');
        // Retry after a short delay
        setTimeout(initLegendWhenReady, 500);
    }
}

// Try immediate initialization
if (typeof map !== 'undefined' && map) {
    console.log('✅ Map already available, creating legend immediately');
    createMapLegend();
} else {
    // Wait for DOMContentLoaded
    if (document.readyState === 'loading') {
        console.log('📄 Document still loading, waiting for DOMContentLoaded');
        document.addEventListener('DOMContentLoaded', initLegendWhenReady);
    } else {
        console.log('📄 Document already loaded, starting legend initialization');
        initLegendWhenReady();
    }
}

// Expose functions globally
window.createMapLegend = createMapLegend;
window.updateLegendHighlights = updateLegendHighlights;

console.log('✅ Map legend module loaded');
