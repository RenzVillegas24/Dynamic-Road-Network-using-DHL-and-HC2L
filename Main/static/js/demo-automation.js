/**
 * Demo Automation Module
 * Automated demo sequence for thesis defense presentation:
 * 1. Load preset locations
 * 2. Calculate base routes
 * 3. Add disruptions
 * 4. Show auto-recalculation
 * 5. Compare algorithms
 */

// Demo configuration
const DEMO_CONFIG = {
    // Preset locations in Quezon City
    locations: {
        start: {
            name: 'Quezon Memorial Circle',
            lat: 14.6540,
            lng: 121.0490,
            description: 'Popular landmark and park'
        },
        destination: {
            name: 'SM North EDSA',
            lat: 14.6563,
            lng: 121.0315,
            description: 'Major shopping mall'
        }
    },
    
    // Demo disruptions
    disruptions: [
        {
            delay: 3000,
            location: { lat: 14.6555, lng: 121.0400 },
            severity: 'heavy',
            type: 'accident',
            description: 'Simulated accident on main route'
        }
    ],
    
    // Timing configuration (in milliseconds)
    timing: {
        locationSet: 1500,
        routeCalculation: 2000,
        disruptionAdd: 3000,
        algorithmSwitch: 2500,
        comparison: 2000,
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
 * Main demo execution function
 */
async function runDemo() {
    if (demoState.isRunning) {
        showUpdateToast('Demo already running', 'warning');
        return;
    }
    
    demoState.isRunning = true;
    demoState.currentStep = 0;
    
    console.log('🎬 Starting automated demo...');
    showUpdateToast('🎬 Starting Demo Sequence...', 'info');
    
    try {
        // Step 1: Reset and prepare
        await demoStep1_Reset();
        
        // Step 2: Load preset locations
        await demoStep2_LoadLocations();
        
        // Step 3: Calculate base route with Lazy HC2L
        await demoStep3_CalculateLazyRoute();
        
        // Step 4: Calculate DHL route for comparison
        await demoStep4_CalculateDHLRoute();
        
        // Step 5: Show algorithm comparison
        await demoStep5_CompareAlgorithms();
        
        // Step 6: Add disruption
        await demoStep6_AddDisruption();
        
        // Step 7: Show auto-recalculation
        await demoStep7_ShowRecalculation();
        
        // Step 8: Compare with Google Maps
        await demoStep8_GoogleComparison();
        
        // Step 9: Final summary
        await demoStep9_Summary();
        
        showUpdateToast('✅ Demo Complete!', 'success');
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
 * Step 2: Load preset start and destination
 */
async function demoStep2_LoadLocations() {
    narrate('Step 2: Loading preset locations...');
    demoState.currentStep = 2;
    
    const start = DEMO_CONFIG.locations.start;
    const destination = DEMO_CONFIG.locations.destination;
    
    showUpdateToast(`📍 Start: ${start.name}`, 'info');
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Set start location
    if (typeof handleStartLocationPin === 'function') {
        await handleStartLocationPin(start.lat, start.lng);
    }
    
    await delay(DEMO_CONFIG.timing.locationSet);
    
    showUpdateToast(`📍 Destination: ${destination.name}`, 'info');
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Set destination location
    if (typeof handleDestLocationPin === 'function') {
        await handleDestLocationPin(destination.lat, destination.lng);
    }
    
    await delay(DEMO_CONFIG.timing.locationSet);
}

/**
 * Step 3: Calculate route with Lazy HC2L
 */
async function demoStep3_CalculateLazyRoute() {
    narrate('Step 3: Calculating route with Lazy HC2L...');
    demoState.currentStep = 3;
    
    showUpdateToast('🔵 Calculating Lazy HC2L route...', 'info');
    
    // Select Lazy HC2L algorithm
    const lazyRadio = document.querySelector('input[value="hc2l_base"]');
    if (lazyRadio) {
        lazyRadio.checked = true;
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Trigger route calculation
    const goButton = document.getElementById('go-button');
    if (goButton) {
        goButton.click();
    }
    
    await delay(DEMO_CONFIG.timing.routeCalculation);
}

/**
 * Step 4: Calculate route with DHL
 */
async function demoStep4_CalculateDHLRoute() {
    narrate('Step 4: Calculating route with DHL...');
    demoState.currentStep = 4;
    
    showUpdateToast('🟣 Calculating DHL route...', 'info');
    
    // Select DHL algorithm
    const dhlRadio = document.querySelector('input[value="dhl_base"]');
    if (dhlRadio) {
        dhlRadio.checked = true;
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Trigger route calculation
    const goButton = document.getElementById('go-button');
    if (goButton) {
        goButton.click();
    }
    
    await delay(DEMO_CONFIG.timing.routeCalculation);
}

/**
 * Step 5: Show algorithm comparison
 */
async function demoStep5_CompareAlgorithms() {
    narrate('Step 5: Comparing algorithms...');
    demoState.currentStep = 5;
    
    showUpdateToast('📊 Showing algorithm comparison...', 'info');
    
    // Select comparison mode
    const comparisonRadio = document.querySelector('input[value="comparison"]');
    if (comparisonRadio) {
        comparisonRadio.checked = true;
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Trigger comparison calculation
    const goButton = document.getElementById('go-button');
    if (goButton) {
        goButton.click();
    }
    
    await delay(DEMO_CONFIG.timing.algorithmSwitch);
    
    // Open comparison modal
    const comparisonButton = document.getElementById('show-comparison-summary');
    if (comparisonButton) {
        comparisonButton.click();
        await delay(3000); // Show modal for 3 seconds
        
        // Close modal
        const closeButton = document.getElementById('comparison-modal-close');
        if (closeButton) {
            closeButton.click();
        }
    }
    
    await delay(DEMO_CONFIG.timing.comparison);
}

/**
 * Step 6: Add disruption to trigger update
 */
async function demoStep6_AddDisruption() {
    narrate('Step 6: Adding road disruption...');
    demoState.currentStep = 6;
    
    showUpdateToast('⚠️ Simulating road accident...', 'warning');
    
    // Select Lazy HC2L with disruptions
    const lazyDisruptedRadio = document.querySelector('input[value="hc2l_disrupted"]');
    if (lazyDisruptedRadio) {
        lazyDisruptedRadio.checked = true;
    }
    
    await delay(DEMO_CONFIG.timing.narrationDelay);
    
    // Add disruption via UI
    const addDisruptionBtn = document.getElementById('add-disruption-btn');
    if (addDisruptionBtn) {
        addDisruptionBtn.click();
        
        await delay(1000);
        
        // Set severity to heavy
        const heavyBtn = document.querySelector('[data-severity="heavy"]');
        if (heavyBtn) {
            heavyBtn.click();
        }
        
        await delay(500);
        
        // Confirm disruption
        const confirmBtn = document.getElementById('confirm-disruption');
        if (confirmBtn) {
            confirmBtn.click();
        }
    }
    
    await delay(DEMO_CONFIG.timing.disruptionAdd);
}

/**
 * Step 7: Show automatic route recalculation
 */
async function demoStep7_ShowRecalculation() {
    narrate('Step 7: Demonstrating auto-recalculation...');
    demoState.currentStep = 7;
    
    showUpdateToast('🔄 Auto-recalculating route with disruption...', 'info');
    
    // Trigger route calculation with disruptions
    const goButton = document.getElementById('go-button');
    if (goButton) {
        goButton.click();
    }
    
    await delay(DEMO_CONFIG.timing.routeCalculation);
    
    // Show update region overlay
    showUpdateToast('🟢 Lazy update region displayed', 'success');
    
    await delay(2000);
}

/**
 * Step 8: Compare with Google Maps
 */
async function demoStep8_GoogleComparison() {
    narrate('Step 8: Comparing with Google Maps...');
    demoState.currentStep = 8;
    
    showUpdateToast('🗺️ Fetching Google Maps route...', 'info');
    
    // Trigger Google Maps comparison
    if (typeof compareWithGoogleMaps === 'function') {
        await compareWithGoogleMaps();
    }
    
    await delay(DEMO_CONFIG.timing.comparison);
}

/**
 * Step 9: Show final summary
 */
async function demoStep9_Summary() {
    narrate('Step 9: Demo complete - Summary displayed');
    demoState.currentStep = 9;
    
    showUpdateToast('📋 Demo Summary:', 'info');
    await delay(1000);
    
    showUpdateToast('✅ All thesis features demonstrated', 'success');
    await delay(1000);
    
    // Open admin panel to show metrics
    const adminToggle = document.getElementById('admin-toggle');
    if (adminToggle) {
        adminToggle.click();
    }
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
