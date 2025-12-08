/**
 * Demo Creator
 * 
 * Unified demo creation with:
 * - Location search like start/destination selection
 * - Random route generation option
 * - Visual disruption configuration
 * - Edit and Create modes
 * - Easy-to-use interface
 */

const DemoCreator = {
    // ==========================================================================
    // DEFAULT VALUES - Used for HTML element defaults and JS processing fallbacks
    // ==========================================================================
    DEFAULTS: {
        // Disruption settings
        disruption: {
            mode: 'random-both',
            generationScope: 'per-trial-route',
            flowCount: 1500,
            incidentCount: 5,
            severityMin: 0.1,
            severityMax: 0.7,
        },
        // TAU/Algorithm settings
        sequence: {
            algorithm: 'both',
            tauMode: 'random',
            tauFixed: 0.5,
            tauRandomMin: 0.1,
            tauRandomMax: 0.9,
            tauGenerationScope: 'per-trial-route',
            stepDelay: 2000,
            trials: 1,
        },
        // Route generation
        route: {
            minDistance: 0.5,  // km
            maxDistance: 10,   // km
            randomCount: 3,
        },
        // Custom disruption
        customDisruption: {
            type: 'incident',
            criticality: 'major',
            jamFactor: 5,
        }
    },
    
    // Mode: 'create' or 'edit'
    mode: 'create',
    
    // State
    routes: [],
    currentRouteIndex: -1,
    disruptions: {
        mode: 'random-both', // 'none', 'random-flow', 'random-incidents', 'random-both', 'custom'
        generationScope: 'per-trial-route', // 'all', 'per-trial', 'per-route', 'per-trial-route'
        randomFlowCount: 1500,
        randomIncidentCount: 5,
        severityMin: 0.1,
        severityMax: 0.7,
        customItems: [],
        // Store multiple disruption sets based on generation scope
        disruptionSets: {}  // Key: 'all', 'trial_0', 'route_1', 'trial_0_route_1', etc.
    },
    sequence: {
        algorithm: 'both',
        tauMode: 'random', // 'fixed', 'random'
        tauFixed: 0.5,
        tauSequence: [],
        tauRandomMin: 0.1,
        tauRandomMax: 0.9,
        tauGenerationScope: 'per-trial-route', // 'all', 'per-trial', 'per-route', 'per-trial-route'
        stepDelay: 2000,
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
    
    // Track if disruptions need to be generated when entering step 2
    disruptionsNeedGeneration: true,
    
    // Track if TAU values need to be generated when entering step 3
    tauNeedsGeneration: true,
    
    // Track last generated trials/routes for change detection
    lastGeneratedTrials: undefined,
    lastGeneratedRoutes: undefined,
    lastGeneratedTauTrials: undefined,
    lastGeneratedTauRoutes: undefined,
    
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
    // GUI SYNC HELPERS
    // ==========================================================================

    /**
     * Sync disruption settings from GUI inputs into this.disruptions state.
     * Call this before reading from this.disruptions to ensure values match GUI.
     */
    syncDisruptionsFromGUI() {
        // Read disruption mode from radio
        const modeRadio = document.querySelector('input[name="disruption-type"]:checked');
        if (modeRadio) {
            this.disruptions.mode = modeRadio.value;
        }

        // Read generation scope
        const scopeRadio = document.querySelector('input[name="disruption-generation-scope"]:checked');
        if (scopeRadio) {
            this.disruptions.generationScope = scopeRadio.value;
        }

        // Read flow count from GUI
        const flowCountEl = document.getElementById('random-flow-count');
        if (flowCountEl) {
            this.disruptions.randomFlowCount = parseInt(flowCountEl.value) || 1500;
        }

        // Read incident count from GUI
        const incidentCountEl = document.getElementById('random-incident-count');
        if (incidentCountEl) {
            this.disruptions.randomIncidentCount = parseInt(incidentCountEl.value) || 5;
        }

        // Read severity min/max from GUI
        const severityMinEl = document.getElementById('random-severity-min');
        if (severityMinEl) {
            this.disruptions.severityMin = parseFloat(severityMinEl.value) || 0.1;
        }

        const severityMaxEl = document.getElementById('random-severity-max');
        if (severityMaxEl) {
            this.disruptions.severityMax = parseFloat(severityMaxEl.value) || 0.7;
        }
    },

    /**
     * Sync TAU settings from GUI inputs into this.sequence state.
     * Call this before reading from this.sequence to ensure values match GUI.
     */
    syncTauFromGUI() {
        // Read TAU mode
        const tauModeRadio = document.querySelector('input[name="demo-tau-mode"]:checked');
        if (tauModeRadio) {
            this.sequence.tauMode = tauModeRadio.value;
        }

        // Read TAU scope
        const tauScopeRadio = document.querySelector('input[name="tau-generation-scope"]:checked');
        if (tauScopeRadio) {
            this.sequence.tauGenerationScope = tauScopeRadio.value;
        }

        // Read TAU random min/max
        const tauMinEl = document.getElementById('demo-tau-random-min');
        if (tauMinEl) {
            this.sequence.tauRandomMin = parseFloat(tauMinEl.value) || 0.1;
        }

        const tauMaxEl = document.getElementById('demo-tau-random-max');
        if (tauMaxEl) {
            this.sequence.tauRandomMax = parseFloat(tauMaxEl.value) || 0.9;
        }

        // Read trials count
        const trialsEl = document.getElementById('demo-trials-count');
        if (trialsEl) {
            this.sequence.trials = parseInt(trialsEl.value) || 1;
        }
    },

    // ==========================================================================
    // INITIALIZATION
    // ==========================================================================

    async init() {
        await this.loadQCBoundary();
        console.log('Initializing Demo Creator...');
        this.applyDefaultsToUI();
        this.bindEvents();
        this.renderRoutesList();
    },
    
    /**
     * Apply default values to UI elements
     */
    applyDefaultsToUI() {
        const d = this.DEFAULTS;
        
        // Disruption defaults
        const flowCountEl = document.getElementById('random-flow-count');
        if (flowCountEl) flowCountEl.value = d.disruption.flowCount;
        
        const incidentCountEl = document.getElementById('random-incident-count');
        if (incidentCountEl) incidentCountEl.value = d.disruption.incidentCount;
        
        const severityMinEl = document.getElementById('random-severity-min');
        if (severityMinEl) {
            severityMinEl.value = d.disruption.severityMin;
            const display = document.getElementById('random-severity-min-display');
            if (display) display.textContent = d.disruption.severityMin;
        }
        
        const severityMaxEl = document.getElementById('random-severity-max');
        if (severityMaxEl) {
            severityMaxEl.value = d.disruption.severityMax;
            const display = document.getElementById('random-severity-max-display');
            if (display) display.textContent = d.disruption.severityMax;
        }
        
        // TAU defaults
        const tauRandomMinEl = document.getElementById('demo-tau-random-min');
        if (tauRandomMinEl) tauRandomMinEl.value = d.sequence.tauRandomMin;
        
        const tauRandomMaxEl = document.getElementById('demo-tau-random-max');
        if (tauRandomMaxEl) tauRandomMaxEl.value = d.sequence.tauRandomMax;
        
        const stepDelayEl = document.getElementById('demo-step-delay');
        if (stepDelayEl) stepDelayEl.value = d.sequence.stepDelay;
        
        const trialsEl = document.getElementById('demo-trials-count');
        if (trialsEl) trialsEl.value = d.sequence.trials;
        
        // Set default radio selections
        const disruptionModeRadio = document.querySelector(`input[name="demo-disruption-mode"][value="${d.disruption.mode}"]`);
        if (disruptionModeRadio) disruptionModeRadio.checked = true;
        
        const disruptionScopeRadio = document.querySelector(`input[name="disruption-generation-scope"][value="${d.disruption.generationScope}"]`);
        if (disruptionScopeRadio) disruptionScopeRadio.checked = true;
        
        const algorithmRadio = document.querySelector(`input[name="demo-algorithm"][value="${d.sequence.algorithm}"]`);
        if (algorithmRadio) algorithmRadio.checked = true;
        
        const tauModeRadio = document.querySelector(`input[name="demo-tau-mode"][value="${d.sequence.tauMode}"]`);
        if (tauModeRadio) tauModeRadio.checked = true;
        
        const tauScopeRadio = document.querySelector(`input[name="tau-generation-scope"][value="${d.sequence.tauGenerationScope}"]`);
        if (tauScopeRadio) tauScopeRadio.checked = true;
        
        console.log('✅ Applied default values to UI');
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
        
        // Note: All selections (tau mode, algorithm, disruption mode, disruption scope, tau scope)
        // now use radio buttons with onchange handlers in HTML
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
            
            // Set mode based on whether we're editing
            if (configToEdit) {
                this.mode = 'edit';
                this.loadConfig(configToEdit);
            } else {
                this.mode = 'create';
                this.editingConfigId = null;
                this.disruptionsNeedGeneration = true;
                this.tauNeedsGeneration = true;
                // Apply defaults for create mode
                this.applyDefaultsToUI();
            }
            
            // Update panel title based on mode
            this.updatePanelTitle();
            
            // Update route/disruption visibility for step 1
            this.updateMapLayerVisibility(1);
            
            this.goToStep(1);
        }
    },
    
    /**
     * Update panel title based on current mode (create/edit)
     */
    updatePanelTitle() {
        const titleEl = document.getElementById('demo-creator-title');
        if (titleEl) {
            if (this.mode === 'edit') {
                titleEl.innerHTML = `
                    <span class="flex items-center gap-2">
                        <span>Edit Demo</span>
                        <span class="px-2 py-0.5 bg-blue-500 text-white text-xs rounded-full">Editing</span>
                    </span>
                `;
            } else {
                titleEl.innerHTML = `
                    <span class="flex items-center gap-2">
                        <span>Demo Creator</span>
                        <span class="px-2 py-0.5 bg-green-500 text-white text-xs rounded-full">New</span>
                    </span>
                `;
            }
        }
    },
    
    /**
     * Update map layer visibility based on current step
     * Routes: only on steps 1 and 4 (Config and Review)
     * Disruptions: only on steps 2 and 4 (Disruptions and Review)
     */
    updateMapLayerVisibility(step) {
        const showRoutes = step === 1 || step === 4;
        const showDisruptions = step === 2 || step === 4;
        
        // Show/hide route markers
        this.routeMarkers.forEach(marker => {
            if (map && marker) {
                if (showRoutes) {
                    if (!map.hasLayer(marker)) map.addLayer(marker);
                } else {
                    if (map.hasLayer(marker)) map.removeLayer(marker);
                }
            }
        });
        
        // Show/hide disruption preview markers
        this.disruptionPreviewMarkers.forEach(marker => {
            if (map && marker) {
                if (showDisruptions) {
                    if (!map.hasLayer(marker)) map.addLayer(marker);
                } else {
                    if (map.hasLayer(marker)) map.removeLayer(marker);
                }
            }
        });
        
        // Show/hide custom disruption markers
        this.disruptionMarkers.forEach(m => {
            if (map && m.marker) {
                if (showDisruptions) {
                    if (!map.hasLayer(m.marker)) map.addLayer(m.marker);
                } else {
                    if (map.hasLayer(m.marker)) map.removeLayer(m.marker);
                }
            }
        });
    },

    async loadConfig(config) {
        console.log('📝 Loading config for editing:', config.name);
        
        // Store editing state
        this.editingConfigId = config.id;
        this.mode = 'edit';
        
        // Load routes (preserve trials[] array if present)
        this.routes = config.routes ? config.routes.map(r => ({
            id: r.id || `route-${Date.now()}-${Math.random()}`,
            start: r.start,
            end: r.end,
            distance: r.distance,
            trials: r.trials,  // Preserve trials array if present
            tauValues: r.tauValues  // Keep legacy for backward compat
        })) : [];
        
        // Load disruptions - check both disruptionSets and savedSets
        if (config.disruptions) {
            // Use savedSets if available (Flask format), otherwise disruptionSets (in-memory format)
            const loadedSets = config.disruptions.savedSets || config.disruptions.disruptionSets || {};
            
            this.disruptions = {
                mode: config.disruptions.mode || config.disruptionMode || 'none',
                generationScope: config.disruptions.scope || config.disruptions.generationScope || 'per-trial-route',
                randomFlowCount: config.disruptions.flowCount || config.disruptions.randomFlowCount || 1500,
                randomIncidentCount: config.disruptions.incidentCount || config.disruptions.randomIncidentCount || 5,
                severityMin: config.disruptions.severityMin || 0.3,
                severityMax: config.disruptions.severityMax || 0.9,
                customItems: config.disruptions.customItems || [],
                disruptionSets: loadedSets  // Unified: use whichever exists
            };
        } else {
            // Handle legacy config format
            this.disruptions.mode = config.disruptionMode || 'none';
            this.disruptions.disruptionSets = {};
        }
        
        // Determine if we need to generate disruptions (only if no sets exist)
        const hasExistingDisruptions = Object.keys(this.disruptions.disruptionSets || {}).length > 0;
        this.disruptionsNeedGeneration = !hasExistingDisruptions;
        
        // Load sequence settings - check both legacy and new format
        this.sequence.algorithm = config.settings?.algorithm || config.algorithm || 'both';
        this.sequence.trials = config.settings?.trials || config.trials || 1;
        this.sequence.stepDelay = config.settings?.stepDelay || config.stepDelay || 2000;
        
        // Load tau settings from config.tau or from first route
        if (config.tau) {
            this.sequence.tauMode = config.tau.mode || 'random';
            this.sequence.tauFixed = config.tau.fixed || 0.5;
            this.sequence.tauRandomMin = config.tau.randomMin || 0.1;
            this.sequence.tauRandomMax = config.tau.randomMax || 0.9;
            this.sequence.tauGenerationScope = config.tau.scope || 'per-trial-route';
            this.sequence.tauSequence = config.tau.sequence || [];
        } else if (config.routes && config.routes[0]) {
            // Load tau settings from first route if available (legacy format)
            const tauValues = config.routes[0].tauValues;
            if (tauValues && tauValues.length === 1) {
                this.sequence.tauMode = 'fixed';
                this.sequence.tauFixed = tauValues[0];
            } else if (tauValues && tauValues.length > 1) {
                this.sequence.tauMode = 'random';  // Or sequence, depending on scope
            }
        }
        
        // Preserve TAU values during UI update (don't regenerate saved values)
        // Only preserve if we have saved TAU sequence or if routes have trial data with tau
        const hasExistingTau = (this.sequence.tauSequence && this.sequence.tauSequence.length > 0) ||
                               this.routes.some(r => r.trials && r.trials.some(t => t.tau !== undefined));
        this._preserveTauValues = hasExistingTau;
        
        // CRITICAL: Populate generatedTauValues from saved sequence to prevent regeneration
        // when entering the Sequence Configuration step later
        if (hasExistingTau && this.sequence.tauSequence && this.sequence.tauSequence.length > 0) {
            this.generatedTauValues = [...this.sequence.tauSequence];
            // Set the last generated counts so we don't detect a "change" later
            this.lastGeneratedTauTrials = this.sequence.trials;
            this.lastGeneratedTauRoutes = this.routes.length;
            this.tauNeedsGeneration = false;
            console.log(`🔒 Preserved ${this.generatedTauValues.length} TAU values from saved config`);
        }
        
        // Update UI elements
        this.updateUIFromState();
        
        // Clear the preserve flag after UI update
        this._preserveTauValues = false;
        
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
        
        // Show disruption sets if they exist
        const disruptionSets = this.disruptions.disruptionSets || {};
        const setKeys = Object.keys(disruptionSets);
        if (setKeys.length > 0) {
            console.log(`📦 Loaded ${setKeys.length} disruption sets:`, setKeys);
            this.currentPreviewSet = setKeys[0];
            
            // Check if this is savedSets format (has disruption_dir) or in-memory format (has flow/incidents)
            const firstSet = disruptionSets[setKeys[0]];
            if (firstSet.disruption_dir && config.disruptionKey) {
                // savedSets format - load ALL disruption sets from API
                await this.loadAllSavedDisruptionSets(config.disruptionKey, setKeys);
            } else if (firstSet.flow || firstSet.incidents) {
                // In-memory format - display directly
                this.displayDisruptionsOnMap(firstSet);
            }
            
            // Show preview after loading
            this.showDisruptionSetsPreview();
            
            // Update the disruption set status text
            const statusEl = document.getElementById('disruption-sets-status');
            if (statusEl) {
                statusEl.textContent = `${setKeys.length} set(s) loaded`;
            }
        }
        
        showUpdateToast(`Loaded: ${config.name}`, 'info');
    },

    /**
     * Load all saved disruption sets and convert them to in-memory format for editing.
     * @param {string} disruptionKey - The main disruption key
     * @param {string[]} setKeys - Array of set keys to load
     */
    async loadAllSavedDisruptionSets(disruptionKey, setKeys) {
        console.log(`📂 Loading ${setKeys.length} saved disruption sets from ${disruptionKey}...`);
        
        for (const setKey of setKeys) {
            try {
                const response = await fetch(`/api/demo/disruption-data/${disruptionKey}/${setKey}`);
                if (!response.ok) {
                    console.warn(`Failed to load disruption set ${setKey}`);
                    continue;
                }
                
                const data = await response.json();
                if (data.success) {
                    // Convert savedSets format to in-memory disruptionSets format
                    this.disruptions.disruptionSets[setKey] = {
                        flow: (data.flowSegments || []).map(f => ({
                            edge_id: f.edge_id,
                            osm_id: f.osm_id,
                            road_name: f.road_name || 'Unknown Road',
                            source_lat: f.source_lat,
                            source_lon: f.source_lon || f.source_lng,
                            target_lat: f.target_lat,
                            target_lon: f.target_lon || f.target_lng,
                            speed_kph: f.current_speed || f.speed_kph,
                            free_flow_kph: f.free_flow_speed || f.free_flow_kph,
                            jam_factor: f.jam_factor || (10 - ((f.current_speed || 30) / (f.free_flow_speed || 50)) * 10)
                        })),
                        incidents: (data.incidents || []).map(i => ({
                            edge_id: i.edge_id,
                            osm_id: i.osm_id,
                            road_name: i.road_name || 'Unknown Road',
                            source_lat: i.source_lat,
                            source_lon: i.source_lon || i.source_lng,
                            target_lat: i.target_lat,
                            target_lon: i.target_lon || i.target_lng,
                            type: i.type || i.incident_type || 'Incident',
                            criticality: i.criticality || i.severity || 'minor',
                            description: i.description || ''
                        }))
                    };
                    console.log(`   ✅ Loaded ${setKey}: ${data.flowSegments?.length || 0} flow, ${data.incidents?.length || 0} incidents`);
                }
            } catch (error) {
                console.error(`Error loading disruption set ${setKey}:`, error);
            }
        }
        
        // Display the first set on map
        const firstSet = this.disruptions.disruptionSets[setKeys[0]];
        if (firstSet) {
            this.displayDisruptionsOnMap(firstSet);
        }
    },

    /**
     * Load and display disruption data from a saved disruption set.
     * This fetches the actual disruption data from CSV files stored on the server.
     * @param {string} disruptionKey - The main disruption key (e.g., "disruption_20250608_123456")
     * @param {string} setKey - The specific set key (e.g., "global" or "route_0_trial_0")
     */
    async loadAndDisplaySavedDisruptionSet(disruptionKey, setKey) {
        try {
            const response = await fetch(`/api/demo/disruption-data/${disruptionKey}/${setKey}`);
            if (!response.ok) {
                console.warn(`Failed to load disruption set ${setKey} from ${disruptionKey}`);
                return;
            }
            
            const data = await response.json();
            
            // Store the loaded disruption data
            this.disruptions.loadedSetKey = setKey;
            this.disruptions.loadedDisruptionKey = disruptionKey;
            
            // Populate the customItems with loaded data for display
            this.disruptions.customItems = [];
            
            // Add flows
            if (data.flows && Array.isArray(data.flows)) {
                data.flows.forEach(flow => {
                    this.disruptions.customItems.push({
                        type: 'flow',
                        edgeId: flow.edge_id,
                        osmId: flow.osm_id,
                        source: flow.source,
                        target: flow.target,
                        speed: flow.speed,
                        freeFlowSpeed: flow.free_flow_speed,
                        lat: flow.lat || 0,
                        lon: flow.lon || 0
                    });
                });
            }
            
            // Add incidents
            if (data.incidents && Array.isArray(data.incidents)) {
                data.incidents.forEach(incident => {
                    this.disruptions.customItems.push({
                        type: 'incident',
                        edgeId: incident.edge_id,
                        osmId: incident.osm_id,
                        severity: incident.severity,
                        description: incident.description || 'Loaded incident',
                        lat: incident.lat || 0,
                        lon: incident.lon || 0
                    });
                });
            }
            
            // Update UI to show loaded disruptions
            this.updateDisruptionList();
            this.visualizeDisruptions();
            
            console.log(`Loaded disruption set: ${setKey} (${this.disruptions.customItems.length} items)`);
        } catch (error) {
            console.error('Error loading saved disruption set:', error);
        }
    },

    updateUIFromState() {
        // Update algorithm radio buttons
        const algorithmRadio = document.querySelector(`input[name="demo-algorithm"][value="${this.sequence.algorithm}"]`);
        if (algorithmRadio) algorithmRadio.checked = true;
        
        // Update tau mode radio buttons
        const tauModeRadio = document.querySelector(`input[name="demo-tau-mode"][value="${this.sequence.tauMode}"]`);
        if (tauModeRadio) {
            tauModeRadio.checked = true;
            this.updateTauModeUI();
        }
        
        // Update tau scope radio buttons
        const tauScopeRadio = document.querySelector(`input[name="tau-generation-scope"][value="${this.sequence.tauGenerationScope || 'all'}"]`);
        if (tauScopeRadio) tauScopeRadio.checked = true;
        
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
        
        // Update disruption mode radio buttons
        const disruptionModeRadio = document.querySelector(`input[name="demo-disruption-mode"][value="${this.disruptions.mode}"]`);
        if (disruptionModeRadio) {
            disruptionModeRadio.checked = true;
            this.updateDisruptionModeUI();
        }
        
        // Update disruption scope radio buttons
        const disruptionScopeRadio = document.querySelector(`input[name="disruption-generation-scope"][value="${this.disruptions.generationScope || 'per-trial-route'}"]`);
        if (disruptionScopeRadio) disruptionScopeRadio.checked = true;
        
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
        
    // Reset edit mode and panel mode (default to create)
    this.editingConfigId = null;
    this.mode = 'create';
    // Update panel title to reflect mode
    try { this.updatePanelTitle(); } catch (e) { /* ignore if UI not initialized */ }
        
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
        
        // Reset disruption mode radio buttons
        const disruptionModeRadio = document.querySelector('input[name="demo-disruption-mode"][value="random-both"]');
        if (disruptionModeRadio) disruptionModeRadio.checked = true;
        this.disruptions.mode = 'random-both';
        this.updateDisruptionModeUI();
        
        // Reset disruption scope radio buttons
        const disruptionScopeRadio = document.querySelector('input[name="disruption-generation-scope"][value="per-trial-route"]');
        if (disruptionScopeRadio) disruptionScopeRadio.checked = true;
        
        // Reset algorithm radio buttons
        const algorithmRadio = document.querySelector('input[name="demo-algorithm"][value="both"]');
        if (algorithmRadio) algorithmRadio.checked = true;
        
        // Reset tau mode radio buttons
        const tauModeRadio = document.querySelector('input[name="demo-tau-mode"][value="sequence"]');
        if (tauModeRadio) tauModeRadio.checked = true;
        this.updateTauModeUI();
        
        // Reset tau scope radio buttons
        const tauScopeRadio = document.querySelector('input[name="tau-generation-scope"][value="all"]');
        if (tauScopeRadio) tauScopeRadio.checked = true;
        
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
                const item = document.getElementById(`demo-v2-step-item-${s}`);
                const indicator = document.getElementById(`demo-v2-indicator-${s}`);
                const line = document.getElementById(`demo-v2-line-${s}`);
                
                if (item) {
                    if (s === step) {
                        item.classList.add('wizard-steps__item--active');
                    } else {
                        item.classList.remove('wizard-steps__item--active');
                    }
                    
                    if (s < step) {
                        item.classList.add('wizard-steps__item--completed');
                    } else {
                        item.classList.remove('wizard-steps__item--completed');
                    }
                }
                
                if (indicator) {
                    if (s === step) {
                        indicator.classList.add('wizard-steps__indicator--active');
                        indicator.classList.remove('wizard-steps__indicator--completed');
                    } else if (s < step) {
                        indicator.classList.add('wizard-steps__indicator--completed');
                        indicator.classList.remove('wizard-steps__indicator--active');
                    } else {
                        indicator.classList.remove('wizard-steps__indicator--active', 'wizard-steps__indicator--completed');
                    }
                }
                
                if (line) {
                    if (s < step) {
                        line.classList.add('wizard-steps__line--completed');
                    } else {
                        line.classList.remove('wizard-steps__line--completed');
                    }
                }
            });
            
            // Update map layer visibility based on step
            this.updateMapLayerVisibility(step);
        }
        
        // Update nav buttons based on current step
        const isRunning = step === 'running';
        
        // Toggle navigation buttons (shown on steps 1-3)
        const navButtonsContainer = document.getElementById('demo-v2-nav-buttons');
        if (navButtonsContainer) {
            navButtonsContainer.classList.toggle('hidden', step === 4 || isRunning);
        }
        
        // Toggle save buttons (shown only on step 4)
        const saveButtonsContainer = document.getElementById('demo-v2-save-buttons');
        if (saveButtonsContainer) {
            saveButtonsContainer.classList.toggle('hidden', step !== 4);
        }
        
        // Update individual button visibility within navigation buttons
        document.getElementById('demo-v2-prev-btn')?.classList.toggle('hidden', step === 1 || isRunning);
        document.getElementById('demo-v2-next-btn')?.classList.toggle('hidden', step === 4 || isRunning);
        
        // Show/hide step indicators during running
        document.querySelector('.sticky.top-\\[68px\\]')?.classList.toggle('opacity-50', isRunning);
        
        // Step 2: Auto-generate disruptions if empty and entering disruption step
        if (step === 2) {
            this.handleDisruptionStepEntry();
        }
        
        // Step 3: Auto-generate TAU values if needed when entering sequence step
        if (step === 3) {
            this.handleSequenceStepEntry();
        }
        
        // Update review if on step 4
        if (step === 4) {
            this.updateReviewSummary();
        }
    },
    
    /**
     * Handle entering the disruption step (step 2)
     * Auto-generates disruptions if the sets are empty or trials/routes changed
     */
    handleDisruptionStepEntry() {
        const disruptionSets = this.disruptions.disruptionSets || {};
        const hasDisruptions = Object.keys(disruptionSets).length > 0;
        
        // Get current trials and routes count
        const currentTrials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const currentRoutes = this.routes.length || 1;
        
        // Check if trials or routes changed since last generation
        const trialsChanged = this.lastGeneratedTrials !== undefined && this.lastGeneratedTrials !== currentTrials;
        const routesChanged = this.lastGeneratedRoutes !== undefined && this.lastGeneratedRoutes !== currentRoutes;
        
        if (trialsChanged || routesChanged) {
            console.log(`📦 Disruption regeneration needed: trials ${this.lastGeneratedTrials} → ${currentTrials}, routes ${this.lastGeneratedRoutes} → ${currentRoutes}`);
            this.disruptionsNeedGeneration = true;
        }
        
        if ((!hasDisruptions || trialsChanged || routesChanged) && this.disruptionsNeedGeneration) {
            console.log('📦 Disruption step opened - auto-generating disruptions...');
            
            // Trigger auto-generation with a small delay to let UI settle
            setTimeout(() => {
                this.autoGenerateDisruptions();
            }, 100);
        } else if (hasDisruptions) {
            // Show existing disruption sets
            const setKeys = Object.keys(disruptionSets);
            this.currentPreviewSet = setKeys[0];
            this.showDisruptionSetsPreview();
            this.displayDisruptionsOnMap(disruptionSets[setKeys[0]]);
            
            console.log(`📦 Showing existing ${setKeys.length} disruption sets`);
        }
    },

    /**
     * Handle entering the sequence step (step 3)
     * Auto-generates TAU values if needed or if trials/routes changed
     */
    handleSequenceStepEntry() {
        // Get current trials and routes count
        const currentTrials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const currentRoutes = this.routes.length || 1;
        const tauMode = this.getSelectedTauMode();
        
        // IMPORTANT: Always update the TAU mode UI when entering this step
        // This ensures the correct UI (fixed/random settings) is displayed based on selected mode
        this.updateTauModeUI();
        
        // Check if trials or routes changed since last TAU generation
        const trialsChanged = this.lastGeneratedTauTrials !== undefined && this.lastGeneratedTauTrials !== currentTrials;
        const routesChanged = this.lastGeneratedTauRoutes !== undefined && this.lastGeneratedTauRoutes !== currentRoutes;
        
        if (trialsChanged || routesChanged) {
            console.log(`🎯 TAU regeneration needed: trials ${this.lastGeneratedTauTrials} → ${currentTrials}, routes ${this.lastGeneratedTauRoutes} → ${currentRoutes}`);
            this.tauNeedsGeneration = true;
        }
        
        // Auto-generate TAU values if in random mode and needs generation
        if (tauMode === 'random' && (this.tauNeedsGeneration || !this.generatedTauValues || this.generatedTauValues.length === 0)) {
            console.log('🎯 Sequence step opened - auto-generating TAU values...');
            
            // Store current trials/routes for change detection
            this.lastGeneratedTauTrials = currentTrials;
            this.lastGeneratedTauRoutes = currentRoutes;
            
            // Trigger auto-generation with a small delay to let UI settle
            setTimeout(() => {
                this.generateRandomTauValues();
                this.tauNeedsGeneration = false;
            }, 100);
        } else {
            console.log(`🎯 TAU values already generated: ${this.generatedTauValues?.length || 0} values`);
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
        
        // Clear the disruption preview when mode changes
        this.clearDisruptionPreview(true);
        
        document.getElementById('disruption-random-settings')?.classList.toggle('hidden', 
            mode === 'none' || mode === 'custom');
        document.getElementById('disruption-custom-settings')?.classList.toggle('hidden', 
            mode !== 'custom');
        
        // Show/hide flow count based on mode
        document.getElementById('disruption-flow-count-row')?.classList.toggle('hidden',
            mode !== 'random-flow' && mode !== 'random-both');
        document.getElementById('disruption-incident-count-row')?.classList.toggle('hidden',
            mode !== 'random-incidents' && mode !== 'random-both');
        
        // Update visual styling for radio options
        document.querySelectorAll('.disruption-mode-option').forEach(label => {
            const radio = label.querySelector('input[type="radio"]');
            if (radio && radio.checked) {
                label.classList.add('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-slate-100', 'shadow-lg');
            } else {
                label.classList.remove('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-slate-100', 'shadow-lg');
            }
        });
    },

    /**
     * Set disruption mode from radio button (called from HTML)
     */
    setDisruptionMode(mode) {
        this.disruptions.mode = mode;
        this.updateDisruptionModeUI();
    },

    /**
     * Get selected disruption mode from radio buttons
     */
    getSelectedDisruptionMode() {
        return document.querySelector('input[name="demo-disruption-mode"]:checked')?.value || 'random-both';
    },

    /**
     * Get selected disruption scope from radio buttons
     */
    getSelectedDisruptionScope() {
        return document.querySelector('input[name="disruption-generation-scope"]:checked')?.value || 'per-trial-route';
    },

    /**
     * Update custom disruption type-specific inputs (incident: criticality, traffic: jam factor)
     */
    updateCustomDisruptionTypeUI() {
        const selectedType = document.querySelector('input[name="custom-disruption-type"]:checked')?.value || 'incident';
        
        // Show/hide type-specific settings
        document.getElementById('custom-incident-settings')?.classList.toggle('hidden', selectedType !== 'incident');
        document.getElementById('custom-traffic-settings')?.classList.toggle('hidden', selectedType !== 'traffic');
    },

    /**
     * Get custom disruption type from radio buttons
     */
    getCustomDisruptionType() {
        return document.querySelector('input[name="custom-disruption-type"]:checked')?.value || 'incident';
    },

    /**
     * Get custom incident criticality from radio buttons
     */
    getCustomIncidentCriticality() {
        return document.querySelector('input[name="custom-incident-criticality"]:checked')?.value || 'major';
    },

    /**
     * Get custom jam factor from slider
     */
    getCustomJamFactor() {
        return parseFloat(document.getElementById('custom-jam-factor')?.value) || 5;
    },

    /**
     * Update scope description based on selection
     */
    updateScopeDescription() {
        const scope = this.getSelectedDisruptionScope();
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
        const scope = this.getSelectedTauScope();
        this.sequence.tauGenerationScope = scope;
        
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

    // Debounce timer for auto-generation
    disruptionGenerationTimer: null,
    
    /**
     * Called when disruption scope or settings change - triggers auto-generation
     */
    setDisruptionScope(scope) {
        this.disruptions.generationScope = scope;
        this.updateScopeDescription();
        // Trigger auto-generation with debounce
        this.onDisruptionSettingChange();
    },
    
    /**
     * Called when any disruption setting changes - auto-generates disruptions
     */
    onDisruptionSettingChange() {
        // Clear previous timer
        if (this.disruptionGenerationTimer) {
            clearTimeout(this.disruptionGenerationTimer);
        }
        
        // Update status to show pending
        const statusText = document.getElementById('disruption-status-text');
        if (statusText) {
            statusText.textContent = 'Regenerating...';
            statusText.className = 'text-orange-500';
        }
        
        // Debounce: wait 500ms before generating to avoid rapid calls
        this.disruptionGenerationTimer = setTimeout(() => {
            this.autoGenerateDisruptions();
        }, 500);
    },
    
    /**
     * Auto-generate disruptions and show on map
     */
    async autoGenerateDisruptions() {
        const flowCount = parseInt(document.getElementById('random-flow-count')?.value) || 1500;
        const incidentCount = parseInt(document.getElementById('random-incident-count')?.value) || 5;
        const severityMin = parseFloat(document.getElementById('random-severity-min')?.value) || 0.1;
        const severityMax = parseFloat(document.getElementById('random-severity-max')?.value) || 0.7;
        const scope = this.getSelectedDisruptionScope();
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const routeCount = this.routes.length || 1;
        
        // Show loading indicator
        const loadingIndicator = document.getElementById('disruption-loading-indicator');
        const loadingText = document.getElementById('disruption-loading-text');
        const statusText = document.getElementById('disruption-status-text');
        
        if (loadingIndicator) loadingIndicator.classList.remove('hidden');
        if (statusText) statusText.textContent = 'Generating...';
        
        // Disable navigation buttons while generating
        this.setNavigationButtonsEnabled(false);
        
        try {
            // Calculate required sets
            const requiredSets = this.calculateRequiredSets();
            if (loadingText) loadingText.textContent = `Generating ${requiredSets} sets...`;
            
            // Clear previous sets
            this.disruptions.disruptionSets = {};
            
            // Generate set keys
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
                if (loadingText) loadingText.textContent = `Set ${generatedCount}/${setKeys.length}...`;
            }
            
            // Show the first set on map
            const firstKey = setKeys[0];
            if (this.disruptions.disruptionSets[firstKey]) {
                this.currentPreviewSet = firstKey;
                this.displayDisruptionsOnMap(this.disruptions.disruptionSets[firstKey]);
            }
            
            // Show sets list UI
            this.showDisruptionSetsPreview();
            
            // Update status
            if (statusText) {
                statusText.textContent = `✓ ${generatedCount} sets ready`;
                statusText.className = 'text-green-600 font-medium';
            }
            
            // Update status text below button
            const setsStatusEl = document.getElementById('disruption-sets-status');
            if (setsStatusEl) {
                setsStatusEl.textContent = `${generatedCount} set(s) generated`;
            }
            
            console.log(`📦 Auto-generated ${generatedCount} disruption sets for scope: ${scope}`);
            
            // Track what trials/routes we generated for
            this.lastGeneratedTrials = trials;
            this.lastGeneratedRoutes = routeCount;
            this.disruptionsNeedGeneration = false;
            
        } catch (error) {
            console.error('Error auto-generating disruptions:', error);
            if (statusText) {
                statusText.textContent = 'Generation failed';
                statusText.className = 'text-red-600';
            }
        } finally {
            // Hide loading indicator
            if (loadingIndicator) loadingIndicator.classList.add('hidden');
            // Re-enable navigation buttons
            this.setNavigationButtonsEnabled(true);
        }
    },
    
    /**
     * Generate random disruptions - called by button click
     * Similar to generateRandomTauValues()
     */
    async generateRandomDisruptions() {
        // Check if disruption mode is not 'custom' or 'none'
        const mode = this.disruptions.mode || 'random-both';
        if (mode === 'none') {
            showUpdateToast('Disruption mode is set to None', 'warning');
            return;
        }
        
        // Update button to show loading
        const btn = document.getElementById('generate-disruptions-btn');
        const originalContent = btn?.innerHTML;
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="animate-spin inline-block">⏳</span> Generating...';
        }
        
        try {
            await this.autoGenerateDisruptions();
            showUpdateToast('Disruptions generated successfully!', 'success');
        } catch (error) {
            console.error('Error generating disruptions:', error);
            showUpdateToast('Failed to generate disruptions', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalContent;
            }
        }
    },
    
    /**
     * Enable/disable navigation buttons
     */
    setNavigationButtonsEnabled(enabled) {
        const prevBtn = document.getElementById('demo-prev-btn');
        const nextBtn = document.getElementById('demo-next-btn');
        if (prevBtn) prevBtn.disabled = !enabled;
        if (nextBtn) nextBtn.disabled = !enabled;
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
        const flowCount = parseInt(document.getElementById('random-flow-count')?.value) || 1500;
        const incidentCount = parseInt(document.getElementById('random-incident-count')?.value) || 5;
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
            
            // Update status text
            const statusEl = document.getElementById('disruption-sets-status');
            if (statusEl) {
                statusEl.textContent = `${generatedCount} set(s) generated`;
            }
            
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
     * Display disruption preview on the map using unified TrafficUtils
     * Uses actual road geometry from OSM graph when available
     */
    displayDisruptionsOnMap(data) {
        // Clear existing preview markers
        this.clearDisruptionPreview(false);
        
        // Prepare flow segments with geometry handling
        const flowSegments = (data.flow || []).map(f => {
            // Process geometry if available
            let geometry = null;
            if (f.geometry && Array.isArray(f.geometry) && f.geometry.length >= 2) {
                geometry = f.geometry.map(coord => {
                    if (Array.isArray(coord)) {
                        return [parseFloat(coord[0]), parseFloat(coord[1])];
                    }
                    return null;
                }).filter(c => c !== null);
            }
            
            return {
                ...f,
                geometry: geometry,
                source_lng: f.source_lon || f.source_lng,
                target_lng: f.target_lon || f.target_lng
            };
        });
        
        // Prepare incidents  
        const incidents = (data.incidents || []).map(inc => ({
            ...inc,
            source_lng: inc.source_lon || inc.source_lng,
            target_lng: inc.target_lon || inc.target_lng,
            type: inc.type || 'Incident'
        }));
        
        // Use TrafficUtils unified display function
        // This ensures incidents are rendered ON TOP with icons inside markers
        TrafficUtils.displayDisruptionsOnMap({
            flowSegments: flowSegments,
            incidents: incidents,
            map: map,
            layerStorage: this.disruptionPreviewMarkers,
            showFlow: true,
            showIncidents: true
        });
        
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
        // Use TrafficUtils to clear layers
        TrafficUtils.clearDisruptionLayers(this.disruptionPreviewMarkers, map);
        
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
                    const disruptionType = this.getCustomDisruptionType();
                    
                    // Build disruption with type-specific properties
                    const disruption = {
                        id: `disruption-${Date.now()}`,
                        type: disruptionType,
                        lat: data.snapped_point.lat,
                        lng: data.snapped_point.lng,
                        roadName: data.road_name || 'Unknown Road',
                        source: data.routing_nodes[0],
                        target: data.routing_nodes[1]
                    };
                    
                    if (disruptionType === 'incident') {
                        // For incidents: store criticality
                        disruption.criticality = this.getCustomIncidentCriticality();
                        // Map criticality to severity for display
                        disruption.severity = disruption.criticality === 'critical' ? 0.9 : 
                                              disruption.criticality === 'major' ? 0.6 : 0.3;
                    } else {
                        // For traffic: store jam factor
                        disruption.jamFactor = this.getCustomJamFactor();
                        // Map jam factor to severity for display (0-10 → 0-1)
                        disruption.severity = disruption.jamFactor / 10;
                    }
                    
                    this.disruptions.customItems.push(disruption);
                    this.addDisruptionMarker(disruption);
                    this.renderDisruptionsList();
                    
                    showUpdateToast(`Added ${disruptionType} disruption on ${disruption.roadName}`, 'success');
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
        
        // Build popup content based on type
        let popupContent = `<b>${disruption.type === 'incident' ? '🚨 Incident' : '🚦 Traffic'}</b><br>${disruption.roadName}<br>`;
        
        if (disruption.type === 'incident') {
            const criticalityEmoji = disruption.criticality === 'critical' ? '🚫' : 
                                     disruption.criticality === 'major' ? '🚧' : '⚠️';
            popupContent += `Criticality: ${criticalityEmoji} ${disruption.criticality || 'major'}`;
        } else {
            popupContent += `Jam Factor: ${disruption.jamFactor?.toFixed(1) || (disruption.severity * 10).toFixed(1)}`;
        }
        
        const marker = L.circleMarker([disruption.lat, disruption.lng], {
            radius: 10,
            fillColor: color,
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        }).bindPopup(popupContent).addTo(map);
        
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
        
        container.innerHTML = this.disruptions.customItems.map(d => {
            // Build type-specific detail text
            let detailText;
            if (d.type === 'incident') {
                const criticalityEmoji = d.criticality === 'critical' ? '🚫' : 
                                         d.criticality === 'major' ? '🚧' : '⚠️';
                detailText = `Criticality: ${criticalityEmoji} ${d.criticality || 'major'}`;
            } else {
                detailText = `Jam Factor: ${d.jamFactor?.toFixed(1) || (d.severity * 10).toFixed(1)}`;
            }
            
            return `
                <div class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <span class="text-xl">${d.type === 'incident' ? '🚨' : '🚦'}</span>
                    <div class="flex-1 min-w-0">
                        <div class="font-medium text-gray-800 truncate">${d.roadName}</div>
                        <div class="text-xs text-gray-500">${detailText}</div>
                    </div>
                    <button onclick="DemoCreator.removeDisruption('${d.id}')" 
                            class="p-1 hover:bg-red-100 rounded transition-colors">
                        <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
            `;
        }).join('');
    },

    // ==========================================================================
    // TAU CONFIGURATION
    // ==========================================================================

    // Store generated tau values for random mode
    generatedTauValues: [],

    updateTauModeUI() {
        // Get the selected tau mode from radio buttons (fixed or random only)
        const selectedMode = this.getSelectedTauMode();
        this.sequence.tauMode = selectedMode;
        
        document.getElementById('tau-fixed-setting')?.classList.toggle('hidden', selectedMode !== 'fixed');
        document.getElementById('tau-random-setting')?.classList.toggle('hidden', selectedMode !== 'random');
        
        // Update visual styling for mode options
        document.querySelectorAll('.tau-mode-option').forEach(label => {
            const radio = label.querySelector('input[type="radio"]');
            if (radio && radio.checked) {
                label.classList.add('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-purple-100', 'shadow-lg');
            } else {
                label.classList.remove('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-purple-100', 'shadow-lg');
            }
        });
        
        // Update fixed value inputs based on scope
        this.updateTauInputs();
        
        // Auto-generate random values when switching to random mode
        // But skip if we're loading saved TAU values in edit mode
        if (selectedMode === 'random' && !this._preserveTauValues) {
            this.generateRandomTauValues();
        }
    },

    updateTauScopeUI() {
        const scope = this.getSelectedTauScope();
        const mode = this.getSelectedTauMode();
        
        // Update visual styling for scope options
        document.querySelectorAll('.tau-scope-option').forEach(label => {
            const radio = label.querySelector('input[type="radio"]');
            if (radio && radio.checked) {
                label.classList.add('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-purple-100', 'shadow-lg');
            } else {
                label.classList.remove('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-purple-100', 'shadow-lg');
            }
        });
        
        // Update tau inputs based on scope
        this.updateTauInputs();
        
        // Auto-regenerate random values when scope changes (if in random mode)
        // But skip if we're loading saved TAU values in edit mode
        if (mode === 'random' && !this._preserveTauValues) {
            this.generateRandomTauValues();
        }
    },

    updateTauInputs() {
        const scope = this.getSelectedTauScope();
        const mode = this.getSelectedTauMode();
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const routes = this.routes.length || 1;
        
        // Calculate how many inputs we need
        let inputCount = 1;
        let inputLabels = ['All'];
        
        switch (scope) {
            case 'all':
                inputCount = 1;
                inputLabels = ['All Trials & Routes'];
                break;
            case 'per-trial':
                inputCount = trials;
                inputLabels = Array(trials).fill(0).map((_, i) => `Trial ${i + 1}`);
                break;
            case 'per-route':
                inputCount = routes;
                inputLabels = this.routes.map((r, i) => `Route ${i + 1}: ${r.start?.name?.substring(0, 15) || 'Start'}...`);
                break;
            case 'per-trial-route':
                inputCount = trials * routes;
                inputLabels = [];
                for (let t = 0; t < trials; t++) {
                    for (let r = 0; r < routes; r++) {
                        inputLabels.push(`T${t + 1}R${r + 1}`);
                    }
                }
                break;
        }
        
        // Update help text
        const helpEl = document.getElementById('tau-fixed-help');
        if (helpEl) {
            helpEl.textContent = `Enter τ values (0-1) for ${inputCount} ${scope === 'all' ? 'configuration' : 'item(s)'}`;
        }
        
        // Generate dynamic inputs for fixed mode
        if (mode === 'fixed') {
            this.generateTauFixedInputs(inputCount, inputLabels);
        }
        
        // Reset generated values display for random mode
        if (mode === 'random') {
            this.generatedTauValues = [];
            document.getElementById('tau-random-generated')?.classList.add('hidden');
        }
    },

    generateTauFixedInputs(count, labels) {
        const container = document.getElementById('tau-fixed-inputs-container');
        if (!container) return;
        
        // Get existing values to preserve them
        const existingInputs = container.querySelectorAll('input[type="number"]');
        const existingValues = Array.from(existingInputs).map(input => parseFloat(input.value) || 0.5);
        
        if (count <= 4) {
            // Show individual inputs with labels
            container.innerHTML = labels.map((label, i) => `
                <div class="flex items-center gap-2">
                    <span class="text-xs text-purple-600 w-24 truncate" title="${label}">${label}</span>
                    <input type="number" class="tau-fixed-input flex-1 px-3 py-2 border border-purple-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-center"
                           value="${existingValues[i] !== undefined ? existingValues[i] : 0.5}" 
                           min="0" max="1" step="0.1"
                           data-index="${i}">
                </div>
            `).join('');
        } else {
            // Show compact comma-separated input
            const values = existingValues.length >= count 
                ? existingValues.slice(0, count) 
                : Array(count).fill(0.5);
            container.innerHTML = `
                <div class="space-y-2">
                    <p class="text-xs text-purple-500">Enter ${count} comma-separated values:</p>
                    <input type="text" id="demo-tau-fixed-values" 
                           value="${values.join(', ')}"
                           placeholder="${Array(Math.min(count, 5)).fill(0.5).join(', ')}${count > 5 ? ', ...' : ''}"
                           class="w-full px-4 py-2 border border-purple-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500">
                    <p class="text-xs text-purple-400">Format: Trial 1 Route 1, Trial 1 Route 2, Trial 2 Route 1, ...</p>
                </div>
            `;
        }
    },

    generateRandomTauValues() {
        const scope = this.getSelectedTauScope();
        const min = parseFloat(document.getElementById('demo-tau-random-min')?.value) || 0.1;
        const max = parseFloat(document.getElementById('demo-tau-random-max')?.value) || 0.9;
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const routes = this.routes.length || 1;
        
        // Calculate how many values we need
        let count = 1;
        switch (scope) {
            case 'all': count = 1; break;
            case 'per-trial': count = trials; break;
            case 'per-route': count = routes; break;
            case 'per-trial-route': count = trials * routes; break;
        }
        
        // Generate random values
        this.generatedTauValues = Array(count).fill(0).map(() => 
            parseFloat((Math.random() * (max - min) + min).toFixed(2))
        );
        
        // Display generated values
        const displayEl = document.getElementById('tau-random-values-display');
        const containerEl = document.getElementById('tau-random-generated');
        
        if (displayEl && containerEl) {
            containerEl.classList.remove('hidden');
            
            if (count <= 10) {
                // Show detailed view
                let labels = [];
                switch (scope) {
                    case 'all': labels = ['All']; break;
                    case 'per-trial': labels = Array(trials).fill(0).map((_, i) => `Trial ${i + 1}`); break;
                    case 'per-route': labels = this.routes.map((r, i) => `Route ${i + 1}`); break;
                    case 'per-trial-route':
                        for (let t = 0; t < trials; t++) {
                            for (let r = 0; r < routes; r++) {
                                labels.push(`T${t + 1}R${r + 1}`);
                            }
                        }
                        break;
                }
                displayEl.innerHTML = this.generatedTauValues.map((v, i) => 
                    `<span class="inline-block bg-orange-200 px-2 py-0.5 rounded mr-1 mb-1">${labels[i]}: ${v}</span>`
                ).join('');
            } else {
                // Show compact view
                displayEl.innerHTML = `<span class="text-orange-700">${this.generatedTauValues.map(v => v.toFixed(2)).join(', ')}</span>`;
            }
        }
        
        showUpdateToast(`Generated ${count} random τ values`, 'success');
    },

    updateTauFixedHelp() {
        // This is now handled in updateTauInputs()
        this.updateTauInputs();
    },

    /**
     * Get the selected algorithm from radio buttons
     */
    getSelectedAlgorithm() {
        return document.querySelector('input[name="demo-algorithm"]:checked')?.value || 'both';
    },

    /**
     * Update visual styling for algorithm radio options
     */
    updateAlgorithmUI() {
        document.querySelectorAll('.algorithm-option').forEach(label => {
            const radio = label.querySelector('input[type="radio"]');
            if (radio && radio.checked) {
                label.classList.add('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-slate-100', 'shadow-lg');
            } else {
                label.classList.remove('ring-2', 'ring-white', 'ring-offset-2', 'ring-offset-slate-100', 'shadow-lg');
            }
        });
    },

    /**
     * Get the selected TAU generation scope from radio buttons
     */
    getSelectedTauScope() {
        return document.querySelector('input[name="tau-generation-scope"]:checked')?.value || 'per-trial-route';
    },

    getSelectedTauMode() {
        return document.querySelector('input[name="demo-tau-mode"]:checked')?.value || 'random';
    },

    getTauValues() {
        const mode = this.getSelectedTauMode();
        const scope = this.getSelectedTauScope();
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const routes = this.routes.length || 1;
        
        // Calculate needed count
        let needed = 1;
        if (scope === 'per-trial') needed = trials;
        else if (scope === 'per-route') needed = routes;
        else if (scope === 'per-trial-route') needed = trials * routes;
        
        switch (mode) {
            case 'fixed':
                // First try to get from individual number inputs
                const numberInputs = document.querySelectorAll('#tau-fixed-inputs-container input.tau-fixed-input');
                if (numberInputs.length > 0) {
                    const vals = Array.from(numberInputs).map(input => parseFloat(input.value) || 0.5);
                    while (vals.length < needed) {
                        vals.push(vals[vals.length - 1] || 0.5);
                    }
                    return vals.slice(0, needed);
                }
                
                // Fall back to comma-separated text input
                const fixedStr = document.getElementById('demo-tau-fixed-values')?.value || '0.5';
                const fixedVals = fixedStr.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v));
                
                // Expand values if not enough provided
                while (fixedVals.length < needed) {
                    fixedVals.push(fixedVals[fixedVals.length - 1] || 0.5);
                }
                return fixedVals.slice(0, needed);
                
            case 'random':
                // Use pre-generated values if available
                if (this.generatedTauValues && this.generatedTauValues.length === needed) {
                    return this.generatedTauValues;
                }
                
                // Otherwise generate new random values
                const min = parseFloat(document.getElementById('demo-tau-random-min')?.value) || 0.1;
                const max = parseFloat(document.getElementById('demo-tau-random-max')?.value) || 0.9;
                
                return Array(needed).fill(0).map(() => 
                    parseFloat((Math.random() * (max - min) + min).toFixed(2))
                );
                
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
        
        // Sync state from GUI before reading values
        this.syncDisruptionsFromGUI();
        this.syncTauFromGUI();
        
        const algorithm = this.getSelectedAlgorithm();
        const tauValues = this.getTauValues();
        const tauScope = this.getSelectedTauScope();
        const tauMode = this.getSelectedTauMode();
        const stepDelay = parseInt(document.getElementById('demo-step-delay')?.value) || 2000;
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        const disruptionScope = document.querySelector('input[name="disruption-generation-scope"]:checked')?.value || 'per-trial-route';
        
        // Build routes table with TAU values
        let routesTableHtml = '';
        if (this.routes.length > 0) {
            // Determine table columns based on TAU scope
            let tauColumns = '';
            let tauHeaders = '';
            
            if (tauScope === 'all') {
                tauHeaders = '<th class="px-2 py-1 text-left text-xs font-medium text-blue-600">τ Value</th>';
                routesTableHtml = this.routes.map((r, i) => `
                    <tr class="border-t border-blue-100">
                        <td class="px-2 py-1 text-xs text-blue-800 font-medium">${i + 1}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.start?.name || 'Unknown'}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.end?.name || 'Unknown'}</td>
                        <td class="px-2 py-1 text-xs text-purple-600 font-mono">${tauValues[0]?.toFixed(2) || '0.50'}</td>
                    </tr>
                `).join('');
            } else if (tauScope === 'per-trial') {
                tauHeaders = Array(trials).fill(0).map((_, t) => 
                    `<th class="px-2 py-1 text-left text-xs font-medium text-purple-600">T${t + 1}</th>`
                ).join('');
                routesTableHtml = this.routes.map((r, i) => `
                    <tr class="border-t border-blue-100">
                        <td class="px-2 py-1 text-xs text-blue-800 font-medium">${i + 1}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.start?.name || 'Unknown'}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.end?.name || 'Unknown'}</td>
                        ${Array(trials).fill(0).map((_, t) => 
                            `<td class="px-2 py-1 text-xs text-purple-600 font-mono">${tauValues[t]?.toFixed(2) || '0.50'}</td>`
                        ).join('')}
                    </tr>
                `).join('');
            } else if (tauScope === 'per-route') {
                tauHeaders = '<th class="px-2 py-1 text-left text-xs font-medium text-purple-600">τ Value</th>';
                routesTableHtml = this.routes.map((r, i) => `
                    <tr class="border-t border-blue-100">
                        <td class="px-2 py-1 text-xs text-blue-800 font-medium">${i + 1}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.start?.name || 'Unknown'}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.end?.name || 'Unknown'}</td>
                        <td class="px-2 py-1 text-xs text-purple-600 font-mono">${tauValues[i]?.toFixed(2) || '0.50'}</td>
                    </tr>
                `).join('');
            } else { // per-trial-route
                tauHeaders = Array(trials).fill(0).map((_, t) => 
                    `<th class="px-2 py-1 text-left text-xs font-medium text-purple-600">T${t + 1}</th>`
                ).join('');
                routesTableHtml = this.routes.map((r, rIdx) => `
                    <tr class="border-t border-blue-100">
                        <td class="px-2 py-1 text-xs text-blue-800 font-medium">${rIdx + 1}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.start?.name || 'Unknown'}</td>
                        <td class="px-2 py-1 text-xs text-blue-700">${r.end?.name || 'Unknown'}</td>
                        ${Array(trials).fill(0).map((_, tIdx) => {
                            const valIdx = tIdx * this.routes.length + rIdx;
                            return `<td class="px-2 py-1 text-xs text-purple-600 font-mono">${tauValues[valIdx]?.toFixed(2) || '0.50'}</td>`;
                        }).join('')}
                    </tr>
                `).join('');
            }
            
            routesTableHtml = `
                <table class="w-full text-left">
                    <thead>
                        <tr class="text-xs text-blue-600">
                            <th class="px-2 py-1">#</th>
                            <th class="px-2 py-1">Start</th>
                            <th class="px-2 py-1">End</th>
                            ${tauHeaders}
                        </tr>
                    </thead>
                    <tbody>
                        ${routesTableHtml}
                    </tbody>
                </table>
            `;
        }
        
        // Get algorithm display name
        const algorithmNames = {
            'both': 'HC2L + DHL',
            'hc2l': 'HC2L Only',
            'dhl': 'DHL Only'
        };
        
        // Get scope display names
        const scopeNames = {
            'all': 'Same for All',
            'per-trial': 'Per Trial',
            'per-route': 'Per Route',
            'per-trial-route': 'Per Trial & Route'
        };
        
        container.innerHTML = `
            <div class="space-y-3">
                <!-- Routes Table -->
                <div class="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-200">
                    <h4 class="font-bold text-blue-800 mb-3 flex items-center gap-2">
                        <span>📍</span> Routes & TAU Values (${this.routes.length} routes × ${trials} trials)
                    </h4>
                    <div class="overflow-y-auto bg-white rounded-lg p-2">
                        ${this.routes.length > 0 ? routesTableHtml : '<p class="text-sm text-blue-400 italic">No routes defined</p>'}
                    </div>
                    <div class="mt-2 flex gap-4 text-xs text-blue-600">
                        <span>🎯 TAU Mode: <strong>${tauMode === 'fixed' ? 'Fixed' : 'Random'}</strong></span>
                        <span>📐 TAU Scope: <strong>${scopeNames[tauScope]}</strong></span>
                    </div>
                </div>
                
                <!-- Disruptions Summary -->
                <div class="bg-gradient-to-br from-orange-50 to-amber-50 rounded-xl p-4 border border-orange-200">
                    <h4 class="font-bold text-orange-800 mb-2 flex items-center gap-2">
                        <span>🚦</span> Disruptions
                    </h4>
                    <div class="grid grid-cols-2 gap-2 text-sm text-orange-700">
                        <div>Mode: <strong>${this.disruptions.mode}</strong></div>
                        <div>Scope: <strong>${scopeNames[disruptionScope]}</strong></div>
                        ${this.disruptions.mode.includes('random') ? `
                            <div>Flow Count: <strong>${this.disruptions.randomFlowCount || 50}</strong></div>
                            <div>Incident Count: <strong>${this.disruptions.randomIncidentCount || 5}</strong></div>
                            <div class="col-span-2">Severity: <strong>${this.disruptions.severityMin} - ${this.disruptions.severityMax}</strong></div>
                        ` : ''}
                        ${this.disruptions.mode === 'custom' ? `
                            <div class="col-span-2">Custom Items: <strong>${this.disruptions.customItems.length}</strong></div>
                        ` : ''}
                    </div>
                </div>
                
                <!-- Execution Summary -->
                <div class="bg-gradient-to-br from-purple-50 to-violet-50 rounded-xl p-4 border border-purple-200">
                    <h4 class="font-bold text-purple-800 mb-2 flex items-center gap-2">
                        <span>⚙️</span> Execution Settings
                    </h4>
                    <div class="grid grid-cols-2 gap-2 text-sm text-purple-700">
                        <div>Algorithm: <strong>${algorithmNames[algorithm] || algorithm}</strong></div>
                        <div>Step Delay: <strong>${stepDelay}ms</strong></div>
                        <div>Total Trials: <strong>${trials}</strong></div>
                        <div>Total Runs: <strong>${this.routes.length * trials}</strong></div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Build demo configuration object in the new format.
     * Creates routes with trials[] array containing tau and disruption metadata per trial.
     * @param {string} name - Demo name
     * @returns {Object} Config object ready for saving or running
     */
    /**
     * Build demo configuration object
     * 
     * SIMPLIFIED FORMAT (per FIX GUIDE):
     * - route.trials[].disruption is just the setKey string (metadata is in savedSets)
     * - No duplicate root-level fields
     * - settings, tau, disruptions are the main config blocks
     */
    buildDemoConfig(name = null) {
        // Sync all values from GUI before building config
        this.syncDisruptionsFromGUI();
        this.syncTauFromGUI();
        
        const trials = parseInt(document.getElementById('demo-trials-count')?.value) || 1;
        
        // Read TAU generation scope from radio buttons
        const tauScope = this.getSelectedTauScope();
        this.sequence.tauGenerationScope = tauScope;
        
        // Get all TAU values - these will be distributed based on scope
        const allTauValues = this.getTauValues();
        
        // Get disruption scope
        const disruptionScope = this.getSelectedDisruptionScope();
        
        // Build routes with trials[] array - SIMPLIFIED: disruption is just setKey
        const routesWithTrials = this.routes.map((r, routeIdx) => {
            const trialsArray = [];
            
            for (let t = 0; t < trials; t++) {
                // Determine tau for this trial/route based on scope
                let tau;
                switch (tauScope) {
                    case 'all':
                        tau = allTauValues[0] || 0.5;
                        break;
                    case 'per-trial':
                        tau = allTauValues[t] || 0.5;
                        break;
                    case 'per-route':
                        tau = allTauValues[routeIdx] || 0.5;
                        break;
                    case 'per-trial-route':
                        const idx = routeIdx * trials + t;
                        tau = allTauValues[idx] || 0.5;
                        break;
                    default:
                        tau = 0.5;
                }
                
                // Determine disruption set key for this trial/route based on scope
                let setKey;
                switch (disruptionScope) {
                    case 'all':
                        setKey = 'set_all';
                        break;
                    case 'per-trial':
                        setKey = `set_trial_${t}`;
                        break;
                    case 'per-route':
                        setKey = `set_route_${routeIdx}`;
                        break;
                    case 'per-trial-route':
                        setKey = `set_trial_${t}_route_${routeIdx}`;
                        break;
                    default:
                        setKey = 'set_all';
                }
                
                // SIMPLIFIED: disruption is just the setKey string
                // Metadata (flowCount, incidentCount, disruption_dir) is stored in savedSets
                trialsArray.push({
                    trial: t,
                    tau: tau,
                    disruption: setKey  // Just the key, not an object
                });
            }
            
            return {
                id: r.id,
                start: r.start,
                end: r.end,
                distance: r.distance,
                trials: trialsArray
            };
        });
        
        // Build configuration object - CLEAN FORMAT (no duplicates)
        const config = {
            name: name || document.getElementById('demo-v2-name')?.value || `Custom Demo - ${new Date().toLocaleString()}`,
            routes: routesWithTrials,
            
            // Settings block
            settings: {
                algorithm: this.getSelectedAlgorithm(),
                trials: trials,
                stepDelay: parseInt(document.getElementById('demo-step-delay')?.value) || 1000
            },
            
            // TAU configuration (template for regeneration/editing)
            tau: {
                mode: this.sequence.tauMode,
                scope: tauScope,
                fixed: this.sequence.tauFixed,
                randomMin: this.sequence.tauRandomMin,
                randomMax: this.sequence.tauRandomMax,
                sequence: this.sequence.tauSequence || []
            },
            
            // Disruption configuration (template settings + generated sets)
            disruptions: {
                mode: this.disruptions.mode,
                scope: disruptionScope,
                flowCount: this.disruptions.randomFlowCount,
                incidentCount: this.disruptions.randomIncidentCount,
                severityMin: this.disruptions.severityMin,
                severityMax: this.disruptions.severityMax,
                // Include the generated disruption sets for saving (will be converted to savedSets by Flask)
                disruptionSets: this.disruptions.disruptionSets || {}
            }
        };
        
        return config;
    },

    async saveForLater() {
        const saveBtn = document.getElementById('demo-v2-save-btn');
        const originalContent = saveBtn?.innerHTML;
        
        // Show loading state
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = `
                <svg class="animate-spin h-5 w-5 mr-2 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Saving...
            `;
        }
        
        try {
            // Build config using helper function
            const config = this.buildDemoConfig();
            
            // If editing, update the config; otherwise save new
            if (this.editingConfigId) {
                config.id = this.editingConfigId;
                await DemoRunner.updateConfig(config);
                showUpdateToast('Demo configuration updated!', 'success');
            } else {
                await DemoRunner.saveConfig(config);
                showUpdateToast('Demo configuration saved!', 'success');
            }
            
            // Close the panel after saving
            const panel = document.getElementById('demo-creator-panel');
            if (panel) {
                panel.classList.add('translate-x-full');
            }
            this.resetAll();
        } catch (error) {
            console.error('Error saving configuration:', error);
            showUpdateToast('Error saving configuration: ' + error.message, 'error');
        } finally {
            // Restore button state
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = originalContent;
            }
        }
    },

    /**
     * Run the demo without saving
     */
    async runOnly() {
        const runBtn = document.getElementById('demo-v2-run-btn');
        const originalContent = runBtn?.innerHTML;
        
        // Show loading state
        if (runBtn) {
            runBtn.disabled = true;
            runBtn.innerHTML = `
                <svg class="animate-spin h-5 w-5 mr-2 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Starting...
            `;
        }
        
        try {
            // Build config using helper function
            const config = this.buildDemoConfig(`Demo Run - ${new Date().toLocaleString()}`);
            
            // Run demo with detailed progress in this panel
            await this.runDemoWithProgress(config);
        } catch (error) {
            console.error('Error running demo:', error);
            showUpdateToast('Error running demo: ' + error.message, 'error');
        } finally {
            // Restore button state
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.innerHTML = originalContent;
            }
        }
    },

    async saveAndRun() {
        const runBtn = document.getElementById('demo-v2-save-run-btn');
        const originalContent = runBtn?.innerHTML;
        
        // Show loading state
        if (runBtn) {
            runBtn.disabled = true;
            runBtn.innerHTML = `
                <svg class="animate-spin h-5 w-5 mr-2 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Preparing...
            `;
        }
        
        try {
            // Build config using helper function
            const config = this.buildDemoConfig();
            
            // Save the configuration
            if (this.editingConfigId) {
                config.id = this.editingConfigId;
                await DemoRunner.updateConfig(config);
                showUpdateToast('Demo configuration updated!', 'success');
            } else {
                await DemoRunner.saveConfig(config);
                showUpdateToast('Demo configuration saved!', 'success');
            }
            
            // Run demo with detailed progress in this panel
            await this.runDemoWithProgress(config);
        } catch (error) {
            console.error('Error running demo:', error);
            showUpdateToast('Error running demo: ' + error.message, 'error');
        } finally {
            // Restore button state
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.innerHTML = originalContent;
            }
        }
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
    // Update config list to reflect running state (disables run buttons)
    if (typeof DemoRunner !== 'undefined' && DemoRunner.renderConfigList) DemoRunner.renderConfigList();
        
        const trials = config.trials || config.settings?.trials || 1;
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
            // Update config list to reflect stopped state (re-enable buttons)
            if (typeof DemoRunner !== 'undefined' && DemoRunner.renderConfigList) DemoRunner.renderConfigList();
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
        const flowCount = config.disruptions?.randomFlowCount || this.disruptions.randomFlowCount || 1500;
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
            // Revert to create mode when stopping the demo
            this.mode = 'create';
            this.editingConfigId = null;
            try { this.updatePanelTitle(); } catch (e) { /* ignore if UI not present */ }
            this.goToStep(1);
            // Update config list to reflect stopped demo
            if (typeof DemoRunner !== 'undefined' && DemoRunner.renderConfigList) DemoRunner.renderConfigList();
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
