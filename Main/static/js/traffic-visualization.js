/**
 * Traffic Visualization Module
 * Handles OSM graph display, incident markers, and traffic overlay
 */

// Global state for traffic visualization
const trafficVisualization = {
  osmGraphLayer: null,
  incidentsLayer: null,
  trafficOverlayLayer: null,
  rawTrafficLayer: null,  // For non-matched HERE data
  currentRoute: null,
  trafficMode: 'both', // 'incidents', 'flow', or 'both'
  showMatched: true  // Toggle between matched and raw traffic
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
          
          // Add popup with edge info
          polyline.bindPopup(`
            <div class="p-2">
              <p class="font-bold">${edge.name}</p>
              <p class="text-xs">Type: ${edge.highway}</p>
              <p class="text-xs">Length: ${edge.length.toFixed(0)}m</p>
              ${edge.oneway ? '<p class="text-xs text-orange-600">One-way</p>' : ''}
            </div>
          `);
          
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
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Create layer group if it doesn't exist
        if (!trafficVisualization.incidentsLayer) {
          trafficVisualization.incidentsLayer = L.layerGroup().addTo(map);
        }
        
        // Clear existing layers
        trafficVisualization.incidentsLayer.clearLayers();
        
        // Get icon for incident type
        const getIncidentIcon = (type, severity) => {
          const colors = {
            'Heavy': '#ef4444',
            'Medium': '#f59e0b',
            'Light': '#10b981'
          };
          
          const icons = {
            'Accident': '🚗',
            'Road Closure': '🚧',
            'Construction': '🏗️',
            'Congestion': '🚦',
            'Weather': '🌧️',
            'Road Hazard': '⚠️',
            'Disabled Vehicle': '🚙',
            'Mass Transit Event': '🚇',
            'Planned Event': '📅',
            'Lane Restriction': '⚠️'
          };
          
          return {
            color: colors[severity] || '#6b7280',
            icon: icons[type] || '📍'
          };
        };
        
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
            
            const { color, icon } = getIncidentIcon(incidentType, incident.severity);
            
            // Create custom marker
            const marker = L.circleMarker([midLat, midLng], {
              radius: 8,
              fillColor: color,
              color: '#fff',
              weight: 2,
              opacity: 1,
              fillOpacity: 0.8
            });
            
            // Add popup
            marker.bindPopup(`
              <div class="p-3">
                <div class="flex items-center mb-2">
                  <span class="text-2xl mr-2">${icon}</span>
                  <h3 class="font-bold text-lg">${incidentType}</h3>
                </div>
                <div class="space-y-1 text-sm">
                  <p><span class="font-semibold">Road:</span> ${incident.road_name}</p>
                  <p><span class="font-semibold">Severity:</span> 
                    <span class="px-2 py-1 rounded" style="background-color: ${color}; color: white;">
                      ${incident.severity}
                    </span>
                  </p>
                  <p><span class="font-semibold">Speed:</span> ${incident.speed_kph.toFixed(1)} km/h 
                    (Normal: ${incident.free_flow_kph.toFixed(1)} km/h)</p>
                  <p><span class="font-semibold">Jam Factor:</span> ${incident.jam_factor.toFixed(1)}/10</p>
                  ${incident.is_closed ? '<p class="text-red-600 font-bold">⛔ Road Closed</p>' : ''}
                </div>
              </div>
            `);
            
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
 * Apply traffic overlay
 * @param {string} mode - 'incidents', 'flow', or 'both'
 * @param {boolean} routeOnly - If true, show traffic only for current route
 * @param {boolean} showMatched - If true, show matched edges; if false, show raw HERE data
 */
function applyTrafficOverlay(mode, routeOnly, showMatched = true) {
  console.log(`Applying Traffic Overlay (mode: ${mode}, routeOnly: ${routeOnly}, showMatched: ${showMatched})`);
  
  // Update state
  trafficVisualization.trafficMode = mode;
  trafficVisualization.showMatched = showMatched;
  
  if (showMatched) {
    // Clear raw traffic layer if it exists
    if (trafficVisualization.rawTrafficLayer) {
      trafficVisualization.rawTrafficLayer.clearLayers();
    }
    
    // Show matched edges (existing implementation)
    applyMatchedTrafficOverlay(mode, routeOnly);
  } else {
    // Clear matched traffic layer if it exists
    if (trafficVisualization.trafficOverlayLayer) {
      trafficVisualization.trafficOverlayLayer.clearLayers();
    }
    
    // Show raw HERE traffic data
    applyRawTrafficOverlay(mode);
  }
}

/**
 * Apply matched traffic overlay (original implementation)
 */
function applyMatchedTrafficOverlay(mode, routeOnly) {
  console.log(`Applying Matched Traffic Overlay...`);
  
  // Create layer group if it doesn't exist
  if (!trafficVisualization.trafficOverlayLayer) {
    trafficVisualization.trafficOverlayLayer = L.layerGroup().addTo(map);
  }
  
  // Clear existing overlay
  trafficVisualization.trafficOverlayLayer.clearLayers();
  
  // Load disruptions based on mode
  fetch('/get_active_disruptions')
    .then(response => response.json())
    .then(data => {
      if (!data.success) {
        throw new Error(data.error || 'Failed to load traffic data');
      }
      
      // Filter disruptions by mode and route
      let disruptionsToShow = [];
      
      Object.entries(data.disruptions_by_type).forEach(([type, disruptions]) => {
        disruptions.forEach(d => {
          // Mode filtering
          const isIncident = ['Accident', 'Road Closure', 'Construction', 'Road Hazard'].includes(type);
          const isFlow = type === 'Congestion';
          
          if (mode === 'incidents' && !isIncident) return;
          if (mode === 'flow' && !isFlow) return;
          
          // Route filtering (if enabled and route exists)
          if (routeOnly && trafficVisualization.currentRoute) {
            // Check if disruption segment is on current route
            // This is simplified - ideally would check actual route path
            const onRoute = isSegmentOnRoute(
              d.source_id, d.target_id, 
              trafficVisualization.currentRoute
            );
            if (!onRoute) return;
          }
          
          disruptionsToShow.push(d);
        });
      });
      
      // Visualize traffic as colored road segments
      disruptionsToShow.forEach(disruption => {
        // Color based on severity
        let color, opacity, weight;
        
        if (disruption.is_closed) {
          color = '#000000';
          opacity = 0.9;
          weight = 6;
        } else {
          switch (disruption.severity) {
            case 'Heavy':
              color = '#ef4444';
              opacity = 0.8;
              weight = 5;
              break;
            case 'Medium':
              color = '#f59e0b';
              opacity = 0.7;
              weight = 4;
              break;
            default:
              color = '#10b981';
              opacity = 0.6;
              weight = 3;
          }
        }
        
        const segment = L.polyline([
          [disruption.source_lat, disruption.source_lng],
          [disruption.target_lat, disruption.target_lng]
        ], {
          color: color,
          weight: weight,
          opacity: opacity
        });
        
        segment.bindPopup(`
          <div class="p-2">
            <p class="font-bold">${disruption.road_name}</p>
            <p class="text-xs">Severity: ${disruption.severity}</p>
            <p class="text-xs">Speed: ${disruption.speed_kph.toFixed(0)} km/h</p>
            <p class="text-xs">Jam Factor: ${disruption.jam_factor.toFixed(1)}/10</p>
          </div>
        `);
        
        trafficVisualization.trafficOverlayLayer.addLayer(segment);
      });
      
      console.log(`✅ Traffic overlay applied (${disruptionsToShow.length} segments)`);
    })
    .catch(error => {
      console.error('Error applying traffic overlay:', error);
      showUpdateToast('Error applying traffic overlay', 'error');
    });
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
  if (trafficVisualization.rawTrafficLayer) {
    trafficVisualization.rawTrafficLayer.clearLayers();
    map.removeLayer(trafficVisualization.rawTrafficLayer);
    trafficVisualization.rawTrafficLayer = null;
  }
  console.log('Traffic Overlay cleared');
}

/**
 * Apply raw HERE traffic overlay (non-matched to OSM edges)
 * @param {string} mode - 'incidents', 'flow', or 'both'
 */
function applyRawTrafficOverlay(mode) {
  console.log(`Applying Raw HERE Traffic Overlay (mode: ${mode})...`);
  
  // Create layer group if it doesn't exist
  if (!trafficVisualization.rawTrafficLayer) {
    trafficVisualization.rawTrafficLayer = L.layerGroup().addTo(map);
  }
  
  // Clear existing overlay
  trafficVisualization.rawTrafficLayer.clearLayers();
  
  // Fetch raw HERE traffic data
  fetch('/get_raw_here_traffic')
    .then(response => response.json())
    .then(data => {
      if (!data.success) {
        throw new Error(data.error || 'Failed to load raw traffic data');
      }
      
      let segmentsAdded = 0;
      
      // Process flow segments
      if (mode === 'flow' || mode === 'both') {
        data.data.flow_segments.forEach(segment => {
          // Color based on severity
          let color, opacity, weight;
          
          switch (segment.severity) {
            case 'Heavy':
              color = '#ef4444';
              opacity = 0.8;
              weight = 5;
              break;
            case 'Medium':
              color = '#f59e0b';
              opacity = 0.7;
              weight = 4;
              break;
            default:
              color = '#10b981';
              opacity = 0.6;
              weight = 3;
          }
          
          const polyline = L.polyline(segment.coordinates, {
            color: color,
            weight: weight,
            opacity: opacity
          });
          
          polyline.bindPopup(`
            <div class="p-3">
              <h3 class="font-bold text-lg mb-2">🚦 ${segment.description}</h3>
              <div class="space-y-1 text-sm">
                <p><span class="font-semibold">Type:</span> <span class="text-purple-600">Raw Flow Data (Non-matched)</span></p>
                <p><span class="font-semibold">Severity:</span> 
                  <span class="px-2 py-1 rounded" style="background-color: ${color}; color: white;">
                    ${segment.severity}
                  </span>
                </p>
                <p><span class="font-semibold">Speed:</span> ${segment.speed_kph.toFixed(1)} km/h</p>
                <p><span class="font-semibold">Free Flow:</span> ${segment.free_flow_kph.toFixed(1)} km/h</p>
                <p><span class="font-semibold">Jam Factor:</span> ${segment.jam_factor.toFixed(1)}/10</p>
                <p><span class="font-semibold">Confidence:</span> ${(segment.confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
          `);
          
          trafficVisualization.rawTrafficLayer.addLayer(polyline);
          segmentsAdded++;
        });
      }
      
      // Process incidents
      if (mode === 'incidents' || mode === 'both') {
        data.data.incidents.forEach(incident => {
          // Color based on severity
          let color, opacity, weight;
          
          if (incident.road_closed) {
            color = '#000000';
            opacity = 0.9;
            weight = 6;
          } else {
            switch (incident.severity) {
              case 'Heavy':
                color = '#ef4444';
                opacity = 0.8;
                weight = 5;
                break;
              case 'Medium':
                color = '#f59e0b';
                opacity = 0.7;
                weight = 4;
                break;
              default:
                color = '#10b981';
                opacity = 0.6;
                weight = 3;
            }
          }
          
          const polyline = L.polyline(incident.coordinates, {
            color: color,
            weight: weight,
            opacity: opacity,
            dashArray: '5, 10'  // Dashed line for incidents
          });
          
          // Get icon for incident type
          const icons = {
            'accident': '🚗',
            'construction': '🏗️',
            'congestion': '🚦',
            'disabledVehicle': '🚙',
            'massTransit': '🚇',
            'plannedEvent': '📅',
            'roadHazard': '⚠️',
            'roadClosure': '🚧',
            'weather': '🌧️',
            'laneRestriction': '⚠️',
            'other': '📍'
          };
          
          const icon = icons[incident.type] || '📍';
          
          polyline.bindPopup(`
            <div class="p-3">
              <div class="flex items-center mb-2">
                <span class="text-2xl mr-2">${icon}</span>
                <h3 class="font-bold text-lg">${incident.type}</h3>
              </div>
              <div class="space-y-1 text-sm">
                <p><span class="font-semibold">Description:</span> ${incident.description}</p>
                <p><span class="font-semibold">Type:</span> <span class="text-purple-600">Raw Incident Data (Non-matched)</span></p>
                <p><span class="font-semibold">Severity:</span> 
                  <span class="px-2 py-1 rounded" style="background-color: ${color}; color: white;">
                    ${incident.severity}
                  </span>
                </p>
                <p><span class="font-semibold">Criticality:</span> ${incident.criticality}</p>
                ${incident.road_closed ? '<p class="text-red-600 font-bold">⛔ Road Closed</p>' : ''}
                ${incident.start_time ? `<p class="text-xs text-gray-600">Start: ${new Date(incident.start_time).toLocaleString()}</p>` : ''}
              </div>
            </div>
          `);
          
          trafficVisualization.rawTrafficLayer.addLayer(polyline);
          segmentsAdded++;
        });
      }
      
      console.log(`✅ Raw traffic overlay applied (${segmentsAdded} segments)`);
      showUpdateToast(`Showing ${segmentsAdded} raw HERE traffic segments`, 'info');
    })
    .catch(error => {
      console.error('Error applying raw traffic overlay:', error);
      showUpdateToast('Error applying raw traffic overlay', 'error');
    });
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
window.updateCurrentRoute = updateCurrentRoute;
