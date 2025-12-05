/**
 * Demo Runner Module
 * Unified demo system with Run Demo panel featuring:
 * - Load saved configurations
 * - Create custom demo
 * - Run random demo with configurable settings
 */

const DemoRunner = {
    // State
    isRunning: false,
    isPaused: false,
    currentDemo: null,
    savedConfigs: [],
    randomDemoSettings: {
        trials: 1,
        routeCount: 1,
        algorithm: 'both',
        tauMode: 'fixed', // 'fixed', 'random', 'sequence'
        tauValue: 0.5,
        tauMin: 0.1,
        tauMax: 0.9,
        tauSequence: [0.1, 0.3, 0.5, 0.7, 0.9],
        enableDisruptions: true,
        disruptionMode: 'both', // 'none', 'flow', 'incidents', 'both'
        stepDelay: 2000
    },
    
    // Quezon City boundary data (loaded from GeoJSON)
    qcBoundary: null,
    qcBoundingBox: null,
    
    // Demo-specific disruption data
    demoDisruptionDir: null,
    generatedDisruptions: {
        flowSegments: [],
        incidents: []
    },
    
    // Detailed progress tracking
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
        lastResult: null,
        results: []
    },
    
    // Location presets for Quezon City
    presetLocations: [
        { name: 'Quezon Memorial Circle', lat: 14.6540, lng: 121.0490 },
        { name: 'SM North EDSA', lat: 14.6563, lng: 121.0315 },
        { name: 'UP Diliman', lat: 14.6537, lng: 121.0685 },
        { name: 'Trinoma Mall', lat: 14.6560, lng: 121.0324 },
        { name: 'Araneta Coliseum', lat: 14.6225, lng: 121.0501 },
        { name: 'Eastwood City', lat: 14.6093, lng: 121.0776 },
        { name: 'Tomas Morato', lat: 14.6320, lng: 121.0324 },
        { name: 'Ateneo de Manila', lat: 14.6386, lng: 121.0779 },
        { name: 'Katipunan Avenue', lat: 14.6300, lng: 121.0700 },
        { name: 'Commonwealth Avenue', lat: 14.6700, lng: 121.0700 },
        { name: 'Cubao', lat: 14.6180, lng: 121.0540 },
        { name: 'Fairview', lat: 14.7000, lng: 121.0800 }
    ],

    // ==========================================================================
    // INITIALIZATION
    // ==========================================================================
    
    async init() {
        console.log('🎬 Initializing Demo Runner...');
        this.loadSavedConfigs();
        this.bindEvents();
        await this.loadQCBoundary();
    },
    
    /**
     * Load Quezon City boundary from GeoJSON file
     */
    async loadQCBoundary() {
        try {
            const response = await fetch('/static/quezon_city_boundaries.geojson');
            if (response.ok) {
                const geojson = await response.json();
                // Get the polygon coordinates from the first feature
                if (geojson.features && geojson.features.length > 0) {
                    const geometry = geojson.features[0].geometry;
                    if (geometry.type === 'Polygon') {
                        this.qcBoundary = geometry.coordinates[0]; // Outer ring
                    } else if (geometry.type === 'MultiPolygon') {
                        // Use the first polygon for simplicity
                        this.qcBoundary = geometry.coordinates[0][0];
                    }
                    
                    // Calculate bounding box for faster rejection
                    if (this.qcBoundary) {
                        const lngs = this.qcBoundary.map(c => c[0]);
                        const lats = this.qcBoundary.map(c => c[1]);
                        this.qcBoundingBox = {
                            minLng: Math.min(...lngs),
                            maxLng: Math.max(...lngs),
                            minLat: Math.min(...lats),
                            maxLat: Math.max(...lats)
                        };
                        console.log('📍 QC boundary loaded:', this.qcBoundingBox);
                    }
                }
            }
        } catch (error) {
            console.warn('⚠️ Could not load QC boundary GeoJSON:', error);
            // Fallback to hardcoded bounding box
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
        // Quick bounding box check first
        if (this.qcBoundingBox) {
            if (lng < this.qcBoundingBox.minLng || lng > this.qcBoundingBox.maxLng ||
                lat < this.qcBoundingBox.minLat || lat > this.qcBoundingBox.maxLat) {
                return false;
            }
        }
        
        // If no polygon data, use bounding box only
        if (!this.qcBoundary) {
            return true; // Already passed bounding box check
        }
        
        // Ray casting algorithm for point-in-polygon
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
            // Generate random point within bounding box
            const lat = this.qcBoundingBox.minLat + Math.random() * (this.qcBoundingBox.maxLat - this.qcBoundingBox.minLat);
            const lng = this.qcBoundingBox.minLng + Math.random() * (this.qcBoundingBox.maxLng - this.qcBoundingBox.minLng);
            
            // Check if point is inside QC boundary
            if (this.isPointInQC(lat, lng)) {
                return { lat, lng, name: `Random (${lat.toFixed(4)}, ${lng.toFixed(4)})` };
            }
        }
        
        // Fallback to preset if all attempts fail
        console.warn('⚠️ Could not generate random point in QC, using preset');
        return this.getRandomLocation();
    },

    bindEvents() {
        // Random demo settings
        document.getElementById('random-route-count')?.addEventListener('input', (e) => {
            this.randomDemoSettings.routeCount = parseInt(e.target.value) || 1;
        });
        
        document.getElementById('random-algorithm')?.addEventListener('change', (e) => {
            this.randomDemoSettings.algorithm = e.target.value;
        });
        
        document.getElementById('random-tau-mode')?.addEventListener('change', (e) => {
            this.randomDemoSettings.tauMode = e.target.value;
            this.updateTauModeUI();
        });
        
        document.getElementById('random-disruption-mode')?.addEventListener('change', (e) => {
            this.randomDemoSettings.disruptionMode = e.target.value;
        });
        
        // Demo disruption toggles
        document.getElementById('demo-show-incidents')?.addEventListener('change', (e) => {
            const showFlow = document.getElementById('demo-show-flow')?.checked || false;
            this.showGeneratedDisruptions(e.target.checked, showFlow);
        });
        
        document.getElementById('demo-show-flow')?.addEventListener('change', (e) => {
            const showIncidents = document.getElementById('demo-show-incidents')?.checked || false;
            this.showGeneratedDisruptions(showIncidents, e.target.checked);
        });
    },

    // ==========================================================================
    // PANEL CONTROLS
    // ==========================================================================

    openPanel() {
        const panel = document.getElementById('demo-runner-panel');
        if (panel) {
            panel.classList.remove('translate-x-full');
            this.loadSavedConfigs();
            this.showTab('main');
            
            // Turn off admin panel toggles when Demo Runner opens
            this.disableAdminToggles();
        }
    },

    closePanel() {
        // If demo is running, show confirmation dialog
        if (this.isRunning) {
            this.showStopConfirmation();
            return;
        }
        
        const panel = document.getElementById('demo-runner-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
        }
    },
    
    forceClosePanel() {
        const panel = document.getElementById('demo-runner-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
        }
    },

    showStopConfirmation() {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.id = 'demo-stop-modal';
        overlay.className = 'fixed inset-0 bg-black/50 flex items-center justify-center z-[100]';
        overlay.innerHTML = `
            <div class="bg-white rounded-2xl p-6 max-w-md mx-4 shadow-2xl">
                <div class="flex items-center gap-3 mb-4">
                    <div class="bg-amber-100 p-3 rounded-full">
                        <svg class="w-6 h-6 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                    </div>
                    <h3 class="text-lg font-bold text-gray-800">Demo Running</h3>
                </div>
                <p class="text-gray-600 mb-6">A demo is currently running. Do you want to stop it and close?</p>
                <div class="flex gap-3">
                    <button id="demo-stop-cancel" class="flex-1 py-2 px-4 bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold rounded-xl transition-colors">
                        Continue Demo
                    </button>
                    <button id="demo-stop-confirm" class="flex-1 py-2 px-4 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-xl transition-colors">
                        Stop & Close
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        // Handle cancel
        document.getElementById('demo-stop-cancel').addEventListener('click', () => {
            overlay.remove();
        });
        
        // Handle confirm
        document.getElementById('demo-stop-confirm').addEventListener('click', () => {
            this.stopDemo();
            overlay.remove();
            this.forceClosePanel();
        });
        
        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.remove();
            }
        });
    },

    disableAdminToggles() {
        // Store previous state
        const incidentToggle = document.getElementById('show-active-incidents');
        const flowToggle = document.getElementById('show-traffic-overlay');
        
        this.previousToggleStates = {
            incidents: incidentToggle?.checked || false,
            flow: flowToggle?.checked || false
        };
        
        // Turn off toggles
        if (incidentToggle && incidentToggle.checked) {
            incidentToggle.checked = false;
            incidentToggle.dispatchEvent(new Event('change'));
        }
        if (flowToggle && flowToggle.checked) {
            flowToggle.checked = false;
            flowToggle.dispatchEvent(new Event('change'));
        }
        
        console.log('🔇 Admin toggles disabled for demo');
    },

    showTab(tabName) {
        // Hide all tabs (including results)
        ['main', 'random-settings', 'running', 'results'].forEach(tab => {
            const el = document.getElementById(`demo-runner-tab-${tab}`);
            if (el) el.classList.add('hidden');
        });
        
        // Show selected tab
        const selectedTab = document.getElementById(`demo-runner-tab-${tabName}`);
        if (selectedTab) selectedTab.classList.remove('hidden');
        
        // Update tab indicators
        document.querySelectorAll('[data-demo-tab]').forEach(btn => {
            btn.classList.remove('bg-purple-600', 'text-white');
            btn.classList.add('bg-gray-200', 'text-gray-700');
        });
        
        const activeBtn = document.querySelector(`[data-demo-tab="${tabName}"]`);
        if (activeBtn) {
            activeBtn.classList.remove('bg-gray-200', 'text-gray-700');
            activeBtn.classList.add('bg-purple-600', 'text-white');
        }
        
        // When switching to running tab, refresh the disruption display
        if (tabName === 'running') {
            console.log('🗺️ Switching to running tab, checking disruptions...');
            console.log('   generatedDisruptions:', this.generatedDisruptions);
            console.log('   disruptionSets:', Object.keys(this.disruptionSets || {}));
            
            // Initialize checkboxes to be checked
            const showIncidentsCheckbox = document.getElementById('demo-show-incidents');
            const showFlowCheckbox = document.getElementById('demo-show-flow');
            
            // Ensure checkboxes are checked by default
            if (showIncidentsCheckbox && !showIncidentsCheckbox.checked) {
                showIncidentsCheckbox.checked = true;
            }
            if (showFlowCheckbox && !showFlowCheckbox.checked) {
                showFlowCheckbox.checked = true;
            }
            
            const showIncidents = showIncidentsCheckbox?.checked ?? true;
            const showFlow = showFlowCheckbox?.checked ?? true;
            
            // Check if we have disruptions to display
            const hasIncidents = this.generatedDisruptions?.incidents?.length > 0;
            const hasFlow = this.generatedDisruptions?.flowSegments?.length > 0;
            
            console.log(`   Has incidents: ${hasIncidents}, Has flow: ${hasFlow}`);
            
            if (hasIncidents || hasFlow) {
                // Force refresh the disruption visualization
                this.refreshDisruptionDisplay();
            } else {
                // Update preview to show "no disruptions"
                this.updateDisruptionPreview();
            }
        }
    },
    
    /**
     * Force refresh the disruption display on the map
     */
    refreshDisruptionDisplay() {
        const showIncidents = document.getElementById('demo-show-incidents')?.checked ?? true;
        const showFlow = document.getElementById('demo-show-flow')?.checked ?? true;
        
        console.log('🔄 Refreshing disruption display:', { showIncidents, showFlow });
        
        // Show the disruptions on map
        this.showGeneratedDisruptions(showIncidents, showFlow);
        
        // Update the preview list
        this.updateDisruptionPreview();
        
        // Update disruption sets if available
        if (this.disruptionSets && Object.keys(this.disruptionSets).length > 0) {
            this.showDisruptionSetsPreview();
        }
    },

    updateTauModeUI() {
        const mode = this.randomDemoSettings.tauMode;
        
        document.getElementById('tau-fixed-container')?.classList.toggle('hidden', mode !== 'fixed');
        document.getElementById('tau-random-container')?.classList.toggle('hidden', mode !== 'random');
        document.getElementById('tau-sequence-container')?.classList.toggle('hidden', mode !== 'sequence');
    },

    // ==========================================================================
    // CONFIG MANAGEMENT (File-based storage via API)
    // ==========================================================================

    async loadSavedConfigs() {
        try {
            const response = await fetch('/api/demo/configs');
            const result = await response.json();
            
            if (result.success) {
                this.savedConfigs = result.configs || [];
            } else {
                console.error('Error loading configs:', result.error);
                this.savedConfigs = [];
            }
            this.renderConfigList();
        } catch (e) {
            console.error('Error loading saved configs:', e);
            this.savedConfigs = [];
            this.renderConfigList();
        }
    },

    async saveConfig(config) {
        try {
            const response = await fetch('/api/demo/configs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.savedConfigs.push(result.config);
                this.renderConfigList();
                showUpdateToast('Demo configuration saved', 'success');
            } else {
                showUpdateToast('Failed to save configuration: ' + result.error, 'error');
            }
        } catch (e) {
            console.error('Error saving config:', e);
            showUpdateToast('Error saving configuration', 'error');
        }
    },

    async updateConfig(config) {
        try {
            const response = await fetch(`/api/demo/configs/${config.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            
            if (result.success) {
                const index = this.savedConfigs.findIndex(c => c.id === config.id);
                if (index !== -1) {
                    this.savedConfigs[index] = result.config;
                } else {
                    this.savedConfigs.push(result.config);
                }
                this.renderConfigList();
                showUpdateToast('Configuration updated', 'success');
            } else {
                showUpdateToast('Failed to update configuration: ' + result.error, 'error');
            }
        } catch (e) {
            console.error('Error updating config:', e);
            showUpdateToast('Error updating configuration', 'error');
        }
    },

    editConfig(configId) {
        const config = this.savedConfigs.find(c => c.id === configId);
        if (config) {
            // Close this panel
            this.closePanel();
            // Open Demo Creator with the config to edit
            DemoCreator.openPanel(config);
        }
    },

    async deleteConfig(configId) {
        if (!confirm('Delete this configuration? This will also remove associated disruption files and results.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/demo/configs/${configId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.savedConfigs = this.savedConfigs.filter(c => c.id !== configId);
                this.renderConfigList();
                showUpdateToast('Configuration deleted', 'info');
            } else {
                showUpdateToast('Failed to delete: ' + result.error, 'error');
            }
        } catch (e) {
            console.error('Error deleting config:', e);
            showUpdateToast('Error deleting configuration', 'error');
        }
    },

    renderConfigList() {
        const container = document.getElementById('saved-configs-list');
        if (!container) return;

        if (this.savedConfigs.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <svg class="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" 
                              d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>
                    </svg>
                    <p class="text-sm">No saved configurations</p>
                    <p class="text-xs mt-1">Create a custom demo to save it here</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.savedConfigs.map(config => `
            <div class="bg-white rounded-xl p-4 border border-gray-200 hover:border-purple-300 hover:shadow-md transition-all">
                <div class="flex items-start justify-between mb-2">
                    <div class="flex-1 min-w-0">
                        <h4 class="font-bold text-gray-800 truncate">${config.name || 'Unnamed Demo'}</h4>
                        <p class="text-xs text-gray-500">${new Date(config.savedAt).toLocaleDateString()}</p>
                    </div>
                    <div class="flex gap-1">
                        <button onclick="DemoRunner.editConfig('${config.id}')" 
                                class="p-1.5 hover:bg-blue-100 rounded-lg transition-colors" title="Edit">
                            <svg class="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                            </svg>
                        </button>
                        <button onclick="DemoRunner.deleteConfig('${config.id}')" 
                                class="p-1.5 hover:bg-red-100 rounded-lg transition-colors" title="Delete">
                            <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="flex flex-wrap items-center gap-2 text-xs text-gray-600 mb-3">
                    <span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded">${config.routes?.length || 0} routes</span>
                    <span class="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded">${config.trials || 1} trials</span>
                    <span class="px-2 py-0.5 bg-orange-100 text-orange-700 rounded">${config.algorithm?.toUpperCase() || 'HC2L'}</span>
                </div>
                <button onclick="DemoRunner.runSavedConfig('${config.id}')" 
                        class="w-full py-2 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-lg transition-all text-sm">
                    ▶️ Run Demo
                </button>
            </div>
        `).join('');
    },

    runSavedConfig(configId) {
        const config = this.savedConfigs.find(c => c.id === configId);
        if (config) {
            this.runDemo(config);
        }
    },

    // ==========================================================================
    // RANDOM DEMO
    // ==========================================================================

    openRandomSettings() {
        this.showTab('random-settings');
    },

    getRandomLocation() {
        const idx = Math.floor(Math.random() * this.presetLocations.length);
        return this.presetLocations[idx];
    },

    /**
     * Get a pair of random locations for route generation.
     * If useRandomQC is true, uses truly random coords within QC boundary.
     * Otherwise uses preset locations.
     */
    getRandomLocationPair(useRandomQC = false) {
        if (useRandomQC && this.qcBoundary) {
            // Generate truly random locations within QC
            const start = this.getRandomLocationInQC();
            let end;
            let attempts = 0;
            do {
                end = this.getRandomLocationInQC();
                attempts++;
            } while (attempts < 10 && 
                     Math.abs(end.lat - start.lat) < 0.01 && 
                     Math.abs(end.lng - start.lng) < 0.01);
            return { start, end };
        } else {
            // Use preset locations
            let start = this.getRandomLocation();
            let end;
            do {
                end = this.getRandomLocation();
            } while (end.name === start.name);
            return { start, end };
        }
    },

    getTauValue() {
        const settings = this.randomDemoSettings;
        switch (settings.tauMode) {
            case 'fixed':
                return [parseFloat(document.getElementById('random-tau-fixed')?.value) || 0.5];
            case 'random':
                const min = parseFloat(document.getElementById('random-tau-min')?.value) || 0.1;
                const max = parseFloat(document.getElementById('random-tau-max')?.value) || 0.9;
                return [Math.random() * (max - min) + min];
            case 'sequence':
                const seqStr = document.getElementById('random-tau-sequence')?.value || '0.1, 0.3, 0.5, 0.7, 0.9';
                return seqStr.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v));
            default:
                return [0.5];
        }
    },

    async startRandomDemo() {
        const settings = this.randomDemoSettings;
        settings.trials = parseInt(document.getElementById('random-trials-count')?.value) || 1;
        settings.routeCount = parseInt(document.getElementById('random-route-count')?.value) || 1;
        settings.algorithm = document.getElementById('random-algorithm')?.value || 'both';
        settings.disruptionMode = document.getElementById('random-disruption-mode')?.value || 'both';
        settings.stepDelay = parseInt(document.getElementById('random-step-delay')?.value) || 2000;

        // Always use truly random QC locations
        const useRandomQC = true;

        // Generate random routes
        const routes = [];
        for (let i = 0; i < settings.routeCount; i++) {
            const pair = this.getRandomLocationPair(useRandomQC);
            routes.push({
                id: `route-${i}`,
                start: pair.start,
                end: pair.end,
                tauValues: this.getTauValue()
            });
        }

        const config = {
            name: `Random Demo - ${routes.length} route(s) × ${settings.trials} trial(s)`,
            routes: routes,
            trials: settings.trials,
            algorithm: settings.algorithm,
            disruptionMode: settings.disruptionMode,
            stepDelay: settings.stepDelay,
            isRandom: true
        };

        this.showTab('main');
        this.runDemo(config);
    },

    // ==========================================================================
    // DEMO EXECUTION
    // ==========================================================================

    async runDemo(config) {
        if (this.isRunning) {
            showUpdateToast('A demo is already running', 'warning');
            return;
        }

        this.isRunning = true;
        this.isPaused = false;
        this.currentDemo = config;
        this.currentDemoId = null;  // Track demoId for cleanup
        
        const trials = config.trials || 1;
        const routes = config.routes || [];
        
        // Check if this is a saved config with pre-generated disruptions (in-memory)
        const configDisruptionSets = config.disruptions?.disruptionSets || {};
        const hasConfigDisruptions = Object.keys(configDisruptionSets).length > 0;
        
        // Initialize detailed progress
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
            results: [],
            configName: config.name
        };
        
        console.log('🎬 Starting demo:', config.name);
        if (hasConfigDisruptions) {
            console.log(`� Using ${Object.keys(configDisruptionSets).length} saved disruption sets from config`);
        }
        showUpdateToast(`🎬 Starting: ${config.name}`, 'info');
        
        this.showTab('running');
        this.updateDetailedProgressUI();

        try {
            // Reset map
            await this.resetMap();
            
            // Get disruption config
            const disruptions = config.disruptions || {};
            const generationScope = disruptions.generationScope || 'all';
            
            // Handle disruption setup
            this.disruptionSets = {};  // Store disruption sets by key
            this.currentDemoId = `demo_${Date.now()}`;
            
            if (hasConfigDisruptions) {
                // Use saved disruption sets from config - write to temp files for routing
                for (const [setKey, setData] of Object.entries(configDisruptionSets)) {
                    await this.activateConfigDisruptionSet(setKey, setData, this.currentDemoId);
                }
            } else {
                // Generate new disruptions based on scope
                if (generationScope === 'all') {
                    // Generate one set for all trials/routes
                    await this.setupDemoDisruptions(config, this.currentDemoId, 'set_all');
                } else if (generationScope === 'per-route') {
                    // Pre-generate disruption set for each route (used across all trials)
                    for (let i = 0; i < routes.length; i++) {
                        const routeKey = `set_route_${i}`;
                        await this.setupDemoDisruptions(config, `${this.currentDemoId}_${routeKey}`, routeKey);
                    }
                }
                // For per-trial and per-trial-route, generate on-the-fly in the loop
            }
            
            // Run for each trial
            for (let trial = 0; trial < trials; trial++) {
                if (!this.isRunning) break;
                
                this.currentProgress.trial = trial + 1;
                
                // Generate disruptions for this trial if per-trial scope (only if not using config-saved)
                if (!hasConfigDisruptions && generationScope === 'per-trial') {
                    const trialKey = `set_trial_${trial}`;
                    await this.setupDemoDisruptions(config, `${this.currentDemoId}_${trialKey}`, trialKey);
                }
                
                // Process each route
                for (let i = 0; i < routes.length; i++) {
                    if (!this.isRunning) break;
                    while (this.isPaused) {
                        await this.delay(100);
                    }
                    
                    const route = routes[i];
                    this.currentProgress.route = i + 1;
                    this.currentProgress.status = `Setting up route ${i + 1}...`;
                    this.updateDetailedProgressUI();
                    
                    // Generate disruptions for this trial-route if per-trial-route scope (only if not using config-saved)
                    if (!hasConfigDisruptions && generationScope === 'per-trial-route') {
                        const comboKey = `set_trial_${trial}_route_${i}`;
                        await this.setupDemoDisruptions(config, `${this.currentDemoId}_${comboKey}`, comboKey);
                    }
                    
                    // Set active disruptions based on scope
                    await this.activateDisruptionSet(generationScope, trial, i);
                    
                    await this.processRouteWithProgress(route, config, trial);
                    await this.delay(config.stepDelay || 2000);
                }
            }

            if (this.isRunning) {
                this.currentProgress.status = '✅ Demo completed!';
                this.updateDetailedProgressUI();
                showUpdateToast('✅ Demo completed!', 'success');
                
                // Clear routes from map
                if (typeof clearRoutes === 'function') {
                    clearRoutes();
                }
                
                // Cleanup demo disruptions (only if we generated them at runtime)
                if (this.currentDemoId) {
                    await this.cleanupDemoDisruptions(this.currentDemoId);
                }
                
                // Show results summary after a short delay
                setTimeout(() => {
                    this.showResultsSummary();
                }, 500);
            }

        } catch (error) {
            console.error('Demo error:', error);
            this.currentProgress.status = `❌ Error: ${error.message}`;
            this.updateDetailedProgressUI();
            showUpdateToast('Demo failed: ' + error.message, 'error');
        } finally {
            this.isRunning = false;
            this.currentDemo = null;
            this.currentDemoId = null;  // Reset demoId
            this.demoDisruptionDir = null;
        }
    },
    
    /**
     * Setup demo-specific disruptions by generating files via API
     * @param {Object} config - Demo configuration
     * @param {string} demoId - Unique ID for this demo run
     * @param {string} setKey - Key to store this disruption set (e.g., 'all', 'trial_0', 'route_1', 'trial_0_route_1')
     */
    async setupDemoDisruptions(config, demoId, setKey = 'all') {
        const disruptions = config.disruptions || {};
        const mode = disruptions.mode || config.disruptionMode || 'none';
        
        if (mode === 'none') {
            this.demoDisruptionDir = null;
            console.log('📍 Demo running without disruptions');
            return;
        }
        
        const scopeLabel = setKey === 'all' ? '' : ` (${setKey})`;
        this.currentProgress.status = `Generating demo disruptions${scopeLabel}...`;
        this.updateDetailedProgressUI();
        
        try {
            // NEW: Use random matched edges from existing CSV files
            const severityMin = disruptions.severityMin || 0;
            const severityMax = disruptions.severityMax || 1;
            
            // Determine counts based on mode
            let flowCount = 0;
            let incidentCount = 0;
            
            if (mode === 'flow' || mode === 'both' || mode === 'random-both') {
                flowCount = disruptions.randomFlowCount || 5;
            }
            if (mode === 'incidents' || mode === 'both' || mode === 'random-both') {
                incidentCount = disruptions.randomIncidentCount || 3;
            }
            
            // Build request for new API
            const requestBody = {
                demo_id: demoId,
                use_random_edges: true,  // NEW: Use matched edges from existing CSVs
                flow_count: flowCount,
                incident_count: incidentCount,
                severity_min: severityMin,
                severity_max: severityMax
            };
            
            // Add custom disruption items if any (uses legacy snap-to-edge mode)
            if (disruptions.customItems && disruptions.customItems.length > 0) {
                requestBody.use_random_edges = false;
                
                const flowData = [];
                const incidentData = [];
                
                for (const item of disruptions.customItems) {
                    if (item.type === 'flow') {
                        flowData.push({
                            lat: item.lat,
                            lng: item.lng,
                            severity: item.severity || 0.5
                        });
                    } else if (item.type === 'incident') {
                        incidentData.push({
                            lat: item.lat,
                            lng: item.lng,
                            severity: item.severity || 0.5,
                            type: item.incidentType || 'construction'
                        });
                    }
                }
                
                requestBody.flow_data = flowData;
                requestBody.incident_data = incidentData;
            }
            
            // Call API to create disruption files
            const response = await fetch('/api/demo/disruptions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Store this disruption set for later activation
                this.disruptionSets = this.disruptionSets || {};
                this.disruptionSets[setKey] = {
                    demoId: demoId,
                    disruptionDir: result.disruption_dir,
                    disruptions: result.disruptions || { flow: [], incidents: [] },
                    flowCount: result.flow_count,
                    incidentCount: result.incident_count
                };
                
                console.log(`📍 Demo disruptions created for ${setKey}:`, result);
                console.log(`   Flow: ${result.flow_count}, Incidents: ${result.incident_count}`);
                
                // If this is the 'all' scope or first set, activate it immediately
                if (setKey === 'all') {
                    this.activateDisruptionSet('all', 0, 0);
                }
            } else {
                console.warn('⚠️ Failed to create demo disruptions:', result.error);
            }
            
        } catch (error) {
            console.error('Error setting up demo disruptions:', error);
        }
    },
    
    /**
     * Activate a disruption set from config - writes to temp files and stores in disruptionSets
     * @param {string} setKey - The disruption set key (e.g., 'set_all', 'set_trial_0', etc.)
     * @param {Object} setData - The disruption data { flow: [...], incidents: [...] }
     * @param {string} demoId - The demo ID for file naming
     */
    async activateConfigDisruptionSet(setKey, setData, demoId) {
        try {
            // Write the disruption data to temp files via API
            const response = await fetch('/api/demo/disruptions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    demo_id: `${demoId}_${setKey}`,
                    use_random_edges: false,  // Use custom locations from config
                    flow_data: setData.flow || [],
                    incident_data: setData.incidents || []
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Store in our runtime disruption sets
                this.disruptionSets[setKey] = {
                    disruptionDir: result.disruption_dir,
                    demoId: `${demoId}_${setKey}`,
                    disruptions: {
                        flow: setData.flow || [],
                        incidents: setData.incidents || []
                    }
                };
                console.log(`📦 Activated config disruption set: ${setKey} -> ${result.disruption_dir}`);
            } else {
                console.warn(`⚠️ Failed to activate config disruption set ${setKey}:`, result.error);
            }
        } catch (error) {
            console.error(`❌ Error activating config disruption set ${setKey}:`, error);
        }
    },
    
    /**
     * Activate the appropriate disruption set based on scope
     * @param {string} scope - Generation scope ('all', 'per-trial', 'per-route', 'per-trial-route')
     * @param {number} trialIndex - Current trial index
     * @param {number} routeIndex - Current route index
     */
    async activateDisruptionSet(scope, trialIndex, routeIndex) {
        // Determine set key based on scope
        let setKey;
        switch (scope) {
            case 'all':
                setKey = 'set_all';
                break;
            case 'per-trial':
                setKey = `set_trial_${trialIndex}`;
                break;
            case 'per-route':
                setKey = `set_route_${routeIndex}`;
                break;
            case 'per-trial-route':
                setKey = `set_trial_${trialIndex}_route_${routeIndex}`;
                break;
            default:
                setKey = 'set_all';
        }
        
        // Use runtime-generated disruption sets
        if (!this.disruptionSets) return;
        
        const disruptionSet = this.disruptionSets[setKey];
        if (disruptionSet) {
            this.demoDisruptionDir = disruptionSet.disruptionDir;
            window.demoDisruptionDir = disruptionSet.disruptionDir;
            
            // Convert API format (flow/incidents) to display format (flowSegments/incidents)
            const disruptions = disruptionSet.disruptions || {};
            this.generatedDisruptions = {
                incidents: (disruptions.incidents || []).map(d => ({
                    ...d,
                    source_lng: d.source_lon || d.source_lng,
                    target_lng: d.target_lon || d.target_lng,
                    incident_type: d.type || d.incident_type || 'Incident',
                    severity: d.criticality === 'critical' ? 'Heavy' : 
                              d.criticality === 'major' ? 'Medium' : 'Light'
                })),
                flowSegments: (disruptions.flow || []).map(d => ({
                    ...d,
                    source_lng: d.source_lon || d.source_lng,
                    target_lng: d.target_lon || d.target_lng,
                    incident_type: 'Congestion',
                    severity: d.jam_factor > 7 ? 'Heavy' : 
                              d.jam_factor > 4 ? 'Medium' : 'Light',
                    current_speed: d.speed_kph,
                    free_flow_speed: d.free_flow_kph
                }))
            };
            
            console.log(`🔄 Activated disruption set: ${setKey}`);
            console.log(`   Incidents: ${this.generatedDisruptions.incidents.length}, Flow: ${this.generatedDisruptions.flowSegments.length}`);
            
            // Update current preview set and refresh UI
            this.currentPreviewSet = setKey;
            
            // Update map visualization to show current disruptions
            this.showGeneratedDisruptions(true, true);
            
            // Update the disruption preview panel
            this.showDisruptionSetsPreview();
        } else {
            console.warn(`⚠️ Disruption set not found for key: ${setKey}`);
        }
    },
    
    /**
     * Cleanup demo disruption files after demo completes
     */
    async cleanupDemoDisruptions(demoId) {
        try {
            // Clean up all disruption sets
            if (this.disruptionSets) {
                for (const [setKey, setData] of Object.entries(this.disruptionSets)) {
                    if (setData.demoId) {
                        try {
                            await fetch(`/api/demo/disruptions/${setData.demoId}`, { method: 'DELETE' });
                        } catch (e) {
                            console.debug(`Could not cleanup disruption set ${setKey}:`, e);
                        }
                    }
                }
                this.disruptionSets = {};
            }
            
            // Also try to cleanup the base demoId
            await fetch(`/api/demo/disruptions/${demoId}`, { method: 'DELETE' });
            
            window.demoDisruptionDir = null;
            this.demoDisruptionDir = null;
            this.hideGeneratedDisruptions();
            console.log('🧹 Demo disruptions cleaned up');
        } catch (error) {
            console.warn('Could not cleanup demo disruptions:', error);
        }
    },

    async processRouteWithProgress(route, config, trialIndex) {
        // Set start location
        this.currentProgress.status = `Setting start: ${route.start.name}`;
        this.updateDetailedProgressUI();
        
        if (typeof handleOSMStartLocationPin === 'function') {
            await handleOSMStartLocationPin(route.start.lat, route.start.lng);
        }
        await this.delay(1000);

        // Set destination
        this.currentProgress.status = `Setting destination: ${route.end.name}`;
        this.updateDetailedProgressUI();
        
        if (typeof handleOSMDestLocationPin === 'function') {
            await handleOSMDestLocationPin(route.end.lat, route.end.lng);
        }
        await this.delay(1000);

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

        await this.delay(500);

        // Determine TAU values to test based on scope
        const tauScope = config.sequence?.tauGenerationScope || 'all';
        let tauValuesToTest;
        
        switch (tauScope) {
            case 'per-trial':
                // For per-trial, route has all trial TAUs, pick the one for this trial
                tauValuesToTest = [(route.tauValues || [])[trialIndex] || 0.5];
                break;
            case 'per-trial-route':
                // For per-trial-route, route has TAUs for each trial, pick the one for this trial
                tauValuesToTest = [(route.tauValues || [])[trialIndex] || 0.5];
                break;
            case 'all':
            case 'per-route':
            default:
                // For 'all' and 'per-route', route has single TAU, use all values provided
                tauValuesToTest = route.tauValues || [0.5];
                break;
        }
        
        this.currentProgress.totalTaus = tauValuesToTest.length;
        
        for (let tauIdx = 0; tauIdx < tauValuesToTest.length; tauIdx++) {
            if (!this.isRunning) break;
            while (this.isPaused) {
                await this.delay(100);
            }
            
            const tau = tauValuesToTest[tauIdx];
            this.currentProgress.tauIndex = tauIdx + 1;
            this.currentProgress.currentTau = tau;

            // Test each algorithm with this tau
            for (const algo of algorithms) {
                if (!this.isRunning) break;
                while (this.isPaused) {
                    await this.delay(100);
                }

                // Skip redundant DHL runs - DHL doesn't use TAU so only run once (on first tau iteration)
                if (algo === 'dhl' && tauIdx > 0) {
                    continue;
                }

                // DHL uses default 0.5, HC2L uses the specified tau
                const effectiveTau = algo === 'hc2l' ? tau : 0.5;
                
                this.currentProgress.algorithm = algo.toUpperCase();
                this.currentProgress.currentTau = effectiveTau;
                this.currentProgress.status = `Testing ${algo.toUpperCase()} with τ = ${effectiveTau.toFixed(2)}`;
                this.updateDetailedProgressUI();
                
                // Set algorithm
                document.querySelector(`input[name="algorithm"][value="${algo}"]`)?.click();
                
                // Set tau value
                const thresholdInput = document.getElementById('threshold-input');
                if (thresholdInput) {
                    thresholdInput.value = effectiveTau;
                    thresholdInput.dispatchEvent(new Event('input'));
                }

                await this.delay(300);

                // Calculate route
                if (typeof computeRouteBasedOnSelection === 'function') {
                    await computeRouteBasedOnSelection();
                }

                // Capture result with the effective tau used
                await this.delay(500);
                const result = this.captureCurrentResult(algo, effectiveTau, route, trialIndex);
                if (result) {
                    console.log(`✅ Captured ${algo.toUpperCase()} result:`, {
                        distance: result.metrics.displayDistance,
                        distanceKm: result.metrics.distanceKm,
                        tau: result.tau,
                        route: result.route
                    });
                    this.currentProgress.lastResult = result;
                    this.currentProgress.results.push(result);
                }
                
                this.updateDetailedProgressUI();

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

            // Read from Algorithm Metrics panel elements with improved extraction
            const getMetricValue = (id, stripUnits = false) => {
                const el = document.getElementById(id);
                if (el) {
                    let text = el.textContent.trim();
                    if (text === '--' || text === '-- sec' || text === '-- ms' || text === '-- edges' || text.startsWith('--')) {
                        return null;
                    }
                    // Strip common unit suffixes if requested
                    if (stripUnits) {
                        text = text.replace(/\s*(sec|ms|edges|km|m|MB|nodes|units)$/i, '').trim();
                    }
                    return text;
                }
                return null;
            };

            // Get numeric value from an element
            const getNumericValue = (id) => {
                const text = getMetricValue(id, true);
                if (text === null) return null;
                const num = parseFloat(text.replace(/[^\d.-]/g, ''));
                return isNaN(num) ? null : num;
            };

            // Algorithm Metrics panel elements
            result.metrics.algorithm = getMetricValue('metrics-algorithm');
            result.metrics.queryTime = getMetricValue('metrics-query-time');
            result.metrics.queryTimeNum = getNumericValue('metrics-query-time');
            result.metrics.baselineEta = getMetricValue('metrics-baseline-eta');
            result.metrics.actualEta = getMetricValue('metrics-actual-eta');
            result.metrics.timeImpact = getMetricValue('metrics-time-impact');
            result.metrics.disruptedEdges = getMetricValue('metrics-disrupted-edges');
            
            // Distance - try multiple sources
            result.metrics.distance = getMetricValue('metrics-distance');
            result.metrics.distanceNum = getNumericValue('metrics-distance');
            result.metrics.pathLength = getMetricValue('metrics-path-length');
            result.metrics.edgeCount = getMetricValue('metrics-edge-count');
            result.metrics.labelingTime = getMetricValue('metrics-labeling-time');
            result.metrics.labelingSize = getMetricValue('metrics-labeling-size');
            result.metrics.calculatedDistance = getMetricValue('metrics-calculated-distance');
            result.metrics.calculatedDistanceNum = getNumericValue('metrics-calculated-distance');

            // Also try main route display elements
            const routeDistance = document.getElementById('route-distance')?.textContent?.trim();
            const routeEta = document.getElementById('route-eta')?.textContent?.trim();
            if (routeDistance && routeDistance !== '--') {
                result.metrics.displayDistance = routeDistance;
                // Extract numeric distance in km
                const kmMatch = routeDistance.match(/([\d.]+)\s*km/i);
                if (kmMatch) {
                    result.metrics.distanceKm = parseFloat(kmMatch[1]);
                }
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

    updateDetailedProgressUI() {
        const container = document.getElementById('demo-runner-progress-detail');
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
                <!-- Demo Name -->
                <div class="text-center">
                    <h3 class="font-bold text-lg text-gray-800">${p.configName || 'Demo'}</h3>
                </div>

                <!-- Overall Progress - More Precise -->
                <div class="bg-white rounded-xl p-3 border border-gray-200 shadow-sm">
                    <div class="flex justify-between mb-1">
                        <span class="text-xs font-semibold text-gray-600">Overall Progress</span>
                        <span class="text-xs font-bold text-amber-600">${overallProgress.toFixed(1)}%</span>
                    </div>
                    <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div class="h-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all duration-500 ease-out" 
                             style="width: ${overallProgress}%"></div>
                    </div>
                    <div class="text-xs text-gray-500 mt-1 text-center">${p.status || 'Initializing...'}</div>
                </div>

                <!-- Detailed Progress Grid - Compact -->
                <div class="grid grid-cols-4 gap-2">
                    <div class="bg-blue-50 rounded-lg p-2 border border-blue-200 text-center">
                        <div class="text-[10px] text-blue-600 uppercase">Trial</div>
                        <div class="text-sm font-bold text-blue-800">${p.trial}/${p.totalTrials}</div>
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
                        ${renderMetric('Labeling Time', p.lastResult.metrics.labelingTime, 'text-amber-700')}
                        ${renderMetric('Labeling Size', p.lastResult.metrics.labelingSize, 'text-lime-700')}
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
        
        // Each route has multiple sub-steps:
        // 1. Setting start (5%)
        // 2. Setting destination (5%)
        // 3. Setting algorithm (5%)
        // 4. For each tau: setting tau (10%), computing (50%), capturing (30%) = 90% divided among taus
        // Total per route: 15% + (85% / numTaus per tau step)
        
        const totalTaus = p.totalTaus || 1;
        const stepsPerRoute = 3 + (totalTaus * 3); // 3 setup steps + 3 steps per tau
        const totalSteps = p.totalTrials * p.totalRoutes * stepsPerRoute;
        
        // Calculate completed steps
        const completedTrials = (p.trial - 1) * p.totalRoutes * stepsPerRoute;
        const completedRoutes = (p.route - 1) * stepsPerRoute;
        const completedTauSteps = (p.tauIndex - 1) * 3 + (p.subStep || 0);
        
        // Add current progress within the route (3 setup steps + tau progress)
        const routeProgress = p.setupStep || 0; // 0-3 for setup steps
        
        const completedSteps = completedTrials + completedRoutes + routeProgress + completedTauSteps;
        
        return Math.min(100, (completedSteps / totalSteps) * 100);
    },

    // Toggle incident display during demo
    async toggleIncidents(checked) {
        const adminToggle = document.getElementById('show-active-incidents');
        if (adminToggle) {
            adminToggle.checked = checked;
            adminToggle.dispatchEvent(new Event('change'));
        }
        
        // Also call the handler directly
        if (typeof handleActiveIncidentsToggle === 'function') {
            await handleActiveIncidentsToggle(checked, { silent: true });
        }
    },

    // Toggle flow overlay during demo
    async toggleFlowOverlay(checked) {
        const adminToggle = document.getElementById('show-traffic-overlay');
        if (adminToggle) {
            adminToggle.checked = checked;
            adminToggle.dispatchEvent(new Event('change'));
        }
        
        // Also call the handler directly
        if (typeof handleTrafficOverlayToggle === 'function') {
            await handleTrafficOverlayToggle(checked, { silent: true });
        }
    },

    // Apply disruption mode from config
    async applyDisruptionMode(mode) {
        console.log('🚦 Applying disruption mode:', mode);
        
        // Set the radio button
        const disruptionRadio = document.querySelector(`input[name="dataset"][value="${mode}"]`);
        if (disruptionRadio) {
            disruptionRadio.click();
        }

        // Also update the checkboxes in Demo Runner
        const incidentCheckbox = document.getElementById('demo-show-incidents');
        const flowCheckbox = document.getElementById('demo-show-flow');

        switch (mode) {
            case 'both':
                if (incidentCheckbox) incidentCheckbox.checked = true;
                if (flowCheckbox) flowCheckbox.checked = true;
                await this.toggleIncidents(true);
                await this.toggleFlowOverlay(true);
                break;
            case 'incidents':
                if (incidentCheckbox) incidentCheckbox.checked = true;
                if (flowCheckbox) flowCheckbox.checked = false;
                await this.toggleIncidents(true);
                await this.toggleFlowOverlay(false);
                break;
            case 'flow':
                if (incidentCheckbox) incidentCheckbox.checked = false;
                if (flowCheckbox) flowCheckbox.checked = true;
                await this.toggleIncidents(false);
                await this.toggleFlowOverlay(true);
                break;
            case 'none':
            default:
                if (incidentCheckbox) incidentCheckbox.checked = false;
                if (flowCheckbox) flowCheckbox.checked = false;
                await this.toggleIncidents(false);
                await this.toggleFlowOverlay(false);
                break;
        }
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
        const incidentCount = config.disruptions?.randomIncidentCount || 5;
        const flowCount = config.disruptions?.randomFlowCount || 5;
        const severityMin = config.disruptions?.severityMin || 0.3;
        const severityMax = config.disruptions?.severityMax || 0.9;
        
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

    // Demo disruption layer group for map display
    demoDisruptionLayers: [],

    // Show generated disruptions on map - mirrors DemoCreator.displayDisruptionsOnMap approach
    async showGeneratedDisruptions(showIncidents = true, showFlow = true) {
        console.log('🗺️ showGeneratedDisruptions called:', { showIncidents, showFlow });
        console.log('   Current disruption data:', {
            incidentCount: this.generatedDisruptions?.incidents?.length || 0,
            flowCount: this.generatedDisruptions?.flowSegments?.length || 0
        });
        
        // Clear existing demo disruption layers
        this.clearDemoDisruptionLayers();
        
        // Get map reference - try multiple options
        const mapRef = window.map || (typeof map !== 'undefined' ? map : null);
        
        if (!mapRef) {
            console.warn('❌ Map not available for disruption display');
            return;
        }
        
        console.log('✅ Map reference obtained, adding layers...');
        
        // Color scheme matching traffic-visualization.js
        const flowColors = {
            heavy: { color: '#ef4444', weight: 6, opacity: 0.85 },   // Red - Heavy traffic
            medium: { color: '#f59e0b', weight: 5, opacity: 0.75 },  // Amber - Medium traffic
            light: { color: '#10b981', weight: 4, opacity: 0.65 }    // Green - Light traffic
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
        if (showFlow && this.generatedDisruptions.flowSegments && this.generatedDisruptions.flowSegments.length > 0) {
            this.generatedDisruptions.flowSegments.forEach((f, i) => {
                const sourceLat = parseFloat(f.source_lat);
                const sourceLng = parseFloat(f.source_lng || f.source_lon);
                const targetLat = parseFloat(f.target_lat);
                const targetLng = parseFloat(f.target_lng || f.target_lon);
                
                if (isNaN(sourceLat) || isNaN(sourceLng) || isNaN(targetLat) || isNaN(targetLng)) {
                    console.warn('Skipping flow segment with invalid coordinates:', f);
                    return;
                }
                
                // Determine severity
                const jamFactor = parseFloat(f.jam_factor) || 0;
                let severity = f.severity || (jamFactor >= 7 ? 'Heavy' : jamFactor >= 4 ? 'Medium' : 'Light');
                
                let style;
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
                
                const polyline = L.polyline([
                    [sourceLat, sourceLng],
                    [targetLat, targetLng]
                ], {
                    color: style.color,
                    weight: style.weight,
                    opacity: style.opacity,
                    className: 'demo-disruption-flow'
                });
                
                // Create popup
                const popup = typeof PopupStyles !== 'undefined' ? 
                    PopupStyles.createTrafficPopup({
                        road_name: f.road_name || 'Unknown Road',
                        incident_type: 'Congestion',
                        severity: severity,
                        speed_kph: f.speed_kph || f.current_speed || 0,
                        free_flow_kph: f.free_flow_kph || 50,
                        jam_factor: jamFactor,
                        is_closed: false
                    }) :
                    `<div class="popup-content">
                        <b>🚦 Traffic Congestion</b><br>
                        <b>Road:</b> ${f.road_name || 'Unknown Road'}<br>
                        <b>Severity:</b> <span style="color: ${style.color}">${severity}</span><br>
                        <b>Jam Factor:</b> ${jamFactor.toFixed(1)} / 10
                    </div>`;
                
                polyline.bindPopup(popup);
                
                // Hover effects
                polyline.on('mouseover', function() {
                    this.setStyle({ weight: style.weight + 2, opacity: Math.min(style.opacity + 0.2, 1) });
                });
                polyline.on('mouseout', function() {
                    this.setStyle({ weight: style.weight, opacity: style.opacity });
                });
                
                polyline.addTo(mapRef);
                this.demoDisruptionLayers.push(polyline);
            });
            
            console.log(`✅ Added ${this.generatedDisruptions.flowSegments.length} flow segments to map`);
        }
        
        // Add incident markers with polylines
        if (showIncidents && this.generatedDisruptions.incidents && this.generatedDisruptions.incidents.length > 0) {
            this.generatedDisruptions.incidents.forEach((inc, i) => {
                const sourceLat = parseFloat(inc.source_lat);
                const sourceLng = parseFloat(inc.source_lng || inc.source_lon);
                const targetLat = parseFloat(inc.target_lat);
                const targetLng = parseFloat(inc.target_lng || inc.target_lon);
                
                if (isNaN(sourceLat) || isNaN(sourceLng) || isNaN(targetLat) || isNaN(targetLng)) {
                    console.warn('Skipping incident with invalid coordinates:', inc);
                    return;
                }
                
                // Determine color based on criticality
                const criticality = (inc.criticality || inc.incident_criticality || 'minor').toLowerCase();
                let fillColor = '#f59e0b'; // amber - default
                let severity = 'Medium';
                
                if (criticality === 'critical') {
                    fillColor = '#dc2626'; // dark red
                    severity = 'Heavy';
                } else if (criticality === 'major') {
                    fillColor = '#ef4444'; // red
                    severity = 'Medium';
                } else {
                    fillColor = '#f59e0b'; // amber
                    severity = 'Light';
                }
                
                // Draw polyline for incident edge
                const polyline = L.polyline([
                    [sourceLat, sourceLng],
                    [targetLat, targetLng]
                ], {
                    color: fillColor,
                    weight: 5,
                    opacity: 0.8,
                    dashArray: '10, 5',
                    className: 'demo-disruption-incident'
                });
                
                // Create popup
                const incidentType = inc.incident_type || inc.type || 'Incident';
                const popup = typeof PopupStyles !== 'undefined' ? 
                    PopupStyles.createIncidentPopup({
                        road_name: inc.road_name || 'Unknown Road',
                        incident_type: incidentType,
                        incident_criticality: criticality,
                        incident_road_closed: inc.incident_road_closed || false,
                        incident_description: inc.incident_description || inc.description || '',
                        highway_type: inc.highway_type || ''
                    }) :
                    `<div class="popup-content">
                        <b>${incidentIcons[incidentType] || incidentIcons.default} ${incidentType}</b><br>
                        <b>Road:</b> ${inc.road_name || 'Unknown Road'}<br>
                        <b>Criticality:</b> <span style="color: ${fillColor}">${criticality}</span>
                    </div>`;
                
                polyline.bindPopup(popup);
                
                // Hover effects
                polyline.on('mouseover', function() {
                    this.setStyle({ weight: 7, opacity: 0.95 });
                });
                polyline.on('mouseout', function() {
                    this.setStyle({ weight: 5, opacity: 0.8 });
                });
                
                polyline.addTo(mapRef);
                this.demoDisruptionLayers.push(polyline);
                
                // Add small circle marker at midpoint
                const midLat = (sourceLat + targetLat) / 2;
                const midLng = (sourceLng + targetLng) / 2;
                
                const icon = incidentIcons[incidentType] || incidentIcons.default;
                const marker = L.marker([midLat, midLng], {
                    icon: L.divIcon({
                        className: 'demo-incident-icon',
                        html: `<div style="background: ${fillColor}; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${icon}</div>`,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    })
                });
                
                marker.bindPopup(popup);
                marker.addTo(mapRef);
                this.demoDisruptionLayers.push(marker);
            });
            
            console.log(`✅ Added ${this.generatedDisruptions.incidents.length} incidents to map`);
        }
        
        console.log(`📊 Total demo disruption layers: ${this.demoDisruptionLayers.length}`);
    },
    
    // Clear demo disruption layers from map
    clearDemoDisruptionLayers() {
        if (this.demoDisruptionLayers && this.demoDisruptionLayers.length > 0) {
            const mapRef = window.map || (typeof map !== 'undefined' ? map : null);
            this.demoDisruptionLayers.forEach(layer => {
                if (mapRef) {
                    try {
                        mapRef.removeLayer(layer);
                    } catch (e) {
                        console.debug('Could not remove layer:', e);
                    }
                }
            });
            this.demoDisruptionLayers = [];
            console.log('🧹 Cleared demo disruption layers');
        }
    },
    
    /**
     * Hide generated disruptions from the map
     */
    hideGeneratedDisruptions() {
        this.clearDemoDisruptionLayers();
        // Also clear any existing disruption markers from the main system
        if (typeof clearDisruptionMarkers === 'function') {
            clearDisruptionMarkers();
        }
    },
    
    // Current disruption set key for display
    currentPreviewSet: null,

    /**
     * Show disruption sets preview panel (matching Demo Creator style)
     */
    showDisruptionSetsPreview() {
        const setsPanel = document.getElementById('demo-runner-disruption-sets');
        const buttonsContainer = document.getElementById('demo-runner-set-buttons');
        const previewContainer = document.getElementById('demo-runner-disruption-preview');
        
        if (!setsPanel || !buttonsContainer || !previewContainer) return;
        
        const sets = this.disruptionSets || {};
        const setKeys = Object.keys(sets);
        
        if (setKeys.length === 0) {
            setsPanel.classList.add('hidden');
            previewContainer.innerHTML = this.renderCurrentDisruptionList();
            return;
        }
        
        // Show sets panel and render buttons
        setsPanel.classList.remove('hidden');
        
        buttonsContainer.innerHTML = setKeys.map(key => `
            <button onclick="DemoRunner.selectDisruptionSet('${key}')"
                    class="px-2 py-1 text-xs rounded-lg transition-colors ${this.currentPreviewSet === key ? 
                        'bg-amber-600 text-white' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}">
                ${this.getSetLabel(key)}
            </button>
        `).join('');
        
        // Render current set details
        previewContainer.innerHTML = this.renderCurrentDisruptionList();
    },

    /**
     * Get friendly label for disruption set key
     */
    getSetLabel(key) {
        if (!key) return 'Unknown';
        
        if (key === 'set_all') return 'All Trials/Routes';
        
        const match = key.match(/set_trial_(\d+)(?:_route_(\d+))?/);
        if (match) {
            const trial = parseInt(match[1]) + 1;
            const route = match[2] !== undefined ? parseInt(match[2]) + 1 : null;
            if (route !== null) {
                return `T${trial}/R${route}`;
            }
            return `Trial ${trial}`;
        }
        
        const routeMatch = key.match(/set_route_(\d+)/);
        if (routeMatch) {
            return `Route ${parseInt(routeMatch[1]) + 1}`;
        }
        
        return key.replace('set_', '').replace(/_/g, ' ');
    },

    /**
     * Select a disruption set to view
     */
    selectDisruptionSet(setKey) {
        if (!this.disruptionSets || !this.disruptionSets[setKey]) return;
        
        this.currentPreviewSet = setKey;
        
        // Update generatedDisruptions to match the selected set
        const setData = this.disruptionSets[setKey];
        const disruptions = setData.disruptions || {};
        
        this.generatedDisruptions = {
            incidents: (disruptions.incidents || []).map(d => ({
                ...d,
                source_lng: d.source_lon || d.source_lng,
                target_lng: d.target_lon || d.target_lng,
                incident_type: d.type || d.incident_type || 'Incident',
                severity: d.criticality === 'critical' ? 'Heavy' : 
                          d.criticality === 'major' ? 'Medium' : 'Light'
            })),
            flowSegments: (disruptions.flow || []).map(d => ({
                ...d,
                source_lng: d.source_lon || d.source_lng,
                target_lng: d.target_lon || d.target_lng,
                incident_type: 'Congestion',
                severity: d.jam_factor > 7 ? 'Heavy' : 
                          d.jam_factor > 4 ? 'Medium' : 'Light',
                current_speed: d.speed_kph,
                free_flow_speed: d.free_flow_kph
            }))
        };
        
        // Refresh map display
        const showIncidents = document.getElementById('demo-show-incidents')?.checked ?? true;
        const showFlow = document.getElementById('demo-show-flow')?.checked ?? true;
        this.showGeneratedDisruptions(showIncidents, showFlow);
        
        // Refresh preview panel
        this.showDisruptionSetsPreview();
    },

    /**
     * Render the current disruption list for the preview panel
     */
    renderCurrentDisruptionList() {
        const flow = this.generatedDisruptions.flowSegments || [];
        const incidents = this.generatedDisruptions.incidents || [];
        
        if (flow.length === 0 && incidents.length === 0) {
            return `<div class="text-xs text-gray-500 text-center py-2">No disruptions loaded</div>`;
        }
        
        let html = '';
        
        // Flow disruptions
        if (flow.length > 0) {
            html += `<div class="text-xs font-semibold text-orange-600 mb-1">🚦 Traffic Flow (${flow.length})</div>`;
            html += `<div class="space-y-1 mb-2">`;
            flow.slice(0, 10).forEach((f, i) => {
                const jamFactor = parseFloat(f.jam_factor) || 0;
                const severityColor = jamFactor >= 7 ? 'text-red-600' : jamFactor >= 4 ? 'text-amber-600' : 'text-green-600';
                html += `
                    <div class="flex items-center justify-between bg-orange-50 rounded px-2 py-1 text-xs cursor-pointer hover:bg-orange-100"
                         onclick="DemoRunner.focusDisruption('flow', ${i})">
                        <span class="truncate flex-1 text-gray-700">${f.road_name || 'Unknown Road'}</span>
                        <span class="${severityColor} font-semibold ml-2">JF: ${jamFactor.toFixed(1)}</span>
                    </div>
                `;
            });
            if (flow.length > 10) {
                html += `<div class="text-xs text-gray-400 text-center">+${flow.length - 10} more...</div>`;
            }
            html += `</div>`;
        }
        
        // Incidents
        if (incidents.length > 0) {
            html += `<div class="text-xs font-semibold text-red-600 mb-1">🚨 Incidents (${incidents.length})</div>`;
            html += `<div class="space-y-1">`;
            incidents.slice(0, 10).forEach((inc, i) => {
                const criticality = (inc.criticality || inc.incident_criticality || 'minor').toLowerCase();
                const critColor = criticality === 'critical' ? 'text-red-700' : criticality === 'major' ? 'text-red-500' : 'text-amber-600';
                html += `
                    <div class="flex items-center justify-between bg-red-50 rounded px-2 py-1 text-xs cursor-pointer hover:bg-red-100"
                         onclick="DemoRunner.focusDisruption('incident', ${i})">
                        <span class="truncate flex-1 text-gray-700">${inc.road_name || 'Unknown Road'}</span>
                        <span class="${critColor} font-semibold ml-2">${inc.incident_type || inc.type || 'Incident'}</span>
                    </div>
                `;
            });
            if (incidents.length > 10) {
                html += `<div class="text-xs text-gray-400 text-center">+${incidents.length - 10} more...</div>`;
            }
            html += `</div>`;
        }
        
        return html;
    },

    /**
     * Focus map on a specific disruption
     */
    focusDisruption(type, index) {
        let item;
        if (type === 'flow') {
            item = this.generatedDisruptions.flowSegments?.[index];
        } else {
            item = this.generatedDisruptions.incidents?.[index];
        }
        
        if (!item || !window.map) return;
        
        // Calculate center of the disruption
        const lat = (parseFloat(item.source_lat) + parseFloat(item.target_lat)) / 2;
        const lng = (parseFloat(item.source_lng || item.source_lon) + parseFloat(item.target_lng || item.target_lon)) / 2;
        
        if (!isNaN(lat) && !isNaN(lng)) {
            map.setView([lat, lng], 16);
            console.log(`🔍 Focused on ${type} disruption at [${lat.toFixed(4)}, ${lng.toFixed(4)}]`);
        }
    },

    /**
     * Toggle incidents visibility on map (called from checkbox)
     */
    toggleIncidents(show) {
        console.log('🚨 Toggle incidents:', show);
        const showFlow = document.getElementById('demo-show-flow')?.checked ?? true;
        this.showGeneratedDisruptions(show, showFlow);
        // Also update the preview panel
        this.updateDisruptionPreview();
    },

    /**
     * Toggle flow overlay visibility on map (called from checkbox)
     */
    toggleFlowOverlay(show) {
        console.log('🚦 Toggle flow overlay:', show);
        const showIncidents = document.getElementById('demo-show-incidents')?.checked ?? true;
        this.showGeneratedDisruptions(showIncidents, show);
        // Also update the preview panel
        this.updateDisruptionPreview();
    },
    
    /**
     * Update the disruption preview panel based on current checkbox states
     */
    updateDisruptionPreview() {
        const showIncidents = document.getElementById('demo-show-incidents')?.checked ?? true;
        const showFlow = document.getElementById('demo-show-flow')?.checked ?? true;
        const previewContainer = document.getElementById('demo-runner-disruption-preview');
        
        if (!previewContainer) return;
        
        const flow = showFlow ? (this.generatedDisruptions.flowSegments || []) : [];
        const incidents = showIncidents ? (this.generatedDisruptions.incidents || []) : [];
        
        if (flow.length === 0 && incidents.length === 0) {
            if (!showIncidents && !showFlow) {
                previewContainer.innerHTML = '<div class="text-xs text-gray-500 text-center py-2">Disruption display disabled</div>';
            } else {
                previewContainer.innerHTML = '<div class="text-xs text-gray-500 text-center py-2">No disruptions to display</div>';
            }
            return;
        }
        
        previewContainer.innerHTML = this.renderCurrentDisruptionList();
    },
    
    // Apply disruption mode from config - NOW uses generated disruptions instead of HERE API
    async applyDemoDisruptions(config) {
        const mode = config.disruptions?.mode || config.disruptionMode || 'none';
        console.log('🚦 Applying demo disruptions:', mode);
        
        // Generate disruptions based on config
        this.generateDemoDisruptions(config);
        
        // Update the UI checkboxes
        const incidentCheckbox = document.getElementById('demo-show-incidents');
        const flowCheckbox = document.getElementById('demo-show-flow');
        
        let showIncidents = false;
        let showFlow = false;
        
        switch (mode) {
            case 'random-both':
            case 'both':
                showIncidents = true;
                showFlow = true;
                break;
            case 'random-incidents':
            case 'incidents':
                showIncidents = true;
                break;
            case 'random-flow':
            case 'flow':
                showFlow = true;
                break;
            case 'custom':
                showIncidents = true;
                break;
            case 'none':
            default:
                break;
        }
        
        // Update checkboxes
        if (incidentCheckbox) incidentCheckbox.checked = showIncidents;
        if (flowCheckbox) flowCheckbox.checked = showFlow;
        
        // Show the generated disruptions on map
        await this.showGeneratedDisruptions(showIncidents, showFlow);
        
        // Update the disruption preview panel
        this.showDisruptionSetsPreview();
        
        // Also set the dataset radio for the routing algorithm
        let datasetValue = 'none';
        if (showIncidents && showFlow) {
            datasetValue = 'both';
        } else if (showIncidents) {
            datasetValue = 'incidents';
        } else if (showFlow) {
            datasetValue = 'both'; // flow still needs 'both' for the algorithm
        }
        
        const disruptionRadio = document.querySelector(`input[name="dataset"][value="${datasetValue}"]`);
        if (disruptionRadio) {
            disruptionRadio.click();
        }
    },

    async processRoute(route, config) {
        // Update setup step for progress tracking
        this.currentProgress.setupStep = 0;
        this.currentProgress.status = `Setting start: ${route.start.name}`;
        this.updateDetailedProgressUI();
        
        // Set start location
        if (typeof handleOSMStartLocationPin === 'function') {
            await handleOSMStartLocationPin(route.start.lat, route.start.lng);
        }
        await this.delay(500);
        
        this.currentProgress.setupStep = 1;
        this.currentProgress.status = `Setting destination: ${route.end.name}`;
        this.updateDetailedProgressUI();

        // Set destination
        if (typeof handleOSMDestLocationPin === 'function') {
            await handleOSMDestLocationPin(route.end.lat, route.end.lng);
        }
        await this.delay(500);
        
        this.currentProgress.setupStep = 2;
        this.currentProgress.status = `Configuring algorithm and disruptions...`;
        this.updateDetailedProgressUI();

        // Set algorithm
        const algorithm = config.algorithm || 'hc2l';
        if (algorithm === 'both') {
            document.querySelector('input[name="algorithm"][value="hc2l"]')?.click();
        } else {
            document.querySelector(`input[name="algorithm"][value="${algorithm}"]`)?.click();
        }

        // Apply demo disruptions (generates custom disruptions instead of HERE API)
        await this.applyDemoDisruptions(config);
        
        this.currentProgress.setupStep = 3;
        this.updateDetailedProgressUI();

        await this.delay(300);

        // Test each tau value
        const tauValues = route.tauValues || [0.5];
        this.currentProgress.totalTaus = tauValues.length;
        
        for (let tauIdx = 0; tauIdx < tauValues.length; tauIdx++) {
            const tau = tauValues[tauIdx];
            if (!this.isRunning) break;
            while (this.isPaused) {
                await this.delay(100);
            }

            // Step 1: Setting tau
            this.currentProgress.tauIndex = tauIdx + 1;
            this.currentProgress.currentTau = tau;
            this.currentProgress.subStep = 0;
            this.currentProgress.status = `Setting τ = ${tau.toFixed(2)}`;
            this.updateDetailedProgressUI();
            
            const thresholdInput = document.getElementById('threshold-input');
            if (thresholdInput) {
                thresholdInput.value = tau;
                thresholdInput.dispatchEvent(new Event('input'));
            }

            await this.delay(200);

            // Step 2: Computing route
            this.currentProgress.subStep = 1;
            this.currentProgress.status = `Computing route (τ = ${tau.toFixed(2)})...`;
            this.updateDetailedProgressUI();
            
            if (typeof computeRouteBasedOnSelection === 'function') {
                await computeRouteBasedOnSelection();
            }

            // Step 3: Waiting for result
            this.currentProgress.subStep = 2;
            this.currentProgress.status = `Waiting for result...`;
            this.updateDetailedProgressUI();
            
            await this.delay(config.stepDelay || 2000);
            
            // Step 4: Result captured (will be done by outer loop)
            this.currentProgress.subStep = 3;
            this.updateDetailedProgressUI();
        }

        // Compare algorithms if needed
        if (config.algorithm === 'both') {
            this.currentProgress.status = 'Comparing HC2L vs DHL...';
            this.updateDetailedProgressUI();
            
            // Run with DHL
            document.querySelector('input[name="algorithm"][value="dhl"]')?.click();
            await this.delay(300);
            
            if (typeof computeRouteBasedOnSelection === 'function') {
                await computeRouteBasedOnSelection();
            }
            
            await this.delay(config.stepDelay || 2000);
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
        showUpdateToast('Demo paused', 'info');
    },

    resumeDemo() {
        this.isPaused = false;
        showUpdateToast('Demo resumed', 'info');
    },

    stopDemo() {
        this.isRunning = false;
        this.isPaused = false;
        showUpdateToast('Demo stopped', 'warning');
        this.showTab('main');
    },

    // ==========================================================================
    // RESULTS SUMMARY
    // ==========================================================================

    showResultsSummary() {
        // Use currentProgress.results instead of resultsHistory
        const results = this.currentProgress.results || [];
        console.log('📊 Showing results summary with', results.length, 'results');
        console.log('📊 Raw results:', JSON.stringify(results, null, 2));
        
        if (!results || results.length === 0) {
            showUpdateToast('No results to display', 'info');
            return;
        }

        // Calculate summary statistics - extract metrics from result objects
        const hc2lResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'HC2L');
        const dhlResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'DHL');

        console.log('📊 Results Summary Data:', {
            totalResults: results.length,
            hc2lCount: hc2lResults.length,
            dhlCount: dhlResults.length,
            sampleResult: results[0]
        });

        // Helper to extract numeric value from metrics - try multiple keys
        const getNumericMetric = (metrics, ...keys) => {
            for (const key of keys) {
                const value = metrics[key];
                if (value === null || value === undefined || value === '--' || value === 'N/A') continue;
                if (typeof value === 'number' && !isNaN(value)) return value;
                const str = String(value).replace(/[^\d.-]/g, '');
                const num = parseFloat(str);
                if (!isNaN(num)) return num;
            }
            return NaN;
        };

        // Calculate averages from metrics with detailed logging
        const calcAvg = (arr, ...metricKeys) => {
            const validValues = arr.map(r => {
                const metrics = r.metrics || {};
                return getNumericMetric(metrics, ...metricKeys);
            }).filter(v => !isNaN(v) && v > 0);
            
            const avg = validValues.length > 0 ? (validValues.reduce((a, b) => a + b, 0) / validValues.length).toFixed(2) : 'N/A';
            console.log(`   Distance extraction (${metricKeys.join('|')}): values=${validValues.join(',')}, avg=${avg}`);
            return avg;
        };

        const hc2lStats = {
            count: hc2lResults.length,
            avgDistance: calcAvg(hc2lResults, 'distanceKm', 'distanceNum', 'calculatedDistanceNum', 'displayDistance', 'distance', 'calculatedDistance'),
            avgQueryTime: calcAvg(hc2lResults, 'queryTimeNum', 'queryTime'),
            avgEta: calcAvg(hc2lResults, 'actualEta')
        };

        const dhlStats = {
            count: dhlResults.length,
            avgDistance: calcAvg(dhlResults, 'distanceKm', 'distanceNum', 'calculatedDistanceNum', 'displayDistance', 'distance', 'calculatedDistance'),
            avgQueryTime: calcAvg(dhlResults, 'queryTimeNum', 'queryTime'),
            avgEta: calcAvg(dhlResults, 'actualEta')
        };

        // Update the demo name in the results panel
        const demoNameEl = document.getElementById('demo-results-demo-name');
        if (demoNameEl) {
            demoNameEl.textContent = this.currentDemo?.name || 'Demo Results';
        }

        // Build statistics cards HTML
        let statsHTML = '';
        
        if (hc2lStats.count > 0) {
            statsHTML += `
                <div class="bg-blue-50 rounded-xl p-4 border border-blue-200">
                    <h4 class="font-bold text-blue-700 mb-2 flex items-center gap-1">
                        <span>🔵</span> HC2L
                    </h4>
                    <p class="text-sm text-gray-700"><strong>Routes:</strong> ${hc2lStats.count}</p>
                    <p class="text-sm text-gray-700"><strong>Avg Distance:</strong> ${hc2lStats.avgDistance}</p>
                    <p class="text-sm text-gray-700"><strong>Avg Query:</strong> ${hc2lStats.avgQueryTime} ms</p>
                </div>
            `;
        }
        
        if (dhlStats.count > 0) {
            statsHTML += `
                <div class="bg-green-50 rounded-xl p-4 border border-green-200">
                    <h4 class="font-bold text-green-700 mb-2 flex items-center gap-1">
                        <span>🟢</span> DHL
                    </h4>
                    <p class="text-sm text-gray-700"><strong>Routes:</strong> ${dhlStats.count}</p>
                    <p class="text-sm text-gray-700"><strong>Avg Distance:</strong> ${dhlStats.avgDistance}</p>
                    <p class="text-sm text-gray-700"><strong>Avg Query:</strong> ${dhlStats.avgQueryTime} ms</p>
                </div>
            `;
        }

        // If no stats for either, show a summary card
        if (!statsHTML) {
            statsHTML = `
                <div class="col-span-2 bg-gray-50 rounded-xl p-4 border border-gray-200 text-center">
                    <p class="text-gray-600">No algorithm-specific statistics available</p>
                </div>
            `;
        }

        // Update statistics cards
        const statsContainer = document.getElementById('demo-results-stats');
        if (statsContainer) {
            statsContainer.innerHTML = statsHTML;
        }

        // Update results count
        const countEl = document.getElementById('demo-results-count');
        if (countEl) {
            countEl.textContent = `(${results.length} total)`;
        }

        // Build collapsible results list HTML
        const resultsListHTML = results.map((r, i) => {
            const metrics = r.metrics || {};
            const algoColor = (r.algorithm || '').toUpperCase() === 'HC2L' ? 'blue' : 'green';
            const algoIcon = (r.algorithm || '').toUpperCase() === 'HC2L' ? '🔵' : '🟢';
            
            // Helper to get best display value for a metric
            const getDisplayValue = (...keys) => {
                for (const key of keys) {
                    const val = metrics[key];
                    if (val !== null && val !== undefined && val !== '--' && val !== 'N/A') {
                        return val;
                    }
                }
                return 'N/A';
            };
            
            // Extract key metrics for display - match Results History approach
            // Results History works, so use same order: displayDistance first (it has proper formatting)
            const distance = metrics.displayDistance || metrics.calculatedDistance || metrics.distance || 'N/A';
            const eta = getDisplayValue('actualEta', 'displayEta');
            const queryTime = getDisplayValue('queryTime');
            const pathLength = getDisplayValue('pathLength');
            const edgeCount = getDisplayValue('edgeCount');
            const labelingTime = getDisplayValue('labelingTime');
            const labelingSize = getDisplayValue('labelingSize');
            const disruptedEdges = getDisplayValue('disruptedEdges');
            const timeImpact = getDisplayValue('timeImpact');
            
            return `
                <div class="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden result-item" data-result-index="${i}">
                    <!-- Header (clickable to expand) -->
                    <div class="p-3 cursor-pointer hover:bg-gray-100 transition-colors flex justify-between items-center"
                         onclick="DemoRunner.toggleResultDetails(${i})">
                        <div class="flex items-center gap-2">
                            <span class="text-lg">${algoIcon}</span>
                            <span class="font-medium text-gray-800">#${i + 1} ${r.algorithm || 'Unknown'}</span>
                            <span class="text-xs bg-${algoColor}-100 text-${algoColor}-700 px-2 py-0.5 rounded">τ = ${r.tau?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div class="flex items-center gap-3">
                            <span class="text-sm text-gray-600 font-medium">📏 ${distance}</span>
                            <svg class="w-5 h-5 text-gray-400 transform transition-transform result-chevron" id="chevron-${i}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                            </svg>
                        </div>
                    </div>
                    
                    <!-- Collapsible Details -->
                    <div id="result-details-${i}" class="hidden border-t border-gray-200 bg-white p-3">
                        <div class="text-xs text-gray-500 mb-2">
                            <strong>Route:</strong> ${r.route || 'N/A'}
                        </div>
                        <div class="text-xs text-gray-500 mb-2">
                            <strong>Trial:</strong> ${r.trial || 'N/A'} | <strong>Timestamp:</strong> ${r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : 'N/A'}
                        </div>
                        
                        <div class="grid grid-cols-2 gap-2 text-xs">
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">Distance</div>
                                <div class="font-semibold text-gray-800">${distance}</div>
                            </div>
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">ETA</div>
                                <div class="font-semibold text-gray-800">${eta}</div>
                            </div>
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">Query Time</div>
                                <div class="font-semibold text-gray-800">${queryTime}</div>
                            </div>
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">Path Length</div>
                                <div class="font-semibold text-gray-800">${pathLength}</div>
                            </div>
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">Edge Count</div>
                                <div class="font-semibold text-gray-800">${edgeCount}</div>
                            </div>
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">Labeling Time</div>
                                <div class="font-semibold text-gray-800">${labelingTime}</div>
                            </div>
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">Labeling Size</div>
                                <div class="font-semibold text-gray-800">${labelingSize}</div>
                            </div>
                            <div class="bg-gray-50 rounded p-2">
                                <div class="text-gray-500">Disrupted Edges</div>
                                <div class="font-semibold text-gray-800">${disruptedEdges}</div>
                            </div>
                            ${timeImpact !== 'N/A' ? `
                            <div class="col-span-2 bg-amber-50 rounded p-2">
                                <div class="text-amber-700">Time Impact</div>
                                <div class="font-semibold text-amber-800">${timeImpact}</div>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Update results list
        const resultsListContainer = document.getElementById('demo-results-list');
        if (resultsListContainer) {
            resultsListContainer.innerHTML = resultsListHTML || '<p class="text-gray-500 text-center py-4">No results available</p>';
        }

        // Switch to results tab in the panel
        this.showTab('results');
    },

    /**
     * Toggle result details visibility (collapsible)
     */
    toggleResultDetails(index) {
        const detailsEl = document.getElementById(`result-details-${index}`);
        const chevronEl = document.getElementById(`chevron-${index}`);
        
        if (detailsEl) {
            const isHidden = detailsEl.classList.contains('hidden');
            detailsEl.classList.toggle('hidden');
            
            if (chevronEl) {
                chevronEl.classList.toggle('rotate-180', isHidden);
            }
        }
    },

    exportResults() {
        const results = this.currentProgress.results || [];
        if (!results || results.length === 0) {
            showUpdateToast('No results to export', 'warning');
            return;
        }

        const data = {
            exportedAt: new Date().toISOString(),
            demoName: this.currentDemo?.name || 'Demo Results',
            results: results
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `demo-results-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showUpdateToast('Results exported!', 'success');
    },

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    DemoRunner.init();
});

// Global exports
window.DemoRunner = DemoRunner;
window.openDemoRunner = () => DemoRunner.openPanel();
window.closeDemoRunner = () => DemoRunner.closePanel();
window.openDemoRunnerPanel = () => DemoRunner.openPanel();
window.closeDemoRunnerPanel = () => DemoRunner.closePanel();

console.log('✅ Demo Runner module loaded');
