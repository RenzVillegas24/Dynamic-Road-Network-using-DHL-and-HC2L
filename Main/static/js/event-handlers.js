// ============================================================
// GLOBAL FUNCTIONS - Available for form submission and other handlers
// ============================================================

/**
 * Update Road Closure UI state based on selected incident type
 * Disables/enables controls based on whether Road Closure is selected
 */
function updateRoadClosureUI() {
  const disruptionTypeSelect = document.getElementById('disruption-type');
  if (!disruptionTypeSelect) return;
  
  const selectedType = disruptionTypeSelect.value;
  
  if (selectedType === 'road-closure') {
    // Automatically set criticality to "critical" for Road Closure
    const criticalRadio = document.querySelector('input[name="criticality"][value="critical"]');
    if (criticalRadio) {
      criticalRadio.checked = true;
      // Trigger change event to update UI
      criticalRadio.dispatchEvent(new Event('change', { bubbles: true }));
    }
    
    // Automatically check "Road is Completely Closed"
    const roadClosedCheckbox = document.getElementById('incident-road-closed');
    if (roadClosedCheckbox) {
      roadClosedCheckbox.checked = true;
      roadClosedCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
    }
    
    // Disable all criticality radio buttons except critical
    const criticalityRadios = document.querySelectorAll('input[name="criticality"]');
    criticalityRadios.forEach(radio => {
      if (radio.value !== 'critical') {
        radio.disabled = true;
        radio.parentElement.style.opacity = '0.5';
        radio.parentElement.style.pointerEvents = 'none';
      }
    });
    
    // Disable the road closed checkbox
    if (roadClosedCheckbox) {
      roadClosedCheckbox.disabled = true;
      roadClosedCheckbox.parentElement.style.opacity = '0.5';
      roadClosedCheckbox.parentElement.style.pointerEvents = 'none';
    }
    
    showUpdateToast("Road Closure: Criticality set to Critical, Road marked as Closed", 'info');
  } else {
    // Re-enable all criticality radio buttons
    const criticalityRadios = document.querySelectorAll('input[name="criticality"]');
    criticalityRadios.forEach(radio => {
      radio.disabled = false;
      radio.parentElement.style.opacity = '1';
      radio.parentElement.style.pointerEvents = 'auto';
    });
    
    // Re-enable the road closed checkbox
    const roadClosedCheckbox = document.getElementById('incident-road-closed');
    if (roadClosedCheckbox) {
      roadClosedCheckbox.disabled = false;
      roadClosedCheckbox.parentElement.style.opacity = '1';
      roadClosedCheckbox.parentElement.style.pointerEvents = 'auto';
    }
  }
}

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
        
        window.currentRouteData = routeData;
        
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
      closeCurrentPathPanel();
            
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

      refreshUserDisruptionsUI();
        };
    }
  
    const reportClose = document.getElementById("report-close");
    if (reportClose) {
        reportClose.onclick = () => {
            reportPanel.classList.add("translate-x-full");
        };
    }
  
  async function fetchUserDisruptionsList() {
    try {
      const response = await fetch('/user_disruptions');
      if (!response.ok) {
        throw new Error('Failed to load custom incidents');
      }
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || 'Unable to load custom incidents');
      }
      return data.disruptions || [];
    } catch (error) {
      console.error('Error fetching user disruptions:', error);
      showUpdateToast(error.message, 'warning');
      return [];
    }
  }

  async function refreshActiveDisruptionsOnMapSilently() {
    try {
      const response = await fetch('/get_active_disruptions');
      const data = await response.json();
      if (data.success && typeof showAllDisruptionsOnMap === 'function') {
        showAllDisruptionsOnMap(data);
      }
    } catch (error) {
      console.error('Error refreshing disruption markers:', error);
    }
  }

  async function refreshUserDisruptionsUI(showToast = false) {
    const listElement = document.getElementById('user-disruptions-list');
    const emptyElement = document.getElementById('user-disruptions-empty');
    if (!listElement || !emptyElement) return;

    const disruptions = await fetchUserDisruptionsList();
    listElement.innerHTML = '';

    if (!disruptions.length) {
      emptyElement.classList.remove('hidden');
      if (showToast) {
        showUpdateToast('No custom incidents to display', 'info');
      }
      return;
    }

    emptyElement.classList.add('hidden');

    disruptions.forEach((disruption) => {
      const card = document.createElement('div');
      card.className = 'bg-white border border-purple-100 rounded-2xl p-4 shadow-sm hover:shadow-md transition';
      
      const roadName = disruption.road_name || 'Pinned Location';
      const incidentType = disruption.incident_type || 'User Incident';
      const criticality = disruption.incident_criticality || 'Unknown';
      const roadClosed = disruption.incident_road_closed ? 'Yes' : 'No';
      const description = disruption.incident_description || 'No description';
      const startTime = disruption.incident_start_time ? new Date(disruption.incident_start_time).toLocaleString() : '--';
      const endTime = disruption.incident_end_time ? new Date(disruption.incident_end_time).toLocaleString() : '--';
      const highwayType = disruption.highway_type || 'Unknown';

      card.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-xs font-semibold text-purple-500 uppercase tracking-wide">${incidentType}</p>
            <h4 class="font-bold text-slate-900 text-base">${roadName}</h4>
            <p class="text-xs text-slate-500">${description}</p>
          </div>
          <span class="text-xs font-bold px-2 py-1 rounded-full bg-purple-100 text-purple-700">${criticality.toUpperCase()}</span>
        </div>
        <div class="grid grid-cols-2 gap-3 mt-3 text-xs text-slate-600">
          <div>
            <p class="font-semibold text-slate-800">Road Closed</p>
            <p>${roadClosed}</p>
          </div>
          <div>
            <p class="font-semibold text-slate-800">Highway Type</p>
            <p>${highwayType}</p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-3 mt-2 text-xs text-slate-600">
          <div>
            <p class="font-semibold text-slate-800">Start Time</p>
            <p>${startTime}</p>
          </div>
          <div>
            <p class="font-semibold text-slate-800">End Time</p>
            <p>${endTime}</p>
          </div>
        </div>
        <button type="button" class="mt-4 w-full bg-red-50 hover:bg-red-100 text-red-700 font-semibold text-sm py-2 rounded-xl transition delete-user-disruption" data-incident-id="${disruption.incident_id}">
          Remove Incident
        </button>
      `;

      const removeButton = card.querySelector('.delete-user-disruption');
      if (removeButton) {
        removeButton.onclick = () => handleRemoveUserDisruption(disruption.incident_id, removeButton);
      }

      listElement.appendChild(card);
    });

    if (showToast) {
      showUpdateToast(`Loaded ${disruptions.length} custom incident${disruptions.length === 1 ? '' : 's'}`, 'success');
    }
  }

  async function handleRemoveUserDisruption(reportId, buttonElement) {
    if (!reportId) return;
    if (buttonElement) {
      buttonElement.disabled = true;
      buttonElement.textContent = 'Removing...';
    }
    try {
      const response = await fetch(`/user_disruptions/${reportId}`, { method: 'DELETE' });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || 'Failed to remove incident');
      }
      showUpdateToast('Custom incident removed', 'success');
      if (Array.isArray(window.disruptionMarkers)) {
        window.disruptionMarkers = window.disruptionMarkers.filter((marker) => {
          const shouldRemove = marker?.reportId === reportId;
          if (shouldRemove && map && typeof map.removeLayer === 'function') {
            map.removeLayer(marker);
          }
          return !shouldRemove;
        });
      }
      await refreshUserDisruptionsUI();
      await refreshActiveDisruptionsOnMapSilently();
      
      // Trigger automatic route recalculation if route is active
      console.log('[EventHandlers] Triggering auto route recalculation after incident removal...');
      if (typeof triggerAutoRouteRecalculation === 'function') {
        setTimeout(() => {
          triggerAutoRouteRecalculation();
        }, 500); // Small delay to allow disruption files to be updated
      }
    } catch (error) {
      console.error('Error removing user disruption:', error);
      showUpdateToast(error.message || 'Unable to remove incident', 'warning');
    } finally {
      if (buttonElement) {
        buttonElement.disabled = false;
        buttonElement.textContent = 'Remove Incident';
      }
    }
  }

  const refreshUserDisruptionsBtn = document.getElementById('refresh-user-disruptions');
  if (refreshUserDisruptionsBtn) {
    refreshUserDisruptionsBtn.onclick = () => refreshUserDisruptionsUI(true);
  }

  // Handle Road Closure type automatic criticality and road closed setting
  const disruptionTypeSelect = document.getElementById('disruption-type');
  if (disruptionTypeSelect) {
    // Add event listener for changes
    disruptionTypeSelect.addEventListener('change', updateRoadClosureUI);
    
    // Initialize state on page load
    updateRoadClosureUI();
  }

  const reportForm = document.getElementById('report-form');
    if (reportForm) {
        reportForm.onsubmit = async (e) => {
    e.preventDefault();
    
    if (!window.reportLocation) {
      showUpdateToast("Please pin the incident location on the map", 'warning');
      return;
    }
    
    // Collect all form data
    const incidentType = document.getElementById('disruption-type').value;
    if (!incidentType) {
      showUpdateToast("Please select an incident type", 'warning');
      return;
    }
    
    const criticality = document.querySelector('input[name="criticality"]:checked')?.value;
    if (!criticality) {
      showUpdateToast("Please select incident criticality", 'warning');
      return;
    }
    
    const isRoadClosed = document.getElementById('incident-road-closed')?.checked || false;
    
    const description = document.getElementById('disruption-description')?.value || '';
    const roadName = window.reportLocation.road_name || 'Custom Report';
    const startTime = document.getElementById('incident-start-time')?.value || '';
    const endTime = document.getElementById('incident-end-time')?.value || '';
    
    // Disable submit button to prevent multiple submissions
    const submitButton = reportForm.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.innerHTML = '💾 Saving...';
    submitButton.disabled = true;
    
    try {
      // Save the custom incident
      const response = await fetch('/save_custom_disruption', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          lat: window.reportLocation.lat,
          lng: window.reportLocation.lng,
          snapped_lat: window.reportLocation.snapped_lat,
          snapped_lng: window.reportLocation.snapped_lng,
          source_id: window.reportLocation.source_id || 0,
          target_id: window.reportLocation.target_id || 0,
          source_lat: window.reportLocation.snapped_lat || window.reportLocation.lat,
          source_lng: window.reportLocation.snapped_lng || window.reportLocation.lng,
          target_lat: window.reportLocation.snapped_lat || window.reportLocation.lat,
          target_lng: window.reportLocation.snapped_lng || window.reportLocation.lng,
          road_name: roadName,
          incident_type: incidentType,
          incident_criticality: criticality,
          incident_road_closed: isRoadClosed,
          incident_description: description,
          incident_start_time: startTime,
          incident_end_time: endTime,
          highway_type: window.reportLocation.highway_type || 'residential'
        })
      });
      
      if (!response.ok) { 
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        // Success: incident saved
        showUpdateToast(`✅ Incident saved: ${data.road_name} (${data.incident_type})`, 'success');
        
        // Reset form
        document.getElementById('report-form').reset();
        
        // Reset Road Closure UI state (re-enable all controls)
        updateRoadClosureUI();
        
        // Clear all map markers and UI elements
        clearReportMarkers();
        document.getElementById('pin-disruption-text').textContent = 'Click to pin location on map';
        document.getElementById('disruption-coords').classList.add('hidden');
        document.getElementById('disruption-coords').textContent = '';
        
        // Refresh user disruptions list
        await refreshUserDisruptionsUI(true);
        
        // Refresh active disruptions on map
        await refreshActiveDisruptionsOnMapSilently();
        
        // Close report panel
        const reportPanel = document.getElementById('report-panel');
        if (reportPanel) {
          reportPanel.classList.add('translate-x-full');
        }
        
        // Trigger automatic route recalculation if route is active
        console.log('[EventHandlers] Triggering auto route recalculation after incident addition...');
        if (typeof triggerAutoRouteRecalculation === 'function') {
          setTimeout(() => {
            triggerAutoRouteRecalculation();
          }, 500); // Small delay to allow disruption files to be updated
        }
      } else {
        throw new Error(data.error || 'Failed to save incident');
      }
      
    } catch (error) {
      console.error('Error saving incident:', error);
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





