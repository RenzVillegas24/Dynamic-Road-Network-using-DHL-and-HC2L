/**
 * Experiment Wizard Module
 * 4-Step wizard for configuring and running automated experiments:
 * 1. Locations - Configure start/destination pairs
 * 2. Traffic - Set disruption parameters
 * 3. Sequence - Define batch/trial configuration
 * 4. Review - Preview and launch experiment
 * 
 * Includes real-time experiment progress panel with route visualization
 */

// ============================================================
// WIZARD STATE MANAGEMENT
// ============================================================

const ExperimentWizard = {
    // Current wizard state
    state: {
        currentStep: 1,
        config: {
            name: '',
            description: '',
            locations: {
                start: null,
                destination: null,
                use_preset: true,
                preset_name: 'quezon_city_presets'
            },
            traffic: {
                mode: 'both',  // 'none', 'flow', 'incidents', 'both'
                disruption_count: 3,
                severity_range: [0.1, 1.0],
                dynamic_disruptions: true
            },
            sequence: {
                num_batches: 3,
                disruptions_per_batch: [1, 3, 5],
                trials_per_disruption: 5,
                tau_values: [0.1, 0.3, 0.5, 0.7, 0.9],
                algorithms: ['hc2l', 'dhl']
            },
            settings: {
                auto_export: true,
                visualize_routes: true,
                delay_between_trials: 500,
                pause_on_error: false
            }
        },
        validation: {
            step1: false,
            step2: false,
            step3: false,
            step4: false
        }
    },

    // Experiment execution state
    experiment: {
        isRunning: false,
        isPaused: false,
        experimentId: null,
        progress: {
            currentBatch: 0,
            totalBatches: 0,
            currentDisruption: 0,
            totalDisruptions: 0,
            currentTrial: 0,
            totalTrials: 0,
            currentAlgorithm: null,
            percentComplete: 0
        },
        metrics: {
            hc2l: { avgQueryTime: 0, avgUpdateTime: 0 },
            dhl: { avgQueryTime: 0, avgUpdateTime: 0 }
        },
        pollInterval: null
    },

    // ============================================================
    // INITIALIZATION
    // ============================================================

    init() {
        console.log('🧪 Initializing Experiment Wizard...');
        this.loadSavedConfigs();
        this.bindEvents();
        this.updateStepIndicators();
    },

    bindEvents() {
        // Open wizard button
        const openBtn = document.getElementById('open-experiment-wizard-btn');
        if (openBtn) {
            openBtn.addEventListener('click', () => this.openWizard());
        }

        // Close buttons
        document.querySelectorAll('[data-close-experiment-wizard]').forEach(btn => {
            btn.addEventListener('click', () => this.closeWizard());
        });

        // Navigation buttons
        document.getElementById('experiment-next-btn')?.addEventListener('click', () => this.nextStep());
        document.getElementById('experiment-prev-btn')?.addEventListener('click', () => this.prevStep());
        document.getElementById('experiment-start-btn')?.addEventListener('click', () => this.startExperiment());

        // Step clicks
        document.querySelectorAll('[data-experiment-step]').forEach(indicator => {
            indicator.addEventListener('click', (e) => {
                const step = parseInt(e.currentTarget.dataset.experimentStep);
                if (this.canNavigateToStep(step)) {
                    this.goToStep(step);
                }
            });
        });

        // Input bindings for validation
        this.bindInputValidation();
    },

    bindInputValidation() {
        // Step 1: Locations
        document.getElementById('exp-location-mode')?.addEventListener('change', (e) => {
            this.state.config.locations.use_preset = e.target.value === 'preset';
            this.toggleLocationInputs();
            this.validateStep(1);
        });

        // Step 2: Traffic
        document.getElementById('exp-traffic-mode')?.addEventListener('change', (e) => {
            this.state.config.traffic.mode = e.target.value;
            this.validateStep(2);
        });

        document.getElementById('exp-disruption-count')?.addEventListener('input', (e) => {
            this.state.config.traffic.disruption_count = parseInt(e.target.value) || 3;
            this.validateStep(2);
        });

        // Step 3: Sequence
        document.getElementById('exp-num-batches')?.addEventListener('input', (e) => {
            this.state.config.sequence.num_batches = parseInt(e.target.value) || 3;
            this.updateDisruptionsPerBatchInputs();
            this.validateStep(3);
        });

        document.getElementById('exp-trials-per-disruption')?.addEventListener('input', (e) => {
            this.state.config.sequence.trials_per_disruption = parseInt(e.target.value) || 5;
            this.validateStep(3);
            this.updateTotalCalculation();
        });
    },

    // ============================================================
    // NAVIGATION
    // ============================================================

    openWizard() {
        const panel = document.getElementById('experiment-wizard-panel');
        if (panel) {
            panel.classList.remove('translate-x-full');
            panel.classList.add('translate-x-0');
        }
        this.goToStep(1);
    },

    closeWizard() {
        const panel = document.getElementById('experiment-wizard-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
            panel.classList.remove('translate-x-0');
        }
    },

    nextStep() {
        if (this.validateStep(this.state.currentStep)) {
            if (this.state.currentStep < 4) {
                this.goToStep(this.state.currentStep + 1);
            }
        } else {
            showUpdateToast('Please complete this step before continuing', 'warning');
        }
    },

    prevStep() {
        if (this.state.currentStep > 1) {
            this.goToStep(this.state.currentStep - 1);
        }
    },

    goToStep(step) {
        // Hide all steps
        for (let i = 1; i <= 4; i++) {
            const stepEl = document.getElementById(`experiment-step-${i}`);
            if (stepEl) {
                stepEl.classList.add('hidden');
            }
        }

        // Show target step
        const targetStep = document.getElementById(`experiment-step-${step}`);
        if (targetStep) {
            targetStep.classList.remove('hidden');
        }

        this.state.currentStep = step;
        this.updateStepIndicators();
        this.updateNavigationButtons();

        // If going to review step, populate summary
        if (step === 4) {
            this.populateReviewSummary();
        }
    },

    canNavigateToStep(step) {
        // Can always go back
        if (step < this.state.currentStep) return true;
        
        // Check if all previous steps are valid
        for (let i = 1; i < step; i++) {
            if (!this.state.validation[`step${i}`]) {
                return false;
            }
        }
        return true;
    },

    updateStepIndicators() {
        for (let i = 1; i <= 4; i++) {
            const indicator = document.querySelector(`[data-experiment-step="${i}"]`);
            if (indicator) {
                indicator.classList.remove('bg-blue-600', 'bg-green-600', 'bg-gray-300', 'text-white', 'text-gray-600');
                
                if (i === this.state.currentStep) {
                    indicator.classList.add('bg-blue-600', 'text-white');
                } else if (this.state.validation[`step${i}`]) {
                    indicator.classList.add('bg-green-600', 'text-white');
                } else {
                    indicator.classList.add('bg-gray-300', 'text-gray-600');
                }
            }
        }
    },

    updateNavigationButtons() {
        const prevBtn = document.getElementById('experiment-prev-btn');
        const nextBtn = document.getElementById('experiment-next-btn');
        const startBtn = document.getElementById('experiment-start-btn');

        if (prevBtn) {
            prevBtn.classList.toggle('hidden', this.state.currentStep === 1);
        }

        if (nextBtn) {
            nextBtn.classList.toggle('hidden', this.state.currentStep === 4);
        }

        if (startBtn) {
            startBtn.classList.toggle('hidden', this.state.currentStep !== 4);
        }
    },

    // ============================================================
    // VALIDATION
    // ============================================================

    validateStep(step) {
        let isValid = false;

        switch (step) {
            case 1:
                isValid = this.validateLocationsStep();
                break;
            case 2:
                isValid = this.validateTrafficStep();
                break;
            case 3:
                isValid = this.validateSequenceStep();
                break;
            case 4:
                isValid = this.validateReviewStep();
                break;
        }

        this.state.validation[`step${step}`] = isValid;
        this.updateStepIndicators();
        return isValid;
    },

    validateLocationsStep() {
        const config = this.state.config.locations;
        
        if (config.use_preset) {
            return config.preset_name && config.preset_name.length > 0;
        } else {
            return config.start !== null && config.destination !== null;
        }
    },

    validateTrafficStep() {
        const config = this.state.config.traffic;
        return config.mode !== null && config.disruption_count >= 0;
    },

    validateSequenceStep() {
        const config = this.state.config.sequence;
        return config.num_batches > 0 && 
               config.trials_per_disruption > 0 &&
               config.tau_values.length > 0 &&
               config.algorithms.length > 0;
    },

    validateReviewStep() {
        return this.state.validation.step1 && 
               this.state.validation.step2 && 
               this.state.validation.step3;
    },

    // ============================================================
    // STEP-SPECIFIC UI UPDATES
    // ============================================================

    toggleLocationInputs() {
        const presetInputs = document.getElementById('exp-preset-inputs');
        const customInputs = document.getElementById('exp-custom-inputs');

        if (this.state.config.locations.use_preset) {
            presetInputs?.classList.remove('hidden');
            customInputs?.classList.add('hidden');
        } else {
            presetInputs?.classList.add('hidden');
            customInputs?.classList.remove('hidden');
        }
    },

    updateDisruptionsPerBatchInputs() {
        const container = document.getElementById('exp-disruptions-per-batch');
        if (!container) return;

        const numBatches = this.state.config.sequence.num_batches;
        container.innerHTML = '';

        for (let i = 0; i < numBatches; i++) {
            const defaultValue = this.state.config.sequence.disruptions_per_batch[i] || (i + 1);
            const input = document.createElement('div');
            input.className = 'flex items-center gap-2';
            input.innerHTML = `
                <label class="text-sm font-medium text-gray-700 w-20">Batch ${i + 1}:</label>
                <input type="number" 
                       class="exp-batch-disruption flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" 
                       value="${defaultValue}" 
                       min="1" 
                       max="20"
                       data-batch="${i}">
            `;
            container.appendChild(input);
        }

        // Bind events for new inputs
        container.querySelectorAll('.exp-batch-disruption').forEach(input => {
            input.addEventListener('input', (e) => {
                const batchIndex = parseInt(e.target.dataset.batch);
                this.state.config.sequence.disruptions_per_batch[batchIndex] = parseInt(e.target.value) || 1;
                this.updateTotalCalculation();
            });
        });

        this.updateTotalCalculation();
    },

    updateTotalCalculation() {
        const calc = document.getElementById('exp-total-calculation');
        if (!calc) return;

        const seq = this.state.config.sequence;
        const totalDisruptions = seq.disruptions_per_batch.slice(0, seq.num_batches).reduce((a, b) => a + b, 0);
        const totalTrials = totalDisruptions * seq.trials_per_disruption * seq.tau_values.length * seq.algorithms.length;

        calc.innerHTML = `
            <div class="text-sm text-gray-600">
                <strong>Total experiments:</strong><br>
                ${seq.num_batches} batches × varying disruptions × ${seq.trials_per_disruption} trials × ${seq.tau_values.length} τ values × ${seq.algorithms.length} algorithms
                <br><span class="text-blue-600 font-bold">= ${totalTrials.toLocaleString()} total route calculations</span>
            </div>
        `;
    },

    populateReviewSummary() {
        const summary = document.getElementById('exp-review-summary');
        if (!summary) return;

        const config = this.state.config;
        const seq = config.sequence;
        const totalDisruptions = seq.disruptions_per_batch.slice(0, seq.num_batches).reduce((a, b) => a + b, 0);

        summary.innerHTML = `
            <div class="space-y-4">
                <!-- Experiment Name -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Experiment Name</label>
                    <input type="text" id="exp-name" 
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                           value="${config.name || 'Experiment_' + new Date().toISOString().slice(0, 10)}"
                           placeholder="My Experiment">
                </div>

                <!-- Locations Summary -->
                <div class="bg-blue-50 p-4 rounded-xl">
                    <h4 class="font-semibold text-blue-800 mb-2">📍 Locations</h4>
                    <p class="text-sm text-blue-700">
                        ${config.locations.use_preset 
                            ? `Using preset: ${config.locations.preset_name}`
                            : `Custom: ${config.locations.start?.name || 'Not set'} → ${config.locations.destination?.name || 'Not set'}`
                        }
                    </p>
                </div>

                <!-- Traffic Summary -->
                <div class="bg-orange-50 p-4 rounded-xl">
                    <h4 class="font-semibold text-orange-800 mb-2">🚦 Traffic Configuration</h4>
                    <p class="text-sm text-orange-700">
                        Mode: ${config.traffic.mode}<br>
                        Disruption count: ${config.traffic.disruption_count}<br>
                        Dynamic updates: ${config.traffic.dynamic_disruptions ? 'Yes' : 'No'}
                    </p>
                </div>

                <!-- Sequence Summary -->
                <div class="bg-purple-50 p-4 rounded-xl">
                    <h4 class="font-semibold text-purple-800 mb-2">🔢 Experiment Sequence</h4>
                    <p class="text-sm text-purple-700">
                        Batches: ${seq.num_batches}<br>
                        Total disruptions: ${totalDisruptions}<br>
                        Trials per disruption: ${seq.trials_per_disruption}<br>
                        TAU values: ${seq.tau_values.join(', ')}<br>
                        Algorithms: ${seq.algorithms.map(a => a.toUpperCase()).join(', ')}
                    </p>
                </div>

                <!-- Export Settings -->
                <div class="bg-green-50 p-4 rounded-xl">
                    <h4 class="font-semibold text-green-800 mb-2">📊 Output Settings</h4>
                    <label class="flex items-center gap-2 text-sm text-green-700">
                        <input type="checkbox" id="exp-auto-export" ${config.settings.auto_export ? 'checked' : ''}>
                        Auto-export results to CSV
                    </label>
                    <label class="flex items-center gap-2 text-sm text-green-700 mt-2">
                        <input type="checkbox" id="exp-visualize" ${config.settings.visualize_routes ? 'checked' : ''}>
                        Visualize routes on map
                    </label>
                </div>
            </div>
        `;

        // Bind name input
        document.getElementById('exp-name')?.addEventListener('input', (e) => {
            this.state.config.name = e.target.value;
        });

        document.getElementById('exp-auto-export')?.addEventListener('change', (e) => {
            this.state.config.settings.auto_export = e.target.checked;
        });

        document.getElementById('exp-visualize')?.addEventListener('change', (e) => {
            this.state.config.settings.visualize_routes = e.target.checked;
        });
    },

    // ============================================================
    // CONFIGURATION MANAGEMENT
    // ============================================================

    async loadSavedConfigs() {
        try {
            const response = await fetch('/experiment/configs');
            if (response.ok) {
                const data = await response.json();
                this.populateConfigList(data.configs || []);
            }
        } catch (error) {
            console.error('Failed to load saved configs:', error);
        }
    },

    populateConfigList(configs) {
        const container = document.getElementById('exp-saved-configs');
        if (!container) return;

        if (configs.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-sm italic">No saved configurations</p>';
            return;
        }

        container.innerHTML = configs.map(config => `
            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                <div>
                    <span class="font-medium">${config.name}</span>
                    <span class="text-xs text-gray-500 ml-2">${config.created_at || ''}</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="ExperimentWizard.loadConfig('${config.id}')" 
                            class="text-blue-600 hover:text-blue-800 text-sm font-medium">Load</button>
                    <button onclick="ExperimentWizard.deleteConfig('${config.id}')" 
                            class="text-red-600 hover:text-red-800 text-sm font-medium">Delete</button>
                </div>
            </div>
        `).join('');
    },

    async loadConfig(configId) {
        try {
            const response = await fetch(`/experiment/configs/${configId}`);
            if (response.ok) {
                const data = await response.json();
                this.state.config = { ...this.state.config, ...data.config };
                showUpdateToast(`Loaded configuration: ${data.config.name}`, 'success');
                this.goToStep(1);
                this.refreshAllSteps();
            }
        } catch (error) {
            showUpdateToast('Failed to load configuration', 'error');
        }
    },

    async saveConfig() {
        try {
            const response = await fetch('/experiment/configs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.state.config)
            });

            if (response.ok) {
                showUpdateToast('Configuration saved', 'success');
                this.loadSavedConfigs();
            }
        } catch (error) {
            showUpdateToast('Failed to save configuration', 'error');
        }
    },

    async deleteConfig(configId) {
        if (!confirm('Are you sure you want to delete this configuration?')) return;

        try {
            const response = await fetch(`/experiment/configs/${configId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                showUpdateToast('Configuration deleted', 'success');
                this.loadSavedConfigs();
            }
        } catch (error) {
            showUpdateToast('Failed to delete configuration', 'error');
        }
    },

    refreshAllSteps() {
        this.toggleLocationInputs();
        this.updateDisruptionsPerBatchInputs();
        this.validateStep(1);
        this.validateStep(2);
        this.validateStep(3);
    },

    // ============================================================
    // EXPERIMENT EXECUTION
    // ============================================================

    async startExperiment() {
        if (!this.validateReviewStep()) {
            showUpdateToast('Please complete all steps before starting', 'warning');
            return;
        }

        // Get experiment name
        const nameInput = document.getElementById('exp-name');
        this.state.config.name = nameInput?.value || 'Experiment_' + Date.now();

        try {
            showUpdateToast('🚀 Starting experiment...', 'info');
            
            const response = await fetch('/experiment/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.state.config)
            });

            const data = await response.json();

            if (data.success) {
                this.experiment.experimentId = data.experiment_id;
                this.experiment.isRunning = true;
                this.closeWizard();
                this.openProgressPanel();
                this.startProgressPolling();
                showUpdateToast(`Experiment started: ${data.experiment_id}`, 'success');
            } else {
                showUpdateToast(`Failed to start experiment: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Experiment start error:', error);
            showUpdateToast('Failed to start experiment', 'error');
        }
    },

    // ============================================================
    // PROGRESS PANEL
    // ============================================================

    openProgressPanel() {
        const panel = document.getElementById('experiment-progress-panel');
        if (panel) {
            panel.classList.remove('translate-x-full');
            panel.classList.add('translate-x-0');
        }
    },

    closeProgressPanel() {
        const panel = document.getElementById('experiment-progress-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
            panel.classList.remove('translate-x-0');
        }
        this.stopProgressPolling();
    },

    startProgressPolling() {
        if (this.experiment.pollInterval) {
            clearInterval(this.experiment.pollInterval);
        }

        this.experiment.pollInterval = setInterval(() => this.fetchProgress(), 1000);
        this.fetchProgress(); // Immediate first fetch
    },

    stopProgressPolling() {
        if (this.experiment.pollInterval) {
            clearInterval(this.experiment.pollInterval);
            this.experiment.pollInterval = null;
        }
    },

    async fetchProgress() {
        if (!this.experiment.experimentId) return;

        try {
            const response = await fetch(`/experiment/progress?experiment_id=${this.experiment.experimentId}`);
            const data = await response.json();

            if (data.success) {
                this.updateProgressUI(data.progress);

                // Check if experiment completed
                if (data.progress.status === 'completed' || data.progress.status === 'failed') {
                    this.experiment.isRunning = false;
                    this.stopProgressPolling();
                    this.onExperimentComplete(data.progress);
                }

                // Visualize current route if enabled
                if (this.state.config.settings.visualize_routes && data.progress.current_route) {
                    this.visualizeRoute(data.progress.current_route);
                }
            }
        } catch (error) {
            console.error('Progress fetch error:', error);
        }
    },

    updateProgressUI(progress) {
        // Update progress bar
        const progressBar = document.getElementById('exp-progress-bar');
        const progressText = document.getElementById('exp-progress-text');
        
        if (progressBar) {
            progressBar.style.width = `${progress.percent_complete}%`;
        }
        if (progressText) {
            progressText.textContent = `${progress.percent_complete.toFixed(1)}%`;
        }

        // Update status text
        const statusEl = document.getElementById('exp-status');
        if (statusEl) {
            statusEl.textContent = progress.status_message || progress.status;
        }

        // Update batch/disruption/trial counters
        document.getElementById('exp-batch-counter')?.textContent = 
            `Batch ${progress.current_batch}/${progress.total_batches}`;
        document.getElementById('exp-disruption-counter')?.textContent = 
            `Disruption ${progress.current_disruption}/${progress.total_disruptions}`;
        document.getElementById('exp-trial-counter')?.textContent = 
            `Trial ${progress.current_trial}/${progress.total_trials}`;

        // Update algorithm indicator
        const algoEl = document.getElementById('exp-current-algorithm');
        if (algoEl && progress.current_algorithm) {
            algoEl.textContent = progress.current_algorithm.toUpperCase();
            algoEl.className = `font-bold ${progress.current_algorithm === 'hc2l' ? 'text-cyan-600' : 'text-purple-600'}`;
        }

        // Update live metrics
        if (progress.metrics) {
            this.updateMetricsDisplay(progress.metrics);
        }

        // Update log
        if (progress.log_entry) {
            this.appendLogEntry(progress.log_entry);
        }
    },

    updateMetricsDisplay(metrics) {
        const metricsContainer = document.getElementById('exp-live-metrics');
        if (!metricsContainer) return;

        metricsContainer.innerHTML = `
            <div class="grid grid-cols-2 gap-4">
                <!-- HC2L Metrics -->
                <div class="bg-cyan-50 p-3 rounded-xl">
                    <h5 class="font-bold text-cyan-800 text-sm mb-2">HC2L</h5>
                    <div class="text-xs space-y-1">
                        <div class="flex justify-between">
                            <span>Avg Query:</span>
                            <span class="font-mono">${(metrics.hc2l?.avg_query_time || 0).toFixed(3)}ms</span>
                        </div>
                        <div class="flex justify-between">
                            <span>Avg Update:</span>
                            <span class="font-mono">${(metrics.hc2l?.avg_update_time || 0).toFixed(3)}ms</span>
                        </div>
                    </div>
                </div>
                
                <!-- DHL Metrics -->
                <div class="bg-purple-50 p-3 rounded-xl">
                    <h5 class="font-bold text-purple-800 text-sm mb-2">DHL</h5>
                    <div class="text-xs space-y-1">
                        <div class="flex justify-between">
                            <span>Avg Query:</span>
                            <span class="font-mono">${(metrics.dhl?.avg_query_time || 0).toFixed(3)}ms</span>
                        </div>
                        <div class="flex justify-between">
                            <span>Avg Update:</span>
                            <span class="font-mono">${(metrics.dhl?.avg_update_time || 0).toFixed(3)}ms</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    appendLogEntry(entry) {
        const logContainer = document.getElementById('exp-log');
        if (!logContainer) return;

        const entryEl = document.createElement('div');
        entryEl.className = 'text-xs font-mono py-1 border-b border-gray-100';
        entryEl.innerHTML = `
            <span class="text-gray-400">${entry.timestamp || new Date().toLocaleTimeString()}</span>
            <span class="ml-2 ${entry.level === 'error' ? 'text-red-600' : 'text-gray-700'}">${entry.message}</span>
        `;
        
        logContainer.appendChild(entryEl);
        logContainer.scrollTop = logContainer.scrollHeight;

        // Keep only last 100 entries
        while (logContainer.children.length > 100) {
            logContainer.removeChild(logContainer.firstChild);
        }
    },

    visualizeRoute(routeData) {
        if (!routeData || !routeData.path_coords) return;

        // Use existing map visualization functions
        if (typeof drawRouteOnMap === 'function') {
            const color = routeData.algorithm === 'hc2l' ? '#06b6d4' : '#9333ea';
            drawRouteOnMap(routeData.path_coords, color, routeData.algorithm);
        }
    },

    onExperimentComplete(progress) {
        showUpdateToast(
            progress.status === 'completed' 
                ? '✅ Experiment completed successfully!' 
                : '❌ Experiment failed',
            progress.status === 'completed' ? 'success' : 'error'
        );

        // Update UI to show completion
        const progressBar = document.getElementById('exp-progress-bar');
        if (progressBar) {
            progressBar.classList.add(progress.status === 'completed' ? 'bg-green-500' : 'bg-red-500');
        }

        // Enable export buttons
        document.getElementById('exp-export-csv-btn')?.removeAttribute('disabled');
        document.getElementById('exp-export-appendix-btn')?.removeAttribute('disabled');
    },

    // ============================================================
    // CONTROL BUTTONS
    // ============================================================

    async pauseExperiment() {
        try {
            const response = await fetch('/experiment/pause', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ experiment_id: this.experiment.experimentId })
            });

            if (response.ok) {
                this.experiment.isPaused = true;
                showUpdateToast('Experiment paused', 'info');
                this.updateControlButtons();
            }
        } catch (error) {
            showUpdateToast('Failed to pause experiment', 'error');
        }
    },

    async resumeExperiment() {
        try {
            const response = await fetch('/experiment/resume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ experiment_id: this.experiment.experimentId })
            });

            if (response.ok) {
                this.experiment.isPaused = false;
                showUpdateToast('Experiment resumed', 'info');
                this.updateControlButtons();
            }
        } catch (error) {
            showUpdateToast('Failed to resume experiment', 'error');
        }
    },

    async stopExperiment() {
        if (!confirm('Are you sure you want to stop the experiment?')) return;

        try {
            const response = await fetch('/experiment/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ experiment_id: this.experiment.experimentId })
            });

            if (response.ok) {
                this.experiment.isRunning = false;
                this.stopProgressPolling();
                showUpdateToast('Experiment stopped', 'warning');
            }
        } catch (error) {
            showUpdateToast('Failed to stop experiment', 'error');
        }
    },

    updateControlButtons() {
        const pauseBtn = document.getElementById('exp-pause-btn');
        const resumeBtn = document.getElementById('exp-resume-btn');

        if (pauseBtn && resumeBtn) {
            pauseBtn.classList.toggle('hidden', this.experiment.isPaused);
            resumeBtn.classList.toggle('hidden', !this.experiment.isPaused);
        }
    },

    // ============================================================
    // EXPORT FUNCTIONS
    // ============================================================

    async exportToCSV() {
        try {
            const response = await fetch(`/experiment/export/csv?experiment_id=${this.experiment.experimentId}`);
            const blob = await response.blob();
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `experiment_${this.experiment.experimentId}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            showUpdateToast('CSV exported successfully', 'success');
        } catch (error) {
            showUpdateToast('Failed to export CSV', 'error');
        }
    },

    async exportAppendix() {
        try {
            const response = await fetch(`/experiment/export/appendix?experiment_id=${this.experiment.experimentId}`);
            const blob = await response.blob();
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `appendix_${this.experiment.experimentId}.zip`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            showUpdateToast('Appendix tables exported successfully', 'success');
        } catch (error) {
            showUpdateToast('Failed to export appendix', 'error');
        }
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    ExperimentWizard.init();
});

// Global function bindings for HTML onclick handlers
window.openExperimentWizard = () => ExperimentWizard.openWizard();
window.closeExperimentWizard = () => ExperimentWizard.closeWizard();
window.pauseExperiment = () => ExperimentWizard.pauseExperiment();
window.resumeExperiment = () => ExperimentWizard.resumeExperiment();
window.stopExperiment = () => ExperimentWizard.stopExperiment();
window.exportExperimentCSV = () => ExperimentWizard.exportToCSV();
window.exportExperimentAppendix = () => ExperimentWizard.exportAppendix();
