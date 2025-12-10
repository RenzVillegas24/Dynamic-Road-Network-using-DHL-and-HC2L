/**
 * Sidebar Module
 * Handles sidebar navigation, collapse/expand, and mobile responsiveness
 */

const Sidebar = (function () {
  'use strict';

  // State
  let isCollapsed = false;
  let isMobileOpen = false;
  const MOBILE_BREAKPOINT = 768;

  // Elements
  let sidebarElement = null;
  let toggleButton = null;
  let overlay = null;
  let mainWrapper = null;

  /**
   * Initialize sidebar
   */
  function init() {
    sidebarElement = document.getElementById('sidebar');
    // Look for toggle button by ID first, then by class
    toggleButton = document.getElementById('sidebar-toggle') ||
      document.querySelector('.header-sidebar-toggle') ||
      document.querySelector('.header__toggle');
    mainWrapper = document.getElementById('main-wrapper');

    if (!sidebarElement) {
      console.warn('[Sidebar] Sidebar element not found');
      return;
    }

    // Create overlay for mobile
    createMobileOverlay();

    // Set up event listeners
    setupEventListeners();

    // Check initial state from localStorage
    const savedState = localStorage.getItem('sidebar-collapsed');
    if (savedState === 'true') {
      collapse(false); // No animation on initial load
    }

    // Handle window resize
    handleResize();
    window.addEventListener('resize', debounce(handleResize, 150));

    console.log('[Sidebar] Initialized');
  }

  function isDemoRunning() {
    return (typeof DemoRunner !== 'undefined' && DemoRunner.isRunning);
  }

  /**
   * Create mobile overlay
   */
  function createMobileOverlay() {
    overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    overlay.addEventListener('click', closeMobile);
    document.body.appendChild(overlay);
  }

  /**
   * Set up event listeners
   */
  function setupEventListeners() {
    // Toggle button
    if (toggleButton) {
      toggleButton.addEventListener('click', toggle);
    }

    // Nav items click
    sidebarElement.addEventListener('click', handleNavClick);

    // Nav group headers (expand/collapse)
    sidebarElement.querySelectorAll('.nav-group-header').forEach(header => {
      header.addEventListener('click', (e) => {
        const group = header.closest('.nav-group');
        if (group) {
          toggleNavGroup(group);
        }
      });
    });

    // Keyboard navigation
    sidebarElement.addEventListener('keydown', handleKeyboard);

    // Mobile hamburger
    const mobileToggle = document.querySelector('.mobile-menu-toggle');
    if (mobileToggle) {
      mobileToggle.addEventListener('click', toggleMobile);
    }
  }

  /**
   * Handle nav item click
   */
  function handleNavClick(e) {
    // const navItem = e.target.closest('.nav-item');
    // if (!navItem) return;

    // // Remove active from siblings
    // sidebarElement.querySelectorAll('.nav-item').forEach(item => {
    //   item.classList.remove('active');
    // });

    // // Add active to clicked
    // navItem.classList.add('active');

    // // Close mobile sidebar after selection
    // if (isMobile()) {
    //   closeMobile();
    // }
  }

  /**
   * Handle keyboard navigation
   */
  function handleKeyboard(e) {
    const focusedItem = document.activeElement;
    const navItems = [...sidebarElement.querySelectorAll('.nav-item')];
    const currentIndex = navItems.indexOf(focusedItem);

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        const nextIndex = currentIndex < navItems.length - 1 ? currentIndex + 1 : 0;
        navItems[nextIndex]?.focus();
        break;

      case 'ArrowUp':
        e.preventDefault();
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : navItems.length - 1;
        navItems[prevIndex]?.focus();
        break;

      case 'Enter':
      case ' ':
        if (focusedItem.classList.contains('nav-item')) {
          focusedItem.click();
        }
        break;
    }
  }

  /**
   * Toggle nav group collapse
   */
  function toggleNavGroup(group) {
    group.classList.toggle('collapsed');

    const icon = group.querySelector('.nav-group-header i');
    if (icon) {
      icon.style.transform = group.classList.contains('collapsed')
        ? 'rotate(-90deg)'
        : 'rotate(0deg)';
    }
  }

  /**
   * Toggle sidebar
   */
  function toggle() {
    if (map) {
      setTimeout(() => {
        map.invalidateSize({
          animate: true, // This is the default setting
          pan: true      // This is also the default setting for the pan
        });
      }, 150); // Wait for transition to complete
    }
    
    if (isCollapsed) {
      expand();
    } else {
      collapse();
    }

  }

  /**
   * Collapse sidebar
   * @param {boolean} animate - Whether to animate
   */
  function collapse(animate = true) {
    if (!sidebarElement) return;

    isCollapsed = true;
    sidebarElement.classList.add('sidebar--collapsed');
    document.body.setAttribute('data-sidebar-collapsed', 'true');

    // Update toggle button icon
    updateToggleIcon();

    // Save state
    localStorage.setItem('sidebar-collapsed', 'true');

    console.log('[Sidebar] Collapsed');
  }

  /**
   * Expand sidebar
   * @param {boolean} animate - Whether to animate
   */
  function expand(animate = true) {
    if (!sidebarElement) return;

    isCollapsed = false;
    sidebarElement.classList.remove('sidebar--collapsed');
    document.body.removeAttribute('data-sidebar-collapsed');

    // Update toggle button icon
    updateToggleIcon();

    // Save state
    localStorage.setItem('sidebar-collapsed', 'false');

    console.log('[Sidebar] Expanded');
  }

  /**
   * Update toggle button icon
   */
  function updateToggleIcon() {
    if (!toggleButton) return;

    const icon = toggleButton.querySelector('[data-lucide]');
    if (icon) {
      icon.setAttribute('data-lucide', isCollapsed ? 'chevrons-right' : 'chevrons-left');
      if (typeof lucide !== 'undefined') {
        lucide.createIcons();
      }
    }
  }

  /**
   * Check if mobile viewport
   */
  function isMobile() {
    return window.innerWidth < MOBILE_BREAKPOINT;
  }

  /**
   * Handle window resize
   */
  function handleResize() {
    if (isMobile()) {
      // On mobile, sidebar should be hidden by default
      if (!isMobileOpen) {
        sidebarElement?.classList.add('mobile-hidden');
      }
    } else {
      // On desktop, remove mobile classes
      sidebarElement?.classList.remove('mobile-hidden', 'mobile-open');
      overlay?.classList.remove('active');
      isMobileOpen = false;
    }
  }

  /**
   * Toggle mobile sidebar
   */
  function toggleMobile() {
    if (isMobileOpen) {
      closeMobile();
    } else {
      openMobile();
    }
  }

  /**
   * Open mobile sidebar
   */
  function openMobile() {
    if (!sidebarElement) return;

    isMobileOpen = true;
    sidebarElement.classList.remove('mobile-hidden');
    sidebarElement.classList.add('mobile-open');
    overlay?.classList.add('active');
    document.body.classList.add('sidebar-open');
  }

  /**
   * Close mobile sidebar
   */
  function closeMobile() {
    if (!sidebarElement) return;

    isMobileOpen = false;
    sidebarElement.classList.remove('mobile-open');
    sidebarElement.classList.add('mobile-hidden');
    overlay?.classList.remove('active');
    document.body.classList.remove('sidebar-open');
  }

  /**
   * Debounce helper
   */
  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * Set active nav item by panel key
   * @param {string} panelKey - Panel identifier
   */
  function setActive(panelKey) {
    sidebarElement?.querySelectorAll('.nav-item').forEach(item => {
      if (isDemoRunning() &&
        (
          panelKey === 'route-finder' ||
          panelKey === 'current-route' ||
          panelKey === 'comparison' ||
          panelKey === 'demo-creator'
        )) {
        return;
      }

      item.classList.toggle('active', item.dataset.panel === panelKey);
    });
  }

  /**
   * Get collapsed state
   * @returns {boolean}
   */
  function isCurrentlyCollapsed() {
    return isCollapsed;
  }

  // Public API
  return {
    init,
    toggle,
    collapse,
    expand,
    toggleMobile,
    openMobile,
    closeMobile,
    setActive,
    isCollapsed: isCurrentlyCollapsed,
    isMobile
  };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', Sidebar.init);
} else {
  Sidebar.init();
}

// Expose globally
window.Sidebar = Sidebar;
