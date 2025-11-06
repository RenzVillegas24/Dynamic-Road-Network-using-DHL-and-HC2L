/**
 * Demo Automation Module
 * Automated demo sequence for thesis defense presentation:
 * 1. Load random locations
 * 2. Calculate routes with different TAU values
 * 3. Simulate traffic flow changes
 * 4. Show auto-recalculation
 * 5. Compare algorithms with metrics
 */

// Demo configuration
const DEMO_CONFIG = {
    // Multiple preset location pairs in Quezon City for variety
    locationPairs: [
        {
            start: { name: 'Quezon Memorial Circle', lat: 14.6540, lng: 121.0490 },
            destination: { name: 'SM North EDSA', lat: 14.6563, lng: 121.0315 }
        },
        {
            start: { name: 'UP Diliman', lat: 14.6537, lng: 121.0685 },
            destination: { name: 'Trinoma Mall', lat: 14.6560, lng: 121.0324 }
        },
        {
            start: { name: 'Araneta Coliseum', lat: 14.6225, lng: 121.0501 },
            destination: { name: 'Eastwood City', lat: 14.6093, lng: 121.0776 }
        },
        {
            start: { name: 'Tomas Morato', lat: 14.6320, lng: 121.0324 },
            destination: { name: 'Ateneo de Manila', lat: 14.6386, lng: 121.0779 }
        }
    ],
    
    // TAU threshold values to compare
    tauValues: [0.1, 0.3, 0.5, 0.7, 0.9],
    
    // Traffic scenarios to simulate
    trafficScenarios: [
        { mode: 'none', description: 'No disruptions (baseline)' },
        { mode: 'both', description: 'Active traffic flow' }
    ],
    
    // Timing configuration (in milliseconds)
    timing: {
        locationSet: 1500,
        routeCalculation: 2500,
        tauComparison: 3000,
        trafficUpdate: 2000,
        metricDisplay: 2500,
        narrationDelay: 1000
    }
};

// Demo state
let demoState = {
    isRunning: false,
    currentStep: 0,
    stepTimeout: null,
    narrationEnabled: true
};

/**
 * Main demo execution function - Enhanced with traffic flow simulation
 */
async function runDemo() {
    if (demoState.isRunning) {
        showUpdateToast('Demo already running', 'warning');
        return;
    }
    
    demoState.isRunning = true;
    demoState.currentStep = 0;
    
    console.log('🎬 Starting automated demo with traffic flow simulation...');
    showUpdateToast('🎬 Starting Enhanced Demo Sequence...', 'info');
    
    try {
        // Step 1: Reset and prepare
        await demoStep1_Reset();
        
        // Step 2: Load random locations
        await demoStep2_LoadRandomLocations();
        
        // Step 3: Baseline - No traffic
        await demoStep3_BaselineRoute();
        
        // Step 4: Compare TAU threshold values (HC2L only)
        await demoStep4_CompareTauValues();
        
        // Step 5: Activate traffic flow
        await demoStep5_ActivateTraffic();
        
        // Step 6: Show route adaptation with traffic
        await demoStep6_RouteAdaptation();
        
        // Step 7: Algorithm comparison (HC2L vs DHL)
        await demoStep7_AlgorithmComparison();
        
        // Step 8: Performance metrics summary
        await demoStep8_MetricsSummary();
        
        // Step 9: Final summary
        await demoStep9_FinalSummary();
        
        showUpdateToast('✅ Demo Complete - All scenarios tested!', 'success');
        console.log('✅ Demo sequence completed successfully');
        
    } catch (error) {
        console.error('❌ Demo error:', error);
        showUpdateToast('Demo interrupted: ' + error.message, 'error');
    } finally {
        demoState.isRunning = false;
        demoState.currentStep = 0;
    }
}

/**
 * Step 1: Reset map and clear all routes
 */
async function demoStep1_Reset() {
    narrate('Step 1: Resetting map...');
    
    // Clear existing routes and disruptions
    if (typeof clearRoutes === 'function') {
        clearRoutes();
    }
    if (typeof clearDisruptionMarkers === 'function') {
        clearDisruptionMarkers();
    }
    if (typeof clearUpdateRegions === 'function') {
        clearUpdateRegions();
    }
    if (typeof clearGoogleMapsRoute === 'function') {
        clearGoogleMapsRoute();
    }
    
    // Close panels
    const adminPanel = document.getElementById('admin-panel');
    const disruptionsPanel = document.getElementById('disruptions-panel');
    if (adminPanel) adminPanel.classList.add('translate-x-full');
    if (disruptionsPanel) disruptionsPanel.classList.add('translate-x-full');
    
    await delay(DEMO_CONFIG.timing.locationSet);
}

/**
 * Step 2: Load random locations from preset pairs
 */
async function demoStep2_LoadRandomLocations() {
    narrate('Step 2: Loading random route scenario...');
    demoState.currentStep = 2;
    
    // Select random location pair
    const randomIndex = Math.floor(Math.random() * DEMO_CONFIG.locationPairs.length);
    const locationPair = DEMO_CONFIG.locationPairs[randomIndex];
    demoState.currentLocations = locationPair;
    
    const start = locationPair.start;
    const destination = locationPair.destination;
    
    showUpdateToast(`📍 Random Route: ${start.name} → ${destination.name}`, 'info');
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Set start location with OSM snapping
    if (typeof handleOSMStartLocationPin === 'function') {
        await handleOSMStartLocationPin(start.lat, start.lng);
    } else if (typeof handleStartLocationPin === 'function') {
        await handleStartLocationPin(start.lat, start.lng);
    }
    
    await delay(DEMO_CONFIG.timing.locationSet);
    
    showUpdateToast(`🎯 Destination: ${destination.name}`, 'info');
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Set destination location with OSM snapping
    if (typeof handleOSMDestLocationPin === 'function') {
        await handleOSMDestLocationPin(destination.lat, destination.lng);
    } else if (typeof handleDestLocationPin === 'function') {
        await handleDestLocationPin(destination.lat, destination.lng);
    }
    
    await delay(DEMO_CONFIG.timing.locationSet);
}

/**
 * Step 3: Calculate baseline route (no traffic)
 */
async function demoStep3_BaselineRoute() {
    narrate('Step 3: Calculating baseline route (no traffic)...');
    demoState.currentStep = 3;
    
    showUpdateToast('� Baseline: No traffic disruptions', 'info');
    
    // Select HC2L algorithm
    const hc2lRadio = document.querySelector('input[value="hc2l"]');
    if (hc2lRadio) {
        hc2lRadio.checked = true;
        hc2lRadio.dispatchEvent(new Event('change'));
    }
    
    // Set dataset to none
    const noneRadio = document.querySelector('input[value="none"]');
    if (noneRadio) {
        noneRadio.checked = true;
        noneRadio.dispatchEvent(new Event('change'));
    }
    
    // Set initial TAU value
    const thresholdInput = document.getElementById('threshold-input');
    if (thresholdInput) {
        thresholdInput.value = 0.5;
        thresholdInput.dispatchEvent(new Event('input'));
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Calculate route
    if (typeof computeRouteBasedOnSelection === 'function') {
        const result = await computeRouteBasedOnSelection();
        demoState.baselineResult = result;
    }
    
    await delay(DEMO_CONFIG.timing.routeCalculation);
}

/**
 * Step 4: Compare different TAU threshold values
 */
async function demoStep4_CompareTauValues() {
    narrate('Step 4: Comparing TAU threshold values...');
    demoState.currentStep = 4;
    
    showUpdateToast('🔬 Testing different τ thresholds...', 'info');
    demoState.tauResults = {};
    
    // Test multiple TAU values
    for (const tau of DEMO_CONFIG.tauValues) {
        const thresholdInput = document.getElementById('threshold-input');
        if (thresholdInput) {
            thresholdInput.value = tau;
            thresholdInput.dispatchEvent(new Event('input'));
        }
        
        showUpdateToast(`Testing τ = ${tau}`, 'info');
        await delay(DEMO_CONFIG.timing.narrationDelay);
        
        // Calculate route with this TAU value
        if (typeof computeRouteBasedOnSelection === 'function') {
            const result = await computeRouteBasedOnSelection();
            if (result && result.success) {
                demoState.tauResults[tau] = {
                    distance: result.metrics?.total_distance_m || 0,
                    query_time: result.metrics?.query_time_ms || 0,
                    updated_labels: result.metrics?.updated_labels || 0
                };
                console.log(`τ=${tau}: ${result.metrics?.total_distance_m}m, ${result.metrics?.query_time_ms}ms`);
            }
        }
        
        await delay(DEMO_CONFIG.timing.tauComparison);
    }
    
    // Show TAU comparison summary
    showUpdateToast(`✅ Tested ${DEMO_CONFIG.tauValues.length} TAU values`, 'success');
    await delay(DEMO_CONFIG.timing.narrationDelay);
}

/**
 * Step 5: Activate traffic flow
 */
async function demoStep5_ActivateTraffic() {
    narrate('Step 5: Activating traffic flow data...');
    demoState.currentStep = 5;
    
    showUpdateToast('� Loading real-time traffic conditions...', 'info');
    
    // Select traffic dataset mode
    const bothRadio = document.querySelector('input[value="both"]');
    if (bothRadio) {
        bothRadio.checked = true;
        bothRadio.dispatchEvent(new Event('change'));
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Fetch traffic data
    if (typeof loadActiveDisruptionsForAlgorithm === 'function') {
        await loadActiveDisruptionsForAlgorithm('HC2L');
    }
    
    showUpdateToast('✅ Traffic data loaded', 'success');
    await delay(DEMO_CONFIG.timing.trafficUpdate);
}

/**
 * Step 6: Show route adaptation with traffic
 */
async function demoStep6_RouteAdaptation() {
    narrate('Step 6: Demonstrating route adaptation to traffic...');
    demoState.currentStep = 6;
    
    showUpdateToast('🔄 Recalculating route with traffic...', 'info');
    
    // Set optimal TAU value
    const thresholdInput = document.getElementById('threshold-input');
    if (thresholdInput) {
        thresholdInput.value = 0.5;
        thresholdInput.dispatchEvent(new Event('input'));
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Calculate route with traffic
    if (typeof computeRouteBasedOnSelection === 'function') {
        const result = await computeRouteBasedOnSelection();
        demoState.trafficResult = result;
    }
    
    await delay(DEMO_CONFIG.timing.routeCalculation);
    
    // Show update regions if available
    showUpdateToast('🟢 Showing lazy update regions', 'info');
    await delay(DEMO_CONFIG.timing.metricDisplay);
}

/**
 * Step 7: Algorithm comparison (HC2L vs DHL)
 */
async function demoStep7_AlgorithmComparison() {
    narrate('Step 7: Comparing HC2L and DHL algorithms...');
    demoState.currentStep = 7;
    
    showUpdateToast('📊 Algorithm Comparison Mode', 'info');
    
    // Enable both algorithms
    const bothAlgoRadio = document.querySelector('input[value="both"]');
    if (bothAlgoRadio) {
        bothAlgoRadio.checked = true;
        bothAlgoRadio.dispatchEvent(new Event('change'));
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Calculate routes with both algorithms
    if (typeof computeRouteBasedOnSelection === 'function') {
        const result = await computeRouteBasedOnSelection();
        demoState.comparisonResult = result;
    }
    
    await delay(DEMO_CONFIG.timing.routeCalculation);
}

/**
 * Step 8: Display performance metrics summary
 */
async function demoStep8_MetricsSummary() {
    narrate('Step 8: Displaying performance metrics...');
    demoState.currentStep = 8;
    
    showUpdateToast('� Performance Metrics Summary', 'info');
    
    // Open admin panel to show metrics
    const adminToggle = document.getElementById('admin-toggle');
    if (adminToggle) {
        adminToggle.click();
    }
    
    await delay(DEMO_CONFIG.timing.metricDisplay);
    
    // Log comprehensive metrics
    console.log('🎯 DEMO RESULTS SUMMARY:');
    console.log('=======================');
    
    if (demoState.tauResults) {
        console.log('\n📊 TAU Threshold Comparison:');
        for (const [tau, metrics] of Object.entries(demoState.tauResults)) {
            console.log(`  τ=${tau}: ${metrics.distance}m, ${metrics.query_time}ms, ${metrics.updated_labels} labels updated`);
        }
    }
    
    if (demoState.baselineResult && demoState.trafficResult) {
        console.log('\n🚦 Traffic Impact:');
        const baseDistance = demoState.baselineResult.metrics?.total_distance_m || 0;
        const trafficDistance = demoState.trafficResult.metrics?.total_distance_m || 0;
        const detourPct = ((trafficDistance - baseDistance) / baseDistance * 100).toFixed(1);
        console.log(`  Baseline: ${baseDistance}m`);
        console.log(`  With Traffic: ${trafficDistance}m (${detourPct}% detour)`);
    }
    
    showUpdateToast('✅ Metrics displayed in console', 'success');
    await delay(DEMO_CONFIG.timing.metricDisplay);
}

/**
 * Step 9: Final summary and cleanup
 */
async function demoStep9_FinalSummary() {
    narrate('Step 9: Demo complete - Final summary');
    demoState.currentStep = 9;
    
    const locations = demoState.currentLocations;
    const summary = `
🎬 Demo Completed Successfully!

📍 Route: ${locations?.start?.name} → ${locations?.destination?.name}
🔬 TAU Values Tested: ${DEMO_CONFIG.tauValues.join(', ')}
🚦 Traffic Scenarios: Baseline + Real-time
📊 Algorithms Compared: HC2L vs DHL
    `.trim();
    
    console.log(summary);
    showUpdateToast('✅ Demo sequence complete!', 'success');
    
    await delay(2000);
}

/**
 * Stop demo immediately
 */
function stopDemo() {
    if (!demoState.isRunning) {
        return;
    }
    
    if (demoState.stepTimeout) {
        clearTimeout(demoState.stepTimeout);
        demoState.stepTimeout = null;
    }
    
    demoState.isRunning = false;
    demoState.currentStep = 0;
    
    showUpdateToast('Demo stopped', 'warning');
    console.log('⏹️  Demo stopped by user');
}

/**
 * Helper: Delay execution
 */
function delay(ms) {
    return new Promise(resolve => {
        demoState.stepTimeout = setTimeout(resolve, ms);
    });
}

/**
 * Helper: Narrate demo step (console + optional speech)
 */
function narrate(message) {
    console.log(`🎬 DEMO: ${message}`);
    
    if (demoState.narrationEnabled) {
        // Could add text-to-speech here if desired
        // speechSynthesis.speak(new SpeechSynthesisUtterance(message));
    }
}

/**
 * Quick demo for rapid testing (shorter delays)
 */
async function runQuickDemo() {
    // Temporarily reduce delays
    const originalTiming = { ...DEMO_CONFIG.timing };
    
    Object.keys(DEMO_CONFIG.timing).forEach(key => {
        DEMO_CONFIG.timing[key] = Math.floor(DEMO_CONFIG.timing[key] / 3);
    });
    
    await runDemo();
    
    // Restore original timing
    DEMO_CONFIG.timing = originalTiming;
}

// Expose functions globally
window.runDemo = runDemo;
window.stopDemo = stopDemo;
window.runQuickDemo = runQuickDemo;
window.demoState = demoState;

console.log('✅ Demo automation module loaded');
