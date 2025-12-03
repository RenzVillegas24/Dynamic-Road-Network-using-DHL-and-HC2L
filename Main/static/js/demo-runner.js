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
        flow: [],
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
        // Hide all tabs
        ['main', 'random-settings', 'running'].forEach(tab => {
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
        
        const trials = config.trials || 1;
        const routes = config.routes || [];
        
        // Check if this is a saved config with pre-generated disruptions
        const disruptionKey = config.disruptionKey || null;
        const hasSavedDisruptions = disruptionKey && config.disruptions?.savedSets;
        
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
        if (hasSavedDisruptions) {
            console.log(`📁 Using saved disruptions from: ${disruptionKey}`);
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
            
            // If we have saved disruptions, we don't need to generate new ones
            if (!hasSavedDisruptions) {
                // Generate demo-specific disruptions based on scope
                const demoId = `demo_${Date.now()}`;
                
                // Pre-generate disruption sets based on scope
                this.disruptionSets = {};  // Store disruption sets by key
                
                if (generationScope === 'all') {
                    // Generate one set for all trials/routes
                    await this.setupDemoDisruptions(config, demoId, 'set_all');
                } else if (generationScope === 'per-route') {
                    // Pre-generate disruption set for each route (used across all trials)
                    for (let i = 0; i < routes.length; i++) {
                        const routeKey = `set_route_${i}`;
                        await this.setupDemoDisruptions(config, `${demoId}_${routeKey}`, routeKey);
                    }
                }
                // For per-trial and per-trial-route, generate on-the-fly in the loop
            }
            
            // Run for each trial
            for (let trial = 0; trial < trials; trial++) {
                if (!this.isRunning) break;
                
                this.currentProgress.trial = trial + 1;
                
                // Generate disruptions for this trial if per-trial scope (only if not using saved)
                if (!hasSavedDisruptions && generationScope === 'per-trial') {
                    const demoId = `demo_${Date.now()}`;
                    const trialKey = `set_trial_${trial}`;
                    await this.setupDemoDisruptions(config, `${demoId}_${trialKey}`, trialKey);
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
                    
                    // Generate disruptions for this trial-route if per-trial-route scope (only if not using saved)
                    if (!hasSavedDisruptions && generationScope === 'per-trial-route') {
                        const demoId = `demo_${Date.now()}`;
                        const comboKey = `set_trial_${trial}_route_${i}`;
                        await this.setupDemoDisruptions(config, `${demoId}_${comboKey}`, comboKey);
                    }
                    
                    // Set active disruptions based on scope (pass disruptionKey for saved configs)
                    await this.activateDisruptionSet(generationScope, trial, i, disruptionKey);
                    
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
                
                // Cleanup demo disruptions
                await this.cleanupDemoDisruptions(demoId);
                
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
     * Activate the appropriate disruption set based on scope
     * @param {string} scope - Generation scope ('all', 'per-trial', 'per-route', 'per-trial-route')
     * @param {number} trialIndex - Current trial index
     * @param {number} routeIndex - Current route index
     * @param {string} disruptionKey - Optional: The disruption key from saved config
     */
    async activateDisruptionSet(scope, trialIndex, routeIndex, disruptionKey = null) {
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
        
        // If we have a saved config with disruption key, load from file system
        if (disruptionKey) {
            try {
                const response = await fetch(`/api/demo/disruption-path/${disruptionKey}/${setKey}`);
                const result = await response.json();
                
                if (result.success) {
                    this.demoDisruptionDir = result.disruption_dir;
                    window.demoDisruptionDir = result.disruption_dir;
                    console.log(`🔄 Loaded disruption set from saved config: ${setKey} -> ${result.disruption_dir}`);
                    return;
                }
            } catch (error) {
                console.warn(`⚠️ Could not load saved disruption set: ${error}`);
            }
        }
        
        // Fall back to runtime-generated disruption sets
        if (!this.disruptionSets) return;
        
        const disruptionSet = this.disruptionSets[setKey];
        if (disruptionSet) {
            this.demoDisruptionDir = disruptionSet.disruptionDir;
            window.demoDisruptionDir = disruptionSet.disruptionDir;
            this.generatedDisruptions = disruptionSet.disruptions;
            
            console.log(`🔄 Activated disruption set: ${setKey}`);
            
            // Update map visualization to show current disruptions
            this.showGeneratedDisruptions(true, true);
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

                this.currentProgress.algorithm = algo.toUpperCase();
                this.currentProgress.status = `Testing ${algo.toUpperCase()} with τ = ${tau.toFixed(2)}`;
                this.updateDetailedProgressUI();
                
                // Set algorithm
                document.querySelector(`input[name="algorithm"][value="${algo}"]`)?.click();
                
                // Set tau
                const thresholdInput = document.getElementById('threshold-input');
                if (thresholdInput) {
                    thresholdInput.value = tau;
                    thresholdInput.dispatchEvent(new Event('input'));
                }

                await this.delay(300);

                // Calculate route
                if (typeof computeRouteBasedOnSelection === 'function') {
                    await computeRouteBasedOnSelection();
                }

                // Capture result
                await this.delay(500);
                const result = this.captureCurrentResult(algo, tau, route, trialIndex);
                if (result) {
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
    
    /**
     * Hide generated disruptions from the map
     */
    hideGeneratedDisruptions() {
        if (typeof clearDisruptionMarkers === 'function') {
            clearDisruptionMarkers();
        }
        console.log('🧹 Cleared disruption markers from map');
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
        if (!results || results.length === 0) {
            showUpdateToast('No results to display', 'info');
            return;
        }

        // Calculate summary statistics
        const hc2lResults = results.filter(r => r.algorithm === 'hc2l' || r.algorithm === 'HC2L');
        const dhlResults = results.filter(r => r.algorithm === 'dhl' || r.algorithm === 'DHL');

        const calcAvg = (arr, key) => {
            const validValues = arr.map(r => parseFloat(r[key])).filter(v => !isNaN(v) && v > 0);
            return validValues.length > 0 ? (validValues.reduce((a, b) => a + b, 0) / validValues.length).toFixed(2) : 'N/A';
        };

        const hc2lStats = {
            count: hc2lResults.length,
            avgDistance: calcAvg(hc2lResults, 'displayDistance') || calcAvg(hc2lResults, 'distance'),
            avgTime: calcAvg(hc2lResults, 'time')
        };

        const dhlStats = {
            count: dhlResults.length,
            avgDistance: calcAvg(dhlResults, 'displayDistance') || calcAvg(dhlResults, 'distance'),
            avgTime: calcAvg(dhlResults, 'time')
        };

        // Build summary HTML
        let summaryHTML = `
            <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[10000]" id="demo-results-modal">
                <div class="bg-white rounded-lg shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
                    <div class="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4 flex justify-between items-center">
                        <h3 class="text-xl font-bold text-white">📊 Demo Results Summary</h3>
                        <button onclick="document.getElementById('demo-results-modal').remove()" class="text-white hover:text-gray-200 text-2xl">&times;</button>
                    </div>
                    <div class="p-6 overflow-y-auto max-h-[60vh]">
                        <div class="grid grid-cols-2 gap-4 mb-6">
                            ${hc2lStats.count > 0 ? `
                            <div class="bg-blue-50 rounded-lg p-4 border border-blue-200">
                                <h4 class="font-bold text-blue-700 mb-2">🔵 HC2L Results</h4>
                                <p class="text-sm text-gray-700"><strong>Routes:</strong> ${hc2lStats.count}</p>
                                <p class="text-sm text-gray-700"><strong>Avg Distance:</strong> ${hc2lStats.avgDistance} km</p>
                                <p class="text-sm text-gray-700"><strong>Avg Time:</strong> ${hc2lStats.avgTime} s</p>
                            </div>
                            ` : ''}
                            ${dhlStats.count > 0 ? `
                            <div class="bg-green-50 rounded-lg p-4 border border-green-200">
                                <h4 class="font-bold text-green-700 mb-2">🟢 DHL Results</h4>
                                <p class="text-sm text-gray-700"><strong>Routes:</strong> ${dhlStats.count}</p>
                                <p class="text-sm text-gray-700"><strong>Avg Distance:</strong> ${dhlStats.avgDistance} km</p>
                                <p class="text-sm text-gray-700"><strong>Avg Time:</strong> ${dhlStats.avgTime} s</p>
                            </div>
                            ` : ''}
                        </div>
                        
                        <h4 class="font-semibold text-gray-700 mb-3">📋 All Results (${results.length} total)</h4>
                        <div class="space-y-2 max-h-60 overflow-y-auto">
                            ${results.map((r, i) => `
                                <div class="bg-gray-50 rounded p-3 text-sm border">
                                    <div class="flex justify-between items-start">
                                        <span class="font-medium">#${i + 1} ${r.algorithm?.toUpperCase() || 'Unknown'}</span>
                                        <span class="text-xs text-gray-500">${r.routeLabel || ''}</span>
                                    </div>
                                    <div class="grid grid-cols-3 gap-2 mt-2 text-gray-600">
                                        <span>📏 ${r.displayDistance || r.distance || 'N/A'} km</span>
                                        <span>⏱️ ${r.time || 'N/A'} s</span>
                                        <span>🚗 ${r.hops || 'N/A'} hops</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div class="bg-gray-50 px-6 py-4 flex justify-end gap-3">
                        <button onclick="DemoRunner.exportResults()" class="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 text-sm">
                            📥 Export Results
                        </button>
                        <button onclick="document.getElementById('demo-results-modal').remove()" class="px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 text-sm">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if any
        document.getElementById('demo-results-modal')?.remove();
        
        // Add to document
        document.body.insertAdjacentHTML('beforeend', summaryHTML);
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
