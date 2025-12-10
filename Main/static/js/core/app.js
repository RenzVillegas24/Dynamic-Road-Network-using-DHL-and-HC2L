/**
 * Main Application Module
 * Initializes and coordinates all components
 */

const App = (function() {
  'use strict';

  // Application state
  const state = {
    initialized: false,
    map: null,
    algorithm: 'LazyDHL',
    isConnected: false,
    activeDisruptions: 0
  };

  // Module references
  const modules = {};

  /**
   * Initialize the application
   */
  async function init() {
    if (state.initialized) {
      console.warn('[App] Already initialized');
      return;
    }

    console.log('[App] Initializing application...');

    try {
      // Initialize core modules
      initCoreModules();

      // Initialize Lucide icons
      initIcons();

      // Set up global event listeners
      setupEventListeners();

      // Initialize status indicators
      updateConnectionStatus(true);

      // Load initial data
      await loadInitialData();

      state.initialized = true;
      console.log('[App] Application initialized successfully');

      // Show welcome toast
      if (window.Toast) {
        Toast.success('Application ready');
      }
    } catch (error) {
      console.error('[App] Initialization error:', error);
      if (window.Toast) {
        Toast.error('Failed to initialize application');
      }
    }
  }

  /**
   * Initialize core modules
   */
  function initCoreModules() {
    // These modules self-initialize, but we reference them here
    modules.sidebar = window.Sidebar;
    modules.panelManager = window.PanelManager;
    modules.toast = window.Toast;
    modules.modal = window.Modal;
    modules.icons = window.IconSystem;

    // Link panel manager to sidebar
    if (modules.panelManager && modules.sidebar) {
      modules.panelManager.onPanelChange((event) => {
        modules.sidebar.setActive(event.to);
      });
    }
  }

  /**
   * Initialize Lucide icons
   */
  function initIcons() {
    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
      console.log('[App] Icons initialized');
    } else {
      console.warn('[App] Lucide not loaded');
    }
  }

  /**
   * Set up global event listeners
   */
  function setupEventListeners() {
    // Global keyboard shortcuts
    document.addEventListener('keydown', handleGlobalKeydown);

    // Window events
    window.addEventListener('online', () => updateConnectionStatus(true));
    window.addEventListener('offline', () => updateConnectionStatus(false));

    // Theme toggle
    const themeToggle = document.querySelector('[data-action="toggle-theme"]');
    if (themeToggle) {
      themeToggle.addEventListener('click', toggleTheme);
    }

    // Search shortcut
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
      document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
          e.preventDefault();
          searchInput.focus();
        }
      });
    }

    // Algorithm selector
    const algorithmSelect = document.getElementById('algorithm-select');
    if (algorithmSelect) {
      algorithmSelect.addEventListener('change', (e) => {
        setAlgorithm(e.target.value);
      });
    }
  }

  /**
   * Handle global keyboard shortcuts
   */
  function handleGlobalKeydown(e) {
    // Ctrl+Shift+D - Toggle developer panel
    if (e.ctrlKey && e.shiftKey && e.key === 'D') {
      e.preventDefault();
      modules.panelManager?.showPanel('developer');
    }

    // Ctrl+/ - Toggle help
    if (e.ctrlKey && e.key === '/') {
      e.preventDefault();
      showKeyboardShortcuts();
    }
  }

  /**
   * Load initial data
   */
  async function loadInitialData() {
    try {
      // NOTE: Disruption count endpoint not yet implemented
      // Disruptions are loaded dynamically when routes are calculated
      // const response = await fetch('/api/disruptions/count');
      // if (response.ok) {
      //   const data = await response.json();
      //   state.activeDisruptions = data.count || 0;
      //   updateDisruptionBadge();
      // }
    } catch (error) {
      console.warn('[App] Could not load initial data:', error);
    }
  }

  /**
   * Update connection status indicator
   */
  function updateConnectionStatus(isConnected) {
    state.isConnected = isConnected;
    
    const indicator = document.querySelector('.connection-status');
    if (indicator) {
      indicator.classList.toggle('connected', isConnected);
      indicator.classList.toggle('disconnected', !isConnected);
      
      const text = indicator.querySelector('.status-text');
      if (text) {
        text.textContent = isConnected ? 'Connected' : 'Disconnected';
      }
    }
  }

  /**
   * Update disruption badge with optional count parameter
   * @param {number} count - Optional disruption count to set (if not provided, uses state.activeDisruptions)
   */
  function updateDisruptionBadge(count) {
    const badge = document.querySelector('.disruption-badge');
    if (badge) {
      // Use provided count, otherwise fall back to state
      const disruptionCount = typeof count === 'number' ? count : state.activeDisruptions;
      state.activeDisruptions = disruptionCount;
      badge.textContent = disruptionCount;
      badge.classList.toggle('collapse', disruptionCount === 0);
    }
  }

  /**
   * Set active algorithm
   */
  function setAlgorithm(algorithm) {
    state.algorithm = algorithm;
    
    // Update UI
    const display = document.querySelector('.algorithm-display');
    if (display) {
      display.textContent = algorithm;
    }

    // Notify other components
    document.dispatchEvent(new CustomEvent('algorithm:changed', {
      detail: { algorithm }
    }));

    console.log(`[App] Algorithm changed to: ${algorithm}`);
  }

  /**
   * Toggle theme
   */
  function toggleTheme() {
    const currentTheme = document.documentElement.dataset.theme || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.dataset.theme = newTheme;
    localStorage.setItem('theme', newTheme);

    // Update icon
    const themeIcon = document.querySelector('[data-action="toggle-theme"] [data-lucide]');
    if (themeIcon) {
      themeIcon.setAttribute('data-lucide', newTheme === 'dark' ? 'sun' : 'moon');
      lucide.createIcons();
    }
  }

  /**
   * Load saved theme
   */
  function loadSavedTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      document.documentElement.dataset.theme = savedTheme;
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      document.documentElement.dataset.theme = 'dark';
    }
  }

  /**
   * Show keyboard shortcuts modal
   */
  function showKeyboardShortcuts() {
    const shortcuts = [
      { key: 'Ctrl + K', description: 'Focus search' },
      { key: 'Ctrl + 1-9', description: 'Switch panels' },
      { key: 'Ctrl + Shift + D', description: 'Developer tools' },
      { key: 'Escape', description: 'Close modal/panel' },
      { key: 'Ctrl + /', description: 'Show shortcuts' }
    ];

    const content = shortcuts.map(s => 
      `<div class="shortcut-row">
        <kbd>${s.key}</kbd>
        <span>${s.description}</span>
      </div>`
    ).join('');

    if (window.Modal) {
      Modal.alert({
        title: 'Keyboard Shortcuts',
        message: content,
        type: 'info'
      });
    }
  }

  /**
   * Get application state
   */
  function getState() {
    return { ...state };
  }

  /**
   * Get map instance
   */
  function getMap() {
    return state.map;
  }

  /**
   * Set map instance
   */
  function setMap(map) {
    state.map = map;
  }

  // Load theme immediately
  loadSavedTheme();

  // Public API
  return {
    init,
    getState,
    getMap,
    setMap,
    setAlgorithm,
    toggleTheme,
    updateConnectionStatus,
    updateDisruptionBadge
  };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', App.init);
} else {
  App.init();
}

// Expose globally
window.App = App;
