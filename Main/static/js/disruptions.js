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

// Function to clear the disruption markers from the map
function clearDisruptionMarkers() {
    disruptionMarkers.forEach(marker => {
        marker.setMap(null);
    });
    disruptionMarkers = [];
}


