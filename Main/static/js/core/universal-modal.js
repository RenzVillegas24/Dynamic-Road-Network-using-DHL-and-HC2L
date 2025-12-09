/**
 * Universal Modal Manager
 * Provides a flexible modal system for displaying alerts, confirmations, and custom dialogs
 */

const UniversalModal = (function () {
  'use strict';

  // Store for modal templates and instances
  let modalContainer = null;
  let currentModalId = null;

  /**
   * Initialize the modal system
   */
  function init() {
    // Create a container for dynamically generated modals if it doesn't exist
    if (!document.getElementById('universal-modal-container')) {
      modalContainer = document.createElement('div');
      modalContainer.id = 'universal-modal-container';
      document.body.appendChild(modalContainer);
    } else {
      modalContainer = document.getElementById('universal-modal-container');
    }
    console.log('[UniversalModal] Initialized');
  }

  /**
   * Generate a unique modal ID
   */
  function generateModalId() {
    return `modal-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Get icon HTML for the modal header
   * @param {string} icon - Lucide icon name
   * @param {string} variant - 'warning', 'error', 'success', 'info', 'default'
   */
  function getIconHtml(icon, variant = 'default') {
    const variantClass = `modal__icon--${variant}`;
    return `
      <div class="modal__icon ${variantClass}">
        <i data-lucide="${icon}" class="w-6 h-6"></i>
      </div>
    `;
  }

  /**
   * Get header class based on variant
   */
  function getHeaderClass(variant = 'default') {
    return `modal__header modal__header--${variant}`;
  }

  /**
   * Get button class based on variant
   */
  function getButtonClass(btnVariant = 'primary') {
    const variantMap = {
      'primary': 'btn--primary',
      'danger': 'btn--danger',
      'warning': 'btn--warning',
      'success': 'btn--success',
      'ghost': 'btn--ghost',
      'secondary': 'btn--secondary'
    };
    return `btn ${variantMap[btnVariant] || 'btn--primary'}`;
  }

  /**
   * Show a universal modal dialog
   * 
   * @param {Object} options - Modal configuration
   * @param {string} options.icon - Lucide icon name (e.g., 'alert-circle')
   * @param {string} options.variant - Visual variant: 'warning', 'error', 'success', 'info', 'default'
   * @param {string} options.title - Modal title
   * @param {string} options.subtitle - Modal subtitle (optional)
   * @param {string} options.body - Modal body content (HTML)
   * @param {Object} options.buttons - Primary action buttons {label: function, ...}
   *                                   Functions receive (closeModal) as callback
   * @param {Object} options.closeBtn - Close buttons that also close modal {label: function, ...}
   *                                    Functions receive (closeModal) as callback
   * @param {Array} options.dataOptions - Data attributes for the modal root {dataOption: value, ...}
   * @param {boolean} options.backdropClose - Allow clicking backdrop to close (default: false)
   * @param {boolean} options.escapeClose - Allow ESC key to close (default: true)
   * @returns {string} Modal ID
   */
  function showModal(options = {}) {
    // Validate required options
    if (!options.title) {
      console.error('[UniversalModal] Missing required option: title');
      return null;
    }

    // Set defaults
    const modalId = generateModalId();
    const icon = options.icon || 'info';
    const variant = options.variant || 'default';
    const subtitle = options.subtitle || '';
    const body = options.body || '';
    const buttons = options.buttons || {};
    const closeBtn = options.closeBtn || {};
    const backdropClose = options.backdropClose !== undefined ? options.backdropClose : false;
    const escapeClose = options.escapeClose !== undefined ? options.escapeClose : true;
    const dataOptions = options.dataOptions || {};

    // Build data attributes
    let dataAttrs = '';
    if (!backdropClose) dataAttrs += ' data-backdrop-close="false"';
    if (!escapeClose) dataAttrs += ' data-escape-close="false"';
    Object.entries(dataOptions).forEach(([key, value]) => {
      dataAttrs += ` data-${key}="${value}"`;
    });

    // Build buttons HTML
    let buttonsHtml = '';
    Object.entries(buttons).forEach(([label, callback]) => {
      // Determine button variant from label or use default
      let btnVariant = 'primary';
      if (label.toLowerCase().includes('cancel') || label.toLowerCase().includes('no')) {
        btnVariant = 'ghost';
      } else if (label.toLowerCase().includes('delete') || label.toLowerCase().includes('remove')) {
        btnVariant = 'danger';
      } else if (label.toLowerCase().includes('warning')) {
        btnVariant = 'warning';
      } else if (label.toLowerCase().includes('success')) {
        btnVariant = 'success';
      }

      buttonsHtml += `
        <button class="${getButtonClass(btnVariant)} btn-primary-action" data-btn-label="${label}">
          ${label}
        </button>
      `;
    });

    // Build close buttons HTML (buttons that also trigger close)
    let closeBtnHtml = '';
    Object.entries(closeBtn).forEach(([label, callback]) => {
      let btnVariant = 'ghost';
      if (label.toLowerCase().includes('delete') || label.toLowerCase().includes('remove')) {
        btnVariant = 'danger';
      } else if (label.toLowerCase().includes('warning')) {
        btnVariant = 'warning';
      } else if (label.toLowerCase().includes('success')) {
        btnVariant = 'success';
      }

      closeBtnHtml += `
        <button class="${getButtonClass(btnVariant)} btn-close-action" data-btn-label="${label}">
          ${label}
        </button>
      `;
    });

    // Build modal HTML
    const modalHtml = `
      <div id="${modalId}" class="modal"${dataAttrs}>
        <div class="modal__dialog">
          <div class="${getHeaderClass(variant)}">
            ${getIconHtml(icon, variant)}
            <div class="modal__title-group">
              <h3 class="modal__title">${options.title}</h3>
              ${subtitle ? `<p class="modal__subtitle">${subtitle}</p>` : ''}
            </div>
          </div>
          ${body ? `<div class="modal__body">${body}</div>` : ''}
          <div class="modal__footer modal__footer--right">
            ${closeBtnHtml}
            ${buttonsHtml}
          </div>
        </div>
      </div>
      <div class="modal-backdrop" data-modal-id="${modalId}"></div>
    `;

    // Insert modal into container
    modalContainer.insertAdjacentHTML('beforeend', modalHtml);
    const modalElement = document.getElementById(modalId);

    // Helper function to close modal
    const closeModal = () => {
      if (modalElement) {
        // Find backdrop sibling (next element after modal)
        const backdropElement = modalElement.nextElementSibling;
        
        // Trigger closing animation
        modalElement.classList.remove('active');
        if (backdropElement && backdropElement.classList.contains('modal-backdrop')) {
          backdropElement.classList.remove('active');
          backdropElement.classList.add('closing');
        }
        modalElement.classList.add('closing');
        
        // Remove modal and backdrop from DOM after animation completes
        setTimeout(() => {
          if (modalElement && modalElement.parentNode) {
            modalElement.parentNode.removeChild(modalElement);
          }
          if (backdropElement && backdropElement.parentNode) {
            backdropElement.parentNode.removeChild(backdropElement);
          }
          if (currentModalId === modalId) {
            currentModalId = null;
          }
        }, 300);
      }
    };

    // Set up button event listeners
    Object.entries(buttons).forEach(([label, callback]) => {
      const btn = modalElement.querySelector(`[data-btn-label="${label}"].btn-primary-action`);
      if (btn) {
        btn.addEventListener('click', () => {
          try {
            callback(closeModal);
          } catch (err) {
            console.error('[UniversalModal] Button callback error:', err);
          }
        });
      }
    });

    // Set up close button event listeners (these close the modal after callback)
    Object.entries(closeBtn).forEach(([label, callback]) => {
      const btn = modalElement.querySelector(`[data-btn-label="${label}"].btn-close-action`);
      if (btn) {
        btn.addEventListener('click', () => {
          try {
            callback(closeModal);
          } catch (err) {
            console.error('[UniversalModal] Close button callback error:', err);
          }
          closeModal();
        });
      }
    });

    // Get backdrop element (sibling after modal)
    const backdropElement = modalElement.nextElementSibling;

    // Set up backdrop close
    if (backdropClose && backdropElement && backdropElement.classList.contains('modal-backdrop')) {
      backdropElement.addEventListener('click', closeModal);
    }

    // Set up escape key close
    if (escapeClose) {
      const handleEscape = (e) => {
        if (e.key === 'Escape' && currentModalId === modalId) {
          closeModal();
          document.removeEventListener('keydown', handleEscape);
        }
      };
      document.addEventListener('keydown', handleEscape);
    }

    // Show modal with animation
    // Use requestAnimationFrame to ensure animations work
    requestAnimationFrame(() => {
      modalElement.classList.add('active');
      if (backdropElement && backdropElement.classList.contains('modal-backdrop')) {
        backdropElement.classList.add('active');
      }
    });
    
    currentModalId = modalId;

    // Trigger lucide icon rendering
    if (typeof lucide !== 'undefined') {
      lucide.createIcons({ nodes: [modalElement] });
    }

    console.log(`[UniversalModal] Showing modal: ${modalId}`);
    return modalId;
  }

  /**
   * Close a modal by ID
   * @param {string} modalId - Modal ID to close
   */
  function closeModalById(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      modal.classList.add('closing');
      setTimeout(() => {
        if (modal && modal.parentNode) {
          modal.parentNode.removeChild(modal);
        }
        if (currentModalId === modalId) {
          currentModalId = null;
        }
      }, 300);
    }
  }

  /**
   * Close the currently active modal
   */
  function closeCurrentModal() {
    if (currentModalId) {
      closeModalById(currentModalId);
    }
  }

  // Public API
  return {
    init,
    showModal,
    closeModalById,
    closeCurrentModal
  };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', UniversalModal.init);
} else {
  UniversalModal.init();
}

// Expose globally
window.UniversalModal = UniversalModal;
