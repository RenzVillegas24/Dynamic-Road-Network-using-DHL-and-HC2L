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
      switch (selectedAlgorithm) {
        case 'dhl-base':
          // Clear any existing disruption markers since we're using base dataset
          clearDisruptionMarkers();
          routeData = await computeDHLRoute(false);
          if (routeData) displayDHLRoute(routeData);
          break;
          
        case 'dhl-disrupted':
          // Load active disruptions on the map first
          await loadActiveDisruptionsForAlgorithm('DHL (Disrupted)');
          routeData = await computeDHLRoute(true);
          if (routeData) displayDHLRoute(routeData);
          break;
          
        case 'dhc2l-base':
          // Clear any existing disruption markers since we're using base dataset
          clearDisruptionMarkers();
          routeData = await computeDHC2LRoute(false);
          if (routeData) displayDHC2LRoute(routeData);
          break;
          
        case 'dhc2l-disrupted':
          // Load active disruptions on the map first
          await loadActiveDisruptionsForAlgorithm('D-HC2L (Disrupted)');
          routeData = await computeDHC2LRoute(true);
          if (routeData) displayDHC2LRoute(routeData);
          break;
          
        case 'comparison-base':
          // Clear any existing disruption markers since we're using base dataset
          clearDisruptionMarkers();
          // Use dedicated comparison endpoint for base datasets
          console.log('Starting comparison mode - base datasets');
          showUpdateToast('Computing algorithm comparison (base datasets)...', 'info');
          
          try {
            const response = await fetch('/compare_algorithms', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                start_lat: window.startLocation.lat,
                start_lng: window.startLocation.lng,
                dest_lat: window.destLocation.lat,
                dest_lng: window.destLocation.lng,
                use_disruptions: false,
                threshold: currentThreshold
              })
            });
            
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const comparisonData = await response.json();
            console.log('Received comparison data:', comparisonData);
            
            if (comparisonData.success) {
              // Display both routes with different colors and patterns using Leaflet
              const routes = comparisonData.routes;
              
              if (routes.dhl && routes.dhl.polylines) {
                // Display DHL route with solid blue line (thicker, on top)
                routes.dhl.polylines.forEach(polyline => {
                  const pathCoords = polyline.path.map(p => [p.lat, p.lng]);
                  
                  const dhlPolyline = L.polyline(pathCoords, {
                    color: '#0066FF', // Blue for DHL
                    opacity: 0.9,
                    weight: 6 // Thicker for DHL
                  }).addTo(map);
                  
                  routePolylines.push(dhlPolyline);
                });
                console.log('✅ DHL route displayed in solid blue');
                
                // Add DHL connector polylines
                addDHLConnectorPolylines({ route: routes.dhl });
              }
              
              if (routes.dhc2l && routes.dhc2l.polylines) {
                // Display D-HC2L route with dashed red line (thinner, underneath)
                routes.dhc2l.polylines.forEach(polyline => {
                  const pathCoords = polyline.path.map(p => [p.lat, p.lng]);
                  
                  const dhc2lPolyline = L.polyline(pathCoords, {
                    color: '#FF0000', // Red for D-HC2L
                    opacity: 0.9,
                    weight: 4, // Thinner for D-HC2L
                    dashArray: '10, 5' // Dashed pattern
                  }).addTo(map);
                  
                  routePolylines.push(dhc2lPolyline);
                });
                console.log('✅ D-HC2L route displayed in dashed red');
                
                // Add D-HC2L connector polylines
                addConnectorPolylines({ route: routes.dhc2l });
              }
              
              // Use DHL metrics for performance display if available
              routeData = {
                success: true,
                route: routes.dhl || routes.dhc2l || {},
                routes: routes, // Include both routes for comparison display
                metrics: routes.dhl ? routes.dhl.summary : (routes.dhc2l ? routes.dhc2l.summary : {}),
                algorithm: 'Algorithm Comparison (Base)'
              };
              
              // Update bottom info bar with comparison data
              updateRouteMetrics(routeData);
              
              // Update algorithm comparison modal with actual metrics
              updateAlgorithmComparisonModal(routes.dhl, routes.dhc2l);
              
              showUpdateToast('Both algorithms displayed! Solid Blue = DHL, Dashed Red = D-HC2L', 'success');
            } else {
              throw new Error(comparisonData.error || 'Comparison computation failed');
            }
          } catch (error) {
            console.error('Comparison mode error:', error);
            throw error;
          }
          break;
          
        case 'comparison-disrupted':
          // Load active disruptions on the map first
          await loadActiveDisruptionsForAlgorithm('Algorithm Comparison (Disrupted)');
          // Use dedicated comparison endpoint for disrupted datasets
          console.log('Starting comparison mode - disrupted datasets');
          showUpdateToast('Computing algorithm comparison (disrupted datasets)...', 'info');
          
          try {
            const response = await fetch('/compare_algorithms', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                start_lat: window.startLocation.lat,
                start_lng: window.startLocation.lng,
                dest_lat: window.destLocation.lat,
                dest_lng: window.destLocation.lng,
                use_disruptions: true
              })
            });
            
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const comparisonData = await response.json();
            console.log('Received comparison data:', comparisonData);
            
            if (comparisonData.success) {
              // Display both routes with different colors and patterns using Leaflet
              const routes = comparisonData.routes;
              
              if (routes.dhl && routes.dhl.polylines) {
                // Display DHL route with solid blue line (thicker, on top)
                routes.dhl.polylines.forEach(polyline => {
                  const pathCoords = polyline.path.map(p => [p.lat, p.lng]);
                  
                  const dhlPolyline = L.polyline(pathCoords, {
                    color: '#0066FF', // Blue for DHL
                    opacity: 0.9,
                    weight: 6 // Thicker for DHL
                  }).addTo(map);
                  
                  routePolylines.push(dhlPolyline);
                });
                console.log('✅ DHL route displayed in solid blue');
                
                // Add DHL connector polylines
                addDHLConnectorPolylines({ route: routes.dhl });
              }
              
              if (routes.dhc2l && routes.dhc2l.polylines) {
                // Display D-HC2L route with dashed red line (thinner, underneath)
                routes.dhc2l.polylines.forEach(polyline => {
                  const pathCoords = polyline.path.map(p => [p.lat, p.lng]);
                  
                  const dhc2lPolyline = L.polyline(pathCoords, {
                    color: '#FF0000', // Red for D-HC2L
                    opacity: 0.9,
                    weight: 4, // Thinner for D-HC2L
                    dashArray: '10, 5' // Dashed pattern
                  }).addTo(map);
                  
                  routePolylines.push(dhc2lPolyline);
                });
                console.log('✅ D-HC2L route displayed in dashed red');
                
                // Add D-HC2L connector polylines
                addConnectorPolylines({ route: routes.dhc2l });
              }
              
              // Use DHL metrics for performance display if available
              routeData = {
                success: true,
                route: routes.dhl || routes.dhc2l || {},
                routes: routes, // Include both routes for comparison display
                metrics: routes.dhl ? routes.dhl.summary : (routes.dhc2l ? routes.dhc2l.summary : {}),
                algorithm: 'Algorithm Comparison (Disrupted)'
              };
              
              // Update bottom info bar with comparison data
              // updateRouteMetrics(routeData);
              updateAlgorithmComparisonModal(routes.dhl, routes.dhc2l);
              showUpdateToast('Both algorithms displayed! Solid Blue = DHL, Dashed Red = D-HC2L', 'success');
            } else {
              throw new Error(comparisonData.error || 'Comparison computation failed');
            }
          } catch (error) {
            console.error('Comparison mode error:', error);
            throw error;
          }
          break;
          
        default:
          console.warn('Unknown algorithm selected:', selectedAlgorithm);
          routeData = await computeDHC2LRoute(false);
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
    
    const description = document.getElementById('incident-description').value.trim();
    if (!description) {
      showUpdateToast("Please provide a brief description of the incident", 'warning');
      return;
    }
    
    // Disable submit button to prevent multiple submissions
    const submitButton = document.getElementById('report-submit-btn');
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
          description: description
        })
      });
        if (!response.ok) { 
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.success) {
            showUpdateToast(data.message || 'Disruption reported successfully', 'success');
            // Reset form and remove marker
            document.getElementById('report-form').reset();
            if (reportMarker) {
                reportMarker.setMap(null);
                reportMarker = null;
                reportLocation = null;
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeEventHandlers);
} else {
    // DOM already loaded
    initializeEventHandlers();
}





