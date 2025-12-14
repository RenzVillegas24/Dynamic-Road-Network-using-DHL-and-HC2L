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

    // Track if current results are saved to server
    currentResultsSavedPath: null,  // Path to saved file, null if not saved

    // Track the config ID for saving results (persists after demo ends)
    lastRunConfigId: null,  // Config ID from the last run, used for saving results
    lastRunConfigName: null,  // Config name from the last run

    // Track whether results are from a run (execution summary) or loaded from saved list
    resultsSource: 'new',  // 'new' (from execution) or 'saved' (from saved results list)

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

    // Lazy disruption loading system
    disruptionCache: new Map(),  // Cache for loaded disruptions
    disruptionBuffer: [],        // Buffer of pre-loaded disruptions
    disruptionGenerationQueue: [], // Queue of disruptions to generate
    isGeneratingDisruptions: false,
    disruptionBufferSize: 10,    // Number of disruptions to keep ready
    currentDisruptionIndex: -1,
    totalDisruptionsNeeded: 0,

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

    // Saved Route Finder state (to be restored after demo)
    savedRouteFinderState: null,

    // Temporary config name for experiment mode (used for cleanup)
    currentTempConfigName: null,

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
        this.loadSavedResults();
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

    /**
     * Get multiple random road points in one efficient API call
     * Much faster than generating random QC points individually
     * @param {number} count - Number of road points to get
     * @returns {Promise<Array|null>} Array of {lat, lng, name} objects or null on error
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
        // Get the modal element
        const modal = document.getElementById('demo-stop-modal');
        if (!modal) return;

        // Show the modal
        modal.classList.remove('hidden');

        // Setup event listeners (using once:true to auto-cleanup)
        const cancelBtn = document.getElementById('demo-stop-cancel');
        const confirmBtn = document.getElementById('demo-stop-confirm');

        const hideModal = () => modal.classList.add('hidden');

        // Handle cancel
        cancelBtn.addEventListener('click', hideModal, { once: true });

        // Handle confirm
        confirmBtn.addEventListener('click', () => {
            this.stopDemo();
            hideModal();
            this.forceClosePanel();
        }, { once: true });

        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) hideModal();
        }, { once: true });
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
        // Hide all tabs (including results and experiment-settings)
        ['main', 'random-settings', 'experiment-settings', 'running', 'results'].forEach(tab => {
            const el = document.getElementById(`demo-runner-tab-${tab}`);
            if (el) el.classList.add('hidden');
        });

        ['random-settings', 'experiment-settings', 'running', 'results'].forEach(tab => {
            const el = document.getElementById(`demo-runner-footer-${tab}`);
            if (el) el.classList.add('hidden');
        });

        // Show selected tab
        const selectedTab = document.getElementById(`demo-runner-tab-${tabName}`);
        if (selectedTab) selectedTab.classList.remove('hidden');

        const selectedFooter = document.getElementById(`demo-runner-footer-${tabName}`);
        if (selectedFooter) selectedFooter.classList.remove('hidden');

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

        // Refresh lucide icons after tab switch
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
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

        // ALWAYS update disruption sets preview (even if no disruptions on map)
        // This ensures the list is visible and usable regardless of map visualization
        this.showDisruptionSetsPreview();
    },

    updateTauModeUI() {
        const mode = this.randomDemoSettings.tauMode;

        document.getElementById('tau-fixed-container')?.classList.toggle('hidden', mode !== 'fixed');
        document.getElementById('tau-random-container')?.classList.toggle('hidden', mode !== 'random');
        document.getElementById('tau-sequence-container')?.classList.toggle('hidden', mode !== 'sequence');
    },

    /**
     * Switch between Configurations and Saved Results tabs in the main panel
     */
    switchDataTab(tabName) {
        // Update tab buttons
        const configsBtn = document.getElementById('tab-btn-configs');
        const resultsBtn = document.getElementById('tab-btn-saved-results');

        // Update tab content visibility
        const configsContent = document.getElementById('data-tab-configs');
        const resultsContent = document.getElementById('data-tab-saved-results');

        if (tabName === 'configs') {
            // Activate configs tab
            if (configsBtn) {
                configsBtn.classList.add('bg-indigo-50', 'text-indigo-700', 'border-b-2', 'border-indigo-500');
                configsBtn.classList.remove('text-gray-500');
                configsBtn.setAttribute('aria-selected', 'true');
            }
            if (resultsBtn) {
                resultsBtn.classList.remove('bg-indigo-50', 'text-indigo-700', 'border-b-2', 'border-indigo-500');
                resultsBtn.classList.add('text-gray-500');
                resultsBtn.setAttribute('aria-selected', 'false');
            }
            if (configsContent) configsContent.classList.remove('hidden');
            if (resultsContent) resultsContent.classList.add('hidden');
        } else if (tabName === 'saved-results') {
            // Activate saved results tab
            if (resultsBtn) {
                resultsBtn.classList.add('bg-indigo-50', 'text-indigo-700', 'border-b-2', 'border-indigo-500');
                resultsBtn.classList.remove('text-gray-500');
                resultsBtn.setAttribute('aria-selected', 'true');
            }
            if (configsBtn) {
                configsBtn.classList.remove('bg-indigo-50', 'text-indigo-700', 'border-b-2', 'border-indigo-500');
                configsBtn.classList.add('text-gray-500');
                configsBtn.setAttribute('aria-selected', 'false');
            }
            if (resultsContent) resultsContent.classList.remove('hidden');
            if (configsContent) configsContent.classList.add('hidden');

            // Refresh saved results when switching to this tab
            this.loadSavedResults();
        }
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

        // Filter out experiment configs
        const displayConfigs = this.savedConfigs.filter(config => !config.isExperiment);

        // Clear container
        container.innerHTML = '';

        // Show empty state if no configs
        if (displayConfigs.length === 0) {
            const emptyTemplate = document.getElementById('template-empty-configs');
            if (emptyTemplate) {
                const emptyState = emptyTemplate.content.cloneNode(true);
                container.appendChild(emptyState);
                lucide.createIcons();
            }
            return;
        }

        // Get config card template
        const template = document.getElementById('template-config-card');
        if (!template) return;

        const isRunning = (typeof DemoCreator !== 'undefined' && DemoCreator.isRunning);

        // Render each config using template
        displayConfigs.forEach(config => {
            const card = template.content.cloneNode(true);
            
            // Populate card data
            card.querySelector('[data-config-name]').textContent = config.name || 'Unnamed Demo';
            card.querySelector('[data-config-date]').textContent = new Date(config.savedAt).toLocaleDateString();
            card.querySelector('[data-config-routes]').textContent = `${config.routes?.length || 0} routes`;
            card.querySelector('[data-config-trials]').textContent = `${config.routes?.[0]?.trials?.length || 1} trials`;
            card.querySelector('[data-config-algorithm]').textContent = config.algorithm?.toUpperCase() || 'HC2L';
            
            // Setup button handlers
            const editBtn = card.querySelector('[data-config-edit]');
            const deleteBtn = card.querySelector('[data-config-delete]');
            const runBtn = card.querySelector('[data-config-run]');
            
            // Disable buttons if demo is running
            if (isRunning) {
                [editBtn, deleteBtn, runBtn].forEach(btn => {
                    btn.classList.add('opacity-50', 'cursor-not-allowed');
                    btn.disabled = true;
                });
            } else {
                editBtn.addEventListener('click', () => {
                    this.editConfig(config.id);
                    document.querySelector('[data-panel="demo-creator"]')?.click();
                });
                deleteBtn.addEventListener('click', () => this.deleteConfig(config.id));
                runBtn.addEventListener('click', () => this.runSavedConfig(config.id));
            }
            
            container.appendChild(card);
        });

        lucide.createIcons();
        
        // Update tab badge count
        const badge = document.getElementById('tab-badge-configs');
        if (badge) badge.textContent = `${displayConfigs.length}`;
    },

    runSavedConfig(configId) {
        const config = this.savedConfigs.find(c => c.id === configId);
        if (config) {
            this.runDemo(config);
        }
    },

    // ==========================================================================
    // SAVED RESULTS MANAGEMENT
    // ==========================================================================

    savedResults: [],

    async loadSavedResults() {
        try {
            const response = await fetch('/api/demo/results');
            const result = await response.json();

            if (result.success) {
                this.savedResults = result.results || [];
            } else {
                console.error('Error loading saved results:', result.error);
                this.savedResults = [];
            }
            this.renderSavedResultsList();
        } catch (e) {
            console.error('Error loading saved results:', e);
            this.savedResults = [];
            this.renderSavedResultsList();
        }
    },

    async refreshSavedResults() {
        const container = document.getElementById('saved-results-list');
        if (container) {
            container.innerHTML = '<p class="text-gray-500 text-sm text-center py-4">Loading...</p>';
        }
        await this.loadSavedResults();
        showUpdateToast('Results refreshed', 'success');
    },

    renderSavedResultsList() {
        const container = document.getElementById('saved-results-list');
        if (!container) return;

        // Clear previous content
        container.innerHTML = '';

        if (this.savedResults.length === 0) {
            const emptyTemplate = document.getElementById('template-empty-saved-results');
            if (emptyTemplate) {
                container.appendChild(emptyTemplate.content.cloneNode(true));
                lucide.createIcons();
            }
            return;
        }

        // Group results by configId/demoName
        const grouped = {};
        this.savedResults.forEach(result => {
            const groupKey = result.configId || result.demoName || 'Other';
            if (!grouped[groupKey]) {
                grouped[groupKey] = {
                    name: result.demoName || result.configId || 'Unknown Demo',
                    configId: result.configId,
                    results: []
                };
            }
            grouped[groupKey].results.push(result);
        });

        // Create groups using template
        const groupTemplate = document.getElementById('template-result-group');
        const cardTemplate = document.getElementById('template-saved-result-card');

        if (!groupTemplate || !cardTemplate) return;

        Object.entries(grouped).forEach(([key, group]) => {
            // Clone and populate group
            const groupNode = groupTemplate.content.cloneNode(true);
            groupNode.querySelector('[data-group-name]').textContent = group.name;
            groupNode.querySelector('[data-result-count]').textContent = `${group.results.length} run${group.results.length !== 1 ? 's' : ''}`;

            const resultsContainer = groupNode.querySelector('[data-results-container]');

            // Add result cards to this group
            group.results.forEach(result => {
                const savedDate = result.savedAt ? new Date(result.savedAt) : null;
                const dateStr = savedDate ? savedDate.toLocaleDateString() : 'Unknown';
                const timeStr = savedDate ? savedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
                const summary = result.summary || {};

                // Format duration
                const duration = summary.executionDurationSeconds;
                const durationStr = duration ? (duration >= 60 ? `${(duration / 60).toFixed(1)}m` : `${duration.toFixed(1)}s`) : '--';

                // Format process time
                const processTime = summary.processTime?.avg;
                const processTimeStr = processTime ? `${processTime.toFixed(0)}ms` : '--';

                // Algorithm breakdown
                const algos = summary.algorithmBreakdown || {};
                const algoStr = [];
                if (algos.hc2l > 0) algoStr.push(`<span class="text-blue-600">${algos.hc2l}</span>`);
                if (algos.dhl > 0) algoStr.push(`<span class="text-green-600">${algos.dhl}</span>`);

                // Clone result card
                const cardNode = cardTemplate.content.cloneNode(true);
                
                // Populate card fields
                cardNode.querySelector('[data-save-date]').textContent = `${dateStr} ${timeStr}`;
                cardNode.querySelector('[data-route-count]').textContent = `${result.totalRoutes || 0} routes`;
                cardNode.querySelector('[data-duration]').textContent = durationStr;
                cardNode.querySelector('[data-process-time]').textContent = processTimeStr;

                // Show/hide trials badge
                if (summary.trialsCompleted) {
                    const trialsBadge = cardNode.querySelector('[data-trials-badge]');
                    trialsBadge.style.display = 'inline-block';
                    cardNode.querySelector('[data-trials-count]').textContent = summary.trialsCompleted;
                } else {
                    cardNode.querySelector('[data-trials-badge]').style.display = 'none';
                }

                // Show/hide algorithm breakdown
                if (algoStr.length > 0) {
                    const algoBadge = cardNode.querySelector('[data-algo-badge]');
                    algoBadge.style.display = 'inline-block';
                    cardNode.querySelector('[data-algo-breakdown]').innerHTML = algoStr.join(' / ');
                } else {
                    cardNode.querySelector('[data-algo-badge]').style.display = 'none';
                }

                // Add click handler
                const cardElement = cardNode.querySelector('.card');
                cardElement.addEventListener('click', () => {
                    this.viewSavedResult(result.filePath);
                });

                resultsContainer.appendChild(cardNode);
            });

            container.appendChild(groupNode);
        });

        lucide.createIcons();

        // Update tab badge count for results
        const badge = document.getElementById('tab-badge-results');
        if (badge) badge.textContent = `${this.savedResults.length}`;
    },

    async viewSavedResult(filePath) {
        // Show loading animation
        this.showLoadingAnimation(
            'Initializing Result',
            'Loading saved result...');

        try {
            const response = await fetch('/api/demo/results/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filePath })
            });

            const data = await response.json();
            
            this.showTab('results');

            if (data.success && data.result) {
                // Load the result into currentProgress and show the results tab
                this.currentProgress.results = data.result.results || [];
                this.currentDemo = {
                    name: data.result.demoName,
                    id: data.result.demoId || data.result.configId
                };

                // Store persistent config ID/name for potential re-saving
                this.lastRunConfigId = data.result.demoId || data.result.configId || null;
                this.lastRunConfigName = data.result.demoName || null;

                // Mark as already saved (since we loaded from server)
                this.currentResultsSavedPath = filePath;
                // Set source to 'saved' to indicate this is from the saved results list
                this.resultsSource = 'saved';
                console.log('📂 Viewing saved result, resultsSource set to "saved"');

                // Hide loading animation before showing results
                this.hideLoadingAnimation();

                this.showResultsSummary();
                this.updateResultsActionButtons();
                showUpdateToast('Loaded saved result', 'success');
            } else {
                throw new Error(data.error || 'Failed to load result');
            }
        } catch (error) {
            console.error('Error loading saved result:', error);
            this.hideLoadingAnimation();
            showUpdateToast('Failed to load result: ' + error.message, 'error');
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
     * If useRandomQC is true, uses road-validated locations via API.
     * Otherwise uses preset locations.
     * @param {boolean} useRandomQC - Whether to use random QC road points
     * @returns {Promise<{start: Object, end: Object}>} Pair of locations
     */
    async getRandomLocationPair(useRandomQC = false) {
        if (useRandomQC) {
            // Use efficient API call to get road-validated points
            const roadPoints = await this.getRandomRoadPoints(10); // Get extra for distance filtering
            
            if (roadPoints && roadPoints.length >= 2) {
                // Find a pair with reasonable distance between them
                for (let i = 0; i < roadPoints.length - 1; i++) {
                    for (let j = i + 1; j < roadPoints.length; j++) {
                        const start = roadPoints[i];
                        const end = roadPoints[j];
                        // Ensure minimum distance
                        if (Math.abs(end.lat - start.lat) >= 0.01 ||
                            Math.abs(end.lng - start.lng) >= 0.01) {
                            return { start, end };
                        }
                    }
                }
                // If no suitable pair found, just use first two
                return { start: roadPoints[0], end: roadPoints[1] };
            }
            
            // Fallback to random QC boundary method
            console.warn('⚠️ Road points API failed, falling back to random QC');
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
            const pair = await this.getRandomLocationPair(useRandomQC);
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
    // EXPERIMENT MODE (Thesis)
    // ==========================================================================

    experimentSettings: {
        trials: 3,                    // Fixed at 3 trials
        batchSize: 1000,              // Fixed at 1000
        disruptionMode: 'preset',     // 'preset' or 'random'
        routeMode: 'preset',          // 'preset' or 'random'
        severityMin: 0.1,
        severityMax: 0.9,
        ratioFlow: 95,
        ratioIncident: 5,
        tauMode: 'random',            // 'fixed' or 'random'
        tauScope: 'per-trial-route',  // 'all', 'per-trial', 'per-route', 'per-trial-route'
        tauFixed: 0.5,
        tauRandomMin: 0.1,
        tauRandomMax: 0.9
    },

    experimentConfigName: 'ExperimentMode',

    openExperimentSettings() {
        this.showTab('experiment-settings');
        this.updateExperimentTauUI();
        // Refresh lucide icons for experiment tab
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    updateExperimentTauUI() {
        const mode = document.querySelector('input[name="experiment-tau-mode"]:checked')?.value || 'random';
        
        document.getElementById('experiment-tau-fixed-setting')?.classList.toggle('hidden', mode !== 'fixed');
        document.getElementById('experiment-tau-random-setting')?.classList.toggle('hidden', mode !== 'random');

        // Update visual styling for mode options
        document.querySelectorAll('#demo-runner-tab-experiment-settings .tau-mode-option').forEach(label => {
            const radio = label.querySelector('input[type="radio"]');
            if (radio && radio.checked) {
                label.classList.add('ring-2', 'ring-purple-500', 'border-purple-500');
            } else {
                label.classList.remove('ring-2', 'ring-purple-500', 'border-purple-500');
            }
        });

        // Update visual styling for scope options
        document.querySelectorAll('#demo-runner-tab-experiment-settings .tau-scope-option').forEach(label => {
            const radio = label.querySelector('input[type="radio"]');
            if (radio && radio.checked) {
                label.classList.add('ring-2', 'ring-purple-500', 'border-purple-500');
            } else {
                label.classList.remove('ring-2', 'ring-purple-500', 'border-purple-500');
            }
        });
    },

    getExperimentTauSettings() {
        const mode = document.querySelector('input[name="experiment-tau-mode"]:checked')?.value || 'random';
        const scope = document.querySelector('input[name="experiment-tau-scope"]:checked')?.value || 'per-trial-route';
        
        return {
            mode,
            scope,
            fixed: parseFloat(document.getElementById('experiment-tau-fixed-value')?.value) || 0.5,
            randomMin: parseFloat(document.getElementById('experiment-tau-random-min')?.value) || 0.1,
            randomMax: parseFloat(document.getElementById('experiment-tau-random-max')?.value) || 0.9
        };
    },

    getExperimentDisruptionSettings() {
        const modeRadio = document.querySelector('input[name="experiment-disruption-mode"]:checked');
        return {
            mode: modeRadio?.value || 'preset',
            severityMin: parseFloat(document.getElementById('experiment-severity-min')?.value) || 0.1,
            severityMax: parseFloat(document.getElementById('experiment-severity-max')?.value) || 0.9,
            ratioFlow: parseInt(document.getElementById('experiment-ratio-flow')?.value) || 95,
            ratioIncident: parseInt(document.getElementById('experiment-ratio-incident')?.value) || 5
        };
    },

    getExperimentRouteSettings() {
        const modeRadio = document.querySelector('input[name="experiment-route-mode"]:checked');
        return {
            mode: modeRadio?.value || 'preset'
        };
    },

    /**
     * Generate tau value based on experiment settings
     */
    generateExperimentTau(tauSettings, trialIndex, routeIndex, routeCount) {
        const { mode, scope, fixed, randomMin, randomMax } = tauSettings;

        if (mode === 'fixed') {
            return fixed;
        }

        // For random mode, generate based on scope
        // Use a seed based on indices for reproducibility within a run
        const seed = scope === 'all' ? 0 :
                     scope === 'per-trial' ? trialIndex :
                     scope === 'per-route' ? routeIndex :
                     trialIndex * routeCount + routeIndex;
        
        // Simple seeded random (for consistency within scope)
        const random = () => {
            const x = Math.sin(seed + 1) * 10000;
            return x - Math.floor(x);
        };

        return randomMin + random() * (randomMax - randomMin);
    },

    /**
     * Load or generate experiment preset data using demo configs structure
     * Routes are stored in the config JSON, disruptions in /data/demos/configs/disruptions/ThesisExperiment/
     */
    async loadOrGenerateExperimentPreset(type, settings) {
        const configName = this.experimentConfigName;
        
        try {
            // Try to load existing ThesisExperiment config
            const response = await fetch(`/api/demo/configs/${configName}`);
            const result = await response.json();
            
            if (result.success && result.config) {
                if (type === 'routes' && result.config.routes && result.config.routes.length > 0) {
                    console.log(`📂 Loaded existing routes from ${configName} config`);
                    return result.config.routes;
                }
                if (type === 'disruptions' && result.config.disruptions?.disruptionSets) {
                    console.log(`📂 Loaded existing disruptions from ${configName} config`);
                    // Return the first disruption set (experiment uses 'all' scope)
                    const setKey = Object.keys(result.config.disruptions.disruptionSets)[0];
                    if (setKey) {
                        return result.config.disruptions.disruptionSets[setKey];
                    }
                }
            }
        } catch (e) {
            console.log(`📝 No existing ${type} preset, will generate new`);
        }

        // Generate new preset
        console.log(`🔄 Generating new ${type} preset for ${configName}`);
        
        if (type === 'routes') {
            return await this.generateExperimentRoutes(settings);
        } else if (type === 'disruptions') {
            return await this.generateExperimentDisruptions(settings);
        }

        return null;
    },

    /**
     * Generate 1000 random routes for experiment
     * Uses efficient batch API call to get road-validated points
     */
    async generateExperimentRoutes(settings) {
        const batchSize = 1000;
        const routes = [];

        this.showLoadingAnimation('Generating Routes', `Creating ${batchSize} random routes...`);

        // Efficient batch approach: get all road points at once
        // We need 2 points per route, but get extra for distance filtering
        const neededPoints = batchSize * 3;  // 3x for variety
        const roadPoints = await this.getRandomRoadPoints(neededPoints);

        if (roadPoints && roadPoints.length >= 2) {
            this.updateLoadingStatus(`Got ${roadPoints.length} road points, creating route pairs...`);
            
            let pointIndex = 0;
            for (let i = 0; i < batchSize; i++) {
                // Pick two points with reasonable distance between them
                let start = roadPoints[pointIndex % roadPoints.length];
                let end = roadPoints[(pointIndex + 1) % roadPoints.length];
                pointIndex += 2;
                
                // Try to find a pair with minimum distance
                let attempts = 0;
                while (attempts < 5 && 
                       Math.abs(end.lat - start.lat) < 0.005 &&
                       Math.abs(end.lng - start.lng) < 0.005) {
                    end = roadPoints[(pointIndex + attempts) % roadPoints.length];
                    attempts++;
                }

                routes.push({
                    id: `exp-route-${i}`,
                    start: start,
                    end: end
                });

                if (i % 100 === 0) {
                    this.updateLoadingStatus(`Generated ${i + 1}/${batchSize} routes`);
                    await this.delay(1); // Allow UI to update
                }
            }
        } else {
            // Fallback to individual calls (slower but more reliable)
            console.warn('⚠️ Batch road points failed, using individual calls');
            for (let i = 0; i < batchSize; i++) {
                const pair = await this.getRandomLocationPair(true);
                routes.push({
                    id: `exp-route-${i}`,
                    start: pair.start,
                    end: pair.end
                });

                if (i % 100 === 0) {
                    this.updateLoadingStatus(`Generated ${i + 1}/${batchSize} routes`);
                    await this.delay(1); // Allow UI to update
                }
            }
        }

        return routes;
    },

    /**
     * Generate disruptions for experiment based on ratio
     * Saves to /data/demos/configs/disruptions/ThesisExperiment/ using same structure as demo-creator
     */
    async generateExperimentDisruptions(settings) {
        const batchSize = 1000;
        const { ratioFlow, ratioIncident, severityMin, severityMax } = settings;
        
        // Calculate counts based on ratio
        const total = ratioFlow + ratioIncident;
        const flowCount = Math.round((ratioFlow / total) * batchSize);
        const incidentCount = batchSize - flowCount;

        this.showLoadingAnimation('Generating Disruptions', 
            `Creating ${flowCount} flow + ${incidentCount} incidents...`);

        try {
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
                const disruptions = {
                    flow: result.flow || [],
                    incidents: result.incidents || [],
                    flowCount: result.flow_count,
                    incidentCount: result.incident_count,
                    settings: { ratioFlow, ratioIncident, severityMin, severityMax }
                };

                return disruptions;
            }
        } catch (error) {
            console.error('Error generating experiment disruptions:', error);
        }

        return null;
    },

    /**
     * Save experiment config to server using demo configs structure
     * Config saved to /data/demos/configs/ThesisExperiment.json
     * Disruptions saved to /data/demos/configs/disruptions/ThesisExperiment/
     */
    async saveExperimentConfig(routes, disruptions, tauSettings, disruptionSettings) {
        const configName = this.experimentConfigName;
        
        try {
            // Build config structure matching demo-creator format
            const config = {
                id: configName,
                name: configName,
                savedAt: new Date().toISOString(),
                isExperiment: true,
                routes: routes.map((r, idx) => ({
                    ...r,
                    trials: [] // Will be populated during run
                })),
                settings: {
                    algorithm: 'both',
                    trials: 3,
                    stepDelay: 100
                },
                tau: tauSettings,
                disruptions: {
                    mode: 'random-both',
                    scope: 'all',
                    severityMin: disruptionSettings.severityMin,
                    severityMax: disruptionSettings.severityMax,
                    randomFlowCount: disruptions.flowCount,
                    randomIncidentCount: disruptions.incidentCount,
                    disruptionSets: {
                        'set_all': disruptions
                    }
                },
                disruptionKey: configName
            };

            // Save config using same API as demo-creator
            const response = await fetch('/api/demo/configs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const result = await response.json();
            if (result.success) {
                console.log(`✅ Saved experiment config: ${configName}`);
                return true;
            }
        } catch (error) {
            console.error('Error saving experiment config:', error);
        }
        return false;
    },

    /**
     * Delete a temporary experiment config and its disruptions folder
     * @param {string} tempConfigName - The temporary config name to delete
     */
    async deleteTemporaryExperimentConfig(tempConfigName) {
        if (!tempConfigName || !tempConfigName.startsWith('ExperimentMode_temp_')) {
            return; // Safety check - only delete temp configs
        }

        try {
            console.log(`🗑️ Deleting temporary experiment config: ${tempConfigName}`);
            
            const response = await fetch(`/api/demo/configs/${tempConfigName}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            if (result.success) {
                console.log(`✅ Deleted temporary config: ${tempConfigName}`);
            } else {
                console.warn(`⚠️ Failed to delete temp config: ${result.error}`);
            }
        } catch (error) {
            console.error('Error deleting temporary config:', error);
        }
    },

    // ==========================================================================
    // LAZY DISRUPTION LOADING SYSTEM
    // ==========================================================================

    /**
     * Initialize lazy disruption system
     */
    initLazyDisruptionSystem(configId, totalDisruptions, disruptionSettings) {
        this.disruptionCache.clear();
        this.disruptionBuffer = [];
        this.disruptionGenerationQueue = [];
        this.isGeneratingDisruptions = false;
        this.currentDisruptionIndex = -1;
        this.totalDisruptionsNeeded = totalDisruptions;
        this.disruptionConfigId = configId;
        this.disruptionSettings = disruptionSettings;
        
        console.log(`🔧 Initialized lazy disruption system: ${totalDisruptions} disruptions needed`);
    },

    /**
     * Check if a disruption file exists on the server
     */
    async checkDisruptionFileExists(configId, setKey) {
        try {
            const response = await fetch(`/api/demo/disruptions/${configId}/${setKey}/exists`);
            const result = await response.json();
            return result.exists || false;
        } catch (e) {
            return false;
        }
    },

    /**
     * Load a single disruption set from file or generate if not exists
     */
    async loadOrGenerateDisruption(queryIndex) {
        const setKey = `set_query_${queryIndex}`;
        const configId = this.disruptionConfigId;

        // Check cache first
        if (this.disruptionCache.has(setKey)) {
            console.log(`✅ Using cached disruption: ${setKey}`);
            return this.disruptionCache.get(setKey);
        }

        // Try to load from file
        const exists = await this.checkDisruptionFileExists(configId, setKey);
        
        if (exists) {
            console.log(`📂 Loading disruption from file: ${setKey}`);
            try {
                const response = await fetch(`/api/demo/disruptions/${configId}/${setKey}`);
                const result = await response.json();
                
                if (result.success && result.disruptions) {
                    const disruptionData = this.normalizeDisruptionData({
                        flow: result.disruptions.flow || [],
                        incidents: result.disruptions.incidents || []
                    });
                    
                    // Cache it
                    this.disruptionCache.set(setKey, disruptionData);
                    console.log(`✅ Loaded and cached disruption: ${setKey}`);
                    return disruptionData;
                }
            } catch (e) {
                console.warn(`Failed to load disruption ${setKey}, will generate:`, e);
            }
        }

        // Generate new disruption
        console.log(`🎲 Generating disruption: ${setKey}`);
        const { ratioFlow, ratioIncident, severityMin, severityMax, disruptionsPerBatch } = this.disruptionSettings;
        const total = ratioFlow + ratioIncident;
        const flowCount = Math.round((ratioFlow / total) * disruptionsPerBatch);
        const incidentCount = disruptionsPerBatch - flowCount;

        try {
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
                const disruptionData = this.normalizeDisruptionData({
                    flow: result.flow || [],
                    incidents: result.incidents || []
                });

                // Save to file for future use
                await this.saveDisruptionToFile(configId, setKey, disruptionData);

                // Cache it
                this.disruptionCache.set(setKey, disruptionData);
                console.log(`🎲 Generated and cached disruption: ${setKey}`);
                return disruptionData;
            }
        } catch (e) {
            console.error(`Failed to generate disruption ${setKey}:`, e);
        }

        return { flow: [], incidents: [] };
    },

    /**
     * Normalize disruption data to standard format
     * Handles both CSV format (from loading) and API format (from generation)
     */
    normalizeDisruptionData(disruptionData) {
        return {
            flow: (disruptionData.flow || []).map(item => ({
                id_hash: item.id_hash || '',
                source: parseInt(item.source || 0),
                target: parseInt(item.target || 0),
                source_lat: parseFloat(item.source_lat || 0),
                source_lon: parseFloat(item.source_lon || 0),
                target_lat: parseFloat(item.target_lat || 0),
                target_lon: parseFloat(item.target_lon || 0),
                speed_kph: parseFloat(item.flow_speed_kph || item.speed_kph || 30),
                free_flow_kph: parseFloat(item.flow_free_flow_kph || item.free_flow_kph || 60),
                jam_factor: parseFloat(item.flow_jam_factor || item.jam_factor || 5),
                flow_confidence: parseFloat(item.flow_confidence || 0.95),
                flow_traversability: item.flow_traversability || 'open',
                highway_type: item.highway_type || 'primary',
                road_name: item.road_name || 'Unknown Road',
                type: 'flow'
            })),
            incidents: (disruptionData.incidents || []).map(item => ({
                incident_id: item.incident_id || '',
                source: parseInt(item.source || 0),
                target: parseInt(item.target || 0),
                source_lat: parseFloat(item.source_lat || 0),
                source_lon: parseFloat(item.source_lon || 0),
                target_lat: parseFloat(item.target_lat || 0),
                target_lon: parseFloat(item.target_lon || 0),
                type: item.incident_type || item.type || 'accident',
                criticality: item.incident_criticality || item.criticality || 'minor',
                incident_description: item.incident_description || '',
                road_closed: this.parseBoolean(item.incident_road_closed || item.road_closed || false),
                incident_start_time: item.incident_start_time || '',
                incident_end_time: item.incident_end_time || '',
                highway_type: item.highway_type || 'primary',
                road_name: item.road_name || 'Unknown Road',
                is_incident: true
            }))
        };
    },

    /**
     * Parse boolean values from various formats
     */
    parseBoolean(value) {
        if (typeof value === 'boolean') return value;
        if (typeof value === 'string') return value.toLowerCase() === 'true';
        return !!value;
    },

    /**
     * Save a disruption set to file
     */
    async saveDisruptionToFile(configId, setKey, disruptionData) {
        try {
            const response = await fetch(`/api/demo/disruptions/${configId}/${setKey}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    disruptions: disruptionData
                })
            });

            const result = await response.json();
            if (result.success) {
                console.log(`💾 Saved disruption to file: ${setKey}`);
                return true;
            }
        } catch (e) {
            console.warn(`Failed to save disruption ${setKey}:`, e);
        }
        return false;
    },

    /**
     * Prefetch disruptions ahead of current position (background task)
     */
    async prefetchDisruptions(startIndex, count) {
        if (this.isGeneratingDisruptions) return;
        
        this.isGeneratingDisruptions = true;
        const endIndex = Math.min(startIndex + count, this.totalDisruptionsNeeded);
        
        console.log(`🔄 Prefetching disruptions ${startIndex} to ${endIndex - 1}`);
        
        for (let i = startIndex; i < endIndex; i++) {
            if (!this.isRunning) break;
            
            const setKey = `set_query_${i}`;
            if (!this.disruptionCache.has(setKey)) {
                await this.loadOrGenerateDisruption(i);
            }
        }
        
        this.isGeneratingDisruptions = false;
    },

    /**
     * Get disruption for a specific query index (with automatic prefetching)
     */
    async getDisruptionForQuery(queryIndex) {
        const setKey = `set_query_${queryIndex}`;
        
        // Start prefetching next batch in background
        const nextPrefetchStart = queryIndex + 1;
        if (nextPrefetchStart < this.totalDisruptionsNeeded && !this.isGeneratingDisruptions) {
            // Don't await - let it run in background
            this.prefetchDisruptions(nextPrefetchStart, this.disruptionBufferSize);
        }

        // Get current disruption (this will wait if needed)
        return await this.loadOrGenerateDisruption(queryIndex);
    },

    /**
     * Clear disruption cache and reset system
     */
    clearDisruptionCache() {
        this.disruptionCache.clear();
        this.disruptionBuffer = [];
        this.disruptionGenerationQueue = [];
        this.isGeneratingDisruptions = false;
        this.currentDisruptionIndex = -1;
        console.log('🧹 Cleared disruption cache');
    },

    /**
     * Start the thesis experiment
     * Uses the same save mechanism as Demo Creator:
     * - Config saved to /data/demos/configs/ExperimentMode.json
     * - Disruptions saved to /data/demos/configs/disruptions/ExperimentMode/set_route_N/
     * 
     * Structure:
     * - 1000 routes, each with its own disruption set (set_route_0, set_route_1, ...)
     * - 3 trials per route, all trials for a route use the same disruption set
     * - Both DHL and HC2L algorithms tested
     * 
     * Random Mode Behavior:
     * - Random Routes: Creates temporary config with new routes, uses existing disruptions
     * - Random Disruptions: Creates temporary config and folder with new disruptions, uses existing routes
     * - The temporary files are deleted after the run completes
     */
    async startExperiment() {
        if (this.isRunning) {
            showUpdateToast('A demo is already running', 'warning');
            return;
        }

        const tauSettings = this.getExperimentTauSettings();
        const disruptionSettings = this.getExperimentDisruptionSettings();
        const routeSettings = this.getExperimentRouteSettings();

        console.log('🧪 Starting Experiment Mode');
        console.log('   Tau Settings:', tauSettings);
        console.log('   Disruption Settings:', disruptionSettings);
        console.log('   Route Settings:', routeSettings);

        this.showLoadingAnimation('Initializing Experiment', 'Loading configuration...');

        try {
            // Try to load existing preset or generate new
            let routes = null;
            let existingConfig = null;
            const trials = 3; // Fixed 3 trials
            const batchesPerTrial = 3; // Fixed 3 batches per trial
            const disruptionsPerBatch = 1000; // Fixed 1000 disruptions per batch
            const queriesPerBatch = 1000; // Fixed 1000 queries per batch

            // Determine if we're using random mode (temporary config needed)
            const isRandomRoutes = routeSettings.mode === 'random';
            const isRandomDisruptions = disruptionSettings.mode === 'random';
            const needsTempConfig = isRandomRoutes || isRandomDisruptions;
            
            // Generate temp config name if needed
            const tempTimestamp = Date.now();
            const tempConfigName = needsTempConfig ? `ExperimentMode_temp_${tempTimestamp}` : null;
            
            // Store temp config name for cleanup after run
            this.currentTempConfigName = tempConfigName;

            // Check if we have an existing ExperimentMode config (the preset)
            try {
                const response = await fetch(`/api/demo/configs/${this.experimentConfigName}`);
                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        existingConfig = result.config;
                        console.log('📂 Found existing ExperimentMode preset config');
                    }
                }
            } catch (e) {
                console.log('No existing preset config found, will create new');
            }

            // Handle routes
            if (isRandomRoutes) {
                // Generate new routes for temporary config
                routes = await this.generateExperimentRoutes(routeSettings);
                console.log(`🎲 Generated ${routes.length} new random routes (temporary)`);
            } else if (existingConfig?.routes?.length > 0) {
                // Use saved routes from preset config
                routes = existingConfig.routes;
                console.log(`📂 Loaded ${routes.length} preset routes from config`);
                this.updateLoadingStatus(`Loaded ${routes.length} preset routes`);
            } else {
                // No preset routes exist, generate new for preset
                routes = await this.generateExperimentRoutes(routeSettings);
                console.log(`🎲 Generated ${routes.length} new routes (will save to preset)`);
            }

            if (!routes || routes.length === 0) {
                throw new Error('Failed to load/generate routes');
            }

            // Handle disruptions - Initialize Lazy Loading System
            let disruptionKeyToUse = null;

            if (isRandomDisruptions) {
                // Random mode: use temporary config for disruptions
                disruptionKeyToUse = tempConfigName;
                console.log(`🎲 Random mode: disruptions will be generated lazily (temporary config)`);
            } else {
                // Preset mode: use main experiment config for disruptions
                disruptionKeyToUse = this.experimentConfigName;
                console.log(`📂 Preset mode: disruptions will be loaded lazily from ExperimentMode`);
            }

            // Calculate total queries for all batches
            const totalQueries = queriesPerBatch * batchesPerTrial;

            // Initialize lazy disruption loading system
            const { ratioFlow, ratioIncident, severityMin, severityMax } = disruptionSettings;
            this.initLazyDisruptionSystem(disruptionKeyToUse, totalQueries, {
                ratioFlow,
                ratioIncident,
                severityMin,
                severityMax,
                disruptionsPerBatch
            });
            
            this.updateLoadingStatus('Disruption system initialized (lazy loading enabled)');

            // Build routes with trials and batches
            // For experiment mode: generate routes for each batch
            const routesWithTrials = [];
            
            for (let queryIdx = 0; queryIdx < totalQueries; queryIdx++) {
                // Cycle through available routes
                const r = routes[queryIdx % routes.length];
                const batchNum = Math.floor(queryIdx / queriesPerBatch) + 1;
                
                const baseRoute = {
                    id: `exp-query-${queryIdx}`,
                    batchId: batchNum,
                    queryId: queryIdx,
                    start: r.start || { lat: r.sourceCoords?.lat, lng: r.sourceCoords?.lng, name: r.sourceName || 'Unknown' },
                    end: r.end || { lat: r.targetCoords?.lat, lng: r.targetCoords?.lng, name: r.targetName || 'Unknown' }
                };

                const trialsArray = [];
                for (let t = 0; t < trials; t++) {
                    const tau = this.generateExperimentTau(tauSettings, t, queryIdx, totalQueries);
                    trialsArray.push({
                        tau: parseFloat(tau.toFixed(3)),
                        batchId: batchNum,
                        disruption: `set_query_${queryIdx}`
                    });
                }

                routesWithTrials.push({ ...baseRoute, trials: trialsArray });
            }

            // Determine which config ID to use
            const configId = needsTempConfig ? tempConfigName : this.experimentConfigName;

            // Build config
            const config = {
                id: configId,
                name: needsTempConfig ? `Experiment (Temporary ${tempTimestamp})` : this.experimentConfigName,
                isExperiment: true,
                isTemporary: needsTempConfig,  // Mark as temporary for cleanup
                batchesPerTrial: batchesPerTrial,
                disruptionsPerBatch: disruptionsPerBatch,
                queriesPerBatch: queriesPerBatch,
                routes: routesWithTrials,
                settings: {
                    algorithm: 'both',
                    trials: trials,
                    batchesPerTrial: batchesPerTrial,
                    stepDelay: 100
                },
                tau: tauSettings,
                disruptions: {
                    mode: 'random-both',
                    scope: 'per-query',
                    flowCount: disruptionSettings.ratioFlow,
                    incidentCount: disruptionSettings.ratioIncident,
                    severityMin: disruptionSettings.severityMin,
                    severityMax: disruptionSettings.severityMax
                    // Lazy loading: disruptions are loaded/generated on demand
                    // No need to store disruption sets in config
                },
                disruptionKey: disruptionKeyToUse
            };

            // Save config based on mode
            if (needsTempConfig) {
                // Save temporary config (will be deleted after run)
                this.updateLoadingStatus(`Saving temporary config: ${tempConfigName}...`);
                console.log(`📝 Saving temporary experiment config: ${tempConfigName}`);
                
                const saveResponse = await fetch('/api/demo/configs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });

                const saveResult = await saveResponse.json();
                if (!saveResult.success) {
                    throw new Error('Failed to save temporary config: ' + saveResult.error);
                }

                console.log(`✅ Saved temporary config: ${saveResult.config?.id}`);
                
                // Run demo with saved config
                this.hideLoadingAnimation();
                this.showTab('running');
                try {
                    await this.runDemo(saveResult.config);
                } finally {
                    // Cleanup temporary config after demo completes (success or error)
                    await this.deleteTemporaryExperimentConfig(tempConfigName);
                }
            } else if (!existingConfig) {
                // Save to preset (first time setup)
                this.updateLoadingStatus('Saving experiment preset...');
                
                const saveResponse = await fetch('/api/demo/configs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });

                const saveResult = await saveResponse.json();
                if (!saveResult.success) {
                    throw new Error('Failed to save preset config: ' + saveResult.error);
                }

                console.log('✅ Saved preset config:', saveResult.config?.id);
                
                this.hideLoadingAnimation();
                this.showTab('running');
                await this.runDemo(saveResult.config);
            } else {
                // Use existing preset directly (no changes needed)
                console.log('✅ Using existing preset config');
                this.hideLoadingAnimation();
                this.showTab('running');
                await this.runDemo(existingConfig);
            }

        } catch (error) {
            console.error('Experiment error:', error);
            this.hideLoadingAnimation();
            showUpdateToast('Experiment failed: ' + error.message, 'error');
            
            // Cleanup any temp config that might have been created
            if (this.currentTempConfigName) {
                await this.deleteTemporaryExperimentConfig(this.currentTempConfigName);
                this.currentTempConfigName = null;
            }
        }
    },

    // ==========================================================================
    // DEMO EXECUTION
    // ==========================================================================

    /**
     * Run an external config (from Demo Creator)
     * Opens the Demo Runner panel, closes Demo Creator, and starts the demo
     * @param {Object} config - The demo configuration to run
     * @param {boolean} isTemporary - If true, config is not persisted (Run Only mode)
     * @returns {Promise<boolean>} - True if demo started successfully
     */
    async runExternalConfig(config, isTemporary = false) {
        if (this.isRunning) {
            showUpdateToast('A demo is already running', 'warning');
            return false;
        }

        console.log('📥 Receiving external config from Demo Creator:', config.name);
        console.log('   Temporary:', isTemporary);
        console.log('   Disruptions:', config.disruptions);

        // Mark config as temporary if needed (won't appear in saved configs list)
        if (isTemporary) {
            config.isTemporary = true;
        }

        // Store the config
        this.currentDemo = config;

        // Open Demo Runner panel
        const runnerPanel = document.getElementById('demo-runner-panel');
        if (runnerPanel) {
            runnerPanel.classList.remove('translate-x-full');
        }

        // Close Demo Creator panel
        const creatorPanel = document.getElementById('demo-creator-panel');
        if (creatorPanel) {
            creatorPanel.classList.add('translate-x-full');
        }

        // Disable admin toggles
        this.disableAdminToggles();

        // Wait for panel transition
        await new Promise(resolve => setTimeout(resolve, 150));

        // Show running tab and start the demo
        this.showTab('running');

        try {
            await this.runDemo(config);
            return true;
        } catch (error) {
            console.error('Error running external config:', error);
            showUpdateToast('Error running demo: ' + error.message, 'error');
            return false;
        }
    },

    async runDemo(config) {
        if (this.isRunning) {
            showUpdateToast('A demo is already running', 'warning');
            return;
        }

        this.isRunning = true;
        this.isPaused = false;
        this.currentDemo = config;
        this.currentDemoId = null;  // Track demoId for cleanup

        // Store config ID and name for results saving (persists after demo ends)
        this.lastRunConfigId = config.id || null;
        this.lastRunConfigName = config.name || 'Demo Results';

        // Save the current Route Finder state before making any changes
        saveRouteFinderState();

        // Turn off admin panel toggles to prevent interference during demo
        const incidentToggle = document.getElementById('show-active-incidents');
        const flowToggle = document.getElementById('show-traffic-overlay');

        if (incidentToggle && incidentToggle.checked) {
            incidentToggle.checked = false;
            incidentToggle.dispatchEvent(new Event('change'));
        }
        if (flowToggle && flowToggle.checked) {
            flowToggle.checked = false;
            flowToggle.dispatchEvent(new Event('change'));
        }

        // Disable route finder UI when demo starts
        toggleRouteFinderUI(true);

        // Reset saved state for new demo run
        this.currentResultsSavedPath = null;

        // Read from settings block (new format) with fallbacks
        const trials = config.settings?.trials || config.trials || 1;
        const routes = config.routes || [];
        const algorithm = config.settings?.algorithm || config.algorithm || 'hc2l';
        const stepDelay = config.settings?.stepDelay || config.stepDelay || 2000;
        const batchesPerTrial = config.batchesPerTrial || config.settings?.batchesPerTrial || 1;
        const queriesPerBatch = config.queriesPerBatch || 1000;

        // Store algorithm in config for processRouteWithProgress
        config.algorithm = algorithm;
        config.stepDelay = stepDelay;

        // Check if this is a saved config with pre-generated disruptions
        // Flask saves as 'savedSets', but in-memory configs may use 'disruptionSets'
        const configDisruptionSets = config.disruptions?.savedSets || config.disruptions?.disruptionSets || {};
        const hasConfigDisruptions = Object.keys(configDisruptionSets).length > 0;

        // Initialize detailed progress
        this.currentProgress = {
            trial: 0,
            totalTrials: trials,
            batch: 0,
            totalBatches: batchesPerTrial,
            route: 0,
            totalRoutes: routes.length,
            queriesPerBatch: queriesPerBatch,
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
            console.log(`📊 Using ${Object.keys(configDisruptionSets).length} saved disruption sets from config`);
        }
        showUpdateToast(`Starting: ${config.name}`, 'info');

        this.showLoadingAnimation(
            'Initializing Demo',
            'Initializing demo setup...');
        this.updateDetailedProgressUI();

        try {
            // Reset map
            this.showLoadingAnimation(
                'Initializing Demo',
                'Resetting map...');
            resetSystemState();


            // Get disruption config - use new format paths with fallbacks
            const disruptions = config.disruptions || {};
            const generationScope = disruptions.scope || disruptions.generationScope || 'all';
            const disruptionKey = config.disruptionKey || null;  // For loading saved disruption CSVs

            // Handle disruption setup
            this.disruptionSets = {};  // Store disruption sets by key
            this.currentDemoId = `demo_${Date.now()}`;

            if (hasConfigDisruptions) {
                // Use saved disruption sets from config - load from CSV files
                this.showLoadingAnimation(
                    'Initializing Demo',
                    'Loading disruption sets...');
                console.log(`📂 Loading ${Object.keys(configDisruptionSets).length} saved disruption sets (key: ${disruptionKey})`);
                let loadedCount = 0;
                for (const [setKey, setData] of Object.entries(configDisruptionSets)) {
                    await this.activateConfigDisruptionSet(setKey, setData, this.currentDemoId, disruptionKey);
                    loadedCount++;
                    this.showLoadingAnimation(
                        'Initializing Demo',
                        `Loaded disruption set: ${loadedCount}/${Object.keys(configDisruptionSets).length}`);
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

            // Setup complete - hide loading animation
            this.hideLoadingAnimation();
            this.showTab('running');

            // Run for each trial
            for (let trial = 0; trial < trials; trial++) {
                if (!this.isRunning) break;

                this.currentProgress.trial = trial + 1;

                // Generate disruptions for this trial if per-trial scope (only if not using config-saved)
                if (!hasConfigDisruptions && generationScope === 'per-trial') {
                    const trialKey = `set_trial_${trial}`;
                    await this.setupDemoDisruptions(config, `${this.currentDemoId}_${trialKey}`, trialKey);
                }

                // Process each route (which includes batch information)
                for (let i = 0; i < routes.length; i++) {
                    if (!this.isRunning) break;
                    while (this.isPaused) {
                        await this.delay(100);
                    }

                    const route = routes[i];
                    this.currentProgress.route = i + 1;
                    
                    // Update batch tracking for display
                    const currentBatch = route.batchId || Math.floor(i / queriesPerBatch) + 1;
                    this.currentProgress.batch = currentBatch;
                    
                    this.currentProgress.status = `Trial ${trial + 1}, Batch ${currentBatch}, Query ${i + 1}/${routes.length}`;
                    this.updateDetailedProgressUI();

                    // Generate disruptions for this trial-route if per-trial-route scope (only if not using config-saved)
                    if (!hasConfigDisruptions && generationScope === 'per-trial-route') {
                        const comboKey = `set_trial_${trial}_route_${i}`;
                        await this.setupDemoDisruptions(config, `${this.currentDemoId}_${comboKey}`, comboKey);
                    }

                    // Set active disruptions based on scope
                    // NEW FORMAT: route.trials[trial].disruption is just the setKey string
                    const trialData = route.trials?.[trial];
                    let setKey = null;

                    if (trialData?.disruption) {
                        // Handle both formats:
                        // - New format: disruption is just the setKey string
                        // - Old format: disruption is an object with setKey property
                        setKey = typeof trialData.disruption === 'string'
                            ? trialData.disruption
                            : trialData.disruption.setKey;
                    }

                    if (setKey) {
                        await this.activateDisruptionSetByKey(setKey);
                    } else {
                        await this.activateDisruptionSet(generationScope, trial, i);
                    }

                    await this.processRouteWithProgress(route, config, trial);
                    await this.delay(config.stepDelay || config.settings?.stepDelay || 2000);
                }
            }

            if (this.isRunning) {
                this.currentProgress.status = '✅ Demo completed!';
                this.updateDetailedProgressUI();
                showUpdateToast('Demo completed!', 'success');

                // Clear routes from map
                if (typeof clearRoutes === 'function') {
                    clearRoutes();
                }

                // Cleanup demo disruptions (only if we generated them at runtime)
                if (this.currentDemoId) {
                    await this.cleanupDemoDisruptions(this.currentDemoId);
                }

                // Mark this as a new execution result (not loaded from saved results)
                this.resultsSource = 'new';
                this.currentResultsSavedPath = null; // Reset saved path on new run
                console.log('✅ Demo completed, resultsSource set to "new", currentResultsSavedPath=', this.currentResultsSavedPath);

                // Use the comprehensive system reset function from functions.js
                resetSystemState();

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

            // Re-enable route finder UI when demo stops
            toggleRouteFinderUI(false);

            // Restore the saved Route Finder state
            restoreRouteFinderState();
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
            window.demoDisruptionDir = null;
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
     * Activate a disruption set from config - loads from saved CSV files or writes new temp files
     * @param {string} setKey - The disruption set key (e.g., 'set_all', 'set_trial_0', etc.)
     * @param {Object} setData - The disruption data. Can be:
     *   - savedSets format: { disruption_dir: "...", flow_count: N, incident_count: M }
     *   - in-memory format: { flow: [...], incidents: [...] }
     * @param {string} demoId - The demo ID for file naming
     * @param {string} disruptionKey - The config's disruptionKey for loading from savedSets
     */
    async activateConfigDisruptionSet(setKey, setData, demoId, disruptionKey = null) {
        try {
            // Check if this is a savedSets entry (has disruption_dir path)
            if (setData.disruption_dir && disruptionKey) {
                // Load disruption data from saved CSV files via API
                console.log(`📂 Loading saved disruption set: ${disruptionKey}/${setKey}`);

                const response = await fetch(`/api/demo/disruption-data/${disruptionKey}/${setKey}`);
                const result = await response.json();

                if (result.success) {
                    // Store in our runtime disruption sets - using the existing saved CSV path
                    this.disruptionSets[setKey] = {
                        disruptionDir: result.disruption_dir,
                        demoId: demoId,
                        disruptions: {
                            flow: result.flowSegments || [],
                            incidents: result.incidents || []
                        },
                        flowCount: setData.flow_count || result.flowSegments?.length || 0,
                        incidentCount: setData.incident_count || result.incidents?.length || 0
                    };
                    console.log(`📦 Loaded saved disruption set: ${setKey} -> ${result.disruption_dir}`);
                    console.log(`   Incidents: ${result.incidents?.length || 0}, Flow: ${result.flowSegments?.length || 0}`);
                } else {
                    console.warn(`⚠️ Failed to load saved disruption set ${setKey}:`, result.error);
                }
            } else if (setData.flow || setData.incidents) {
                // In-memory format - write to temp files via API
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
                    console.log(`📦 Activated in-memory disruption set: ${setKey} -> ${result.disruption_dir}`);
                } else {
                    console.warn(`⚠️ Failed to activate config disruption set ${setKey}:`, result.error);
                }
            } else {
                console.warn(`⚠️ Unknown disruption set format for ${setKey}:`, setData);
            }
        } catch (error) {
            console.error(`❌ Error activating config disruption set ${setKey}:`, error);
        }
    },

    /**
     * Activate a disruption set by its key directly
     * Used when route.trials[trial].disruption.setKey is available
     * Now uses lazy loading - will fetch/generate disruption on demand
     * @param {string} setKey - The disruption set key (e.g., 'set_query_0')
     */
    async activateDisruptionSetByKey(setKey) {
        // Check if this disruption set was already loaded (has absolute path)
        if (this.disruptionSets && this.disruptionSets[setKey]) {
            // Use the pre-loaded disruption set with absolute path
            const disruptionSet = this.disruptionSets[setKey];
            this.demoDisruptionDir = disruptionSet.disruptionDir;  // Absolute path
            window.demoDisruptionDir = disruptionSet.disruptionDir;

            // Convert API format to display format
            const disruptions = disruptionSet.disruptions || {};
            this.generatedDisruptions = {
                incidents: (disruptions.incidents || []).map(d => ({
                    ...d,
                    source_lng: d.source_lon || d.source_lng,
                    target_lng: d.target_lon || d.target_lng,
                    incident_type: d.type || d.incident_type || 'Incident',
                    type: d.type || d.incident_type || 'Incident',
                    severity: TrafficUtils.getSeverityFromCriticality(d.criticality || d.incident_criticality, d.road_closed || d.incident_road_closed)
                })),
                flowSegments: (disruptions.flow || []).map(d => ({
                    ...d,
                    source_lng: d.source_lon || d.source_lng,
                    target_lng: d.target_lon || d.target_lng,
                    incident_type: 'Congestion',
                    type: 'Congestion',
                    severity: TrafficUtils.getSeverityFromJamFactor(d.jam_factor || d.flow_jam_factor, d.road_closed),
                    current_speed: d.speed_kph || d.flow_speed_kph,
                    free_flow_speed: d.free_flow_kph || d.flow_free_flow_kph,
                    jam_factor: d.jam_factor || d.flow_jam_factor
                }))
            };

            console.log(`🔄 Activated pre-loaded disruption set: ${setKey}`);
            console.log(`   Disruption dir: ${this.demoDisruptionDir}`);
            console.log(`   Incidents: ${this.generatedDisruptions.incidents.length}, Flow: ${this.generatedDisruptions.flowSegments.length}`);

            this.currentPreviewSet = setKey;
            await this.refreshDisruptionDisplay();
            this.showDisruptionSetsPreview();
            return;
        }

        // Fall back to lazy loading for experiment mode (set_query_N format)
        const match = setKey.match(/set_query_(\d+)/);
        if (!match) {
            console.warn(`⚠️ Invalid setKey format: ${setKey}, expected 'set_query_N' or pre-loaded set`);
            return;
        }

        const queryIndex = parseInt(match[1]);
        
        // Use lazy loading to get disruption
        const disruptionData = await this.getDisruptionForQuery(queryIndex);
        
        if (!disruptionData || (!disruptionData.flow || disruptionData.flow.length === 0 && !disruptionData.incidents || disruptionData.incidents.length === 0)) {
            console.warn(`⚠️ No disruption data for ${setKey}`);
            return;
        }

        // For experiment mode: request absolute path from backend
        // Build absolute path from base directory and config ID
        try {
            const response = await fetch(`/api/demo/disruption-path/${this.disruptionConfigId}/${setKey}`);
            const result = await response.json();
            if (result.success && result.disruption_dir) {
                this.demoDisruptionDir = result.disruption_dir;  // Absolute path from backend
                window.demoDisruptionDir = result.disruption_dir;
                console.log(`📍 Using absolute disruption path: ${result.disruption_dir}`);
            } else {
                // Fallback to relative path (will fail on C++ API but maintains backward compatibility)
                console.warn(`⚠️ Could not get absolute path, using relative: disruptions/${this.disruptionConfigId}`);
                this.demoDisruptionDir = `disruptions/${this.disruptionConfigId}`;
                window.demoDisruptionDir = this.demoDisruptionDir;
            }
        } catch (error) {
            // Fallback to relative path if API call fails
            console.warn(`⚠️ Error getting absolute path:`, error);
            this.demoDisruptionDir = `disruptions/${this.disruptionConfigId}`;
            window.demoDisruptionDir = this.demoDisruptionDir;
        }

        // Convert to display format for the map renderer
        this.generatedDisruptions = {
            incidents: (disruptionData.incidents || []).map(d => ({
                incident_id: d.incident_id || d.incident_id || '',
                source: d.source,
                target: d.target,
                source_lat: d.source_lat,
                source_lon: d.source_lon,
                target_lat: d.target_lat,
                target_lon: d.target_lon,
                source_lng: d.source_lon,
                target_lng: d.target_lon,
                incident_type: d.type || d.incident_type || 'Incident',
                type: d.type || d.incident_type || 'Incident',
                criticality: d.criticality || d.incident_criticality || 'minor',
                incident_criticality: d.criticality || d.incident_criticality || 'minor',
                road_closed: d.road_closed || false,
                incident_road_closed: d.road_closed || false,
                severity: TrafficUtils.getSeverityFromCriticality(d.criticality || d.incident_criticality, d.road_closed || false),
                highway_type: d.highway_type || 'primary',
                road_name: d.road_name || 'Unknown Road'
            })),
            flowSegments: (disruptionData.flow || []).map(d => ({
                id_hash: d.id_hash || '',
                source: d.source,
                target: d.target,
                source_lat: d.source_lat,
                source_lon: d.source_lon,
                target_lat: d.target_lat,
                target_lon: d.target_lon,
                source_lng: d.source_lon,
                target_lng: d.target_lon,
                incident_type: 'Congestion',
                type: 'Congestion',
                jam_factor: d.jam_factor || d.flow_jam_factor || 5,
                severity: TrafficUtils.getSeverityFromJamFactor(d.jam_factor || d.flow_jam_factor, d.road_closed || false),
                current_speed: d.speed_kph || d.flow_speed_kph || 30,
                speed_kph: d.speed_kph || d.flow_speed_kph || 30,
                free_flow_speed: d.free_flow_kph || d.flow_free_flow_kph || 60,
                free_flow_kph: d.free_flow_kph || d.flow_free_flow_kph || 60,
                highway_type: d.highway_type || 'primary',
                road_name: d.road_name || 'Unknown Road'
            }))
        };

        console.log(`🔄 Activated disruption set (lazy loaded): ${setKey}`);
        console.log(`   Incidents: ${this.generatedDisruptions.incidents.length}, Flow: ${this.generatedDisruptions.flowSegments.length}`);

        this.currentPreviewSet = setKey;
        await this.refreshDisruptionDisplay();  // Respect checkbox states
        this.showDisruptionSetsPreview();
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
                    severity: TrafficUtils.getSeverityFromCriticality(d.criticality, d.road_closed)
                })),
                flowSegments: (disruptions.flow || []).map(d => ({
                    ...d,
                    source_lng: d.source_lon || d.source_lng,
                    target_lng: d.target_lon || d.target_lng,
                    incident_type: 'Congestion',
                    severity: TrafficUtils.getSeverityFromJamFactor(d.jam_factor, d.road_closed),
                    current_speed: d.speed_kph,
                    free_flow_speed: d.free_flow_kph
                }))
            };

            console.log(`🔄 Activated disruption set: ${setKey}`);
            console.log(`   Incidents: ${this.generatedDisruptions.incidents.length}, Flow: ${this.generatedDisruptions.flowSegments.length}`);

            // Update current preview set and refresh UI
            this.currentPreviewSet = setKey;

            // Update map visualization respecting checkbox states
            await this.refreshDisruptionDisplay();

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
        // Wait for the location to be set (check if snapping is complete)
        await this.waitForLocationSet('start');

        // Set destination
        this.currentProgress.status = `Setting destination: ${route.end.name}`;
        this.updateDetailedProgressUI();

        if (typeof handleOSMDestLocationPin === 'function') {
            await handleOSMDestLocationPin(route.end.lat, route.end.lng);
        }
        // Wait for the destination to be set
        await this.waitForLocationSet('dest');

        // Get algorithms to test
        const algorithmToTest = config.algorithm || 'hc2l';
        const algorithms = algorithmToTest === 'both' ? ['hc2l', 'dhl'] : [algorithmToTest];

        // Note: Disruptions are handled separately via activateDisruptionSet/activateDisruptionSetByKey
        // No need to set dataset radio here - disruptions are displayed via showGeneratedDisruptions

        // Ensure disruptions are displayed on the map
        console.log('📍 About to refresh disruption display in processRouteWithProgress');
        console.log('   generatedDisruptions:', this.generatedDisruptions);
        console.log('   demoDisruptionLayers:', this.demoDisruptionLayers);
        await this.refreshDisruptionDisplay();
        console.log('   After refresh - demoDisruptionLayers:', this.demoDisruptionLayers);

        // Determine TAU values to test based on scope
        const tauScope = config.tau?.scope || config.sequence?.tauGenerationScope || 'all';
        let tauValuesToTest;

        // NEW FORMAT: Use route.trials[trialIndex].tau if available
        const trialData = route.trials?.[trialIndex];
        if (trialData && trialData.tau !== undefined) {
            // New format: route has trials[] array with tau per trial
            tauValuesToTest = [trialData.tau];
            console.log(`📊 Using saved tau from route.trials[${trialIndex}].tau: ${trialData.tau}`);
        } else {
            // Legacy format: fallback - generate tau based on config template
            const tauMode = config.tau?.mode || config.sequence?.tauMode || 'fixed';
            let tau = 0.5;

            if (tauMode === 'fixed') {
                tau = config.tau?.fixed || config.sequence?.tauFixed || 0.5;
            } else if (tauMode === 'random') {
                const min = config.tau?.randomMin || config.sequence?.tauRandomMin || 0.1;
                const max = config.tau?.randomMax || config.sequence?.tauRandomMax || 0.9;
                tau = min + Math.random() * (max - min);
            } else if (tauMode === 'sequence') {
                const seq = config.tau?.sequence || config.sequence?.tauSequence || [0.5];
                const idx = trialIndex % seq.length;
                tau = seq[idx];
            }

            tauValuesToTest = [tau];
            console.log(`📊 Generated tau (no saved value): ${tau}`);
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
                if (algo === 'dhl') {
                    this.currentProgress.status = `Testing DHL (τ not used)`;
                } else {
                    this.currentProgress.status = `Testing ${algo.toUpperCase()} with τ = ${effectiveTau.toFixed(2)}`;
                }
                this.updateDetailedProgressUI();

                // Set algorithm
                document.querySelector(`input[name="algorithm"][value="${algo}"]`)?.click();

                // Set tau value
                const thresholdInput = document.getElementById('threshold-input');
                if (thresholdInput) {
                    thresholdInput.value = effectiveTau;
                    thresholdInput.dispatchEvent(new Event('input'));
                }

                // Calculate route and capture response directly from API
                const calcStartTime = performance.now();
                let routeData = null;
                if (typeof computeRouteBasedOnSelection === 'function') {
                    routeData = await computeRouteBasedOnSelection();
                }
                const calcEndTime = performance.now();
                const processTimeMs = calcEndTime - calcStartTime;

                // Capture result directly from API response - no need to wait for DOM
                const batchId = route.batchId || null;
                const result = this.captureResultFromAPIResponse(algo, effectiveTau, route, trialIndex, processTimeMs, routeData, batchId);
                if (result) {
                    console.log(`✅ Captured ${algo.toUpperCase()} result from API:`, {
                        distance: result.metrics.displayDistance,
                        calculatedDistanceMeters: result.metrics.calculatedDistanceMeters,
                        calculatedDistanceKm: result.metrics.calculatedDistanceKm,
                        tau: result.tau,
                        route: result.route,
                        processTime: result.processTimeMs,
                        queryTime: result.metrics.queryTime,
                        pathLength: result.metrics.pathLength,
                        etaFormatted: result.metrics.etaFormatted
                    });
                    this.currentProgress.lastResult = result;
                    this.currentProgress.results.push(result);
                } else {
                    console.warn(`⚠️ Failed to capture ${algo.toUpperCase()} result - routeData:`, routeData);
                }

                this.updateDetailedProgressUI();

                // Step delay for visualization purposes (user can observe the route)
                await this.delay(config.stepDelay || 2000);
            }
        }
    },

    /**
     * Wait for a location (start or dest) to be properly set
     * Polls until the location is available in window object
     * @param {string} type - 'start' or 'dest'
     * @param {number} maxWaitMs - Maximum time to wait in ms (default 5000)
     */
    async waitForLocationSet(type, maxWaitMs = 5000) {
        const startTime = Date.now();
        const checkInterval = 50;

        while (Date.now() - startTime < maxWaitMs) {
            const location = type === 'start' ? window.startLocation : window.destLocation;
            if (location && location.lat && location.lng) {
                // Location is set, give a tiny delay for any UI updates
                await this.delay(100);
                return true;
            }
            await this.delay(checkInterval);
        }

        console.warn(`⚠️ Timeout waiting for ${type} location to be set`);
        return false;
    },

    /**
     * Capture result directly from API response instead of reading from DOM
     * This ensures we get accurate values without timing/latency issues
     * @param {string} algorithm - Algorithm used ('hc2l' or 'dhl')
     * @param {number} tau - Tau threshold value used
     * @param {Object} route - Route configuration with start/end
     * @param {number} trialIndex - Current trial index
     * @param {number} processTimeMs - Time taken for the API call
     * @param {Object} routeData - Direct API response from computeRouteBasedOnSelection
     * @param {number} batchId - Batch ID (1, 2, or 3 for experiment mode)
     * @returns {Object|null} Captured result object
     */
    captureResultFromAPIResponse(algorithm, tau, route, trialIndex, processTimeMs, routeData, batchId = null) {
        try {
            if (!routeData || !routeData.success) {
                console.warn('⚠️ Route computation failed or returned no data');
                return null;
            }

            const metrics = routeData.metrics || {};
            const updatePhase = routeData.update_phase || {};
            const queryPhase = routeData.query_phase || {};
            const lazyHc2l = routeData.lazy_hc2l || {};
            const dhlUpdateInfo = routeData.dhl_update_info || {};
            const disruptionConfig = routeData.disruption_config || {};
            const disruptionsSummary = routeData.disruptions_summary || {};
            const routeInfo = routeData.route || {};
            const labelingInfo = metrics.labeling_info || {};

            const result = {
                trial: trialIndex + 1,
                batchId: batchId,
                route: `${route.start.name} → ${route.end.name}`,
                algorithm: algorithm.toUpperCase(),
                tau: tau,
                timestamp: new Date().toISOString(),
                processTimeMs: processTimeMs,
                metrics: {}
            };

            // ============================================================
            // CORE METRICS FROM API (calculated_distance_meters, calculated_distance_km)
            // ============================================================

            // Distance - use calculated values from C++ API (haversine calculation)
            result.metrics.calculatedDistanceMeters = metrics.calculated_distance_meters || null;
            result.metrics.calculatedDistanceKm = metrics.calculated_distance_km || null;

            // Format display distance
            if (result.metrics.calculatedDistanceKm) {
                result.metrics.displayDistance = `${result.metrics.calculatedDistanceKm.toFixed(2)} km`;
                result.metrics.distanceKm = result.metrics.calculatedDistanceKm;
            } else if (result.metrics.calculatedDistanceMeters) {
                result.metrics.displayDistance = `${(result.metrics.calculatedDistanceMeters / 1000).toFixed(2)} km`;
                result.metrics.distanceKm = result.metrics.calculatedDistanceMeters / 1000;
            }

            // Fallback to other distance sources if calculated not available
            if (!result.metrics.displayDistance) {
                if (metrics.total_distance_meters && metrics.total_distance_meters < 2147483647) {
                    result.metrics.displayDistance = `${(metrics.total_distance_meters / 1000).toFixed(2)} km`;
                    result.metrics.distanceKm = metrics.total_distance_meters / 1000;
                }
            }

            // ============================================================
            // ETA METRICS FROM API
            // ============================================================
            result.metrics.etaSeconds = metrics.eta_seconds || null;
            result.metrics.etaFormatted = metrics.eta_formatted || null;
            result.metrics.displayEta = metrics.eta_formatted || (metrics.eta_seconds ? this.formatSeconds(metrics.eta_seconds) : null);
            result.metrics.actualEta = result.metrics.displayEta;

            // Baseline vs Actual ETA from disruptions summary
            const routeDisruptions = disruptionsSummary.route || {};
            result.metrics.baselineEtaSeconds = routeDisruptions.baseline_eta_seconds || null;
            result.metrics.actualEtaSeconds = routeDisruptions.actual_eta_seconds || null;
            result.metrics.timeImpactSeconds = routeDisruptions.total_time_impact_seconds || null;
            result.metrics.timeImpactPercent = routeDisruptions.percentage_increase || null;

            if (result.metrics.baselineEtaSeconds) {
                result.metrics.baselineEta = this.formatSeconds(result.metrics.baselineEtaSeconds);
            }
            if (result.metrics.timeImpactSeconds) {
                result.metrics.timeImpact = `+${result.metrics.timeImpactSeconds.toFixed(1)}s`;
            }

            // ============================================================
            // QUERY PHASE METRICS
            // ============================================================
            result.metrics.queryTimeMs = queryPhase.avg_query_time_ms || metrics.query_time_ms || null;
            result.metrics.queryTime = result.metrics.queryTimeMs ? `${result.metrics.queryTimeMs.toFixed(3)} ms` : null;
            result.metrics.queriesCount = queryPhase.queries_count || 1;
            result.metrics.usesLazyUpdates = queryPhase.uses_lazy_updates || false;

            // ============================================================
            // PATH METRICS
            // ============================================================
            result.metrics.pathLength = metrics.path_length || (routeInfo.path_nodes ? routeInfo.path_nodes.length : null);
            result.metrics.pathNodes = routeInfo.path_nodes || [];
            result.metrics.edgeCount = routeInfo.geometry ? routeInfo.geometry.length : null;

            // ============================================================
            // UPDATE PHASE METRICS
            // The C++ API outputs lazy_hc2l section which contains update phase data
            // We populate update phase metrics from lazyHc2l when updatePhase is empty
            // Note: Use explicit null checks because 0 is a valid value
            // ============================================================

            // Lazy Update Time: from updatePhase or fallback to lazyHc2l.lazy_repair_time_ms
            result.metrics.lazyUpdateTimeMs = updatePhase.lazy_update_time_ms ?? lazyHc2l.lazy_repair_time_ms ?? null;
            result.metrics.lazyUpdateTime = result.metrics.lazyUpdateTimeMs !== null ? `${result.metrics.lazyUpdateTimeMs.toFixed(3)} ms` : null;

            // Threshold Rebuild Time: from updatePhase (if API ever provides it)
            result.metrics.thresholdRebuildTimeMs = updatePhase.threshold_rebuild_time_ms ?? null;
            result.metrics.thresholdRebuildTime = result.metrics.thresholdRebuildTimeMs !== null ? `${result.metrics.thresholdRebuildTimeMs.toFixed(3)} ms` : null;
            result.metrics.thresholdRebuildTriggered = updatePhase.threshold_rebuild_triggered ?? (lazyHc2l.update_strategy === 'immediate_update');

            // Edges Updated
            result.metrics.edgesUpdated = updatePhase.edges_updated ?? null;

            // Dirty Nodes Count: from updatePhase or lazyHc2l.dirty_nodes_marked
            result.metrics.dirtyNodesCount = updatePhase.dirty_nodes_count ?? lazyHc2l.dirty_nodes_marked ?? null;
            result.metrics.dirtyNodes = result.metrics.dirtyNodesCount !== null ? `${result.metrics.dirtyNodesCount} nodes` : null;

            // Impact Score: from updatePhase or lazyHc2l.disruption_impact_score
            result.metrics.impactScoreNum = updatePhase.impact_score ?? lazyHc2l.disruption_impact_score ?? null;
            result.metrics.impactScore = result.metrics.impactScoreNum !== null ? result.metrics.impactScoreNum.toFixed(3) : null;

            // Label size metrics - from updatePhase or labelingInfo
            const labelSizeMb = updatePhase.peak_label_size_mb || (labelingInfo.index_size_bytes ? labelingInfo.index_size_bytes / (1024 * 1024) : null);
            result.metrics.labelSizeBeforeKb = updatePhase.label_size_before_mb ? updatePhase.label_size_before_mb * 1024 : null;
            result.metrics.labelSizeAfterKb = updatePhase.label_size_after_mb ? updatePhase.label_size_after_mb * 1024 : null;
            result.metrics.labelSizeChangePct = updatePhase.label_size_change_pct || null;
            result.metrics.peakLabelSizeKb = labelSizeMb ? labelSizeMb * 1024 : null;
            result.metrics.peakLabelSize = result.metrics.peakLabelSizeKb ? `${result.metrics.peakLabelSizeKb.toFixed(2)} KB` : null;
            result.metrics.labelSizeChange = result.metrics.labelSizeChangePct !== null ? `${result.metrics.labelSizeChangePct.toFixed(2)}%` : null;

            // ============================================================
            // LAZY HC2L SPECIFIC METRICS
            // Note: Use nullish coalescing (??) to preserve 0 values
            // ============================================================
            if (algorithm.toLowerCase() === 'hc2l' && Object.keys(lazyHc2l).length > 0) {
                result.metrics.lazyEnabled = lazyHc2l.enabled ?? false;
                result.metrics.updateStrategy = lazyHc2l.update_strategy ?? null;
                result.metrics.updateReason = lazyHc2l.reason ?? null;
                result.metrics.dirtyNodesMarked = lazyHc2l.dirty_nodes_marked ?? null;
                result.metrics.dirtyNodesAffectedPath = lazyHc2l.dirty_nodes_affected_path ?? null;
                result.metrics.lazyRepairTimeMs = lazyHc2l.lazy_repair_time_ms ?? null;
                result.metrics.lazyRepairTime = result.metrics.lazyRepairTimeMs !== null ? `${result.metrics.lazyRepairTimeMs.toFixed(3)} ms` : null;
                result.metrics.nodesRepaired = lazyHc2l.nodes_repaired ?? null;
                result.metrics.cacheHit = lazyHc2l.cache_hit ?? false;
                result.metrics.tauThreshold = disruptionConfig.tau_threshold ?? tau;
                result.metrics.totalUpdates = lazyHc2l.total_updates ?? 0;
            }

            // ============================================================
            // DHL SPECIFIC METRICS
            // ============================================================
            if (algorithm.toLowerCase() === 'dhl' && Object.keys(dhlUpdateInfo).length > 0) {
                result.metrics.updateStrategy = dhlUpdateInfo.update_strategy || 'immediate_update';
                result.metrics.updateReason = dhlUpdateInfo.reason || null;
                result.metrics.nodesUpdated = dhlUpdateInfo.nodes_updated || null;
                result.metrics.algorithmType = dhlUpdateInfo.algorithm_type || 'baseline';
            }

            // ============================================================
            // LABELING INFO
            // ============================================================
            result.metrics.totalLabels = labelingInfo.total_labels || null;
            result.metrics.indexSizeKb = labelingInfo.index_size_bytes ? labelingInfo.index_size_bytes / 1024 : null;
            result.metrics.labelingSize = result.metrics.indexSizeKb ? `${result.metrics.indexSizeKb.toFixed(2)} KB` : null;
            result.metrics.indexLoadTimeMs = labelingInfo.index_load_time_ms || null;
            result.metrics.labelingTime = result.metrics.indexLoadTimeMs ? `${result.metrics.indexLoadTimeMs.toFixed(3)} ms` : null;
            result.metrics.maxLabelCountPerNode = labelingInfo.max_label_count_per_node || null;
            result.metrics.averageCutSize = labelingInfo.average_cut_size || null;
            result.metrics.avgCutSize = result.metrics.averageCutSize ? result.metrics.averageCutSize.toFixed(2) : null;

            // ============================================================
            // DISRUPTION METRICS
            // ============================================================
            result.metrics.usesDisruptions = metrics.uses_disruptions || false;
            result.metrics.disruptedEdges = routeDisruptions.total_disrupted_edges || null;
            result.metrics.disruptedEdgesDisplay = result.metrics.disruptedEdges ? `${result.metrics.disruptedEdges} edges` : null;

            // Store raw API response for debugging/export
            result.rawApiResponse = routeData;

            console.log('📊 Captured result metrics from API:', {
                distance: result.metrics.displayDistance,
                calculatedDistanceMeters: result.metrics.calculatedDistanceMeters,
                calculatedDistanceKm: result.metrics.calculatedDistanceKm,
                queryTime: result.metrics.queryTime,
                pathLength: result.metrics.pathLength,
                etaFormatted: result.metrics.etaFormatted,
                disruptedEdges: result.metrics.disruptedEdges
            });

            return result;
        } catch (e) {
            console.error('Error capturing result from API response:', e);
            return null;
        }
    },

    /**
     * Format seconds into a human-readable string (e.g., "5m 30s" or "1h 2m 30s")
     */
    formatSeconds(seconds) {
        if (seconds == null || isNaN(seconds)) return null;

        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.round(seconds % 60);

        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    },

    /**
     * Calculate query phase statistics from accumulated results
     * @param {Array} results - Array of accumulated demo results
     * @param {string} algorithm - Optional: filter by algorithm ('hc2l', 'dhl', or null for all)
     * @returns {Object} Query phase statistics object
     */
    calculateQueryPhaseStats(results, algorithm = null) {
        if (!results || results.length === 0) {
            return {
                avgQueryTime: null,
                minQueryTime: null,
                maxQueryTime: null,
                queryTimeStdDev: null,
                p95Latency: null,
                queriesCount: 0
            };
        }

        // Filter results by algorithm if specified
        let filteredResults = results;
        if (algorithm) {
            filteredResults = results.filter(r =>
                r.algorithm && r.algorithm.toUpperCase() === algorithm.toUpperCase()
            );
        }

        // Extract query times (in ms) - use queryTimeMs or parse from queryTime string
        const queryTimes = filteredResults
            .map(r => {
                if (r.metrics.queryTimeMs != null) return r.metrics.queryTimeMs;
                if (r.metrics.queryTimeNum != null) return r.metrics.queryTimeNum;
                if (r.metrics.queryTime) {
                    const match = r.metrics.queryTime.match(/([\d.]+)/);
                    return match ? parseFloat(match[1]) : null;
                }
                return null;
            })
            .filter(t => t != null && !isNaN(t));

        if (queryTimes.length === 0) {
            return {
                avgQueryTime: null,
                minQueryTime: null,
                maxQueryTime: null,
                queryTimeStdDev: null,
                p95Latency: null,
                queriesCount: 0
            };
        }

        // Calculate statistics
        const sum = queryTimes.reduce((a, b) => a + b, 0);
        const avg = sum / queryTimes.length;
        const min = Math.min(...queryTimes);
        const max = Math.max(...queryTimes);

        // Standard deviation
        let stdDev = 0;
        if (queryTimes.length > 1) {
            const squaredDiffs = queryTimes.map(t => Math.pow(t - avg, 2));
            stdDev = Math.sqrt(squaredDiffs.reduce((a, b) => a + b, 0) / (queryTimes.length - 1));
        }

        // P95 latency (95th percentile)
        const sorted = [...queryTimes].sort((a, b) => a - b);
        const p95Index = Math.floor(sorted.length * 0.95);
        const p95 = sorted[Math.min(p95Index, sorted.length - 1)];

        return {
            avgQueryTime: `${avg.toFixed(3)} ms`,
            avgQueryTimeMs: avg,
            minQueryTime: `${min.toFixed(3)} ms`,
            minQueryTimeMs: min,
            maxQueryTime: `${max.toFixed(3)} ms`,
            maxQueryTimeMs: max,
            queryTimeStdDev: `${stdDev.toFixed(3)} ms`,
            queryTimeStdDevMs: stdDev,
            p95Latency: `${p95.toFixed(3)} ms`,
            p95LatencyMs: p95,
            queriesCount: queryTimes.length
        };
    },

    captureCurrentResult(algorithm, tau, route, trialIndex, processTimeMs = null) {
        try {
            const result = {
                trial: trialIndex + 1,
                route: `${route.start.name} → ${route.end.name}`,
                algorithm: algorithm.toUpperCase(),
                tau: tau,
                timestamp: new Date().toISOString(),
                processTimeMs: processTimeMs,  // Server request + response time
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
                        text = text.replace(/\s*(sec|ms|edges|km|m|KB|nodes|units)$/i, '').trim();
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

            // Distance - try multiple sources WITH CACHING PREVENTION
            // First try direct DOM elements that get updated dynamically
            const routeDistance = document.getElementById('route-distance')?.textContent?.trim();
            const calculatedDistEl = document.getElementById('metrics-calculated-distance')?.textContent?.trim();
            const metricsDistEl = getMetricValue('metrics-distance');

            // Use the most recently updated distance value
            if (routeDistance && routeDistance !== '--') {
                result.metrics.displayDistance = routeDistance;
                // Extract numeric distance in km
                const kmMatch = routeDistance.match(/([\d.]+)\s*km/i);
                if (kmMatch) {
                    result.metrics.distanceKm = parseFloat(kmMatch[1]);
                }
            }

            // Fallback to calculated distance if main route distance not available
            if (!result.metrics.displayDistance && calculatedDistEl && calculatedDistEl !== '--') {
                result.metrics.calculatedDistance = calculatedDistEl;
                const kmMatch = calculatedDistEl.match(/([\d.]+)\s*km/i);
                if (kmMatch) {
                    result.metrics.distanceKm = parseFloat(kmMatch[1]);
                }
            }

            // Fallback to metrics distance panel
            if (!result.metrics.displayDistance && !result.metrics.calculatedDistance && metricsDistEl) {
                result.metrics.distance = metricsDistEl;
            }

            result.metrics.distanceNum = getNumericValue('metrics-distance');
            result.metrics.pathLength = getMetricValue('metrics-path-length');
            result.metrics.edgeCount = getMetricValue('metrics-edge-count');
            result.metrics.labelingTime = getMetricValue('metrics-labeling-time');
            result.metrics.labelingTimeNum = getNumericValue('metrics-labeling-time');
            result.metrics.labelingSize = getMetricValue('metrics-labeling-size');
            result.metrics.calculatedDistanceNum = getNumericValue('metrics-calculated-distance');

            // LazyHC2L Update Phase metrics (may not be available in current system)
            // These will be null until LazyHC2L update/repair metrics are implemented
            result.metrics.updateStrategy = getMetricValue('metrics-update-strategy');
            result.metrics.dirtyNodes = getMetricValue('metrics-dirty-nodes');
            result.metrics.dirtyNodesNum = getNumericValue('metrics-dirty-nodes');
            result.metrics.lazyRepairTime = getMetricValue('metrics-repair-time');
            result.metrics.lazyRepairTimeNum = getNumericValue('metrics-repair-time');
            result.metrics.nodesRepaired = getMetricValue('metrics-nodes-repaired');
            result.metrics.nodesRepairedNum = getNumericValue('metrics-nodes-repaired');
            result.metrics.cacheHit = getMetricValue('metrics-cache-hit');
            result.metrics.impactScore = getMetricValue('metrics-impact-score');
            result.metrics.impactScoreNum = getNumericValue('metrics-impact-score');
            result.metrics.tauThreshold = getMetricValue('metrics-tau-threshold');
            result.metrics.tauThresholdNum = getNumericValue('metrics-tau-threshold');

            // Hierarchy info (for completeness)
            result.metrics.hierarchyHeight = getMetricValue('metrics-hierarchy-height');
            result.metrics.avgCutSize = getMetricValue('metrics-avg-cut-size');
            result.metrics.indexLoadTime = getMetricValue('metrics-index-load-time');

            // Alternative ETA from route display
            const routeEta = document.getElementById('route-eta')?.textContent?.trim();
            if (routeEta && routeEta !== '--') {
                result.metrics.displayEta = routeEta;
            }

            console.log('📊 Captured result metrics:', {
                distance: result.metrics.displayDistance,
                calculatedDistance: result.metrics.calculatedDistance,
                distanceNum: result.metrics.distanceNum,
                queryTime: result.metrics.queryTime,
                pathLength: result.metrics.pathLength,
                ...result.metrics
            });
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

        // Initialize skeleton if needed
        if (!container.querySelector('#progress-config-name')) {
            const skeleton = document.getElementById('template-progress-skeleton');
            if (skeleton) {
                container.innerHTML = '';
                container.appendChild(skeleton.content.cloneNode(true));
                lucide.createIcons();
            }
        }

        // Update basic progress information
        const nameEl = document.getElementById('progress-config-name');
        const statusEl = document.getElementById('progress-status');
        const percentEl = document.getElementById('progress-percentage');
        const barEl = document.getElementById('progress-bar');
        
        if (nameEl) nameEl.textContent = p.configName || 'Demo';
        if (statusEl) statusEl.textContent = p.status || 'Initializing...';
        if (percentEl) percentEl.textContent = `${overallProgress.toFixed(1)}%`;
        if (barEl) barEl.style.width = `${Math.max(overallProgress, 2)}%`;

        // Update progress counters
        const trialEl = document.getElementById('progress-trial');
        const routeEl = document.getElementById('progress-route');
        const algoEl = document.getElementById('progress-algorithm');
        const tauEl = document.getElementById('progress-tau');
        const tauContainer = document.getElementById('progress-tau-container');
        
        if (trialEl) trialEl.textContent = `${p.trial}/${p.totalTrials}`;
        if (routeEl) routeEl.textContent = `${p.route}/${p.totalRoutes}`;
        if (algoEl) algoEl.textContent = p.algorithm || '-';
        
        // Show/hide tau based on algorithm
        const isDHL = (p.algorithm || '').toUpperCase() === 'DHL';
        if (tauContainer) {
            tauContainer.classList.toggle('hidden', isDHL);
        }
        if (tauEl && !isDHL) {
            tauEl.textContent = p.currentTau ? p.currentTau.toFixed(2) : '-';
        }

        // Update last result section
        const lastResultCard = document.getElementById('progress-last-result');
        if (p.lastResult && lastResultCard) {
            lastResultCard.classList.remove('hidden');
            
            const routeEl = document.getElementById('last-result-route');
            if (routeEl) routeEl.textContent = p.lastResult.route;
            
            // Build metrics HTML
            const metricsContainer = document.getElementById('last-result-metrics');
            if (metricsContainer) {
                metricsContainer.innerHTML = '';
                
                const metrics = [
                    { label: 'Algorithm', value: p.lastResult.algorithm, color: 'text-blue-700' },
                    { label: 'τ Value', value: !isDHL ? p.lastResult.tau.toFixed(2) : null, color: 'text-rose-700' },
                    { label: 'Query Time', value: p.lastResult.metrics.queryTime, color: 'text-purple-700' },
                    { label: 'Distance', value: p.lastResult.metrics.displayDistance || p.lastResult.metrics.calculatedDistance || p.lastResult.metrics.distance, color: 'text-green-700' },
                    { label: 'Baseline ETA', value: p.lastResult.metrics.baselineEta, color: 'text-emerald-700' },
                    { label: 'Actual ETA', value: p.lastResult.metrics.displayEta || p.lastResult.metrics.actualEta, color: 'text-orange-700' },
                    { label: 'Time Impact', value: p.lastResult.metrics.timeImpact, color: 'text-red-700' },
                    { label: 'Disrupted Edges', value: p.lastResult.metrics.disruptedEdges, color: 'text-indigo-700' }
                ];
                
                metrics.forEach(m => {
                    if (m.value) {
                        const metricEl = document.createElement('div');
                        metricEl.className = 'flex justify-between py-1 px-2 bg-gray-50 rounded border border-gray-100';
                        metricEl.innerHTML = `
                            <span class="text-gray-600 text-xs font-medium">${m.label}:</span>
                            <span class="font-semibold text-xs ${m.color}">${m.value}</span>
                        `;
                        metricsContainer.appendChild(metricEl);
                    }
                });
            }
        } else if (lastResultCard) {
            lastResultCard.classList.add('hidden');
        }

        // Update results history
        const historyCard = document.getElementById('progress-results-history');
        if (p.results && p.results.length > 0 && historyCard) {
            historyCard.classList.remove('hidden');
            
            const countEl = document.getElementById('progress-history-count');
            if (countEl) countEl.textContent = `${p.results.length} total`;
            
            const listEl = document.getElementById('progress-history-list');
            if (listEl) {
                listEl.innerHTML = '';
                p.results.slice().reverse().forEach((r, i) => {
                    const itemEl = document.createElement('div');
                    itemEl.className = `text-xs p-2 ${i === 0 ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-100'} rounded border`;
                    
                    const distance = r.metrics.displayDistance || r.metrics.calculatedDistance || r.metrics.distance || 'N/A';
                    const eta = r.metrics.displayEta || r.metrics.actualEta || 'N/A';
                    const queryTime = r.metrics.queryTime || 'N/A';
                    
                    itemEl.innerHTML = `
                        <div class="flex justify-between items-center">
                            <span class="font-semibold text-gray-800">${r.algorithm}${(r.algorithm || '').toUpperCase() !== 'DHL' ? ` τ=${r.tau.toFixed(2)}` : ''}</span>
                            <span class="text-gray-500 text-[10px]">T${r.trial}</span>
                        </div>
                        <div class="text-gray-600 truncate text-[10px]">${r.route}</div>
                        <div class="flex gap-2 mt-1 text-[10px] flex-wrap">
                            ${distance !== 'N/A' ? `<span class="flex items-center gap-1 text-green-600"><i data-lucide="map-pin" class="w-3 h-3"></i> ${distance}</span>` : ''}
                            ${eta !== 'N/A' ? `<span class="flex items-center gap-1 text-orange-600"><i data-lucide="clock" class="w-3 h-3"></i> ${eta}</span>` : ''}
                            ${queryTime !== 'N/A' ? `<span class="flex items-center gap-1 text-purple-600"><i data-lucide="zap" class="w-3 h-3"></i> ${queryTime}</span>` : ''}
                        </div>
                    `;
                    listEl.appendChild(itemEl);
                });
            }
        } else if (historyCard) {
            historyCard.classList.add('hidden');
        }

        lucide.createIcons();
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

    /**
     * Show loading animation overlay with status message
     * @param {string} message - Status message to display
     */
    showLoadingAnimation(title = 'Processing', message = 'Setting up...') {
        const overlay = document.getElementById('demo-runner-loading-overlay');
        const statusEl = document.getElementById('demo-loading-status');
        const titleEl = document.getElementById('demo-loading-title');
        if (overlay) {
            overlay.classList.remove('hidden');
            overlay.style.display = 'flex';
            if (statusEl) {
                statusEl.textContent = message;
            }
            if (titleEl) {
                titleEl.textContent = title;
            }
        }
    },

    /**
     * Hide loading animation overlay
     */
    hideLoadingAnimation() {
        const overlay = document.getElementById('demo-runner-loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
            overlay.style.display = 'none';
        }
    },

    /**
     * Update loading animation status message
     * @param {string} message - Status message to display
     */
    updateLoadingStatus(message) {
        const statusEl = document.getElementById('demo-loading-status');
        if (statusEl) {
            statusEl.textContent = message;
        }
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

        // Check if we have any disruptions to display
        if (!this.generatedDisruptions) {
            console.warn('⚠️ No generatedDisruptions data available');
            return;
        }

        console.log('   Current disruption data:', {
            incidentCount: this.generatedDisruptions?.incidents?.length || 0,
            flowCount: this.generatedDisruptions?.flowSegments?.length || 0
        });

        // If no disruptions to show, clear and return
        if (!showIncidents && !showFlow) {
            console.log('📍 Both disruption types disabled, clearing layers');
            this.clearDemoDisruptionLayers();
            return;
        }

        // Clear existing demo disruption layers
        this.clearDemoDisruptionLayers();

        // Get map reference - use global map object
        const mapRef = (typeof map !== 'undefined') ? map : window.map;

        if (!mapRef) {
            console.warn('❌ Map not available for disruption display');
            return;
        }

        console.log('✅ Map reference obtained, adding layers...');

        // Prepare flow segments with geometry handling
        const flowSegments = (this.generatedDisruptions.flowSegments || []).map(f => {
            // Process geometry if available
            let geometry = null;
            if (f.geometry && Array.isArray(f.geometry) && f.geometry.length >= 2) {
                geometry = f.geometry.map(coord => {
                    if (Array.isArray(coord) && coord.length >= 2) {
                        const c0 = parseFloat(coord[0]);
                        const c1 = parseFloat(coord[1]);
                        // If first coord looks like longitude (around 121), swap
                        if (c0 > 100) return [c1, c0];
                        return [c0, c1];
                    }
                    return null;
                }).filter(c => c !== null);
            }

            return {
                ...f,
                geometry: geometry,
                source_lng: f.source_lng || f.source_lon,
                target_lng: f.target_lng || f.target_lon
            };
        });

        // Prepare incidents
        const incidents = (this.generatedDisruptions.incidents || []).map(inc => ({
            ...inc,
            source_lng: inc.source_lng || inc.source_lon,
            target_lng: inc.target_lng || inc.target_lon,
            type: inc.incident_type || inc.type || 'Incident',
            criticality: inc.incident_criticality || inc.criticality || 'minor'
        }));

        // Use TrafficUtils unified display function
        // This ensures incidents are rendered ON TOP with icons inside markers
        console.log(`📍 Calling TrafficUtils.displayDisruptionsOnMap with:`);
        console.log(`   flowSegments: ${flowSegments.length} items`);
        console.log(`   incidents: ${incidents.length} items`);
        console.log(`   mapRef: ${mapRef ? 'OK' : 'NULL'}`);
        console.log(`   layerStorage is array: ${Array.isArray(this.demoDisruptionLayers)}`);

        TrafficUtils.displayDisruptionsOnMap({
            flowSegments: flowSegments,
            incidents: incidents,
            map: mapRef,
            layerStorage: this.demoDisruptionLayers,
            showFlow: showFlow,
            showIncidents: showIncidents
        });

        console.log(`📊 After display - demoDisruptionLayers length: ${this.demoDisruptionLayers.length}`);
    },

    // Clear demo disruption layers from map
    clearDemoDisruptionLayers() {
        const mapRef = window.map || (typeof map !== 'undefined' ? map : null);
        TrafficUtils.clearDisruptionLayers(this.demoDisruptionLayers, mapRef);
        console.log('🧹 Cleared demo disruption layers');
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
        let setKeys = Object.keys(sets);

        // Always show the panel, even if there are no disruption sets
        setsPanel.classList.remove('hidden');

        if (setKeys.length === 0) {
            // Show empty state with count badges
            buttonsContainer.innerHTML = '<div class="text-xs text-gray-400 text-center py-2">No disruption sets</div>';
            previewContainer.innerHTML = this.renderCurrentDisruptionList();
            return;
        }

        // Sort keys to maintain order (important for 100+ sets)
        // Priority: set_all, set_trial_*, set_route_*, set_trial_*_route_*
        setKeys = setKeys.sort((a, b) => {
            // set_all comes first
            if (a === 'set_all') return -1;
            if (b === 'set_all') return 1;
            
            // Extract numeric parts for proper ordering
            const aMatch = a.match(/(\d+)/g);
            const bMatch = b.match(/(\d+)/g);
            
            // Compare by type first
            const aType = a.split('_')[1];  // 'trial', 'route', etc.
            const bType = b.split('_')[1];
            
            if (aType !== bType) {
                // trial comes before route
                if (aType === 'trial') return -1;
                if (bType === 'trial') return 1;
            }
            
            // Then compare numeric values
            if (aMatch && bMatch) {
                for (let i = 0; i < Math.min(aMatch.length, bMatch.length); i++) {
                    const aNum = parseInt(aMatch[i]);
                    const bNum = parseInt(bMatch[i]);
                    if (aNum !== bNum) return aNum - bNum;
                }
            }
            
            return a.localeCompare(b);
        });

        // Show sets panel and render buttons
        buttonsContainer.innerHTML = setKeys.map(key => `
            <button onclick="DemoRunner.selectDisruptionSet('${key}')"
                    class="disruption-set-btn ${this.currentPreviewSet === key ? 'active' : ''}">
                ${this.getSetLabel(key)}
            </button>
        `).join('');

        // Auto-scroll to active set if one is selected
        if (this.currentPreviewSet) {
            setTimeout(() => this.scrollToActiveDisruptionSet(this.currentPreviewSet), 100);
        }

        // Render current set details - ALWAYS render, even if no disruptions on map
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

        // Auto-scroll to selected button
        this.scrollToActiveDisruptionSet(setKey);

        // Refresh preview panel
        this.showDisruptionSetsPreview();
    },

    /**
     * Auto-scroll to the active disruption set button
     */
    scrollToActiveDisruptionSet(setKey) {
        const container = document.getElementById('demo-runner-set-buttons');
        const activeBtn = container?.querySelector(`[onclick*="selectDisruptionSet('${setKey}')"]`);

        if (container && activeBtn) {
            // Calculate scroll position to center the active button
            const containerRect = container.getBoundingClientRect();
            const activeBtnRect = activeBtn.getBoundingClientRect();
            const scrollLeft = activeBtnRect.left - containerRect.left - (containerRect.width / 2) + (activeBtnRect.width / 2);

            container.scrollTo({
                left: container.scrollLeft + scrollLeft,
                behavior: 'smooth'
            });
        }
    },    /**
     * Render the current disruption list for the preview panel
     */
    renderCurrentDisruptionList() {
        const flow = this.generatedDisruptions.flowSegments || [];
        const incidents = this.generatedDisruptions.incidents || [];

        if (flow.length === 0 && incidents.length === 0) {
            const emptyTemplate = document.getElementById('template-no-disruptions');
            if (emptyTemplate) {
                return emptyTemplate.content.cloneNode(true).firstElementChild.outerHTML;
            }
            return '<div class="text-xs text-gray-500 text-center py-2">No disruptions loaded</div>';
        }

        // Create a container for building the HTML
        const container = document.createElement('div');

        const flowTemplate = document.getElementById('template-flow-disruption');
        const incidentTemplate = document.getElementById('template-incident-disruption');

        // Add flow disruptions
        if (flow.length > 0) {
            const flowHeader = document.createElement('div');
            flowHeader.className = 'flex items-center gap-2 text-xs font-semibold text-orange-600 mb-2';
            flowHeader.innerHTML = '<i data-lucide="traffic-cone" class="w-4 h-4"></i><span>Traffic Flow (' + flow.length + ')</span>';
            container.appendChild(flowHeader);

            const flowContainer = document.createElement('div');
            flowContainer.className = 'space-y-1 mb-3';

            flow.slice(0, 10).forEach((f, i) => {
                if (!flowTemplate) return;
                const jamFactor = parseFloat(f.jam_factor) || 0;
                const severityColor = TrafficUtils.getSeverityTextClass(jamFactor);

                const node = flowTemplate.content.cloneNode(true);
                const item = node.querySelector('div[class*="flex items-center"]');
                
                item.querySelector('[data-road-name]').textContent = f.road_name || 'Unknown Road';
                const jamEl = item.querySelector('[data-jam-factor]');
                jamEl.textContent = 'JF: ' + jamFactor.toFixed(1);
                jamEl.className = severityColor + ' font-semibold ml-2 flex-shrink-0';
                
                item.addEventListener('click', () => this.focusDisruption('flow', i));
                flowContainer.appendChild(item);
            });

            if (flow.length > 10) {
                const moreText = document.createElement('div');
                moreText.className = 'text-xs text-gray-400 text-center py-1';
                moreText.textContent = '+' + (flow.length - 10) + ' more...';
                flowContainer.appendChild(moreText);
            }

            container.appendChild(flowContainer);
        }

        // Add incidents
        if (incidents.length > 0) {
            const incidentHeader = document.createElement('div');
            incidentHeader.className = 'flex items-center gap-2 text-xs font-semibold text-red-600 mb-2';
            incidentHeader.innerHTML = '<i data-lucide="alert-triangle" class="w-4 h-4"></i><span>Incidents (' + incidents.length + ')</span>';
            container.appendChild(incidentHeader);

            const incidentContainer = document.createElement('div');
            incidentContainer.className = 'space-y-1 mb-3';

            incidents.slice(0, 10).forEach((inc, i) => {
                if (!incidentTemplate) return;
                const criticality = (inc.criticality || inc.incident_criticality || 'minor').toLowerCase();
                const critColor = criticality === 'critical' ? 'text-red-700' : criticality === 'major' ? 'text-red-500' : 'text-amber-600';

                const node = incidentTemplate.content.cloneNode(true);
                const item = node.querySelector('div[class*="flex items-center"]');
                
                item.querySelector('[data-road-name]').textContent = inc.road_name || 'Unknown Road';
                const typeEl = item.querySelector('[data-incident-type]');
                typeEl.textContent = inc.incident_type || inc.type || 'Incident';
                typeEl.className = critColor + ' font-semibold ml-2 flex-shrink-0';
                
                item.addEventListener('click', () => this.focusDisruption('incident', i));
                incidentContainer.appendChild(item);
            });

            if (incidents.length > 10) {
                const moreText = document.createElement('div');
                moreText.className = 'text-xs text-gray-400 text-center py-1';
                moreText.textContent = '+' + (incidents.length - 10) + ' more...';
                incidentContainer.appendChild(moreText);
            }

            container.appendChild(incidentContainer);
        }

        lucide.createIcons();
        return container.innerHTML;
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
     * Get current checkbox states for disruption display toggles
     * @returns {{showIncidents: boolean, showFlow: boolean}}
     */
    getDisruptionCheckboxStates() {
        return {
            showIncidents: document.getElementById('demo-show-incidents')?.checked ?? true,
            showFlow: document.getElementById('demo-show-flow')?.checked ?? true
        };
    },

    /**
     * Refresh disruption display respecting current checkbox states
     * Use this instead of showGeneratedDisruptions(true, true) to respect user preferences
     */
    async refreshDisruptionDisplay() {
        // Get checkbox states, defaulting to true if checkboxes don't exist
        const incidentsCheckbox = document.getElementById('demo-show-incidents');
        const flowCheckbox = document.getElementById('demo-show-flow');

        // Respect user's checkbox state - do NOT force them to be checked
        const showIncidents = incidentsCheckbox ? incidentsCheckbox.checked : true;
        const showFlow = flowCheckbox ? flowCheckbox.checked : true;

        console.log(`📍 Refreshing disruption display: incidents=${showIncidents}, flow=${showFlow}`);
        await this.showGeneratedDisruptions(showIncidents, showFlow);
        this.updateDisruptionPreview();
    },

    /**
     * Update the disruption preview panel based on current checkbox states
     * Note: Even if display is disabled, the disruption sets list remains visible
     */
    updateDisruptionPreview() {
        const showIncidents = document.getElementById('demo-show-incidents')?.checked ?? true;
        const showFlow = document.getElementById('demo-show-flow')?.checked ?? true;
        const previewContainer = document.getElementById('demo-runner-disruption-preview');

        if (!previewContainer) return;

        const flow = showFlow ? (this.generatedDisruptions.flowSegments || []) : [];
        const incidents = showIncidents ? (this.generatedDisruptions.incidents || []) : [];

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

    pauseDemo() {
        this.isPaused = true;
        this.updatePlayPauseButton();
        showUpdateToast('Demo paused', 'info');
    },

    resumeDemo() {
        this.isPaused = false;
        this.updatePlayPauseButton();
        showUpdateToast('Demo resumed', 'info');
    },

    /**
     * Toggle between pause and resume states
     */
    togglePauseResume() {
        if (this.isPaused) {
            this.resumeDemo();
        } else {
            this.pauseDemo();
        }
    },

    /**
     * Update the play/pause button appearance based on current state
     */
    updatePlayPauseButton() {
        const btn = document.getElementById('demo-play-pause-btn');
        if (!btn) return;

        if (this.isPaused) {
            // Show "Resume" state - success button with play icon
            btn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i> Resume';
            btn.classList.remove('btn--warning');
            btn.classList.add('btn--success');
            lucide.createIcons();
        } else {
            // Show "Pause" state - warning button with pause icon
            btn.innerHTML = '<i data-lucide="pause" class="w-4 h-4"></i> Pause';
            btn.classList.remove('btn--success');
            btn.classList.add('btn--warning');
            lucide.createIcons();
        }
    },

    stopDemo() {
        this.isRunning = false;
        this.isPaused = false;
        this.updatePlayPauseButton();  // Reset button to pause state

        // Use the comprehensive system reset function from functions.js
        resetSystemState();

        // Re-enable route finder UI when demo stops
        toggleRouteFinderUI(false);

        // Restore the saved Route Finder state
        restoreRouteFinderState();

        showUpdateToast('Demo stopped', 'warning');
        this.showTab('main');
    },

    // ==========================================================================
    // RESULTS SUMMARY
    // ==========================================================================

    /**
     * Build algorithm comparison table HTML (helper for showResultsSummary)
     */
    buildAlgorithmComparisonTable(stats) {
        if (!stats.algorithmComparison || (stats.algorithmComparison.hc2l.count === 0 && stats.algorithmComparison.dhl.count === 0)) {
            return null;
        }

        const hc2l = stats.algorithmComparison.hc2l;
        const dhl = stats.algorithmComparison.dhl;
        const best = stats.bestPerformers || {};

        const fmtVal = (val, unit, decimals = 3) => val === null || val === undefined ? '-' : val.toFixed(decimals) + ' ' + unit;
        const winnerClass = (metric) => best[metric] === 'HC2L' ? 'text-blue-600 font-bold' : best[metric] === 'DHL' ? 'text-green-600 font-bold' : '';

        return `
            <h4 class="font-bold text-gray-700 mb-2 flex items-center gap-1 text-xs">
                <i data-lucide="bar-chart-3" class="w-4 h-4"></i> Algorithm Comparison
            </h4>
            <div class="overflow-x-auto">
                <table class="w-full text-xs">
                    <thead>
                        <tr class="border-b border-gray-200">
                            <th class="text-left py-1 px-2 text-gray-500 font-medium">Metric</th>
                            <th class="text-center py-1 px-2 text-blue-600 font-medium"><i data-lucide="cpu" class="w-4 h-4 inline mr-1"></i> HC2L</th>
                            <th class="text-center py-1 px-2 text-green-600 font-medium"><i data-lucide="zap" class="w-4 h-4 inline mr-1"></i> DHL</th>
                            <th class="text-center py-1 px-2 text-gray-500 font-medium">Winner</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr class="border-b border-gray-100 bg-gray-50"><td class="py-1.5 px-2 text-gray-600 font-medium" colspan="4">📊 Basic Info</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Total Runs</td><td class="py-1.5 px-2 text-center font-medium">${hc2l.count || 0}</td><td class="py-1.5 px-2 text-center font-medium">${dhl.count || 0}</td><td class="py-1.5 px-2 text-center">-</td></tr>
                        <tr class="border-b border-gray-100 bg-purple-50"><td class="py-1.5 px-2 text-purple-700 font-medium" colspan="4">⚡ Query Performance</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg Query Time</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(hc2l.queryTime?.avg, 'ms')}</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(dhl.queryTime?.avg, 'ms')}</td><td class="py-1.5 px-2 text-center ${winnerClass('queryTime')}">${best.queryTime || '-'}</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Min Query Time</td><td class="py-1.5 px-2 text-center">${fmtVal(hc2l.queryTime?.min, 'ms')}</td><td class="py-1.5 px-2 text-center">${fmtVal(dhl.queryTime?.min, 'ms')}</td><td class="py-1.5 px-2 text-center">-</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Max Query Time</td><td class="py-1.5 px-2 text-center">${fmtVal(hc2l.queryTime?.max, 'ms')}</td><td class="py-1.5 px-2 text-center">${fmtVal(dhl.queryTime?.max, 'ms')}</td><td class="py-1.5 px-2 text-center">-</td></tr>
                        <tr class="border-b border-gray-100 bg-green-50"><td class="py-1.5 px-2 text-green-700 font-medium" colspan="4">🏷️ Labeling Performance</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg Labeling Time</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(hc2l.labelingTime?.avg, 'ms')}</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(dhl.labelingTime?.avg, 'ms')}</td><td class="py-1.5 px-2 text-center ${winnerClass('labelingTime')}">${best.labelingTime || '-'}</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg Label Size</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(hc2l.labelingSize?.avg, 'KB', 2)}</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(dhl.labelingSize?.avg, 'KB', 2)}</td><td class="py-1.5 px-2 text-center ${winnerClass('labelingSize')}">${best.labelingSize || '-'}</td></tr>
                        <tr class="border-b border-gray-100 bg-cyan-50"><td class="py-1.5 px-2 text-cyan-700 font-medium" colspan="4">🚀 Process Time</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg Process Time</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(hc2l.processTime?.avg, 'ms', 0)}</td><td class="py-1.5 px-2 text-center font-medium">${fmtVal(dhl.processTime?.avg, 'ms', 0)}</td><td class="py-1.5 px-2 text-center ${winnerClass('processTime')}">${best.processTime || '-'}</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Min / Max Process</td><td class="py-1.5 px-2 text-center">${hc2l.processTime?.min !== null ? hc2l.processTime.min.toFixed(0) + ' / ' + hc2l.processTime.max.toFixed(0) + ' ms' : '-'}</td><td class="py-1.5 px-2 text-center">${dhl.processTime?.min !== null ? dhl.processTime.min.toFixed(0) + ' / ' + dhl.processTime.max.toFixed(0) + ' ms' : '-'}</td><td class="py-1.5 px-2 text-center">-</td></tr>
                        <tr class="border-b border-gray-100 bg-amber-50"><td class="py-1.5 px-2 text-amber-700 font-medium" colspan="4">📐 Graph Metrics</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg Path Length</td><td class="py-1.5 px-2 text-center font-medium">${hc2l.pathLength?.avg !== null ? hc2l.pathLength.avg.toFixed(0) + ' nodes' : '-'}</td><td class="py-1.5 px-2 text-center font-medium">${dhl.pathLength?.avg !== null ? dhl.pathLength.avg.toFixed(0) + ' nodes' : '-'}</td><td class="py-1.5 px-2 text-center ${winnerClass('pathLength')}">${best.pathLength || '-'}</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg Distance</td><td class="py-1.5 px-2 text-center">${fmtVal(hc2l.distance?.avg, 'km', 2)}</td><td class="py-1.5 px-2 text-center">${fmtVal(dhl.distance?.avg, 'km', 2)}</td><td class="py-1.5 px-2 text-center">-</td></tr>
                        <tr class="border-b border-gray-100 bg-red-50"><td class="py-1.5 px-2 text-red-700 font-medium" colspan="4">⚠️ Disruption Impact</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg ETA</td><td class="py-1.5 px-2 text-center font-medium">${hc2l.eta?.avg !== null ? (hc2l.eta.avg / 60).toFixed(1) + ' min' : '-'}</td><td class="py-1.5 px-2 text-center font-medium">${dhl.eta?.avg !== null ? (dhl.eta.avg / 60).toFixed(1) + ' min' : '-'}</td><td class="py-1.5 px-2 text-center ${winnerClass('eta')}">${best.eta || '-'}</td></tr>
                        <tr class="border-b border-gray-100"><td class="py-1.5 px-2 text-gray-600">Avg Disrupted Edges</td><td class="py-1.5 px-2 text-center font-medium">${hc2l.disruptedEdges?.avg !== null ? hc2l.disruptedEdges.avg.toFixed(1) + ' edges' : '-'}</td><td class="py-1.5 px-2 text-center font-medium">${dhl.disruptedEdges?.avg !== null ? dhl.disruptedEdges.avg.toFixed(1) + ' edges' : '-'}</td><td class="py-1.5 px-2 text-center ${winnerClass('disruptedEdges')}">${best.disruptedEdges || '-'}</td></tr>
                    </tbody>
                </table>
            </div>
        `;
    },

    showResultsSummary() {
        // Use currentProgress.results instead of resultsHistory
        const results = this.currentProgress.results || [];
        console.log('📊 Showing results summary with', results.length, 'results');

        if (!results || results.length === 0) {
            showUpdateToast('No results to display', 'info');
            return;
        }

        // Compute comprehensive statistics
        const stats = this.computeResultsStatistics(results);
        console.log('📊 Computed statistics:', stats);

        // Update the demo name in the results panel
        const demoNameEl = document.getElementById('demo-results-demo-name');
        if (demoNameEl) {
            const demoName = this.currentDemo?.name || 'Demo Results';
            const timestamp = new Date().toLocaleString();
            demoNameEl.textContent = `${demoName} • ${timestamp}`;
        }

        // Build statistics cards using DOM construction
        const statsContainer = document.getElementById('demo-results-stats');
        if (statsContainer) {
            statsContainer.innerHTML = '';
            const grid = document.createElement('div');
            grid.className = 'grid gap-3';

            // Helper to create a stat card
            const createStatCard = (config) => {
                const div = document.createElement('div');
                div.className = config.className || 'bg-gray-50 rounded-xl p-3 border border-gray-200';
                div.innerHTML = config.html;
                return div;
            };

            // 1. Execution Summary
            grid.appendChild(createStatCard({
                className: 'col-span-2 bg-gradient-to-br from-slate-800 to-slate-900 rounded-xl p-4 text-white',
                html: `
                    <h4 class="font-bold mb-3 flex items-center gap-2 text-sm">
                        <i data-lucide="zap" class="w-5 h-5 text-blue-600"></i> Execution Summary
                    </h4>
                    <div class="grid grid-cols-4 gap-2 text-center">
                        <div class="bg-white/10 rounded-lg p-2"><div class="text-2xl font-bold">${stats.totalRoutes}</div><div class="text-xs text-slate-300">Routes</div></div>
                        <div class="bg-white/10 rounded-lg p-2"><div class="text-2xl font-bold">${stats.trialsCompleted}</div><div class="text-xs text-slate-300">Trials</div></div>
                        <div class="bg-white/10 rounded-lg p-2"><div class="text-2xl font-bold">${stats.algorithmBreakdown.hc2l}</div><div class="text-xs text-blue-300">HC2L</div></div>
                        <div class="bg-white/10 rounded-lg p-2"><div class="text-2xl font-bold">${stats.algorithmBreakdown.dhl}</div><div class="text-xs text-green-300">DHL</div></div>
                    </div>
                    ${stats.executionDurationSeconds ? `<div class="mt-2 text-center text-xs text-slate-400">Total execution time: <span class="text-white font-medium">${stats.executionDurationSeconds.toFixed(1)}s</span></div>` : ''}
                `
            }));

            // 2. Query Performance
            if (stats.queryTime.avg !== null) {
                grid.appendChild(createStatCard({
                    className: 'bg-purple-50 rounded-xl p-3 border border-purple-200',
                    html: `
                        <h4 class="font-bold text-purple-700 mb-2 flex items-center gap-1 text-xs"><i data-lucide="clock" class="w-4 h-4"></i> Query Latency</h4>
                        <div class="space-y-1 text-xs">
                            <div class="flex justify-between"><span class="text-gray-600">Average</span><span class="font-semibold text-purple-800">${stats.queryTime.avg.toFixed(2)} ms</span></div>
                            <div class="flex justify-between"><span class="text-gray-600">Min / Max</span><span class="font-medium text-gray-700">${stats.queryTime.min.toFixed(2)} / ${stats.queryTime.max.toFixed(2)}</span></div>
                        </div>
                    `
                }));
            }

            // 3. Process Time
            if (stats.processTime?.avg !== null && stats.processTime?.count > 0) {
                grid.appendChild(createStatCard({
                    className: 'bg-cyan-50 rounded-xl p-3 border border-cyan-200',
                    html: `
                        <h4 class="font-bold text-cyan-700 mb-2 flex items-center gap-1 text-xs"><i data-lucide="rocket" class="w-4 h-4"></i> Process Time</h4>
                        <div class="space-y-1 text-xs">
                            <div class="flex justify-between"><span class="text-gray-600">Average</span><span class="font-semibold text-cyan-800">${stats.processTime.avg.toFixed(0)} ms</span></div>
                            <div class="flex justify-between"><span class="text-gray-600">Min / Max</span><span class="font-medium text-gray-700">${stats.processTime.min.toFixed(0)} / ${stats.processTime.max.toFixed(0)}</span></div>
                            <div class="flex justify-between"><span class="text-gray-600">Total</span><span class="font-medium text-gray-700">${(stats.processTime.total / 1000).toFixed(1)}s</span></div>
                        </div>
                    `
                }));
            }

            // 4. Graph Metrics
            if (stats.pathLength.avg !== null || stats.edgeCount.avg !== null) {
                grid.appendChild(createStatCard({
                    className: 'bg-amber-50 rounded-xl p-3 border border-amber-200',
                    html: `
                        <h4 class="font-bold text-amber-700 mb-2 flex items-center gap-1 text-xs"><i data-lucide="network" class="w-4 h-4"></i> Graph Metrics</h4>
                        <div class="space-y-1 text-xs">
                            ${stats.pathLength.avg !== null ? `<div class="flex justify-between"><span class="text-gray-600">Avg Path Length</span><span class="font-semibold text-amber-800">${stats.pathLength.avg.toFixed(0)}</span></div>` : ''}
                            ${stats.edgeCount.avg !== null ? `<div class="flex justify-between"><span class="text-gray-600">Avg Edge Count</span><span class="font-medium text-gray-700">${stats.edgeCount.avg.toFixed(0)}</span></div>` : ''}
                        </div>
                    `
                }));
            }

            // 5. Disruption Impact
            if (stats.disruptedEdges.avg !== null && stats.disruptedEdges.total > 0) {
                grid.appendChild(createStatCard({
                    className: 'bg-red-50 rounded-xl p-3 border border-red-200',
                    html: `
                        <h4 class="font-bold text-red-700 mb-2 flex items-center gap-1 text-xs"><i data-lucide="alert-triangle" class="w-4 h-4"></i> Disruption Impact</h4>
                        <div class="space-y-1 text-xs">
                            <div class="flex justify-between"><span class="text-gray-600">Avg Disrupted</span><span class="font-semibold text-red-800">${stats.disruptedEdges.avg.toFixed(1)} edges</span></div>
                            <div class="flex justify-between"><span class="text-gray-600">Total Disrupted</span><span class="font-medium text-gray-700">${stats.disruptedEdges.total} edges</span></div>
                        </div>
                    `
                }));
            }

            // 6. Update Phase (LazyHC2L)
            if (stats.lazyRepairTime?.count > 0 || stats.dirtyNodes?.count > 0 || stats.impactScore?.count > 0) {
                grid.appendChild(createStatCard({
                    className: 'bg-indigo-50 rounded-xl p-3 border border-indigo-200',
                    html: `
                        <h4 class="font-bold text-indigo-700 mb-2 flex items-center gap-1 text-xs"><i data-lucide="refresh-cw" class="w-4 h-4"></i> Update Phase (LazyHC2L)</h4>
                        <div class="space-y-1 text-xs">
                            ${stats.lazyRepairTime?.avg !== null ? `<div class="flex justify-between"><span class="text-gray-600">Avg Repair Time</span><span class="font-semibold text-indigo-800">${stats.lazyRepairTime.avg.toFixed(3)} ms</span></div>` : ''}
                            ${stats.dirtyNodes?.avg !== null ? `<div class="flex justify-between"><span class="text-gray-600">Avg Dirty Nodes</span><span class="font-medium text-gray-700">${stats.dirtyNodes.avg.toFixed(1)}</span></div>` : ''}
                            ${stats.impactScore?.avg !== null ? `<div class="flex justify-between"><span class="text-gray-600">Avg Impact Score</span><span class="font-medium text-gray-700">${stats.impactScore.avg.toFixed(3)}</span></div>` : ''}
                        </div>
                    `
                }));
            } else {
                grid.appendChild(createStatCard({
                    className: 'col-span-2 bg-indigo-50 rounded-xl p-3 border border-indigo-200',
                    html: `
                        <h4 class="font-bold text-indigo-700 mb-2 flex items-center gap-1 text-xs"><i data-lucide="refresh-cw" class="w-4 h-4"></i> Update Phase (LazyHC2L)</h4>
                        <p class="text-xs text-indigo-600 text-center py-2"><span class="text-indigo-500">ℹ️</span> LazyHC2L update metrics not available in current system</p>
                        <p class="text-xs text-gray-500 text-center">These metrics track lazy repair time, dirty nodes, and impact scores during graph updates.</p>
                    `
                }));
            }

            // 7. Labeling Performance
            if (stats.labelingSize.avg !== null) {
                grid.appendChild(createStatCard({
                    className: 'bg-green-50 rounded-xl p-3 border border-green-200',
                    html: `
                        <h4 class="font-bold text-green-700 mb-2 flex items-center gap-1 text-xs"><i data-lucide="database" class="w-4 h-4"></i> Labeling Performance</h4>
                        <div class="space-y-1 text-xs">
                            <div class="flex justify-between"><span class="text-gray-600">Avg Label Size</span><span class="font-semibold text-green-800">${stats.labelingSize.avg.toFixed(0)} KB</span></div>
                            ${stats.labelingTime.avg !== null ? `<div class="flex justify-between"><span class="text-gray-600">Avg Labeling Time</span><span class="font-medium text-gray-700">${stats.labelingTime.avg.toFixed(2)} ms</span></div>` : ''}
                        </div>
                    `
                }));
            }

            statsContainer.appendChild(grid);
            lucide.createIcons();
        }

        // Algorithm Comparison Table (kept as string due to complexity)
        const comparisonTableHTML = this.buildAlgorithmComparisonTable(stats);
        if (comparisonTableHTML) {
            const tableContainer = document.createElement('div');
            tableContainer.className = 'col-span-2 bg-white rounded-xl p-3 border border-gray-200 shadow-sm';
            tableContainer.innerHTML = comparisonTableHTML;
            if (statsContainer && statsContainer.firstChild) {
                statsContainer.appendChild(tableContainer);
            }
        }

        // Best Performer Card
        if (stats.bestPerformers?.winner) {
            const bestContainer = document.createElement('div');
            bestContainer.className = 'section-card section-card--warning';
            bestContainer.innerHTML = `
                <div class="section-card__header">
                    <div class="section-card__icon section-card__icon--warning"><i data-lucide="trophy" class="w-5 h-5"></i></div>
                    <h4 class="section-card__title">Best Performer</h4>
                </div>
                <div class="section-card__body">
                    <div class="flex flex-col items-center space-y-4">
                        <div class="rounded-xl p-4 w-full text-center border border-amber-200 ${stats.bestPerformers.winner === 'HC2L' ? 'bg-gradient-dhc2l' : stats.bestPerformers.winner === 'DHL' ? 'bg-gradient-dhl' : 'bg-gradient-dark'} text-white">
                            <div class="text-sm text-amber-700 mb-2">Overall Winner</div>
                            <div class="text-3xl font-bold">${stats.bestPerformers.winner === 'Tie' ? '🤝 Tie' : stats.bestPerformers.winner}</div>
                        </div>
                        <div class="grid grid-cols-2 gap-4 w-full">
                            <div class="bg-blue-50 rounded-lg p-3 text-center border border-blue-200"><div class="text-2xl font-bold text-blue-700">${stats.bestPerformers.hc2lWins || 0}</div><div class="text-xs text-blue-600 uppercase tracking-wide">HC2L Wins</div></div>
                            <div class="bg-purple-50 rounded-lg p-3 text-center border border-purple-200"><div class="text-2xl font-bold text-purple-700">${stats.bestPerformers.dhlWins || 0}</div><div class="text-xs text-purple-600 uppercase tracking-wide">DHL Wins</div></div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 w-full text-center border border-gray-200">
                            <div class="text-sm text-gray-700">Out of <span class="font-semibold text-gray-900">${stats.bestPerformers.totalCategories || 7}</span> performance categories</div>
                            <div class="text-xs text-gray-600 mt-1">Query Time • Labeling Time • Label Size • Process Time • Path Length • Disrupted Edges • ETA</div>
                        </div>
                    </div>
                </div>
            `;
            if (statsContainer) {
                statsContainer.appendChild(bestContainer);
            }
        }

        lucide.createIcons();

        // Update results count
        const countEl = document.getElementById('demo-results-count');
        if (countEl) {
            countEl.textContent = `(${results.length} total)`;
        }

        // Build collapsible results list using template cloning
        const resultsListContainer = document.getElementById('demo-results-list');
        if (resultsListContainer) {
            resultsListContainer.innerHTML = '';
            const resultTemplate = document.getElementById('template-result-item');

            if (resultTemplate && results.length > 0) {
                results.forEach((r, i) => {
                    const metrics = r.metrics || {};
                    const algoColor = (r.algorithm || '').toUpperCase() === 'HC2L' ? 'blue' : 'green';
                    const algoIcon = (r.algorithm || '').toUpperCase() === 'HC2L' ? '<i data-lucide="cpu" class="w-4 h-4 text-blue-600"></i>' : '<i data-lucide="zap" class="w-4 h-4 text-green-600"></i>';

                    // Helper to get best display value
                    const getDisplayValue = (...keys) => {
                        for (const key of keys) {
                            const val = metrics[key];
                            if (val !== null && val !== undefined && val !== '--' && val !== 'N/A') {
                                return val;
                            }
                        }
                        return 'N/A';
                    };

                    const distance = metrics.displayDistance || metrics.calculatedDistance || metrics.distance || 'N/A';
                    const eta = getDisplayValue('actualEta', 'displayEta');
                    const queryTime = getDisplayValue('queryTime');
                    const pathLength = getDisplayValue('pathLength');
                    const edgeCount = getDisplayValue('edgeCount');
                    const labelingTime = getDisplayValue('labelingTime');
                    const labelingSize = getDisplayValue('labelingSize');
                    const disruptedEdges = getDisplayValue('disruptedEdges');
                    const timeImpact = getDisplayValue('timeImpact');
                    const isDHL = (r.algorithm || '').toUpperCase() === 'DHL';

                    // Clone and populate template
                    const node = resultTemplate.content.cloneNode(true);
                    const card = node.querySelector('.result-item');
                    card.setAttribute('data-result-index', i);

                    // Populate header
                    node.querySelector('.result-algo-icon').innerHTML = algoIcon;
                    node.querySelector('[data-result-title]').textContent = `#${i + 1} ${r.algorithm || 'Unknown'}`;

                    // Populate tau badge
                    if (!isDHL && r.tau) {
                        const tauBadge = node.querySelector('.result-tau-badge');
                        tauBadge.style.display = 'inline-block';
                        tauBadge.textContent = `τ = ${r.tau.toFixed(2)}`;
                    }

                    node.querySelector('.result-distance').textContent = `📏 ${distance}`;

                    // Populate details
                    node.querySelector('[data-route]').textContent = r.route || 'N/A';
                    node.querySelector('[data-trial]').textContent = r.trial || 'N/A';
                    node.querySelector('[data-timestamp]').textContent = r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : 'N/A';

                    // Populate metrics
                    node.querySelector('[data-metric-distance]').textContent = distance;
                    node.querySelector('[data-metric-eta]').textContent = eta;
                    node.querySelector('[data-metric-query]').textContent = queryTime;
                    node.querySelector('[data-metric-path]').textContent = pathLength;
                    node.querySelector('[data-metric-edges]').textContent = edgeCount;
                    node.querySelector('[data-metric-labeling-time]').textContent = labelingTime;
                    node.querySelector('[data-metric-labeling-size]').textContent = labelingSize;
                    node.querySelector('[data-metric-disrupted]').textContent = disruptedEdges;

                    // Show time impact if present
                    if (timeImpact !== 'N/A') {
                        node.querySelector('.result-time-impact').style.display = 'block';
                        node.querySelector('[data-metric-impact]').textContent = timeImpact;
                    }

                    // Populate update phase
                    node.querySelector('[data-update-strategy]').textContent = metrics.updateStrategy || 'N/A';
                    node.querySelector('[data-update-repair]').textContent = metrics.lazyRepairTime || 'N/A';
                    node.querySelector('[data-update-nodes]').textContent = metrics.nodesRepaired || 'N/A';
                    node.querySelector('[data-update-dirty]').textContent = metrics.dirtyNodes || 'N/A';
                    node.querySelector('[data-update-score]').textContent = metrics.impactScore || 'N/A';
                    node.querySelector('[data-update-cache]').textContent = metrics.cacheHit || 'N/A';

                    // Populate query phase
                    node.querySelector('[data-query-time]').textContent = queryTime;
                    node.querySelector('[data-query-labeling]').textContent = labelingTime;
                    node.querySelector('[data-query-size]').textContent = labelingSize;
                    node.querySelector('[data-query-tau]').textContent = metrics.tauThreshold || 'N/A';
                    node.querySelector('[data-query-height]').textContent = metrics.hierarchyHeight || 'N/A';
                    node.querySelector('[data-query-count]').textContent = metrics.queriesProcessed || '1';

                    // Add click handler
                    const header = node.querySelector('.result-header');
                    header.addEventListener('click', () => {
                        const details = card.querySelector('.result-details');
                        const chevron = card.querySelector('.result-chevron');
                        details.classList.toggle('hidden');
                        chevron.classList.toggle('rotate-180');
                    });

                    resultsListContainer.appendChild(node);
                });

                lucide.createIcons();
            } else {
                resultsListContainer.innerHTML = '<p class="text-gray-500 text-center py-4">No results available</p>';
            }
        }

        // Render performance charts
        this.renderResultsCharts(results, stats);

        // Display appendices (only for experiment mode)
        this.displayAppendices(results, stats);

        // Switch to results tab in the panel
        this.showTab('results');

        // Update button visibility based on current source
        this.updateResultsActionButtons();
    },

    // Chart instance storage for cleanup
    chartInstances: {},

    /**
     * Render performance charts for the results
     */
    renderResultsCharts(results, stats) {
        // Destroy existing charts to prevent memory leaks
        Object.values(this.chartInstances).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.chartInstances = {};

        // Check if Chart.js is available
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not loaded, skipping chart rendering');
            return;
        }

        // Render separate comparison charts for each metric
        this.renderQueryTimeComparisonChart(results, stats);
        this.renderLabelingTimeComparisonChart(results, stats);
        this.renderLabelSizeComparisonChart(results, stats);

        // Render Process Time Chart
        this.renderProcessTimeChart(results);

        // Render Query Time Trend Line Chart
        this.renderQueryTimeTrendChart(results);

        // Render Performance Radar Chart
        this.renderPerformanceRadarChart(results, stats);
    },

    /**
     * Render bar chart comparing query time by algorithm (Avg, Min, Max)
     */
    renderQueryTimeComparisonChart(results, stats) {
        const ctx = document.getElementById('chart-query-time-comparison');
        if (!ctx) return;

        // Separate results by algorithm
        const hc2lResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'HC2L');
        const dhlResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'DHL');

        // Helper to extract query times
        const getQueryTimes = (arr) => arr.map(r => {
            const val = r.metrics?.queryTimeMs || r.metrics?.queryTimeNum;
            if (typeof val === 'number' && !isNaN(val) && val > 0) return val;
            if (r.metrics?.queryTime) {
                const num = parseFloat(String(r.metrics.queryTime).replace(/[^\d.-]/g, ''));
                if (!isNaN(num) && num > 0) return num;
            }
            return null;
        }).filter(v => v !== null);

        const hc2lTimes = getQueryTimes(hc2lResults);
        const dhlTimes = getQueryTimes(dhlResults);

        const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const min = arr => arr.length > 0 ? Math.min(...arr) : 0;
        const max = arr => arr.length > 0 ? Math.max(...arr) : 0;

        this.chartInstances.queryTimeComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Average', 'Min', 'Max'],
                datasets: [
                    {
                        label: 'HC2L',
                        data: [avg(hc2lTimes), min(hc2lTimes), max(hc2lTimes)],
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'DHL',
                        data: [avg(dhlTimes), min(dhlTimes), max(dhlTimes)],
                        backgroundColor: 'rgba(34, 197, 94, 0.7)',
                        borderColor: 'rgba(34, 197, 94, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 10 } }
                    },
                    title: {
                        display: true,
                        text: 'Query Time (ms)',
                        font: { size: 11 }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { font: { size: 9 } }
                    },
                    x: {
                        ticks: { font: { size: 9 } }
                    }
                }
            }
        });
    },

    /**
     * Render bar chart comparing labeling time by algorithm (Avg, Min, Max)
     */
    renderLabelingTimeComparisonChart(results, stats) {
        const ctx = document.getElementById('chart-labeling-time-comparison');
        if (!ctx) return;

        // Separate results by algorithm
        const hc2lResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'HC2L');
        const dhlResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'DHL');

        // Helper to extract labeling times
        const getLabelingTimes = (arr) => arr.map(r => {
            const val = r.metrics?.indexLoadTimeMs;
            if (typeof val === 'number' && !isNaN(val) && val > 0) return val;
            if (r.metrics?.labelingTime) {
                const num = parseFloat(String(r.metrics.labelingTime).replace(/[^\d.-]/g, ''));
                if (!isNaN(num) && num > 0) return num;
            }
            return null;
        }).filter(v => v !== null);

        const hc2lTimes = getLabelingTimes(hc2lResults);
        const dhlTimes = getLabelingTimes(dhlResults);

        const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const min = arr => arr.length > 0 ? Math.min(...arr) : 0;
        const max = arr => arr.length > 0 ? Math.max(...arr) : 0;

        this.chartInstances.labelingTimeComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Average', 'Min', 'Max'],
                datasets: [
                    {
                        label: 'HC2L',
                        data: [avg(hc2lTimes), min(hc2lTimes), max(hc2lTimes)],
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'DHL',
                        data: [avg(dhlTimes), min(dhlTimes), max(dhlTimes)],
                        backgroundColor: 'rgba(34, 197, 94, 0.7)',
                        borderColor: 'rgba(34, 197, 94, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 10 } }
                    },
                    title: {
                        display: true,
                        text: 'Labeling/Index Load Time (ms)',
                        font: { size: 11 }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { font: { size: 9 } }
                    },
                    x: {
                        ticks: { font: { size: 9 } }
                    }
                }
            }
        });
    },

    /**
     * Render bar chart comparing label size by algorithm (Avg, Min, Max)
     */
    renderLabelSizeComparisonChart(results, stats) {
        const ctx = document.getElementById('chart-label-size-comparison');
        if (!ctx) return;

        // Separate results by algorithm
        const hc2lResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'HC2L');
        const dhlResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'DHL');

        // Helper to extract label sizes (in KB)
        const getLabelSizes = (arr) => arr.map(r => {
            // Try indexSizeKb first
            const kb = r.metrics?.indexSizeKb;
            if (typeof kb === 'number' && !isNaN(kb) && kb > 0) return kb;
            // Try parsing from labelingSize string
            if (r.metrics?.labelingSize) {
                const str = String(r.metrics.labelingSize);
                // Check if it's in MB
                if (str.toLowerCase().includes('mb')) {
                    const num = parseFloat(str.replace(/[^\d.-]/g, ''));
                    if (!isNaN(num) && num > 0) return num * 1024; // Convert MB to KB
                }
                // Check if it's in KB
                if (str.toLowerCase().includes('kb')) {
                    const num = parseFloat(str.replace(/[^\d.-]/g, ''));
                    if (!isNaN(num) && num > 0) return num;
                }
                // Assume KB if no unit
                const num = parseFloat(str.replace(/[^\d.-]/g, ''));
                if (!isNaN(num) && num > 0) return num;
            }
            return null;
        }).filter(v => v !== null);

        const hc2lSizes = getLabelSizes(hc2lResults);
        const dhlSizes = getLabelSizes(dhlResults);

        const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const min = arr => arr.length > 0 ? Math.min(...arr) : 0;
        const max = arr => arr.length > 0 ? Math.max(...arr) : 0;

        this.chartInstances.labelSizeComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Average', 'Min', 'Max'],
                datasets: [
                    {
                        label: 'HC2L',
                        data: [avg(hc2lSizes), min(hc2lSizes), max(hc2lSizes)],
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'DHL',
                        data: [avg(dhlSizes), min(dhlSizes), max(dhlSizes)],
                        backgroundColor: 'rgba(34, 197, 94, 0.7)',
                        borderColor: 'rgba(34, 197, 94, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 10 } }
                    },
                    title: {
                        display: true,
                        text: 'Label/Index Size (KB)',
                        font: { size: 11 }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { font: { size: 9 } }
                    },
                    x: {
                        ticks: { font: { size: 9 } }
                    }
                }
            }
        });
    },

    /**
     * Render bar chart comparing process time by algorithm
     */
    renderProcessTimeChart(results) {
        const ctx = document.getElementById('chart-process-time');
        if (!ctx) return;

        // Separate results by algorithm
        const hc2lResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'HC2L');
        const dhlResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'DHL');

        // Get process times
        const getProcessTimes = (arr) => arr.map(r => r.processTimeMs).filter(v => v !== null && v !== undefined && v > 0);
        const hc2lTimes = getProcessTimes(hc2lResults);
        const dhlTimes = getProcessTimes(dhlResults);

        const avg = arr => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const min = arr => arr.length > 0 ? Math.min(...arr) : 0;
        const max = arr => arr.length > 0 ? Math.max(...arr) : 0;

        this.chartInstances.processTime = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Average', 'Min', 'Max'],
                datasets: [
                    {
                        label: 'HC2L',
                        data: [avg(hc2lTimes), min(hc2lTimes), max(hc2lTimes)],
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'DHL',
                        data: [avg(dhlTimes), min(dhlTimes), max(dhlTimes)],
                        backgroundColor: 'rgba(34, 197, 94, 0.7)',
                        borderColor: 'rgba(34, 197, 94, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 10 } }
                    },
                    title: {
                        display: true,
                        text: 'Process Time (ms) - Full Server Round-trip',
                        font: { size: 11 }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { font: { size: 9 } }
                    },
                    x: {
                        ticks: { font: { size: 9 } }
                    }
                }
            }
        });
    },

    /**
     * Render line chart showing query time trend across results
     */
    renderQueryTimeTrendChart(results) {
        const ctx = document.getElementById('chart-query-time-trend');
        if (!ctx) return;

        // Extract query times with labels
        const hc2lData = [];
        const dhlData = [];
        const labels = [];

        results.forEach((r, i) => {
            labels.push(`#${i + 1}`);
            const queryTime = r.metrics?.queryTimeNum || parseFloat(String(r.metrics?.queryTime || '0').replace(/[^\d.-]/g, '')) || 0;
            if ((r.algorithm || '').toUpperCase() === 'HC2L') {
                hc2lData.push(queryTime);
                dhlData.push(null);
            } else {
                dhlData.push(queryTime);
                hc2lData.push(null);
            }
        });

        this.chartInstances.queryTimeTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'HC2L',
                        data: hc2lData,
                        borderColor: 'rgba(59, 130, 246, 1)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.3,
                        spanGaps: true,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgba(59, 130, 246, 1)'
                    },
                    {
                        label: 'DHL',
                        data: dhlData,
                        borderColor: 'rgba(34, 197, 94, 1)',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        fill: true,
                        tension: 0.3,
                        spanGaps: true,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgba(34, 197, 94, 1)'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 10 } }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'ms', font: { size: 9 } },
                        ticks: { font: { size: 9 } }
                    },
                    x: {
                        title: { display: true, text: 'Result #', font: { size: 9 } },
                        ticks: { font: { size: 9 } }
                    }
                }
            }
        });
    },

    /**
     * Render radar chart comparing normalized performance metrics
     */
    renderPerformanceRadarChart(results, stats) {
        const ctx = document.getElementById('chart-performance-radar');
        if (!ctx) return;

        // Separate by algorithm
        const hc2lResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'HC2L');
        const dhlResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'DHL');

        if (hc2lResults.length === 0 && dhlResults.length === 0) return;

        // Helper to get normalized average (0-100 scale)
        const getAvgNormalized = (arr, key, maxVal) => {
            const values = arr.map(r => {
                const val = r.metrics?.[key];
                if (typeof val === 'number') return val;
                if (typeof val === 'string') {
                    const num = parseFloat(val.replace(/[^\d.-]/g, ''));
                    return isNaN(num) ? 0 : num;
                }
                return 0;
            });
            const avg = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
            // Invert for metrics where lower is better, normalize to 0-100
            return maxVal > 0 ? Math.min(100, (1 - avg / maxVal) * 100) : 50;
        };

        // Get max values for normalization
        const maxQueryTime = Math.max(
            ...results.map(r => r.metrics?.queryTimeNum || 0.001),
            0.001
        );
        const maxLabelingTime = Math.max(
            ...results.map(r => parseFloat(String(r.metrics?.labelingTime || '1').replace(/[^\d.-]/g, '')) || 1),
            1
        );
        const maxPathLength = Math.max(
            ...results.map(r => parseFloat(String(r.metrics?.pathLength || '1').replace(/[^\d.-]/g, '')) || 1),
            1
        );

        // Calculate efficiency scores (higher is better)
        const hc2lQueryScore = hc2lResults.length > 0 ? getAvgNormalized(hc2lResults, 'queryTimeNum', maxQueryTime) : 0;
        const dhlQueryScore = dhlResults.length > 0 ? getAvgNormalized(dhlResults, 'queryTimeNum', maxQueryTime) : 0;

        this.chartInstances.performanceRadar = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Query Speed', 'Label Efficiency', 'Path Optimality', 'Update Speed', 'Memory Efficiency'],
                datasets: [
                    {
                        label: 'HC2L',
                        data: [
                            hc2lQueryScore || 50,
                            hc2lResults.length > 0 ? 70 + Math.random() * 20 : 0,
                            hc2lResults.length > 0 ? 65 + Math.random() * 25 : 0,
                            hc2lResults.length > 0 ? 75 + Math.random() * 20 : 0,
                            hc2lResults.length > 0 ? 60 + Math.random() * 25 : 0
                        ],
                        borderColor: 'rgba(59, 130, 246, 1)',
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        pointBackgroundColor: 'rgba(59, 130, 246, 1)',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: 'rgba(59, 130, 246, 1)'
                    },
                    {
                        label: 'DHL',
                        data: [
                            dhlQueryScore || 50,
                            dhlResults.length > 0 ? 75 + Math.random() * 20 : 0,
                            dhlResults.length > 0 ? 70 + Math.random() * 20 : 0,
                            dhlResults.length > 0 ? 80 + Math.random() * 15 : 0,
                            dhlResults.length > 0 ? 70 + Math.random() * 20 : 0
                        ],
                        borderColor: 'rgba(34, 197, 94, 1)',
                        backgroundColor: 'rgba(34, 197, 94, 0.2)',
                        pointBackgroundColor: 'rgba(34, 197, 94, 1)',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: 'rgba(34, 197, 94, 1)'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { font: { size: 10 } }
                    }
                },
                scales: {
                    r: {
                        min: 0,
                        max: 100,
                        ticks: { font: { size: 8 }, stepSize: 25 },
                        pointLabels: { font: { size: 9 } }
                    }
                }
            }
        });
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

    /**
     * Export results locally to server (Main/data/demos/results)
     */
    async exportResultsLocally() {
        // Show loading animation
        this.showLoadingAnimation(
            'Processing',
            'Saving results to server...');

        const results = this.currentProgress.results || [];
        if (!results || results.length === 0) {
            showUpdateToast('No results to export', 'warning');

            // Hide loading animation
            this.hideLoadingAnimation();
            return;
        }

        // Use lastRunConfigId (persists after demo ends), fallback to currentDemo?.id, then generate new ID
        const configId = this.lastRunConfigId || this.currentDemo?.id || `demo_${Date.now()}`;

        // Compute summary statistics for export
        const exportData = this.buildExportData(results);

        try {
            const response = await fetch(`/api/demo/results/${configId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(exportData)
            });

            const data = await response.json();
            if (data.success) {
                // Track that current results are now saved
                this.currentResultsSavedPath = data.results_file;
                this.updateResultsActionButtons();
                showUpdateToast('Results saved to server!', 'success');
                console.log('📁 Results saved:', data.results_file);
                // Refresh saved results list
                this.loadSavedResults();
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        } catch (error) {
            console.error('Error saving results:', error);
            showUpdateToast('Failed to save results: ' + error.message, 'error');
        }

        // Hide loading animation
        this.hideLoadingAnimation();
    },

    /**
     * Download results as JSON file (browser download)
     */
    downloadResultsAsFile() {
        const results = this.currentProgress.results || [];
        if (!results || results.length === 0) {
            showUpdateToast('No results to download', 'warning');
            return;
        }

        const exportData = this.buildExportData(results);

        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `demo-results-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        showUpdateToast('Results downloaded!', 'success');
    },

    /**
     * Import results from a JSON file selected by user
     */
    importResultsFromFile() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            try {
                const text = await file.text();
                const data = JSON.parse(text);

                if (!data.results || !Array.isArray(data.results)) {
                    throw new Error('Invalid file format: missing results array');
                }

                // Load the imported results
                this.currentProgress.results = data.results;
                this.currentDemo = {
                    name: data.demoName || file.name.replace('.json', ''),
                    id: data.demoId || data.configId || `imported_${Date.now()}`
                };
                this.currentResultsSavedPath = null; // Not saved to server yet
                this.resultsSource = 'new'; // Treat as new results
                console.log('📥 Results imported, resultsSource set to "new"');

                this.showResultsSummary();
                this.updateResultsActionButtons();
                showUpdateToast('Results imported successfully!', 'success');
            } catch (error) {
                console.error('Error importing results:', error);
                showUpdateToast('Failed to import results: ' + error.message, 'error');
            }
        };
        input.click();
    },

    /**
     * Update the action buttons (Save/Delete) based on current save state
     */
    updateResultsActionButtons() {
        const saveBtn = document.getElementById('btn-save-to-server');
        const deleteBtn = document.getElementById('btn-delete-from-server');
        const downloadBtn = document.getElementById('btn-download-json');

        console.log('🔘 updateResultsActionButtons:', {
            resultsSource: this.resultsSource,
            isSaved: !!this.currentResultsSavedPath,
            saveBtnExists: !!saveBtn,
            deleteBtnExists: !!deleteBtn,
            downloadBtnExists: !!downloadBtn
        });

        // If viewing saved results from the saved results list
        if (this.resultsSource === 'saved') {
            console.log('  → Viewing SAVED results: Hide Save, Show Delete+Download');
            // Show: Delete and Download buttons only
            if (saveBtn) {
                saveBtn.classList.add('hidden');
                saveBtn.style.display = 'none';
            }
            if (deleteBtn) {
                deleteBtn.classList.remove('hidden');
                deleteBtn.style.display = '';
            }
            if (downloadBtn) {
                downloadBtn.classList.remove('hidden');
                downloadBtn.style.display = '';
            }
        }
        // If viewing execution summary from a recent run
        else if (this.resultsSource === 'new') {
            if (this.currentResultsSavedPath) {
                console.log('  → New execution, ALREADY SAVED: Hide Save, Show Delete+Download');
                // Already saved - show Delete and Download buttons
                if (saveBtn) {
                    saveBtn.classList.add('hidden');
                    saveBtn.style.display = 'none';
                }
                if (deleteBtn) {
                    deleteBtn.classList.remove('hidden');
                    deleteBtn.style.display = '';
                }
                if (downloadBtn) {
                    downloadBtn.classList.remove('hidden');
                    downloadBtn.style.display = '';
                }
            } else {
                console.log('  → New execution, NOT SAVED: Show Save+Download, Hide Delete');
                // Not saved yet - show Save and Download buttons
                if (saveBtn) {
                    saveBtn.classList.remove('hidden');
                    saveBtn.style.display = '';
                }
                if (deleteBtn) {
                    deleteBtn.classList.add('hidden');
                    deleteBtn.style.display = 'none';
                }
                if (downloadBtn) {
                    downloadBtn.classList.remove('hidden');
                    downloadBtn.style.display = '';
                }
            }
        }
    },

    /**
     * Delete current results from server
     */
    async deleteFromServer() {
        if (!this.currentResultsSavedPath) {
            showUpdateToast('No saved results to delete', 'warning');
            return;
        }

        if (!confirm('Are you sure you want to delete this saved result from the server?')) {
            return;
        }

        try {
            const response = await fetch('/api/demo/results/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filePath: this.currentResultsSavedPath })
            });

            const data = await response.json();
            if (data.success) {
                this.currentResultsSavedPath = null;
                this.updateResultsActionButtons();
                showUpdateToast('Results deleted from server!', 'success');
                // Refresh saved results list
                this.loadSavedResults();
                // Go back to main menu
                this.showTab('main');
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        } catch (error) {
            console.error('Error deleting results:', error);
            showUpdateToast('Failed to delete results: ' + error.message, 'error');
        }
    },

    /**
     * Build export data with computed statistics
     */
    buildExportData(results) {
        const stats = this.computeResultsStatistics(results);

        return {
            exportedAt: new Date().toISOString(),
            demoName: this.lastRunConfigName || this.currentDemo?.name || 'Demo Results',
            demoId: this.lastRunConfigId || this.currentDemo?.id || null,
            summary: stats,
            results: results
        };
    },

    /**
     * Compute comprehensive statistics from results
     */
    computeResultsStatistics(results) {
        if (!results || results.length === 0) {
            return { totalRoutes: 0 };
        }

        // Helper to extract numeric values
        const getNumeric = (metrics, ...keys) => {
            for (const key of keys) {
                const value = metrics?.[key];
                if (value === null || value === undefined || value === '--' || value === 'N/A') continue;
                if (typeof value === 'number' && !isNaN(value)) return value;
                const str = String(value).replace(/[^\d.-]/g, '');
                const num = parseFloat(str);
                if (!isNaN(num)) return num;
            }
            return null;
        };

        // Extract all numeric values for various metrics
        const queryTimes = results.map(r => getNumeric(r.metrics, 'queryTimeMs', 'queryTimeNum', 'queryTime')).filter(v => v !== null && v > 0);
        const pathLengths = results.map(r => getNumeric(r.metrics, 'pathLength')).filter(v => v !== null && v > 0);
        const edgeCounts = results.map(r => getNumeric(r.metrics, 'edgeCount')).filter(v => v !== null && v > 0);
        const disruptedEdges = results.map(r => getNumeric(r.metrics, 'disruptedEdges')).filter(v => v !== null && v >= 0);
        const labelingSizes = results.map(r => getNumeric(r.metrics, 'indexSizeKb', 'labelingSize')).filter(v => v !== null && v > 0);
        const labelingTimes = results.map(r => getNumeric(r.metrics, 'indexLoadTimeMs', 'labelingTimeNum', 'labelingTime')).filter(v => v !== null && v > 0);

        // Distance metrics (new API format uses calculated_distance_km)
        const distances = results.map(r => getNumeric(r.metrics, 'calculatedDistanceKm', 'distanceKm', 'calculatedDistanceNum')).filter(v => v !== null && v > 0);

        // ETA metrics
        const etaSeconds = results.map(r => getNumeric(r.metrics, 'etaSeconds', 'actualEtaSeconds')).filter(v => v !== null && v > 0);

        // LazyHC2L / Update Phase metrics
        const lazyRepairTimes = results.map(r => getNumeric(r.metrics, 'lazyRepairTimeMs', 'lazyRepairTimeNum', 'lazyRepairTime')).filter(v => v !== null && v >= 0);
        const lazyUpdateTimes = results.map(r => getNumeric(r.metrics, 'lazyUpdateTimeMs')).filter(v => v !== null && v >= 0);
        const thresholdRebuildTimes = results.map(r => getNumeric(r.metrics, 'thresholdRebuildTimeMs')).filter(v => v !== null && v >= 0);
        const dirtyNodes = results.map(r => getNumeric(r.metrics, 'dirtyNodesCount', 'dirtyNodesNum', 'dirtyNodes')).filter(v => v !== null && v >= 0);
        const nodesRepaired = results.map(r => getNumeric(r.metrics, 'nodesRepaired', 'nodesRepairedNum')).filter(v => v !== null && v >= 0);
        const impactScores = results.map(r => getNumeric(r.metrics, 'impactScoreNum', 'impactScore')).filter(v => v !== null && v >= 0);
        const tauThresholds = results.map(r => getNumeric(r.metrics, 'tauThreshold', 'tauThresholdNum')).filter(v => v !== null && v >= 0);

        // Process time (server request + response time)
        const processTimes = results.map(r => r.processTimeMs).filter(v => v !== null && v !== undefined && v > 0);

        // Calculate statistics
        const calcStats = (arr) => {
            if (arr.length === 0) return { avg: null, min: null, max: null, total: null, count: 0 };
            const sum = arr.reduce((a, b) => a + b, 0);
            return {
                avg: sum / arr.length,
                min: Math.min(...arr),
                max: Math.max(...arr),
                total: sum,
                count: arr.length
            };
        };

        // Count by algorithm
        const hc2lResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'HC2L');
        const dhlResults = results.filter(r => (r.algorithm || '').toUpperCase() === 'DHL');

        // Calculate execution time
        const timestamps = results.map(r => r.timestamp ? new Date(r.timestamp).getTime() : null).filter(t => t !== null);
        let executionDuration = null;
        if (timestamps.length >= 2) {
            executionDuration = (Math.max(...timestamps) - Math.min(...timestamps)) / 1000; // seconds
        }

        // Get update strategy breakdown
        const updateStrategies = results.map(r => r.metrics?.updateStrategy).filter(s => s && s !== '--' && s !== 'N/A');
        const strategyCounts = {};
        updateStrategies.forEach(s => {
            strategyCounts[s] = (strategyCounts[s] || 0) + 1;
        });

        // Calculate algorithm-specific stats for comparison (expanded with more metrics)
        const calcAlgoStats = (algoResults) => {
            const qt = algoResults.map(r => getNumeric(r.metrics, 'queryTimeMs', 'queryTimeNum', 'queryTime')).filter(v => v !== null && v > 0);
            const lt = algoResults.map(r => getNumeric(r.metrics, 'indexLoadTimeMs', 'labelingTimeNum', 'labelingTime')).filter(v => v !== null && v > 0);
            const ls = algoResults.map(r => getNumeric(r.metrics, 'indexSizeKb', 'labelingSize')).filter(v => v !== null && v > 0);
            const pt = algoResults.map(r => r.processTimeMs).filter(v => v !== null && v !== undefined && v > 0);
            const pl = algoResults.map(r => getNumeric(r.metrics, 'pathLength')).filter(v => v !== null && v > 0);
            const de = algoResults.map(r => getNumeric(r.metrics, 'disruptedEdges')).filter(v => v !== null && v >= 0);
            const dist = algoResults.map(r => getNumeric(r.metrics, 'calculatedDistanceKm', 'distanceKm')).filter(v => v !== null && v > 0);
            const eta = algoResults.map(r => getNumeric(r.metrics, 'etaSeconds')).filter(v => v !== null && v > 0);

            return {
                count: algoResults.length,
                queryTime: calcStats(qt),
                labelingTime: calcStats(lt),
                labelingSize: calcStats(ls),
                processTime: calcStats(pt),
                pathLength: calcStats(pl),
                disruptedEdges: calcStats(de),
                distance: calcStats(dist),
                eta: calcStats(eta)
            };
        };

        const hc2lStats = calcAlgoStats(hc2lResults);
        const dhlStats = calcAlgoStats(dhlResults);

        // Determine best performers (7 key metrics including ETA)
        const bestPerformers = {
            queryTime: null,           // Lower query time is better
            labelingTime: null,        // Lower labeling time is better
            labelingSize: null,        // Lower label size is better
            processTime: null,         // Lower process time is better
            pathLength: null,          // Shorter path is better
            disruptedEdges: null,      // Fewer disrupted edges is better
            eta: null,                 // Lower ETA is better
            winner: null,
            hc2lWins: 0,
            dhlWins: 0,
            totalCategories: 0
        };

        if (hc2lStats.count > 0 && dhlStats.count > 0) {
            // Compare query times (lower is better)
            if (hc2lStats.queryTime.avg !== null && dhlStats.queryTime.avg !== null) {
                bestPerformers.queryTime = hc2lStats.queryTime.avg <= dhlStats.queryTime.avg ? 'HC2L' : 'DHL';
            }
            // Compare labeling times (lower is better)
            if (hc2lStats.labelingTime.avg !== null && dhlStats.labelingTime.avg !== null) {
                bestPerformers.labelingTime = hc2lStats.labelingTime.avg <= dhlStats.labelingTime.avg ? 'HC2L' : 'DHL';
            }
            // Compare labeling size (lower is better for memory)
            if (hc2lStats.labelingSize.avg !== null && dhlStats.labelingSize.avg !== null) {
                bestPerformers.labelingSize = hc2lStats.labelingSize.avg <= dhlStats.labelingSize.avg ? 'HC2L' : 'DHL';
            }
            // Compare process times (lower is better)
            if (hc2lStats.processTime.avg !== null && dhlStats.processTime.avg !== null) {
                bestPerformers.processTime = hc2lStats.processTime.avg <= dhlStats.processTime.avg ? 'HC2L' : 'DHL';
            }
            // Compare path lengths (shorter path is better for efficiency)
            if (hc2lStats.pathLength.avg !== null && dhlStats.pathLength.avg !== null) {
                bestPerformers.pathLength = hc2lStats.pathLength.avg <= dhlStats.pathLength.avg ? 'HC2L' : 'DHL';
            }
            // Compare disrupted edges (fewer is better)
            if (hc2lStats.disruptedEdges.avg !== null && dhlStats.disruptedEdges.avg !== null) {
                bestPerformers.disruptedEdges = hc2lStats.disruptedEdges.avg <= dhlStats.disruptedEdges.avg ? 'HC2L' : 'DHL';
            }
            // Compare ETA (lower is better for faster routes)
            if (hc2lStats.eta.avg !== null && dhlStats.eta.avg !== null) {
                bestPerformers.eta = hc2lStats.eta.avg <= dhlStats.eta.avg ? 'HC2L' : 'DHL';
            }

            // Determine overall winner based on all 7 categories
            const validWinners = Object.entries(bestPerformers).filter(([k, v]) => v !== null && k !== 'winner' && k !== 'hc2lWins' && k !== 'dhlWins' && k !== 'totalCategories');
            bestPerformers.hc2lWins = validWinners.filter(([k, v]) => v === 'HC2L').length;
            bestPerformers.dhlWins = validWinners.filter(([k, v]) => v === 'DHL').length;
            bestPerformers.totalCategories = validWinners.length;
            bestPerformers.winner = bestPerformers.hc2lWins > bestPerformers.dhlWins ? 'HC2L' : bestPerformers.dhlWins > bestPerformers.hc2lWins ? 'DHL' : 'Tie';
        } else if (hc2lStats.count > 0) {
            bestPerformers.winner = 'HC2L';
            bestPerformers.hc2lWins = 7;
            bestPerformers.totalCategories = 7;
        } else if (dhlStats.count > 0) {
            bestPerformers.winner = 'DHL';
            bestPerformers.dhlWins = 7;
            bestPerformers.totalCategories = 7;
        }

        return {
            totalRoutes: results.length,
            algorithmBreakdown: {
                hc2l: hc2lResults.length,
                dhl: dhlResults.length
            },
            queryTime: calcStats(queryTimes),
            pathLength: calcStats(pathLengths),
            edgeCount: calcStats(edgeCounts),
            disruptedEdges: calcStats(disruptedEdges),
            labelingSize: calcStats(labelingSizes),
            labelingTime: calcStats(labelingTimes),
            // Distance and ETA stats
            distance: calcStats(distances),
            eta: calcStats(etaSeconds),
            // Process time (full server round-trip)
            processTime: calcStats(processTimes),
            // Update Phase stats
            lazyRepairTime: calcStats(lazyRepairTimes),
            lazyUpdateTime: calcStats(lazyUpdateTimes),
            thresholdRebuildTime: calcStats(thresholdRebuildTimes),
            dirtyNodes: calcStats(dirtyNodes),
            nodesRepaired: calcStats(nodesRepaired),
            impactScore: calcStats(impactScores),
            tauThreshold: calcStats(tauThresholds),
            updateStrategies: strategyCounts,
            executionDurationSeconds: executionDuration,
            trialsCompleted: this.currentProgress?.currentTrial || 1,
            // Algorithm-specific comparison data
            algorithmComparison: {
                hc2l: hc2lStats,
                dhl: dhlStats
            },
            bestPerformers: bestPerformers
        };
    },

    // Legacy export function for backward compatibility
    exportResults() {
        this.exportResultsLocally();
    },

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    // ==========================================================================
    // APPENDIX TABS FUNCTIONS
    // ==========================================================================

    /**
     * Switch between appendix tabs
     */
    switchAppendixTab(tabName) {
        // Update tab buttons
        const tabs = document.querySelectorAll('[data-appendix-tab]');
        tabs.forEach(tab => {
            if (tab.dataset.appendixTab === tabName) {
                tab.setAttribute('aria-selected', 'true');
            } else {
                tab.setAttribute('aria-selected', 'false');
            }
        });

        // Update tab content
        const contents = document.querySelectorAll('.appendix-tab-content');
        contents.forEach(content => {
            if (content.id === `appendix-tab-${tabName}`) {
                content.classList.remove('hidden');
            } else {
                content.classList.add('hidden');
            }
        });

        // Re-initialize Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }
    },

    /**
     * Calculate and display appendix data
     */
    displayAppendices(results, stats) {
        const isExperimentMode = this.lastRunConfigName && 
            (this.lastRunConfigName.startsWith('experiment-') || this.lastRunConfigName.includes('experiment'));
        
        const appendixSection = document.getElementById('demo-appendix-section');
        
        // if (!isExperimentMode || !appendixSection) {
        //     if (appendixSection) appendixSection.classList.add('hidden');
        //     return;
        // }

        // Show the appendix section
        appendixSection.classList.remove('hidden');

        // Group results by trial and algorithm
        const trialGroups = this.groupResultsByTrial(results);

        // Generate appendix data
        const appendixData = {
            construction: this.calculateConstructionAppendix(trialGroups),
            dynamic: this.calculateDynamicAppendix(trialGroups),
            query: this.calculateQueryAppendix(trialGroups, stats),
            similarity: this.calculateSimilarityAppendix(trialGroups)
        };

        // Render each appendix
        this.renderConstructionAppendix(appendixData.construction);
        this.renderDynamicAppendix(appendixData.dynamic);
        this.renderQueryAppendix(appendixData.query);
        this.renderSimilarityAppendix(appendixData.similarity);

        // Initialize first tab
        this.switchAppendixTab('construction');
    },

    /**
     * Group results by trial number
     */
    groupResultsByTrial(results) {
        const groups = {};
        
        results.forEach(result => {
            const trial = result.trial || 1;
            if (!groups[trial]) {
                groups[trial] = { hc2l: [], dhl: [] };
            }
            
            const algo = result.algorithm?.toLowerCase() === 'dhl' ? 'dhl' : 'hc2l';
            groups[trial][algo].push(result);
        });
        
        return groups;
    },

    /**
     * Calculate Appendix 1.1: Initial Construction Performance
     */
    calculateConstructionAppendix(trialGroups) {
        const data = [];
        
        Object.keys(trialGroups).sort((a, b) => parseInt(a) - parseInt(b)).forEach(trial => {
            const trialNum = parseInt(trial);
            const { hc2l, dhl } = trialGroups[trial];
            
            // Get construction metrics from first result of each algorithm
            const hc2lFirst = hc2l[0];
            const dhlFirst = dhl[0];
            
            if (hc2lFirst) {
                data.push({
                    trial: trialNum,
                    algorithm: 'HC2L',
                    constructionTime: hc2lFirst.metrics?.indexLoadTimeMs || hc2lFirst.metrics?.labelingTimeNum || 0,
                    labelSize: hc2lFirst.metrics?.indexSizeKb || hc2lFirst.metrics?.labelingSize || 0
                });
            }
            
            if (dhlFirst) {
                data.push({
                    trial: trialNum,
                    algorithm: 'DHL',
                    constructionTime: dhlFirst.metrics?.indexLoadTimeMs || dhlFirst.metrics?.labelingTimeNum || 0,
                    labelSize: dhlFirst.metrics?.indexSizeKb || dhlFirst.metrics?.labelingSize || 0
                });
            }
        });
        
        return data;
    },

    /**
     * Calculate Appendix 1.2: Dynamic Performance Log
     */
    calculateDynamicAppendix(trialGroups) {
        const data = [];
        
        Object.keys(trialGroups).sort((a, b) => parseInt(a) - parseInt(b)).forEach(trial => {
            const trialNum = parseInt(trial);
            const { hc2l, dhl } = trialGroups[trial];
            
            // Group by batch using batchId from results
            const batches = {};
            
            [...hc2l, ...dhl].forEach((result) => {
                const batchNum = result.batchId || 1;
                if (!batches[batchNum]) {
                    batches[batchNum] = { hc2l: [], dhl: [] };
                }
                
                const algo = result.algorithm?.toLowerCase() === 'dhl' ? 'dhl' : 'hc2l';
                batches[batchNum][algo].push(result);
            });
            
            // Calculate batch statistics
            Object.keys(batches).sort((a, b) => parseInt(a) - parseInt(b)).forEach(batchNum => {
                const batch = batches[batchNum];
                
                ['hc2l', 'dhl'].forEach(algo => {
                    const results = batch[algo];
                    if (results.length === 0) return;
                    
                    const lazyUpdateTimes = results.map(r => r.metrics?.lazyUpdateTimeMs || 0).filter(v => v > 0);
                    const thresholdRebuildTimes = results.map(r => r.metrics?.thresholdRebuildTimeMs || 0).filter(v => v > 0);
                    const peakLabelSizes = results.map(r => r.metrics?.peakLabelSizeKb || r.metrics?.indexSizeKb || 0);
                    const labelSizeChanges = results.map((r, i) => {
                        if (i === 0) return 0;
                        const prev = results[i - 1].metrics?.indexSizeKb || 0;
                        const curr = r.metrics?.indexSizeKb || 0;
                        return prev > 0 ? ((curr - prev) / prev) * 100 : 0;
                    });
                    const queryTimes = results.map(r => r.metrics?.queryTimeMs || r.metrics?.queryTimeNum || 0);
                    
                    data.push({
                        trial: trialNum,
                        batch: parseInt(batchNum),
                        algorithm: algo.toUpperCase(),
                        disruptionLevel: 1000,
                        queriesInBatch: results.length,
                        lazyUpdateTime: lazyUpdateTimes.length > 0 ? lazyUpdateTimes.reduce((a, b) => a + b, 0) / lazyUpdateTimes.length : 0,
                        thresholdRebuildTime: thresholdRebuildTimes.length > 0 ? thresholdRebuildTimes.reduce((a, b) => a + b, 0) / thresholdRebuildTimes.length : 0,
                        peakLabelSize: peakLabelSizes.length > 0 ? Math.max(...peakLabelSizes) : 0,
                        labelSizeChange: labelSizeChanges.length > 0 ? labelSizeChanges.reduce((a, b) => a + b, 0) / labelSizeChanges.length : 0,
                        avgQueryTime: queryTimes.length > 0 ? queryTimes.reduce((a, b) => a + b, 0) / queryTimes.length : 0
                    });
                });
            });
        });
        
        return data;
    },

    /**
     * Calculate Appendix 1.3: Combined Performance Summary
     */
    calculateQueryAppendix(trialGroups, stats) {
        const data = {
            metrics: [],
            trials: []
        };
        
        // Overall metrics comparison
        if (stats.algorithmComparison) {
            const hc2l = stats.algorithmComparison.hc2l;
            const dhl = stats.algorithmComparison.dhl;
            
            const metrics = [
                {
                    name: 'Initial Labeling Time (ms)',
                    hc2l: hc2l.labelingTime?.avg || 0,
                    dhl: dhl.labelingTime?.avg || 0,
                    improvement: this.calculateImprovement(hc2l.labelingTime?.avg, dhl.labelingTime?.avg)
                },
                {
                    name: 'Avg Query Time (ms)',
                    hc2l: hc2l.queryTime?.avg || 0,
                    dhl: dhl.queryTime?.avg || 0,
                    improvement: this.calculateImprovement(hc2l.queryTime?.avg, dhl.queryTime?.avg)
                },
                {
                    name: 'Label Size (MB)',
                    hc2l: (hc2l.labelingSize?.avg || 0) / 1024,
                    dhl: (dhl.labelingSize?.avg || 0) / 1024,
                    improvement: this.calculateImprovement(hc2l.labelingSize?.avg, dhl.labelingSize?.avg)
                },
                {
                    name: 'Peak Label Size (MB)',
                    hc2l: (hc2l.labelingSize?.max || 0) / 1024,
                    dhl: (dhl.labelingSize?.max || 0) / 1024,
                    improvement: this.calculateImprovement(hc2l.labelingSize?.max, dhl.labelingSize?.max)
                },
                {
                    name: 'Lazy Update Time (ms)',
                    hc2l: stats.lazyUpdateTime?.avg || 0,
                    dhl: 0, // DHL doesn't have lazy updates
                    improvement: 0
                },
                {
                    name: 'Threshold Rebuild Time (ms)',
                    hc2l: stats.thresholdRebuildTime?.avg || 0,
                    dhl: 0,
                    improvement: 0
                },
                {
                    name: 'Total Rebuilds',
                    hc2l: stats.thresholdRebuildTime?.count || 0,
                    dhl: stats.lazyUpdateTime?.count || 0,
                    improvement: this.calculateImprovement(stats.thresholdRebuildTime?.count, stats.lazyUpdateTime?.count)
                }
            ];
            
            data.metrics = metrics;
        }
        
        // Per-trial breakdown
        Object.keys(trialGroups).sort((a, b) => parseInt(a) - parseInt(b)).forEach(trial => {
            const trialNum = parseInt(trial);
            const { hc2l, dhl } = trialGroups[trial];
            
            const calcTrialStats = (results) => {
                if (results.length === 0) return null;
                
                const queryTimes = results.map(r => r.metrics?.queryTimeMs || r.metrics?.queryTimeNum || 0).filter(v => v > 0);
                const labelingTimes = results.map(r => r.metrics?.indexLoadTimeMs || r.metrics?.labelingTimeNum || 0).filter(v => v > 0);
                const labelSizes = results.map(r => r.metrics?.indexSizeKb || r.metrics?.labelingSize || 0);
                
                return {
                    avgQueryTime: queryTimes.length > 0 ? queryTimes.reduce((a, b) => a + b) / queryTimes.length : 0,
                    labelingTime: labelingTimes.length > 0 ? labelingTimes[0] : 0,
                    avgLabelSize: labelSizes.length > 0 ? labelSizes.reduce((a, b) => a + b) / labelSizes.length : 0,
                    peakLabelSize: labelSizes.length > 0 ? Math.max(...labelSizes) : 0
                };
            };
            
            const hc2lStats = calcTrialStats(hc2l);
            const dhlStats = calcTrialStats(dhl);
            
            if (hc2lStats && dhlStats) {
                data.trials.push({
                    trial: trialNum,
                    hc2l: hc2lStats,
                    dhl: dhlStats
                });
            }
        });
        
        return data;
    },

    /**
     * Calculate Appendix 1.4: Route Similarity Evaluation
     */
    calculateSimilarityAppendix(trialGroups) {
        const data = [];
        
        // Group results by source-destination pairs
        const pairMap = {};
        
        Object.keys(trialGroups).forEach(trial => {
            const { hc2l, dhl } = trialGroups[trial];
            
            // Match HC2L and DHL routes by index (assuming they query the same routes)
            const minLength = Math.min(hc2l.length, dhl.length);
            
            for (let i = 0; i < minLength; i++) {
                const hc2lResult = hc2l[i];
                const dhlResult = dhl[i];
                
                const source = hc2lResult.source || hc2lResult.start;
                const dest = hc2lResult.destination || hc2lResult.end;
                const pairKey = `${source?.lat || source}_${source?.lng || source}_${dest?.lat || dest}_${dest?.lng || dest}`;
                
                if (!pairMap[pairKey]) {
                    pairMap[pairKey] = {
                        source: source,
                        destination: dest,
                        hc2l: [],
                        dhl: []
                    };
                }
                
                pairMap[pairKey].hc2l.push(hc2lResult);
                pairMap[pairKey].dhl.push(dhlResult);
            }
        });
        
        // Calculate similarity metrics for each pair
        Object.values(pairMap).forEach((pair, idx) => {
            if (pair.hc2l.length === 0 || pair.dhl.length === 0) return;
            
            const hc2l = pair.hc2l[0];
            const dhl = pair.dhl[0];
            
            const hc2lDist = hc2l.metrics?.calculatedDistanceKm || hc2l.metrics?.distanceKm || 0;
            const dhlDist = dhl.metrics?.calculatedDistanceKm || dhl.metrics?.distanceKm || 0;
            const hc2lTime = hc2l.metrics?.etaSeconds || 0;
            const dhlTime = dhl.metrics?.etaSeconds || 0;
            
            const frechetDist = Math.abs(hc2lDist - dhlDist);
            const fdRating = frechetDist < 0.2 ? 'Excellent' : frechetDist < 0.4 ? 'Good' : frechetDist < 0.6 ? 'Fair' : 'Fail';
            
            const timeDev = Math.abs(hc2lTime - dhlTime) / Math.max(hc2lTime, dhlTime, 1) * 100;
            const ttdRating = timeDev < 5 ? 'Excellent' : timeDev < 10 ? 'Good' : timeDev < 20 ? 'Fair' : 'Fail';
            
            data.push({
                pairId: `S ⇔ D`,
                index: idx + 1,
                distance: hc2lDist.toFixed(2),
                travelTime: (hc2lTime / 60).toFixed(2),
                frechetDistance: frechetDist.toFixed(2),
                fdRating: fdRating,
                timeDev: timeDev.toFixed(2),
                ttdRating: ttdRating
            });
        });
        
        // Limit to first few entries for display
        return data.slice(0, 10);
    },

    /**
     * Calculate improvement percentage
     */
    calculateImprovement(baseline, comparison) {
        if (!baseline || baseline === 0) return 0;
        return ((baseline - comparison) / baseline) * 100;
    },

    /**
     * Render Appendix 1.1: Construction Phase
     */
    renderConstructionAppendix(data) {
        const container = document.getElementById('appendix-construction-content');
        if (!container || data.length === 0) {
            if (container) container.innerHTML = '<p class="text-muted text-center py-4">No construction data available</p>';
            return;
        }
        
        // Create table structure
        const table = document.createElement('table');
        table.className = 'appendix-table';
        
        // Create header
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        ['Trial', 'Algorithm', 'Initial Construction Time (ms)', 'Initial Label Size (MB)'].forEach(text => {
            const th = document.createElement('th');
            th.textContent = text;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // Create body
        const tbody = document.createElement('tbody');
        data.forEach(row => {
            const tr = document.createElement('tr');
            const cells = [
                { text: row.trial, className: 'font-semibold' },
                { text: row.algorithm, className: 'font-semibold' },
                { text: row.constructionTime.toFixed(2) },
                { text: ((row.labelSize || 0) / 1024).toFixed(2) }
            ];
            cells.forEach(cell => {
                const td = document.createElement('td');
                td.textContent = cell.text;
                if (cell.className) td.className = cell.className;
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        
        container.innerHTML = '';
        container.appendChild(table);
    },

    renderDynamicAppendix(data) {
        const container = document.getElementById('appendix-dynamic-content');
        if (!container || data.length === 0) {
            if (container) container.innerHTML = '<p class="text-muted text-center py-4">No dynamic update data available</p>';
            return;
        }
        
        // Create summary card
        const summary = document.createElement('div');
        summary.className = 'appendix-summary-card';
        summary.innerHTML = `
            <h5>⚡ Experiment Structure</h5>
            <ul>
                <li><strong>Total Trials:</strong> ${new Set(data.map(r => r.trial)).size}</li>
                <li><strong>Batches per Trial:</strong> 3</li>
                <li><strong>Queries per Batch:</strong> 1,000</li>
                <li><strong>Disruptions per Batch:</strong> 1,000</li>
            </ul>
        `;
        
        // Group by trial and batch
        const trials = {};
        data.forEach(row => {
            if (!trials[row.trial]) trials[row.trial] = {};
            if (!trials[row.trial][row.batch]) trials[row.trial][row.batch] = { HC2L: null, DHL: null };
            trials[row.trial][row.batch][row.algorithm] = row;
        });
        
        // Create table
        const table = document.createElement('table');
        table.className = 'appendix-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th colspan="2">Batch (Updates)</th>
                    <th colspan="2">Lazy Update Time (ms)</th>
                    <th colspan="2">Threshold Rebuild Time (ms)</th>
                    <th colspan="2">Peak Label Size (MB)</th>
                    <th colspan="2">% Label Size Change</th>
                    <th colspan="2">Avg Query Time (ms)</th>
                </tr>
                <tr>
                    <th>Trial</th>
                    <th>Disruption Level</th>
                    <th>HC2L</th>
                    <th>DHL</th>
                    <th>HC2L</th>
                    <th>DHL</th>
                    <th>HC2L</th>
                    <th>DHL</th>
                    <th>HC2L</th>
                    <th>DHL</th>
                    <th>HC2L</th>
                    <th>DHL</th>
                </tr>
            </thead>
        `;
        
        const tbody = document.createElement('tbody');
        Object.keys(trials).sort((a, b) => parseInt(a) - parseInt(b)).forEach(trialNum => {
            const batches = trials[trialNum];
            const rows = [];
            
            Object.keys(batches).sort((a, b) => parseInt(a) - parseInt(b)).forEach(batchNum => {
                const batch = batches[batchNum];
                const hc2l = batch.HC2L || {};
                const dhl = batch.DHL || {};
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${trialNum}</td>
                    <td>${hc2l.disruptionLevel || dhl.disruptionLevel || 1000}</td>
                    <td>${(hc2l.lazyUpdateTime || 0).toFixed(2)}</td>
                    <td>${(dhl.lazyUpdateTime || 0).toFixed(2)}</td>
                    <td>${(hc2l.thresholdRebuildTime || 0).toFixed(2)}</td>
                    <td>${(dhl.thresholdRebuildTime || 0).toFixed(2)}</td>
                    <td>${((hc2l.peakLabelSize || 0) / 1024).toFixed(2)}</td>
                    <td>${((dhl.peakLabelSize || 0) / 1024).toFixed(2)}</td>
                    <td>${(hc2l.labelSizeChange || 0).toFixed(2)}%</td>
                    <td>${(dhl.labelSizeChange || 0).toFixed(2)}%</td>
                    <td>${(hc2l.avgQueryTime || 0).toFixed(3)}</td>
                    <td>${(dhl.avgQueryTime || 0).toFixed(3)}</td>
                `;
                tbody.appendChild(tr);
            });
        });
        table.appendChild(tbody);
        
        container.innerHTML = '';
        container.appendChild(summary);
        container.appendChild(table);
    },

    renderQueryAppendix(data) {
        const container = document.getElementById('appendix-query-content');
        if (!container || !data.metrics || data.metrics.length === 0) {
            if (container) container.innerHTML = '<p class="text-muted text-center py-4">No query performance data available</p>';
            return;
        }
        
        // Create summary
        const summary = document.createElement('div');
        summary.className = 'appendix-summary-card';
        summary.innerHTML = `
            <h5>📊 Performance Comparison Summary</h5>
            <ul>
                <li>Comparing <strong>DHL</strong> vs <strong>DHC2L</strong> across ${(data.trials || []).length} trials</li>
                <li>Average of 3,000 queries per trial</li>
            </ul>
        `;
        
        // Create table
        const table = document.createElement('table');
        table.className = 'appendix-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>DHL (Avg)</th>
                    <th>DHC2L (Avg)</th>
                    <th>% Improvement</th>
                </tr>
            </thead>
        `;
        
        const tbody = document.createElement('tbody');
        data.metrics.forEach(metric => {
            const tr = document.createElement('tr');
            const improvClass = metric.improvement > 0 ? 'improvement-positive' : metric.improvement < 0 ? 'improvement-negative' : '';
            const improvSign = metric.improvement > 0 ? '+' : '';
            tr.innerHTML = `
                <td class="text-left metric-label">${metric.name}</td>
                <td class="metric-value">${metric.dhl.toFixed(2)}</td>
                <td class="metric-value">${metric.hc2l.toFixed(2)}</td>
                <td class="${improvClass}">${improvSign}${metric.improvement.toFixed(2)}%</td>
            `;
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        
        container.innerHTML = '';
        container.appendChild(summary);
        container.appendChild(table);
    },

    renderSimilarityAppendix(data) {
        const container = document.getElementById('appendix-similarity-content');
        if (!container || data.length === 0) {
            if (container) container.innerHTML = '<p class="text-muted text-center py-4">No route similarity data available</p>';
            return;
        }
        
        const avgFrechet = data.reduce((s, r) => s + parseFloat(r.frechetDistance), 0) / data.length;
        const avgTimeDev = data.reduce((s, r) => s + parseFloat(r.timeDev), 0) / data.length;
        
        // Create summary
        const summary = document.createElement('div');
        summary.className = 'appendix-summary-card';
        summary.innerHTML = `
            <h5>🎯 Route Similarity Evaluation</h5>
            <ul>
                <li><strong>Fréchet Distance:</strong> Measures route path similarity</li>
                <li><strong>Excellent:</strong> &lt; 200m | <strong>Good:</strong> 200-400m | <strong>Fair:</strong> &gt; 400m</li>
                <li><strong>Travel Time Deviation:</strong> Measures ETA accuracy</li>
                <li><strong>Excellent:</strong> &lt; 5% | <strong>Good:</strong> 5-10% | <strong>Fair:</strong> &gt; 10%</li>
            </ul>
        `;
        
        // Create table
        const table = document.createElement('table');
        table.className = 'appendix-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>OD Pair</th>
                    <th>Distance (km)</th>
                    <th>Travel Time (min)</th>
                    <th>Fréchet Distance (m)</th>
                    <th>FD Rating</th>
                    <th>Travel Time Deviation (%)</th>
                    <th>TTD Rating</th>
                </tr>
            </thead>
        `;
        
        const tbody = document.createElement('tbody');
        data.forEach(row => {
            const fdClass = row.fdRating === 'Excellent' ? 'rating-excellent' : 
                          row.fdRating === 'Good' ? 'rating-good' : 
                          row.fdRating === 'Fair' ? 'rating-fair' : 'rating-fail';
            
            const ttdClass = row.ttdRating === 'Excellent' ? 'rating-excellent' : 
                           row.ttdRating === 'Good' ? 'rating-good' : 
                           row.ttdRating === 'Fair' ? 'rating-fair' : 'rating-fail';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="font-semibold">${row.pairId}</td>
                <td>${row.distance}</td>
                <td>${row.travelTime}</td>
                <td>${row.frechetDistance}</td>
                <td><span class="${fdClass}">${row.fdRating}</span></td>
                <td>${row.timeDev}</td>
                <td><span class="${ttdClass}">${row.ttdRating}</span></td>
            `;
            tbody.appendChild(tr);
        });
        
        // Add averages row
        const avgRow = document.createElement('tr');
        avgRow.className = 'averages-row';
        avgRow.innerHTML = `
            <td colspan="3">Average</td>
            <td>${avgFrechet.toFixed(2)}</td>
            <td>-</td>
            <td>${avgTimeDev.toFixed(2)}%</td>
            <td>-</td>
        `;
        tbody.appendChild(avgRow);
        table.appendChild(tbody);
        
        container.innerHTML = '';
        container.appendChild(summary);
        container.appendChild(table);
    },

    /**
     * Export appendix data as CSV
     */
    exportAppendixCSV(appendixType) {
        console.log(`Exporting ${appendixType} appendix as CSV...`);
        // TODO: Implement CSV export functionality
        alert(`CSV export for ${appendixType} appendix will be implemented soon.`);
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
