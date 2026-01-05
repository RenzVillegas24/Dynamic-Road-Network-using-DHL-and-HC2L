/**
 * Experiment Runner Module
 * 
 * Display-only frontend for experiment execution with:
 * - WebSocket real-time updates from backend
 * - Multi-thread progress visualization
 * - Per-thread metrics display
 * - Color-coded route visualization on map
 * 
 * NO client-side computation - all processing done by Python backend
 */

const ExperimentRunner = {
    // =========================================================================
    // STATE
    // =========================================================================
    
    // Current experiment state
    currentExperimentId: null,
    isRunning: false,
    isPaused: false,
    
    // WebSocket connection
    socket: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 1000,
    lastUpdateTimestamp: null,
    
    // Results data from backend
    resultsData: null,
    currentResultId: null,
    
    // Chart instances (for cleanup)
    chartInstances: {},
    
    // Display settings
    threadColors: [
        '#3B82F6', // blue
        '#10B981', // green
        '#F59E0B', // amber
        '#EF4444', // red
        '#8B5CF6', // violet
        '#EC4899', // pink
        '#14B8A6', // teal
        '#F97316', // orange
        '#6366F1'  // indigo
    ],
    
    // Progress data from backend
    progressData: null,
    
    // Preset experiments
    presets: [],
    
    // Settings
    settings: {
        threadCount: 3,  // 3 (default) or 9 (advanced)
        algorithms: ['DHL', 'HC2L'],
        trials: 3,
        batchesPerTrial: 3,
        routesPerBatch: 1000,
        tauMode: 'random',
        tauScope: 'per-trial-route',
        tauFixed: 0.5,
        tauRandomMin: 0.1,
        tauRandomMax: 0.9
    },
    
    // HERE comparison pagination state
    similarityData: [],           // All similarity data from backend
    similarityDisplayedCount: 0,  // Number of rows currently displayed
    similarityPageSize: 20,       // Rows per page (infinite scroll)
    hereComparisonProgress: null, // HERE comparison thread progress
    
    // =========================================================================
    // INITIALIZATION
    // =========================================================================
    
    init() {
        console.log('🧪 Initializing Experiment Runner');
        
        // Load presets
        this.loadPresets();
        
        // Load results list
        this.loadResultsList();
        
        // Initialize UI event listeners
        this.initEventListeners();
        
        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        console.log('✅ Experiment Runner initialized');
    },
    
    initEventListeners() {
        // Panel toggle
        const panelBtn = document.getElementById('experiment-runner-btn');
        if (panelBtn) {
            panelBtn.addEventListener('click', () => this.togglePanel());
        }
        
        // Close button
        const closeBtn = document.getElementById('close-experiment-runner');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closePanel());
        }
        
        // Tab navigation - now handled by radio input onchange handlers in HTML
        
        // Thread count toggle
        const threadCountToggle = document.getElementById('experiment-thread-count');
        if (threadCountToggle) {
            threadCountToggle.addEventListener('change', (e) => {
                this.settings.threadCount = e.target.checked ? 9 : 3;
                this.updateThreadCountDisplay();
            });
        }
        
        // Tau mode radios
        document.querySelectorAll('input[name="experiment-tau-mode"]').forEach(radio => {
            radio.addEventListener('change', () => this.updateTauUI());
        });
        
        // Start experiment button
        const startBtn = document.getElementById('start-experiment-btn');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.startExperiment());
        }
        
        // Pause/Resume button
        const pauseBtn = document.getElementById('pause-experiment-btn');
        if (pauseBtn) {
            pauseBtn.addEventListener('click', () => this.togglePause());
        }
        
        // Stop button
        const stopBtn = document.getElementById('stop-experiment-btn');
        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopExperiment());
        }
    },
    
    // =========================================================================
    // PANEL MANAGEMENT
    // =========================================================================
    
    togglePanel() {
        const panel = document.getElementById('experiment-runner-panel');
        if (panel) {
            panel.classList.toggle('translate-x-full');
        }
    },
    
    closePanel() {
        const panel = document.getElementById('experiment-runner-panel');
        if (panel) {
            panel.classList.add('translate-x-full');
        }
    },
    
    showTab(tabId) {
        // Hide all tabs
        document.querySelectorAll('[data-experiment-tab-content]').forEach(tab => {
            tab.classList.add('hidden');
        });
        
        // Show selected tab
        const selectedTab = document.getElementById(`experiment-tab-${tabId}`);
        if (selectedTab) {
            selectedTab.classList.remove('hidden');
        }
        
        // Update radio button state
        const radioBtn = document.querySelector(`input[name="experiment-main-tab"][value="${tabId}"]`);
        if (radioBtn) {
            radioBtn.checked = true;
        }
        
        // Special handling for results-list tab
        if (tabId === 'results-list') {
            this.refreshResultsList();
        }

        const nav = document.getElementById('experiment-panel-nav');
        if (nav){
            if (tabId === 'running' || tabId === 'results') {
                nav.classList.add('hidden');
            } else {
                nav.classList.remove('hidden');
            }
        }
        


        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    // =========================================================================
    // WEBSOCKET CONNECTION
    // =========================================================================
    
    connectWebSocket(experimentId) {
        if (this.socket) {
            this.socket.disconnect();
        }
        
        // Connect to SocketIO namespace
        this.socket = io('/experiment', {
            transports: ['websocket', 'polling']
        });
        
        // Connection event handlers
        this.socket.on('connect', () => {
            console.log('🔌 WebSocket connected to /experiment namespace');
            this.reconnectAttempts = 0;
            this.updateConnectionStatus(true);
            
            // Join experiment room
            this.socket.emit('join', { experiment_id: experimentId });
        });
        
        this.socket.on('disconnect', () => {
            console.log('🔌 WebSocket disconnected');
            this.updateConnectionStatus(false);
            
            // Attempt reconnection
            if (this.isRunning && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
                console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
                setTimeout(() => this.socket.connect(), delay);
            }
        });
        
        // Progress updates (experiment running)
        this.socket.on('progress_update', (data) => {
            this.lastUpdateTimestamp = new Date();
            this.handleProgressUpdate(data);
        });
        
        // Preset progress updates (during preset creation/loading)
        this.socket.on('preset_progress', (data) => {
            this.handlePresetProgress(data);
        });
        
        // Error handling
        this.socket.on('error', (error) => {
            console.error('WebSocket error:', error);
            this.showNotification('WebSocket error: ' + error.message, 'error');
        });
        
        // Start keepalive ping
        this.startKeepalive();
    },
    
    handlePresetProgress(data) {
        console.log('Preset progress:', data);
        
        const statusEl = document.getElementById('experiment-status');
        const progressBar = document.getElementById('experiment-overall-progress-bar');
        const progressText = document.getElementById('experiment-overall-progress-text');
        
        // Update status message
        if (statusEl) {
            statusEl.textContent = data.message || 'Preparing...';
            
            // Color based on status
            const statusColors = {
                'loading': 'text-blue-600',
                'creating': 'text-yellow-600',
                'loading_complete': 'text-green-600',
                'creating_complete': 'text-green-600',
                'error': 'text-red-600'
            };
            statusEl.className = `text-sm font-medium ${statusColors[data.status] || 'text-gray-600'}`;
        }
        
        // Update progress bar
        if (progressBar) {
            progressBar.style.width = `${data.progress || 0}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${data.progress || 0}%`;
        }
        
        // Show notification for completion or errors
        if (data.status === 'loading_complete') {
            this.showNotification('Preset loaded successfully', 'success');
        } else if (data.status === 'creating_complete') {
            this.showNotification('Preset created successfully', 'success');
        } else if (data.status === 'error') {
            this.showNotification(`Preset error: ${data.message}`, 'error');
        }
    },
    
    disconnectWebSocket() {
        if (this.socket) {
            if (this.currentExperimentId) {
                this.socket.emit('leave', { experiment_id: this.currentExperimentId });
            }
            this.socket.disconnect();
            this.socket = null;
        }
        this.stopKeepalive();
    },
    
    startKeepalive() {
        this.keepaliveInterval = setInterval(() => {
            if (this.socket && this.socket.connected) {
                this.socket.emit('ping');
            }
        }, 30000);
    },
    
    stopKeepalive() {
        if (this.keepaliveInterval) {
            clearInterval(this.keepaliveInterval);
            this.keepaliveInterval = null;
        }
    },
    
    updateConnectionStatus(connected) {
        const statusIndicator = document.getElementById('experiment-connection-status');
        if (statusIndicator) {
            if (connected) {
                statusIndicator.classList.remove('bg-red-500');
                statusIndicator.classList.add('bg-green-500');
                statusIndicator.title = 'Connected';
            } else {
                statusIndicator.classList.remove('bg-green-500');
                statusIndicator.classList.add('bg-red-500');
                statusIndicator.title = 'Disconnected';
            }
        }
        
        const lastUpdateEl = document.getElementById('experiment-last-update');
        if (lastUpdateEl && this.lastUpdateTimestamp) {
            lastUpdateEl.textContent = `Last update: ${this.lastUpdateTimestamp.toLocaleTimeString()}`;
        }
    },
    
    // =========================================================================
    // EXPERIMENT LIFECYCLE
    // =========================================================================
    
    async loadPresets() {
        try {
            const response = await fetch('/api/experiment/preset/list', { method: 'GET' });
            const result = await response.json();
            
            if (result.success) {
                this.presets = result.presets || [];
                this.renderPresetList();
            }
        } catch (error) {
            console.error('Error loading presets:', error);
        }
    },
    
    async startExperiment() {
        if (this.isRunning) {
            this.showNotification('An experiment is already running', 'warning');
            return;
        }
        
        // Gather settings from UI
        const config = this.gatherExperimentConfig();
        
        this.showNotification('Preparing experiment...', 'info');
        
        // Show running tab (automatically during execution)
        this.showTab('running');
        this.showPreparationStatus('Checking preset configuration...');
        
        try {
            const response = await fetch('/api/experiment/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.currentExperimentId = result.experiment_id;
                this.isRunning = true;
                this.isPaused = false;
                
                // Connect WebSocket for real-time updates (including preset progress)
                this.connectWebSocket(result.experiment_id);
                
                // Initialize thread displays
                this.initializeThreadDisplays(config.thread_count || 3);
                
                this.showNotification(`Experiment started: ${result.experiment_id}`, 'success');
            } else {
                this.showNotification(`Failed to start experiment: ${result.error}`, 'error');
                this.showTab('settings'); // Return to settings on error
            }
        } catch (error) {
            console.error('Error starting experiment:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
            this.showTab('settings'); // Return to settings on error
        }
    },
    
    showPreparationStatus(message) {
        // Show status in the status card
        const statusEl = document.getElementById('experiment-status');
        if (statusEl) {
            statusEl.textContent = message;
            statusEl.className = 'text-sm font-medium text-yellow-600';
        }
        
        // Show in progress bar area
        const progressText = document.getElementById('experiment-overall-progress-text');
        if (progressText) {
            progressText.textContent = '...';
        }
    },
    
    async togglePause(mode='toggle') {
        if (!this.currentExperimentId) return;
        
        if (mode === 'toggle') {
            this.isPaused = !this.isPaused;
        } else if (mode === 'pause') {
            this.isPaused = true;
        } else if (mode === 'resume') {
            this.isPaused = false;
        }
        
        const endpoint = this.isPaused ? 'pause' : 'resume';
        
        try {
            const response = await fetch(`/api/experiment/${this.currentExperimentId}/${endpoint}`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.isPaused = !this.isPaused;
                this.updatePauseButton();
                this.showNotification(`Experiment ${this.isPaused ? 'paused' : 'resumed'}`, 'info');
            }
        } catch (error) {
            console.error(`Error ${endpoint}ing experiment:`, error);
        }
    },
    
    async stopExperiment() {
        if (!this.currentExperimentId) return;
        
        // First, pause the experiment to freeze progress
        await this.togglePause('pause');
        
        // Now show confirmation modal with experiment paused
        if (typeof UniversalModal === 'undefined') {
            console.error('UniversalModal not available, falling back to browser confirm');
            if (!confirm('Are you sure you want to stop the experiment?')) {
                // User cancelled - resume the experiment
                await this.togglePause('resume');
                return;
            }
            this._performStopExperiment();
            return;
        }
        
        UniversalModal.showModal({
            icon: 'alert-circle',
            variant: 'warning',
            title: 'Stop Experiment?',
            body: '<p class="text-sm text-slate-700 leading-relaxed">The experiment is now paused. Are you sure you want to stop it? This action cannot be undone and all current progress will be lost.</p>',
            buttons: {
                'Stop Experiment': (closeModal) => {
                    closeModal();
                    this._performStopExperiment();
                }
            },
            closeBtn: {
                'Cancel': async (closeModal) => {
                    // User cancelled - resume the experiment
                    await this.togglePause('resume');
                }
            },
            backdropClose: false,
            escapeClose: true
        });
    },
    
    async _performStopExperiment() {
        try {
            const response = await fetch(`/api/experiment/${this.currentExperimentId}/stop`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.isRunning = false;
                this.isPaused = false;
                this.disconnectWebSocket();
                this.showNotification('Experiment stopped', 'warning');
                
                // Show results tab
                this.showTab('settings');
            }
        } catch (error) {
            console.error('Error stopping experiment:', error);
            this.showNotification('Error stopping experiment', 'error');
        }
    },
    
    gatherExperimentConfig() {
        // Get settings from UI
        const threadCount = document.getElementById('experiment-thread-count')?.checked ? 9 : 3;
        
        // Route mode
        const routeMode = document.querySelector('input[name="experiment-route-mode"]:checked')?.value || 'preset';
        
        // Determine if preset mode (includes both preset types)
        const isPreset = routeMode === 'preset' || routeMode === 'same_batch_preset';
        
        // Routes per batch
        const routesPerBatch = parseInt(document.getElementById('experiment-routes-per-batch')?.value || 1000);
        
        // Disruption mode
        const disruptionMode = document.querySelector('input[name="experiment-disruption-mode"]:checked')?.value || 'preset';
        
        // Severity range
        const severityMin = parseFloat(document.getElementById('experiment-severity-min')?.value || 0.1);
        const severityMax = parseFloat(document.getElementById('experiment-severity-max')?.value || 0.9);
        
        // Flow:Incident ratio
        const ratioFlow = parseInt(document.getElementById('experiment-ratio-flow')?.value || 95);
        const ratioIncident = parseInt(document.getElementById('experiment-ratio-incident')?.value || 5);
        
        // Tau settings
        const tauMode = document.querySelector('input[name="experiment-tau-mode"]:checked')?.value || 'random';
        const tauScope = document.querySelector('input[name="experiment-tau-scope"]:checked')?.value || 'per-trial-route';
        
        return {
            is_preset: isPreset,
            thread_count: threadCount,
            trials: 3,
            batches_per_trial: 3,
            routes_per_batch: routesPerBatch,
            algorithms: ['DHL', 'HC2L'],
            route_mode: routeMode,
            disruption_mode: disruptionMode,
            disruption_settings: {
                ratio_flow: ratioFlow,
                ratio_incident: ratioIncident,
                severity_min: severityMin,
                severity_max: severityMax
            },
            tau_settings: {
                mode: tauMode,
                scope: tauScope,
                fixed: parseFloat(document.getElementById('experiment-tau-fixed-value')?.value || 0.5),
                random_min: parseFloat(document.getElementById('experiment-tau-random-min')?.value || 0.1),
                random_max: parseFloat(document.getElementById('experiment-tau-random-max')?.value || 0.9)
            }
        };
    },
    
    // =========================================================================
    // PROGRESS HANDLING
    // =========================================================================
    
    handleProgressUpdate(data) {
        this.progressData = data;
        
        // Update overall progress
        this.updateOverallProgress(data);
        
        // Update per-thread progress
        if (data.threads) {
            Object.entries(data.threads).forEach(([threadId, threadData]) => {
                this.updateThreadProgress(threadId, threadData);
            });
        }
        
        // Update HERE comparison progress
        if (data.here_comparison) {
            this.updateHereComparisonProgress(data.here_comparison);
        }
        
        // Update disruption display
        if (data.disruption_display) {
            this.updateDisruptionDisplay(data.disruption_display);
        }
        
        // Check for completion or finalizing
        if (data.status === 'finalizing') {
            // Show finalizing status with progress message
            this.handleExperimentFinalizing(data.finalization_phase || 'Processing results...');
        } else if (data.status === 'completed') {
            this.handleExperimentComplete();
        } else if (data.status === 'error') {
            this.handleExperimentError(data.error_message);
        }
        
        // Update route visualization on map
        this.updateMapVisualization(data);
    },
    
    updateOverallProgress(data) {
        // Update status
        const statusEl = document.getElementById('experiment-status');
        if (statusEl) {
            // If finalizing, show the finalization phase message
            if (data.status === 'finalizing' && data.finalization_phase) {
                statusEl.textContent = data.finalization_phase;
            } else {
                statusEl.textContent = this.formatStatus(data.status);
            }
            statusEl.className = `text-sm font-medium ${this.getStatusColor(data.status)}`;
        }
        
        // Update overall progress bar
        const progressBar = document.getElementById('experiment-overall-progress-bar');
        const progressText = document.getElementById('experiment-overall-progress-text');
        
        if (progressBar) {
            progressBar.style.width = `${data.overall_percentage || 0}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${(data.overall_percentage || 0).toFixed(1)}%`;
        }
        
        // Update route counts
        const routeCountEl = document.getElementById('experiment-route-count');
        if (routeCountEl) {
            if (data.status === 'finalizing') {
                // Show finalization progress instead of route counts
                routeCountEl.textContent = `Finalizing... (${data.finalization_percentage || 0}% of finalization phase)`;
            } else {
                routeCountEl.textContent = `${data.completed_routes || 0} / ${data.total_routes || 0}`;
            }
        }
        
        // Update ETA - hide during finalization
        const etaEl = document.getElementById('experiment-eta');
        if (etaEl) {
            if (data.status === 'finalizing') {
                etaEl.textContent = 'Computing...';
            } else {
                etaEl.textContent = data.estimated_time_remaining || '--';
            }
        }
    },
    
    updateThreadProgress(threadId, threadData) {
        const container = document.getElementById(`experiment-thread-${threadId}`);
        if (!container) return;
        
        // Get thread index for color
        const threadIndex = parseInt(threadId.replace('thread_', '')) || 0;
        const color = this.threadColors[threadIndex % this.threadColors.length];
        
        // Update thread header
        const headerEl = container.querySelector('.thread-header');
        if (headerEl) {
            headerEl.style.borderLeftColor = color;
        }
        
        // Update status badge
        const statusEl = container.querySelector('.thread-status');
        if (statusEl) {
            statusEl.textContent = this.formatStatus(threadData.status);
            statusEl.className = `thread-status text-xs px-2 py-1 rounded ${this.getStatusBgColor(threadData.status)}`;
        }
        
        // Update progress bar
        const progressBar = container.querySelector('.thread-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${threadData.percentage || 0}%`;
            progressBar.style.backgroundColor = color;
        }
        
        // Update trial/batch info
        const trialEl = container.querySelector('.thread-trial');
        if (trialEl) {
            trialEl.textContent = `Trial: ${threadData.trial_number || 'N/A'}`;
        }
        
        const batchEl = container.querySelector('.thread-batch');
        if (batchEl && threadData.batch_number) {
            batchEl.textContent = `Batch: ${threadData.batch_number}`;
        }
        
        // Update route progress
        const routeEl = container.querySelector('.thread-route');
        if (routeEl) {
            routeEl.textContent = `Route: ${threadData.route_progress || '0/0'}`;
        }
        
        // Update algorithm
        const algorithmEl = container.querySelector('.thread-algorithm');
        if (algorithmEl) {
            algorithmEl.textContent = threadData.algorithm || '--';
        }
        
        // Update Last Result section
        this.updateThreadLastResult(container, threadData.last_result);
        
        // Update Update Phase section
        this.updateThreadUpdatePhase(container, threadData.update_phase);
        
        // Update Query Phase section
        this.updateThreadQueryPhase(container, threadData.query_phase);
        
        // Update Route History section (last 5 routes)
        this.updateThreadRouteHistory(container, threadData.results_history);
        
        // Update throughput
        const throughputEl = container.querySelector('.thread-throughput');
        if (throughputEl) {
            const rpm = threadData.routes_per_minute || 0;
            throughputEl.textContent = `${rpm.toFixed(1)} routes/min`;
        }
    },
    
    updateThreadLastResult(container, lastResult) {
        if (!lastResult) return;
        
        const section = container.querySelector('.thread-last-result');
        if (!section) return;
        
        // Route: Show as "start_node -> end_node"
        const routeEl = section.querySelector('[data-metric="route"]');
        if (routeEl) {
            const startNode = lastResult.start_node || '--';
            const endNode = lastResult.end_node || '--';
            routeEl.textContent = `${startNode} → ${endNode}`;
        }
        
        // Start Road Name
        const startRoadEl = section.querySelector('[data-metric="start-road"]');
        if (startRoadEl) startRoadEl.textContent = lastResult.start_road_name || 'Unknown Road';
        
        // End Road Name
        const endRoadEl = section.querySelector('[data-metric="end-road"]');
        if (endRoadEl) endRoadEl.textContent = lastResult.end_road_name || 'Unknown Road';
        
        // Algorithm
        const algoEl = section.querySelector('[data-metric="algorithm"]');
        if (algoEl) algoEl.textContent = lastResult.algorithm || '--';
        
        // Path Length
        const pathLengthEl = section.querySelector('[data-metric="path-length"]');
        if (pathLengthEl) pathLengthEl.textContent = lastResult.path_length || '--';
        
        // Query Time
        const queryTimeEl = section.querySelector('[data-metric="query-time"]');
        if (queryTimeEl) queryTimeEl.textContent = `${(lastResult.query_time_ms || 0).toFixed(3)} ms`;
        
        // Distance
        const distanceEl = section.querySelector('[data-metric="distance"]');
        if (distanceEl) distanceEl.textContent = `${(lastResult.distance_km || 0).toFixed(2)} km`;
        
        // Index Load Time
        const indexLoadTimeEl = section.querySelector('[data-metric="index-load-time"]');
        if (indexLoadTimeEl) indexLoadTimeEl.textContent = `${(lastResult.index_load_time_ms || 0).toFixed(3)} ms`;
        
        // ETAs
        const baselineEtaEl = section.querySelector('[data-metric="baseline-eta"]');
        if (baselineEtaEl) baselineEtaEl.textContent = lastResult.baseline_eta || '--';
        
        const actualEtaEl = section.querySelector('[data-metric="actual-eta"]');
        if (actualEtaEl) actualEtaEl.textContent = lastResult.actual_eta || '--';
        
        // Max Cut Size
        const maxCutSizeEl = section.querySelector('[data-metric="max-cut-size"]');
        if (maxCutSizeEl) maxCutSizeEl.textContent = lastResult.max_cut_size || '--';
        
        // Time Impact
        const impactEl = section.querySelector('[data-metric="time-impact"]');
        if (impactEl) {
            const impact = lastResult.time_impact_seconds || 0;
            impactEl.textContent = `${impact >= 0 ? '+' : ''}${impact.toFixed(1)}s`;
            impactEl.className = impact > 0 ? 'text-red-500' : 'text-green-500';
        }
        
        // Non-Empty Cuts
        const nonEmptyCutsEl = section.querySelector('[data-metric="non-empty-cuts"]');
        if (nonEmptyCutsEl) nonEmptyCutsEl.textContent = lastResult.non_empty_cuts || '--';
        
        // Label Size
        const labelEl = section.querySelector('[data-metric="label-size"]');
        if (labelEl) labelEl.textContent = lastResult.label_size || '--';
        
        // Tau
        const tauEl = section.querySelector('[data-metric="tau"]');
        if (tauEl) tauEl.textContent = (lastResult.tau || 0).toFixed(3);
        
        // Disrupted Edges
        const edgesEl = section.querySelector('[data-metric="disrupted-edges"]');
        if (edgesEl) edgesEl.textContent = lastResult.disrupted_edges || '0';
        
        // Memory Usage (if available)
        const memoryEl = section.querySelector('[data-metric="memory-peak"]');
        if (memoryEl && lastResult.memory_peak_mb) {
            memoryEl.textContent = `${lastResult.memory_peak_mb.toFixed(2)} MB`;
        } else if (memoryEl) {
            memoryEl.textContent = 'N/A';
        }
    },
    
    updateThreadUpdatePhase(container, updatePhase) {
        if (!updatePhase) return;
        
        const section = container.querySelector('.thread-update-phase');
        if (!section) return;
        
        // Status
        const statusEl = section.querySelector('[data-metric="status"]');
        if (statusEl) statusEl.textContent = updatePhase.status || '--';
        
        // Lazy Update Time
        const lazyTimeEl = section.querySelector('[data-metric="lazy-time"]');
        if (lazyTimeEl) lazyTimeEl.textContent = `${(updatePhase.lazy_update_time_ms || 0).toFixed(3)} ms`;
        
        // Strategy
        const strategyEl = section.querySelector('[data-metric="strategy"]');
        if (strategyEl) strategyEl.textContent = updatePhase.update_strategy || '--';
        
        // Max Label Size
        const maxLabelEl = section.querySelector('[data-metric="max-label"]');
        if (maxLabelEl) maxLabelEl.textContent = updatePhase.max_label_size || '--';
        
        // Min Label Size
        const minLabelEl = section.querySelector('[data-metric="min-label"]');
        if (minLabelEl) minLabelEl.textContent = updatePhase.min_label_size || '--';
        
        // Nodes Repaired (HC2L only)
        const repairedEl = section.querySelector('[data-metric="nodes-repaired"]');
        if (repairedEl) repairedEl.textContent = updatePhase.nodes_repaired ?? 'N/A';
        
        // Dirty Nodes (HC2L only)
        const dirtyEl = section.querySelector('[data-metric="dirty-nodes"]');
        if (dirtyEl) dirtyEl.textContent = updatePhase.dirty_nodes ?? 'N/A';
        
        // Impact Score
        const impactEl = section.querySelector('[data-metric="impact-score"]');
        if (impactEl) impactEl.textContent = updatePhase.impact_score ?? 'N/A';
    },
    
    updateThreadQueryPhase(container, queryPhase) {
        if (!queryPhase) return;
        
        const section = container.querySelector('.thread-query-phase');
        if (!section) return;
        
        // Algorithm
        const algoEl = section.querySelector('[data-metric="algorithm"]');
        if (algoEl) algoEl.textContent = queryPhase.algorithm || '--';
        
        // Avg Query Time
        const avgTimeEl = section.querySelector('[data-metric="avg-time"]');
        if (avgTimeEl) avgTimeEl.textContent = `${(queryPhase.avg_query_time_ms || 0).toFixed(3)} ms`;
        
        // Std Dev
        const stdDevEl = section.querySelector('[data-metric="std-dev"]');
        if (stdDevEl) stdDevEl.textContent = queryPhase.std_dev ?? 'N/A';
        
        // Min Query Time
        const minTimeEl = section.querySelector('[data-metric="min-time"]');
        if (minTimeEl) minTimeEl.textContent = `${(queryPhase.min_query_time_ms || 0).toFixed(3)} ms`;
        
        // Max Query Time
        const maxTimeEl = section.querySelector('[data-metric="max-time"]');
        if (maxTimeEl) maxTimeEl.textContent = queryPhase.max_query_time_ms ? `${queryPhase.max_query_time_ms.toFixed(3)} ms` : 'N/A';
        
        // P95 Latency
        const p95El = section.querySelector('[data-metric="p95"]');
        if (p95El) p95El.textContent = queryPhase.p95_latency_ms ?? 'N/A';
        
        // Queries Count
        const countEl = section.querySelector('[data-metric="queries-count"]');
        if (countEl) countEl.textContent = queryPhase.queries_count || 0;
    },
    
    updateThreadRouteHistory(container, routeHistory) {
        if (!routeHistory || routeHistory.length === 0) return;
        
        const historyContainer = container.querySelector('.thread-route-history');
        if (!historyContainer) return;
        
        // Build HTML for each route in history (last 5)
        const routesHtml = routeHistory.slice(-5).reverse().map((route, idx) => {
            const routeNum = route.query_number || '--';  // Use actual query number from history
            const startNode = route.start_node || '--';
            const endNode = route.end_node || '--';
            const startRoad = route.start_road_name || 'Unknown';
            const endRoad = route.end_road_name || 'Unknown';
            const queryTime = (route.query_time_ms || 0).toFixed(2);
            const distance = (route.distance_km || 0).toFixed(2);
            const eta = route.actual_eta || '--';
            
            return `
                <div class="bg-white rounded p-2 border border-green-200 text-xs space-y-1">
                    <div class="flex items-center justify-between">
                        <span class="font-medium text-gray-700">Query ${routeNum}: ${startNode} → ${endNode}</span>
                        <span class="text-gray-500">${queryTime}ms</span>
                    </div>
                    <div class="text-gray-600 space-y-0.5">
                        <div><span class="text-gray-400">Start:</span> ${startRoad}</div>
                        <div><span class="text-gray-400">End:</span> ${endRoad}</div>
                        <div class="flex gap-3">
                            <span><span class="text-gray-400">Distance:</span> ${distance}km</span>
                            <span><span class="text-gray-400">ETA:</span> ${eta}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        historyContainer.innerHTML = routesHtml || '<p class="text-gray-400 text-xs italic">No routes executed yet</p>';
    },
    
    updateDisruptionDisplay(disruptionData) {
        const container = document.getElementById('experiment-disruption-display');
        if (!container) return;
        
        // Update toggles
        const showIncidentsToggle = container.querySelector('#experiment-show-incidents');
        if (showIncidentsToggle) {
            showIncidentsToggle.checked = disruptionData.show_incidents;
        }
        
        const showFlowToggle = container.querySelector('#experiment-show-flow');
        if (showFlowToggle) {
            showFlowToggle.checked = disruptionData.show_flow;
        }
        
        // Update count
        const countEl = container.querySelector('.disruption-count');
        if (countEl) {
            countEl.textContent = `${disruptionData.total_count || 0} disruptions`;
        }
    },
    
    // =========================================================================
    // MAP VISUALIZATION
    // =========================================================================
    
    updateMapVisualization(data) {
        // In multi-thread mode, don't auto-zoom, show all routes
        if (data.thread_count > 1) {
            this.showMultiThreadRoutes(data);
        } else {
            this.showSingleThreadRoute(data);
        }
    },
    
    showMultiThreadRoutes(data) {
        // Center map on Quezon City without zooming
        if (typeof map !== 'undefined' && map) {
            // Only set center once at start
            if (!this.mapCentered) {
                map.setView([14.65, 121.05], 12);
                this.mapCentered = true;
            }
        }
        
        // Show routes with thread-specific colors
        // This would integrate with the main map's route display
    },
    
    showSingleThreadRoute(data) {
        // Zoom to current route
        const activeThread = Object.values(data.threads || {}).find(t => t.status === 'running');
        if (activeThread && activeThread.last_result) {
            // Zoom to current route
        }
    },
    
    // =========================================================================
    // UI HELPERS
    // =========================================================================
    
    initializeThreadDisplays(threadCount) {
        const container = document.getElementById('experiment-threads-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        for (let i = 0; i < threadCount; i++) {
            const threadId = `thread_${i}`;
            const color = this.threadColors[i % this.threadColors.length];
            
            const threadHtml = this.createThreadDisplayHTML(threadId, color, i, threadCount);
            container.insertAdjacentHTML('beforeend', threadHtml);
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    createThreadDisplayHTML(threadId, color, index, totalThreads) {
        const trialNum = totalThreads === 3 ? index + 1 : Math.floor(index / 3) + 1;
        const batchNum = totalThreads === 9 ? (index % 3) + 1 : null;
        
        const batchHtml = batchNum ? `<span class="thread-batch text-gray-500">Batch: ${batchNum}/3</span>` : '';
        
        return `
        <div id="experiment-thread-${threadId}" class="thread-display bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
            <!-- Thread Header -->
            <div class="thread-header border-l-4 pl-3 mb-3" style="border-left-color: ${color};">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <div class="w-3 h-3 rounded-full" style="background-color: ${color};"></div>
                        <span class="font-medium text-gray-800">Thread ${index + 1}</span>
                        <span class="thread-status text-xs px-2 py-1 rounded bg-gray-200 text-gray-600">Not Started</span>
                    </div>
                    <button class="text-gray-500 hover:text-gray-700" onclick="ExperimentRunner.toggleThreadDetails('${threadId}')">
                        <i data-lucide="chevron-down" class="w-4 h-4"></i>
                    </button>
                </div>
                
                <!-- Progress Bar -->
                <div class="mt-2 bg-gray-200 rounded-full h-2 overflow-hidden">
                    <div class="thread-progress-bar h-full transition-all duration-300" style="width: 0%; background-color: ${color};"></div>
                </div>
                
                <!-- Quick Stats -->
                <div class="mt-2 flex items-center gap-4 text-xs text-gray-600">
                    <span class="thread-trial">Trial: ${trialNum}/3</span>
                    ${batchHtml}
                    <span class="thread-route">Route: 0/0</span>
                    <span class="thread-algorithm font-medium">--</span>
                    <span class="thread-throughput text-purple-600">0 routes/min</span>
                </div>
            </div>
            
            <!-- Thread Details (collapsible) -->
            <div id="experiment-thread-${threadId}-details" class="thread-details space-y-3">
                <!-- Last Result -->
                <div class="thread-last-result bg-gray-50 rounded-lg p-3">
                    <h4 class="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1">
                        <i data-lucide="zap" class="w-3 h-3"></i> Last Result
                    </h4>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <div><span class="text-gray-500">Route:</span> <span data-metric="route" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Algorithm:</span> <span data-metric="algorithm" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Start Road:</span> <span data-metric="start-road" class="font-medium text-blue-600">Unknown Road</span></div>
                        <div><span class="text-gray-500">End Road:</span> <span data-metric="end-road" class="font-medium text-blue-600">Unknown Road</span></div>
                        <div><span class="text-gray-500">Path Length:</span> <span data-metric="path-length" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Query Time:</span> <span data-metric="query-time" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Distance:</span> <span data-metric="distance" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Index Load Time:</span> <span data-metric="index-load-time" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Baseline ETA:</span> <span data-metric="baseline-eta" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Actual ETA:</span> <span data-metric="actual-eta" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Max Cut Size:</span> <span data-metric="max-cut-size" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Time Impact:</span> <span data-metric="time-impact" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Non-Empty Cuts:</span> <span data-metric="non-empty-cuts" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Label Size:</span> <span data-metric="label-size" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Tau (τ):</span> <span data-metric="tau" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Disrupted Edges:</span> <span data-metric="disrupted-edges" class="font-medium">0</span></div>
                        <div><span class="text-gray-500">Peak Memory:</span> <span data-metric="memory-peak" class="font-medium">--</span></div>
                    </div>
                </div>
                
                <!-- Update Phase -->
                <div class="thread-update-phase bg-blue-50 rounded-lg p-3">
                    <h4 class="text-xs font-semibold text-blue-700 mb-2 flex items-center gap-1">
                        <i data-lucide="refresh-cw" class="w-3 h-3"></i> Update Phase
                    </h4>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <div><span class="text-gray-500">Status:</span> <span data-metric="status" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Lazy Update:</span> <span data-metric="lazy-time" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Strategy:</span> <span data-metric="strategy" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Max Label:</span> <span data-metric="max-label" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Min Label:</span> <span data-metric="min-label" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Nodes Repaired:</span> <span data-metric="nodes-repaired" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Dirty Nodes:</span> <span data-metric="dirty-nodes" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Impact Score:</span> <span data-metric="impact-score" class="font-medium">--</span></div>
                    </div>
                </div>
                
                <!-- Query Phase -->
                <div class="thread-query-phase bg-green-50 rounded-lg p-3">
                    <h4 class="text-xs font-semibold text-green-700 mb-2 flex items-center gap-1">
                        <i data-lucide="search" class="w-3 h-3"></i> Query Phase
                    </h4>
                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <div><span class="text-gray-500">Algorithm:</span> <span data-metric="algorithm" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Avg Time:</span> <span data-metric="avg-time" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Std Dev:</span> <span data-metric="std-dev" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Min Time:</span> <span data-metric="min-time" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Max Time:</span> <span data-metric="max-time" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">P95 Latency:</span> <span data-metric="p95" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Queries:</span> <span data-metric="queries-count" class="font-medium">--</span></div>
                    </div>
                    
                    <!-- Route History (Last 5 Routes) -->
                    <div class="mt-3 border-t border-green-200 pt-3">
                        <h5 class="text-xs font-semibold text-green-700 mb-2">Last 5 Routes</h5>
                        <div class="thread-route-history space-y-1 max-h-40 overflow-y-auto">
                            <p class="text-gray-400 text-xs italic">No routes executed yet</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;
    },
    
    toggleThreadDetails(threadId) {
        const details = document.getElementById(`experiment-thread-${threadId}-details`);
        if (details) {
            details.classList.toggle('hidden');
        }
    },
    
    renderPresetList() {
        const container = document.getElementById('experiment-preset-list');
        if (!container) return;
        
        if (this.presets.length === 0) {
            container.innerHTML = `
                <div class="text-center text-gray-500 py-4">
                    <i data-lucide="folder-open" class="w-8 h-8 mx-auto mb-2"></i>
                    <p>No preset experiments found</p>
                </div>
            `;
        } else {
            container.innerHTML = this.presets.map(preset => `
                <div class="preset-item bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-2 hover:border-purple-500 cursor-pointer"
                     onclick="ExperimentRunner.loadPreset('${preset.id}')">
                    <div class="flex items-center justify-between">
                        <div>
                            <h4 class="font-medium text-gray-800">${preset.name}</h4>
                            <p class="text-xs text-gray-500">${preset.description || 'No description'}</p>
                        </div>
                        <div class="text-right text-xs text-gray-500">
                            <div>${preset.trial_count} trials × ${preset.batch_count} batches</div>
                            <div>${preset.created_at ? new Date(preset.created_at).toLocaleDateString() : 'Unknown date'}</div>
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    loadPreset(presetId) {
        // Load preset configuration
        const preset = this.presets.find(p => p.id === presetId);
        if (preset) {
            this.showNotification(`Loaded preset: ${preset.name}`, 'success');
            // Settings would be applied here
        }
    },
    
    updateTauUI() {
        const mode = document.querySelector('input[name="experiment-tau-mode"]:checked')?.value || 'random';
        
        const fixedSettings = document.getElementById('experiment-tau-fixed-setting');
        const randomSettings = document.getElementById('experiment-tau-random-setting');
        
        if (fixedSettings) {
            fixedSettings.classList.toggle('hidden', mode !== 'fixed');
        }
        
        if (randomSettings) {
            randomSettings.classList.toggle('hidden', mode !== 'random');
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    updateDisruptionModeUI() {
        const mode = document.querySelector('input[name="experiment-disruption-mode"]:checked')?.value || 'preset';
        
        const severityRangeSection = document.getElementById('experiment-severity-range-section');
        
        // Hide severity range when variety_preset is selected
        if (severityRangeSection) {
            severityRangeSection.classList.toggle('hidden', mode === 'variety_preset');
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    updateThreadCountDisplay() {
        const display = document.getElementById('experiment-thread-count-display');
        if (display) {
            display.textContent = `${this.settings.threadCount} threads`;
        }
    },
    
    updatePauseButton() {
        const btn = document.getElementById('pause-experiment-btn');
        if (btn) {
            const icon = btn.querySelector('[data-lucide]');
            const text = btn.querySelector('.btn-text');
            
            if (this.isPaused) {
                if (icon) icon.setAttribute('data-lucide', 'play');
                if (text) text.textContent = 'Resume';
            } else {
                if (icon) icon.setAttribute('data-lucide', 'pause');
                if (text) text.textContent = 'Pause';
            }
            
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    },
    
    formatStatus(status) {
        const statusMap = {
            'initializing': 'Initializing',
            'running': 'Running',
            'paused': 'Paused',
            'finalizing': 'Finalizing',
            'completed': 'Completed',
            'error': 'Error',
            'stopped': 'Stopped',
            'not_started': 'Not Started'
        };
        return statusMap[status] || status;
    },
    
    getStatusColor(status) {
        const colorMap = {
            'initializing': 'text-yellow-600',
            'running': 'text-green-600',
            'paused': 'text-orange-600',
            'finalizing': 'text-purple-600',
            'completed': 'text-blue-600',
            'error': 'text-red-600',
            'stopped': 'text-gray-600'
        };
        return colorMap[status] || 'text-gray-600';
    },
    
    getStatusBgColor(status) {
        const colorMap = {
            'initializing': 'bg-yellow-100 text-yellow-700',
            'running': 'bg-green-100 text-green-700',
            'paused': 'bg-orange-100 text-orange-700',
            'finalizing': 'bg-purple-100 text-purple-700',
            'completed': 'bg-blue-100 text-blue-700',
            'error': 'bg-red-100 text-red-700',
            'stopped': 'bg-gray-100 text-gray-700',
            'not_started': 'bg-gray-100 text-gray-600'
        };
        return colorMap[status] || 'bg-gray-100 text-gray-600';
    },
    
    handleExperimentFinalizing(message) {
        console.log('🔄 Experiment finalizing:', message);
        this.showNotification(message || 'Processing results...', 'info');
    },
    
    handleExperimentComplete() {
        this.isRunning = false;
        this.disconnectWebSocket();
        this.showNotification('Experiment completed! Loading results...', 'success');
        
        // Clear map centering flag for next run
        this.mapCentered = false;
        
        // CRITICAL: Poll for the result endpoint until JSON file is saved and readable
        // This ensures the file is fully written to disk before attempting to load
        const experimentId = this.currentExperimentId;
        let attempts = 0;
        const maxAttempts = 60; // 60 seconds max wait (results file might be large)
        const pollInterval = 500; // Check every 500ms initially, then every 1s after 10 attempts
        
        const checkResults = async () => {
            attempts++;
            
            // Increase poll interval after multiple attempts to reduce server load
            const delay = attempts > 10 ? 1000 : 500;
            
            try {
                const response = await fetch(`/api/experiment/${experimentId}/result`);
                
                // Check if response is actually valid JSON with results
                if (response.ok) {
                    const data = await response.json();
                    if (data.success && data.result && data.result.summary) {
                        // Results are ready and valid
                        console.log(`✓ Results loaded successfully after ${attempts} attempts`);
                        await this.fetchAndDisplayResults();
                        await this.loadResultsList();
                        this.showTab('results');
                        this.showNotification('Results loaded successfully!', 'success');
                        return; // Success - stop polling
                    }
                }
                
                // Results not ready yet - continue polling
                if (attempts < maxAttempts) {
                    console.log(`Waiting for results... (attempt ${attempts}/${maxAttempts})`);
                    setTimeout(checkResults, delay);
                } else {
                    // Timeout after max attempts
                    console.warn(`Timeout waiting for results after ${maxAttempts} attempts`);
                    this.showNotification('Results are processing, they will appear in the list shortly', 'warning');
                    await this.loadResultsList();
                    this.showTab('results-list');
                }
            } catch (error) {
                // Network error - continue polling
                console.debug(`Error checking results (attempt ${attempts}/${maxAttempts}):`, error.message);
                
                if (attempts < maxAttempts) {
                    setTimeout(checkResults, delay);
                } else {
                    // Max attempts exceeded
                    console.error(`Failed to load results after ${maxAttempts} attempts`);
                    this.showNotification('Results may take a moment to appear', 'warning');
                    await this.loadResultsList();
                    this.showTab('results-list');
                }
            }
        };
        
        // Start polling
        checkResults();
    },
    
    // =========================================================================
    // RESULTS LIST MANAGEMENT
    // =========================================================================
    
    async loadResultsList() {
        try {
            const response = await fetch('/api/experiment/results/list');
            const result = await response.json();
            
            if (result.success) {
                this.renderResultsList(result.results || []);
            } else {
                console.error('Failed to load results list:', result.error);
            }
        } catch (error) {
            console.error('Error loading results list:', error);
        }
    },
    
    async refreshResultsList() {
        await this.loadResultsList();
    },
    
    renderResultsList(results) {
        const container = document.getElementById('results-list-container');
        if (!container) return;
        
        if (!results || results.length === 0) {
            // Show empty state
            const template = document.getElementById('template-empty-results-list');
            if (template) {
                container.innerHTML = template.innerHTML;
            } else {
                container.innerHTML = `
                    <div class="empty-state text-center py-12">
                        <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
                            <i data-lucide="inbox" class="w-8 h-8 text-gray-400"></i>
                        </div>
                        <h4 class="font-semibold text-gray-700 mb-2">No Results Yet</h4>
                        <p class="text-sm text-gray-500 mb-4">Run your first experiment to see results here</p>
                        <button onclick="ExperimentRunner.showTab('settings')" class="btn btn--primary btn--sm">
                            <i data-lucide="play" class="w-4 h-4"></i> Start Experiment
                        </button>
                    </div>
                `;
            }
        } else {
            // Render result items
            container.innerHTML = results.map(result => {
                const date = new Date(result.timestamp * 1000);
                const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                
                return `
                    <div class="card card--bordered hover:border-purple-300 hover:shadow-md transition-all" data-id="${result.id}">
                        <div class="p-4">
                            <div class="flex items-start justify-between mb-3">
                                <div class="flex-1 cursor-pointer" onclick="ExperimentRunner.viewResult('${result.id}')">
                                    <h4 class="font-semibold text-gray-800 mb-1 hover:text-purple-600">${result.id}</h4>
                                    <p class="text-xs text-gray-500">${dateStr}</p>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="badge badge--success">${result.completed.toFixed(0)}% Complete</span>
                                    <button class="btn btn--ghost btn--sm text-red-600 hover:bg-red-50"
                                        onclick="event.stopPropagation(); ExperimentRunner.confirmDeleteResult('${result.id}')"
                                        title="Delete result">
                                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                                    </button>
                                </div>
                            </div>
                            <div class="grid grid-cols-4 gap-3 text-xs cursor-pointer" onclick="ExperimentRunner.viewResult('${result.id}')">
                                <div class="text-center bg-blue-50 rounded py-2">
                                    <div class="text-blue-600 font-medium">Trials</div>
                                    <div class="font-bold text-blue-700">${result.trials}</div>
                                </div>
                                <div class="text-center bg-green-50 rounded py-2">
                                    <div class="text-green-600 font-medium">Batches</div>
                                    <div class="font-bold text-green-700">${result.batches}</div>
                                </div>
                                <div class="text-center bg-purple-50 rounded py-2">
                                    <div class="text-purple-600 font-medium">Routes</div>
                                    <div class="font-bold text-purple-700">${result.routes_per_batch}</div>
                                </div>
                                <div class="text-center bg-yellow-50 rounded py-2">
                                    <div class="text-yellow-600 font-medium">Status</div>
                                    <div class="font-bold text-yellow-700 text-xs">Complete</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    async viewResult(resultId) {
        try {
            const response = await fetch(`/api/experiment/results/${resultId}`);
            const result = await response.json();
            
            if (result.success && result.result) {
                this.currentResultId = resultId;
                this.resultsData = result.result;
                this.populateResultsDashboard(result.result);
                this.showTab('results');
            } else {
                this.showNotification('Failed to load result', 'error');
            }
        } catch (error) {
            console.error('Error loading result:', error);
            this.showNotification('Error loading result', 'error');
        }
    },
    
    confirmDeleteResult(resultId) {
        // Use modal for confirmation instead of browser confirm
        if (typeof UniversalModal === 'undefined') {
            console.error('UniversalModal not available, falling back to browser confirm');
            if (!confirm('Are you sure you want to delete this result? This action cannot be undone.')) {
                return;
            }
            this._performDeleteResult(resultId);
            return;
        }
        
        UniversalModal.showModal({
            icon: 'trash-2',
            variant: 'error',
            title: 'Delete Result?',
            body: '<p class="text-sm text-slate-700 leading-relaxed">Are you sure you want to delete this result? This action cannot be undone and all data will be permanently lost.</p>',
            buttons: {
                'Delete Result': (closeModal) => {
                    closeModal();
                    this._performDeleteResult(resultId);
                }
            },
            closeBtn: {
                'Cancel': (closeModal) => {
                    // Just close the modal
                }
            },
            backdropClose: false,
            escapeClose: true
        });
    },
    
    async _performDeleteResult(resultId) {
        try {
            const response = await fetch(`/api/experiment/results/${resultId}`, {
                method: 'DELETE'
            });
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('Result deleted successfully', 'success');
                this.refreshResultsList();
            } else {
                this.showNotification('Failed to delete result', 'error');
            }
        } catch (error) {
            console.error('Error deleting result:', error);
            this.showNotification('Error deleting result', 'error');
        }
    },
    
    async deleteResult(resultId) {
        this.confirmDeleteResult(resultId);
    },
    
    // =========================================================================
    // RESULTS DASHBOARD
    // =========================================================================
    
    async fetchAndDisplayResults() {
        if (!this.currentExperimentId) {
            console.warn('No experiment ID available for results');
            return;
        }
        
        try {
            const response = await fetch(`/api/experiment/${this.currentExperimentId}/result`);
            const result = await response.json();
            
            if (result.success && result.result) {
                this.resultsData = result.result;
                this.populateResultsDashboard(result.result);
            } else {
                console.error('Failed to fetch results:', result.error);
                this.showNotification('Failed to load results', 'error');
            }
        } catch (error) {
            console.error('Error fetching results:', error);
            this.showNotification('Error loading results', 'error');
        }
    },
    
    populateResultsDashboard(data) {
        // Update summary cards
        this.updateResultsSummary(data);
        
        // Populate each tab
        this.populateConstructionPhase(data.construction_phase || []);
        this.populateDynamicUpdates(data.dynamic_updates || []);
        this.populateQueryPerformance(data.query_performance || []);
        this.populateRouteSimilarity(data.route_similarity || []);
        
        // Populate additional similarity metrics
        this.populateSimilarityExtra(data.similarity_extra || {});
        
        // Populate graphs
        this.populateGraphs(data.graph_data || {});
        
        // Initialize result tab navigation
        this.initResultTabNavigation();
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    updateResultsSummary(data) {
        const trialsEl = document.getElementById('result-total-trials');
        const batchesEl = document.getElementById('result-total-batches');
        const routesPerBatchEl = document.getElementById('result-routes-per-batch');
        const avgMemoryDhlEl = document.getElementById('result-avg-memory-dhl');
        const avgMemoryHc2lEl = document.getElementById('result-avg-memory-hc2l');
        
        if (trialsEl) trialsEl.textContent = data.total_trials || 3;
        if (batchesEl) batchesEl.textContent = data.total_batches || 3;
        if (routesPerBatchEl) routesPerBatchEl.textContent = data.routes_per_batch || 1000;
        
        // Display average memory usage in the summary card
        const summary = data.summary || {};
        if (avgMemoryDhlEl) avgMemoryDhlEl.textContent = summary.avg_memory_dhl_mb?.toFixed(1) || '0';
        if (avgMemoryHc2lEl) avgMemoryHc2lEl.textContent = summary.avg_memory_hc2l_mb?.toFixed(1) || '0';
        
        // Remove the old separate memory summary display since it's now in the grid
        const memoryContainer = document.getElementById('result-memory-summary');
        if (memoryContainer) {
            memoryContainer.innerHTML = '';
        }
    },
    
    initResultTabNavigation() {
        // Result tabs now handled by radio input onchange handlers in HTML
    },
    
    showResultTab(tabId) {
        // Hide all result tabs
        document.querySelectorAll('[data-result-tab-content]').forEach(tab => {
            tab.classList.add('hidden');
        });
        
        // Show selected tab
        const selectedTab = document.getElementById(`result-tab-${tabId}`);
        if (selectedTab) {
            selectedTab.classList.remove('hidden');
        }
        
        // Update radio button state
        const radioBtn = document.querySelector(`input[name="result-main-tab"][value="${tabId}"]`);
        if (radioBtn) {
            radioBtn.checked = true;
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    
    populateConstructionPhase(data) {
        const tbody = document.getElementById('result-construction-tbody');
        if (!tbody) return;
        
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-gray-500 py-4">No construction data available</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.map(row => `
            <tr class="hover:bg-gray-50">
                <td class="p-2 text-gray-700">${row.trial || '--'}</td>
                <td class="p-2">
                    <span class="px-2 py-1 rounded text-xs font-medium ${row.algorithm === 'DHL' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}">
                        ${row.algorithm || '--'}
                    </span>
                </td>
                <td class="p-2 text-right font-mono">${this.formatNumber(row.initial_construction_time_ms, 3)} ms</td>
                <td class="p-2 text-right font-mono">${this.formatNumber(row.initial_label_size_mb, 5)} MB</td>
            </tr>
        `).join('');
    },
    
    populateDynamicUpdates(data) {
        const container = document.getElementById('result-updates-container');
        if (!container) return;
        
        if (!data || data.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 py-4">No dynamic update data available</p>';
            return;
        }
        
        // Group by trial
        const groupedByTrial = {};
        const averages = [];
        
        data.forEach(row => {
            // Check if this is an average row
            if (row.trial === 'Average' || row.trial === 'Overall' || row.batch === 'Average') {
                averages.push(row);
            } else {
                const trial = row.trial || 1;
                if (!groupedByTrial[trial]) {
                    groupedByTrial[trial] = [];
                }
                groupedByTrial[trial].push(row);
            }
        });
        
        let html = '';
        
        // Render trial data
        html += Object.entries(groupedByTrial).map(([trial, batches]) => `
            <div class="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div class="bg-purple-50 px-3 py-2 border-b border-gray-200">
                    <span class="font-semibold text-purple-700">Trial ${trial}</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-xs">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="text-left p-2">Batch</th>
                                <th class="text-left p-2">Algorithm</th>
                                <th class="text-right p-2">Disruption Level</th>
                                <th class="text-right p-2">Lazy Update (ms)</th>
                                <th class="text-right p-2">Threshold Rebuild (ms)</th>
                                <th class="text-right p-2">Peak Label (MB)</th>
                                <th class="text-right p-2">% Size Change</th>
                                <th class="text-right p-2">Query Avg (ms)</th>
                                <th class="text-right p-2">Query Min (ms)</th>
                                <th class="text-right p-2">Query Max (ms)</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-100">
                            ${batches.map(batch => `
                                <tr class="hover:bg-gray-50">
                                    <td class="p-2">${batch.batch || '--'}</td>
                                    <td class="p-2">
                                        <span class="px-1 py-0.5 rounded text-xs ${batch.algorithm === 'DHL' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}">
                                            ${batch.algorithm || '--'}
                                        </span>
                                    </td>
                                    <td class="p-2 text-right font-mono">${batch.disruption_level !== '-' ? this.formatNumber(batch.disruption_level * 100, 1) + '%' : '-'}</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.lazy_update_time_ms, 3)}</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.threshold_rebuild_time_ms, 3)}</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.peak_label_size_mb, 5)}</td>
                                    <td class="p-2 text-right font-mono ${batch.label_size_change_pct > 0 ? 'text-red-600' : 'text-green-600'}">
                                        ${batch.label_size_change_pct >= 0 ? '+' : ''}${this.formatNumber(batch.label_size_change_pct, 1)}%
                                    </td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.query_avg_ms, 3)}</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.query_min_ms, 3)}</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.query_max_ms, 3)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `).join('');
        
        // Render averages section
        if (averages.length > 0) {
            html += `
                <div class="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border-2 border-purple-300 overflow-hidden mt-4">
                    <div class="bg-gradient-to-r from-purple-600 to-indigo-600 px-3 py-2 text-white">
                        <span class="font-semibold">📊 Averages</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-xs">
                            <thead class="bg-purple-100">
                                <tr>
                                    <th class="text-left p-2">Scope</th>
                                    <th class="text-left p-2">Trial</th>
                                    <th class="text-left p-2">Batch</th>
                                    <th class="text-left p-2">Algorithm</th>
                                    <th class="text-right p-2">Lazy Update (ms)</th>
                                    <th class="text-right p-2">Threshold Rebuild (ms)</th>
                                    <th class="text-right p-2">Peak Label (MB)</th>
                                    <th class="text-right p-2">% Size Change</th>
                                    <th class="text-right p-2">Query Avg (ms)</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-purple-200 bg-white">
                                ${averages.map(avg => {
                                    let scope = 'Per-Batch';
                                    if (avg.trial === 'Overall') scope = 'Overall';
                                    else if (avg.batch === 'Average') scope = 'Per-Trial';
                                    
                                    return `
                                        <tr class="hover:bg-purple-50 font-medium">
                                            <td class="p-2 text-purple-700">${scope}</td>
                                            <td class="p-2">${avg.trial || '-'}</td>
                                            <td class="p-2">${avg.batch || '-'}</td>
                                            <td class="p-2">
                                                <span class="px-1 py-0.5 rounded text-xs ${avg.algorithm === 'DHL' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}">
                                                    ${avg.algorithm || '--'}
                                                </span>
                                            </td>
                                            <td class="p-2 text-right font-mono text-purple-700">${this.formatNumber(avg.lazy_update_time_ms, 3)}</td>
                                            <td class="p-2 text-right font-mono text-purple-700">${this.formatNumber(avg.threshold_rebuild_time_ms, 3)}</td>
                                            <td class="p-2 text-right font-mono text-purple-700">${this.formatNumber(avg.peak_label_size_mb, 5)}</td>
                                            <td class="p-2 text-right font-mono text-purple-700">
                                                ${avg.label_size_change_pct >= 0 ? '+' : ''}${this.formatNumber(avg.label_size_change_pct, 1)}%
                                            </td>
                                            <td class="p-2 text-right font-mono text-purple-700">${this.formatNumber(avg.query_avg_ms, 3)}</td>
                                        </tr>
                                    `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }
        
        container.innerHTML = html;
    },
    
    populateQueryPerformance(data) {
        const tbody = document.getElementById('result-performance-tbody');
        if (!tbody) return;
        
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-gray-500 py-4">No performance data available</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.map(row => {
            const improvement = row.improvement_pct || 0;
            const improvementClass = improvement > 0 ? 'text-green-600' : (improvement < 0 ? 'text-red-600' : 'text-gray-600');
            const improvementIcon = improvement > 0 ? '↓' : (improvement < 0 ? '↑' : '−');
            
            return `
                <tr class="hover:bg-gray-50">
                    <td class="p-2 font-medium text-gray-700">${row.metric || '--'}</td>
                    <td class="p-2 text-right font-mono text-blue-700">${this.formatMetricValue(row.dhl_value, row.unit)}</td>
                    <td class="p-2 text-right font-mono text-green-700">${this.formatMetricValue(row.dhc2l_value, row.unit)}</td>
                    <td class="p-2 text-right font-mono ${improvementClass}">
                        ${improvementIcon} ${Math.abs(improvement).toFixed(1)}%
                    </td>
                </tr>
            `;
        }).join('');
    },
    
    populateRouteSimilarity(data) {
        const tbody = document.getElementById('result-similarity-tbody');
        if (!tbody) return;
        
        // Store full data for pagination
        this.similarityData = data || [];
        this.similarityDisplayedCount = 0;
        
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center text-gray-500 py-4">No similarity data available</td></tr>';
            this.updateLoadMoreButton(false);
            return;
        }
        
        // Clear table and load first page
        tbody.innerHTML = '';
        this.loadMoreSimilarityData();
    },
    
    loadMoreSimilarityData() {
        const tbody = document.getElementById('result-similarity-tbody');
        if (!tbody) return;
        
        const startIdx = this.similarityDisplayedCount;
        const endIdx = Math.min(startIdx + this.similarityPageSize, this.similarityData.length);
        
        for (let i = startIdx; i < endIdx; i++) {
            const row = this.similarityData[i];
            const fdRating = this.getFrechetRating(row.frechet_distance_m);
            const ttdRating = this.getTravelTimeDeviationRating(row.time_deviation_pct);
            
            // Parse od_pair if it exists (format: "source_node → target_node")
            let sourceNode = '--';
            let targetNode = '--';
            if (row.od_pair) {
                const parts = row.od_pair.split('→').map(p => p.trim());
                if (parts.length === 2) {
                    sourceNode = parts[0];
                    targetNode = parts[1];
                }
            }
            
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-gray-50';
            tr.innerHTML = `
                <td class="p-2 font-mono text-xs text-gray-600">${row.route_idx || i + 1}</td>
                <td class="p-2 font-mono text-xs">
                    <span class="text-blue-600">${sourceNode}</span>
                    <span class="text-gray-400 mx-1">→</span>
                    <span class="text-green-600">${targetNode}</span>
                </td>
                <td class="p-2 text-xs">
                    <span class="text-gray-700">${row.start_road_hc2l || '--'}</span>
                </td>
                <td class="p-2 text-xs">
                    <span class="text-gray-700">${row.end_road_hc2l || '--'}</span>
                </td>
                <td class="p-2 text-right font-mono text-xs">
                    <div class="flex flex-col">
                        <span class="text-gray-700">${this.formatNumber(row.distance_km_hc2l, 2)}</span>
                        <span class="text-blue-600">${this.formatNumber(row.distance_km_here, 2)}</span>
                    </div>
                </td>
                <td class="p-2 text-right font-mono text-xs">
                    <div class="flex flex-col">
                        <span class="text-gray-700">${this.formatNumber(row.travel_time_min_hc2l, 1)}</span>
                        <span class="text-blue-600">${this.formatNumber(row.travel_time_min_here, 1)}</span>
                    </div>
                </td>
                <td class="p-2 text-right font-mono text-xs">
                    <div class="flex flex-col">
                        <span class="text-gray-700">${this.formatNumber(row.query_time_ms_hc2l, 1)}</span>
                        <span class="text-blue-600">${this.formatNumber(row.query_time_ms_here, 0)}</span>
                    </div>
                </td>
                <td class="p-2 text-right font-mono">${this.formatNumber(row.frechet_distance_m, 0)}</td>
                <td class="p-2 text-center">
                    <span class="px-2 py-1 rounded text-xs font-medium ${fdRating.class}">${fdRating.label}</span>
                </td>
                <td class="p-2 text-right font-mono">${this.formatNumber(row.time_deviation_pct, 1)}%</td>
                <td class="p-2 text-center">
                    <span class="px-2 py-1 rounded text-xs font-medium ${ttdRating.class}">${ttdRating.label}</span>
                </td>
            `;
            tbody.appendChild(tr);
        }
        
        this.similarityDisplayedCount = endIdx;
        this.updateLoadMoreButton(endIdx < this.similarityData.length);
    },
    
    updateLoadMoreButton(show) {
        const loadMoreDiv = document.getElementById('similarity-load-more');
        if (loadMoreDiv) {
            loadMoreDiv.classList.toggle('hidden', !show);
        }
    },
    
    updateHereComparisonProgress(progress) {
        const progressDiv = document.getElementById('here-comparison-progress');
        const statusBadge = document.getElementById('similarity-status-badge');
        
        // Also update running tab display
        const runningProgressDiv = document.getElementById('running-here-comparison-progress');
        const runningStatusBadge = document.getElementById('running-here-status-badge');
        
        if (!progress) return;
        
        this.hereComparisonProgress = progress;
        
        // Update status badge (results tab)
        if (statusBadge) {
            if (progress.status === 'running') {
                statusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700';
                statusBadge.innerHTML = '<i data-lucide="loader-2" class="w-3 h-3 inline mr-1 animate-spin"></i>Running';
            } else if (progress.status === 'completed') {
                statusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700';
                statusBadge.innerHTML = '<i data-lucide="check" class="w-3 h-3 inline mr-1"></i>Complete';
            } else if (progress.status === 'error') {
                statusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-700';
                statusBadge.innerHTML = '<i data-lucide="alert-circle" class="w-3 h-3 inline mr-1"></i>Error';
            } else {
                statusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600';
                statusBadge.innerHTML = '<i data-lucide="clock" class="w-3 h-3 inline mr-1"></i>Waiting';
            }
            // Refresh lucide icons
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        
        // Update running tab status badge
        if (runningStatusBadge) {
            if (progress.status === 'running') {
                runningStatusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700';
                runningStatusBadge.innerHTML = '<i data-lucide="loader-2" class="w-3 h-3 inline mr-1 animate-spin"></i>Running';
            } else if (progress.status === 'completed') {
                runningStatusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700';
                runningStatusBadge.innerHTML = '<i data-lucide="check" class="w-3 h-3 inline mr-1"></i>Complete';
            } else if (progress.status === 'error') {
                runningStatusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-700';
                runningStatusBadge.innerHTML = '<i data-lucide="alert-circle" class="w-3 h-3 inline mr-1"></i>Error';
            } else {
                runningStatusBadge.className = 'px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600';
                runningStatusBadge.innerHTML = '<i data-lucide="clock" class="w-3 h-3 inline mr-1"></i>Waiting';
            }
            // Refresh lucide icons
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        
        // Show/hide running tab progress section
        if (runningProgressDiv) {
            if (progress.status === 'running' || progress.status === 'completed') {
                runningProgressDiv.classList.remove('hidden');
            } else {
                runningProgressDiv.classList.add('hidden');
            }
        }
        
        // Update progress bar (results tab)
        if (progressDiv) {
            if (progress.status === 'running') {
                progressDiv.classList.remove('hidden');
                
                const progressBar = document.getElementById('here-progress-bar');
                const progressText = document.getElementById('here-progress-text');
                const progressPct = document.getElementById('here-progress-pct');
                const progressEta = document.getElementById('here-progress-eta');
                
                const pct = progress.total > 0 ? (progress.completed / progress.total * 100) : 0;
                
                if (progressBar) progressBar.style.width = `${pct}%`;
                if (progressText) progressText.textContent = `${progress.completed} / ${progress.total}`;
                if (progressPct) progressPct.textContent = `${pct.toFixed(1)}%`;
                if (progressEta) progressEta.textContent = progress.eta ? `ETA: ${progress.eta}` : 'ETA: --';
            } else if (progress.status === 'completed') {
                progressDiv.classList.add('hidden');
            } else {
                progressDiv.classList.add('hidden');
            }
        }
        
        // Update running tab progress bar
        if (runningProgressDiv) {
            const runningProgressBar = document.getElementById('running-here-progress-bar');
            const runningProgressText = document.getElementById('running-here-progress-text');
            const runningProgressPct = document.getElementById('running-here-progress-pct');
            const runningProgressEta = document.getElementById('running-here-progress-eta');
            
            const pct = progress.total > 0 ? (progress.completed / progress.total * 100) : 0;
            
            if (runningProgressBar) runningProgressBar.style.width = `${pct}%`;
            if (runningProgressText) runningProgressText.textContent = `${progress.completed} / ${progress.total}`;
            if (runningProgressPct) runningProgressPct.textContent = `${pct.toFixed(1)}%`;
            if (runningProgressEta) runningProgressEta.textContent = progress.eta ? `ETA: ${progress.eta}` : 'ETA: Calculating...';
            
            // Update error count
            const errorCountEl = document.getElementById('running-here-error-count');
            if (errorCountEl) errorCountEl.textContent = progress.errors || 0;
            
            // Update last route info and compute live metrics from the full results data
            if (progress.current_route !== undefined) {
                const lastRouteEl = document.getElementById('running-here-last-route-idx');
                if (lastRouteEl) lastRouteEl.textContent = progress.current_route;
            }
            
            // Compute and display live metrics from resultsData if available
            this.updateHereComparisonRunningMetrics();
        }
    },
    
    updateHereComparisonRunningMetrics() {
        /**
         * Compute and display live metrics from progress data
         * Backend calculates running averages and sends them in progress updates
         */
        if (!this.hereComparisonProgress) return;
        
        const progress = this.hereComparisonProgress;
        
        // Update HC2L metrics from progress
        if (progress.hc2l_avg_query_ms !== undefined) {
            const hc2lQueryEl = document.getElementById('running-here-hc2l-avg-query');
            if (hc2lQueryEl) hc2lQueryEl.textContent = progress.hc2l_avg_query_ms.toFixed(1) + ' ms';
        }
        
        if (progress.hc2l_avg_distance_km !== undefined) {
            const hc2lDistanceEl = document.getElementById('running-here-hc2l-avg-distance');
            if (hc2lDistanceEl) hc2lDistanceEl.textContent = progress.hc2l_avg_distance_km.toFixed(2) + ' km';
        }
        
        if (progress.hc2l_avg_time_min !== undefined) {
            const hc2lTimeEl = document.getElementById('running-here-hc2l-avg-time');
            if (hc2lTimeEl) hc2lTimeEl.textContent = progress.hc2l_avg_time_min.toFixed(2) + ' min';
        }
        
        // Update HERE metrics from progress
        if (progress.here_avg_query_ms !== undefined) {
            const hereQueryEl = document.getElementById('running-here-here-avg-query');
            if (hereQueryEl) hereQueryEl.textContent = progress.here_avg_query_ms.toFixed(1) + ' ms';
        }
        
        if (progress.here_avg_distance_km !== undefined) {
            const hereDistanceEl = document.getElementById('running-here-here-avg-distance');
            if (hereDistanceEl) hereDistanceEl.textContent = progress.here_avg_distance_km.toFixed(2) + ' km';
        }
        
        if (progress.here_avg_time_min !== undefined) {
            const hereTimeEl = document.getElementById('running-here-here-avg-time');
            if (hereTimeEl) hereTimeEl.textContent = progress.here_avg_time_min.toFixed(2) + ' min';
        }
        
        // Update quality metrics from progress
        if (progress.avg_frechet_m !== undefined) {
            const avgFrechetEl = document.getElementById('running-here-avg-frechet');
            if (avgFrechetEl) avgFrechetEl.textContent = progress.avg_frechet_m.toFixed(0);
        }
        
        if (progress.avg_time_deviation_pct !== undefined) {
            const avgTimeDevEl = document.getElementById('running-here-avg-time-dev');
            if (avgTimeDevEl) avgTimeDevEl.textContent = progress.avg_time_deviation_pct.toFixed(2) + '%';
        }
        
        // Update last route frechet distance
        if (progress.last_frechet_m !== undefined) {
            const lastFrechetEl = document.getElementById('running-here-last-frechet');
            if (lastFrechetEl) lastFrechetEl.textContent = progress.last_frechet_m.toFixed(0) + ' m';
        }
    },
    
    getFrechetRating(distance) {
        if (distance < 200) {
            return { label: 'Excellent', class: 'bg-green-100 text-green-700' };
        } else if (distance <= 400) {
            return { label: 'Good', class: 'bg-yellow-100 text-yellow-700' };
        } else {
            return { label: 'Fair', class: 'bg-orange-100 text-orange-700' };
        }
    },
    
    getTravelTimeDeviationRating(deviation) {
        if (deviation < 5) {
            return { label: 'Excellent', class: 'bg-green-100 text-green-700' };
        } else if (deviation <= 10) {
            return { label: 'Good', class: 'bg-yellow-100 text-yellow-700' };
        } else {
            return { label: 'Fair', class: 'bg-orange-100 text-orange-700' };
        }
    },
    
    populateSimilarityExtra(data) {
        // Update HERE vs HC2L comparison summary metrics
        const avgFrechetEl = document.getElementById('similarity-avg-frechet');
        const avgTimeDevEl = document.getElementById('similarity-avg-time-deviation');
        const avgDistDevEl = document.getElementById('similarity-avg-distance-deviation');
        const routesComparedEl = document.getElementById('similarity-routes-compared');
        const hereErrorsEl = document.getElementById('similarity-here-errors');
        
        if (avgFrechetEl) avgFrechetEl.textContent = data.avg_frechet_distance_m ? `${data.avg_frechet_distance_m.toFixed(0)}m` : '--';
        if (avgTimeDevEl) avgTimeDevEl.textContent = data.avg_time_deviation_pct ? `${data.avg_time_deviation_pct.toFixed(1)}%` : '--';
        if (avgDistDevEl) avgDistDevEl.textContent = data.avg_distance_deviation_pct ? `${data.avg_distance_deviation_pct.toFixed(1)}%` : '--';
        if (routesComparedEl) routesComparedEl.textContent = data.total_routes_compared || '0';
        if (hereErrorsEl) hereErrorsEl.textContent = data.errors_count || '0';
    },
    
    // =========================================================================
    // GRAPH RENDERING
    // =========================================================================
    
    populateGraphs(graphData) {
        if (!graphData || Object.keys(graphData).length === 0) {
            console.warn('No graph data available');
            return;
        }
        
        // Clean up existing charts
        Object.values(this.chartInstances).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.chartInstances = {};
        
        // Render each graph
        this.renderQueryTimeSeriesChart(graphData.time_series);
        this.renderUpdateTimeSeriesChart(graphData.time_series);
        this.renderAverageQueryTimeChart(graphData.algorithm_comparison);
        this.renderAverageLabelSizeChart(graphData.algorithm_comparison);
        this.renderPerTrialBreakdownChart(graphData.per_trial);
        this.renderOverallComparisonChart(graphData.algorithm_comparison);
        this.renderRebuildAnalysisChart(graphData.rebuild_analysis);
        this.renderLabelSizeTrendChart(graphData.label_size_trend);
    },
    
    renderQueryTimeSeriesChart(timeSeriesData) {
        if (!timeSeriesData) return;
        
        const ctx = document.getElementById('chart-query-time-series');
        if (!ctx) return;
        
        const dhlData = timeSeriesData.DHL || {};
        const hc2lData = timeSeriesData.HC2L || {};
        
        this.chartInstances['query-time-series'] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dhlData.batch_labels || [],
                datasets: [
                    {
                        label: 'DHL Query Time',
                        data: dhlData.query_times || [],
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'HC2L Query Time',
                        data: hc2lData.query_times || [],
                        borderColor: '#10B981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Query Time Performance Over Batches'
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Time (ms)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Trial-Batch'
                        }
                    }
                }
            }
        });
    },
    
    renderUpdateTimeSeriesChart(timeSeriesData) {
        if (!timeSeriesData) return;
        
        const ctx = document.getElementById('chart-update-time-series');
        if (!ctx) return;
        
        const dhlData = timeSeriesData.DHL || {};
        const hc2lData = timeSeriesData.HC2L || {};
        
        this.chartInstances['update-time-series'] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dhlData.batch_labels || [],
                datasets: [
                    {
                        label: 'DHL Update Time',
                        data: dhlData.update_times || [],
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'HC2L Update Time',
                        data: hc2lData.update_times || [],
                        borderColor: '#10B981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Lazy Update Time Over Batches'
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Time (ms)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Trial-Batch'
                        }
                    }
                }
            }
        });
    },
    
    renderAverageQueryTimeChart(comparisonData) {
        if (!comparisonData) return;
        
        const ctx = document.getElementById('chart-avg-query-time');
        if (!ctx) return;
        
        const avgQueryTime = comparisonData.avg_query_time || {};
        
        this.chartInstances['avg-query-time'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['DHL', 'HC2L'],
                datasets: [{
                    label: 'Average Query Time (ms)',
                    data: [avgQueryTime.DHL || 0, avgQueryTime.HC2L || 0],
                    backgroundColor: ['rgba(59, 130, 246, 0.7)', 'rgba(16, 185, 129, 0.7)'],
                    borderColor: ['#3B82F6', '#10B981'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Average Query Time Comparison'
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Time (ms)'
                        }
                    }
                }
            }
        });
    },
    
    renderAverageLabelSizeChart(comparisonData) {
        if (!comparisonData) return;
        
        const ctx = document.getElementById('chart-avg-label-size');
        if (!ctx) return;
        
        const avgLabelSize = comparisonData.avg_label_size || {};
        
        this.chartInstances['avg-label-size'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['DHL', 'HC2L'],
                datasets: [{
                    label: 'Average Label Size (MB)',
                    data: [avgLabelSize.DHL || 0, avgLabelSize.HC2L || 0],
                    backgroundColor: ['rgba(139, 92, 246, 0.7)', 'rgba(251, 191, 36, 0.7)'],
                    borderColor: ['#8B5CF6', '#FBBF24'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Average Label Size Comparison'
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Size (MB)'
                        }
                    }
                }
            }
        });
    },
    
    renderPerTrialBreakdownChart(perTrialData) {
        if (!perTrialData) return;
        
        const ctx = document.getElementById('chart-per-trial-breakdown');
        if (!ctx) return;
        
        this.chartInstances['per-trial-breakdown'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: perTrialData.trial_labels || [],
                datasets: [
                    {
                        label: 'DHL Query Time',
                        data: perTrialData.DHL_query || [],
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: '#3B82F6',
                        borderWidth: 1
                    },
                    {
                        label: 'HC2L Query Time',
                        data: perTrialData.HC2L_query || [],
                        backgroundColor: 'rgba(16, 185, 129, 0.7)',
                        borderColor: '#10B981',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Query Time by Trial'
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Time (ms)'
                        }
                    }
                }
            }
        });
    },
    
    renderOverallComparisonChart(comparisonData) {
        if (!comparisonData) return;
        
        const ctx = document.getElementById('chart-overall-comparison');
        if (!ctx) return;
        
        const avgQueryTime = comparisonData.avg_query_time || {};
        const avgLabelSize = comparisonData.avg_label_size || {};
        
        this.chartInstances['overall-comparison'] = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Query Time', 'Label Size Efficiency', 'Overall Performance'],
                datasets: [
                    {
                        label: 'DHL',
                        data: [
                            avgQueryTime.DHL ? 100 - (avgQueryTime.DHL / 10) : 0,
                            avgLabelSize.DHL ? 100 - (avgLabelSize.DHL * 10) : 0,
                            50
                        ],
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        borderColor: '#3B82F6',
                        pointBackgroundColor: '#3B82F6'
                    },
                    {
                        label: 'HC2L',
                        data: [
                            avgQueryTime.HC2L ? 100 - (avgQueryTime.HC2L / 10) : 0,
                            avgLabelSize.HC2L ? 100 - (avgLabelSize.HC2L * 10) : 0,
                            50
                        ],
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        borderColor: '#10B981',
                        pointBackgroundColor: '#10B981'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Overall Algorithm Comparison (Higher = Better)'
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    },
    
    renderRebuildAnalysisChart(rebuildData) {
        if (!rebuildData) return;
        
        const ctx = document.getElementById('chart-rebuild-time-analysis');
        if (!ctx) return;
        
        const labels = rebuildData.DHL_rebuild_times.map((_, i) => `Batch ${Math.floor(i / 3) + 1}.${(i % 3) + 1}`);
        
        this.chartInstances['rebuild-analysis'] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'DHL Rebuild Time',
                        data: rebuildData.DHL_rebuild_times || [],
                        borderColor: '#EF4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'HC2L Rebuild Time',
                        data: rebuildData.HC2L_rebuild_times || [],
                        borderColor: '#F59E0B',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Threshold Rebuild Time Analysis'
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Time (ms)'
                        }
                    }
                }
            }
        });
    },
    
    renderLabelSizeTrendChart(labelSizeData) {
        if (!labelSizeData) return;
        
        const ctx = document.getElementById('chart-label-size-trend');
        if (!ctx) return;
        
        this.chartInstances['label-size-trend'] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labelSizeData.batch_labels || [],
                datasets: [
                    {
                        label: 'DHL Label Size',
                        data: labelSizeData.DHL_labels || [],
                        borderColor: '#8B5CF6',
                        backgroundColor: 'rgba(139, 92, 246, 0.2)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'HC2L Label Size',
                        data: labelSizeData.HC2L_labels || [],
                        borderColor: '#EC4899',
                        backgroundColor: 'rgba(236, 72, 153, 0.2)',
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Label Size Evolution Over Time'
                    },
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Size (MB)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Trial-Batch'
                        }
                    }
                }
            }
        });
    },
    
    formatNumber(value, decimals = 2) {
        if (value === null || value === undefined || isNaN(value)) {
            return '--';
        }
        return Number(value).toFixed(decimals);
    },
    
    formatMetricValue(value, unit) {
        if (value === null || value === undefined) return '--';
        
        const formatted = this.formatNumber(value, unit === 'ms' ? 3 : 2);
        return unit ? `${formatted} ${unit}` : formatted;
    },
    
    // =========================================================================
    // EXPORT FUNCTIONALITY
    // =========================================================================
    
    async exportResults(format) {
        if (!this.currentExperimentId) {
            this.showNotification('No experiment results to export', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/api/experiment/${this.currentExperimentId}/result`);
            const result = await response.json();
            
            if (!result.success || !result.result) {
                this.showNotification('No results available for export', 'warning');
                return;
            }
            
            const data = result.result;
            
            if (format === 'json') {
                this.downloadFile(
                    JSON.stringify(data, null, 2),
                    `experiment_${this.currentExperimentId}_results.json`,
                    'application/json'
                );
            } else if (format === 'csv') {
                // Export all tabs as separate CSV files in a zip or combined
                this.exportAllCSV(data);
            }
            
            this.showNotification(`Results exported as ${format.toUpperCase()}`, 'success');
        } catch (error) {
            console.error('Error exporting results:', error);
            this.showNotification('Error exporting results', 'error');
        }
    },
    
    exportTab(tabName) {
        if (!this.resultsData) {
            this.showNotification('No results data available', 'warning');
            return;
        }
        
        let data;
        let filename;
        
        switch (tabName) {
            case 'construction':
                data = this.resultsData.construction_phase || [];
                filename = `appendix_1_1_construction_phase_${this.currentExperimentId}.csv`;
                break;
            case 'updates':
                data = this.resultsData.dynamic_updates || [];
                filename = `appendix_1_2_dynamic_updates_${this.currentExperimentId}.csv`;
                break;
            case 'performance':
                data = this.resultsData.query_performance || [];
                filename = `appendix_1_3_query_performance_${this.currentExperimentId}.csv`;
                break;
            case 'similarity':
                data = this.resultsData.route_similarity || [];
                filename = `appendix_1_4_route_similarity_${this.currentExperimentId}.csv`;
                break;
            default:
                this.showNotification('Unknown tab', 'error');
                return;
        }
        
        if (!data || data.length === 0) {
            this.showNotification('No data available for this tab', 'warning');
            return;
        }
        
        const csv = this.convertToCSV(data);
        this.downloadFile(csv, filename, 'text/csv');
        this.showNotification(`Exported ${tabName} data to CSV`, 'success');
    },
    
    exportAllCSV(data) {
        // Export each section
        if (data.construction_phase && data.construction_phase.length > 0) {
            this.downloadFile(
                this.convertToCSV(data.construction_phase),
                `appendix_1_1_construction_phase_${this.currentExperimentId}.csv`,
                'text/csv'
            );
        }
        
        if (data.dynamic_updates && data.dynamic_updates.length > 0) {
            this.downloadFile(
                this.convertToCSV(data.dynamic_updates),
                `appendix_1_2_dynamic_updates_${this.currentExperimentId}.csv`,
                'text/csv'
            );
        }
        
        if (data.query_performance && data.query_performance.length > 0) {
            this.downloadFile(
                this.convertToCSV(data.query_performance),
                `appendix_1_3_query_performance_${this.currentExperimentId}.csv`,
                'text/csv'
            );
        }
        
        if (data.route_similarity && data.route_similarity.length > 0) {
            this.downloadFile(
                this.convertToCSV(data.route_similarity),
                `appendix_1_4_route_similarity_${this.currentExperimentId}.csv`,
                'text/csv'
            );
        }
    },
    
    convertToCSV(data) {
        if (!data || data.length === 0) return '';
        
        const headers = Object.keys(data[0]);
        const rows = data.map(row => 
            headers.map(header => {
                let value = row[header];
                if (value === null || value === undefined) value = '';
                // Escape quotes and wrap in quotes if contains comma
                if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                    value = `"${value.replace(/"/g, '""')}"`;
                }
                return value;
            }).join(',')
        );
        
        return [headers.join(','), ...rows].join('\n');
    },
    
    downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
    
    handleExperimentError(errorMessage) {
        this.isRunning = false;
        this.disconnectWebSocket();
        this.showNotification(`Experiment error: ${errorMessage}`, 'error');
    },
    
    showNotification(message, type = 'info') {
        // Use existing toast system if available
        if (typeof showUpdateToast === 'function') {
            showUpdateToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    ExperimentRunner.init();
});

// Export for global access
window.ExperimentRunner = ExperimentRunner;
