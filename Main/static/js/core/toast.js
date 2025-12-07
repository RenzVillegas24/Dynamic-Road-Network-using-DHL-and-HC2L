/**
 * Toast Notification System
 * Provides user feedback through animated toast notifications with stacking support
 */

const Toast = (function() {
  'use strict';

  // Configuration
  const config = {
    duration: 5000,
    maxToasts: 4,
    position: 'bottom-left',
    animation: 'bottom' // 'top', 'bottom', 'left', 'right', 'center'
  };

  // Toast container
  let container = null;

  // Active toasts
  let activeToasts = [];

  /**
   * Initialize toast system
   */
  function init() {
    createContainer();
    console.log('[Toast] Initialized');
  }

  /**
   * Create toast container
   */
  function createContainer() {
    container = document.getElementById('toast-container');
    
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = `toast-container toast-container--${config.position}`;
      document.body.appendChild(container);
    }
  }

  /**
   * Show a toast notification
   * @param {Object} options - Toast options
   * @param {string} options.message - Toast message
   * @param {string} options.type - Toast type (success, error, warning, info)
   * @param {number} options.duration - Duration in ms (0 for persistent)
   * @param {string} options.icon - Custom icon name
   * @param {Array} options.actions - Action buttons
   * @param {string} options.position - Toast position
   * @param {string} options.animation - Animation type (top, bottom, left, center)
   * @returns {Object} Toast instance
   */
  function show(options) {
    const {
      message,
      type = 'info',
      duration = config.duration,
      icon = null,
      actions = [],
      position = null,
      animation = null
    } = typeof options === 'string' ? { message: options } : options;

    // Ensure container exists
    if (!container) {
      createContainer();
    }

    // Update container position if specified
    if (position && position !== config.position) {
      config.position = position;
      container.className = `toast-container toast-container--${config.position}`;
    }

    // Update animation if specified
    if (animation) {
      config.animation = animation;
    }

    // Remove oldest toast if at max
    if (activeToasts.length >= config.maxToasts) {
      dismiss(activeToasts[activeToasts.length - 1].id);
    }

    // Create toast element
    const toast = createToastElement({
      message,
      type,
      icon,
      actions
    });

    // Prepend to container (newest first for proper stacking)
    if (container.firstChild) {
      container.insertBefore(toast, container.firstChild);
    } else {
      container.appendChild(toast);
    }

    // Track toast (newest at beginning of array)
    const toastObj = {
      id: toast.id,
      element: toast,
      timeoutId: null
    };
    activeToasts.unshift(toastObj);

    // Trigger entrance animation
    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    // Auto dismiss
    if (duration > 0) {
      toastObj.timeoutId = setTimeout(() => {
        dismiss(toast.id);
      }, duration);
    }

    return {
      id: toast.id,
      dismiss: () => dismiss(toast.id)
    };
  }

  /**
   * Create toast DOM element
   */
  function createToastElement({ message, type, icon, actions }) {
    const toast = document.createElement('div');
    toast.id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    toast.className = `toast toast--${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');

    // Icon mapping
    const iconMap = {
      success: 'check-circle',
      error: 'alert-circle',
      warning: 'alert-triangle',
      info: 'info'
    };

    const iconName = icon || iconMap[type] || 'info';

    toast.innerHTML = `
      <div class="toast-content">
        ${iconName ? `<div class="toast-icon"><i data-lucide="${iconName}"></i></div>` : ''}
        <div class="toast-message">${escapeHtml(message)}</div>
        <button class="toast-dismiss" aria-label="Dismiss">
          <i data-lucide="x"></i>
        </button>
        ${actions.length > 0 ? `
          <div class="toast-actions">
            ${actions.map(action => `
              <button class="toast-action" data-action="${action.id || action.label}">
                ${escapeHtml(action.label)}
              </button>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;

    // Bind dismiss button
    const dismissBtn = toast.querySelector('.toast-dismiss');
    dismissBtn.addEventListener('click', () => dismiss(toast.id));

    // Bind action buttons
    actions.forEach(action => {
      const btn = toast.querySelector(`[data-action="${action.id || action.label}"]`);
      if (btn && action.onClick) {
        btn.addEventListener('click', () => {
          action.onClick();
          if (action.dismissOnClick !== false) {
            dismiss(toast.id);
          }
        });
      }
    });

    // Initialize Lucide icons
    if (typeof lucide !== 'undefined') {
      setTimeout(() => lucide.createIcons({ nodes: [toast] }), 0);
    }

    // Pause timer on hover
    toast.addEventListener('mouseenter', () => {
      const toastObj = activeToasts.find(t => t.id === toast.id);
      if (toastObj?.timeoutId) {
        clearTimeout(toastObj.timeoutId);
      }
    });

    toast.addEventListener('mouseleave', () => {
      const toastObj = activeToasts.find(t => t.id === toast.id);
      if (toastObj) {
        toastObj.timeoutId = setTimeout(() => {
          dismiss(toast.id);
        }, 2000);
      }
    });

    return toast;
  }

  /**
   * Dismiss a toast
   * @param {string} id - Toast ID
   */
  function dismiss(id) {
    const toastIndex = activeToasts.findIndex(t => t.id === id);
    if (toastIndex === -1) return;

    const toastObj = activeToasts[toastIndex];
    const { element, timeoutId } = toastObj;

    // Clear timeout
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    // Remove from tracking
    activeToasts.splice(toastIndex, 1);

    // Animate out
    element.classList.remove('show');
    element.classList.add('hide');

    // Remove from DOM after animation
    setTimeout(() => {
      element.remove();
    }, 300);
  }

  /**
   * Dismiss all toasts
   */
  function dismissAll() {
    [...activeToasts].forEach(toast => dismiss(toast.id));
  }

  /**
   * Helper methods for common types
   */
  function success(message, options = {}) {
    return show({ ...options, message, type: 'success' });
  }

  function error(message, options = {}) {
    return show({ ...options, message, type: 'error' });
  }

  function warning(message, options = {}) {
    return show({ ...options, message, type: 'warning' });
  }

  function info(message, options = {}) {
    return show({ ...options, message, type: 'info' });
  }

  /**
   * Show loading toast (persistent until dismissed)
   * @param {string} message - Loading message
   * @returns {Object} Toast instance with update method
   */
  function loading(message) {
    const toast = show({
      message,
      type: 'info',
      icon: 'loader-2',
      duration: 0
    });

    // Add spinning animation to icon
    const toastElement = document.getElementById(toast.id);
    const icon = toastElement?.querySelector('.toast-icon i');
    if (icon) {
      icon.classList.add('animate-spin');
    }

    return {
      ...toast,
      success: (msg) => {
        dismiss(toast.id);
        return success(msg);
      },
      error: (msg) => {
        dismiss(toast.id);
        return error(msg);
      },
      update: (msg) => {
        const messageEl = toastElement?.querySelector('.toast-message');
        if (messageEl) {
          messageEl.textContent = msg;
        }
      }
    };
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Configure toast system
   * @param {Object} newConfig - Configuration options
   */
  function configure(newConfig) {
    Object.assign(config, newConfig);
    
    if (container && (newConfig.position || newConfig.animation)) {
      const posClass = newConfig.position || config.position;
      container.className = `toast-container toast-container--${posClass}`;
    }
  }

  // Public API
  return {
    init,
    show,
    dismiss,
    dismissAll,
    success,
    error,
    warning,
    info,
    loading,
    configure
  };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', Toast.init);
} else {
  Toast.init();
}

// Expose globally
window.Toast = Toast;
