/**
 * Traffic Visualization Module
 * Handles OSM graph display, incident markers, and traffic overlay
 */

// Global state for traffic visualization
const trafficVisualization = {
  osmGraphLayer: null,
  incidentsLayer: null,
  trafficOverlayLayer: null,
  currentRoute: null,
  trafficMode: 'both', // 'incidents', 'flow', or 'both'
  cachedSegments: null,
  segmentsPromise: null
};

/**
 * Load and display OSM graph edges
 */
function loadOSMGraph() {
  console.log('Loading OSM Graph...');
  
  fetch('/get_osm_graph_edges?limit=100000')
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Create layer group if it doesn't exist
        if (!trafficVisualization.osmGraphLayer) {
          trafficVisualization.osmGraphLayer = L.layerGroup().addTo(map);
        }
        
        // Clear existing layers
        trafficVisualization.osmGraphLayer.clearLayers();
        
        // Add each edge as a polyline
        data.edges.forEach(edge => {
          const latlngs = edge.coordinates.map(coord => [coord[0], coord[1]]);
          const polyline = L.polyline(latlngs, {
            color: '#3b82f6',
            weight: 2,
            opacity: 0.4
          });
          
          // Add popup with edge info using modern style
          const edgePopup = PopupStyles.createEdgePopup({
            name: edge.name,
            highway: edge.highway,
            length: edge.length,
            oneway: edge.oneway
          });
          polyline.bindPopup(edgePopup);
          
          trafficVisualization.osmGraphLayer.addLayer(polyline);
        });
        
        console.log(`✅ Loaded ${data.count} OSM edges`);
      } else {
        console.error('Failed to load OSM graph:', data.error);
        showUpdateToast('Failed to load OSM graph', 'error');
      }
    })
    .catch(error => {
      console.error('Error loading OSM graph:', error);
      showUpdateToast('Error loading OSM graph', 'error');
    });
}

/**
 * Clear OSM graph display
 */
function clearOSMGraph() {
  if (trafficVisualization.osmGraphLayer) {
    trafficVisualization.osmGraphLayer.clearLayers();
    map.removeLayer(trafficVisualization.osmGraphLayer);
    trafficVisualization.osmGraphLayer = null;
  }
  console.log('OSM Graph cleared');
}

/**
 * Load and display active incidents (excludes flow/congestion data)
 */
function loadActiveIncidents() {
  console.log('Loading Active Incidents (excluding flow data)...');
  
  fetch('/get_active_disruptions')
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.text().then(text => {
        console.log('Raw response length:', text.length, 'bytes');
        if (text.length < 500) {
          console.log('Raw response:', text);
        }
        try {
          return JSON.parse(text);
        } catch (error) {
          console.error('JSON parse error:', error.message);
          console.error('Response preview:', text.substring(0, 200));
          throw error;
        }
      });
    })
    .then(data => {
      if (data.success) {
        // Create layer group if it doesn't exist
        if (!trafficVisualization.incidentsLayer) {
          trafficVisualization.incidentsLayer = L.layerGroup().addTo(map);
        }
        
        // Clear existing layers
        trafficVisualization.incidentsLayer.clearLayers();
        
        let severityColor = '#10b981'; // green
        if (incident.severity === 'low') {
          severityColor = '#10b981'; // green
        } else if (incident.severity === 'critical') {
          severityColor = '#dc2626'; // dark red
        } else if (incident.severity === 'medium') {
          severityColor = '#f59e0b'; // amber
        }
        
        // Filter to show ONLY true incidents (exclude Congestion which is flow data)
        const incidentTypes = ['Accident', 'Road Closure', 'Construction', 'Weather', 
                               'Road Hazard', 'Disabled Vehicle', 'Mass Transit Event', 
                               'Planned Event', 'Lane Restriction'];
        
        let totalIncidents = 0;
        
        // Add incidents by type (excluding Congestion/flow)
        Object.entries(data.disruptions_by_type).forEach(([incidentType, disruptions]) => {
          // Skip if not a true incident (e.g., Congestion is flow data)
          if (!incidentTypes.includes(incidentType)) {
            console.log(`Skipping ${incidentType} (flow data, not incident)`);
            return;
          }
          
          disruptions.forEach(incident => {
            const midLat = (incident.source_lat + incident.target_lat) / 2;
            const midLng = (incident.source_lng + incident.target_lng) / 2;
            
            // Create custom marker
            const marker = L.circleMarker([midLat, midLng], {
              radius: 8,
              fillColor: severityColor,
              color: '#fff',
              weight: 2,
              opacity: 1,
              fillOpacity: 0.8
            });
            
            // Add popup using modern style
            const incidentPopup = PopupStyles.createTrafficPopup({
              road_name: incident.road_name,
              incident_type: incidentType,
              severity: incident.severity,
              speed_kph: incident.speed_kph,
              free_flow_kph: incident.free_flow_kph,
              jam_factor: incident.jam_factor,
              is_closed: incident.is_closed,
            });
            marker.bindPopup(incidentPopup);
            
            trafficVisualization.incidentsLayer.addLayer(marker);
            totalIncidents++;
          });
        });
        
        console.log(`✅ Loaded ${totalIncidents} incidents (excluding flow/congestion data)`);
      } else {
        console.error('Failed to load incidents:', data.error);
        showUpdateToast('Failed to load incidents', 'error');
      }
    })
    .catch(error => {
      console.error('Error loading incidents:', error);
      showUpdateToast('Error loading incidents', 'error');
    });
}

/**
 * Clear active incidents display
 */
function clearActiveIncidents() {
  if (trafficVisualization.incidentsLayer) {
    trafficVisualization.incidentsLayer.clearLayers();
    map.removeLayer(trafficVisualization.incidentsLayer);
    trafficVisualization.incidentsLayer = null;
  }
  console.log('Active Incidents cleared');
}

/**
 * Apply traffic overlay with full OSM road geometries
 * @param {string} mode - 'incidents', 'flow', or 'both'
 * @param {boolean} routeOnly - If true, show traffic only for current route
 */
function applyTrafficOverlay(mode, routeOnly) {
  console.log(`Applying Traffic Overlay (mode: ${mode}, routeOnly: ${routeOnly})`);
  
  // Update state
  trafficVisualization.trafficMode = mode;
  
  // Always show matched edges with full OSM road geometries
  return applyMatchedTrafficWithGeometry(mode, routeOnly);
}

/**
 * Apply matched traffic overlay with full OSM road geometries
 * Uses the new hash-based matching system with LineString geometries
 */
function applyMatchedTrafficWithGeometry(mode, routeOnly, options = {}) {
  console.log(`🗺️  Loading traffic with OSM geometries...`);

  return ensureTrafficSegments(options.forceReload)
    .then(segments => {
      const displayedCount = renderTrafficSegments(segments, mode, routeOnly);
      if (displayedCount > 0) {
        showUpdateToast(`Showing ${displayedCount} traffic segments with road geometries`, 'success');
      } else {
        showUpdateToast('No traffic data to display for current filters', 'info');
      }
      return displayedCount;
    })
    .catch(error => {
      console.error('Error applying traffic overlay:', error);
      showUpdateToast('Error loading traffic overlay', 'error');
      throw error;
    });
}

function ensureTrafficSegments(forceReload = false) {
  if (trafficVisualization.cachedSegments && !forceReload) {
    return Promise.resolve(trafficVisualization.cachedSegments);
  }

  if (trafficVisualization.segmentsPromise && !forceReload) {
    return trafficVisualization.segmentsPromise;
  }

  trafficVisualization.segmentsPromise = fetch('/get_traffic_with_geometry')
    .then(response => response.json())
    .then(data => {
      if (!data.success) {
        throw new Error(data.error || 'Failed to load traffic data');
      }

      const segments = Array.isArray(data.segments) ? data.segments : [];
      trafficVisualization.cachedSegments = segments;

      if (segments.length > 0) {
        console.log(`   📊 Received ${data.total_segments || segments.length} traffic segments with geometry`);
        console.log(`   🔍 Sample segment:`, segments[0]);
      }

      return segments;
    })
    .catch(error => {
      console.error('Error fetching traffic data:', error);
      throw error;
    })
    .finally(() => {
      trafficVisualization.segmentsPromise = null;
    });

  return trafficVisualization.segmentsPromise;
}

function renderTrafficSegments(segments, mode, routeOnly) {
  if (!map) {
    console.warn('Map not ready for traffic overlay');
    return 0;
  }

  if (!trafficVisualization.trafficOverlayLayer) {
    trafficVisualization.trafficOverlayLayer = L.layerGroup().addTo(map);
  } else if (!map.hasLayer(trafficVisualization.trafficOverlayLayer)) {
    trafficVisualization.trafficOverlayLayer.addTo(map);
  }

  trafficVisualization.trafficOverlayLayer.clearLayers();

  if (!Array.isArray(segments) || segments.length === 0) {
    console.log('   ⚠️  No traffic segments to render');
    return 0;
  }

  const incidentIcons = {
    'Accident': '🚗',
    'Road Closure': '🚧',
    'Construction': '🏗️',
    'Congestion': '🚦',
    'Weather': '🌧️',
    'Road Hazard': '⚠️',
    'Disabled Vehicle': '🚙',
    'Other': '📍'
  };

  let displayedCount = 0;

  segments.forEach(segment => {
    try {
      const isIncident = segment.type === 'incident';
      const isFlow = segment.type === 'flow';

      if (mode === 'incidents' && !isIncident) return;
      if (mode === 'flow' && !isFlow) return;

      // Filter: Only show meaningful disruptions (jam_factor >= 2.0 or is_closed or has severity beyond 'Light')
      if (isFlow && !segment.is_closed && segment.jam_factor < 2.0) {
        console.debug(`   ⊘ Skipping non-disruptive flow (jam_factor=${segment.jam_factor})`);
        return;
      }

      if (routeOnly && trafficVisualization.currentRoute) {
        const onRoute = isSegmentOnRoute(
          segment.source,
          segment.target,
          trafficVisualization.currentRoute
        );
        if (!onRoute) return;
      }

      // Use TrafficUtils for consistent color determination
      const jamFactor = segment.jam_factor || 0;
      const isClosed = segment.is_closed || false;
      const style = TrafficUtils.getDisruptionStyle(jamFactor, isClosed);
      const { color, weight } = style;
      const opacity = 0.55;

      if (!segment.geometry || !Array.isArray(segment.geometry) || segment.geometry.length < 2) {
        console.warn('   ⚠️  Skipping segment with invalid geometry:', segment);
        return;
      }

      const geometry = segment.geometry
        .map(coord => [parseFloat(coord[0]), parseFloat(coord[1])])
        .filter(coord => coord.every(value => Number.isFinite(value)));

      if (!geometry || geometry.length < 2) {
        return;
      }

      const polyline = L.polyline(geometry, {
        color: color,
        weight: weight,
        opacity: opacity,
        className: 'route-segment-clickable'
      });

      const icon = TrafficUtils.getIncidentIcon(segment.incident_type);
      const severity = TrafficUtils.getSeverityFromJamFactor(jamFactor, isClosed);
      const popup = PopupStyles.createTrafficOverlayPopup({
        incident_type: segment.incident_type,
        road_name: segment.road_name,
        highway_type: segment.highway_type,
        severity: severity,
        speed_kph: segment.speed_kph || 0,
        free_flow_kph: segment.free_flow_kph || 0,
        jam_factor: jamFactor,
        length: segment.length,
        is_closed: isClosed,
        description: segment.description
      });

      polyline.bindPopup(popup);
      polyline.on('mouseover', function() {
        this.setStyle({
          weight: weight + 2,
          opacity: Math.min(opacity + 0.2, 1)
        });
      });

      polyline.on('mouseout', function() {
        this.setStyle({
          weight: weight,
          opacity: opacity
        });
      });

      trafficVisualization.trafficOverlayLayer.addLayer(polyline);
      displayedCount++;
    } catch (error) {
      console.error('Error processing segment:', error, segment);
    }
  });

  console.log(`   ✅ Displayed ${displayedCount} traffic segments on map`);
  return displayedCount;
}

function hideTrafficOverlayLayer() {
  if (trafficVisualization.trafficOverlayLayer && map && map.hasLayer(trafficVisualization.trafficOverlayLayer)) {
    map.removeLayer(trafficVisualization.trafficOverlayLayer);
  }
}

/**
 * Apply matched traffic overlay (DEPRECATED - kept for backwards compatibility)
 * Use applyMatchedTrafficWithGeometry instead
 */
function applyMatchedTrafficOverlay(mode, routeOnly) {
  console.warn('⚠️  applyMatchedTrafficOverlay is deprecated, use applyMatchedTrafficWithGeometry');
  applyMatchedTrafficWithGeometry(mode, routeOnly);
}

/**
 * Clear traffic overlay
 */
function clearTrafficOverlay() {
  if (trafficVisualization.trafficOverlayLayer) {
    trafficVisualization.trafficOverlayLayer.clearLayers();
    map.removeLayer(trafficVisualization.trafficOverlayLayer);
    trafficVisualization.trafficOverlayLayer = null;
  }
  console.log('Traffic Overlay cleared');
}

/**
 * Clear cached traffic segments (forces fresh fetch on next load)
 * Call this when disruptions are updated
 */
function clearTrafficCache() {
  trafficVisualization.cachedSegments = null;
  trafficVisualization.segmentsPromise = null;
  console.log('[TrafficVisualization] Traffic cache cleared - will fetch fresh data on next load');
}

/**
 * Update current route for route-only traffic filtering
 * @param {Array} routePath - Array of node IDs representing the route
 */
function updateCurrentRoute(routePath) {
  trafficVisualization.currentRoute = routePath;
  console.log('Current route updated:', routePath);
}

/**
 * Check if a segment is on the current route
 * @param {number} sourceId - Source node ID
 * @param {number} targetId - Target node ID
 * @param {Array} routePath - Array of node IDs
 * @returns {boolean}
 */
function isSegmentOnRoute(sourceId, targetId, routePath) {
  if (!routePath || routePath.length < 2) return false;
  
  for (let i = 0; i < routePath.length - 1; i++) {
    if ((routePath[i] === sourceId && routePath[i + 1] === targetId) ||
        (routePath[i] === targetId && routePath[i + 1] === sourceId)) {
      return true;
    }
  }
  
  return false;
}

// Export functions for global use
window.loadOSMGraph = loadOSMGraph;
window.clearOSMGraph = clearOSMGraph;
window.loadActiveIncidents = loadActiveIncidents;
window.clearActiveIncidents = clearActiveIncidents;
window.applyTrafficOverlay = applyTrafficOverlay;
window.clearTrafficOverlay = clearTrafficOverlay;
window.clearTrafficCache = clearTrafficCache;
window.hideTrafficOverlayLayer = hideTrafficOverlayLayer;
window.updateCurrentRoute = updateCurrentRoute;
