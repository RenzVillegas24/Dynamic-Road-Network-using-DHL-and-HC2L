/**
 * Custom Demo Creator
 * 
 * Intuitive demo creation with:
 * - Location search like start/destination selection
 * - Random route generation option
 * - Visual disruption configuration
 * - Easy-to-use interface
 */

const DemoCreator = {
    // State
    routes: [],
    currentRouteIndex: -1,
    disruptions: {
        mode: 'random-both', // 'none', 'random-flow', 'random-incidents', 'random-both', 'custom'
        generationScope: 'per-trial-route', // 'all', 'per-trial', 'per-route', 'per-trial-route'
        randomFlowCount: 5,
        randomIncidentCount: 3,
        severityMin: 0,
        severityMax: 1,
        customItems: [],
        // Store multiple disruption sets based on generation scope
        disruptionSets: {}  // Key: 'all', 'trial_0', 'route_1', 'trial_0_route_1', etc.
    },
    sequence: {
        algorithm: 'both',
        tauMode: 'sequence', // 'fixed', 'random', 'sequence'
        tauFixed: 0.5,
        tauSequence: [0.1, 0.3, 0.5, 0.7, 0.9],
        tauRandomMin: 0.1,
        tauRandomMax: 0.9,
        tauGenerationScope: 'all', // 'all', 'per-trial', 'per-route', 'per-trial-route'
        stepDelay: 1000,
        showMetrics: true,
        trials: 1
    },
    markers: {},
    routeMarkers: [],
    disruptionMarkers: [],
    matchedEdgeLayers: [],
    
    // Quezon City boundary data (loaded from GeoJSON)
    qcBoundary: null,
    qcBoundingBox: null,
    
    // Edit mode state
    editingConfigId: null,
    
    // Running state
    isRunning: false,
    isPaused: false,
    currentProgress: {
        trial: 0,
        totalTrials: 1,
        route: 0,
        totalRoutes: 0,
        tauIndex: 0,
        totalTaus: 0,
        algorithm: '',
        currentTau: 0,
        status: '',
        lastResult: null
    },
    
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

    async init() {
        await this.loadQCBoundary();
        console.log('🎨 Initializing Demo Creator...');
        this.bindEvents();
        this.renderRoutesList();
    },
    
    /**
     * Load Quezon City boundary from GeoJSON file
     */
    async loadQCBoundary() {
        try {
            const response = await fetch('/static/quezon_city_boundaries.geojson');
            if (response.ok) {
                const geojson = await response.json();
                if (geojson.features && geojson.features.length > 0) {
                    const geometry = geojson.features[0].geometry;
                    if (geometry.type === 'Polygon') {
                        this.qcBoundary = geometry.coordinates[0];
                    } else if (geometry.type === 'MultiPolygon') {
                        this.qcBoundary = geometry.coordinates[0][0];
                    }
                    
                    if (this.qcBoundary) {
                        const lngs = this.qcBoundary.map(c => c[0]);
                        const lats = this.qcBoundary.map(c => c[1]);
                        this.qcBoundingBox = {
                            minLng: Math.min(...lngs),
                            maxLng: Math.max(...lngs),
                            minLat: Math.min(...lats),
                            maxLat: Math.max(...lats)
                        };
                        console.log('📍 DemoCreator: QC boundary loaded:', this.qcBoundingBox);
                    }
                }
            }
        } catch (error) {
            console.warn('⚠️ Could not load QC boundary GeoJSON:', error);
            this.qcBoundingBox = {
                minLng: 121.01,
                maxLng: 121.12,
                minLat: 14.58,
                maxLat: 14.78
            };
        }
    },
    
    /**
     * Check if a point is inside Quezon City boundary using ray casting algorithm
     */
    isPointInQC(lat, lng) {
        if (this.qcBoundingBox) {
            if (lng < this.qcBoundingBox.minLng || lng > this.qcBoundingBox.maxLng ||
                lat < this.qcBoundingBox.minLat || lat > this.qcBoundingBox.maxLat) {
                return false;
            }
        }
        
        if (!this.qcBoundary) {
            return true;
        }
        
        let inside = false;
        const polygon = this.qcBoundary;
        
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i][0], yi = polygon[i][1];
            const xj = polygon[j][0], yj = polygon[j][1];
            
            if (((yi > lat) !== (yj > lat)) &&
                (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi)) {
                inside = !inside;
            }
        }
        
        return inside;
    },
    
    /**
     * Generate a random location within Quezon City boundaries
     */
    getRandomLocationInQC() {
        const maxAttempts = 100;
        
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const lat = this.qcBoundingBox.minLat + Math.random() * (this.qcBoundingBox.maxLat - this.qcBoundingBox.minLat);
            const lng = this.qcBoundingBox.minLng + Math.random() * (this.qcBoundingBox.maxLng - this.qcBoundingBox.minLng);
            
            if (this.isPointInQC(lat, lng)) {
                return { lat, lng, name: `Random (${lat.toFixed(4)}, ${lng.toFixed(4)})` };
            }
        }
        
        // Fallback to preset
        const idx = Math.floor(Math.random() * this.presetLocations.length);
        return this.presetLocations[idx];
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
        
        // Disruption generation scope change
        document.getElementById('disruption-generation-scope')?.addEventListener('change', (e) => {
            this.disruptions.generationScope = e.target.value;
            this.updateScopeDescription();
        });
        
        // TAU generation scope change
        document.getElementById('tau-generation-scope')?.addEventListener('change', (e) => {
            this.sequence.tauGenerationScope = e.target.value;
            this.updateTauScopeDescription();
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

    openPanel(configToEdit = null) {
        const panel = document.getElementById('demo-creator-panel');
        if (panel) {
            panel.classList.remove('translate-x-full');
            
            // If editing a saved config, load it
            if (configToEdit) {
                this.loadConfig(configToEdit);
            } else {
                this.editingConfigId = null;
            }
            
            this.goToStep(1);
        }
    },

    loadConfig(config) {
        console.log('📝 Loading config for editing:', config.name);
        
        // Store editing state
        this.editingConfigId = config.id;
        
        // Load routes
        this.routes = config.routes ? config.routes.map(r => ({
            id: r.id || `route-${Date.now()}-${Math.random()}`,
            start: r.start,
            end: r.end
        })) : [];
        
        // Load disruptions
        if (config.disruptions) {
            this.disruptions = {
                mode: config.disruptions.mode || config.disruptionMode || 'none',
                randomFlowCount: config.disruptions.randomFlowCount || 5,
                randomIncidentCount: config.disruptions.randomIncidentCount || 3,
                severityMin: config.disruptions.severityMin || 0.3,
                severityMax: config.disruptions.severityMax || 0.9,
                customItems: config.disruptions.customItems || []
            };
        } else {
            // Handle legacy config format
            this.disruptions.mode = config.disruptionMode || 'none';
        }
        
        // Load sequence settings
        this.sequence.algorithm = config.algorithm || 'both';
        this.sequence.trials = config.trials || 1;
        this.sequence.stepDelay = config.stepDelay || 2000;
        
        // Load tau settings from first route if available
        if (config.routes && config.routes[0] && config.routes[0].tauValues) {
            const tauValues = config.routes[0].tauValues;
            if (tauValues.length === 1) {
                this.sequence.tauMode = 'fixed';
                this.sequence.tauFixed = tauValues[0];
            } else {
                this.sequence.tauMode = 'sequence';
                this.sequence.tauSequence = tauValues;
            }
        }
        
        // Update UI elements
        this.updateUIFromState();
        
        // Show routes on map
        this.clearAllRouteMarkers();
        if (this.routes.length > 0) {
            this.showRoutesOnMap(this.routes);
        }
        
        // Render lists
        this.renderRoutesList();
        this.renderDisruptionsList();
        
        // Set demo name
        const nameInput = document.getElementById('demo-v2-name');
        if (nameInput) {
            nameInput.value = config.name || '';
        }
        
        showUpdateToast(`Loaded: ${config.name}`, 'info');
    },

    updateUIFromState() {
        // Update algorithm select
        const algorithmSelect = document.getElementById('demo-algorithm-select');
        if (algorithmSelect) algorithmSelect.value = this.sequence.algorithm;
        
        // Update tau mode
        const tauMode = document.getElementById('demo-tau-mode');
        if (tauMode) {
            tauMode.value = this.sequence.tauMode;
            this.updateTauModeUI();
        }
        
        // Update tau values
        const tauFixed = document.getElementById('demo-tau-fixed');
        if (tauFixed) tauFixed.value = this.sequence.tauFixed;
        
        const tauSequence = document.getElementById('demo-tau-sequence');
        if (tauSequence && Array.isArray(this.sequence.tauSequence)) {
            tauSequence.value = this.sequence.tauSequence.join(', ');
        }
        
        // Update trials
        const trialsInput = document.getElementById('demo-trials-count');
        if (trialsInput) trialsInput.value = this.sequence.trials;
        
        // Update step delay
        const stepDelay = document.getElementById('demo-step-delay');
        if (stepDelay) stepDelay.value = this.sequence.stepDelay;
        
        // Update disruption mode
        const disruptionMode = document.getElementById('demo-disruption-mode');
        if (disruptionMode) {
            disruptionMode.value = this.disruptions.mode;
            this.updateDisruptionModeUI();
        }
        
        // Update disruption counts
        const flowCount = document.getElementById('random-flow-count');
        if (flowCount) flowCount.value = this.disruptions.randomFlowCount;
        
        const incidentCount = document.getElementById('random-incident-count');
        if (incidentCount) incidentCount.value = this.disruptions.randomIncidentCount;
        
        // Update severity sliders
        const severityMin = document.getElementById('random-severity-min');
        const severityMinDisplay = document.getElementById('random-severity-min-display');
        if (severityMin) {
            severityMin.value = this.disruptions.severityMin;
            if (severityMinDisplay) severityMinDisplay.textContent = this.disruptions.severityMin;
        }
        
        const severityMax = document.getElementById('random-severity-max');
        const severityMaxDisplay = document.getElementById('random-severity-max-display');
        if (severityMax) {
            severityMax.value = this.disruptions.severityMax;
            if (severityMaxDisplay) severityMaxDisplay.textContent = this.disruptions.severityMax;
        }
    },

    closePanel() {
        // Check if there are unsaved changes
        const hasChanges = (this.routes && this.routes.length > 0) || 
                          (this.disruptions.customItems && this.disruptions.customItems.length > 0) ||
                          this.disruptions.mode !== 'none';
        
        if (hasChanges) {
            if (!confirm('You have unsaved changes. Are you sure you want to exit and discard them?')) {
                return;
            }
        }
        
        const panel = document.getElementById('demo-creator-panel');
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
        this.clearDisruptionPreview(true);  // Also clear disruption preview polylines
        
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
        
        // Reset edit mode
        this.editingConfigId = null;
        
        // Reset running state
        this.isRunning = false;
        this.isPaused = false;
        this.currentProgress = {
            trial: 0,
            totalTrials: 1,
            route: 0,
            totalRoutes: 0,
            tauIndex: 0,
            totalTaus: 0,
            algorithm: '',
            currentTau: 0,
            status: '',
            lastResult: null
        };
        
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
        
        // Reset demo name
        const nameInput = document.getElementById('demo-v2-name');
        if (nameInput) nameInput.value = '';
        
        // Hide running step, show step 1
        document.getElementById('demo-v2-step-running')?.classList.add('hidden');
        
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
        // Hide all steps including running
        [1, 2, 3, 4, 'running'].forEach(s => {
            document.getElementById(`demo-v2-step-${s}`)?.classList.add('hidden');
        });
        
        // Show selected step
        document.getElementById(`demo-v2-step-${step}`)?.classList.remove('hidden');
        
        // Update step indicators (only for numbered steps)
        if (typeof step === 'number') {
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
        }
        
        // Update nav buttons
        const isRunning = step === 'running';
        document.getElementById('demo-v2-prev-btn')?.classList.toggle('hidden', step === 1 || isRunning);
        document.getElementById('demo-v2-next-btn')?.classList.toggle('hidden', step === 4 || isRunning);
        document.getElementById('demo-v2-run-btn')?.classList.toggle('hidden', step !== 4);
        document.getElementById('demo-v2-save-later-btn')?.classList.toggle('hidden', step !== 4);
        
        // Show/hide step indicators during running
        document.querySelector('.sticky.top-\\[68px\\]')?.classList.toggle('opacity-50', isRunning);
        
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
        
        const isStart = type === 'start';
        const iconColor = isStart ? 'green' : 'red';
        const icon = L.icon({
            iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${iconColor}.png`,
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        
        // Create modern popup matching osm-snapping style
        const popupContent = `
            <div class="p-3 min-w-[250px]">
                <div class="font-bold text-lg mb-2 ${isStart ? 'text-green-700' : 'text-red-700'} flex items-center">
                    <span class="mr-2">${isStart ? '🟢' : '🔴'}</span> ${isStart ? 'Start Location' : 'Destination'}
                </div>
                <div class="bg-gradient-to-r ${isStart ? 'from-green-50 to-emerald-50 border-green-200' : 'from-red-50 to-rose-50 border-red-200'} px-3 py-2 rounded-lg mb-2 border">
                    <div class="text-sm font-semibold text-slate-800">${location.name}</div>
                </div>
                <div class="space-y-1 text-sm">
                    ${location.type ? `<div class="flex items-center"><span class="font-semibold text-slate-600 w-16">Type:</span><span class="text-slate-700 capitalize">${location.type}</span></div>` : ''}
                    <div class="text-xs text-slate-400 font-mono bg-slate-50 px-2 py-1 rounded mt-2">${location.lat.toFixed(6)}, ${location.lng.toFixed(6)}</div>
                </div>
            </div>
        `;
        
        this.markers[markerId] = L.marker([location.lat, location.lng], { icon })
            .bindPopup(popupContent)
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

    /**
     * Calculate haversine distance between two points in kilometers
     */
    haversineDistance(lat1, lng1, lat2, lng2) {
        const R = 6371; // Earth's radius in km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLng/2) * Math.sin(dLng/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    },

    /**
     * Validate if a location is near a road
     */
    async validateLocationNearRoad(lat, lng, maxDistance = 100) {
        try {
            const response = await fetch('/api/demo/validate_location', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat, lng, max_distance: maxDistance })
            });
            const result = await response.json();
            return result;
        } catch (error) {
            console.error('Error validating location:', error);
            return { valid: false, error: error.message };
        }
    },

    /**
     * Get a random location in QC that is validated to be near a road
     * DEPRECATED: Use getRandomRoadPoints() for better performance
     */
    async getValidatedRandomLocation() {
        const maxAttempts = 20;
        
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            const location = this.getRandomLocationInQC();
            const validation = await this.validateLocationNearRoad(location.lat, location.lng);
            
            if (validation.valid) {
                // Use snapped coordinates for accuracy
                return {
                    lat: validation.snapped_lat,
                    lng: validation.snapped_lng,
                    name: validation.road_name || `Road (${location.lat.toFixed(4)}, ${location.lng.toFixed(4)})`
                };
            }
        }
        
        // Fallback: return unvalidated location
        return this.getRandomLocationInQC();
    },

    /**
     * Get multiple random road points in one efficient API call
     * Much faster than validateLocationNearRoad for each point
     */
    async getRandomRoadPoints(count) {
        try {
            const response = await fetch('/api/demo/random_road_points', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    count: count,
                    min_lat: this.qcBoundingBox?.minLat || 14.55,
                    max_lat: this.qcBoundingBox?.maxLat || 14.78,
                    min_lng: this.qcBoundingBox?.minLng || 120.98,
                    max_lng: this.qcBoundingBox?.maxLng || 121.12
                })
            });
            const result = await response.json();
            
            if (result.success && result.points) {
                return result.points.map(p => ({
                    lat: p.lat,
                    lng: p.lng,
                    name: p.road_name || `Road (${p.lat.toFixed(4)}, ${p.lng.toFixed(4)})`
                }));
            }
            return null;
        } catch (error) {
            console.error('Error getting random road points:', error);
            return null;
        }
    },

    async generateRandomRoutes() {
        const countInput = document.getElementById('demo-random-count');
        const minDistInput = document.getElementById('demo-random-min-dist');
        const maxDistInput = document.getElementById('demo-random-max-dist');
        const validateRoadsCheckbox = document.getElementById('demo-random-validate-roads');
        const generateBtn = document.getElementById('demo-generate-routes-btn');
        
        const count = parseInt(countInput?.value) || 3;
        const minDist = parseFloat(minDistInput?.value) || 1;
        const maxDist = parseFloat(maxDistInput?.value) || 10;
        const validateRoads = validateRoadsCheckbox?.checked !== false;
        
        console.log(`🗺️ Generating ${count} random routes (${minDist}-${maxDist} km, validate: ${validateRoads})`);
        
        // Disable button and show loading
        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="inline-block animate-spin mr-2">⏳</span> Generating...';
        }
        
        try {
            const newRoutes = [];
            
            if (validateRoads) {
                // FAST PATH: Get all road points in one API call
                // Request more points to allow for distance filtering and variety
                const neededPoints = Math.max(count * 10, 50);
                const roadPoints = await this.getRandomRoadPoints(neededPoints);
                
                if (roadPoints && roadPoints.length >= 2) {
                    let routesCreated = 0;
                    const usedPairs = new Set();
                    
                    // Try to create routes with proper distance constraints
                    for (let attempts = 0; attempts < neededPoints * 5 && routesCreated < count; attempts++) {
                        // Pick two random points
                        const startIdx = Math.floor(Math.random() * roadPoints.length);
                        let endIdx = Math.floor(Math.random() * roadPoints.length);
                        
                        // Ensure different points
                        while (endIdx === startIdx && roadPoints.length > 1) {
                            endIdx = Math.floor(Math.random() * roadPoints.length);
                        }
                        
                        // Skip if already used this pair
                        const pairKey = `${startIdx}-${endIdx}`;
                        if (usedPairs.has(pairKey)) continue;
                        usedPairs.add(pairKey);
                        
                        const start = roadPoints[startIdx];
                        const end = roadPoints[endIdx];
                        const distance = this.haversineDistance(start.lat, start.lng, end.lat, end.lng);
                        
                        // Check distance constraints
                        if (distance >= minDist && distance <= maxDist) {
                            const route = {
                                id: `route-${Date.now()}-${routesCreated}`,
                                start: { ...start },
                                end: { ...end },
                                distance: distance.toFixed(2)
                            };
                            this.routes.push(route);
                            newRoutes.push(route);
                            routesCreated++;
                            console.log(`   ✅ Route ${routesCreated}: ${distance.toFixed(2)} km (${start.name} → ${end.name})`);
                        }
                    }
                    
                    // If we couldn't find enough routes within constraints, relax them
                    if (routesCreated < count) {
                        console.warn(`   ⚠️ Only found ${routesCreated}/${count} routes within ${minDist}-${maxDist} km, relaxing constraints...`);
                        for (let i = routesCreated; i < count && i < roadPoints.length - 1; i++) {
                            const start = roadPoints[i * 2 % roadPoints.length];
                            const end = roadPoints[(i * 2 + 1) % roadPoints.length];
                            const distance = this.haversineDistance(start.lat, start.lng, end.lat, end.lng);
                            
                            const route = {
                                id: `route-${Date.now()}-${i}`,
                                start: { ...start },
                                end: { ...end },
                                distance: distance.toFixed(2)
                            };
                            this.routes.push(route);
                            newRoutes.push(route);
                        }
                    }
                } else {
                    // Fallback to old method if API fails
                    console.warn('Random road points API failed, using fallback');
                    for (let i = 0; i < count; i++) {
                        const start = this.getRandomLocationInQC();
                        const end = this.getRandomLocationInQC();
                        const distance = this.haversineDistance(start.lat, start.lng, end.lat, end.lng);
                        
                        const route = {
                            id: `route-${Date.now()}-${i}`,
                            start: { ...start },
                            end: { ...end },
                            distance: distance.toFixed(2)
                        };
                        this.routes.push(route);
                        newRoutes.push(route);
                    }
                }
            } else {
                // Non-validated: just use random QC coordinates
                for (let i = 0; i < count; i++) {
                    let start, end, distance;
                    let attempts = 0;
                    const maxAttempts = 50;
                    
                    do {
                        start = this.qcBoundary ? this.getRandomLocationInQC() : 
                                this.presetLocations[Math.floor(Math.random() * this.presetLocations.length)];
                        end = this.qcBoundary ? this.getRandomLocationInQC() : 
                              this.presetLocations[Math.floor(Math.random() * this.presetLocations.length)];
                        
                        distance = this.haversineDistance(start.lat, start.lng, end.lat, end.lng);
                        attempts++;
                    } while (attempts < maxAttempts && (distance < minDist || distance > maxDist));
                    
                    const route = {
                        id: `route-${Date.now()}-${i}`,
                        start: { ...start },
                        end: { ...end },
                        distance: distance.toFixed(2)
                    };
                    this.routes.push(route);
                    newRoutes.push(route);
                }
            }
            
            // Show markers on map for new routes
            this.showRoutesOnMap(newRoutes);
            
            this.renderRoutesList();
            showUpdateToast(`Added ${newRoutes.length} random routes${validateRoads ? ' (road-validated)' : ''}`, 'success');
            
        } catch (error) {
            console.error('Error generating routes:', error);
            showUpdateToast('Error generating routes: ' + error.message, 'error');
        } finally {
            // Re-enable button
            if (generateBtn) {
                generateBtn.disabled = false;
                generateBtn.innerHTML = 'Generate Routes';
            }
        }
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
        
        container.innerHTML = this.routes.map((route, index) => {
            // Calculate distance if not already present
            const distance = route.distance || this.haversineDistance(
                route.start.lat, route.start.lng, route.end.lat, route.end.lng
            ).toFixed(2);
            
            return `
            <div class="bg-white rounded-xl p-4 border border-gray-200 shadow-sm hover:shadow-md transition-all">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-purple-600 bg-purple-100 px-2 py-1 rounded">Route ${index + 1}</span>
                        <span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">${distance} km</span>
                    </div>
                    <button onclick="DemoCreator.removeRoute('${route.id}')" 
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
        `}).join('');
    },

    // ==========================================================================
    // DISRUPTION MANAGEMENT
    // ==========================================================================

    disruptionPreviewMarkers: [],
    previewedDisruptions: null,

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

    /**
     * Update scope description based on selection
     */
    updateScopeDescription() {
        const scope = document.getElementById('disruption-generation-scope')?.value || 'per-trial-route';
        const descriptions = {
            'all': 'One set of disruptions used for all routes across all trials',
            'per-trial': 'Each trial gets different disruptions (same across routes within trial)',
            'per-route': 'Each route gets different disruptions (same across trials)',
            'per-trial-route': 'Each route in each trial gets unique disruptions'
        };
        const descEl = document.getElementById('scope-description');
        if (descEl) {
            descEl.textContent = descriptions[scope] || '';
        }
    },

    updateTauScopeDescription() {
        const scope = document.getElementById('tau-generation-scope')?.value || 'all';
        const descriptions = {
            'all': 'All routes in all trials use the same TAU values in sequence',
            'per-trial': 'TAU sequence restarts for each trial',
            'per-route': 'TAU sequence restarts for each route',
            'per-trial-route': 'TAU sequence restarts for each trial AND route combination'
        };
        const descEl = document.getElementById('tau-scope-description');
        if (descEl) {
            descEl.textContent = descriptions[scope] || '';
        }
    },

    /**
     * Calculate how many disruption sets are needed based on scope
     */
    calculateRequiredSets() {
        const scope = document.getElementById('disruption-generation-scope')?.value || 'per-trial-route';
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const routeCount = this.routes.length || 1;
        
        switch (scope) {
            case 'all':
                return 1;
            case 'per-trial':
                return trials;
            case 'per-route':
                return routeCount;
            case 'per-trial-route':
                return trials * routeCount;
            default:
                return 1;
        }
    },

    /**
     * Generate set key based on scope, trial index, and route index
     */
    getSetKey(scope, trialIndex, routeIndex) {
        switch (scope) {
            case 'all':
                return 'set_all';
            case 'per-trial':
                return `set_trial_${trialIndex}`;
            case 'per-route':
                return `set_route_${routeIndex}`;
            case 'per-trial-route':
                return `set_trial_${trialIndex}_route_${routeIndex}`;
            default:
                return 'set_all';
        }
    },

    /**
     * Generate a descriptive label for a set key
     */
    getSetLabel(setKey) {
        if (setKey === 'set_all') return 'All (Shared)';
        if (setKey.startsWith('set_trial_') && !setKey.includes('route')) {
            const trial = setKey.replace('set_trial_', '');
            return `Trial ${parseInt(trial) + 1}`;
        }
        if (setKey.startsWith('set_route_') && !setKey.includes('trial')) {
            const route = setKey.replace('set_route_', '');
            return `Route ${parseInt(route) + 1}`;
        }
        if (setKey.includes('trial') && setKey.includes('route')) {
            const match = setKey.match(/set_trial_(\d+)_route_(\d+)/);
            if (match) {
                return `Trial ${parseInt(match[1]) + 1}, Route ${parseInt(match[2]) + 1}`;
            }
        }
        return setKey;
    },

    /**
     * Preview disruptions on the map - generates all sets based on scope
     */
    async previewDisruptions() {
        const flowCount = parseInt(document.getElementById('random-flow-count')?.value) || 5;
        const incidentCount = parseInt(document.getElementById('random-incident-count')?.value) || 3;
        const severityMin = parseFloat(document.getElementById('random-severity-min')?.value) || 0;
        const severityMax = parseFloat(document.getElementById('random-severity-max')?.value) || 1;
        const scope = document.getElementById('disruption-generation-scope')?.value || 'per-trial-route';
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const routeCount = this.routes.length || 1;
        
        const btn = document.getElementById('preview-disruptions-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="inline-block animate-spin">⏳</span> Generating...';
        }
        
        try {
            // Calculate required sets
            const requiredSets = this.calculateRequiredSets();
            console.log(`📦 Generating ${requiredSets} disruption sets for scope: ${scope}`);
            
            // Clear previous sets
            this.disruptions.disruptionSets = {};
            
            // Generate all required sets
            const setKeys = [];
            
            if (scope === 'all') {
                setKeys.push('set_all');
            } else if (scope === 'per-trial') {
                for (let t = 0; t < trials; t++) {
                    setKeys.push(`set_trial_${t}`);
                }
            } else if (scope === 'per-route') {
                for (let r = 0; r < routeCount; r++) {
                    setKeys.push(`set_route_${r}`);
                }
            } else if (scope === 'per-trial-route') {
                for (let t = 0; t < trials; t++) {
                    for (let r = 0; r < routeCount; r++) {
                        setKeys.push(`set_trial_${t}_route_${r}`);
                    }
                }
            }
            
            // Generate each set
            let generatedCount = 0;
            for (const setKey of setKeys) {
                const response = await fetch('/api/demo/random_edges', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        flow_count: flowCount,
                        incident_count: incidentCount,
                        severity_min: severityMin,
                        severity_max: severityMax
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    this.disruptions.disruptionSets[setKey] = {
                        flow: result.flow || [],
                        incidents: result.incidents || [],
                        flowCount: result.flow_count,
                        incidentCount: result.incident_count
                    };
                    generatedCount++;
                }
                
                // Update progress
                if (btn) {
                    btn.innerHTML = `<span class="inline-block animate-spin">⏳</span> Set ${generatedCount}/${setKeys.length}...`;
                }
            }
            
            // Show the first set on map
            const firstKey = setKeys[0];
            if (this.disruptions.disruptionSets[firstKey]) {
                this.currentPreviewSet = firstKey;
                this.displayDisruptionsOnMap(this.disruptions.disruptionSets[firstKey]);
            }
            
            // Show sets list UI
            this.showDisruptionSetsPreview();
            
            showUpdateToast(`Generated ${generatedCount} disruption sets`, 'success');
            
        } catch (error) {
            console.error('Error previewing disruptions:', error);
            showUpdateToast('Error generating disruptions', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                    </svg>
                    Preview Disruptions on Map
                `;
            }
        }
    },

    currentPreviewSet: null,

    /**
     * Show list of all disruption sets for preview/selection
     */
    showDisruptionSetsPreview() {
        const panel = document.getElementById('disruption-preview-panel');
        const content = document.getElementById('disruption-preview-content');
        
        if (!panel || !content) return;
        
        panel.classList.remove('hidden');
        
        const sets = this.disruptions.disruptionSets;
        const setKeys = Object.keys(sets);
        
        if (setKeys.length === 0) {
            content.innerHTML = '<p class="text-gray-500 text-sm">No disruptions generated</p>';
            return;
        }
        
        let html = `
            <div class="mb-3">
                <div class="text-xs font-semibold text-purple-600 mb-2">📦 Disruption Sets (${setKeys.length})</div>
                <div class="flex flex-wrap gap-1">
                    ${setKeys.map(key => `
                        <button onclick="DemoCreator.selectDisruptionSet('${key}')"
                                class="px-2 py-1 text-xs rounded-lg transition-colors ${this.currentPreviewSet === key ? 
                                    'bg-purple-600 text-white' : 'bg-purple-100 text-purple-700 hover:bg-purple-200'}">
                            ${this.getSetLabel(key)}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
        
        // Show current set details
        if (this.currentPreviewSet && sets[this.currentPreviewSet]) {
            const currentSet = sets[this.currentPreviewSet];
            html += this.renderDisruptionSetDetails(this.currentPreviewSet, currentSet);
        }
        
        content.innerHTML = html;
    },

    /**
     * Render detailed view of a disruption set with delete buttons
     */
    renderDisruptionSetDetails(setKey, setData) {
        let html = `<div class="border-t border-gray-200 pt-2 mt-2">`;
        
        // Flow disruptions
        if (setData.flow && setData.flow.length > 0) {
            html += '<div class="text-xs font-semibold text-orange-600 mb-1">🚦 Traffic Flow</div>';
            html += setData.flow.map((f, i) => `
                <div class="flex items-center justify-between bg-orange-50 rounded px-2 py-1 text-xs mb-1 group cursor-pointer hover:bg-orange-100"
                     onclick="DemoCreator.focusDisruption('flow', ${i}, '${setKey}')">
                    <span class="truncate flex-1">${f.road_name || 'Unknown'}</span>
                    <span class="text-orange-600 font-semibold ml-2">Jam: ${(f.jam_factor || 0).toFixed(1)}</span>
                    <button onclick="event.stopPropagation(); DemoCreator.deleteDisruption('flow', ${i}, '${setKey}')"
                            class="ml-2 text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-opacity">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            `).join('');
        }
        
        // Incidents
        if (setData.incidents && setData.incidents.length > 0) {
            html += '<div class="text-xs font-semibold text-red-600 mb-1 mt-2">🚨 Incidents</div>';
            html += setData.incidents.map((inc, i) => `
                <div class="flex items-center justify-between bg-red-50 rounded px-2 py-1 text-xs mb-1 group cursor-pointer hover:bg-red-100"
                     onclick="DemoCreator.focusDisruption('incident', ${i}, '${setKey}')">
                    <span class="truncate flex-1">${inc.road_name || 'Unknown'}</span>
                    <span class="text-red-600 font-semibold ml-2">${inc.type || 'Incident'}</span>
                    <button onclick="event.stopPropagation(); DemoCreator.deleteDisruption('incident', ${i}, '${setKey}')"
                            class="ml-2 text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-opacity">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            `).join('');
        }
        
        if ((!setData.flow || setData.flow.length === 0) && (!setData.incidents || setData.incidents.length === 0)) {
            html += '<p class="text-gray-500 text-xs">No disruptions in this set</p>';
        }
        
        html += '</div>';
        return html;
    },

    /**
     * Select a disruption set to view
     */
    selectDisruptionSet(setKey) {
        if (!this.disruptions.disruptionSets[setKey]) return;
        
        this.currentPreviewSet = setKey;
        this.displayDisruptionsOnMap(this.disruptions.disruptionSets[setKey]);
        this.showDisruptionSetsPreview();
    },

    /**
     * Focus map on a specific disruption
     */
    focusDisruption(type, index, setKey) {
        const set = this.disruptions.disruptionSets[setKey];
        if (!set) return;
        
        const items = type === 'flow' ? set.flow : set.incidents;
        if (!items || !items[index]) return;
        
        const item = items[index];
        const lat = (parseFloat(item.source_lat) + parseFloat(item.target_lat)) / 2;
        const lng = (parseFloat(item.source_lon || item.source_lng) + parseFloat(item.target_lon || item.target_lng)) / 2;
        
        if (map && !isNaN(lat) && !isNaN(lng)) {
            map.setView([lat, lng], 16);
            
            // Flash the polyline if it exists
            const markers = this.disruptionPreviewMarkers;
            if (markers[index]) {
                const original = markers[index].options;
                markers[index].setStyle({ weight: 10, opacity: 1 });
                setTimeout(() => {
                    markers[index].setStyle({ weight: original.weight, opacity: original.opacity });
                }, 1000);
            }
        }
    },

    /**
     * Delete a specific disruption from a set
     */
    deleteDisruption(type, index, setKey) {
        const set = this.disruptions.disruptionSets[setKey];
        if (!set) return;
        
        if (type === 'flow' && set.flow) {
            set.flow.splice(index, 1);
        } else if (type === 'incident' && set.incidents) {
            set.incidents.splice(index, 1);
        }
        
        // Refresh display
        this.displayDisruptionsOnMap(set);
        this.showDisruptionSetsPreview();
        showUpdateToast('Disruption removed', 'info');
    },

    /**
     * Display disruption preview on the map using polylines (matching traffic overlay style)
     * Uses actual road geometry from OSM graph when available
     */
    displayDisruptionsOnMap(data) {
        // Clear existing preview markers
        this.clearDisruptionPreview(false);
        
        // Color scheme matching traffic-visualization.js
        const flowColors = {
            heavy: { color: '#ef4444', weight: 6, opacity: 0.85 },   // Red - Heavy traffic
            medium: { color: '#f59e0b', weight: 5, opacity: 0.75 },  // Amber - Medium traffic
            light: { color: '#10b981', weight: 4, opacity: 0.65 }    // Green - Light traffic
        };
        
        const incidentColors = {
            critical: { color: '#dc2626', weight: 7, opacity: 0.9 },  // Dark red
            major: { color: '#ef4444', weight: 6, opacity: 0.85 },    // Red
            minor: { color: '#f59e0b', weight: 5, opacity: 0.75 }     // Amber
        };
        
        const incidentIcons = {
            'accident': '🚗',
            'construction': '🏗️',
            'roadClosure': '🚧',
            'hazard': '⚠️',
            'Road Closure': '🚧',
            'Accident': '🚗',
            'Construction': '🏗️',
            'default': '📍'
        };
        
        // Add flow disruption polylines
        if (data.flow) {
            data.flow.forEach((f, i) => {
                // Use actual geometry if available, otherwise fall back to source/target
                let geometry;
                if (f.geometry && Array.isArray(f.geometry) && f.geometry.length >= 2) {
                    // Use actual road geometry from OSM graph
                    geometry = f.geometry.map(coord => {
                        if (Array.isArray(coord)) {
                            return [parseFloat(coord[0]), parseFloat(coord[1])];
                        }
                        return null;
                    }).filter(c => c !== null);
                }
                
                // Fallback to simple line if no geometry
                if (!geometry || geometry.length < 2) {
                    geometry = [
                        [parseFloat(f.source_lat), parseFloat(f.source_lon)],
                        [parseFloat(f.target_lat), parseFloat(f.target_lon)]
                    ];
                }
                
                // Determine severity based on jam_factor
                const jamFactor = parseFloat(f.jam_factor) || 0;
                let style;
                let severity = f.severity || (jamFactor >= 6.0 ? 'Heavy' : jamFactor >= 3.0 ? 'Medium' : 'Light');
                
                switch (severity) {
                    case 'Heavy':
                        style = flowColors.heavy;
                        break;
                    case 'Medium':
                        style = flowColors.medium;
                        break;
                    default:
                        style = flowColors.light;
                }
                
                const polyline = L.polyline(geometry, {
                    color: style.color,
                    weight: style.weight,
                    opacity: style.opacity,
                    className: 'disruption-preview-flow'
                });
                
                // Create popup matching traffic overlay style (use PopupStyles if available)
                const popup = typeof PopupStyles !== 'undefined' ? 
                    PopupStyles.createTrafficOverlayPopup({
                        road_name: f.road_name,
                        highway_type: f.highway_type,
                        severity: severity,
                        jam_factor: jamFactor,
                        is_closed: false,
                        description: `Traffic congestion (Jam Factor: ${jamFactor.toFixed(1)})`
                    }) :
                    `<div class="popup-content">
                        <b>🚦 Traffic Congestion</b><br>
                        <b>Road:</b> ${f.road_name || 'Unknown Road'}<br>
                        <b>Severity:</b> <span style="color: ${style.color}">${severity}</span><br>
                        <b>Jam Factor:</b> ${jamFactor.toFixed(1)} / 10
                    </div>`;
                
                polyline.bindPopup(popup);
                
                // Hover effects like traffic overlay
                polyline.on('mouseover', function() {
                    this.setStyle({ weight: style.weight + 2, opacity: Math.min(style.opacity + 0.2, 1) });
                });
                polyline.on('mouseout', function() {
                    this.setStyle({ weight: style.weight, opacity: style.opacity });
                });
                
                polyline.addTo(map);
                this.disruptionPreviewMarkers.push(polyline);
            });
        }
        
        // Add incident CIRCLE MARKERS (matching Active Incidents style, NOT polylines)
        if (data.incidents) {
            data.incidents.forEach((inc, i) => {
                // Calculate midpoint for circle marker position
                const midLat = (parseFloat(inc.source_lat) + parseFloat(inc.target_lat)) / 2;
                const midLon = (parseFloat(inc.source_lon) + parseFloat(inc.target_lon)) / 2;
                
                // Determine color based on criticality
                const criticality = (inc.criticality || 'minor').toLowerCase();
                let fillColor = '#f59e0b'; // amber - default
                
                if (criticality === 'critical') {
                    fillColor = '#dc2626'; // dark red
                } else if (criticality === 'major') {
                    fillColor = '#ef4444'; // red
                } else if (criticality === 'minor') {
                    fillColor = '#f59e0b'; // amber
                }
                
                // If road is closed, use black
                if (inc.road_closed) {
                    fillColor = '#000000';
                }
                
                // Get icon for incident type
                const incidentIcons = {
                    'accident': '🚗',
                    'construction': '🏗️',
                    'roadClosure': '🚧',
                    'hazard': '⚠️',
                    'Road Closure': '🚧',
                    'Accident': '🚗',
                    'Construction': '🏗️',
                    'default': '📍'
                };
                const icon = incidentIcons[inc.type] || incidentIcons.default;
                
                // Create circle marker like Active Incidents
                const marker = L.circleMarker([midLat, midLon], {
                    radius: 10,
                    fillColor: fillColor,
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.85
                });
                
                // Create popup matching incident style
                const popup = typeof PopupStyles !== 'undefined' ?
                    PopupStyles.createIncidentPopup({
                        road_name: inc.road_name || 'Unknown Road',
                        incident_type: inc.type || 'Incident',
                        incident_criticality: inc.criticality || 'Minor',
                        incident_road_closed: inc.road_closed || false,
                        incident_description: inc.description || `Demo ${inc.type} incident`,
                        highway_type: inc.highway_type || ''
                    }) :
                    `<div class="p-3 min-w-[220px]">
                        <div class="font-bold text-lg mb-2">${icon} ${inc.type || 'Incident'}</div>
                        <div class="text-sm text-slate-600 mb-1">📍 ${inc.road_name || 'Unknown Road'}</div>
                        <div class="text-sm"><b>Criticality:</b> <span style="color: ${fillColor}">${inc.criticality || 'Unknown'}</span></div>
                        ${inc.road_closed ? '<div class="text-sm font-bold text-red-600 mt-1">🚫 Road Closed</div>' : ''}
                    </div>`;
                
                marker.bindPopup(popup);
                
                // Hover effects
                marker.on('mouseover', function() {
                    this.setStyle({ radius: 12, weight: 3 });
                });
                marker.on('mouseout', function() {
                    this.setStyle({ radius: 10, weight: 2 });
                });
                
                marker.addTo(map);
                this.disruptionPreviewMarkers.push(marker);
            });
        }
        
        // Fit map to show all markers if we have some
        if (this.disruptionPreviewMarkers.length > 0) {
            const group = L.featureGroup(this.disruptionPreviewMarkers);
            map.fitBounds(group.getBounds().pad(0.1));
        }
    },

    /**
     * Clear disruption preview from map
     */
    clearDisruptionPreview(hidePanel = true) {
        // Remove markers from map
        this.disruptionPreviewMarkers.forEach(marker => {
            if (map.hasLayer(marker)) {
                map.removeLayer(marker);
            }
        });
        this.disruptionPreviewMarkers = [];
        
        // Hide panel if requested
        if (hidePanel) {
            document.getElementById('disruption-preview-panel')?.classList.add('hidden');
            this.previewedDisruptions = null;
        }
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
                <button onclick="DemoCreator.removeDisruption('${d.id}')" 
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

    async saveForLater() {
        // Read severity range values
        this.disruptions.severityMin = parseFloat(document.getElementById('random-severity-min')?.value) || 0;
        this.disruptions.severityMax = parseFloat(document.getElementById('random-severity-max')?.value) || 1;
        
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        
        // Read TAU generation scope
        this.sequence.tauGenerationScope = document.getElementById('tau-generation-scope')?.value || 'all';
        
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
            sequence: { ...this.sequence },
            stepDelay: parseInt(document.getElementById('demo-step-delay')?.value) || 1000
        };
        
        // If editing, update the config; otherwise save new
        if (this.editingConfigId) {
            config.id = this.editingConfigId;
            await DemoRunner.updateConfig(config);
            showUpdateToast('Demo configuration updated!', 'success');
        } else {
            await DemoRunner.saveConfig(config);
            showUpdateToast('Demo configuration saved for later!', 'success');
        }
        
        // Close the panel after saving
        const panel = document.getElementById('demo-creator-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
        }
        this.resetAll();
    },

    async saveAndRun() {
        // Read severity range values
        this.disruptions.severityMin = parseFloat(document.getElementById('random-severity-min')?.value) || 0;
        this.disruptions.severityMax = parseFloat(document.getElementById('random-severity-max')?.value) || 1;
        
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        
        // Read TAU generation scope
        this.sequence.tauGenerationScope = document.getElementById('tau-generation-scope')?.value || 'all';
        
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
            sequence: { ...this.sequence },
            stepDelay: parseInt(document.getElementById('demo-step-delay')?.value) || 1000
        };
        
        // If editing, update the config; otherwise save new
        if (document.getElementById('demo-v2-save-config')?.checked) {
            if (this.editingConfigId) {
                config.id = this.editingConfigId;
                await DemoRunner.updateConfig(config);
            } else {
                await DemoRunner.saveConfig(config);
            }
        }
        
        // Run demo with detailed progress in this panel
        await this.runDemoWithProgress(config);
    },

    async runDemoWithProgress(config) {
        if (this.isRunning) {
            showUpdateToast('A demo is already running', 'warning');
            return;
        }

        // Clear all visual markers before running the demo
        this.clearPreviewMarkers();
        this.clearAllRouteMarkers();
        this.clearAllDisruptionMarkers();

        this.isRunning = true;
        this.isPaused = false;
        
        const trials = config.trials || 1;
        const routes = config.routes || [];
        
        // Initialize progress
        this.currentProgress = {
            trial: 0,
            totalTrials: trials,
            route: 0,
            totalRoutes: routes.length,
            tauIndex: 0,
            totalTaus: 0,
            algorithm: '',
            currentTau: 0,
            status: 'Initializing...',
            lastResult: null,
            results: []
        };
        
        console.log('🎬 Starting demo with detailed progress:', config.name);
        showUpdateToast(`🎬 Starting: ${config.name}`, 'info');
        
        // Show running step
        this.goToStep('running');
        this.updateProgressDisplay();

        try {
            // Reset map
            await this.resetMap();
            
            // Run for each trial
            for (let trial = 0; trial < trials; trial++) {
                if (!this.isRunning) break;
                
                this.currentProgress.trial = trial + 1;
                
                // Process each route
                for (let i = 0; i < routes.length; i++) {
                    if (!this.isRunning) break;
                    while (this.isPaused) {
                        await this.delay(100);
                    }
                    
                    const route = routes[i];
                    this.currentProgress.route = i + 1;
                    this.currentProgress.status = `Setting up route ${i + 1}...`;
                    this.updateProgressDisplay();
                    
                    await this.processRouteWithProgress(route, config, trial);
                    await this.delay(config.stepDelay || 2000);
                }
            }

            if (this.isRunning) {
                this.currentProgress.status = '✅ Demo completed!';
                this.updateProgressDisplay();
                showUpdateToast('✅ Demo completed!', 'success');
            }

        } catch (error) {
            console.error('Demo error:', error);
            this.currentProgress.status = `❌ Error: ${error.message}`;
            this.updateProgressDisplay();
            showUpdateToast('Demo failed: ' + error.message, 'error');
        } finally {
            this.isRunning = false;
        }
    },

    async processRouteWithProgress(route, config, trialIndex) {
        // Step 0: Set start location
        this.currentProgress.setupStep = 0;
        this.currentProgress.status = `Setting start: ${route.start.name}`;
        this.updateProgressDisplay();
        
        if (typeof handleOSMStartLocationPin === 'function') {
            await handleOSMStartLocationPin(route.start.lat, route.start.lng);
        }
        await this.delay(500);

        // Step 1: Set destination
        this.currentProgress.setupStep = 1;
        this.currentProgress.status = `Setting destination: ${route.end.name}`;
        this.updateProgressDisplay();
        
        if (typeof handleOSMDestLocationPin === 'function') {
            await handleOSMDestLocationPin(route.end.lat, route.end.lng);
        }
        await this.delay(500);

        // Step 2: Configure disruptions
        this.currentProgress.setupStep = 2;
        this.currentProgress.status = `Configuring disruptions...`;
        this.updateProgressDisplay();
        
        // Get algorithms to test
        const algorithmToTest = config.algorithm || 'hc2l';
        const algorithms = algorithmToTest === 'both' ? ['hc2l', 'dhl'] : [algorithmToTest];

        // Set disruption mode
        const disruption = config.disruptions?.mode || config.disruptionMode || 'none';
        let datasetValue = 'none';
        if (disruption.includes('flow') || disruption === 'random-both' || disruption === 'both') {
            datasetValue = 'both';
        } else if (disruption.includes('incident')) {
            datasetValue = 'incidents';
        }
        
        const disruptionRadio = document.querySelector(`input[name="dataset"][value="${datasetValue}"]`);
        if (disruptionRadio) {
            disruptionRadio.click();
        }

        // Apply disruption visualization
        await this.applyDisruptionVisualization(disruption, config.disruptions?.customItems);

        this.currentProgress.setupStep = 3;
        this.updateProgressDisplay();

        await this.delay(300);

        // Test each tau value
        const tauValues = route.tauValues || [0.5];
        this.currentProgress.totalTaus = tauValues.length;
        
        for (let tauIdx = 0; tauIdx < tauValues.length; tauIdx++) {
            if (!this.isRunning) break;
            while (this.isPaused) {
                await this.delay(100);
            }
            
            const tau = tauValues[tauIdx];
            this.currentProgress.tauIndex = tauIdx + 1;
            this.currentProgress.currentTau = tau;

            // Test each algorithm with this tau
            for (const algo of algorithms) {
                if (!this.isRunning) break;
                while (this.isPaused) {
                    await this.delay(100);
                }

                // Sub-step 0: Setting algorithm and tau
                this.currentProgress.subStep = 0;
                this.currentProgress.algorithm = algo.toUpperCase();
                this.currentProgress.status = `Setting ${algo.toUpperCase()} with τ = ${tau.toFixed(2)}`;
                this.updateProgressDisplay();
                
                // Set algorithm
                document.querySelector(`input[name="algorithm"][value="${algo}"]`)?.click();
                
                // Set tau
                const thresholdInput = document.getElementById('threshold-input');
                if (thresholdInput) {
                    thresholdInput.value = tau;
                    thresholdInput.dispatchEvent(new Event('input'));
                }

                await this.delay(200);

                // Sub-step 1: Computing route
                this.currentProgress.subStep = 1;
                this.currentProgress.status = `Computing route (${algo.toUpperCase()}, τ = ${tau.toFixed(2)})...`;
                this.updateProgressDisplay();
                
                if (typeof computeRouteBasedOnSelection === 'function') {
                    await computeRouteBasedOnSelection();
                }

                // Sub-step 2: Waiting for result
                this.currentProgress.subStep = 2;
                this.currentProgress.status = `Waiting for result...`;
                this.updateProgressDisplay();
                
                await this.delay(config.stepDelay || 2000);
                
                // Sub-step 3: Capturing result
                this.currentProgress.subStep = 3;
                const result = this.captureCurrentResult(algo, tau, route, trialIndex);
                if (result) {
                    this.currentProgress.lastResult = result;
                    this.currentProgress.results.push(result);
                }
                
                this.updateProgressDisplay();

                await this.delay(config.stepDelay || 2000);
            }
        }
    },

    captureCurrentResult(algorithm, tau, route, trialIndex) {
        try {
            const result = {
                trial: trialIndex + 1,
                route: `${route.start.name} → ${route.end.name}`,
                algorithm: algorithm.toUpperCase(),
                tau: tau,
                timestamp: new Date().toISOString(),
                metrics: {}
            };

            // Read from Algorithm Metrics panel elements
            const getMetricValue = (id) => {
                const el = document.getElementById(id);
                if (el) {
                    const text = el.textContent.trim();
                    return text !== '--' ? text : null;
                }
                return null;
            };

            // Algorithm Metrics panel elements
            result.metrics.algorithm = getMetricValue('metrics-algorithm');
            result.metrics.queryTime = getMetricValue('metrics-query-time');
            result.metrics.baselineEta = getMetricValue('metrics-baseline-eta');
            result.metrics.actualEta = getMetricValue('metrics-actual-eta');
            result.metrics.timeImpact = getMetricValue('metrics-time-impact');
            result.metrics.disruptedEdges = getMetricValue('metrics-disrupted-edges');
            result.metrics.distance = getMetricValue('metrics-distance');
            result.metrics.pathLength = getMetricValue('metrics-path-length');
            result.metrics.edgeCount = getMetricValue('metrics-edge-count');
            result.metrics.labelingTime = getMetricValue('metrics-labeling-time');
            result.metrics.labelingSize = getMetricValue('metrics-labeling-size');
            result.metrics.calculatedDistance = getMetricValue('metrics-calculated-distance');

            // Also try main route display elements
            const routeDistance = document.getElementById('route-distance')?.textContent?.trim();
            const routeEta = document.getElementById('route-eta')?.textContent?.trim();
            if (routeDistance && routeDistance !== '--') {
                result.metrics.displayDistance = routeDistance;
            }
            if (routeEta && routeEta !== '--') {
                result.metrics.displayEta = routeEta;
            }

            console.log('📊 Captured result metrics:', result.metrics);
            return result;
        } catch (e) {
            console.warn('Could not capture result metrics:', e);
            return null;
        }
    },

    updateProgressDisplay() {
        const container = document.getElementById('demo-v2-progress-display');
        if (!container) return;

        const p = this.currentProgress;
        const overallProgress = this.calculateOverallProgress();

        // Helper function to render metric if exists
        const renderMetric = (label, value, colorClass = 'text-gray-800') => {
            if (!value) return '';
            return `<div class="flex justify-between py-1 px-2 bg-white rounded border border-gray-100">
                <span class="text-gray-500 text-xs">${label}:</span>
                <span class="font-semibold text-xs ${colorClass}">${value}</span>
            </div>`;
        };

        container.innerHTML = `
            <div class="space-y-3">
                <!-- Overall Progress - More Precise -->
                <div class="bg-white rounded-xl p-3 border border-gray-200 shadow-sm">
                    <div class="flex justify-between mb-1">
                        <span class="text-xs font-semibold text-gray-600">Overall Progress</span>
                        <span class="text-xs font-bold text-purple-600">${overallProgress.toFixed(1)}%</span>
                    </div>
                    <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div class="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500 ease-out" 
                             style="width: ${overallProgress}%"></div>
                    </div>
                    <div class="text-xs text-gray-500 mt-1 text-center">${p.status || 'Initializing...'}</div>
                </div>

                <!-- Detailed Progress Grid - Compact -->
                <div class="grid grid-cols-4 gap-2">
                    <div class="bg-amber-50 rounded-lg p-2 border border-amber-200 text-center">
                        <div class="text-[10px] text-amber-600 uppercase">Trial</div>
                        <div class="text-sm font-bold text-amber-800">${p.trial}/${p.totalTrials}</div>
                    </div>
                    <div class="bg-emerald-50 rounded-lg p-2 border border-emerald-200 text-center">
                        <div class="text-[10px] text-emerald-600 uppercase">Route</div>
                        <div class="text-sm font-bold text-emerald-800">${p.route}/${p.totalRoutes}</div>
                    </div>
                    <div class="bg-violet-50 rounded-lg p-2 border border-violet-200 text-center">
                        <div class="text-[10px] text-violet-600 uppercase">Algo</div>
                        <div class="text-sm font-bold text-violet-800">${p.algorithm || '-'}</div>
                    </div>
                    <div class="bg-rose-50 rounded-lg p-2 border border-rose-200 text-center">
                        <div class="text-[10px] text-rose-600 uppercase">τ</div>
                        <div class="text-sm font-bold text-rose-800">${p.currentTau ? p.currentTau.toFixed(2) : '-'}</div>
                    </div>
                </div>

                <!-- Last Result - Full Algorithm Metrics -->
                ${p.lastResult ? `
                <div class="bg-gradient-to-br from-gray-50 to-slate-50 rounded-xl p-3 border border-gray-200">
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="text-xs font-bold text-gray-700">📊 Last Result</h4>
                        <span class="text-[10px] text-gray-500">${p.lastResult.route}</span>
                    </div>
                    
                    <!-- Key Metrics Grid -->
                    <div class="grid grid-cols-2 gap-1 mb-2">
                        ${renderMetric('Algorithm', p.lastResult.algorithm, 'text-blue-700')}
                        ${renderMetric('τ Value', p.lastResult.tau.toFixed(2), 'text-rose-700')}
                        ${renderMetric('Query Time', p.lastResult.metrics.queryTime, 'text-purple-700')}
                        ${renderMetric('Distance', p.lastResult.metrics.displayDistance || p.lastResult.metrics.calculatedDistance || p.lastResult.metrics.distance, 'text-green-700')}
                        ${renderMetric('Baseline ETA', p.lastResult.metrics.baselineEta, 'text-emerald-700')}
                        ${renderMetric('Actual ETA', p.lastResult.metrics.displayEta || p.lastResult.metrics.actualEta, 'text-orange-700')}
                        ${renderMetric('Time Impact', p.lastResult.metrics.timeImpact, 'text-red-700')}
                        ${renderMetric('Disrupted Edges', p.lastResult.metrics.disruptedEdges, 'text-indigo-700')}
                        ${renderMetric('Path Length', p.lastResult.metrics.pathLength, 'text-cyan-700')}
                        ${renderMetric('Edge Count', p.lastResult.metrics.edgeCount, 'text-teal-700')}
                    </div>
                </div>
                ` : ''}

                <!-- Results History - All Results -->
                ${p.results && p.results.length > 0 ? `
                <div class="bg-white rounded-xl p-3 border border-gray-200">
                    <h4 class="text-xs font-bold text-gray-700 mb-2">📜 Results History (${p.results.length} total)</h4>
                    <div class="space-y-1 max-h-48 overflow-y-auto">
                        ${p.results.slice().reverse().map((r, i) => `
                            <div class="text-xs p-2 ${i === 0 ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-100'} rounded border">
                                <div class="flex justify-between items-center">
                                    <span class="font-semibold text-gray-800">${r.algorithm} τ=${r.tau.toFixed(2)}</span>
                                    <span class="text-gray-500">T${r.trial}</span>
                                </div>
                                <div class="text-gray-600 truncate text-[10px]">${r.route}</div>
                                <div class="flex gap-2 mt-1 text-[10px]">
                                    ${r.metrics.displayDistance || r.metrics.calculatedDistance || r.metrics.distance ? `<span class="text-green-600">📏 ${r.metrics.displayDistance || r.metrics.calculatedDistance || r.metrics.distance}</span>` : ''}
                                    ${r.metrics.displayEta || r.metrics.actualEta ? `<span class="text-orange-600">⏱ ${r.metrics.displayEta || r.metrics.actualEta}</span>` : ''}
                                    ${r.metrics.queryTime ? `<span class="text-purple-600">⚡ ${r.metrics.queryTime}</span>` : ''}
                                    ${r.metrics.pathLength ? `<span class="text-cyan-600">📍 ${r.metrics.pathLength}</span>` : ''}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    },

    calculateOverallProgress() {
        const p = this.currentProgress;
        if (p.totalTrials === 0 || p.totalRoutes === 0) return 0;
        
        // Each route has multiple sub-steps
        const totalTaus = p.totalTaus || 1;
        const stepsPerRoute = 3 + (totalTaus * 3);
        const totalSteps = p.totalTrials * p.totalRoutes * stepsPerRoute;
        
        const completedTrials = (p.trial - 1) * p.totalRoutes * stepsPerRoute;
        const completedRoutes = (p.route - 1) * stepsPerRoute;
        const completedTauSteps = (p.tauIndex - 1) * 3 + (p.subStep || 0);
        const routeProgress = p.setupStep || 0;
        
        const completedSteps = completedTrials + completedRoutes + routeProgress + completedTauSteps;
        
        return Math.min(100, (completedSteps / totalSteps) * 100);
    },

    // ==========================================================================
    // CUSTOM DISRUPTION GENERATION (NOT FROM HERE API)
    // ==========================================================================

    // Store generated disruptions for the current demo
    generatedDisruptions: {
        incidents: [],
        flowSegments: []
    },

    // Generate random incidents within Quezon City bounds
    generateRandomIncidents(count = 5, severityMin = 0.3, severityMax = 0.9) {
        const incidentTypes = [
            'Accident', 'Road Closure', 'Construction', 
            'Road Hazard', 'Disabled Vehicle', 'Lane Restriction'
        ];
        
        const severityLevels = ['Heavy', 'Medium', 'Light'];
        
        // Quezon City bounds
        const bounds = {
            minLat: 14.58, maxLat: 14.72,
            minLng: 121.00, maxLng: 121.12
        };
        
        const incidents = [];
        for (let i = 0; i < count; i++) {
            const lat = bounds.minLat + Math.random() * (bounds.maxLat - bounds.minLat);
            const lng = bounds.minLng + Math.random() * (bounds.maxLng - bounds.minLng);
            const severity = severityMin + Math.random() * (severityMax - severityMin);
            
            incidents.push({
                id: `demo-incident-${i}`,
                type: incidentTypes[Math.floor(Math.random() * incidentTypes.length)],
                incident_type: incidentTypes[Math.floor(Math.random() * incidentTypes.length)],
                source_lat: lat - 0.0005,
                target_lat: lat + 0.0005,
                source_lng: lng - 0.0005,
                target_lng: lng + 0.0005,
                severity: severityLevels[Math.floor(Math.random() * severityLevels.length)],
                severity_value: severity,
                road_name: `Demo Road ${i + 1}`,
                description: `Demo incident ${i + 1}`,
                custom: true
            });
        }
        
        return incidents;
    },

    // Generate random flow segments
    generateRandomFlowSegments(count = 5, severityMin = 0.3, severityMax = 0.9) {
        // Quezon City bounds
        const bounds = {
            minLat: 14.58, maxLat: 14.72,
            minLng: 121.00, maxLng: 121.12
        };
        
        const segments = [];
        for (let i = 0; i < count; i++) {
            const lat = bounds.minLat + Math.random() * (bounds.maxLat - bounds.minLat);
            const lng = bounds.minLng + Math.random() * (bounds.maxLng - bounds.minLng);
            const severity = severityMin + Math.random() * (severityMax - severityMin);
            const currentSpeed = Math.floor(10 + Math.random() * 40); // 10-50 kph
            
            segments.push({
                id: `demo-flow-${i}`,
                type: 'Congestion',
                incident_type: 'Congestion',
                source_lat: lat,
                target_lat: lat + 0.002,
                source_lng: lng,
                target_lng: lng + 0.001,
                severity: severity > 0.7 ? 'Heavy' : severity > 0.4 ? 'Medium' : 'Light',
                severity_value: severity,
                current_speed: currentSpeed,
                free_flow_speed: 50,
                road_name: `Demo Road ${i + 1}`,
                custom: true
            });
        }
        
        return segments;
    },

    // Generate disruptions based on config and store them
    generateDemoDisruptions(config) {
        const mode = config.disruptions?.mode || config.disruptionMode || 'none';
        const incidentCount = config.disruptions?.randomIncidentCount || this.disruptions.randomIncidentCount || 5;
        const flowCount = config.disruptions?.randomFlowCount || this.disruptions.randomFlowCount || 5;
        const severityMin = config.disruptions?.severityMin || this.disruptions.severityMin || 0.3;
        const severityMax = config.disruptions?.severityMax || this.disruptions.severityMax || 0.9;
        
        console.log('🎲 Generating demo disruptions:', { mode, incidentCount, flowCount });
        
        this.generatedDisruptions = {
            incidents: [],
            flowSegments: []
        };
        
        switch (mode) {
            case 'random-both':
            case 'both':
                this.generatedDisruptions.incidents = this.generateRandomIncidents(incidentCount, severityMin, severityMax);
                this.generatedDisruptions.flowSegments = this.generateRandomFlowSegments(flowCount, severityMin, severityMax);
                break;
            case 'random-incidents':
            case 'incidents':
                this.generatedDisruptions.incidents = this.generateRandomIncidents(incidentCount, severityMin, severityMax);
                break;
            case 'random-flow':
            case 'flow':
                this.generatedDisruptions.flowSegments = this.generateRandomFlowSegments(flowCount, severityMin, severityMax);
                break;
            case 'custom':
                // Use custom items from config
                if (config.disruptions?.customItems) {
                    this.generatedDisruptions.incidents = config.disruptions.customItems.map((item, i) => ({
                        id: `custom-${i}`,
                        type: item.type || 'Road Hazard',
                        incident_type: item.type || 'Road Hazard',
                        source_lat: item.location?.lat || item.lat,
                        target_lat: (item.location?.lat || item.lat) + 0.001,
                        source_lng: item.location?.lng || item.lng,
                        target_lng: (item.location?.lng || item.lng) + 0.001,
                        severity: item.severity > 0.7 ? 'Heavy' : item.severity > 0.4 ? 'Medium' : 'Light',
                        severity_value: item.severity || 0.5,
                        road_name: item.description || `Custom Disruption ${i + 1}`,
                        custom: true
                    }));
                }
                break;
            case 'none':
            default:
                // No disruptions
                break;
        }
        
        console.log('✅ Generated disruptions:', {
            incidents: this.generatedDisruptions.incidents.length,
            flowSegments: this.generatedDisruptions.flowSegments.length
        });
        
        return this.generatedDisruptions;
    },

    // Show generated disruptions on map
    async showGeneratedDisruptions(showIncidents = true, showFlow = true) {
        console.log('🗺️ Showing generated disruptions:', { showIncidents, showFlow });
        
        // Clear existing disruption markers first
        if (typeof clearDisruptionMarkers === 'function') {
            clearDisruptionMarkers();
        }
        
        const allDisruptions = [];
        
        if (showIncidents && this.generatedDisruptions.incidents.length > 0) {
            allDisruptions.push(...this.generatedDisruptions.incidents);
        }
        
        if (showFlow && this.generatedDisruptions.flowSegments.length > 0) {
            allDisruptions.push(...this.generatedDisruptions.flowSegments);
        }
        
        if (allDisruptions.length === 0) {
            console.log('No disruptions to display');
            return;
        }
        
        // Format for showAllDisruptionsOnMap
        const disruptionData = {
            disruptions_by_type: {},
            total_disruptions: allDisruptions.length,
            severity_counts: { Heavy: 0, Medium: 0, Light: 0 }
        };
        
        // Group by type
        allDisruptions.forEach(d => {
            const type = d.incident_type || d.type || 'Other';
            if (!disruptionData.disruptions_by_type[type]) {
                disruptionData.disruptions_by_type[type] = [];
            }
            disruptionData.disruptions_by_type[type].push(d);
            
            // Count severity
            const severity = d.severity || 'Medium';
            if (disruptionData.severity_counts[severity] !== undefined) {
                disruptionData.severity_counts[severity]++;
            }
        });
        
        // Show on map
        if (typeof showAllDisruptionsOnMap === 'function') {
            showAllDisruptionsOnMap(disruptionData);
            console.log(`✅ Displayed ${allDisruptions.length} demo disruptions on map`);
        }
    },

    // Apply disruption visualization based on mode - NOW uses generated disruptions
    async applyDisruptionVisualization(mode, customItems) {
        console.log('🚦 Applying disruption visualization:', mode);
        
        // Generate disruptions based on mode
        const config = {
            disruptions: {
                mode: mode,
                customItems: customItems,
                randomIncidentCount: this.disruptions.randomIncidentCount,
                randomFlowCount: this.disruptions.randomFlowCount,
                severityMin: this.disruptions.severityMin,
                severityMax: this.disruptions.severityMax
            }
        };
        
        this.generateDemoDisruptions(config);
        
        let showIncidents = false;
        let showFlow = false;
        
        switch (mode) {
            case 'both':
            case 'random-both':
                showIncidents = true;
                showFlow = true;
                break;
            case 'incidents':
            case 'random-incidents':
                showIncidents = true;
                break;
            case 'flow':
            case 'random-flow':
                showFlow = true;
                break;
            case 'custom':
                showIncidents = true; // Custom items are treated as incidents
                break;
            case 'none':
            default:
                // Clear existing markers
                if (typeof clearDisruptionMarkers === 'function') {
                    clearDisruptionMarkers();
                }
                return;
        }
        
        // Show the generated disruptions on map
        await this.showGeneratedDisruptions(showIncidents, showFlow);
        
        // Set the dataset radio for the routing algorithm
        let datasetValue = 'none';
        if (showIncidents && showFlow) {
            datasetValue = 'both';
        } else if (showIncidents) {
            datasetValue = 'incidents';
        } else if (showFlow) {
            datasetValue = 'both';
        }
        
        const disruptionRadio = document.querySelector(`input[name="dataset"][value="${datasetValue}"]`);
        if (disruptionRadio) {
            disruptionRadio.click();
        }
    },

    // Show custom disruptions on map (legacy support)
    async showCustomDisruptionsOnMap(customItems) {
        if (!customItems || customItems.length === 0) return;
        
        console.log('🚧 Showing custom disruptions on map:', customItems.length);
        
        const formattedDisruptions = customItems.map((item, index) => ({
            id: `custom-${index}`,
            type: item.type || 'roadwork',
            lat: item.location?.lat || item.lat,
            lng: item.location?.lng || item.lng,
            location: item.location,
            severity: item.severity || 0.5,
            description: item.description || `Custom Disruption ${index + 1}`,
            custom: true
        }));
        
        if (typeof showAllDisruptionsOnMap === 'function') {
            await showAllDisruptionsOnMap({ 
                disruptions: formattedDisruptions, 
                total_disruptions: formattedDisruptions.length 
            });
        }
    },

    async resetMap() {
        if (typeof clearRoutes === 'function') clearRoutes();
        if (typeof clearDisruptionMarkers === 'function') clearDisruptionMarkers();
        if (typeof clearUpdateRegions === 'function') clearUpdateRegions();
        if (typeof clearGoogleMapsRoute === 'function') clearGoogleMapsRoute();
        await this.delay(500);
    },

    pauseDemo() {
        this.isPaused = true;
        this.currentProgress.status = '⏸️ Paused';
        this.updateProgressDisplay();
        showUpdateToast('Demo paused', 'info');
    },

    resumeDemo() {
        this.isPaused = false;
        this.currentProgress.status = 'Resuming...';
        this.updateProgressDisplay();
        showUpdateToast('Demo resumed', 'info');
    },

    stopDemo() {
        this.isRunning = false;
        this.isPaused = false;
        this.currentProgress.status = '⏹️ Stopped';
        this.updateProgressDisplay();
        showUpdateToast('Demo stopped', 'warning');
        
        // Return to step 1 after a short delay
        setTimeout(() => {
            this.goToStep(1);
        }, 1000);
    },

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    DemoCreator.init();
});

// Global exports
window.DemoCreator = DemoCreator;
window.openDemoCreator = () => DemoCreator.openPanel();
window.closeDemoCreator = () => DemoCreator.closePanel();

console.log('✅ Demo Creator V2 module loaded');
