/**
 * Panel Manager Module
 * Handles panel switching, visibility, and state management
 */

const PanelManager = (function () {
  'use strict';

  // Panel configuration - maps sidebar data-panel values to actual DOM IDs
  const panels = {
    'route-finder': {
      id: 'finder-panel',
      title: 'Route Finder',
      icon: 'navigation',
      size: 'md',
      isPassable: () => {
        if (isDemoRunning()) {
          // Show modal dialog instead of toast
          showDemoStopModal('route-finder', 'sidebar');
          return false;
        }
        return true;
      }
    },
    'current-route': {
      id: 'current-path-panel',
      title: 'Current Route',
      icon: 'route',
      size: 'md',
      isPassable: () => {
        if (isDemoRunning()) {
          // Show modal dialog instead of toast
          showDemoStopModal('current-route', 'sidebar');
          return false;
        }

        if (window.currentRouteData == null) {
          showNoRouteModal();
          return false;
        }
        return true;
      }
    },
    'report': {
      id: 'report-panel',
      title: 'Report Disruption',
      icon: 'alert-triangle',
      size: 'lg',
      isPassable: () => true
    },
    'disruptions': {
      id: 'disruptions-panel',
      title: 'Active Disruptions',
      icon: 'list',
      size: 'lg',
      isPassable: () => {
        if (window.currentRouteData == null && !isDemoRunning()) {
          showNoRouteModal();
          return false;
        }
        return true;
      }
    },
    'metrics': {
      id: 'route-metrics-panel',
      title: 'Route Metrics',
      icon: 'activity',
      size: 'lg',
      isPassable: () => {
        if (window.currentRouteData == null && !isDemoRunning()) {
          showNoRouteModal();
          return false;
        }
        return true;
      }
    },
    'comparison': {
      id: 'algorithm-comparison-panel',
      title: 'Algorithm Comparison',
      icon: 'git-compare',
      size: 'lg',
      isPassable: () => {
        if (window.currentRouteData == null) {
          showNoRouteModal();
          return false;
        }
        if (isDemoRunning()) {
          // Show modal dialog instead of toast
          showDemoStopModal('current-route', 'sidebar');
          return false;
        }
        return true;
      }
    },
    'developer': {
      id: 'developer-view-panel',
      title: 'Developer Tools',
      icon: 'terminal',
      size: 'xl',
      isPassable: () => true
    },
    'demo-runner': {
      id: 'demo-runner-panel',
      title: 'Demo Runner',
      icon: 'play-circle',
      size: 'lg',
      isPassable: () => true
    },
    'demo-creator': {
      id: 'demo-creator-panel',
      title: 'Demo Creator',
      icon: 'plus-circle',
      size: 'lg',
      isPassable: () => {
        if (isDemoRunning()) {
          // Show modal dialog instead of toast
          showDemoStopModal('demo-creator', 'sidebar');
          return false;
        }
        return true;
      }
    }
  };

  // State
  let activePanel = null;
  let panelHistory = [];
  let listeners = [];
  let isRightPanelOpen = false;
  let navigationSource = 'sidebar'; // 'sidebar' or 'panel'

  /**
   * Initialize panel manager
   */
  function init() {
    // Set up event delegation for panel triggers
    document.addEventListener('click', handlePanelTrigger);

    // Set up close/back button handlers
    setupCloseBackButtons();

    // Listen for keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);

    console.log('[PanelManager] Initialized');
  }

  function isDemoRunning() {
    return (typeof DemoRunner !== 'undefined' && DemoRunner.isRunning) ||
      (typeof DemoCreator !== 'undefined' && DemoCreator.isRunning);
  }

  /**
   * Set up close and back button handlers
   */
  function setupCloseBackButtons() {
    // Handle all panel close buttons
    document.querySelectorAll('.panel__close').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Only go back if navigation came from within the panel
        if (panelHistory.length > 0 && navigationSource === 'panel') {
          goBack();
        } else {
          closeRightPanel();
        }
      });
    });
  }

  /**
   * Update close button to show back or close icon
   */
  function updateCloseBackButton(panelElement) {
    const closeBtn = panelElement?.querySelector('.panel__close');
    if (!closeBtn) return;

    const icon = closeBtn.querySelector('[data-lucide]');
    if (icon) {
      // Show back arrow only if there's history AND navigation came from within panel
      const showBack = panelHistory.length > 0 && navigationSource === 'panel';
      const iconName = showBack ? 'arrow-left' : 'x';
      icon.setAttribute('data-lucide', iconName);
      if (typeof lucide !== 'undefined') {
        lucide.createIcons({ nodes: [closeBtn] });
      }
    }
  }

  /**
   * Handle panel trigger clicks
   */
  function handlePanelTrigger(e) {
    const trigger = e.target.closest('[data-panel]');
    if (trigger) {
      e.preventDefault();
      const panelKey = trigger.dataset.panel;

      // Determine if this trigger is from sidebar or from within a panel
      const isFromSidebar = trigger.closest('#sidebar') || trigger.closest('.nav-item');
      const isFromPanel = trigger.closest('.panel') || trigger.closest('#right-panel-container');

      if (isFromPanel && !isFromSidebar) {
        // Navigation from within a panel - add to history
        showPanel(panelKey, 'panel');
      } else {
        // Navigation from sidebar - clear history
        showPanel(panelKey, 'sidebar');
      }
    }
  }

  /**
   * Handle keyboard shortcuts
   */
  function handleKeyboardShortcuts(e) {
    // Escape to close modals/overlays or go back
    if (e.key === 'Escape') {
      const modal = document.querySelector('.modal.active');
      if (modal) {
        closeModal(modal);
      } else if (isRightPanelOpen) {
        if (panelHistory.length > 0 && navigationSource === 'panel') {
          goBack();
        } else {
          closeRightPanel();
        }
      }
    }

    // Ctrl+1-9 for quick panel switching
    if (e.ctrlKey && e.key >= '1' && e.key <= '9') {
      const panelKeys = Object.keys(panels);
      const index = parseInt(e.key) - 1;
      if (index < panelKeys.length) {
        e.preventDefault();
        showPanel(panelKeys[index], 'sidebar');
      }
    }
  }

  /**
   * Show a panel by key
   * @param {string} panelKey - Panel identifier
   * @param {string} source - Navigation source ('sidebar' or 'panel')
   */
  function showPanel(panelKey, source = 'sidebar') {
    const panelConfig = panels[panelKey];
    if (!panelConfig) {
      console.warn(`[PanelManager] Unknown panel: ${panelKey}`);
      return;
    }

    // Check if demo is running and prevent opening route-finder panel
    if (typeof panelConfig.isPassable === 'function') {
      if (!panelConfig.isPassable()) {
        return;
      }
    } else if (panelConfig.isPassable === false) {
      return;
    }

    const panelElement = document.getElementById(panelConfig.id);
    if (!panelElement) {
      console.warn(`[PanelManager] Panel element not found: ${panelConfig.id}`);
      return;
    }

    // If navigation is from sidebar, clear history BEFORE updating source
    if (source === 'sidebar') {
      panelHistory = [];
    }

    // Update navigation source after validation
    navigationSource = source;

    // Hide all panels (but don't close the container)
    hideAllPanelsInternal();

    // Show target panel with animation
    panelElement.classList.remove('hidden');
    panelElement.classList.add('active');

    // Add slide-in animation
    panelElement.style.animation = 'slideInRight 0.3s ease-out';

    // Add panel-open class to main content area for layout adjustments
    const mainContentArea = document.getElementById('main-content-area');
    if (mainContentArea) {
      mainContentArea.classList.add('panel-open');
    }

    // Open the split-view secondary container
    const rightPanelContainer = document.getElementById('right-panel-container');
    if (rightPanelContainer) {
      rightPanelContainer.classList.add('open');
      isRightPanelOpen = true;

      // Set the width based on panel size
      const panelWidth = panelConfig.size || 'md';
      rightPanelContainer.classList.remove('split-view__secondary--sm', 'split-view__secondary--md', 'split-view__secondary--lg', 'split-view__secondary--xl', 'split-view__secondary--xxl');
      if (panelWidth !== 'md') {
        rightPanelContainer.classList.add(`split-view__secondary--${panelWidth}`);
      }
    }

    // Update sidebar active state
    // updateSidebarActive(panelKey);

    // Track history only if navigating from within a panel
    if (source === 'panel' && activePanel && activePanel !== panelKey) {
      panelHistory.push(activePanel);
      // Keep history manageable
      if (panelHistory.length > 10) {
        panelHistory.shift();
      }
    }

    // Update state
    const previousPanel = activePanel;
    activePanel = panelKey;

    // Update close/back button icon (after panel is visible)
    setTimeout(() => {
      updateCloseBackButton(panelElement);
    }, 0);

    // Notify listeners
    notifyListeners({
      type: 'panel-changed',
      from: previousPanel,
      to: panelKey,
      panelConfig,
      source
    });

    // Trigger map resize to adjust to new container size
    if (map) {
      setTimeout(() => {
        map.invalidateSize({
          animate: true, // This is the default setting
          pan: true      // This is also the default setting for the pan
        });
      }, 250); // Wait for transition to complete
    }


    console.log(`[PanelManager] Switched to panel: ${panelKey} (source: ${source})`);
  }

  /**
   * Hide all panels internally (without closing the container)
   */
  function hideAllPanelsInternal() {
    Object.values(panels).forEach(config => {
      const panel = document.getElementById(config.id);
      if (panel) {
        panel.classList.add('hidden');
        panel.classList.remove('active');
      }
    });
  }

  /**
   * Hide all panels and close the right panel container
   */
  function hideAllPanels() {
    hideAllPanelsInternal();
    closeRightPanel();
  }

  /**
   * Close the right panel container
   */
  function closeRightPanel() {
    // Remove panel-open class from main content area
    const mainContentArea = document.getElementById('main-content-area');
    if (mainContentArea) {
      mainContentArea.classList.remove('panel-open', 'panel-lg');
    }

    // Close the split-view secondary container
    const rightPanelContainer = document.getElementById('right-panel-container');
    if (rightPanelContainer) {
      rightPanelContainer.classList.remove('open');
      rightPanelContainer.classList.remove('split-view__secondary--sm', 'split-view__secondary--md', 'split-view__secondary--lg', 'split-view__secondary--xl', 'split-view__secondary--xxl');
    }

    // Reset state
    isRightPanelOpen = false;
    activePanel = null;
    panelHistory = [];
    navigationSource = 'sidebar';

    // Remove active from all nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
    });

    // Hide all panels
    hideAllPanelsInternal();

    console.log('[PanelManager] Right panel closed');

    // Trigger map resize to adjust to new container size
    if (map) {
      setTimeout(() => {
        map.invalidateSize({
          animate: true, // This is the default setting
          pan: true      // This is also the default setting for the pan
        });
      }, 250); // Wait for transition to complete
    }

  }

  /**
   * Update sidebar active state
   */
  // function updateSidebarActive(panelKey) {
  //   // Remove active from all nav items
  //   document.querySelectorAll('.nav-item').forEach(item => {
  //     item.classList.remove('active');
  //   });

  //   // Add active to current
  //   const navItem = document.querySelector(`[data-panel="${panelKey}"]`);
  //   if (navItem) {
  //     navItem.classList.add('active');
  //   }
  // }

  /**
   * Go back to previous panel
   */
  function goBack() {
    if (panelHistory.length > 0) {
      const previousPanel = panelHistory.pop();
      showPanel(previousPanel);
    } else {
      closeRightPanel();
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

  /**
   * Show demo stop modal dialog using universal modal system
   * Allows user to stop demo and navigate or cancel
   * @param {string} targetPanelKey - Panel key to navigate to
   * @param {string} source - Navigation source ('sidebar' or 'panel')
   */
  function showDemoStopModal(targetPanelKey, source = 'sidebar') {
    if (typeof UniversalModal === 'undefined') {
      console.error('[PanelManager] UniversalModal not loaded');
      return;
    }

    UniversalModal.showModal({
      icon: 'alert-circle',
      variant: 'warning',
      title: 'Demo is Running',
      subtitle: 'A demo is currently in progress',
      body: '<p class="text-sm text-slate-700 leading-relaxed">You are attempting to navigate while the demo is running. Would you like to stop the demo and navigate, or cancel this action?</p>',
      buttons: {
        'Stop Demo & Navigate': (closeModal) => {
          // Stop the demo
          if (typeof DemoCreator !== 'undefined' && DemoCreator.isRunning) {
            DemoCreator.stopDemo();
          } else if (typeof DemoRunner !== 'undefined' && DemoRunner.isRunning) {
            DemoRunner.stopDemo();
          }

          // Close modal
          closeModal();

          // Navigate to target panel after a brief delay
          setTimeout(() => {
            showPanel(targetPanelKey, source);
          }, 300);
        }
      },
      closeBtn: {
        'Cancel': (closeModal) => {
          // Just close the modal, no additional action needed
        }
      },
      backdropClose: false,
      escapeClose: true
    });
  }

  function showNoRouteModal() {
    if (typeof UniversalModal === 'undefined') {
      console.error('[PanelManager] UniversalModal not loaded');
      return;
    }

    UniversalModal.showModal({
      icon: 'alert-circle',
      variant: 'warning',
      title: 'No Active Route',
      body: '<p class="text-sm text-slate-700 leading-relaxed">There is currently no active route to display. Please create a route first.</p>',
      closeBtn: {
        'OK': (closeModal) => {
          // Just close the modal, no additional action needed
        }
      },
      backdropClose: false,
      escapeClose: true
    });

  }
  

  // Public API
  return {
    init,
    showPanel,
    hideAllPanels,
    closeRightPanel,
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
