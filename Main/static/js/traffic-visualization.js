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
  trafficMode: 'both' // 'incidents', 'flow', or 'both'
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
 * Apply traffic overlay with full OSM road geometries
 * @param {string} mode - 'incidents', 'flow', or 'both'
 * @param {boolean} routeOnly - If true, show traffic only for current route
 */
function applyTrafficOverlay(mode, routeOnly) {
  console.log(`Applying Traffic Overlay (mode: ${mode}, routeOnly: ${routeOnly})`);
  
  // Update state
  trafficVisualization.trafficMode = mode;
  
  // Clear existing overlay
  if (trafficVisualization.trafficOverlayLayer) {
    trafficVisualization.trafficOverlayLayer.clearLayers();
  }
  
  // Always show matched edges with full OSM road geometries
  applyMatchedTrafficWithGeometry(mode, routeOnly);
}

/**
 * Apply matched traffic overlay with full OSM road geometries
 * Uses the new hash-based matching system with LineString geometries
 */
function applyMatchedTrafficWithGeometry(mode, routeOnly) {
  console.log(`🗺️  Loading traffic with OSM geometries...`);
  
  // Create layer group if it doesn't exist
  if (!trafficVisualization.trafficOverlayLayer) {
    trafficVisualization.trafficOverlayLayer = L.layerGroup().addTo(map);
  }
  
  // Clear existing overlay
  trafficVisualization.trafficOverlayLayer.clearLayers();
  
  // Fetch traffic with geometry
  fetch('/get_traffic_with_geometry')
    .then(response => response.json())
    .then(data => {
      if (!data.success) {
        throw new Error(data.error || 'Failed to load traffic data');
      }
      
      console.log(`   📊 Received ${data.total_segments} traffic segments with geometry`);
      
      if (data.segments && data.segments.length > 0) {
        console.log(`   🔍 Sample segment:`, data.segments[0]);
      }
      
      let displayedCount = 0;
      
      // Process each traffic segment
      data.segments.forEach(segment => {
        try {
          // Mode filtering
          const isIncident = segment.type === 'incident';
          const isFlow = segment.type === 'flow';
          
          if (mode === 'incidents' && !isIncident) return;
          if (mode === 'flow' && !isFlow) return;
          
          // Route filtering (if enabled and route exists)
          if (routeOnly && trafficVisualization.currentRoute) {
            const onRoute = isSegmentOnRoute(
              segment.source,
              segment.target,
              trafficVisualization.currentRoute
            );
            if (!onRoute) return;
          }
          
          // Get color and style based on severity
          let color, opacity, weight;
          
          if (segment.is_closed) {
            color = '#000000';  // Black for closed roads
            opacity = 0.9;
            weight = 7;
          } else {
            switch (segment.severity) {
              case 'Heavy':
                color = '#ef4444';  // Red
                opacity = 0.85;
                weight = 6;
                break;
              case 'Medium':
                color = '#f59e0b';  // Orange
                opacity = 0.75;
                weight = 5;
                break;
              default:  // Light
                color = '#10b981';  // Green
                opacity = 0.65;
                weight = 4;
            }
          }
          
          // Parse geometry coordinates
          // Geometry is [[lat, lon], [lat, lon], ...] format from OSM edges CSV
          // Leaflet expects [lat, lng] so we can use it directly
          if (!segment.geometry || !Array.isArray(segment.geometry) || segment.geometry.length < 2) {
            console.warn(`   ⚠️  Skipping segment with invalid geometry:`, segment);
            return;
          }
          
          const latlngs = segment.geometry;
          
          console.log(`   🔍 Plotting segment on ${segment.road_name}: ${latlngs.length} points, severity: ${segment.severity}`);
          
          // Create polyline with geometry
          const polyline = L.polyline(latlngs, {
            color: color,
            weight: weight,
            opacity: opacity,
            className: `traffic-segment traffic-${segment.severity.toLowerCase()}`
          });
          
          // Get icon for incident type
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
          
          const icon = incidentIcons[segment.incident_type] || '📍';
          
          // Create popup with detailed info
          const popup = `
            <div class="p-3 min-w-[250px]">
              <div class="flex items-center mb-2">
                <span class="text-2xl mr-2">${icon}</span>
                <h3 class="font-bold text-lg">${segment.incident_type}</h3>
              </div>
              <div class="space-y-1 text-sm">
                <p><span class="font-semibold">Road:</span> ${segment.road_name}</p>
                <p><span class="font-semibold">Type:</span> ${segment.highway_type}</p>
                <p><span class="font-semibold">Severity:</span> 
                  <span class="px-2 py-1 rounded text-white" style="background-color: ${color};">
                    ${segment.severity}
                  </span>
                </p>
                <p><span class="font-semibold">Speed:</span> ${segment.speed_kph.toFixed(1)} km/h 
                  <span class="text-gray-500">(Free flow: ${segment.free_flow_kph.toFixed(1)} km/h)</span>
                </p>
                <p><span class="font-semibold">Jam Factor:</span> ${segment.jam_factor.toFixed(1)}/10</p>
                <p><span class="font-semibold">Length:</span> ${segment.length.toFixed(0)}m</p>
                ${segment.is_closed ? '<p class="text-red-600 font-bold mt-2">⛔ ROAD CLOSED</p>' : ''}
                ${segment.description ? `<p class="text-xs text-gray-600 mt-2">${segment.description}</p>` : ''}
                <p class="text-xs text-teal-600 mt-2">✅ Matched to OSM network with geometry</p>
              </div>
            </div>
          `;
          
          polyline.bindPopup(popup);
          
          // Add hover effect
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
      
      if (displayedCount > 0) {
        showUpdateToast(`Showing ${displayedCount} traffic segments with road geometries`, 'success');
      } else {
        showUpdateToast('No traffic data to display for current filters', 'info');
      }
    })
    .catch(error => {
      console.error('Error applying traffic overlay:', error);
      showUpdateToast('Error loading traffic overlay', 'error');
    });
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
