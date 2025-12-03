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
    
    init() {
        console.log('🎬 Initializing Demo Runner...');
        this.loadSavedConfigs();
        this.bindEvents();
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
        }
    },

    closePanel() {
        const panel = document.getElementById('demo-runner-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
        }
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
    // CONFIG MANAGEMENT
    // ==========================================================================

    loadSavedConfigs() {
        try {
            const saved = localStorage.getItem('demoConfigs');
            this.savedConfigs = saved ? JSON.parse(saved) : [];
            this.renderConfigList();
        } catch (e) {
            console.error('Error loading saved configs:', e);
            this.savedConfigs = [];
        }
    },

    saveConfig(config) {
        config.id = `demo-${Date.now()}`;
        config.savedAt = new Date().toISOString();
        this.savedConfigs.push(config);
        localStorage.setItem('demoConfigs', JSON.stringify(this.savedConfigs));
        this.renderConfigList();
        showUpdateToast('Demo configuration saved', 'success');
    },

    deleteConfig(configId) {
        this.savedConfigs = this.savedConfigs.filter(c => c.id !== configId);
        localStorage.setItem('demoConfigs', JSON.stringify(this.savedConfigs));
        this.renderConfigList();
        showUpdateToast('Configuration deleted', 'info');
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
                    <button onclick="DemoRunner.deleteConfig('${config.id}')" 
                            class="p-1 hover:bg-red-100 rounded-lg transition-colors">
                        <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
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

    getRandomLocationPair() {
        let start = this.getRandomLocation();
        let end;
        do {
            end = this.getRandomLocation();
        } while (end.name === start.name);
        return { start, end };
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

        // Generate random routes
        const routes = [];
        for (let i = 0; i < settings.routeCount; i++) {
            const pair = this.getRandomLocationPair();
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
        const totalSteps = routes.length * trials;
        
        console.log('🎬 Starting demo:', config.name);
        showUpdateToast(`🎬 Starting: ${config.name}`, 'info');
        
        this.showTab('running');
        this.updateRunningUI(0, totalSteps, 'Initializing...');

        try {
            // Reset map
            await this.resetMap();
            
            let currentStep = 0;
            
            // Run for each trial
            for (let trial = 0; trial < trials; trial++) {
                if (!this.isRunning) break;
                
                // Process each route
                for (let i = 0; i < routes.length; i++) {
                    if (!this.isRunning) break;
                    while (this.isPaused) {
                        await this.delay(100);
                    }
                    
                    currentStep++;
                    const route = routes[i];
                    const trialLabel = trials > 1 ? ` (Trial ${trial + 1}/${trials})` : '';
                    this.updateRunningUI(currentStep, totalSteps, `Route ${i + 1}: ${route.start.name} → ${route.end.name}${trialLabel}`);
                    
                    await this.processRoute(route, config);
                    await this.delay(config.stepDelay || 2000);
                }
            }

            if (this.isRunning) {
                showUpdateToast('✅ Demo completed!', 'success');
                this.updateRunningUI(totalSteps, totalSteps, 'Demo completed!');
            }

        } catch (error) {
            console.error('Demo error:', error);
            showUpdateToast('Demo failed: ' + error.message, 'error');
        } finally {
            this.isRunning = false;
            this.currentDemo = null;
        }
    },

    async processRoute(route, config) {
        // Set start location
        this.updateRunningUI(null, null, `Setting start: ${route.start.name}`);
        if (typeof handleOSMStartLocationPin === 'function') {
            await handleOSMStartLocationPin(route.start.lat, route.start.lng);
        }
        await this.delay(1000);

        // Set destination
        this.updateRunningUI(null, null, `Setting destination: ${route.end.name}`);
        if (typeof handleOSMDestLocationPin === 'function') {
            await handleOSMDestLocationPin(route.end.lat, route.end.lng);
        }
        await this.delay(1000);

        // Set algorithm
        const algorithm = config.algorithm || 'hc2l';
        if (algorithm === 'both') {
            document.querySelector('input[name="algorithm"][value="hc2l"]')?.click();
        } else {
            document.querySelector(`input[name="algorithm"][value="${algorithm}"]`)?.click();
        }

        // Set disruption mode
        const disruption = config.disruptionMode || 'none';
        const disruptionRadio = document.querySelector(`input[name="dataset"][value="${disruption}"]`);
        if (disruptionRadio) {
            disruptionRadio.click();
        }

        await this.delay(500);

        // Test each tau value
        const tauValues = route.tauValues || [0.5];
        for (const tau of tauValues) {
            if (!this.isRunning) break;
            while (this.isPaused) {
                await this.delay(100);
            }

            this.updateRunningUI(null, null, `Testing τ = ${tau.toFixed(2)}`);
            
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

            await this.delay(config.stepDelay || 2000);
        }

        // Compare algorithms if needed
        if (config.algorithm === 'both') {
            this.updateRunningUI(null, null, 'Comparing HC2L vs DHL...');
            
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

    updateRunningUI(current, total, status) {
        const progressEl = document.getElementById('demo-running-progress');
        const statusEl = document.getElementById('demo-running-status');
        const barEl = document.getElementById('demo-running-bar');
        
        if (current !== null && total !== null && progressEl) {
            progressEl.textContent = `${current} / ${total}`;
            if (barEl) {
                barEl.style.width = `${(current / total) * 100}%`;
            }
        }
        
        if (statusEl && status) {
            statusEl.textContent = status;
        }
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
