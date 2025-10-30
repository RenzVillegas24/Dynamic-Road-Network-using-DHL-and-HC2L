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
        if (routePolylines.length > 0 && startLocation && destLocation) {
        setTimeout(() => {
            showUpdateToast("Threshold changed. Click 'Go' to recalculate route.", 'warning');
        }, 1500);
        }
    });
});

document.getElementById('start-location-btn').addEventListener('click', () => {
    if (!map) {
        showUpdateToast("Please wait for the map to load", 'warning');
        return;
    }
    pinningMode = 'start';
    map.setOptions({ cursor: 'crosshair' });
    showUpdateToast("Click on the map to pin starting location", 'info');
});
  
document.getElementById('dest-location-btn').addEventListener('click', () => {
    if (!map) {
    showUpdateToast("Please wait for the map to load", 'warning');
    return;
    }
    pinningMode = 'dest';
    map.setOptions({ cursor: 'crosshair' });
    showUpdateToast("Click on the map to pin destination", 'info');
});
  
document.getElementById('pin-disruption-btn').addEventListener('click', () => {
    if (!map) {
        showUpdateToast("Please wait for the map to load", 'warning');
        return;
    }
    pinningMode = 'report';
    map.setOptions({ cursor: 'crosshair' });
    showUpdateToast("Click on the map to pin disruption location", 'info');
});


document.getElementById("go-button").onclick = async () => {
    if (!startLocation || !destLocation) {
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
    
    // Get Google Maps route data for Fréchet distance computation (runs in background)
    let googleRouteData = null;
    try {
        googleRouteData = await getGoogleMapsRouteWithCoordinates(startLocation.lat, startLocation.lng, destLocation.lat, destLocation.lng);
        console.log('Google Maps route data obtained for Fréchet distance computation');
        // Store Google route for comparison calculations
        window.googleRouteMetadata = googleRouteData;
    } catch (error) {
        console.warn('Google Maps route failed (Fréchet distance will not be available):', error.message);
        // Continue with algorithm routing even if Google Maps fails
        window.googleRouteMetadata = null;
    }
    
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
                start_lat: startLocation.lat,
                start_lng: startLocation.lng,
                dest_lat: destLocation.lat,
                dest_lng: destLocation.lng,
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
              // Display both routes with different colors and patterns
              const routes = comparisonData.routes;
              
              if (routes.dhl && routes.dhl.polylines) {
                // Display DHL route with solid blue line (thicker, on top)
                routes.dhl.polylines.forEach(polyline => {
                  const dhlPolyline = new google.maps.Polyline({
                    path: polyline.path,
                    geodesic: polyline.geodesic,
                    strokeColor: '#0066FF', // Blue for DHL
                    strokeOpacity: 0.9,
                    strokeWeight: 6, // Thicker for DHL
                    zIndex: 1000 // Higher z-index to show on top
                  });
                  dhlPolyline.setMap(map);
                  routePolylines.push(dhlPolyline);
                });
                console.log('✅ DHL route displayed in solid blue');
                
                // Add DHL connector polylines
                addDHLConnectorPolylines({ route: routes.dhl });
              }
              
              if (routes.dhc2l && routes.dhc2l.polylines) {
                // Display D-HC2L route with dashed red line (thinner, underneath)
                routes.dhc2l.polylines.forEach(polyline => {
                  const dhc2lPolyline = new google.maps.Polyline({
                    path: polyline.path,
                    geodesic: polyline.geodesic,
                    strokeColor: '#FF0000', // Red for D-HC2L
                    strokeOpacity: 0.9,
                    strokeWeight: 4, // Thinner for D-HC2L
                    zIndex: 999, // Lower z-index so it shows under DHL
                    icons: [{
                      icon: {
                        path: 'M 0,-1 0,1',
                        strokeOpacity: 1,
                        strokeColor: '#FF0000',
                        strokeWeight: 4,
                        scale: 1
                      },
                      offset: '0',
                      repeat: '12px'
                    }],
                    strokeOpacity: 0 // Make the main stroke invisible so only dashes show
                  });
                  dhc2lPolyline.setMap(map);
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
                start_lat: startLocation.lat,
                start_lng: startLocation.lng,
                dest_lat: destLocation.lat,
                dest_lng: destLocation.lng,
                use_disruptions: true
              })
            });
            
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const comparisonData = await response.json();
            console.log('Received comparison data:', comparisonData);
            
            if (comparisonData.success) {
              // Display both routes with different colors and patterns
              const routes = comparisonData.routes;
              
              if (routes.dhl && routes.dhl.polylines) {
                // Display DHL route with solid blue line (thicker, on top)
                routes.dhl.polylines.forEach(polyline => {
                  const dhlPolyline = new google.maps.Polyline({
                    path: polyline.path,
                    geodesic: polyline.geodesic,
                    strokeColor: '#0066FF', // Blue for DHL
                    strokeOpacity: 0.9,
                    strokeWeight: 6, // Thicker for DHL
                    zIndex: 1000 // Higher z-index to show on top
                  });
                  dhlPolyline.setMap(map);
                  routePolylines.push(dhlPolyline);
                });
                console.log('✅ DHL route displayed in solid blue');
                
                // Add DHL connector polylines
                addDHLConnectorPolylines({ route: routes.dhl });
              }
              
              if (routes.dhc2l && routes.dhc2l.polylines) {
                // Display D-HC2L route with dashed red line (thinner, underneath)
                routes.dhc2l.polylines.forEach(polyline => {
                  const dhc2lPolyline = new google.maps.Polyline({
                    path: polyline.path,
                    geodesic: polyline.geodesic,
                    strokeColor: '#FF0000', // Red for D-HC2L
                    strokeOpacity: 0.9,
                    strokeWeight: 4, // Thinner for D-HC2L
                    zIndex: 999, // Lower z-index so it shows under DHL
                    icons: [{
                      icon: {
                        path: 'M 0,-1 0,1',
                        strokeOpacity: 1,
                        strokeColor: '#FF0000',
                        strokeWeight: 4,
                        scale: 1
                      },
                      offset: '0',
                      repeat: '12px'
                    }],
                    strokeOpacity: 0 // Make the main stroke invisible so only dashes show
                  });
                  dhc2lPolyline.setMap(map);
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
        currentRouteData = routeData;
        
        // Update UI with route information
        updateRouteMetrics(routeData);
        updateAdminPerformanceMetrics(routeData);
        
        // Update Current Path Panel with real route data
        updateCurrentPathPanel(routeData);
        
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
          console.log('✅ Current Path Panel should now be visible');
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
  
// Admin panel start button handler
document.getElementById("admin-start-btn").onclick = async () => {
    // Trigger the go button functionality
    document.getElementById("go-button").click();
};
  
document.getElementById("current-path-close").onclick = () => {
    currentPathPanel.classList.add("translate-x-full");
};
  
document.getElementById("admin-toggle").onclick = () => {
    // Only clear routes if map is ready
    // if (map && directionsRenderer) {
    //   clearRoutes    (); // Clear routes when opening admin panel
    // }
    disruptionsPanel.classList.add("translate-x-full");
    reportPanel.classList.add("translate-x-full");
    currentPathPanel.classList.add("translate-x-full");
    adminPanel.classList.remove("translate-x-full");
};
  
document.getElementById("admin-close").onclick = () => {
    adminPanel.classList.add("translate-x-full");
};
  
document.getElementById("disruptions-toggle").onclick = async () => {
    adminPanel.classList.add("translate-x-full");
    reportPanel.classList.add("translate-x-full");
    currentPathPanel.classList.add("translate-x-full");
    disruptionsPanel.classList.remove("translate-x-full");
    
    // Fetch and display active disruptions
    await loadActiveDisruptions();
};
  
document.getElementById("disruptions-close").onclick = () => {
    disruptionsPanel.classList.add("translate-x-full");
};
  
document.getElementById("report-toggle").onclick = () => {
    adminPanel.classList.add("translate-x-full");
    disruptionsPanel.classList.add("translate-x-full");
    currentPathPanel.classList.add("translate-x-full");
    reportPanel.classList.remove("translate-x-full");
};
  
document.getElementById("report-close").onclick = () => {
    reportPanel.classList.add("translate-x-full");
};
  
document.getElementById('report-form').onsubmit = async (e) => {
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
  
document.getElementById('show-comparison-summary').onclick = () => {
    comparisonModal.classList.remove('hidden');
};
  
document.getElementById('comparison-modal-close').onclick = () => {
    comparisonModal.classList.add('hidden');
};
  
// document.getElementById('show-similarity-computation').onclick = () => {
//     similarityModal.classList.remove('hidden');
// };
  
// document.getElementById('similarity-modal-close').onclick = () => {
//     similarityModal.classList.add('hidden');
// };

document.getElementById('admin-reset-btn').onclick = () => {
    // Only clear routes if map is ready
    if (map && directionsRenderer) {
      clearRoutes(); // Clear routes when opening admin panel
    }
    // resetAll();
}
  
document.getElementById('new-dataset').onclick = async () => {
    const originalText = newDatasetButtonText.innerHTML;
    newDatasetButtonText.innerHTML = 'Adding...........';
    newDatasetButtonText.disabled = true;

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
    newDatasetButtonText.disabled = false;
}

comparisonModal.onclick = (e) => {
    if (e.target === comparisonModal) {
      comparisonModal.classList.add('hidden');
    }
};

// similarityModal.onclick = (e) => {
//     if (e.target === similarityModal) {
//       similarityModal.classList.add('hidden');
//     }
// };









