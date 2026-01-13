/**
 * Icon System Utilities
 * Provides helper functions for working with Lucide icons
 */

// Icon registry - maps semantic names to Lucide icon names
const IconRegistry = {
  // Navigation
  'menu': 'menu',
  'close': 'x',
  'chevron-left': 'chevron-left',
  'chevron-right': 'chevron-right',
  'chevron-down': 'chevron-down',
  'chevron-up': 'chevron-up',
  'arrow-left': 'arrow-left',
  'arrow-right': 'arrow-right',
  'external-link': 'external-link',
  
  // Route & Navigation
  'route': 'route',
  'navigation': 'navigation',
  'map-pin': 'map-pin',
  'map': 'map',
  'compass': 'compass',
  'locate': 'locate-fixed',
  'directions': 'signpost',
  'start-point': 'circle-dot',
  'end-point': 'flag',
  'waypoint': 'map-pin',
  
  // Transport
  'car': 'car',
  'traffic': 'traffic-cone',
  'road': 'milestone',
  'highway': 'square-m',
  
  // Actions
  'search': 'search',
  'go': 'send',
  'refresh': 'refresh-cw',
  'sync': 'refresh-ccw',
  'play': 'play',
  'pause': 'pause',
  'stop': 'square',
  'reset': 'rotate-ccw',
  'edit': 'pencil',
  'delete': 'trash-2',
  'add': 'plus',
  'remove': 'minus',
  'save': 'save',
  'download': 'download',
  'upload': 'upload',
  'copy': 'copy',
  'expand': 'maximize-2',
  'collapse': 'minimize-2',
  
  // Status & Alerts
  'warning': 'alert-triangle',
  'error': 'alert-circle',
  'success': 'check-circle',
  'info': 'info',
  'help': 'help-circle',
  'bell': 'bell',
  'alert': 'alert-octagon',
  
  // Disruptions - Standard incident types
  // Valid incident types: accident, construction, disabledVehicle, massTransit, 
  // plannedEvent, roadHazard, weather, laneRestriction, roadClosure, other, congestion
  'disruption': 'alert-triangle',
  'incident': 'siren',
  'accident': 'car-front',
  'construction': 'construction',
  'disabledVehicle': 'wrench',
  'disabled-vehicle': 'wrench',
  'massTransit': 'bus',
  'mass-transit': 'bus',
  'plannedEvent': 'calendar',
  'planned-event': 'calendar',
  'roadHazard': 'skull',
  'road-hazard': 'skull',
  'hazard': 'skull',
  'weather': 'cloud-rain',
  'laneRestriction': 'octagon',
  'lane-restriction': 'octagon',
  'roadClosure': 'ban',
  'road-closure': 'ban',
  'closure': 'ban',
  'congestion': 'traffic-cone',
  'other': 'help-circle',
  'event': 'calendar',
  
  // Severity
  'severity-critical': 'flame',
  'severity-high': 'alert-triangle',
  'severity-moderate': 'alert-circle',
  'severity-low': 'info',
  
  // UI Elements
  'settings': 'settings',
  'user': 'user',
  'clock': 'clock',
  'calendar': 'calendar',
  'chart': 'bar-chart-2',
  'graph': 'trending-up',
  'list': 'list',
  'grid': 'grid',
  'filter': 'filter',
  'sort': 'arrow-up-down',
  'eye': 'eye',
  'eye-off': 'eye-off',
  'lock': 'lock',
  'unlock': 'unlock',
  
  // Panels & Sections
  'dashboard': 'layout-dashboard',
  'report': 'file-text',
  'admin': 'shield',
  'developer': 'code',
  'metrics': 'activity',
  'demo': 'play-circle',
  'comparison': 'git-compare',
  'layers': 'layers',
  
  // Algorithms
  'algorithm': 'cpu',
  'dhl': 'zap',
  'hc2l': 'network',
  'dijkstra': 'git-branch',
  'astar': 'star',
  
  // Misc
  'loading': 'loader-2',
  'check': 'check',
  'x': 'x',
  'more': 'more-horizontal',
  'more-vertical': 'more-vertical',
  'link': 'link',
  'unlink': 'unlink',
  'zap': 'zap',
  'fire': 'flame',
  'heart': 'heart',
  'star': 'star',
  'bookmark': 'bookmark',
  'flag': 'flag',
  'pin': 'pin',
  'folder': 'folder',
  'file': 'file',
  'image': 'image',
  'video': 'video',
  'volume': 'volume-2',
  'mute': 'volume-x'
};

// Size presets
const IconSizes = {
  'xs': 14,
  'sm': 16,
  'md': 20,
  'lg': 24,
  'xl': 32,
  '2xl': 40,
  '3xl': 48
};

/**
 * Creates an icon element
 * @param {string} name - Icon name (from IconRegistry or direct Lucide name)
 * @param {Object} options - Icon options
 * @param {string} options.size - Size preset or number
 * @param {string} options.class - Additional CSS classes
 * @param {string} options.color - Icon color
 * @param {number} options.strokeWidth - Stroke width (default 2)
 * @returns {HTMLElement} - The icon element
 */
function createIcon(name, options = {}) {
  const {
    size = 'md',
    class: className = '',
    color = 'currentColor',
    strokeWidth = 2
  } = options;
  
  // Resolve icon name from registry
  const iconName = IconRegistry[name] || name;
  
  // Resolve size
  const iconSize = IconSizes[size] || parseInt(size) || 20;
  
  // Create the icon element
  const icon = document.createElement('i');
  icon.setAttribute('data-lucide', iconName);
  icon.style.width = `${iconSize}px`;
  icon.style.height = `${iconSize}px`;
  icon.style.color = color;
  
  if (className) {
    icon.className = className;
  }
  
  // Store attributes for Lucide to pick up
  icon.setAttribute('data-size', iconSize);
  icon.setAttribute('data-stroke-width', strokeWidth);
  
  return icon;
}

/**
 * Gets the HTML string for an icon
 * @param {string} name - Icon name
 * @param {Object} options - Icon options
 * @returns {string} - HTML string
 */
function getIconHtml(name, options = {}) {
  const {
    size = 'md',
    class: className = '',
    color = 'currentColor',
    strokeWidth = 2
  } = options;
  
  const iconName = IconRegistry[name] || name;
  const iconSize = IconSizes[size] || parseInt(size) || 20;
  
  return `<i data-lucide="${iconName}" 
            style="width: ${iconSize}px; height: ${iconSize}px; color: ${color};"
            class="${className}"
            data-size="${iconSize}"
            data-stroke-width="${strokeWidth}"></i>`;
}

/**
 * Replaces emoji in text with icons
 * @param {string} text - Text containing emoji
 * @returns {string} - Text with emoji replaced by icon HTML
 */
function replaceEmojiWithIcon(text) {
  const emojiMap = {
    '⚠️': getIconHtml('warning', { size: 'sm' }),
    '🚨': getIconHtml('alert', { size: 'sm' }),
    '🔴': getIconHtml('error', { size: 'sm', color: '#ef4444' }),
    '🟡': getIconHtml('warning', { size: 'sm', color: '#f59e0b' }),
    '🟢': getIconHtml('success', { size: 'sm', color: '#22c55e' }),
    '📍': getIconHtml('map-pin', { size: 'sm' }),
    '🏁': getIconHtml('flag', { size: 'sm' }),
    '🚗': getIconHtml('car', { size: 'sm' }),
    '🛣️': getIconHtml('road', { size: 'sm' }),
    '⚡': getIconHtml('zap', { size: 'sm' }),
    '🔥': getIconHtml('fire', { size: 'sm' }),
    '✅': getIconHtml('check', { size: 'sm', color: '#22c55e' }),
    '❌': getIconHtml('x', { size: 'sm', color: '#ef4444' }),
    '📊': getIconHtml('chart', { size: 'sm' }),
    '⏱️': getIconHtml('clock', { size: 'sm' }),
    '🗺️': getIconHtml('map', { size: 'sm' }),
    '🔄': getIconHtml('refresh', { size: 'sm' }),
    '➡️': getIconHtml('arrow-right', { size: 'sm' }),
    '⬆️': getIconHtml('chevron-up', { size: 'sm' }),
    '⬇️': getIconHtml('chevron-down', { size: 'sm' }),
    '📝': getIconHtml('edit', { size: 'sm' }),
    '🗑️': getIconHtml('delete', { size: 'sm' }),
    '💾': getIconHtml('save', { size: 'sm' }),
    '🔍': getIconHtml('search', { size: 'sm' }),
    '⚙️': getIconHtml('settings', { size: 'sm' }),
    '🔔': getIconHtml('bell', { size: 'sm' }),
    '📤': getIconHtml('upload', { size: 'sm' }),
    '📥': getIconHtml('download', { size: 'sm' })
  };
  
  let result = text;
  for (const [emoji, iconHtml] of Object.entries(emojiMap)) {
    result = result.replace(new RegExp(emoji, 'g'), iconHtml);
  }
  
  return result;
}

/**
 * Initializes all icons on the page
 * Should be called after DOM is ready and after dynamic content is added
 */
function initializeIcons() {
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }
}

/**
 * Creates a loading spinner icon
 * @param {string} size - Size preset
 * @returns {string} - HTML string
 */
function getLoadingSpinner(size = 'md') {
  return `<i data-lucide="loader-2" 
            class="animate-spin"
            style="width: ${IconSizes[size] || 20}px; height: ${IconSizes[size] || 20}px;"></i>`;
}

/**
 * Creates a severity icon based on level
 * @param {string} severity - Severity level (critical, high, moderate, low)
 * @returns {string} - HTML string
 */
function getSeverityIcon(severity) {
  const severityMap = {
    'critical': { icon: 'severity-critical', color: '#dc2626' },
    'high': { icon: 'severity-high', color: '#ea580c' },
    'moderate': { icon: 'severity-moderate', color: '#f59e0b' },
    'low': { icon: 'severity-low', color: '#22c55e' }
  };
  
  const config = severityMap[severity.toLowerCase()] || severityMap['low'];
  return getIconHtml(config.icon, { size: 'sm', color: config.color });
}

/**
 * Creates an algorithm icon
 * @param {string} algorithm - Algorithm name (dhl, hc2l, dijkstra, astar)
 * @returns {string} - HTML string
 */
function getAlgorithmIcon(algorithm) {
  const algoMap = {
    'dhl': { icon: 'dhl', color: '#3b82f6' },
    'hc2l': { icon: 'hc2l', color: '#10b981' },
    'dijkstra': { icon: 'dijkstra', color: '#8b5cf6' },
    'astar': { icon: 'astar', color: '#f59e0b' }
  };
  
  const name = algorithm.toLowerCase().replace('lazy', '');
  const config = algoMap[name] || { icon: 'algorithm', color: '#6b7280' };
  return getIconHtml(config.icon, { size: 'sm', color: config.color });
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    IconRegistry,
    IconSizes,
    createIcon,
    getIconHtml,
    replaceEmojiWithIcon,
    initializeIcons,
    getLoadingSpinner,
    getSeverityIcon,
    getAlgorithmIcon
  };
}

// Expose globally for inline scripts
window.IconSystem = {
  IconRegistry,
  IconSizes,
  createIcon,
  getIconHtml,
  replaceEmojiWithIcon,
  initializeIcons,
  getLoadingSpinner,
  getSeverityIcon,
  getAlgorithmIcon
};
