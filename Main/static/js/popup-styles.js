/**
 * Centralized Popup Styling Module
 * Handles consistent modern popup formatting across all map interactions
 */

const PopupStyles = {
  /**
   * Get severity/criticality badge styling
   */
  getBadgeClass: (severity) => {
    const sev = severity?.toLowerCase() || 'light';
    if (sev === 'critical') return 'icon-badge-critical';
    if (sev === 'major') return 'icon-badge-major';
    if (sev === 'heavy') return 'icon-badge-heavy';
    if (sev === 'medium') return 'icon-badge-medium';
    if (sev === 'default') return 'icon-badge-default';
    return 'icon-badge-light';
  },
  /**
   * Get icon for incident type
   */
  getIncidentIcon: (type) => {
    const icons = {
      'Road Closure': '✖️',
      'Accident': '🚑',
      'Construction': '🚧',
      'Congestion': '🚦',
      'Disabled Vehicle': '🔧',
      'Mass Transit Event': '🚌',
      'Planned Event': '📅',
      'Road Hazard': '⚠️',
      'Lane Restriction': '🚧',
      'Weather': '🌧',
      'Heavy': '🛑',
      'Medium': '⚠️',
      'Light': '✅'
    };
    return icons[type] || '📍';
  },

  /**
   * Create modern popup for incidents
   */
  createIncidentPopup: (data) => {
    const {
      road_name = 'Unknown Road',
      incident_type = 'Incident',
      incident_criticality = 'Minor',
      incident_road_closed = false,
      incident_description = '',
      incident_start_time = '',
      incident_end_time = '',
      highway_type = ''
    } = data;

    const criticality = incident_criticality.toLowerCase();
    const badgeClass = PopupStyles.getBadgeClass(criticality);
    const icon = PopupStyles.getIncidentIcon(incident_type);

    return `
      <div class="popup-container">
        <div class="popup-header">
          <div class="popup-icon-badge ${badgeClass}">
            ${icon}
          </div>
          <div class="popup-header-title">
            <h3>${road_name}</h3>
            <p>${incident_type}</p>
          </div>
        </div>
        <div class="popup-divider"></div>
        <div class="popup-section">
          <div class="popup-item">
            <span class="popup-item-label">Criticality:</span>
            <span class="popup-item-value popup-severity-badge ${criticality}">
                ${incident_criticality.toUpperCase()}
            </span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Road Closed:</span>
            <span class="popup-item-value">${incident_road_closed ? '🔴 Yes' : '🟢 No'}</span>
          </div>
          ${highway_type ? `<div class="popup-item">
            <span class="popup-item-label">Road Type:</span>
            <span class="popup-item-value">${highway_type}</span>
          </div>` : ''}
        </div>
        ${incident_description ? `
        <div class="popup-divider"></div>
        <div class="popup-section">
          <p class="popup-section-title">Description</p>
          <p class="popup-text-muted">${incident_description}</p>
        </div>
        ` : ''}
        ${incident_start_time || incident_end_time ? `
        <div class="popup-divider"></div>
        <div class="popup-section">
          ${incident_start_time ? `<div class="popup-item">
            <span class="popup-item-label">Start:</span>
            <span class="popup-item-value">${incident_start_time}</span>
          </div>` : ''}
          ${incident_end_time ? `<div class="popup-item">
            <span class="popup-item-label">End:</span>
            <span class="popup-item-value">${incident_end_time}</span>
          </div>` : ''}
        </div>
        ` : ''}
      </div>
    `;
  },

  /**
   * Create modern popup for traffic/flow data
   */
  createTrafficPopup: (data) => {
    const {
      road_name = 'Unknown Road',
      incident_type = 'Traffic',
      severity = 'Light',
      speed_kph = 0,
      free_flow_kph = 50,
      jam_factor = 0,
      is_closed = false,
      color = '#10b981',
    } = data;

    const slowdownRatio = speed_kph > 0 ? (speed_kph / free_flow_kph) : 0.5;
    const badgeClass = PopupStyles.getBadgeClass(severity);
    const icon = PopupStyles.getIncidentIcon(severity);

    return `
      <div class="popup-container">
        <div class="popup-header">
          <div class="popup-icon-badge ${badgeClass}">
            ${icon}
          </div>
          <div class="popup-header-title">
            <h3>${road_name}</h3>
            <p>${incident_type}</p>
          </div>
        </div>
        <div class="popup-divider"></div>
        <div class="popup-section">
          <div class="popup-item">
            <span class="popup-item-label">Severity:</span>
            <span class="popup-item-value popup-severity-badge ${severity.toLowerCase()}">
                ${severity.toUpperCase()}
            </span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Current Speed:</span>
            <span class="popup-item-value">${speed_kph.toFixed(1)} km/h</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Free Flow:</span>
            <span class="popup-item-value">${free_flow_kph.toFixed(1)} km/h</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Slowdown:</span>
            <span class="popup-item-value">${Math.round(slowdownRatio * 100)}% of normal</span>
          </div>
          ${jam_factor > 0 ? `<div class="popup-item">
            <span class="popup-item-label">Jam Factor:</span>
            <span class="popup-item-value ${jam_factor > 5 ? 'popup-value-jam-high' : 'popup-value-jam-low'}">
              ${jam_factor.toFixed(1)}/10
            </span>
          </div>` : ''}
          ${is_closed ? `<div class="popup-item">
            <span class="popup-item-label">Status:</span>
            <span class="popup-item-value popup-status-closed">
                🚫 CLOSED
            </span>
          </div>` : ''}
        </div>
      </div>
    `;
  },

  /**
   * Create modern popup for OSM edges
   */
  createEdgePopup: (data) => {
    const {
      name = 'Unknown Road',
      highway = 'Unknown',
      length = 0,
      oneway = false
    } = data;

    return `
      <div class="popup-container popup-container-small">
        <div class="popup-header">
          <div class="popup-icon-badge popup-icon-badge-edge">
            🛣️
          </div>
          <div class="popup-header-title">
            <h3>${name}</h3>
            <p>Road Segment</p>
          </div>
        </div>
        <div class="popup-divider"></div>
        <div class="popup-section">
          <div class="popup-item">
            <span class="popup-item-label">Type:</span>
            <span class="popup-item-value">${highway}</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Length:</span>
            <span class="popup-item-value">${length.toFixed(0)}m</span>
          </div>
          ${oneway ? `<div class="popup-item">
            <span class="popup-item-label">Direction:</span>
            <span class="popup-item-value popup-value-oneway">🔄 One-way</span>
          </div>` : ''}
        </div>
      </div>
    `;
  },

  /**
   * Create modern popup for route segments
   */
  createRouteSegmentPopup: (data) => {
    const {
      road_name = 'Unknown Road',
      from = 0,
      to = 0,
      distance_km = 0,
      highway_type = 'unknown',
      severity = null,
      current_speed = 0,
      free_flow_speed = 50,
      jam_factor = 0,
      is_closed = false,
      incident_type = 'none',
      incident_confidence = 0,
      segment_index = 0,
      total_segments = 0,
      route_type = 'DHL'
    } = data;

    // Compute displaySeverity: use passed severity or fall back to computing from jam_factor
    const displaySeverity = severity || (typeof TrafficUtils !== 'undefined' ? TrafficUtils.getSeverityFromJamFactor(jam_factor, is_closed) : 'FreeFlow');
    const statusSeverityClass = displaySeverity.toLowerCase();
    const iconBadgeClass = route_type === 'DHL' ? 'popup-icon-badge-dhl' : 'popup-icon-badge-hc2l';
    
    return `
      <div class="popup-container popup-container-large">
        <div class="popup-header">
          <div class="popup-icon-badge ${iconBadgeClass}">
            🛣️
          </div>
          <div class="popup-header-title">
            <h3>${road_name}</h3>
            <p>${route_type} Segment ${segment_index + 1}/${total_segments}</p>
          </div>
        </div>
        <div class="popup-divider"></div>
        <div class="popup-section">
          <div class="popup-item">
            <span class="popup-item-label">Edge:</span>
            <span class="popup-item-value">${from} → ${to}</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Distance:</span>
            <span class="popup-item-value">${distance_km} km</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Highway:</span>
            <span class="popup-item-value">${highway_type}</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Severity:</span>
            <span class="popup-item-value popup-severity-badge ${statusSeverityClass}">
              ${displaySeverity.toUpperCase()}
            </span>
          </div>
        </div>

        ${!is_closed ? `
        <div class="popup-divider"></div>
        <div class="popup-section">
          <p class="popup-section-title">Traffic Info</p>
          <div class="popup-item">
            <span class="popup-item-label">Current Speed:</span>
            <span class="popup-item-value">${current_speed.toFixed(1)} km/h</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Free Flow:</span>
            <span class="popup-item-value">${free_flow_speed.toFixed(1)} km/h</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Jam Factor:</span>
            <span class="popup-item-value ${jam_factor > 5 ? 'popup-value-jam-high' : 'popup-value-jam-low'}">
              ${jam_factor.toFixed(1)}
            </span>
          </div>
        </div>
        ` : ''}

        ${is_closed ? `
        <div class="popup-divider"></div>
        <div class="popup-section">
          <p class="popup-section-title popup-section-title-danger">🚫 Road Closed</p>
          <div class="popup-item">
            <span class="popup-item-label">Type:</span>
            <span class="popup-item-value">${incident_type}</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Confidence:</span>
            <span class="popup-item-value">${(incident_confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
        ` : ''}

        ${incident_type !== 'none' && !is_closed ? `
        <div class="popup-divider"></div>
        <div class="popup-section">
          <p class="popup-section-title popup-section-title-warning">⚠️ Incident</p>
          <div class="popup-item">
            <span class="popup-item-label">Type:</span>
            <span class="popup-item-value">${incident_type}</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Confidence:</span>
            <span class="popup-item-value">${(incident_confidence * 100).toFixed(0)}%</span>
          </div>
        </div>
        ` : ''}
      </div>
    `;
  },

  /**
   * Create modern popup for traffic overlay segments
   */
  createTrafficOverlayPopup: (data) => {
    const {
      incident_type = 'Traffic',
      road_name = 'Unknown Road',
      highway_type = 'Unknown',
      severity = 'Light',
      speed_kph = 0,
      free_flow_kph = 50,
      jam_factor = 0,
      length = 0,
      is_closed = false,
      description = ''
    } = data;

    const icon = PopupStyles.getIncidentIcon(incident_type);
    const badgeClass = PopupStyles.getBadgeClass(severity);
    const severityLower = severity.toLowerCase();

    return `
      <div class="popup-container popup-container-medium">
        <div class="popup-header">
          <div class="popup-icon-badge ${badgeClass}">
            ${icon}
          </div>
          <div class="popup-header-title">
            <h3>${road_name}</h3>
            <p>${incident_type}</p>
          </div>
        </div>
        <div class="popup-divider"></div>
        <div class="popup-section">
          <div class="popup-item">
            <span class="popup-item-label">Type:</span>
            <span class="popup-item-value">${highway_type.charAt(0).toUpperCase() + highway_type.slice(1).toLowerCase()}</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Severity:</span>
            <span class="popup-item-value popup-severity-badge ${severityLower}">
                ${severity.toUpperCase()}
            </span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Speed:</span>
            <span class="popup-item-value">${speed_kph.toFixed(1)} km/h</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Free Flow:</span>
            <span class="popup-item-value">${free_flow_kph.toFixed(1)} km/h</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Jam Factor:</span>
            <span class="popup-item-value">${jam_factor.toFixed(1)}/10</span>
          </div>
          <div class="popup-item">
            <span class="popup-item-label">Length:</span>
            <span class="popup-item-value">${length ? length.toFixed(0) : 0}m</span>
          </div>
        </div>
        ${is_closed ? `
        <div class="popup-divider"></div>
        <div class="popup-section">
          <p class="popup-section-title popup-section-title-danger">🚫 ROAD CLOSED</p>
        </div>
        ` : ''}
        ${description ? `
        <div class="popup-divider"></div>
        <div class="popup-section">
          <p class="popup-section-title">Details</p>
          <p class="popup-text-muted">${description}</p>
        </div>
        ` : ''}
      </div>
    `;
  },

  /**
   * Create modern popup for snapped locations
   */
  createSnappedLocationPopup: (data) => {
    const {
      role = 'start',
      location_name = 'Location',
      road_name = 'Unknown Road',
      distance_to_snap = 0,
      edge_id = ''
    } = data;

    const roleTitle = role === 'start' ? 'Start Location' : role === 'dest' ? 'Destination' : 'Location';
    const roleClass = role === 'start' ? 'popup-icon-badge-start' : role === 'dest' ? 'popup-icon-badge-dest' : 'popup-icon-badge-info';

    return `
      <div class="popup-container popup-container-small">
        <div class="popup-header">
          <div class="popup-icon-badge ${roleClass}">
            📍
          </div>
          <div class="popup-header-title">
            <h3>${location_name}</h3>
            <p>${roleTitle}</p>
          </div>
        </div>
        <div class="popup-divider"></div>
        <div class="popup-section">
          <div class="popup-item">
            <span class="popup-item-label">Snapped Road:</span>
            <span class="popup-item-value">${road_name}</span>
          </div>
          ${distance_to_snap > 0 ? `<div class="popup-item">
            <span class="popup-item-label">Distance:</span>
            <span class="popup-item-value">${distance_to_snap.toFixed(1)}m</span>
          </div>` : ''}
          ${edge_id ? `<div class="popup-item">
            <span class="popup-item-label">Edge ID:</span>
            <span class="popup-item-value popup-value-monospace">${edge_id}</span>
          </div>` : ''}
        </div>
      </div>
    `;
  }
};

// Export for global use
window.PopupStyles = PopupStyles;
