/**
 * Panel Manager Module
 * Handles panel switching, visibility, and state management
 */

const PanelManager = (function() {
  'use strict';

  // Panel configuration - maps sidebar data-panel values to actual DOM IDs
  const panels = {
    'route-finder': {
      id: 'admin-panel',
      title: 'Route Finder',
      icon: 'navigation'
    },
    'current-route': {
      id: 'current-path-panel',
      title: 'Current Route',
      icon: 'route'
    },
    'report': {
      id: 'report-panel',
      title: 'Report Disruption',
      icon: 'alert-triangle'
    },
    'disruptions': {
      id: 'disruptions-panel',
      title: 'Active Disruptions',
      icon: 'list'
    },
    'metrics': {
      id: 'route-metrics-panel',
      title: 'Route Metrics',
      icon: 'activity'
    },
    'comparison': {
      id: 'algorithm-comparison-panel',
      title: 'Algorithm Comparison',
      icon: 'git-compare'
    },
    'developer': {
      id: 'developer-view-panel',
      title: 'Developer Tools',
      icon: 'code'
    },
    'demo-runner': {
      id: 'demo-runner-panel',
      title: 'Demo Runner',
      icon: 'play-circle'
    },
    'demo-creator': {
      id: 'demo-creator-panel',
      title: 'Demo Creator',
      icon: 'plus-circle'
    }
  };

  // State
  let activePanel = 'route-finder';
  let panelHistory = [];
  let listeners = [];

  /**
   * Initialize panel manager
   */
  function init() {
    // Set up event delegation for panel triggers
    document.addEventListener('click', handlePanelTrigger);
    
    // Show default panel
    showPanel(activePanel);
    
    // Listen for keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
    
    console.log('[PanelManager] Initialized');
  }

  /**
   * Handle panel trigger clicks
   */
  function handlePanelTrigger(e) {
    const trigger = e.target.closest('[data-panel]');
    if (trigger) {
      e.preventDefault();
      const panelKey = trigger.dataset.panel;
      showPanel(panelKey);
    }
  }

  /**
   * Handle keyboard shortcuts
   */
  function handleKeyboardShortcuts(e) {
    // Escape to close modals/overlays
    if (e.key === 'Escape') {
      const modal = document.querySelector('.modal.active');
      if (modal) {
        closeModal(modal);
      }
    }

    // Ctrl+1-9 for quick panel switching
    if (e.ctrlKey && e.key >= '1' && e.key <= '9') {
      const panelKeys = Object.keys(panels);
      const index = parseInt(e.key) - 1;
      if (index < panelKeys.length) {
        e.preventDefault();
        showPanel(panelKeys[index]);
      }
    }
  }

  /**
   * Show a panel by key
   * @param {string} panelKey - Panel identifier
   */
  function showPanel(panelKey) {
    const panelConfig = panels[panelKey];
    if (!panelConfig) {
      console.warn(`[PanelManager] Unknown panel: ${panelKey}`);
      return;
    }

    const panelElement = document.getElementById(panelConfig.id);
    if (!panelElement) {
      console.warn(`[PanelManager] Panel element not found: ${panelConfig.id}`);
      return;
    }

    // Hide all panels
    hideAllPanels();

    // Show target panel with animation
    panelElement.classList.remove('hidden');
    panelElement.classList.add('active');
    
    // Add slide-in animation
    panelElement.style.animation = 'slideInRight 0.3s ease-out';

    // Update sidebar active state
    updateSidebarActive(panelKey);

    // Track history
    if (activePanel !== panelKey) {
      panelHistory.push(activePanel);
      // Keep history manageable
      if (panelHistory.length > 10) {
        panelHistory.shift();
      }
    }

    // Update state
    const previousPanel = activePanel;
    activePanel = panelKey;

    // Notify listeners
    notifyListeners({
      type: 'panel-changed',
      from: previousPanel,
      to: panelKey,
      panelConfig
    });

    console.log(`[PanelManager] Switched to panel: ${panelKey}`);
  }

  /**
   * Hide all panels
   */
  function hideAllPanels() {
    Object.values(panels).forEach(config => {
      const panel = document.getElementById(config.id);
      if (panel) {
        panel.classList.add('hidden');
        panel.classList.remove('active');
      }
    });
  }

  /**
   * Update sidebar active state
   */
  function updateSidebarActive(panelKey) {
    // Remove active from all nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
    });

    // Add active to current
    const navItem = document.querySelector(`[data-panel="${panelKey}"]`);
    if (navItem) {
      navItem.classList.add('active');
    }
  }

  /**
   * Go back to previous panel
   */
  function goBack() {
    if (panelHistory.length > 0) {
      const previousPanel = panelHistory.pop();
      showPanel(previousPanel);
    }
  }

  /**
   * Get current active panel
   * @returns {string} Active panel key
   */
  function getActivePanel() {
    return activePanel;
  }

  /**
   * Get panel configuration
   * @param {string} panelKey - Panel key
   * @returns {Object} Panel configuration
   */
  function getPanelConfig(panelKey) {
    return panels[panelKey] || null;
  }

  /**
   * Register a panel state listener
   * @param {Function} callback - Listener function
   */
  function onPanelChange(callback) {
    listeners.push(callback);
    return () => {
      listeners = listeners.filter(l => l !== callback);
    };
  }

  /**
   * Notify all listeners of state change
   */
  function notifyListeners(event) {
    listeners.forEach(listener => {
      try {
        listener(event);
      } catch (err) {
        console.error('[PanelManager] Listener error:', err);
      }
    });
  }

  /**
   * Toggle panel collapse/expand
   * @param {string} panelKey - Panel key
   */
  function togglePanelCollapse(panelKey) {
    const panelConfig = panels[panelKey];
    if (!panelConfig) return;

    const panelElement = document.getElementById(panelConfig.id);
    if (!panelElement) return;

    const panelBody = panelElement.querySelector('.panel-body');
    if (panelBody) {
      panelBody.classList.toggle('collapsed');
    }

    const collapseBtn = panelElement.querySelector('.panel-collapse-btn');
    if (collapseBtn) {
      collapseBtn.classList.toggle('rotated');
    }
  }

  /**
   * Close a modal
   */
  function closeModal(modal) {
    if (modal) {
      modal.classList.remove('active');
      modal.classList.add('closing');
      setTimeout(() => {
        modal.classList.remove('closing');
      }, 300);
    }
  }

  /**
   * Open a modal
   * @param {string} modalId - Modal element ID
   */
  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
    }
  }

  // Public API
  return {
    init,
    showPanel,
    hideAllPanels,
    goBack,
    getActivePanel,
    getPanelConfig,
    onPanelChange,
    togglePanelCollapse,
    openModal,
    closeModal
  };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', PanelManager.init);
} else {
  PanelManager.init();
}

// Expose globally
window.PanelManager = PanelManager;
