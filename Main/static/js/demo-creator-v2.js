/**
 * Custom Demo Creator V2 - Reimagined
 * 
 * Intuitive demo creation with:
 * - Location search like start/destination selection
 * - Random route generation option
 * - Visual disruption configuration
 * - Easy-to-use interface
 */

const DemoCreatorV2 = {
    // State
    routes: [],
    currentRouteIndex: -1,
    disruptions: {
        mode: 'none', // 'none', 'random-flow', 'random-incidents', 'random-both', 'custom'
        randomFlowCount: 5,
        randomIncidentCount: 3,
        severityMin: 0.3,
        severityMax: 0.9,
        customItems: []
    },
    sequence: {
        algorithm: 'both',
        tauMode: 'sequence', // 'fixed', 'random', 'sequence'
        tauFixed: 0.5,
        tauSequence: [0.1, 0.3, 0.5, 0.7, 0.9],
        tauRandomMin: 0.1,
        tauRandomMax: 0.9,
        stepDelay: 2000,
        showMetrics: true,
        trials: 1
    },
    markers: {},
    routeMarkers: [],
    disruptionMarkers: [],
    matchedEdgeLayers: [],
    
    // Preset locations
    presetLocations: [
        { name: 'Quezon Memorial Circle', lat: 14.6540, lng: 121.0490, type: 'landmark' },
        { name: 'SM North EDSA', lat: 14.6563, lng: 121.0315, type: 'mall' },
        { name: 'UP Diliman', lat: 14.6537, lng: 121.0685, type: 'university' },
        { name: 'Trinoma Mall', lat: 14.6560, lng: 121.0324, type: 'mall' },
        { name: 'Araneta Coliseum', lat: 14.6225, lng: 121.0501, type: 'landmark' },
        { name: 'Eastwood City', lat: 14.6093, lng: 121.0776, type: 'business' },
        { name: 'Tomas Morato Ave', lat: 14.6320, lng: 121.0324, type: 'street' },
        { name: 'Ateneo de Manila', lat: 14.6386, lng: 121.0779, type: 'university' },
        { name: 'Katipunan Avenue', lat: 14.6300, lng: 121.0700, type: 'street' },
        { name: 'Commonwealth Avenue', lat: 14.6700, lng: 121.0700, type: 'street' },
        { name: 'Cubao', lat: 14.6180, lng: 121.0540, type: 'area' },
        { name: 'Fairview', lat: 14.7000, lng: 121.0800, type: 'area' },
        { name: 'Diliman', lat: 14.6500, lng: 121.0600, type: 'area' },
        { name: 'Project 6', lat: 14.6450, lng: 121.0350, type: 'area' },
        { name: 'Teacher\'s Village', lat: 14.6400, lng: 121.0500, type: 'area' }
    ],

    // ==========================================================================
    // INITIALIZATION
    // ==========================================================================

    init() {
        console.log('🎨 Initializing Demo Creator V2...');
        this.bindEvents();
        this.renderRoutesList();
    },

    bindEvents() {
        // Route search inputs
        this.setupLocationSearch('demo-start-search', 'demo-start-dropdown', 'start');
        this.setupLocationSearch('demo-end-search', 'demo-end-dropdown', 'end');
        
        // Tau mode change
        document.getElementById('demo-tau-mode')?.addEventListener('change', (e) => {
            this.sequence.tauMode = e.target.value;
            this.updateTauModeUI();
        });
        
        // Algorithm change
        document.getElementById('demo-algorithm-select')?.addEventListener('change', (e) => {
            this.sequence.algorithm = e.target.value;
        });
        
        // Disruption mode change
        document.getElementById('demo-disruption-mode')?.addEventListener('change', (e) => {
            this.disruptions.mode = e.target.value;
            this.updateDisruptionModeUI();
        });
    },

    setupLocationSearch(inputId, dropdownId, type) {
        const input = document.getElementById(inputId);
        const dropdown = document.getElementById(dropdownId);
        
        if (!input || !dropdown) return;
        
        let searchTimeout;
        
        input.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim().toLowerCase();
            
            if (query.length < 2) {
                dropdown.classList.add('hidden');
                return;
            }
            
            searchTimeout = setTimeout(() => {
                this.performLocalSearch(query, dropdown, type);
            }, 200);
        });
        
        input.addEventListener('focus', () => {
            if (input.value.length >= 2) {
                dropdown.classList.remove('hidden');
            }
        });
        
        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest(`#${inputId}`) && !e.target.closest(`#${dropdownId}`)) {
                dropdown.classList.add('hidden');
            }
        });
    },

    performLocalSearch(query, dropdown, type) {
        // Filter preset locations
        const matches = this.presetLocations.filter(loc => 
            loc.name.toLowerCase().includes(query)
        ).slice(0, 6);
        
        if (matches.length === 0) {
            dropdown.innerHTML = `
                <div class="p-4 text-center text-gray-400">
                    <p class="text-sm">No locations found</p>
                    <p class="text-xs mt-1">Try a different search or use map pin</p>
                </div>
            `;
        } else {
            const color = type === 'start' ? 'emerald' : 'rose';
            dropdown.innerHTML = matches.map(loc => `
                <div class="location-result px-4 py-3 hover:bg-${color}-50 cursor-pointer border-b border-gray-100 last:border-0 transition-colors"
                     data-lat="${loc.lat}" data-lng="${loc.lng}" data-name="${loc.name}" data-type="${type}">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-full bg-${color}-100 flex items-center justify-center">
                            <span class="text-${color}-600">${type === 'start' ? '🟢' : '🔴'}</span>
                        </div>
                        <div>
                            <div class="font-semibold text-gray-800">${loc.name}</div>
                            <div class="text-xs text-gray-500">${loc.lat.toFixed(4)}, ${loc.lng.toFixed(4)}</div>
                        </div>
                    </div>
                </div>
            `).join('');
            
            // Add click handlers
            dropdown.querySelectorAll('.location-result').forEach(el => {
                el.addEventListener('click', () => {
                    const lat = parseFloat(el.dataset.lat);
                    const lng = parseFloat(el.dataset.lng);
                    const name = el.dataset.name;
                    const locType = el.dataset.type;
                    
                    this.setRouteLocation(locType, { name, lat, lng });
                    dropdown.classList.add('hidden');
                    
                    // Update input
                    const inputId = locType === 'start' ? 'demo-start-search' : 'demo-end-search';
                    document.getElementById(inputId).value = name;
                });
            });
        }
        
        dropdown.classList.remove('hidden');
    },

    // ==========================================================================
    // PANEL CONTROLS
    // ==========================================================================

    openPanel() {
        const panel = document.getElementById('demo-creator-v2-panel');
        if (panel) {
            panel.classList.remove('translate-x-full');
            this.goToStep(1);
        }
    },

    closePanel() {
        const panel = document.getElementById('demo-creator-v2-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
        }
        this.resetAll();
    },

    resetAll() {
        // Clear all markers from map
        this.clearPreviewMarkers();
        this.clearAllRouteMarkers();
        this.clearAllDisruptionMarkers();
        
        // Reset routes
        this.routes = [];
        this.currentRouteIndex = -1;
        
        // Reset disruptions
        this.disruptions = {
            mode: 'none',
            randomFlowCount: 5,
            randomIncidentCount: 3,
            severityMin: 0.3,
            severityMax: 0.9,
            customItems: []
        };
        
        // Reset sequence
        this.sequence = {
            algorithm: 'both',
            tauMode: 'sequence',
            tauFixed: 0.5,
            tauSequence: [0.1, 0.3, 0.5, 0.7, 0.9],
            tauRandomMin: 0.1,
            tauRandomMax: 0.9,
            stepDelay: 2000,
            showMetrics: true,
            trials: 1
        };
        
        // Reset currentEditRoute
        this.currentEditRoute = { start: null, end: null };
        
        // Reset UI elements
        this.renderRoutesList();
        this.renderDisruptionsList();
        
        // Reset form inputs
        const startSearch = document.getElementById('demo-start-search');
        const endSearch = document.getElementById('demo-end-search');
        if (startSearch) startSearch.value = '';
        if (endSearch) endSearch.value = '';
        
        // Reset disruption mode select
        const disruptionMode = document.getElementById('demo-disruption-mode');
        if (disruptionMode) disruptionMode.value = 'none';
        
        // Reset algorithm select
        const algorithmSelect = document.getElementById('demo-algorithm-select');
        if (algorithmSelect) algorithmSelect.value = 'both';
        
        // Reset tau mode
        const tauMode = document.getElementById('demo-tau-mode');
        if (tauMode) tauMode.value = 'sequence';
        
        // Reset trials
        const trialsInput = document.getElementById('demo-trials-count');
        if (trialsInput) trialsInput.value = '1';
        
        console.log('🔄 Demo Creator V2 reset');
    },

    clearAllRouteMarkers() {
        this.routeMarkers.forEach(marker => {
            if (map && marker) {
                map.removeLayer(marker);
            }
        });
        this.routeMarkers = [];
    },

    clearAllDisruptionMarkers() {
        this.disruptionMarkers.forEach(m => {
            if (map && m.marker) {
                map.removeLayer(m.marker);
            }
        });
        this.disruptionMarkers = [];
    },

    goToStep(step) {
        // Hide all steps
        [1, 2, 3, 4].forEach(s => {
            document.getElementById(`demo-v2-step-${s}`)?.classList.add('hidden');
        });
        
        // Show selected step
        document.getElementById(`demo-v2-step-${step}`)?.classList.remove('hidden');
        
        // Update step indicators
        [1, 2, 3, 4].forEach(s => {
            const indicator = document.getElementById(`demo-v2-indicator-${s}`);
            if (indicator) {
                if (s === step) {
                    indicator.classList.remove('bg-gray-300', 'text-gray-600');
                    indicator.classList.add('bg-purple-600', 'text-white');
                } else if (s < step) {
                    indicator.classList.remove('bg-gray-300', 'text-gray-600', 'bg-purple-600');
                    indicator.classList.add('bg-green-500', 'text-white');
                } else {
                    indicator.classList.remove('bg-purple-600', 'text-white', 'bg-green-500');
                    indicator.classList.add('bg-gray-300', 'text-gray-600');
                }
            }
        });
        
        // Update nav buttons
        document.getElementById('demo-v2-prev-btn')?.classList.toggle('hidden', step === 1);
        document.getElementById('demo-v2-next-btn')?.classList.toggle('hidden', step === 4);
        document.getElementById('demo-v2-run-btn')?.classList.toggle('hidden', step !== 4);
        
        // Update review if on step 4
        if (step === 4) {
            this.updateReviewSummary();
        }
    },

    nextStep() {
        const currentStep = this.getCurrentStep();
        if (this.validateStep(currentStep)) {
            this.goToStep(Math.min(4, currentStep + 1));
        }
    },

    prevStep() {
        const currentStep = this.getCurrentStep();
        this.goToStep(Math.max(1, currentStep - 1));
    },

    getCurrentStep() {
        for (let s = 1; s <= 4; s++) {
            if (!document.getElementById(`demo-v2-step-${s}`)?.classList.contains('hidden')) {
                return s;
            }
        }
        return 1;
    },

    validateStep(step) {
        switch (step) {
            case 1:
                if (this.routes.length === 0) {
                    showUpdateToast('Please add at least one route', 'warning');
                    return false;
                }
                return true;
            case 2:
                return true; // Disruptions are optional
            case 3:
                return true; // Sequence always has defaults
            default:
                return true;
        }
    },

    // ==========================================================================
    // ROUTE MANAGEMENT
    // ==========================================================================

    currentEditRoute: null,

    setRouteLocation(type, location) {
        if (!this.currentEditRoute) {
            this.currentEditRoute = { id: `route-${Date.now()}`, start: null, end: null };
        }
        
        this.currentEditRoute[type] = location;
        
        // Add preview marker
        this.addPreviewMarker(type, location);
        
        // Check if route is complete
        if (this.currentEditRoute.start && this.currentEditRoute.end) {
            document.getElementById('demo-add-route-btn')?.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    },

    addPreviewMarker(type, location) {
        const markerId = `preview-${type}`;
        
        // Remove existing marker
        if (this.markers[markerId]) {
            map.removeLayer(this.markers[markerId]);
        }
        
        const iconColor = type === 'start' ? 'green' : 'red';
        const icon = L.icon({
            iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${iconColor}.png`,
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        
        this.markers[markerId] = L.marker([location.lat, location.lng], { icon })
            .bindPopup(`<b>${type === 'start' ? '🟢 Start' : '🔴 End'}</b><br>${location.name}`)
            .addTo(map);
        
        // Fit bounds to show both markers
        if (this.markers['preview-start'] && this.markers['preview-end']) {
            const bounds = L.latLngBounds([
                [this.currentEditRoute.start.lat, this.currentEditRoute.start.lng],
                [this.currentEditRoute.end.lat, this.currentEditRoute.end.lng]
            ]);
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    },

    clearPreviewMarkers() {
        ['preview-start', 'preview-end'].forEach(id => {
            if (this.markers[id]) {
                map.removeLayer(this.markers[id]);
                delete this.markers[id];
            }
        });
    },

    addRouteFromInputs() {
        if (!this.currentEditRoute?.start || !this.currentEditRoute?.end) {
            showUpdateToast('Please select both start and end locations', 'warning');
            return;
        }
        
        const newRoute = {
            id: `route-${Date.now()}`,
            ...this.currentEditRoute
        };
        this.routes.push(newRoute);
        this.currentEditRoute = { start: null, end: null };
        
        // Clear inputs
        document.getElementById('demo-start-search').value = '';
        document.getElementById('demo-end-search').value = '';
        
        this.clearPreviewMarkers();
        
        // Show the new route on map
        this.showRoutesOnMap([newRoute]);
        
        this.renderRoutesList();
        
        // Disable add button again
        document.getElementById('demo-add-route-btn')?.classList.add('opacity-50', 'cursor-not-allowed');
        
        showUpdateToast('Route added successfully', 'success');
    },

    generateRandomRoutes() {
        const countInput = document.getElementById('demo-random-count');
        const count = parseInt(countInput?.value) || 3;
        
        const newRoutes = [];
        for (let i = 0; i < count; i++) {
            let start, end;
            do {
                const startIdx = Math.floor(Math.random() * this.presetLocations.length);
                const endIdx = Math.floor(Math.random() * this.presetLocations.length);
                start = this.presetLocations[startIdx];
                end = this.presetLocations[endIdx];
            } while (start.name === end.name);
            
            const route = {
                id: `route-${Date.now()}-${i}`,
                start: { ...start },
                end: { ...end }
            };
            this.routes.push(route);
            newRoutes.push(route);
        }
        
        // Show markers on map for new routes
        this.showRoutesOnMap(newRoutes);
        
        this.renderRoutesList();
        showUpdateToast(`Added ${count} random routes`, 'success');
    },

    showRoutesOnMap(routes) {
        const bounds = [];
        const colors = ['green', 'red', 'blue', 'orange', 'violet', 'yellow', 'grey', 'gold'];
        
        routes.forEach((route, index) => {
            const colorIndex = (this.routes.indexOf(route)) % colors.length;
            const startColor = 'green';
            const endColor = 'red';
            
            // Create start marker
            const startIcon = L.icon({
                iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${startColor}.png`,
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            });
            
            const startMarker = L.marker([route.start.lat, route.start.lng], { icon: startIcon })
                .bindPopup(`<b>🟢 Route ${this.routes.indexOf(route) + 1} Start</b><br>${route.start.name}`)
                .addTo(map);
            
            // Create end marker
            const endIcon = L.icon({
                iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${endColor}.png`,
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            });
            
            const endMarker = L.marker([route.end.lat, route.end.lng], { icon: endIcon })
                .bindPopup(`<b>🔴 Route ${this.routes.indexOf(route) + 1} End</b><br>${route.end.name}`)
                .addTo(map);
            
            // Store markers for later cleanup
            this.routeMarkers.push(startMarker, endMarker);
            
            // Add to bounds
            bounds.push([route.start.lat, route.start.lng]);
            bounds.push([route.end.lat, route.end.lng]);
            
            // Draw dashed line between start and end
            const line = L.polyline([
                [route.start.lat, route.start.lng],
                [route.end.lat, route.end.lng]
            ], {
                color: colors[colorIndex % colors.length],
                weight: 2,
                dashArray: '5, 10',
                opacity: 0.7
            }).addTo(map);
            
            this.routeMarkers.push(line);
        });
        
        // Fit map to show all routes
        if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    },

    removeRoute(routeId) {
        this.routes = this.routes.filter(r => r.id !== routeId);
        // Redraw all route markers
        this.clearAllRouteMarkers();
        if (this.routes.length > 0) {
            this.showRoutesOnMap(this.routes);
        }
        this.renderRoutesList();
    },

    clearAllRoutes() {
        this.routes = [];
        this.clearAllRouteMarkers();
        this.renderRoutesList();
        showUpdateToast('All routes cleared', 'info');
    },

    renderRoutesList() {
        const container = document.getElementById('demo-routes-list');
        if (!container) return;
        
        if (this.routes.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <svg class="w-16 h-16 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" 
                              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
                    </svg>
                    <p class="font-medium">No routes added</p>
                    <p class="text-xs mt-1">Search for locations or generate random routes</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.routes.map((route, index) => `
            <div class="bg-white rounded-xl p-4 border border-gray-200 shadow-sm hover:shadow-md transition-all">
                <div class="flex items-start justify-between mb-3">
                    <span class="text-xs font-bold text-purple-600 bg-purple-100 px-2 py-1 rounded">Route ${index + 1}</span>
                    <button onclick="DemoCreatorV2.removeRoute('${route.id}')" 
                            class="p-1 hover:bg-red-100 rounded-lg transition-colors">
                        <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                <div class="space-y-2">
                    <div class="flex items-center gap-2">
                        <span class="text-lg">🟢</span>
                        <div class="flex-1 min-w-0">
                            <div class="font-semibold text-gray-800 truncate">${route.start.name}</div>
                            <div class="text-xs text-gray-500">${route.start.lat.toFixed(4)}, ${route.start.lng.toFixed(4)}</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 pl-3">
                        <div class="w-0.5 h-4 bg-gray-300"></div>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="text-lg">🔴</span>
                        <div class="flex-1 min-w-0">
                            <div class="font-semibold text-gray-800 truncate">${route.end.name}</div>
                            <div class="text-xs text-gray-500">${route.end.lat.toFixed(4)}, ${route.end.lng.toFixed(4)}</div>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    },

    // ==========================================================================
    // DISRUPTION MANAGEMENT
    // ==========================================================================

    updateDisruptionModeUI() {
        const mode = this.disruptions.mode;
        
        document.getElementById('disruption-random-settings')?.classList.toggle('hidden', 
            mode === 'none' || mode === 'custom');
        document.getElementById('disruption-custom-settings')?.classList.toggle('hidden', 
            mode !== 'custom');
        
        // Show/hide flow count based on mode
        document.getElementById('disruption-flow-count-row')?.classList.toggle('hidden',
            mode !== 'random-flow' && mode !== 'random-both');
        document.getElementById('disruption-incident-count-row')?.classList.toggle('hidden',
            mode !== 'random-incidents' && mode !== 'random-both');
    },

    async addCustomDisruption() {
        showUpdateToast('Click on the map to add a disruption point', 'info');
        map.getContainer().style.cursor = 'crosshair';
        
        const clickHandler = async (e) => {
            const lat = e.latlng.lat;
            const lng = e.latlng.lng;
            
            try {
                // Snap to nearest road
                const response = await fetch('/find_nearest_osm_road', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lat, lng })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    const disruption = {
                        id: `disruption-${Date.now()}`,
                        type: document.getElementById('custom-disruption-type')?.value || 'incident',
                        lat: data.snapped_point.lat,
                        lng: data.snapped_point.lng,
                        roadName: data.road_name || 'Unknown Road',
                        source: data.routing_nodes[0],
                        target: data.routing_nodes[1],
                        severity: parseFloat(document.getElementById('custom-disruption-severity')?.value) || 0.5
                    };
                    
                    this.disruptions.customItems.push(disruption);
                    this.addDisruptionMarker(disruption);
                    this.renderDisruptionsList();
                    
                    showUpdateToast(`Added disruption on ${disruption.roadName}`, 'success');
                } else {
                    showUpdateToast('Could not snap to road', 'warning');
                }
            } catch (error) {
                console.error('Error adding disruption:', error);
                showUpdateToast('Error adding disruption', 'error');
            }
            
            map.getContainer().style.cursor = '';
            map.off('click', clickHandler);
        };
        
        map.once('click', clickHandler);
    },

    addDisruptionMarker(disruption) {
        const color = disruption.type === 'incident' ? 'red' : 'orange';
        const marker = L.circleMarker([disruption.lat, disruption.lng], {
            radius: 10,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).bindPopup(`
            <b>${disruption.type === 'incident' ? '🚨 Incident' : '🚦 Traffic'}</b><br>
            ${disruption.roadName}<br>
            Severity: ${(disruption.severity * 100).toFixed(0)}%
        `).addTo(map);
        
        this.disruptionMarkers.push({ id: disruption.id, marker });
    },

    removeDisruption(disruptionId) {
        this.disruptions.customItems = this.disruptions.customItems.filter(d => d.id !== disruptionId);
        
        const markerEntry = this.disruptionMarkers.find(m => m.id === disruptionId);
        if (markerEntry) {
            map.removeLayer(markerEntry.marker);
            this.disruptionMarkers = this.disruptionMarkers.filter(m => m.id !== disruptionId);
        }
        
        this.renderDisruptionsList();
    },

    clearAllDisruptions() {
        this.disruptions.customItems = [];
        this.disruptionMarkers.forEach(m => map.removeLayer(m.marker));
        this.disruptionMarkers = [];
        this.renderDisruptionsList();
    },

    renderDisruptionsList() {
        const container = document.getElementById('demo-disruptions-list');
        if (!container) return;
        
        if (this.disruptions.customItems.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-gray-400 text-sm">
                    No custom disruptions added
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.disruptions.customItems.map(d => `
            <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <span class="text-xl">${d.type === 'incident' ? '🚨' : '🚦'}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-medium text-gray-800 truncate">${d.roadName}</div>
                    <div class="text-xs text-gray-500">Severity: ${(d.severity * 100).toFixed(0)}%</div>
                </div>
                <button onclick="DemoCreatorV2.removeDisruption('${d.id}')" 
                        class="p-1 hover:bg-red-100 rounded transition-colors">
                    <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        `).join('');
    },

    // ==========================================================================
    // SEQUENCE CONFIGURATION
    // ==========================================================================

    updateTauModeUI() {
        const mode = this.sequence.tauMode;
        
        document.getElementById('tau-fixed-setting')?.classList.toggle('hidden', mode !== 'fixed');
        document.getElementById('tau-random-setting')?.classList.toggle('hidden', mode !== 'random');
        document.getElementById('tau-sequence-setting')?.classList.toggle('hidden', mode !== 'sequence');
    },

    getTauValues() {
        switch (this.sequence.tauMode) {
            case 'fixed':
                return [parseFloat(document.getElementById('demo-tau-fixed')?.value) || 0.5];
            case 'random':
                const min = parseFloat(document.getElementById('demo-tau-random-min')?.value) || 0.1;
                const max = parseFloat(document.getElementById('demo-tau-random-max')?.value) || 0.9;
                return [Math.random() * (max - min) + min];
            case 'sequence':
                const seqStr = document.getElementById('demo-tau-sequence')?.value || '0.1, 0.3, 0.5, 0.7, 0.9';
                return seqStr.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v));
            default:
                return [0.5];
        }
    },

    // ==========================================================================
    // REVIEW & RUN
    // ==========================================================================

    updateReviewSummary() {
        const container = document.getElementById('demo-v2-review-summary');
        if (!container) return;
        
        const algorithm = document.getElementById('demo-algorithm-select')?.value || 'both';
        const tauValues = this.getTauValues();
        const stepDelay = parseInt(document.getElementById('demo-step-delay')?.value) || 2000;
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        
        container.innerHTML = `
            <div class="space-y-4">
                <div class="bg-blue-50 rounded-xl p-4">
                    <h4 class="font-bold text-blue-800 mb-2">📍 Routes (${this.routes.length})</h4>
                    <div class="space-y-2 max-h-32 overflow-y-auto">
                        ${this.routes.map((r, i) => `
                            <div class="text-sm text-blue-700">
                                <span class="font-medium">${i + 1}.</span> ${r.start.name} → ${r.end.name}
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <div class="bg-orange-50 rounded-xl p-4">
                    <h4 class="font-bold text-orange-800 mb-2">🚦 Disruptions</h4>
                    <p class="text-sm text-orange-700">
                        Mode: ${this.disruptions.mode}<br>
                        ${this.disruptions.mode.includes('random') ? `Severity range: ${this.disruptions.severityMin} - ${this.disruptions.severityMax}<br>` : ''}
                        ${this.disruptions.mode === 'custom' ? `Custom items: ${this.disruptions.customItems.length}` : ''}
                    </p>
                </div>
                
                <div class="bg-purple-50 rounded-xl p-4">
                    <h4 class="font-bold text-purple-800 mb-2">⚙️ Sequence</h4>
                    <p class="text-sm text-purple-700">
                        Algorithm: ${algorithm.toUpperCase()}<br>
                        τ values: ${tauValues.map(v => v.toFixed(2)).join(', ')}<br>
                        Step delay: ${stepDelay}ms
                    </p>
                </div>
                
                <div class="bg-indigo-50 rounded-xl p-4">
                    <h4 class="font-bold text-indigo-800 mb-2">🔄 Execution</h4>
                    <p class="text-sm text-indigo-700">
                        Trials: ${trials}<br>
                        Total runs: ${this.routes.length * trials}
                    </p>
                </div>
            </div>
        `;
    },

    async saveAndRun() {
        // Read severity range values
        this.disruptions.severityMin = parseFloat(document.getElementById('random-severity-min')?.value) || 0.3;
        this.disruptions.severityMax = parseFloat(document.getElementById('random-severity-max')?.value) || 0.9;
        
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        
        // Collect configuration
        const config = {
            name: document.getElementById('demo-v2-name')?.value || `Custom Demo - ${new Date().toLocaleString()}`,
            routes: this.routes.map(r => ({
                ...r,
                tauValues: this.getTauValues()
            })),
            trials: trials,
            algorithm: document.getElementById('demo-algorithm-select')?.value || 'both',
            disruptions: { ...this.disruptions },
            stepDelay: parseInt(document.getElementById('demo-step-delay')?.value) || 2000
        };
        
        // Save to DemoRunner
        if (document.getElementById('demo-v2-save-config')?.checked) {
            DemoRunner.saveConfig(config);
        }
        
        // Close panel
        this.closePanel();
        
        // Run via DemoRunner
        DemoRunner.runDemo(config);
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    DemoCreatorV2.init();
});

// Global exports
window.DemoCreatorV2 = DemoCreatorV2;
window.openDemoCreatorV2 = () => DemoCreatorV2.openPanel();
window.closeDemoCreatorV2 = () => DemoCreatorV2.closePanel();

console.log('✅ Demo Creator V2 module loaded');
