/**
 * Modal System
 * Handles modal dialogs with animations
 */

const Modal = (function() {
  'use strict';

  // Active modals stack
  let activeModals = [];

  /**
   * Initialize modal system
   */
  function init() {
    // Set up event delegation
    document.addEventListener('click', handleClick);
    document.addEventListener('keydown', handleKeydown);
    
    console.log('[Modal] Initialized');
  }

  /**
   * Handle click events
   */
  function handleClick(e) {
    // Modal triggers
    const trigger = e.target.closest('[data-modal]');
    if (trigger) {
      e.preventDefault();
      const modalId = trigger.dataset.modal;
      open(modalId);
      return;
    }

    // Modal close buttons
    const closeBtn = e.target.closest('[data-modal-close]');
    if (closeBtn) {
      e.preventDefault();
      const modal = closeBtn.closest('.modal');
      if (modal) {
        close(modal.id);
      }
      return;
    }

    // Click on backdrop
    if (e.target.classList.contains('modal')) {
      const modal = e.target;
      if (modal.dataset.backdropClose !== 'false') {
        close(modal.id);
      }
    }
  }

  /**
   * Handle keyboard events
   */
  function handleKeydown(e) {
    if (e.key === 'Escape' && activeModals.length > 0) {
      const topModal = activeModals[activeModals.length - 1];
      if (topModal.dataset.escapeClose !== 'false') {
        close(topModal.id);
      }
    }

    // Trap focus within modal
    if (e.key === 'Tab' && activeModals.length > 0) {
      trapFocus(e);
    }
  }

  /**
   * Trap focus within active modal
   */
  function trapFocus(e) {
    const modal = activeModals[activeModals.length - 1];
    const focusableElements = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (e.shiftKey && document.activeElement === firstElement) {
      e.preventDefault();
      lastElement.focus();
    } else if (!e.shiftKey && document.activeElement === lastElement) {
      e.preventDefault();
      firstElement.focus();
    }
  }

  /**
   * Open a modal
   * @param {string} modalId - Modal element ID
   * @param {Object} options - Modal options
   */
  function open(modalId, options = {}) {
    const modal = document.getElementById(modalId);
    if (!modal) {
      console.warn(`[Modal] Modal not found: ${modalId}`);
      return;
    }

    // Apply options
    if (options.backdropClose !== undefined) {
      modal.dataset.backdropClose = options.backdropClose;
    }
    if (options.escapeClose !== undefined) {
      modal.dataset.escapeClose = options.escapeClose;
    }

    // Store previously focused element
    modal._previousFocus = document.activeElement;

    // Add to stack
    activeModals.push(modal);

    // Show modal
    modal.classList.add('active');
    document.body.classList.add('modal-open');

    // Focus first focusable element
    requestAnimationFrame(() => {
      const firstFocusable = modal.querySelector(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (firstFocusable) {
        firstFocusable.focus();
      }
    });

    // Dispatch event
    modal.dispatchEvent(new CustomEvent('modal:open', { bubbles: true }));
  }

  /**
   * Close a modal
   * @param {string} modalId - Modal element ID
   */
  function close(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    // Remove from stack
    activeModals = activeModals.filter(m => m.id !== modalId);

    // Hide modal
    modal.classList.remove('active');
    modal.classList.add('closing');

    setTimeout(() => {
      modal.classList.remove('closing');
    }, 300);

    // Update body class
    if (activeModals.length === 0) {
      document.body.classList.remove('modal-open');
    }

    // Restore focus
    if (modal._previousFocus) {
      modal._previousFocus.focus();
    }

    // Dispatch event
    modal.dispatchEvent(new CustomEvent('modal:close', { bubbles: true }));
  }

  /**
   * Close all modals
   */
  function closeAll() {
    [...activeModals].forEach(modal => close(modal.id));
  }

  /**
   * Create and show a confirm dialog
   * @param {Object} options - Dialog options
   * @returns {Promise<boolean>}
   */
  function confirm({
    title = 'Confirm',
    message,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    confirmClass = 'btn-primary',
    dangerous = false
  }) {
    return new Promise((resolve) => {
      // Create modal element
      const modalId = `confirm-modal-${Date.now()}`;
      const modal = document.createElement('div');
      modal.id = modalId;
      modal.className = 'modal';
      modal.innerHTML = `
        <div class="modal-backdrop"></div>
        <div class="modal-container modal-sm">
          <div class="modal-content">
            <div class="modal-header">
              <h3 class="modal-title">${escapeHtml(title)}</h3>
              <button class="modal-close" data-modal-close aria-label="Close">
                <i data-lucide="x"></i>
              </button>
            </div>
            <div class="modal-body">
              <p>${escapeHtml(message)}</p>
            </div>
            <div class="modal-footer">
              <button class="btn btn-ghost" data-action="cancel">
                ${escapeHtml(cancelText)}
              </button>
              <button class="btn ${dangerous ? 'btn-danger' : confirmClass}" data-action="confirm">
                ${escapeHtml(confirmText)}
              </button>
            </div>
          </div>
        </div>
      `;

      // Add to DOM
      document.body.appendChild(modal);

      // Initialize icons
      if (typeof lucide !== 'undefined') {
        lucide.createIcons({ nodes: [modal] });
      }

      // Bind events
      const handleAction = (result) => {
        close(modalId);
        setTimeout(() => modal.remove(), 300);
        resolve(result);
      };

      modal.querySelector('[data-action="confirm"]').addEventListener('click', () => handleAction(true));
      modal.querySelector('[data-action="cancel"]').addEventListener('click', () => handleAction(false));
      modal.querySelector('[data-modal-close]').addEventListener('click', () => handleAction(false));

      // Open modal
      open(modalId);
    });
  }

  /**
   * Create and show an alert dialog
   * @param {Object} options - Dialog options
   * @returns {Promise<void>}
   */
  function alert({
    title = 'Alert',
    message,
    okText = 'OK',
    type = 'info'
  }) {
    return new Promise((resolve) => {
      const modalId = `alert-modal-${Date.now()}`;
      const iconMap = {
        success: 'check-circle',
        error: 'alert-circle',
        warning: 'alert-triangle',
        info: 'info'
      };

      const modal = document.createElement('div');
      modal.id = modalId;
      modal.className = 'modal';
      modal.innerHTML = `
        <div class="modal-backdrop"></div>
        <div class="modal-container modal-sm">
          <div class="modal-content">
            <div class="modal-body text-center" style="padding: 2rem;">
              <div class="modal-icon modal-icon-${type}" style="margin-bottom: 1rem;">
                <i data-lucide="${iconMap[type] || 'info'}" style="width: 48px; height: 48px;"></i>
              </div>
              <h3 style="margin-bottom: 0.5rem;">${escapeHtml(title)}</h3>
              <p style="color: var(--color-text-secondary);">${escapeHtml(message)}</p>
            </div>
            <div class="modal-footer" style="justify-content: center;">
              <button class="btn btn-primary" data-action="ok">
                ${escapeHtml(okText)}
              </button>
            </div>
          </div>
        </div>
      `;

      document.body.appendChild(modal);

      if (typeof lucide !== 'undefined') {
        lucide.createIcons({ nodes: [modal] });
      }

      const handleOk = () => {
        close(modalId);
        setTimeout(() => modal.remove(), 300);
        resolve();
      };

      modal.querySelector('[data-action="ok"]').addEventListener('click', handleOk);

      open(modalId);
    });
  }

  /**
   * Escape HTML
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Public API
  return {
    init,
    open,
    close,
    closeAll,
    confirm,
    alert
  };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', Modal.init);
} else {
  Modal.init();
}

// Expose globally
window.Modal = Modal;
