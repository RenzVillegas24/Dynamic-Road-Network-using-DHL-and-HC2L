// Demo Runner Module (DEPRECATED)
// This module has been replaced by ExperimentRunner.
// Old code moved to demo-runner.js.old

const DemoRunner = {
    isRunning: false,
    isPaused: false,
    init: function() { console.log("DemoRunner is deprecated"); },
    openExperimentSettings: function() {
        if (typeof ExperimentRunner !== "undefined") {
            var panel = document.getElementById("experiment-runner-panel");
            if (panel) panel.classList.remove("translate-x-full");
            ExperimentRunner.showTab("settings");
        }
    },
    openRandomSettings: function() { this.openExperimentSettings(); },
    showTab: function() {},
    runDemo: function() { if (typeof ExperimentRunner !== "undefined") ExperimentRunner.startExperiment(); },
    stopDemo: function() { if (typeof ExperimentRunner !== "undefined") ExperimentRunner.stopExperiment(); },
    pauseDemo: function() { if (typeof ExperimentRunner !== "undefined") ExperimentRunner.togglePause(); },
    loadSavedConfigs: function() {},
    refreshSavedResults: function() {},
    switchDataTab: function() {}
};

document.addEventListener("DOMContentLoaded", function() { DemoRunner.init(); });
window.DemoRunner = DemoRunner;
