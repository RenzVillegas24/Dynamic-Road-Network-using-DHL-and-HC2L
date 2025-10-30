
// Function to show update toast messages
function showUpdateToast(message, type = 'info') {
    const toast = document.getElementById("update-toast");
    const msg = document.getElementById("update-toast-message");

    toast.classList.remove("border-orange-500", "text-orange-700", "border-emerald-500", "text-emerald-700", "border-blue-500", "text-blue-700");

    toast.classList.remove("hidden");
    msg.textContent = message;

    if (type === 'warning') {
        toast.classList.add("border-orange-500", "text-orange-700");
    } else if (type === 'success') {
        toast.classList.add("border-emerald-500", "text-emerald-700");
    } else {
        toast.classList.add("border-blue-500", "text-blue-700");
    }

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 4000);
}

// Function to trigger Immediate Update (simulated)
// function simulateRouteComputation() {
//     const disruptionDetected = true;
//     const impactScore = 0.65;

//     if (disruptionDetected && impactScore >= currentThreshold) {
//         triggerImmediateUpdate();
//         showUpdateToast("Immediate Update triggered: labels refreshed.", 'warning');
//     } else {
//         triggerLazyUpdate();
//         showUpdateToast("Lazy Update: labels will be repaired when queried.", 'success');
//     }
// }

// Function to clear routes and reset related UI components
function clearRoutes() {
    console.log('Clearing routes...');

    // Clear existing route polylines
    if (routePolylines && routePolylines.length > 0) {
        routePolylines.forEach(polyline => {
        if (polyline && polyline.setMap) {
            polyline.setMap(null);
        }
        });
        routePolylines = [];
        console.log('Cleared', routePolylines.length, 'route polylines');
    }

    // Clear current route data
    currentRouteData = null;

    // Reset Current Path Panel to placeholder
    resetCurrentPathPanel();

    // Reset bottom info bar
    resetBottomInfoBar();

    // We don't need to clear DirectionsRenderer since we're only using D-HC2L polylines
    // The DirectionsRenderer should remain untouched to avoid the travelMode error

    console.log('D-HC2L route clearing complete');
}

// Function to reset the Bottom Information Bar
function resetBottomInfoBar() {
    const etaElement = document.getElementById('bottom-info-eta');
    const distanceElement = document.getElementById('bottom-info-distance');
    const metricLabelElement = document.getElementById('bottom-info-metric-label');
    const metricValueElement = document.getElementById('bottom-info-metric-value');

    if (etaElement) {
        etaElement.textContent = '--';
        etaElement.classList.remove('text-slate-800');
        etaElement.classList.add('text-slate-400');
    }

    if (distanceElement) {
        distanceElement.textContent = '--';
        distanceElement.classList.remove('text-slate-800');
        distanceElement.classList.add('text-slate-400');
    }

    if (metricLabelElement) {
        metricLabelElement.textContent = 'Query Time';
    }

    if (metricValueElement) {
        metricValueElement.textContent = '--';
        metricValueElement.classList.remove('text-slate-800');
        metricValueElement.classList.add('text-slate-400');
    }

    // Reset Fréchet distance and segment overlap
    resetComparisonMetrics();

    console.log('📊 Bottom info bar reset');
}

// Function to clear the distruption markers from the map
function clearDisruptionMarkers() {
    disruptionMarkers.forEach(marker => {
        marker.setMap(null);
    });
    disruptionMarkers = [];
}

// Function to get selected algorithm from admin panel
function getSelectedAlgorithm() {
    const selectedRadio = document.querySelector('input[name="algo-dataset"]:checked');
    return selectedRadio ? selectedRadio.value : 'dhc2l-base';
}

// Function to update the Alternative Route UI based on current state
function updateAlternativeRouteUI() {
    // Update the alternative route details to show it's now active
    const altRouteToggle = document.getElementById('alt-route-toggle');
    const altRouteDetails = document.getElementById('alt-route-details');

    if (useDisruptions) {
        // Show that alternative route is now active
        altRouteToggle.innerHTML = `
        <div class="flex items-center">
            <div class="bg-gradient-to-br from-emerald-600 to-green-600 rounded-xl p-2 mr-3">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path>
            </svg>
            </div>
            <span class="font-bold text-emerald-900">Using Alternative Route</span>
        </div>
        <svg id="alt-route-chevron" class="w-6 h-6 text-emerald-600 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"></path>
        </svg>
        `;
        altRouteToggle.className = "w-full bg-gradient-to-br from-emerald-50 to-green-50 border-2 border-emerald-300 rounded-2xl p-4 mb-5 flex items-center justify-between transition-all duration-300 shadow-md";
        
        // Update the button inside alt-route-details to "Switch to Normal Route"
        setTimeout(() => {
        const switchButton = altRouteDetails.querySelector('button');
        if (switchButton) {
            switchButton.innerHTML = 'Switch to Normal Route';
            switchButton.className = "w-full bg-gradient-to-r from-slate-600 to-slate-700 hover:from-slate-700 hover:to-slate-800 text-white py-3 rounded-xl font-bold text-sm shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105";
        }
        }, 100);
        
    } else {
        // Restore original appearance for normal route
        altRouteToggle.innerHTML = `
        <div class="flex items-center">
            <div class="bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl p-2 mr-3">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>
            </svg>
            </div>
            <span class="font-bold text-blue-900">View Alternate Route</span>
        </div>
        <svg id="alt-route-chevron" class="w-6 h-6 text-blue-600 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"></path>
        </svg>
        `;
        altRouteToggle.className = "w-full bg-gradient-to-br from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 border-2 border-blue-300 rounded-2xl p-4 mb-5 flex items-center justify-between transition-all duration-300 shadow-md hover:shadow-lg";
        
        // Update the button inside alt-route-details back to "Switch to This Route"
        setTimeout(() => {
        const switchButton = altRouteDetails.querySelector('button');
        if (switchButton) {
            switchButton.innerHTML = 'Switch to This Route';
            switchButton.className = "w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white py-3 rounded-xl font-bold text-sm shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105";
        }
        }, 100);
    }
}

// function triggerImmediateUpdate() {
//     updateModeBadge.textContent = "Immediate Update";
//     updateModeBadge.className = "px-4 py-2 bg-orange-500 text-white rounded-xl text-sm font-bold shadow-md";
//     alertBanner.classList.remove("hidden");
    
//     document.getElementById("incident-type").textContent = "Accident";
//     document.getElementById("severity-level").textContent = "Heavy";
//     document.getElementById("incident-location").textContent = "EDSA";
//     document.getElementById("eta-time").textContent = "22 min";
//     document.getElementById("eta-delay").textContent = "(+4 min)";
// }
  
// function triggerLazyUpdate() {
//     updateModeBadge.textContent = "Lazy Update";
//     updateModeBadge.className = "px-4 py-2 bg-emerald-500 text-white rounded-xl text-sm font-bold shadow-md";
//     alertBanner.classList.add("hidden");
// }

  
function updateDisruptionsPanel(disruptionData) {
    // Find the disruptions content container
    const disruptionsContainer = document.querySelector('#disruptions-panel .p-6.space-y-4');
    if (!disruptionsContainer) return;

    // Clear existing content
    disruptionsContainer.innerHTML = '';

    // Add summary stats
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'bg-gradient-to-br from-slate-50 to-gray-50 border border-slate-200 rounded-2xl p-4 mb-4';
    summaryDiv.innerHTML = `
        <h3 class="font-bold text-slate-900 text-lg mb-3">Disruption Summary</h3>
        <div class="grid grid-cols-2 gap-3">
        <div class="text-center">
            <div class="text-2xl font-bold text-red-600">${disruptionData.total_disruptions}</div>
            <div class="text-xs text-slate-600">Total Active</div>
        </div>
        <div class="text-center">
            <div class="text-lg font-semibold text-slate-700">
            <span class="text-red-600">${disruptionData.severity_counts.Heavy}</span> / 
            <span class="text-orange-600">${disruptionData.severity_counts.Medium}</span> / 
            <span class="text-green-600">${disruptionData.severity_counts.Light}</span>
            </div>
            <div class="text-xs text-slate-600">Heavy / Medium / Light</div>
        </div>
        </div>
    `;
    disruptionsContainer.appendChild(summaryDiv);

    // Group and display disruptions by type
    const disruptionsByType = disruptionData.disruptions_by_type;

    for (const [incidentType, disruptions] of Object.entries(disruptionsByType)) {
        // Create type header
        const typeHeader = document.createElement('div');
        typeHeader.className = 'flex items-center justify-between py-2 border-b border-slate-200';
        typeHeader.innerHTML = `
        <h4 class="font-bold text-slate-800">${incidentType}</h4>
        <span class="px-2 py-1 bg-slate-200 text-slate-700 rounded-lg text-xs font-bold">${disruptions.length}</span>
        `;
        disruptionsContainer.appendChild(typeHeader);
        
        // Display first few disruptions of this type (limit to avoid overwhelming UI)
        const displayLimit = 3;
        const disruptionsToShow = disruptions.slice(0, displayLimit);
        
        disruptionsToShow.forEach(disruption => {
        const disruptionElement = createDisruptionElement(disruption);
        disruptionsContainer.appendChild(disruptionElement);
        });
        
        // Show "and X more" if there are more disruptions
        if (disruptions.length > displayLimit) {
        const moreDiv = document.createElement('div');
        moreDiv.className = 'text-center py-2 text-sm text-slate-600 italic';
        moreDiv.textContent = `... and ${disruptions.length - displayLimit} more ${incidentType.toLowerCase()} disruptions`;
        disruptionsContainer.appendChild(moreDiv);
        }
    }   
}
  
function createDisruptionElement(disruption) {
    const severityColors = {
      'Heavy': { bg: 'from-red-50 to-rose-50', border: 'border-red-500', icon: 'from-red-500 to-rose-600', badge: 'bg-red-500', text: 'text-red-700' },
      'Medium': { bg: 'from-orange-50 to-amber-50', border: 'border-orange-500', icon: 'from-orange-400 to-red-500', badge: 'bg-orange-500', text: 'text-orange-700' },
      'Light': { bg: 'from-green-50 to-emerald-50', border: 'border-green-500', icon: 'from-green-400 to-emerald-500', badge: 'bg-green-500', text: 'text-green-700' }
    };
    
    const colors = severityColors[disruption.severity] || severityColors['Medium'];
    
    // Calculate delay estimation
    const delayMinutes = Math.round((1 - disruption.slowdown_ratio) * 15); // Rough estimate
    
    const disruptionDiv = document.createElement('div');
    disruptionDiv.className = `bg-gradient-to-br ${colors.bg} border-l-4 ${colors.border} rounded-2xl p-4 hover:shadow-lg transition-all duration-300 mb-3`;
    
    // Get appropriate icon based on incident type
    const getIncidentIcon = (type) => {
      const icons = {
        'Road Closure': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L5.636 5.636"/>',
        'Accident': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z"/>',
        'Construction': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>',
        'Congestion': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>',
        'Default': '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>'
      };
      return icons[type] || icons['Default'];
    };
    
    disruptionDiv.innerHTML = `
      <div class="flex items-start">
        <div class="bg-gradient-to-br ${colors.icon} rounded-xl p-3 mr-4 shadow-md">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            ${getIncidentIcon(disruption.incident_type)}
          </svg>
        </div>
        <div class="flex-1">
          <h3 class="font-bold text-slate-900 text-lg mb-1">${disruption.road_name}</h3>
          <p class="text-sm ${colors.text} font-semibold mb-2">${disruption.incident_type} • ~${delayMinutes} min delay</p>
          <div class="flex items-center justify-between">
            <div class="text-xs text-slate-600">
              <div>Speed: ${disruption.speed_kph.toFixed(1)} km/h (${Math.round(disruption.slowdown_ratio * 100)}% of normal)</div>
              <div>Jam Factor: ${disruption.jam_factor.toFixed(1)}</div>
            </div>
            <span class="px-3 py-1 ${colors.badge} text-white rounded-lg text-xs font-bold">${disruption.severity}</span>
          </div>
        </div>
      </div>
    `;
    
    // Add click handler to show location on map
    disruptionDiv.addEventListener('click', () => {
      showDisruptionOnMap(disruption);
    });
    disruptionDiv.style.cursor = 'pointer';
    
    return disruptionDiv;
}
  
function showDisruptionOnMap(disruption) {
    if (!map) {
      showUpdateToast("Map not available", 'warning');
      return;
    }
    
    // Calculate center point of the disrupted segment
    const centerLat = (disruption.source_lat + disruption.target_lat) / 2;
    const centerLng = (disruption.source_lng + disruption.target_lng) / 2;
    
    // Center map on the disruption
    map.setCenter({ lat: centerLat, lng: centerLng });
    map.setZoom(16);
    
    // Create a temporary marker to highlight the disruption
    const marker = new google.maps.Marker({
      position: { lat: centerLat, lng: centerLng },
      map: map,
      title: `${disruption.incident_type} on ${disruption.road_name}`,
      icon: {
        url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
          <svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="12" fill="${disruption.severity === 'Heavy' ? '#ef4444' : disruption.severity === 'Medium' ? '#f59e0b' : '#10b981'}" stroke="white" stroke-width="2"/>
            <text x="16" y="20" text-anchor="middle" fill="white" font-size="12" font-weight="bold">!</text>
          </svg>
        `)}`,
        scaledSize: new google.maps.Size(32, 32)
      }
    });
    
    // Remove marker after 5 seconds
    setTimeout(() => {
      marker.setMap(null);
    }, 5000);
    
    // Close disruptions panel to see the map
    disruptionsPanel.classList.add("translate-x-full");
    
    showUpdateToast(`Showing ${disruption.incident_type} on ${disruption.road_name}`, 'info');
}
  
function showAllDisruptionsOnMap(disruptionData) {
    if (!map) return;
    
    // Clear existing disruption markers
    clearDisruptionMarkers();
    
    // Add markers for each disruption type
    for (const [incidentType, disruptions] of Object.entries(disruptionData.disruptions_by_type)) {
      // Limit markers to prevent performance issues (show max 50 per type)
      const markersToShow = disruptions.slice(0, 50);
      
      markersToShow.forEach(disruption => {
        const centerLat = (disruption.source_lat + disruption.target_lat) / 2;
        const centerLng = (disruption.source_lng + disruption.target_lng) / 2;
        
        // Get color based on severity
        const markerColor = disruption.severity === 'Heavy' ? '#ef4444' : 
                           disruption.severity === 'Medium' ? '#f59e0b' : '#10b981';
        
        // Get icon based on incident type
        const getMarkerSymbol = (type) => {
          const symbols = {
            'Road Closure': '✖',
            'Accident': '⚠',
            'Construction': '🚧',
            'Congestion': '🚗',
            'Disabled Vehicle': '🔧',
            'Mass Transit Event': '🚌',
            'Planned Event': '📅',
            'Road Hazard': '⚠',
            'Lane Restriction': '🚧',
            'Weather': '🌧'
          };
          return symbols[type] || '!';
        };
        
        const marker = new google.maps.Marker({
          position: { lat: centerLat, lng: centerLng },
          map: map,
          title: `${disruption.incident_type} on ${disruption.road_name}`,
          icon: {
            url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
              <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" fill="${markerColor}" stroke="white" stroke-width="1"/>
                <text x="12" y="16" text-anchor="middle" fill="white" font-size="10" font-weight="bold">${getMarkerSymbol(disruption.incident_type)}</text>
              </svg>
            `)}`,
            scaledSize: new google.maps.Size(24, 24)
          }
        });
        
        // Add info window
        const infoWindow = new google.maps.InfoWindow({
          content: `
            <div class="p-2">
              <h3 class="font-bold text-sm">${disruption.road_name}</h3>
              <p class="text-xs text-gray-600">${disruption.incident_type}</p>
              <p class="text-xs">Severity: <span class="font-semibold" style="color: ${markerColor}">${disruption.severity}</span></p>
              <p class="text-xs">Speed: ${disruption.speed_kph.toFixed(1)} km/h (${Math.round(disruption.slowdown_ratio * 100)}% of normal)</p>
            </div>
          `
        });
        
        marker.addListener('click', () => {
          infoWindow.open(map, marker);
        });
        
        disruptionMarkers.push(marker);
      });
    }
    
    console.log(`Added ${disruptionMarkers.length} disruption markers to map`);
}
  
function updateRouteHeaderMetrics(route, metrics) {
    try {
      // Debug: Log the actual structure of metrics and route
      console.log('Debug - Metrics object:', metrics);
      console.log('Debug - Route object keys:', Object.keys(route));
      console.log('Debug - Road segments:', route.road_segments);
      
      // Try multiple possible field names for distance
      let distanceM = 0;
      let distanceSource = 'unknown';
      
      // Always try to calculate from road segments first (most accurate for display)
      if (route && route.road_segments && route.road_segments.length > 0) {
        let segmentTotal = 0;
        console.log('Calculating distance from road segments:');
        route.road_segments.forEach((segment, index) => {
          const segmentLength = segment.length_meters || segment.length || 0;
          console.log(`  Segment ${index + 1}: ${segment.road_name} = ${segmentLength}m`);
          segmentTotal += segmentLength;
        });
        
        if (segmentTotal > 0) {
          distanceM = segmentTotal;
          distanceSource = 'road_segments';
          console.log('✅ Using distance from road segments:', distanceM, 'meters from', route.road_segments.length, 'segments');
        }
      }
      
      // Fallback to metrics if road segments calculation failed
      if (distanceM === 0) {
        if (metrics && metrics.total_distance_meters && metrics.total_distance_meters > 0) {
          distanceM = metrics.total_distance_meters;
          distanceSource = 'metrics.total_distance_meters';
          console.log('Using total_distance_meters:', distanceM);
        } else if (metrics && metrics.total_distance_m && metrics.total_distance_m > 0) {
          distanceM = metrics.total_distance_m;
          distanceSource = 'metrics.total_distance_m';
          console.log('Using total_distance_m:', distanceM);
        } else if (metrics && metrics.total_distance && metrics.total_distance > 0) {
          distanceM = metrics.total_distance;
          distanceSource = 'metrics.total_distance';
          console.log('Using total_distance:', distanceM);
        }
      }
      
      // Final fallback: estimate from coordinates
      if (distanceM === 0) {
        console.warn('No distance data found in metrics or route segments');
        if (route && route.coordinates && route.coordinates.length >= 2) {
          const start = route.coordinates[0];
          const end = route.coordinates[route.coordinates.length - 1];
          if (start && end && start.lat && start.lng && end.lat && end.lng) {
            distanceM = calculateHaversineDistance(start.lat, start.lng, end.lat, end.lng);
            distanceSource = 'coordinate_estimation';
            console.log('Estimated distance from coordinates:', distanceM);
          }
        }
      }
      
      const distanceKm = (distanceM / 1000).toFixed(1);
      
      console.log(`📏 Final distance calculation: ${distanceM}m (${distanceKm}km) from ${distanceSource}`);
      
      // Estimate duration (simple calculation: 30 km/h average in urban areas)
      const avgSpeedKmh = 30;
      const durationMinutes = Math.round((distanceM / 1000) / avgSpeedKmh * 60);
      
      // Count steps
      const turnDirections = route.turn_by_turn_directions || [];
      const stepCount = turnDirections.length;
      
      // Update distance metric
      const distanceElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-emerald-600');
      if (distanceElement) {
        distanceElement.textContent = `${distanceKm} km`;
        console.log('✅ Updated distance element with:', `${distanceKm} km`);
      } else {
        console.error('❌ Distance element not found with selector: #current-path-panel .text-xl.font-bold.text-emerald-600');
        // Try alternative selector
        const allDistanceElements = document.querySelectorAll('.text-xl.font-bold.text-emerald-600');
        console.log('Found distance elements:', allDistanceElements.length);
        if (allDistanceElements.length > 0) {
          allDistanceElements[0].textContent = `${distanceKm} km`;
          console.log('✅ Updated first distance element as fallback');
        }
      }
      
      // Update duration metric
      const durationElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-blue-600');
      if (durationElement) {
        durationElement.textContent = `${durationMinutes} min`;
        console.log('✅ Updated duration element with:', `${durationMinutes} min`);
      } else {
        console.error('❌ Duration element not found with selector: #current-path-panel .text-xl.font-bold.text-blue-600');
        // Try alternative selector
        const allDurationElements = document.querySelectorAll('.text-xl.font-bold.text-blue-600');
        console.log('Found duration elements:', allDurationElements.length);
        if (allDurationElements.length > 0) {
          allDurationElements[0].textContent = `${durationMinutes} min`;
          console.log('✅ Updated first duration element as fallback');
        }
      }
      
      // Update steps count
      const stepsElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-purple-600');
      if (stepsElement) {
        stepsElement.textContent = stepCount.toString();
        console.log('✅ Updated steps element with:', stepCount.toString());
      } else {
        console.error('❌ Steps element not found with selector: #current-path-panel .text-xl.font-bold.text-purple-600');
        // Try alternative selector
        const allStepsElements = document.querySelectorAll('.text-xl.font-bold.text-purple-600');
        console.log('Found steps elements:', allStepsElements.length);
        if (allStepsElements.length > 0) {
          allStepsElements[0].textContent = stepCount.toString();
          console.log('✅ Updated first steps element as fallback');
        }
      }
      
      console.log(`Route metrics updated: ${distanceKm}km, ${durationMinutes}min, ${stepCount} steps`);
      
    } catch (error) {
      console.error('Error updating route header metrics:', error);
    }
}
  
function calculateHaversineDistance(lat1, lng1, lat2, lng2) {
    const R = 6371000; // Earth's radius in meters
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}
  
function updateRouteSteps(route) {
    try {
      const turnDirections = route.turn_by_turn_directions || [];
      const roadSegments = route.road_segments || [];
      
      if (turnDirections.length === 0) {
        console.warn('No turn-by-turn directions available');
        return;
      }
      
      // Find the route steps container
      const stepsContainer = document.querySelector('#current-path-panel .space-y-4.max-h-96.overflow-y-auto');
      if (!stepsContainer) {
        console.error('Route steps container not found');
        return;
      }
      
      // Hide placeholder
      const placeholder = document.getElementById('route-steps-placeholder');
      if (placeholder) {
        placeholder.style.display = 'none';
      }
      
      // Clear existing steps (except placeholder)
      const existingSteps = stepsContainer.querySelectorAll('.flex.gap-4.items-start');
      existingSteps.forEach(step => step.remove());
      
      // Add each direction as a step
      turnDirections.forEach((direction, index) => {
        const stepNumber = index + 1;
        const isLastStep = index === turnDirections.length - 1;
        
        // Get corresponding road segment for additional info
        const roadSegment = roadSegments[index] || {};
        const roadName = roadSegment.road_name || 'Unknown Road';
        const distance = roadSegment.length_meters || 0;
        
        // Create step element
        const stepElement = createRouteStepElement(stepNumber, direction, roadName, distance, isLastStep);
        stepsContainer.appendChild(stepElement);
      });
      
      console.log(`Added ${turnDirections.length} route steps to Current Path Panel`);
      
    } catch (error) {
      console.error('Error updating route steps:', error);
    }
}
  
function createRouteStepElement(stepNumber, instruction, roadName, distanceMeters, isLastStep) {
    const stepDiv = document.createElement('div');
    stepDiv.className = 'flex gap-4 items-start';
    
    // Determine step colors
    const stepColors = isLastStep 
      ? 'bg-gradient-to-br from-rose-500 to-red-600 text-white'
      : 'bg-gradient-to-br from-emerald-500 to-green-600 text-white';
    
    const contentColors = isLastStep
      ? 'bg-gradient-to-br from-rose-50 to-red-50 border-2 border-rose-300'
      : 'bg-slate-50 border border-slate-200';
    
    const distanceColor = isLastStep ? 'text-rose-600' : 'text-emerald-600';
    
    // Clean up instruction text (remove step numbers if present)
    const cleanInstruction = instruction.replace(/^\d+\.\s*/, '');
    
    // Format distance
    const distanceText = distanceMeters > 0 ? `${(distanceMeters / 1000).toFixed(1)} km` : '';
    
    stepDiv.innerHTML = `
      <div class="${stepColors} w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm flex-shrink-0 shadow-md">
        ${stepNumber}
      </div>
      <div class="flex-1 ${contentColors} rounded-xl p-3">
        <div class="text-sm text-slate-900 font-semibold mb-1">${cleanInstruction}</div>
        <div class="text-xs text-slate-600 font-medium">
          ${roadName} 
          ${distanceText ? `<span class="${distanceColor} ml-2 font-bold">${distanceText}</span>` : ''}
        </div>
      </div>
    `;
    
    return stepDiv;
}
  
function updateComparisonMetrics(routeData) {
    try {
      // Check algorithm type to determine behavior
      const metrics = routeData.metrics || {};
      const algorithm = routeData.algorithm || metrics.algorithm || 'Unknown';
      
      // Check if algorithm is Comparison mode - if so, set metrics to "--"
      if (algorithm.includes('Comparison')) {
        console.log('Comparison mode detected - setting Fréchet distance and segment overlap to "--"');
        
        // Set Fréchet Distance to "--" for Comparison mode
        const frechetElement = document.getElementById('frechet-distance-value');
        if (frechetElement) {
          frechetElement.textContent = '--';
          frechetElement.classList.remove('text-slate-800');
          frechetElement.classList.add('text-slate-400');
        }
        
        // Also update the old selector for backwards compatibility
        const frechetElementOld = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-blue-700');
        if (frechetElementOld) {
          frechetElementOld.textContent = '--';
        }
        
        // Set Segment Overlap to "--" for Comparison mode
        const overlapElement = document.getElementById('segment-overlap-value');
        if (overlapElement) {
          overlapElement.textContent = '--';
          overlapElement.classList.remove('text-slate-800');
          overlapElement.classList.add('text-slate-400');
        }
        
        // Also update the old selector for backwards compatibility
        const overlapElementOld = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-emerald-700');
        if (overlapElementOld) {
          overlapElementOld.textContent = '--';
        }
        
        console.log('✅ Fréchet distance and segment overlap set to "--" for Comparison mode');
        return; // Exit early for Comparison mode
      }
      
      // Check if algorithm is DHL - if so, set metrics to "--"
      if (algorithm.includes('DHL')) {
        console.log('DHL algorithm detected - setting Fréchet distance and segment overlap to "--"');
        
        // Set Fréchet Distance to "--" for DHL
        const frechetElement = document.getElementById('frechet-distance-value');
        if (frechetElement) {
          frechetElement.textContent = '--';
          frechetElement.classList.remove('text-slate-800');
          frechetElement.classList.add('text-slate-400');
        }
        
        // Also update the old selector for backwards compatibility
        const frechetElementOld = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-blue-700');
        if (frechetElementOld) {
          frechetElementOld.textContent = '--';
        }
        
        // Set Segment Overlap to "--" for DHL
        const overlapElement = document.getElementById('segment-overlap-value');
        if (overlapElement) {
          overlapElement.textContent = '--';
          overlapElement.classList.remove('text-slate-800');
          overlapElement.classList.add('text-slate-400');
        }
        
        // Also update the old selector for backwards compatibility
        const overlapElementOld = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-emerald-700');
        if (overlapElementOld) {
          overlapElementOld.textContent = '--';
        }
        
        console.log('✅ Fréchet distance and segment overlap set to "--" for DHL algorithm');
        return; // Exit early for DHL
      }
      
      // For D-HC2L algorithms, compute the metrics as before
      if (window.googleRouteMetadata && routeData) {
        console.log('Computing Fréchet distance for comparison (D-HC2L algorithm)...');
        
        // Get Google Maps route with coordinates
        getGoogleMapsRouteWithCoordinates(startLocation.lat, startLocation.lng, destLocation.lat, destLocation.lng)
          .then(googleRouteWithCoords => {
            const frechetResult = computeDiscreteFrechetDistance(routeData, googleRouteWithCoords);
            
            if (frechetResult.success) {
              // Update Fréchet Distance display
              const frechetElement = document.getElementById('frechet-distance-value');
              if (frechetElement) {
                frechetElement.textContent = `${frechetResult.distance_m} m`;
                frechetElement.classList.remove('text-slate-400');
                frechetElement.classList.add('text-slate-800');
                console.log(`✅ Fréchet distance updated: ${frechetResult.distance_m} m`);
              }
              
              // Also update the old selector for backwards compatibility
              const frechetElementOld = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-blue-700');
              if (frechetElementOld) {
                frechetElementOld.textContent = `${frechetResult.distance_m} m`;
              }
            } else {
              console.warn('Failed to compute Fréchet distance:', frechetResult.error);
              // Show error state
              const frechetElement = document.getElementById('frechet-distance-value');
              if (frechetElement) {
                frechetElement.textContent = 'Error';
              }
            }
            
            // Compute Segment Overlap
            console.log('Computing segment overlap for comparison...');
            const overlapResult = computeSegmentOverlap(routeData, googleRouteWithCoords);
            
            if (overlapResult.success) {
              // Update Segment Overlap display
              const overlapElement = document.getElementById('segment-overlap-value');
              if (overlapElement) {
                overlapElement.textContent = overlapResult.overlap_percentage_formatted;
                overlapElement.classList.remove('text-slate-400');
                overlapElement.classList.add('text-slate-800');
                console.log(`✅ Segment overlap updated: ${overlapResult.overlap_percentage_formatted}`);
              }
              
              // Also update the old selector for backwards compatibility
              const overlapElementOld = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-emerald-700');
              if (overlapElementOld) {
                overlapElementOld.textContent = overlapResult.overlap_percentage_formatted;
              }
            } else {
              console.warn('Failed to compute segment overlap:', overlapResult.error);
              // Show error state
              const overlapElement = document.getElementById('segment-overlap-value');
              if (overlapElement) {
                overlapElement.textContent = 'Error';
              }
            }
          })
          .catch(error => {
            console.error('Error getting Google Maps route for Fréchet computation:', error);
            const frechetElement = document.getElementById('frechet-distance-value');
            if (frechetElement) {
              frechetElement.textContent = 'N/A';
            }
            const overlapElement = document.getElementById('segment-overlap-value');
            if (overlapElement) {
              overlapElement.textContent = 'N/A';
            }
          });
      } else {
        // No Google Maps data available, show placeholder
        const frechetElement = document.getElementById('frechet-distance-value');
        if (frechetElement) {
          frechetElement.textContent = '-- m';
        }
        const overlapElement = document.getElementById('segment-overlap-value');
        if (overlapElement) {
          overlapElement.textContent = '--%';
        }
        console.log('No Google Maps route data available for comparison metrics computation');
      }
      
    } catch (error) {
      console.error('Error updating comparison metrics:', error);
    }
}

// Function to reset Fréchet distance display
function resetFrechetDistance() {
    const frechetElement = document.getElementById('frechet-distance-value');
    if (frechetElement) {
        frechetElement.textContent = '-- m';
    }
}

// Function to reset comparison metrics display
function resetComparisonMetrics() {
    const frechetElement = document.getElementById('frechet-distance-value');
    if (frechetElement) {
        frechetElement.textContent = '--';
        frechetElement.classList.remove('text-slate-800');
        frechetElement.classList.add('text-slate-400');
    }
    
    const overlapElement = document.getElementById('segment-overlap-value');
    if (overlapElement) {
        overlapElement.textContent = '--';
        overlapElement.classList.remove('text-slate-800');
        overlapElement.classList.add('text-slate-400');
    }
}

  // DHL Route Display Functions
function displayDHLRoute(routeData) {
    console.log('Displaying DHL route:', routeData);
    
    // Clear existing routes first
    clearRoutes();
    
    if (!routeData.success || !routeData.route) {
      console.error('Invalid DHL route data:', routeData);
      return;
    }
    
    const route = routeData.route;
    
    // Display route polylines on map
    if (route.polylines && route.polylines.length > 0) {
      route.polylines.forEach(polylineData => {
        // Handle both internal format (coordinates) and Google Maps format (path)
        let pathCoords;
        if (polylineData.path) {
          // Google Maps format from Flask server
          pathCoords = polylineData.path;
        } else if (polylineData.coordinates) {
          // Internal format
          pathCoords = polylineData.coordinates.map(coord => ({lat: coord[0], lng: coord[1]}));
        } else {
          console.warn('No valid path or coordinates found in polyline data:', polylineData);
          return;
        }
        
        const polyline = new google.maps.Polyline({
          path: pathCoords,
          geodesic: polylineData.geodesic || true,
          strokeColor: polylineData.strokeColor || polylineData.color || '#0066FF', // Blue for DHL
          strokeOpacity: polylineData.strokeOpacity || polylineData.opacity || 0.8,
          strokeWeight: polylineData.strokeWeight || polylineData.weight || 5
        });
        
        polyline.setMap(map);
        routePolylines.push(polyline);
      });
      
      console.log(`✅ Added ${route.polylines.length} DHL polylines to map`);
    } else if (route.coordinates && route.coordinates.length >= 2) {
      // Fallback: Create polyline directly from coordinates if polylines array is missing
      console.log('Creating DHL polyline from coordinates array');
      const pathCoords = route.coordinates.map(coord => ({
        lat: coord.lat, 
        lng: coord.lng
      }));
      
      const polyline = new google.maps.Polyline({
        path: pathCoords,
        geodesic: true,
        strokeColor: '#0066FF', // Blue for DHL
        strokeOpacity: 0.8,
        strokeWeight: 5
      });
      polyline.setMap(map);
      routePolylines.push(polyline);
      
      console.log(`✅ Created DHL polyline from ${route.coordinates.length} coordinates`);
    } else {
      console.warn('No valid polyline data or coordinates found in DHL route');
    }
    
    // Add connector polylines from pinned locations to route start/end nodes
    addDHLConnectorPolylines(routeData);
    
    // Fit map to show the route (including connectors)
    if (routePolylines.length > 0) {
      const bounds = new google.maps.LatLngBounds();
      
      // Add route points to bounds
      routePolylines.forEach(polyline => {
        const path = polyline.getPath();
        path.forEach(point => bounds.extend(point));
      });
      
      // Add pinned locations to bounds
      if (startLocation) bounds.extend(startLocation);
      if (destLocation) bounds.extend(destLocation);
      
      map.fitBounds(bounds);
      
      // Ensure reasonable zoom level
      google.maps.event.addListenerOnce(map, 'bounds_changed', () => {
        if (map.getZoom() > 15) map.setZoom(15);
      });
    }
    
    // Update route metrics in bottom info bar
    if (routeData.metrics) {
      updateRouteMetrics(routeData);
    }
}
 

function resetCurrentPathPanel() {
    // Show placeholder in route steps
    const placeholder = document.getElementById('route-steps-placeholder');
    if (placeholder) {
      placeholder.style.display = 'block';
    }
    
    // Clear any dynamic route steps
    const stepsContainer = document.querySelector('#current-path-panel .space-y-4.max-h-96.overflow-y-auto');
    if (stepsContainer) {
      const existingSteps = stepsContainer.querySelectorAll('.flex.gap-4.items-start');
      existingSteps.forEach(step => step.remove());
    }
    
    // Reset metrics to defaults
    const distanceElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-emerald-600');
    if (distanceElement) distanceElement.textContent = '0.0 km';
    
    const durationElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-blue-600');
    if (durationElement) durationElement.textContent = '0 min';
    
    const stepsElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-purple-600');
    if (stepsElement) stepsElement.textContent = '0';
    
    // Hide route disruption alert when resetting
    const alertElement = document.getElementById('route-disruption-alert');
    if (alertElement) {
      alertElement.classList.add('hidden');
    }
    
    console.log('Current Path Panel reset to placeholder state');
}


function highlightDisruptedSegments(disruptedSegments) {
    if (!map) return;
    
    // Clear any existing highlights
    if (window.disruptionHighlights) {
      window.disruptionHighlights.forEach(highlight => highlight.setMap(null));
    }
    window.disruptionHighlights = [];
    
    disruptedSegments.forEach(segment => {
      // Create a visual highlight for each disrupted segment
      const marker = new google.maps.Marker({
        position: { 
          lat: (segment.sourceNode?.lat || 0), 
          lng: (segment.sourceNode?.lng || 0) 
        },
        map: map,
        title: `${segment.incidentType} on ${segment.roadName}`,
        icon: {
          url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
            <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" fill="#ef4444" stroke="white" stroke-width="2"/>
              <text x="12" y="16" text-anchor="middle" fill="white" font-size="10" font-weight="bold">!</text>
            </svg>
          `)}`,
          scaledSize: new google.maps.Size(24, 24)
        },
        animation: google.maps.Animation.BOUNCE
      });
      
      // Stop animation after 3 seconds
      setTimeout(() => {
        marker.setAnimation(null);
      }, 3000);
      
      window.disruptionHighlights.push(marker);
    });
}

  
function displayRouteDisruptionAlert(disruptedSegments) {
    const alertElement = document.getElementById('route-disruption-alert');
    if (!alertElement || !disruptedSegments || disruptedSegments.length === 0) {
      // Hide alert if no disruptions
      if (alertElement) {
        alertElement.classList.add('hidden');
      }
      return;
    }
    
    // Show alert and update content
    alertElement.classList.remove('hidden');
    
    // Get the most severe disruption for the main display
    const severityOrder = { 'Heavy': 3, 'Medium': 2, 'Light': 1 };
    const mostSevere = disruptedSegments.reduce((prev, current) => {
      return severityOrder[current.severity] > severityOrder[prev.severity] ? current : prev;
    });
    
    // Count disruptions by type
    const disruptionCounts = {};
    disruptedSegments.forEach(segment => {
      disruptionCounts[segment.incidentType] = (disruptionCounts[segment.incidentType] || 0) + 1;
    });
    
    // Create description text
    const totalDisruptions = disruptedSegments.length;
    const uniqueRoads = [...new Set(disruptedSegments.map(s => s.roadName))];
    
    let description = '';
    if (totalDisruptions === 1) {
      description = `${mostSevere.roadName} affected by ${mostSevere.incidentType.toLowerCase()}`;
    } else {
      const roadList = uniqueRoads.slice(0, 2).join(', ');
      const remainingRoads = uniqueRoads.length - 2;
      description = `${roadList}${remainingRoads > 0 ? ` and ${remainingRoads} other road${remainingRoads > 1 ? 's' : ''}` : ''} affected by ${totalDisruptions} disruption${totalDisruptions > 1 ? 's' : ''}`;
    }
    
    // Update alert content
    const titleElement = alertElement.querySelector('.text-sm.font-bold.text-red-900');
    const descElement = alertElement.querySelector('.text-xs.text-red-700');
    
    if (titleElement) {
      titleElement.textContent = `${totalDisruptions} Disruption${totalDisruptions > 1 ? 's' : ''} on Route`;
    }
    
    if (descElement) {
      descElement.textContent = description;
    }
    
    // Update severity styling based on most severe disruption
    alertElement.className = alertElement.className.replace(/from-\w+-50 to-\w+-50 border-\w+-500/, '');
    const severityColors = {
      'Heavy': 'from-red-50 to-rose-50 border-red-500',
      'Medium': 'from-orange-50 to-amber-50 border-orange-500', 
      'Light': 'from-yellow-50 to-orange-50 border-yellow-500'
    };
    alertElement.className += ' ' + (severityColors[mostSevere.severity] || severityColors['Heavy']);
    
    // Add click handler to show disruptions
    alertElement.style.cursor = 'pointer';
    alertElement.onclick = () => {
      showRouteDisruptionsDetail(disruptedSegments);
    };
    
    console.log(`Route passes through ${totalDisruptions} disrupted segment(s):`, disruptedSegments);
}
  
function showRouteDisruptionsDetail(disruptedSegments) {
    // Show a detailed modal or toast with all disruptions on the route
    const segmentList = disruptedSegments.map(segment => 
      `• ${segment.roadName} - ${segment.incidentType} (${segment.severity})`
    ).join('\n');
    
    
    showUpdateToast(`Route disruptions:\n${segmentList}`, 'warning');
    
    // Optionally highlight the disrupted segments on the map
    highlightDisruptedSegments(disruptedSegments);
}

// Function to compute discrete Fréchet distance between two routes
function computeDiscreteFrechetDistance(dhc2lRouteData, googleMapsRouteData) {
    try {
        console.log('🧮 Starting Fréchet distance computation...');
        console.log('D-HC2L Route Data:', dhc2lRouteData);
        console.log('Google Maps Route Data:', googleMapsRouteData);
        
        // Extract coordinate arrays from both routes
        const dhc2lCoords = extractDHC2LCoordinates(dhc2lRouteData);
        const googleCoords = extractGoogleMapsCoordinates(googleMapsRouteData);
        
        if (!dhc2lCoords || dhc2lCoords.length === 0) {
            console.warn('❌ Failed to extract D-HC2L coordinates');
            return {
                success: false,
                error: 'Failed to extract D-HC2L coordinates',
                distance: null
            };
        }
        
        if (!googleCoords || googleCoords.length === 0) {
            console.warn('❌ Failed to extract Google Maps coordinates');
            return {
                success: false,
                error: 'Failed to extract Google Maps coordinates',
                distance: null
            };
        }
        
        console.log(`✅ Computing Fréchet distance: D-HC2L (${dhc2lCoords.length} points) vs Google Maps (${googleCoords.length} points)`);
        
        // Validate coordinate data
        const validDhc2l = dhc2lCoords.every(coord => 
            coord && typeof coord.lat === 'number' && typeof coord.lng === 'number' && 
            !isNaN(coord.lat) && !isNaN(coord.lng)
        );
        const validGoogle = googleCoords.every(coord => 
            coord && typeof coord.lat === 'number' && typeof coord.lng === 'number' && 
            !isNaN(coord.lat) && !isNaN(coord.lng)
        );
        
        if (!validDhc2l) {
            console.warn('❌ Invalid D-HC2L coordinate data detected');
            return {
                success: false,
                error: 'Invalid D-HC2L coordinate data',
                distance: null
            };
        }
        
        if (!validGoogle) {
            console.warn('❌ Invalid Google Maps coordinate data detected');
            return {
                success: false,
                error: 'Invalid Google Maps coordinate data',
                distance: null
            };
        }
        
        // Compute discrete Fréchet distance
        const frechetDistance = discreteFrechetDistance(dhc2lCoords, googleCoords);
        
        console.log(`✅ Fréchet distance computed: ${frechetDistance.toFixed(1)}m`);
        
        return {
            success: true,
            distance: frechetDistance,
            dhc2l_points: dhc2lCoords.length,
            google_points: googleCoords.length,
            distance_km: (frechetDistance / 1000).toFixed(3),
            distance_m: frechetDistance.toFixed(1)
        };
        
    } catch (error) {
        console.error('❌ Error computing Fréchet distance:', error);
        return {
            success: false,
            error: error.message,
            distance: null
        };
    }
}

// Helper function to extract coordinates from D-HC2L route data
function extractDHC2LCoordinates(dhc2lRouteData) {
    console.log('🔍 Extracting D-HC2L coordinates from:', dhc2lRouteData);
    
    if (!dhc2lRouteData || !dhc2lRouteData.route) {
        console.warn('❌ Invalid D-HC2L route data structure:', dhc2lRouteData);
        return null;
    }
    
    // Try multiple sources for coordinates
    let coordinates = [];
    
    // First try: direct coordinates array
    if (dhc2lRouteData.route.coordinates && dhc2lRouteData.route.coordinates.length > 0) {
        console.log('✅ Found coordinates array with', dhc2lRouteData.route.coordinates.length, 'points');
        coordinates = dhc2lRouteData.route.coordinates.map(coord => {
            // Handle both object format {lat: x, lng: y} and array format [lat, lng]
            if (typeof coord === 'object' && coord.lat !== undefined && coord.lng !== undefined) {
                return { lat: coord.lat, lng: coord.lng };
            } else if (Array.isArray(coord) && coord.length >= 2) {
                return { lat: coord[0], lng: coord[1] };
            } else {
                console.warn('⚠️ Invalid coordinate format:', coord);
                return null;
            }
        }).filter(coord => coord !== null);
    }
    // Second try: polylines path
    else if (dhc2lRouteData.route.polylines && dhc2lRouteData.route.polylines.length > 0) {
        console.log('✅ Found polylines array with', dhc2lRouteData.route.polylines.length, 'polylines');
        // Extract from first polyline
        const firstPolyline = dhc2lRouteData.route.polylines[0];
        if (firstPolyline.path && firstPolyline.path.length > 0) {
            console.log('✅ Using polyline path with', firstPolyline.path.length, 'points');
            coordinates = firstPolyline.path.map(point => ({
                lat: point.lat,
                lng: point.lng
            }));
        }
    }
    // Third try: road segments with various coordinate formats
    else if (dhc2lRouteData.route.road_segments && dhc2lRouteData.route.road_segments.length > 0) {
        console.log('✅ Found road segments array with', dhc2lRouteData.route.road_segments.length, 'segments');
        // Extract coordinates from road segments
        dhc2lRouteData.route.road_segments.forEach((segment, segIndex) => {
            // Try different coordinate sources in segments
            if (segment.coordinates && segment.coordinates.length > 0) {
                console.log(`  Segment ${segIndex}: found coordinates array with ${segment.coordinates.length} points`);
                segment.coordinates.forEach(coord => {
                    if (typeof coord === 'object' && coord.lat !== undefined && coord.lng !== undefined) {
                        coordinates.push({ lat: coord.lat, lng: coord.lng });
                    } else if (Array.isArray(coord) && coord.length >= 2) {
                        coordinates.push({ lat: coord[0], lng: coord[1] });
                    }
                });
            }
            // Fallback: try to use source/target coordinates
            else if (segment.source_lat !== undefined && segment.source_lng !== undefined) {
                console.log(`  Segment ${segIndex}: using source coordinates`);
                coordinates.push({ lat: segment.source_lat, lng: segment.source_lng });
                if (segment.target_lat !== undefined && segment.target_lng !== undefined) {
                    coordinates.push({ lat: segment.target_lat, lng: segment.target_lng });
                }
            }
        });
    }
    
    console.log(`🎯 Extracted ${coordinates.length} D-HC2L coordinates`);
    return coordinates.length > 0 ? coordinates : null;
}

// Helper function to extract coordinates from Google Maps route data
function extractGoogleMapsCoordinates(googleMapsRouteData) {
    console.log('🔍 Extracting Google Maps coordinates from:', googleMapsRouteData);
    
    if (!googleMapsRouteData) {
        console.warn('❌ No Google Maps route data provided');
        return null;
    }
    
    let coordinates = [];
    
    // Check if it has a coordinates array (from our enhanced getGoogleMapsRouteWithCoordinates)
    if (googleMapsRouteData.coordinates && googleMapsRouteData.coordinates.length > 0) {
        console.log('✅ Found coordinates array with', googleMapsRouteData.coordinates.length, 'points');
        coordinates = googleMapsRouteData.coordinates.map(coord => ({
            lat: coord.lat,
            lng: coord.lng
        }));
    }
    // If it's a DirectionsResult object from Google Maps API
    else if (googleMapsRouteData.routes && googleMapsRouteData.routes.length > 0) {
        console.log('✅ Found DirectionsResult with', googleMapsRouteData.routes.length, 'routes');
        const route = googleMapsRouteData.routes[0];
        if (route.overview_path && route.overview_path.length > 0) {
            console.log('✅ Using overview_path with', route.overview_path.length, 'points');
            coordinates = route.overview_path.map(point => ({
                lat: point.lat(),
                lng: point.lng()
            }));
        }
        // Fallback: extract from legs
        else if (route.legs && route.legs.length > 0) {
            console.log('✅ Extracting from route legs');
            route.legs.forEach(leg => {
                if (leg.steps && leg.steps.length > 0) {
                    leg.steps.forEach(step => {
                        if (step.path && step.path.length > 0) {
                            step.path.forEach(point => {
                                coordinates.push({
                                    lat: point.lat(),
                                    lng: point.lng()
                                });
                            });
                        }
                    });
                }
            });
        }
    }
    // Check if it has a directionsResult property
    else if (googleMapsRouteData.directionsResult && googleMapsRouteData.directionsResult.routes) {
        console.log('✅ Found directionsResult property');
        const route = googleMapsRouteData.directionsResult.routes[0];
        if (route.overview_path && route.overview_path.length > 0) {
            console.log('✅ Using overview_path with', route.overview_path.length, 'points');
            coordinates = route.overview_path.map(point => ({
                lat: point.lat(),
                lng: point.lng()
            }));
        }
    }
    // If it's our custom metadata object without coordinates
    else if (googleMapsRouteData.steps && googleMapsRouteData.steps.length > 0) {
        console.warn('⚠️ Google Maps metadata found but no coordinate data - need to request full route');
        return null;
    }
    else {
        console.warn('❌ Unrecognized Google Maps route data format:', Object.keys(googleMapsRouteData));
    }
    
    console.log(`🎯 Extracted ${coordinates.length} Google Maps coordinates`);
    return coordinates.length > 0 ? coordinates : null;
}

// Function to compute segment overlap percentage between HC2L and Google Maps routes
function computeSegmentOverlap(dhc2lRouteData, googleMapsRouteData) {
    try {
        console.log('🔍 Computing segment overlap...');
        console.log('D-HC2L Route Data:', dhc2lRouteData);
        console.log('Google Maps Route Data:', googleMapsRouteData);
        
        // Extract road segments from D-HC2L route
        const hc2lSegments = extractHC2LSegments(dhc2lRouteData);
        if (!hc2lSegments || hc2lSegments.length === 0) {
            console.warn('❌ Failed to extract HC2L segments');
            return {
                success: false,
                error: 'Failed to extract HC2L segments',
                overlap_percentage: 0
            };
        }
        
        // Extract road segments from Google Maps route (reference)
        const googleSegments = extractGoogleMapsSegments(googleMapsRouteData);
        if (!googleSegments || googleSegments.length === 0) {
            console.warn('❌ Failed to extract Google Maps segments');
            return {
                success: false,
                error: 'Failed to extract Google Maps segments',
                overlap_percentage: 0
            };
        }
        
        // Count shared segments
        const sharedSegments = findSharedSegments(hc2lSegments, googleSegments);
        const totalGoogleSegments = googleSegments.length;
        
        // Calculate overlap percentage: (shared / total_google) * 100
        const overlapPercentage = (sharedSegments / totalGoogleSegments) * 100;
        
        console.log(`✅ Segment overlap computed: ${sharedSegments}/${totalGoogleSegments} = ${overlapPercentage.toFixed(1)}%`);
        
        return {
            success: true,
            shared_segments: sharedSegments,
            total_hc2l_segments: hc2lSegments.length,
            total_google_segments: totalGoogleSegments,
            overlap_percentage: overlapPercentage,
            overlap_percentage_formatted: `${overlapPercentage.toFixed(1)}%`
        };
        
    } catch (error) {
        console.error('❌ Error computing segment overlap:', error);
        return {
            success: false,
            error: error.message,
            overlap_percentage: 0
        };
    }
}

// Helper function to extract road segments from HC2L route data
function extractHC2LSegments(dhc2lRouteData) {
    if (!dhc2lRouteData || !dhc2lRouteData.route) {
        return null;
    }
    
    let segments = [];
    
    // Extract from road_segments array
    if (dhc2lRouteData.route.road_segments && dhc2lRouteData.route.road_segments.length > 0) {
        console.log('✅ Found HC2L road segments:', dhc2lRouteData.route.road_segments.length);
        segments = dhc2lRouteData.route.road_segments.map(segment => ({
            road_name: segment.road_name || segment.name || 'Unknown Road',
            source_lat: segment.source_lat || segment.start_lat,
            source_lng: segment.source_lng || segment.start_lng,
            target_lat: segment.target_lat || segment.end_lat,
            target_lng: segment.target_lng || segment.end_lng,
            length: segment.length_meters || segment.length || 0,
            normalized_name: normalizeRoadName(segment.road_name || segment.name || 'Unknown Road')
        }));
    }
    // Fallback: create segments from coordinates if road_segments not available
    else if (dhc2lRouteData.route.coordinates && dhc2lRouteData.route.coordinates.length > 1) {
        console.log('⚠️ No road segments found, creating from coordinates');
        const coords = dhc2lRouteData.route.coordinates;
        for (let i = 0; i < coords.length - 1; i++) {
            const start = coords[i];
            const end = coords[i + 1];
            segments.push({
                road_name: 'Unknown Road',
                source_lat: start.lat || start[0],
                source_lng: start.lng || start[1],
                target_lat: end.lat || end[0],
                target_lng: end.lng || end[1],
                length: calculateHaversineDistance(
                    start.lat || start[0], start.lng || start[1],
                    end.lat || end[0], end.lng || end[1]
                ),
                normalized_name: normalizeRoadName('Unknown Road')
            });
        }
    }
    
    console.log(`🎯 Extracted ${segments.length} HC2L segments`);
    return segments.length > 0 ? segments : null;
}

// Helper function to extract road segments from Google Maps route data
function extractGoogleMapsSegments(googleMapsRouteData) {
    if (!googleMapsRouteData) {
        return null;
    }
    
    let segments = [];
    
    // Extract from Google Maps steps (turn-by-turn directions)
    if (googleMapsRouteData.steps && googleMapsRouteData.steps.length > 0) {
        console.log('✅ Found Google Maps steps:', googleMapsRouteData.steps.length);
        segments = googleMapsRouteData.steps.map((step, index) => {
            // Extract road name from instruction (basic parsing)
            const roadName = extractRoadNameFromInstruction(step.instruction);
            return {
                road_name: roadName,
                step_index: index,
                instruction: step.instruction,
                distance: step.distance,
                duration: step.duration,
                normalized_name: normalizeRoadName(roadName)
            };
        });
    }
    // Fallback: extract from DirectionsResult if available
    else if (googleMapsRouteData.directionsResult && googleMapsRouteData.directionsResult.routes) {
        console.log('✅ Extracting from DirectionsResult');
        const route = googleMapsRouteData.directionsResult.routes[0];
        if (route.legs && route.legs.length > 0) {
            route.legs.forEach(leg => {
                if (leg.steps && leg.steps.length > 0) {
                    leg.steps.forEach((step, index) => {
                        const roadName = extractRoadNameFromInstruction(step.instructions);
                        segments.push({
                            road_name: roadName,
                            step_index: index,
                            instruction: step.instructions,
                            distance: step.distance.text,
                            duration: step.duration.text,
                            normalized_name: normalizeRoadName(roadName)
                        });
                    });
                }
            });
        }
    }
    
    console.log(`🎯 Extracted ${segments.length} Google Maps segments`);
    return segments.length > 0 ? segments : null;
}

// Helper function to normalize road names for comparison
function normalizeRoadName(roadName) {
    if (!roadName || roadName === 'Unknown Road') {
        return 'unknown';
    }
    
    return roadName
        .toLowerCase()
        .replace(/\b(road|rd|street|st|avenue|ave|boulevard|blvd|highway|hwy|lane|ln)\b/g, '')
        .replace(/[^a-z0-9\s]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

// Helper function to extract road name from Google Maps instruction
function extractRoadNameFromInstruction(instruction) {
    if (!instruction) return 'Unknown Road';
    
    // Remove HTML tags
    const cleanInstruction = instruction.replace(/<[^>]*>/g, '');
    
    // Common patterns to extract road names
    const patterns = [
        /(?:on|onto|via|along)\s+([^,]+?)(?:\s+(?:for|toward|until))/i,
        /(?:turn\s+(?:left|right)\s+onto)\s+([^,]+?)(?:\s|$)/i,
        /(?:continue\s+on)\s+([^,]+?)(?:\s|$)/i,
        /(?:head|go)\s+[^,]*?\s+on\s+([^,]+?)(?:\s|$)/i
    ];
    
    for (const pattern of patterns) {
        const match = cleanInstruction.match(pattern);
        if (match && match[1]) {
            return match[1].trim();
        }
    }
    
    // Fallback: look for capitalized words that might be road names
    const words = cleanInstruction.split(/\s+/);
    const capitalizedWords = words.filter(word => 
        word.length > 2 && 
        word[0] === word[0].toUpperCase() &&
        !/^(turn|left|right|continue|head|go|toward|for|until|then|and|the|on|onto|via|along)$/i.test(word)
    );
    
    if (capitalizedWords.length > 0) {
        return capitalizedWords.slice(0, 2).join(' '); // Take first 1-2 capitalized words
    }
    
    return 'Unknown Road';
}

// Helper function to find shared segments between HC2L and Google Maps
function findSharedSegments(hc2lSegments, googleSegments) {
    let sharedCount = 0;
    
    // Create a set of normalized HC2L road names for efficient lookup
    const hc2lRoadNames = new Set(hc2lSegments.map(segment => segment.normalized_name));
    
    // Count how many Google segments have matching road names in HC2L
    googleSegments.forEach(googleSegment => {
        if (hc2lRoadNames.has(googleSegment.normalized_name)) {
            sharedCount++;
            console.log(`✅ Shared segment: ${googleSegment.road_name} (${googleSegment.normalized_name})`);
        } else {
            console.log(`❌ Unmatched Google segment: ${googleSegment.road_name} (${googleSegment.normalized_name})`);
        }
    });
    
    return sharedCount;
}

// Core discrete Fréchet distance algorithm
function discreteFrechetDistance(curve1, curve2) {
    const n = curve1.length;
    const m = curve2.length;
    
    // Create memoization table
    const memo = Array(n).fill(null).map(() => Array(m).fill(-1));
    
    // Distance function between two points (Haversine distance in meters)
    function pointDistance(p1, p2) {
        return calculateHaversineDistance(p1.lat, p1.lng, p2.lat, p2.lng);
    }
    
    // Recursive function with memoization
    function frechetRecursive(i, j) {
        if (memo[i][j] !== -1) {
            return memo[i][j];
        }
        
        const dist = pointDistance(curve1[i], curve2[j]);
        
        if (i === 0 && j === 0) {
            memo[i][j] = dist;
        } else if (i === 0) {
            memo[i][j] = Math.max(dist, frechetRecursive(i, j - 1));
        } else if (j === 0) {
            memo[i][j] = Math.max(dist, frechetRecursive(i - 1, j));
        } else {
            memo[i][j] = Math.max(dist, Math.min(
                frechetRecursive(i - 1, j),
                frechetRecursive(i, j - 1),
                frechetRecursive(i - 1, j - 1)
            ));
        }
        
        return memo[i][j];
    }
    
    return frechetRecursive(n - 1, m - 1);
}

// Function to get Google Maps route with full coordinate data
async function getGoogleMapsRouteWithCoordinates(startLat, startLng, destLat, destLng) {
    return new Promise((resolve, reject) => {
        if (!directionsService) {
            reject(new Error('Google Maps DirectionsService not available'));
            return;
        }

        const request = {
            origin: { lat: startLat, lng: startLng },
            destination: { lat: destLat, lng: destLng },
            travelMode: google.maps.TravelMode.DRIVING,
            unitSystem: google.maps.UnitSystem.METRIC,
            avoidHighways: false,
            avoidTolls: false
        };

        directionsService.route(request, (result, status) => {
            if (status === 'OK' && result) {
                console.log('Google Maps route with coordinates received');
                
                const route = result.routes[0];
                const leg = route.legs[0];
                
                // Extract full path coordinates
                let pathCoordinates = [];
                if (route.overview_path && route.overview_path.length > 0) {
                    pathCoordinates = route.overview_path.map(point => ({
                        lat: point.lat(),
                        lng: point.lng()
                    }));
                }
                
                // Enhanced metadata with coordinates
                const routeMetadata = {
                    success: true,
                    distance: leg.distance.text,
                    distanceValue: leg.distance.value,
                    duration: leg.duration.text,
                    durationValue: leg.duration.value,
                    startAddress: leg.start_address,
                    endAddress: leg.end_address,
                    coordinates: pathCoordinates,
                    directionsResult: result, // Store the full result for coordinate extraction
                    steps: leg.steps.map(step => ({
                        instruction: step.instructions.replace(/<[^>]*>/g, ''),
                        distance: step.distance.text,
                        duration: step.duration.text,
                        maneuver: step.maneuver || 'straight'
                    })),
                    overview_polyline: route.overview_polyline.points,
                    bounds: {
                        northeast: route.bounds.getNorthEast().toJSON(),
                        southwest: route.bounds.getSouthWest().toJSON()
                    },
                    warnings: route.warnings || [],
                    copyrights: route.copyrights
                };

                resolve(routeMetadata);
            } else {
                console.error('Google Maps route request failed:', status);
                const errorMessage = `Route request failed: ${status}`;
                reject(new Error(errorMessage));
            }
        });
    });
}
  

  

// Function to get Google Maps route suggestion
async function getGoogleMapsRoute(startLat, startLng, destLat, destLng) {
    return new Promise((resolve, reject) => {
        if (!directionsService) {
            reject(new Error('Google Maps DirectionsService not available'));
            return;
        }

        const request = {
            origin: { lat: startLat, lng: startLng },
            destination: { lat: destLat, lng: destLng },
            travelMode: google.maps.TravelMode.DRIVING,
            unitSystem: google.maps.UnitSystem.METRIC,
            avoidHighways: false,
            avoidTolls: false
        };

        console.log('Requesting Google Maps route:', request);
        showUpdateToast('Getting Google Maps route suggestion...', 'info');

        directionsService.route(request, (result, status) => {
            if (status === 'OK' && result) {
                console.log('Google Maps route received:', result);
                
                const route = result.routes[0];
                const leg = route.legs[0];
                
                // Extract metadata
                const routeMetadata = {
                    success: true,
                    distance: leg.distance.text,
                    distanceValue: leg.distance.value, // in meters
                    duration: leg.duration.text,
                    durationValue: leg.duration.value, // in seconds
                    startAddress: leg.start_address,
                    endAddress: leg.end_address,
                    steps: leg.steps.map(step => ({
                        instruction: step.instructions.replace(/<[^>]*>/g, ''), // Remove HTML tags
                        distance: step.distance.text,
                        duration: step.duration.text,
                        maneuver: step.maneuver || 'straight'
                    })),
                    overview_polyline: route.overview_polyline.points,
                    bounds: {
                        northeast: route.bounds.getNorthEast().toJSON(),
                        southwest: route.bounds.getSouthWest().toJSON()
                    },
                    warnings: route.warnings || [],
                    copyrights: route.copyrights
                };

                showUpdateToast(`Google route: ${routeMetadata.distance}, ${routeMetadata.duration}`, 'success');
                resolve(routeMetadata);
            } else {
                console.error('Google Maps route request failed:', status, result);
                const errorMessage = status === 'ZERO_RESULTS' ? 'No route found between the locations' :
                                   status === 'OVER_QUERY_LIMIT' ? 'Google Maps query limit exceeded' :
                                   status === 'REQUEST_DENIED' ? 'Google Maps request denied' :
                                   status === 'INVALID_REQUEST' ? 'Invalid route request' :
                                   status === 'UNKNOWN_ERROR' ? 'Unknown error occurred' :
                                   `Route request failed: ${status}`;
                
                showUpdateToast(errorMessage, 'warning');
                reject(new Error(errorMessage));
            }
        });
    });
}

// Function to display Google Maps route on the map
function displayGoogleMapsRoute(routeMetadata) {
    if (!directionsRenderer || !routeMetadata.success) {
        console.error('Cannot display Google Maps route: renderer not available or invalid data');
        return;
    }

    try {
        // Clear existing routes first
        clearRoutes();
        directionsRenderer.setDirections(null);

        // Create a new directions request to get the full result object
        const request = {
            origin: { lat: startLocation.lat, lng: startLocation.lng },
            destination: { lat: destLocation.lat, lng: destLocation.lng },
            travelMode: google.maps.TravelMode.DRIVING,
            unitSystem: google.maps.UnitSystem.METRIC
        };

        directionsService.route(request, (result, status) => {
            if (status === 'OK') {
                // Set the directions result to the renderer
                directionsRenderer.setDirections(result);
                
                // Fit the map to show the route
                const bounds = result.routes[0].bounds;
                map.fitBounds(bounds);
                
                // Update Current Path Panel with Google Maps data
                updateCurrentPathPanelWithGoogleRoute(routeMetadata);
                
                console.log('✅ Google Maps route displayed successfully');
                showUpdateToast('Google Maps route displayed', 'success');
            } else {
                console.error('Failed to display Google Maps route:', status);
                showUpdateToast('Failed to display Google Maps route', 'warning');
            }
        });

    } catch (error) {
        console.error('Error displaying Google Maps route:', error);
        showUpdateToast('Error displaying route', 'warning');
    }
}

// Function to update Current Path Panel with Google Maps route data
function updateCurrentPathPanelWithGoogleRoute(routeMetadata) {
    try {
        // Update route header metrics with Google Maps data
        const distanceElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-emerald-600');
        if (distanceElement) {
            distanceElement.textContent = routeMetadata.distance;
        }
        
        const durationElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-blue-600');
        if (durationElement) {
            durationElement.textContent = routeMetadata.duration;
        }
        
        const stepsElement = document.querySelector('#current-path-panel .text-xl.font-bold.text-purple-600');
        if (stepsElement) {
            stepsElement.textContent = routeMetadata.steps.length.toString();
        }
        
        // Update route steps with Google Maps turn-by-turn directions
        const stepsContainer = document.querySelector('#current-path-panel .space-y-4.max-h-96.overflow-y-auto');
        if (stepsContainer) {
            // Hide placeholder
            const placeholder = document.getElementById('route-steps-placeholder');
            if (placeholder) {
                placeholder.style.display = 'none';
            }
            
            // Clear existing steps (except placeholder)
            const existingSteps = stepsContainer.querySelectorAll('.flex.gap-4.items-start');
            existingSteps.forEach(step => step.remove());
            
            // Add each Google Maps step
            routeMetadata.steps.forEach((step, index) => {
                const stepNumber = index + 1;
                const isLastStep = index === routeMetadata.steps.length - 1;
                
                // Create step element with Google Maps data
                const stepElement = createGoogleRouteStepElement(stepNumber, step.instruction, step.distance, step.maneuver, isLastStep);
                stepsContainer.appendChild(stepElement);
            });
        }
        
        // Hide route disruption alert (Google Maps routes don't show disruptions)
        const alertElement = document.getElementById('route-disruption-alert');
        if (alertElement) {
            alertElement.classList.add('hidden');
        }
        
        console.log('Current Path Panel updated with Google Maps route data');
        
    } catch (error) {
        console.error('Error updating Current Path Panel with Google route:', error);
    }
}

// Function to create route step element for Google Maps data
function createGoogleRouteStepElement(stepNumber, instruction, distance, maneuver, isLastStep) {
    const stepDiv = document.createElement('div');
    stepDiv.className = 'flex gap-4 items-start';
    
    // Determine step colors (use Google's blue theme)
    const stepColors = isLastStep 
      ? 'bg-gradient-to-br from-red-500 to-rose-600 text-white'
      : 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white';
    
    const contentColors = isLastStep
      ? 'bg-gradient-to-br from-red-50 to-rose-50 border-2 border-red-300'
      : 'bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-300';
    
    const distanceColor = isLastStep ? 'text-red-600' : 'text-blue-600';
    
    stepDiv.innerHTML = `
      <div class="${stepColors} w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm flex-shrink-0 shadow-md">
        ${stepNumber}
      </div>
      <div class="flex-1 ${contentColors} rounded-xl p-3">
        <div class="text-sm text-slate-900 font-semibold mb-1">${instruction}</div>
        <div class="text-xs text-slate-600 font-medium">
          Google Maps Navigation
          <span class="${distanceColor} ml-2 font-bold">${distance}</span>
        </div>
      </div>
    `;
    
    return stepDiv;
}
  

  


