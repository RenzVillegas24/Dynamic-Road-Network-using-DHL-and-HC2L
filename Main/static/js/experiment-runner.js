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
    
    // =========================================================================
    // INITIALIZATION
    // =========================================================================
    
    init() {
        console.log('🧪 Initializing Experiment Runner');
        
        // Load presets
        this.loadPresets();
        
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
        
        // Tab navigation
        document.querySelectorAll('[data-experiment-tab]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabId = e.currentTarget.dataset.experimentTab;
                this.showTab(tabId);
            });
        });
        
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
        
        // Update tab button states
        document.querySelectorAll('[data-experiment-tab]').forEach(btn => {
            if (btn.dataset.experimentTab === tabId) {
                btn.classList.add('bg-purple-600', 'text-white');
                btn.classList.remove('bg-gray-200', 'text-gray-700');
            } else {
                btn.classList.remove('bg-purple-600', 'text-white');
                btn.classList.add('bg-gray-200', 'text-gray-700');
            }
        });
        
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
        
        // Show preparing status in running tab
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
    
    async togglePause() {
        if (!this.currentExperimentId) return;
        
        const endpoint = this.isPaused ? 'resume' : 'pause';
        
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
        
        if (!confirm('Are you sure you want to stop the experiment?')) {
            return;
        }
        
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
                this.showTab('results');
            }
        } catch (error) {
            console.error('Error stopping experiment:', error);
        }
    },
    
    gatherExperimentConfig() {
        // Get settings from UI
        const threadCount = document.getElementById('experiment-thread-count')?.checked ? 9 : 3;
        
        // Route mode
        const routeMode = document.querySelector('input[name="experiment-route-mode"]:checked')?.value || 'preset';
        
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
            is_preset: routeMode === 'preset',
            thread_count: threadCount,
            trials: 3,
            batches_per_trial: 3,
            routes_per_batch: 1000,
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
        
        // Update disruption display
        if (data.disruption_display) {
            this.updateDisruptionDisplay(data.disruption_display);
        }
        
        // Check for completion
        if (data.status === 'completed') {
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
            statusEl.textContent = this.formatStatus(data.status);
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
            routeCountEl.textContent = `${data.completed_routes || 0} / ${data.total_routes || 0}`;
        }
        
        // Update ETA
        const etaEl = document.getElementById('experiment-eta');
        if (etaEl) {
            etaEl.textContent = data.estimated_time_remaining || '--';
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
        
        // Route
        const routeEl = section.querySelector('[data-metric="route"]');
        if (routeEl) routeEl.textContent = lastResult.route || '--';
        
        // Algorithm
        const algoEl = section.querySelector('[data-metric="algorithm"]');
        if (algoEl) algoEl.textContent = lastResult.algorithm || '--';
        
        // Query Time
        const queryTimeEl = section.querySelector('[data-metric="query-time"]');
        if (queryTimeEl) queryTimeEl.textContent = `${(lastResult.query_time_ms || 0).toFixed(3)} ms`;
        
        // Distance
        const distanceEl = section.querySelector('[data-metric="distance"]');
        if (distanceEl) distanceEl.textContent = `${(lastResult.distance_km || 0).toFixed(2)} km`;
        
        // ETAs
        const baselineEtaEl = section.querySelector('[data-metric="baseline-eta"]');
        if (baselineEtaEl) baselineEtaEl.textContent = lastResult.baseline_eta || '--';
        
        const actualEtaEl = section.querySelector('[data-metric="actual-eta"]');
        if (actualEtaEl) actualEtaEl.textContent = lastResult.actual_eta || '--';
        
        // Time Impact
        const impactEl = section.querySelector('[data-metric="time-impact"]');
        if (impactEl) {
            const impact = lastResult.time_impact_seconds || 0;
            impactEl.textContent = `${impact >= 0 ? '+' : ''}${impact.toFixed(1)}s`;
            impactEl.className = impact > 0 ? 'text-red-500' : 'text-green-500';
        }
        
        // Label Size
        const labelEl = section.querySelector('[data-metric="label-size"]');
        if (labelEl) labelEl.textContent = lastResult.label_size || '--';
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
                        <div><span class="text-gray-500">Query Time:</span> <span data-metric="query-time" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Distance:</span> <span data-metric="distance" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Baseline ETA:</span> <span data-metric="baseline-eta" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Actual ETA:</span> <span data-metric="actual-eta" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Time Impact:</span> <span data-metric="time-impact" class="font-medium">--</span></div>
                        <div><span class="text-gray-500">Label Size:</span> <span data-metric="label-size" class="font-medium">--</span></div>
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
            'completed': 'bg-blue-100 text-blue-700',
            'error': 'bg-red-100 text-red-700',
            'stopped': 'bg-gray-100 text-gray-700',
            'not_started': 'bg-gray-100 text-gray-600'
        };
        return colorMap[status] || 'bg-gray-100 text-gray-600';
    },
    
    handleExperimentComplete() {
        this.isRunning = false;
        this.disconnectWebSocket();
        this.showNotification('Experiment completed!', 'success');
        this.showTab('results');
        
        // Clear map centering flag for next run
        this.mapCentered = false;
        
        // Fetch and display results
        this.fetchAndDisplayResults();
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
        const algorithmsEl = document.getElementById('result-algorithms');
        
        if (trialsEl) trialsEl.textContent = data.total_trials || 3;
        if (batchesEl) batchesEl.textContent = data.total_batches || 3;
        if (algorithmsEl) algorithmsEl.textContent = '2 (DHL vs DHC2L)';
    },
    
    initResultTabNavigation() {
        document.querySelectorAll('[data-result-tab]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabId = e.currentTarget.dataset.resultTab;
                this.showResultTab(tabId);
            });
        });
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
        
        // Update tab button states
        document.querySelectorAll('[data-result-tab]').forEach(btn => {
            if (btn.dataset.resultTab === tabId) {
                btn.classList.add('bg-purple-600', 'text-white');
                btn.classList.remove('bg-gray-200', 'text-gray-700');
            } else {
                btn.classList.remove('bg-purple-600', 'text-white');
                btn.classList.add('bg-gray-200', 'text-gray-700');
            }
        });
        
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
                <td class="p-2 text-right font-mono">${this.formatNumber(row.initial_label_size_mb, 2)} MB</td>
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
        data.forEach(row => {
            const trial = row.trial || 1;
            if (!groupedByTrial[trial]) {
                groupedByTrial[trial] = [];
            }
            groupedByTrial[trial].push(row);
        });
        
        container.innerHTML = Object.entries(groupedByTrial).map(([trial, batches]) => `
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
                                <th class="text-right p-2">Disruption Level (%)</th>
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
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.disruption_level * 100, 1)}%</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.lazy_update_time_ms, 3)}</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.threshold_rebuild_time_ms, 3)}</td>
                                    <td class="p-2 text-right font-mono">${this.formatNumber(batch.peak_label_size_mb, 2)}</td>
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
        
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-gray-500 py-4">No similarity data available</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.map(row => {
            const fdRating = this.getFrechetRating(row.frechet_distance_m);
            const ttdRating = this.getTravelTimeDeviationRating(row.travel_time_deviation_pct);
            
            return `
                <tr class="hover:bg-gray-50">
                    <td class="p-2 font-mono text-xs">${row.od_pair || '--'}</td>
                    <td class="p-2 text-right font-mono">${this.formatNumber(row.distance_km, 2)}</td>
                    <td class="p-2 text-right font-mono">${this.formatNumber(row.travel_time_min, 1)}</td>
                    <td class="p-2 text-right font-mono">${this.formatNumber(row.frechet_distance_m, 0)}</td>
                    <td class="p-2 text-center">
                        <span class="px-2 py-1 rounded text-xs font-medium ${fdRating.class}">${fdRating.label}</span>
                    </td>
                    <td class="p-2 text-right font-mono">${this.formatNumber(row.travel_time_deviation_pct, 1)}%</td>
                    <td class="p-2 text-center">
                        <span class="px-2 py-1 rounded text-xs font-medium ${ttdRating.class}">${ttdRating.label}</span>
                    </td>
                </tr>
            `;
        }).join('');
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
