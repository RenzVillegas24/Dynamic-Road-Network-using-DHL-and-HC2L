// Initialize all event handlers when DOM is ready
function initializeEventHandlers() {
    console.log('🎯 Initializing event handlers...');
    
    // Threshold buttons
    document.querySelectorAll('.threshold-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.threshold-btn').forEach(b => {
            b.classList.remove('border-blue-500', 'bg-blue-50', 'shadow-md');
            b.classList.add('border-slate-300');
            });
            
            e.target.classList.remove('border-slate-300');
            e.target.classList.add('border-blue-500', 'bg-blue-50', 'shadow-md');
            
            currentThreshold = parseFloat(e.target.dataset.value);
            thresholdValue.textContent = currentThreshold.toFixed(1);
            
            // Show toast about threshold change
            showUpdateToast(`Threshold updated to τ = ${currentThreshold}`, 'info');
            
            // If we have active routes, offer to recalculate
            if (routePolylines.length > 0 && window.startLocation && window.destLocation) {
            setTimeout(() => {
                showUpdateToast("Threshold changed. Click 'Go' to recalculate route.", 'warning');
            }, 1500);
            }
        });
    });

    const startLocationBtn = document.getElementById('start-location-btn');
    if (startLocationBtn) {
        startLocationBtn.addEventListener('click', () => {
            if (!map) {
                showUpdateToast("Please wait for the map to load", 'warning');
                return;
            }
            pinningMode = 'start';
            map.getContainer().style.cursor = 'crosshair';
            showUpdateToast("Click on the map to pin starting location", 'info');
        });
    }
  
    const destLocationBtn = document.getElementById('dest-location-btn');
    if (destLocationBtn) {
        destLocationBtn.addEventListener('click', () => {
            if (!map) {
                showUpdateToast("Please wait for the map to load", 'warning');
                return;
            }
            pinningMode = 'dest';
            map.getContainer().style.cursor = 'crosshair';
            showUpdateToast("Click on the map to pin destination", 'info');
        });
    }
  
    const pinDisruptionBtn = document.getElementById('pin-disruption-btn');
    if (pinDisruptionBtn) {
        pinDisruptionBtn.addEventListener('click', () => {
            if (!map) {
                showUpdateToast("Please wait for the map to load", 'warning');
                return;
            }
            pinningMode = 'report';
            map.getContainer().style.cursor = 'crosshair';
            showUpdateToast("Click on the map to pin disruption location", 'info');
        });
    }


    const goButton = document.getElementById("go-button");
    if (goButton) {
        goButton.onclick = async () => {
    // Debug logging
    console.log('Go button clicked');
    console.log('startLocation:', window.startLocation);
    console.log('destLocation:', window.destLocation);
    console.log('OSM start data:', window.osmSnapMarkers?.start?.data);
    console.log('OSM dest data:', window.osmSnapMarkers?.dest?.data);
    
    if (!window.startLocation || !window.destLocation) {
      showUpdateToast("Please pin both starting location and destination", 'warning');
      return;
    }
    
    if (!map) {
      showUpdateToast("Please wait for the map to load", 'warning');
      return;
    }
    
    // Get selected algorithm from admin panel
    const selectedAlgorithm = getSelectedAlgorithm();
    console.log('Selected algorithm:', selectedAlgorithm);
    
    // Get dataset selection to determine if disruptions should be used
    const datasetRadio = document.querySelector('input[name="dataset"]:checked');
    const selectedDataset = datasetRadio ? datasetRadio.value : 'none';
    const useDisruptions = selectedDataset !== 'none';
    console.log('Selected dataset:', selectedDataset, 'useDisruptions:', useDisruptions);
    
    // Clear any existing routes
    clearRoutes();
    
    // Show loading state
    const goButton = document.getElementById("go-button");
    const originalText = goButton.innerHTML;
    goButton.innerHTML = '<span class="text-lg">Computing...</span>';
    goButton.disabled = true;
    
    try {
      let routeData = null;
      
      // Route computation based on selected algorithm
      // isPreview=false because user clicked "Go" button - this is route CONFIRMATION with alternatives
      switch (selectedAlgorithm) {
        case 'dhl':
          // DHL only
          if (useDisruptions) {
            // await loadActiveDisruptionsForAlgorithm('DHL');
          } else {
            clearDisruptionMarkers();
          }
          routeData = await computeDHLRoute(useDisruptions, false);
          if (routeData) displayDHLRoute(routeData);
          break;
          
        case 'hc2l':
          // HC2L only
          if (useDisruptions) {
            // await loadActiveDisruptionsForAlgorithm('HC2L');
          } else {
            clearDisruptionMarkers();
          }
          routeData = await computeDHC2LRoute(useDisruptions, currentThreshold, false);
          if (routeData) displayDHC2LRoute(routeData);
          break;
          
        default:
          console.warn('Unknown algorithm selected:', selectedAlgorithm);
          // Fallback to HC2L with isPreview=false (confirmation with alternatives)
          routeData = await computeDHC2LRoute(useDisruptions, currentThreshold, false);
          if (routeData) displayDHC2LRoute(routeData);
      }
      
      if (routeData) {
        // Store route data globally for Current Path Panel
        // Add input coordinates for Google Maps comparison
        routeData.input = {
          start_snap_lat: window.osmSnapMarkers?.start?.data?.latitude,
          start_snap_lng: window.osmSnapMarkers?.start?.data?.longitude,
          dest_snap_lat: window.osmSnapMarkers?.dest?.data?.latitude,
          dest_snap_lng: window.osmSnapMarkers?.dest?.data?.longitude
        };
        
        // Ensure metrics object exists and has algorithm name
        if (!routeData.metrics) {
          routeData.metrics = {};
        }
        routeData.metrics.algorithm = selectedAlgorithm;
        
        currentRouteData = routeData;
        
        console.log('✅ Route data stored with input coordinates:', {
          algorithm: selectedAlgorithm,
          startLat: routeData.input.start_snap_lat,
          startLng: routeData.input.start_snap_lng,
          destLat: routeData.input.dest_snap_lat,
          destLng: routeData.input.dest_snap_lng
        });
        
        // 🧹 Clear previous Google Maps comparison when new route is calculated
        if (typeof clearGoogleMapsComparison === 'function') {
          clearGoogleMapsComparison();
          console.log('✅ Google Maps comparison cleared for new route');
        }
        
        // Show "Current Route Only" button after route is calculated
        const showCurrentRouteBtn = document.getElementById('show-current-route-only-btn');
        if (showCurrentRouteBtn) {
            showCurrentRouteBtn.style.display = 'flex';
        }
        
        // Enable "Compare with Google Maps" button after route is calculated
        const googleCompareBtn = document.getElementById('admin-google-compare-btn');
        if (googleCompareBtn) {
            googleCompareBtn.disabled = false;
        }
        
        // Update UI with route information
        updateRouteMetrics(routeData);
        updateAdminPerformanceMetrics(routeData);
        
        // Update Current Path Panel with real route data
        updateCurrentPathPanel(routeData);
        
        // Show update region overlay if applicable
        if (typeof showUpdateRegion === 'function') {
          showUpdateRegion(routeData);
        }
        
        // Add route to CSV export buffer
        if (typeof addRouteToExport === 'function') {
          addRouteToExport(routeData);
        }
        
        setTimeout(() => {
          const currentMode = updateModeBadge.textContent;
          if (currentMode === "Lazy Update") {
            showUpdateToast("Query triggered lazy repair...", "info");
          } else {
            showUpdateToast("Using updated labels for routing.", "info");
          }
        }, 500);
        
        setTimeout(() => {
          adminPanel.classList.add("translate-x-full");
          disruptionsPanel.classList.add("translate-x-full");
          reportPanel.classList.add("translate-x-full");
          currentPathPanel.classList.remove("translate-x-full");
          
          // Adjust map container to make room for the panel
          const mapContainer = document.getElementById("map-container");
          if (mapContainer) {
              mapContainer.style.marginRight = "28rem";
          }
          
          // Trigger map resize to adjust to new container size
          if (map) {
            setTimeout(() => {
              map.invalidateSize();
            }, 350); // Wait for transition to complete
          }
          
          console.log('✅ Current Path Panel visible, map adjusted');
        }, 800);
        
      } else {
        showUpdateToast('Route calculation failed', 'warning');
      }
      
    } catch (error) {
      showUpdateToast(`Error: ${error.message}`, 'warning');
      console.error('Route calculation error:', error);
    } finally {
      // Restore button state
      goButton.innerHTML = originalText;
      goButton.disabled = false;
    }
        };
    }
  
    // Admin panel start button handler
    const adminStartBtn = document.getElementById("admin-start-btn");
    if (adminStartBtn) {
        adminStartBtn.onclick = async () => {
            // Trigger the go button functionality
            document.getElementById("go-button")?.click();
        };
    }
  
    const currentPathClose = document.getElementById("current-path-close");
    if (currentPathClose) {
        currentPathClose.onclick = () => {
            // Hide the panel using translate
            currentPathPanel.classList.add("translate-x-full");
            
            // Reset map container to full width
            const mapContainer = document.getElementById("map-container");
            if (mapContainer) {
                mapContainer.style.marginRight = "0";
            }
            
            // Reset the route and snap points
            clearRoutes();
            
            // Reset snap points visualization
            if (window.startSnapMarker) {
                map.removeLayer(window.startSnapMarker);
                window.startSnapMarker = null;
            }
            if (window.destSnapMarker) {
                map.removeLayer(window.destSnapMarker);
                window.destSnapMarker = null;
            }
            if (window.startSnapLine) {
                map.removeLayer(window.startSnapLine);
                window.startSnapLine = null;
            }
            if (window.destSnapLine) {
                map.removeLayer(window.destSnapLine);
                window.destSnapLine = null;
            }
            
            // Clear stored snap data
            window.startOsmEdge = null;
            window.destOsmEdge = null;
            
            // Clear Google Maps comparison
            if (typeof clearGoogleMapsComparison === 'function') {
                clearGoogleMapsComparison();
            }
            
            // Trigger map resize to adjust to full container
            if (map) {
                setTimeout(() => {
                    map.invalidateSize();
                }, 350); // Wait for transition to complete
            }
            
            console.log('✅ Route and snap points cleared, map resized');
        };
    }
  
    const adminToggle = document.getElementById("admin-toggle");
    if (adminToggle) {
        adminToggle.onclick = () => {
            console.log('Admin toggle clicked');
            disruptionsPanel.classList.add("translate-x-full");
            reportPanel.classList.add("translate-x-full");
            // Keep current path panel open
            adminPanel.classList.remove("translate-x-full");
            
            // Keep map margin since current path panel is still visible
            // Map resize will be triggered below
            
            // Trigger map resize
            if (map) {
                setTimeout(() => {
                    map.invalidateSize();
                }, 350);
            }
        };
        console.log('✅ Admin toggle handler registered');
    } else {
        console.error('❌ Admin toggle button not found');
    }
  
    const adminClose = document.getElementById("admin-close");
    if (adminClose) {
        adminClose.onclick = () => {
            adminPanel.classList.add("translate-x-full");
        };
    }
  
    const disruptionsToggle = document.getElementById("disruptions-toggle");
    if (disruptionsToggle) {
        disruptionsToggle.onclick = async () => {
            adminPanel.classList.add("translate-x-full");
            reportPanel.classList.add("translate-x-full");
            // Keep current path panel open
            disruptionsPanel.classList.remove("translate-x-full");
            
            // Keep map margin since current path panel is still visible
            // Map resize will be triggered below
            
            // Trigger map resize
            if (map) {
                setTimeout(() => {
                    map.invalidateSize();
                }, 350);
            }
            
            // Fetch and display active disruptions
            await loadActiveDisruptions();
        };
    }
  
    const disruptionsClose = document.getElementById("disruptions-close");
    if (disruptionsClose) {
        disruptionsClose.onclick = () => {
            disruptionsPanel.classList.add("translate-x-full");
        };
    }
  
    const reportToggle = document.getElementById("report-toggle");
    if (reportToggle) {
        reportToggle.onclick = () => {
            adminPanel.classList.add("translate-x-full");
            disruptionsPanel.classList.add("translate-x-full");
            // Keep current path panel open
            reportPanel.classList.remove("translate-x-full");
            
            // Keep map margin since current path panel is still visible
            // Map resize will be triggered below
            
            // Trigger map resize
            if (map) {
                setTimeout(() => {
                    map.invalidateSize();
                }, 350);
            }
        };
    }
  
    const reportClose = document.getElementById("report-close");
    if (reportClose) {
        reportClose.onclick = () => {
            reportPanel.classList.add("translate-x-full");
        };
    }
  
    const reportForm = document.getElementById('report-form');
    if (reportForm) {
        reportForm.onsubmit = async (e) => {
    e.preventDefault();
    
    if (!reportLocation) {
      showUpdateToast("Please pin the incident location on the map", 'warning');
      return;
    }
    
    // Get incident type
    const incidentType = document.getElementById('disruption-type')?.value;
    if (!incidentType) {
      showUpdateToast("Please select an incident type", 'warning');
      return;
    }
    
    // Get traffic severity
    const severityRadio = document.querySelector('input[name="traffic"]:checked');
    if (!severityRadio) {
      showUpdateToast("Please select traffic severity", 'warning');
      return;
    }
    const severity = severityRadio.value;
    
    // Get custom flow parameters
    const isClosed = document.getElementById('road-closure-toggle')?.checked || false;
    const customSpeed = parseFloat(document.getElementById('custom-speed-input')?.value || 30);
    const freeFlowSpeed = 50; // Normal city speed
    
    // Calculate jam factor
    let jamFactor;
    if (isClosed) {
      jamFactor = 10.0;
    } else {
      jamFactor = Math.max(0, Math.min(10, 10 * (1 - customSpeed / freeFlowSpeed)));
    }
    
    // Disable submit button to prevent multiple submissions
    const submitButton = reportForm.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.innerHTML = 'Submitting...';
    submitButton.disabled = true;
    
    try {
      const response = await fetch('/report_disruption', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          lat: reportLocation.lat,
          lng: reportLocation.lng,
          incident_type: incidentType,
          severity: severity,
          custom_speed: customSpeed,
          free_flow_speed: freeFlowSpeed,
          jam_factor: jamFactor,
          is_closed: isClosed,
          description: `User reported ${incidentType} (${severity} severity)`
        })
      });
        if (!response.ok) { 
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.success) {
            showUpdateToast(data.message || 'Disruption reported successfully!', 'success');
            
            // Add incident marker to the map immediately
            if (map && typeof L !== 'undefined') {
              const severityColorMap = {
                'heavy': '#ef4444',
                'medium': '#f59e0b',
                'light': '#10b981'
              };
              const markerColor = severityColorMap[severity] || '#f59e0b';
              
              const incidentIcon = L.divIcon({
                html: `<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="16" cy="16" r="14" fill="${markerColor}" stroke="white" stroke-width="2"/>
                        <text x="16" y="21" text-anchor="middle" fill="white" font-size="14" font-weight="bold">!</text>
                      </svg>`,
                className: 'reported-incident-marker',
                iconSize: [32, 32],
                iconAnchor: [16, 32]
              });
              
              const incidentMarker = L.marker([reportLocation.lat, reportLocation.lng], {
                icon: incidentIcon,
                title: `${incidentType} (${severity}) - Just reported`
              }).addTo(map);
              
              // Add popup with info
              const popupContent = `
                <div class="p-2">
                  <h3 class="font-bold text-sm">${data.road_name || 'Reported Location'}</h3>
                  <p class="text-xs text-gray-600">${incidentType}</p>
                  <p class="text-xs">Severity: <span class="font-semibold" style="color: ${markerColor}">${severity}</span></p>
                  <p class="text-xs">Speed: ${customSpeed} km/h</p>
                  ${isClosed ? '<p class="text-xs text-red-600 font-bold">⚠️ ROAD BLOCKED</p>' : ''}
                  <p class="text-xs text-green-600 mt-1">✅ Just reported</p>
                </div>
              `;
              
              incidentMarker.bindPopup(popupContent);
              incidentMarker.openPopup(); // Show popup immediately
              
              // Store in disruptionMarkers array
              if (typeof disruptionMarkers !== 'undefined') {
                disruptionMarkers.push(incidentMarker);
              } else {
                // Create array if it doesn't exist
                window.disruptionMarkers = window.disruptionMarkers || [];
                window.disruptionMarkers.push(incidentMarker);
              }
              
              console.log('✅ Incident marker added to map');
              
              // Ensure the "Show Active Incidents" toggle is checked
              const showIncidentsToggle = document.getElementById('show-active-incidents');
              if (showIncidentsToggle && !showIncidentsToggle.checked) {
                showIncidentsToggle.checked = true;
                console.log('✅ Auto-enabled "Show Active Incidents" toggle');
              }
            }
            
            // Reset form and remove report markers (but keep the incident marker)
            document.getElementById('report-form').reset();
            if (reportMarker) {
                map.removeLayer(reportMarker);
                reportMarker = null;
            }
            if (window.reportSnapMarker) {
                map.removeLayer(window.reportSnapMarker);
                window.reportSnapMarker = null;
            }
            if (window.reportConnectorLine) {
                map.removeLayer(window.reportConnectorLine);
                window.reportConnectorLine = null;
            }
            reportLocation = null;
            
            // Close report panel
            const reportPanel = document.getElementById('report-panel');
            if (reportPanel) {
              reportPanel.classList.add('translate-x-full');
            }
            
            // Reset custom flow controls
            if (document.getElementById('road-closure-toggle')) {
              document.getElementById('road-closure-toggle').checked = false;
            }
            if (document.getElementById('custom-speed-input')) {
              document.getElementById('custom-speed-input').value = 30;
              document.getElementById('custom-speed-slider').value = 30;
            }
            
        } else {
            throw new Error(data.error || 'Failed to report disruption');
        }
    } catch (error) {
      console.error('Error reporting disruption:', error);
      showUpdateToast(`Error: ${error.message}`, 'warning');
    } finally {
      submitButton.innerHTML = originalText;
      submitButton.disabled = false;
    }
        };
    }



    document.querySelectorAll('input[name="algo-dataset"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
          const value = e.target.nextElementSibling.textContent;
          if (value.includes('Comparison Mode')) {
            comparisonButtons.classList.remove('hidden');
            isComparisonMode = true;
          } else {
            comparisonButtons.classList.add('hidden');
            isComparisonMode = false;
          }
        });
    });
  
    const showComparisonSummary = document.getElementById('show-comparison-summary');
    if (showComparisonSummary) {
        showComparisonSummary.onclick = () => {
            comparisonModal.classList.remove('hidden');
        };
    }
  
    const comparisonModalClose = document.getElementById('comparison-modal-close');
    if (comparisonModalClose) {
        comparisonModalClose.onclick = () => {
            comparisonModal.classList.add('hidden');
        };
    }
  
// document.getElementById('show-similarity-computation').onclick = () => {
//     similarityModal.classList.remove('hidden');
// };
  
// document.getElementById('similarity-modal-close').onclick = () => {
//     similarityModal.classList.add('hidden');
// };

    const adminResetBtn = document.getElementById('admin-reset-btn');
    if (adminResetBtn) {
        adminResetBtn.onclick = () => {
            // Only clear routes if map is ready
            if (map && directionsRenderer) {
              clearRoutes(); // Clear routes when opening admin panel
            }
            // resetAll();
        };
    }
  
    const newDatasetBtn = document.getElementById('new-dataset');
    if (newDatasetBtn) {
        newDatasetBtn.onclick = async () => {
            console.log('New dataset button clicked');
            const originalText = newDatasetButtonText.innerHTML;
        newDatasetButtonText.innerHTML = 'Adding...........';
        newDatasetBtn.disabled = true;

        try {
          const response = await fetch('/request_new_dataset');
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          const data = await response.json();
          if (data.success) {
            showUpdateToast(data.message || 'New dataset added successfully', 'success');

          } else {
            throw new Error(data.error || 'Failed to add new dataset');
            }
        } catch (error) {
          console.error('Error requesting new dataset:', error);
          showUpdateToast(`Error: ${error.message}`, 'warning');
        }
        newDatasetButtonText.innerHTML = originalText;
        newDatasetBtn.disabled = false;
    };
    console.log('✅ New dataset button handler registered');
} else {
    console.error('❌ New dataset button not found');
}

if (comparisonModal) {
    comparisonModal.onclick = (e) => {
        if (e.target === comparisonModal) {
          comparisonModal.classList.add('hidden');
        }
    };
}

// similarityModal.onclick = (e) => {
//     if (e.target === similarityModal) {
//       similarityModal.classList.add('hidden');
//     }
// };


// OSM Graph Visualization Toggle
let osmGraphLayer = null;
let osmGraphVisible = false;

const showOsmGraphBtn = document.getElementById('show-osm-graph-btn');
if (showOsmGraphBtn) {
    showOsmGraphBtn.onclick = async () => {
        console.log('Show OSM graph button clicked');
        const button = document.getElementById('show-osm-graph-btn');
        const buttonText = document.getElementById('show-osm-graph-text');
        
        if (!osmGraphVisible) {
            // Show OSM graph
            if (buttonText) buttonText.textContent = 'Loading...';
            button.disabled = true;
            
            try {
                const response = await fetch('/get_osm_graph_edges?limit=1000000');
                const data = await response.json();
                
                if (data.success) {
                    // Create layer group for OSM edges
                    osmGraphLayer = L.layerGroup();
                    
                    // Add each edge as a polyline
                    data.edges.forEach(edge => {
                        const polyline = L.polyline(edge.coordinates, {
                            color: getHighwayColor(edge.highway),
                            weight: getHighwayWeight(edge.highway),
                            opacity: 0.4,
                            className: 'osm-graph-edge'
                    });
                    
                    // Add popup with edge info
                    polyline.bindPopup(
                        `<b>${edge.name}</b><br>` +
                        `Type: ${edge.highway}<br>` +
                        `${edge.oneway ? '⚠️ One-way<br>' : ''}` +
                        `Length: ${edge.length}m<br>` +
                        `<small>Nodes: ${edge.u} → ${edge.v}</small>`
                    );
                    
                    osmGraphLayer.addLayer(polyline);
                });
                
                osmGraphLayer.addTo(map);
                osmGraphVisible = true;
                if (buttonText) buttonText.textContent = 'Hide OSM Graph';
                showUpdateToast(`Showing ${data.count} road segments`, 'success');
                
                if (data.count < data.total_edges) {
                    setTimeout(() => {
                        showUpdateToast(`${data.message}`, 'info');
                    }, 1500);
                }
            } else {
                throw new Error(data.error || 'Failed to load OSM graph');
            }
        } catch (error) {
            console.error('Error loading OSM graph:', error);
            showUpdateToast(`Error: ${error.message}`, 'warning');
            if (buttonText) buttonText.textContent = 'Show OSM Graph';
        }
        
        button.disabled = false;
    } else {
        // Hide OSM graph
        if (osmGraphLayer) {
            map.removeLayer(osmGraphLayer);
            osmGraphLayer = null;
        }
        osmGraphVisible = false;
        if (buttonText) buttonText.textContent = 'Show OSM Graph';
        showUpdateToast('OSM graph hidden', 'info');
    }
    };
    console.log('✅ Show OSM graph button handler registered');
} else {
    console.error('❌ Show OSM graph button not found');
}

    console.log('✅ All event handlers initialized');
}

// Helper function to get color based on highway type
function getHighwayColor(type) {
    const colors = {
        'motorway': '#e74c3c',
        'trunk': '#e67e22',
        'primary': '#3498db',
        'secondary': '#2ecc71',
        'tertiary': '#9b59b6',
        'residential': '#95a5a6',
        'service': '#bdc3c7',
        'unclassified': '#7f8c8d'
    };
    return colors[type] || '#34495e';
}

// Helper function to get weight based on highway type
function getHighwayWeight(type) {
    const weights = {
        'motorway': 4,
        'trunk': 3.5,
        'primary': 3,
        'secondary': 2.5,
        'tertiary': 2,
        'residential': 1.5,
        'service': 1,
        'unclassified': 1
    };
    return weights[type] || 1;
}

// Handle algorithm selection change to show/hide threshold section
function handleAlgorithmChange() {
    const algorithmRadios = document.querySelectorAll('input[name="algorithm"]');
    const thresholdContainer = document.getElementById('threshold-container');
    
    algorithmRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            const selectedAlgorithm = radio.value;
            
            // Show threshold only for HC2L (LazyHC2L uses threshold)
            // Hide threshold for DHL and Both modes
            if (selectedAlgorithm === 'hc2l') {
                if (thresholdContainer) {
                    thresholdContainer.style.display = 'block';
                    showUpdateToast('Threshold (τ) controls LazyHC2L update strategy', 'info');
                }
            } else {
                if (thresholdContainer) {
                    thresholdContainer.style.display = 'none';
                    if (selectedAlgorithm === 'dhl') {
                        showUpdateToast('DHL uses immediate updates (no threshold needed)', 'info');
                    } else {
                        showUpdateToast('Comparison mode: threshold applies to HC2L only', 'info');
                    }
                }
            }
        });
    });
    
    // Initial state based on default selection
    const selectedAlgorithm = document.querySelector('input[name="algorithm"]:checked')?.value;
    if (selectedAlgorithm !== 'hc2l' && thresholdContainer) {
        thresholdContainer.style.display = 'none';
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initializeEventHandlers();
        handleAlgorithmChange();
    });
} else {
    // DOM already loaded
    initializeEventHandlers();
    handleAlgorithmChange();
}





