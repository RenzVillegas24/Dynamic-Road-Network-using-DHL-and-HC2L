/**
 * Panel Population Functions
 * Handles populating the Route Metrics Panel and Disruption Analysis Panel
 * with data from DHL and HC2L routing APIs
 */

/**
 * Populate the Algorithm Metrics Panel (non-disruption data)
 * Shows: algorithm, query_time, labeling metrics, path info, distances, ETA
 * @param {Object} routeData - The complete route response from backend
 */
window.populateRouteMetricsPanel = function(routeData) {
  console.log('📊 Populating Route Metrics Panel with:', routeData);
  
  if (!routeData) {
    console.warn('⚠️ No route data provided to populateRouteMetricsPanel');
    return;
  }

  // Extract metrics object
  const metrics = routeData.metrics || {};
  
  // Determine which algorithm is being used
  const algorithm = routeData.algorithm || '';
  const isHC2L = algorithm.includes('HC2L') || algorithm.includes('Hierarchical');
  const isDHL = algorithm.includes('DHL') || algorithm.includes('Dual-Hierarchy');
  
  console.log(`🔍 Algorithm detected: ${algorithm} (HC2L: ${isHC2L}, DHL: ${isDHL})`);
  
  // Show/Hide algorithm-specific sections
  const hc2lLabelingSection = document.getElementById('hc2l-labeling-info-section');
  const hc2lLazySection = document.getElementById('hc2l-lazy-section');
  const dhlUpdateSection = document.getElementById('dhl-update-info-section');
  const disruptionConfigSection = document.getElementById('disruption-config-section');
  
  // Labeling Information: Show for BOTH algorithms (now DHL has it too)
  if (hc2lLabelingSection) {
    hc2lLabelingSection.style.display = 'block';  // Always show
  }
  
  // LazyHC2L Section: HC2L only
  if (hc2lLazySection) {
    hc2lLazySection.style.display = isHC2L ? 'block' : 'none';
  }
  
  // DHL Update Section: DHL only
  if (dhlUpdateSection) {
    dhlUpdateSection.style.display = isDHL ? 'block' : 'none';
  }
  
  // Disruption Configuration: HC2L only (DHL doesn't need tau threshold)
  if (disruptionConfigSection) {
    disruptionConfigSection.style.display = isHC2L ? 'block' : 'none';
  }
  
  // Populate Algorithm
  const algorithmEl = document.getElementById('metrics-algorithm');
  if (algorithmEl) {
    algorithmEl.textContent = routeData.algorithm || '--';
  }
  
  // Populate Query Time
  const queryTimeEl = document.getElementById('metrics-query-time');
  if (queryTimeEl) {
    const queryTime = metrics.query_time_ms;
    queryTimeEl.textContent = queryTime !== undefined ? `${queryTime.toFixed(3)} ms` : '-- ms';
  }
  
  // Populate Baseline ETA (from disruptions_summary if available)
  const baselineEtaEl = document.getElementById('metrics-baseline-eta');
  if (baselineEtaEl) {
    const baselineEta = routeData.disruptions_summary?.route?.baseline_eta_seconds;
    if (baselineEta !== undefined) {
      baselineEtaEl.textContent = `${baselineEta.toFixed(0)} sec (${formatTime(baselineEta)})`;
    } else {
      baselineEtaEl.textContent = '-- sec';
    }
  }
  
  // Populate Actual ETA
  const actualEtaEl = document.getElementById('metrics-actual-eta');
  if (actualEtaEl) {
    const actualEta = metrics.eta_seconds || routeData.disruptions_summary?.route?.actual_eta_seconds;
    if (actualEta !== undefined) {
      actualEtaEl.textContent = `${actualEta.toFixed(0)} sec (${metrics.eta_formatted || formatTime(actualEta)})`;
    } else {
      actualEtaEl.textContent = '-- sec';
    }
  }
  
  // Populate Time Impact
  const timeImpactEl = document.getElementById('metrics-time-impact');
  if (timeImpactEl) {
    const timeImpact = routeData.disruptions_summary?.route?.total_time_impact_seconds;
    if (timeImpact !== undefined) {
      timeImpactEl.textContent = `${timeImpact.toFixed(1)} sec (${formatTime(timeImpact)})`;
      // Color code based on impact
      if (timeImpact > 300) {
        timeImpactEl.classList.add('text-red-600');
      } else if (timeImpact > 60) {
        timeImpactEl.classList.add('text-orange-600');
      } else {
        timeImpactEl.classList.add('text-green-600');
      }
    } else {
      timeImpactEl.textContent = '-- sec';
    }
  }
  
  // Populate Disrupted Edges
  const disruptedEdgesEl = document.getElementById('metrics-disrupted-edges');
  if (disruptedEdgesEl) {
    const disruptedEdges = routeData.disruptions_summary?.route?.total_disrupted_edges;
    disruptedEdgesEl.textContent = disruptedEdges !== undefined ? `${disruptedEdges} edges` : '-- edges';
  }
  
  // Detailed Metrics
  const distanceEl = document.getElementById('metrics-distance');
  if (distanceEl) {
    const distance = metrics.total_distance_units || metrics.total_distance_meters;
    distanceEl.textContent = distance !== undefined ? distance : '--';
  }
  
  const pathLengthEl = document.getElementById('metrics-path-length');
  if (pathLengthEl) {
    pathLengthEl.textContent = metrics.path_length || '--';
  }
  
  const edgeCountEl = document.getElementById('metrics-edge-count');
  if (edgeCountEl && routeData.route && routeData.route.geometry) {
    edgeCountEl.textContent = routeData.route.geometry.length;
  } else if (edgeCountEl) {
    edgeCountEl.textContent = '--';
  }
  
  const usesDisruptionsEl = document.getElementById('metrics-uses-disruptions');
  if (usesDisruptionsEl) {
    const usesDisruptions = metrics.uses_disruptions;
    usesDisruptionsEl.textContent = usesDisruptions ? 'Yes' : 'No';
    usesDisruptionsEl.className = usesDisruptions ? 'font-bold text-orange-600' : 'font-bold text-slate-800';
  }
  
  const labelingTimeEl = document.getElementById('metrics-labeling-time');
  if (labelingTimeEl) {
    const labelingTime = metrics.labeling_time_ms;
    labelingTimeEl.textContent = labelingTime !== undefined ? `${labelingTime.toFixed(3)} ms` : '--';
  }
  
  const labelingSizeEl = document.getElementById('metrics-labeling-size');
  if (labelingSizeEl) {
    const labelingSize = metrics.labeling_size_mb;
    labelingSizeEl.textContent = labelingSize !== undefined ? `${labelingSize.toFixed(2)} MB` : '--';
  }
  
  // ===== ADDITIONAL FIELDS FROM C++ OUTPUT =====
  
  // HC2L Labeling Info (from labeling_info object)
  if (metrics.labeling_info) {
    const labelingInfo = metrics.labeling_info;
    
    // Total labels count
    const totalLabelsEl = document.getElementById('metrics-total-labels');
    if (totalLabelsEl) {
      totalLabelsEl.textContent = labelingInfo.total_labels !== undefined 
        ? labelingInfo.total_labels.toLocaleString() 
        : '--';
    }
    
    // Index size in bytes
    const indexSizeBytesEl = document.getElementById('metrics-index-size-bytes');
    if (indexSizeBytesEl) {
      indexSizeBytesEl.textContent = labelingInfo.index_size_bytes !== undefined 
        ? labelingInfo.index_size_bytes.toLocaleString() + ' bytes' 
        : '--';
    }
    
    // Hierarchy height
    const hierarchyHeightEl = document.getElementById('metrics-hierarchy-height');
    if (hierarchyHeightEl) {
      hierarchyHeightEl.textContent = labelingInfo.hierarchy_height || '--';
    }
    
    // Max label count per node
    const maxLabelCountEl = document.getElementById('metrics-max-label-count');
    if (maxLabelCountEl) {
      maxLabelCountEl.textContent = labelingInfo.max_label_count_per_node || '--';
    }
    
    // Max cut size
    const maxCutSizeEl = document.getElementById('metrics-max-cut-size');
    if (maxCutSizeEl) {
      maxCutSizeEl.textContent = labelingInfo.max_cut_size || '--';
    }
    
    // Average cut size
    const avgCutSizeEl = document.getElementById('metrics-avg-cut-size');
    if (avgCutSizeEl) {
      avgCutSizeEl.textContent = labelingInfo.average_cut_size !== undefined 
        ? labelingInfo.average_cut_size.toFixed(2) 
        : '--';
    }
    
    // Non-empty cuts
    const nonEmptyCutsEl = document.getElementById('metrics-non-empty-cuts');
    if (nonEmptyCutsEl) {
      nonEmptyCutsEl.textContent = labelingInfo.non_empty_cuts !== undefined 
        ? labelingInfo.non_empty_cuts.toLocaleString() 
        : '--';
    }
    
    // Infinite labels
    const infLabelsEl = document.getElementById('metrics-infinite-labels');
    if (infLabelsEl) {
      infLabelsEl.textContent = labelingInfo.infinite_labels !== undefined 
        ? labelingInfo.infinite_labels.toLocaleString() 
        : '--';
    }
    
    // Index load time
    const indexLoadTimeEl = document.getElementById('metrics-index-load-time');
    if (indexLoadTimeEl) {
      indexLoadTimeEl.textContent = labelingInfo.index_load_time_ms !== undefined 
        ? labelingInfo.index_load_time_ms.toFixed(3) + ' ms' 
        : '--';
    }
  }
  
  // LazyHC2L Update Strategy (for HC2L algorithm)
  if (routeData.lazy_hc2l) {
    const lazyHC2L = routeData.lazy_hc2l;
    
    // Update strategy
    const updateStrategyEl = document.getElementById('metrics-update-strategy');
    if (updateStrategyEl) {
      updateStrategyEl.textContent = lazyHC2L.update_strategy || '--';
    }
    
    // Dirty nodes marked
    const dirtyNodesEl = document.getElementById('metrics-dirty-nodes');
    if (dirtyNodesEl) {
      dirtyNodesEl.textContent = lazyHC2L.dirty_nodes_marked !== undefined 
        ? lazyHC2L.dirty_nodes_marked.toLocaleString() 
        : '--';
    }
    
    // Lazy repair time
    const repairTimeEl = document.getElementById('metrics-repair-time');
    if (repairTimeEl) {
      repairTimeEl.textContent = lazyHC2L.lazy_repair_time_ms !== undefined 
        ? lazyHC2L.lazy_repair_time_ms.toFixed(3) + ' ms' 
        : '--';
    }
    
    // Nodes repaired
    const nodesRepairedEl = document.getElementById('metrics-nodes-repaired');
    if (nodesRepairedEl) {
      nodesRepairedEl.textContent = lazyHC2L.nodes_repaired || '--';
    }
    
    // Cache hit status
    const cacheHitEl = document.getElementById('metrics-cache-hit');
    if (cacheHitEl) {
      const cacheHit = lazyHC2L.cache_hit;
      cacheHitEl.textContent = cacheHit ? 'Yes (Cache Hit)' : 'No (Repair Needed)';
      cacheHitEl.className = cacheHit 
        ? 'font-bold text-green-600' 
        : 'font-bold text-orange-600';
    }
    
    // Disruption impact score
    const impactScoreEl = document.getElementById('metrics-impact-score');
    if (impactScoreEl) {
      impactScoreEl.textContent = lazyHC2L.disruption_impact_score !== undefined 
        ? lazyHC2L.disruption_impact_score.toFixed(3) 
        : '--';
    }
    
    // Tau threshold
    const tauThresholdEl = document.getElementById('metrics-tau-threshold');
    if (tauThresholdEl) {
      tauThresholdEl.textContent = lazyHC2L.tau_threshold !== undefined 
        ? lazyHC2L.tau_threshold.toFixed(2) 
        : '--';
    }
  }
  
  // DHL Update Info (for DHL algorithm)
  if (routeData.dhl_update_info) {
    const dhlInfo = routeData.dhl_update_info;
    
    // Algorithm type
    const algorithmTypeEl = document.getElementById('metrics-algorithm-type');
    if (algorithmTypeEl) {
      algorithmTypeEl.textContent = dhlInfo.algorithm_type || '--';
    }
    
    // Update strategy
    const dhlStrategyEl = document.getElementById('metrics-dhl-strategy');
    if (dhlStrategyEl) {
      dhlStrategyEl.textContent = dhlInfo.update_strategy || '--';
    }
    
    // Nodes updated
    const nodesUpdatedEl = document.getElementById('metrics-nodes-updated');
    if (nodesUpdatedEl) {
      nodesUpdatedEl.textContent = dhlInfo.nodes_updated !== undefined 
        ? dhlInfo.nodes_updated.toLocaleString() 
        : '--';
    }
    
    // Disruption impact score
    const dhlImpactEl = document.getElementById('metrics-dhl-impact');
    if (dhlImpactEl) {
      dhlImpactEl.textContent = dhlInfo.disruption_impact_score !== undefined 
        ? dhlInfo.disruption_impact_score.toFixed(3) 
        : '--';
    }
  }
  
  // Tau Threshold (from disruption_config)
  if (routeData.disruption_config) {
    const disruptionConfig = routeData.disruption_config;
    
    const configTauEl = document.getElementById('metrics-config-tau');
    if (configTauEl) {
      configTauEl.textContent = disruptionConfig.tau_threshold !== undefined 
        ? disruptionConfig.tau_threshold.toFixed(2) 
        : '--';
    }
    
    const disruptionFileEl = document.getElementById('metrics-disruption-file');
    if (disruptionFileEl) {
      const filePath = disruptionConfig.disruption_file || '';
      // Extract just the filename
      const fileName = filePath.split('/').pop() || filePath.split('\\').pop() || '--';
      disruptionFileEl.textContent = fileName;
      disruptionFileEl.title = filePath; // Show full path on hover
    }
  }
  
  // Interpolation used (always false in current implementation)
  const interpolationEl = document.getElementById('metrics-interpolation');
  if (interpolationEl) {
    const interpolated = metrics.interpolation_used;
    interpolationEl.textContent = interpolated ? 'Yes' : 'No';
    interpolationEl.className = interpolated 
      ? 'font-bold text-blue-600' 
      : 'font-bold text-slate-600';
  }
  
  // Calculated distances
  const calculatedDistanceEl = document.getElementById('metrics-calculated-distance');
  if (calculatedDistanceEl) {
    const calcDist = metrics.calculated_distance_meters;
    if (calcDist !== undefined) {
      const calcDistKm = metrics.calculated_distance_km || (calcDist / 1000);
      calculatedDistanceEl.textContent = `${calcDistKm.toFixed(2)} km (${calcDist.toFixed(0)} m)`;
    } else {
      calculatedDistanceEl.textContent = '--';
    }
  }
  
  // Populate Alternative Routes Section
  const alternativeRoutesSection = document.getElementById('metrics-alternative-routes-section');
  const alternativeRoutesList = document.getElementById('metrics-alternative-routes-list');
  
  if (routeData.alternative_routes && routeData.alternative_routes.length > 0) {
    // Get primary route color from the main route polyline if available
    let primaryRouteColor = '#3b82f6'; // Default blue
    if (window.routePolylines && window.routePolylines.length > 0) {
      const mainPolyline = window.routePolylines[0];
      if (mainPolyline && mainPolyline.options && mainPolyline.options.color) {
        primaryRouteColor = mainPolyline.options.color;
      }
    }
    
    // Convert hex color to RGB for transparency
    const hexToRgb = (hex) => {
      const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      return result ? `rgb(${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)})` : hex;
    };
    
    // Filter out rank 1 (fastest route - already the main route)
    const alternativeRoutesFiltered = routeData.alternative_routes.filter(r => r.rank > 1);
    
    if (alternativeRoutesFiltered.length > 0) {
      // Show the section
      if (alternativeRoutesSection) {
        alternativeRoutesSection.classList.remove('hidden');
      }
      
      // Clear existing routes
      if (alternativeRoutesList) {
        alternativeRoutesList.innerHTML = '';
        
        alternativeRoutesFiltered.forEach((altRoute, index) => {
          // Use primary route color with varying opacity
          const rgbColor = hexToRgb(primaryRouteColor);
          const bgColor = primaryRouteColor + '15'; // Add transparency (15 = 8% opacity)
          const borderColor = primaryRouteColor;
          
          // Check if this route is currently selected
          const isSelected = window.currentSelectedAlternativeRouteIndex === index;
          
          const routeCard = document.createElement('div');
          routeCard.className = 'border-2 rounded-xl p-3 cursor-pointer hover:shadow-md transition-all';
          routeCard.id = `alt-route-card-${index}`; // Add ID for state tracking
          
          // Apply selected or unselected styles
          if (isSelected) {
            routeCard.style.backgroundColor = primaryRouteColor + '25'; // More visible when selected
            routeCard.style.borderColor = primaryRouteColor;
            routeCard.style.borderWidth = '3px'; // Thicker border when selected
            routeCard.style.boxShadow = `0 0 12px ${primaryRouteColor}40`; // Glow effect
          } else {
            routeCard.style.backgroundColor = bgColor;
            routeCard.style.borderColor = borderColor;
            routeCard.style.borderWidth = '2px';
            routeCard.style.boxShadow = 'none';
          }
          
          routeCard.onclick = () => highlightAlternativeRoute(index, altRoute);
          
          const etaMinutes = (altRoute.eta_seconds / 60).toFixed(1);
          const distanceKm = (altRoute.distance / 1000).toFixed(2);
          
          // Get text color to match primary route color (for badge)
          let badgeTextColor = '#ffffff'; // Default white text
          let badgeBgColor = primaryRouteColor;
          
          routeCard.innerHTML = `
            <div class="flex items-start gap-3">
              <div class="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold" style="background-color: ${badgeBgColor}; color: ${badgeTextColor};">
                ${altRoute.rank}
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-bold text-sm mb-1" style="color: ${primaryRouteColor};">
                  ${altRoute.description || `Alternative Route ${index + 1}`}
                </div>
                <div class="text-xs text-slate-600 space-y-1">
                  <div class="flex items-center justify-between">
                    <span><strong>Distance:</strong> ${distanceKm} km</span>
                    <span><strong>ETA:</strong> ${etaMinutes} min</span>
                  </div>
                  <div>
                    <strong>Avg Jam Factor:</strong> 
                    <span class="${altRoute.avg_jam_factor > 5 ? 'font-bold' : ''}" style="color: ${primaryRouteColor};">${altRoute.avg_jam_factor.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            </div>
          `;
          
          alternativeRoutesList.appendChild(routeCard);
        });
      }
    } else {
      // Hide the section if no alternative routes (after filtering rank 1)
      if (alternativeRoutesSection) {
        alternativeRoutesSection.classList.add('hidden');
      }
    }
  } else {
    // Hide the section if no alternative routes
    if (alternativeRoutesSection) {
      alternativeRoutesSection.classList.add('hidden');
    }
  }
  
  console.log('✅ Route Metrics Panel populated successfully with all fields');
};

/**
 * Populate the Disruption Analysis Panel (disruption-specific data)
 * Shows: disruptions_summary.route.*, disruptions_summary.network.*, all_disruptions list
 * @param {Object} routeData - The complete route response from backend
 */
window.populateDisruptionsPanel = function(routeData) {
  console.log('🚧 Populating Disruption Analysis Panel with:', routeData);
  
  if (!routeData || !routeData.disruptions_summary) {
    console.warn('⚠️ No disruption data available');
    
    // Hide the disruption alert if no data
    const alertContainer = document.getElementById('disruption-alert-container');
    if (alertContainer) {
      alertContainer.classList.add('hidden');
    }
    return;
  }

  const disruptions = routeData.disruptions_summary;
  const routeDisruptions = disruptions.route || {};
  const networkDisruptions = disruptions.network || {};
  
  // Show disruption alert in Current Path Panel
  const alertContainer = document.getElementById('disruption-alert-container');
  if (alertContainer) {
    const totalDisruptions = routeDisruptions.total_disrupted_edges || 0;
    if (totalDisruptions > 0) {
      alertContainer.classList.remove('hidden');
      
      // Update alert text
      const titleEl = document.getElementById('disruption-alert-title');
      if (titleEl) {
        titleEl.textContent = `${totalDisruptions} Disruption${totalDisruptions !== 1 ? 's' : ''} Detected`;
      }
      
      const summaryEl = document.getElementById('disruption-alert-summary');
      if (summaryEl) {
        const critical = routeDisruptions.critical || 0;
        const high = routeDisruptions.high || 0;
        const medium = routeDisruptions.medium || 0;
        const low = routeDisruptions.low || 0;
        
        let summaryParts = [];
        if (critical > 0) summaryParts.push(`${critical} critical`);
        if (high > 0) summaryParts.push(`${high} high`);
        if (medium > 0) summaryParts.push(`${medium} medium`);
        if (low > 0) summaryParts.push(`${low} low`);
        
        summaryEl.textContent = summaryParts.join(', ') || 'Various severities';
      }
      
      const impactEl = document.getElementById('disruption-alert-impact');
      if (impactEl) {
        const timeImpact = routeDisruptions.total_time_impact_seconds || 0;
        const timeImpactMin = (timeImpact / 60).toFixed(1);
        impactEl.textContent = `Time Impact: +${timeImpactMin} min`;
      }
    } else {
      alertContainer.classList.add('hidden');
    }
  }
  
  // ===== Populate Disruption Analysis Panel =====
  
  // Summary Cards
  const routeDisruptionCount = document.getElementById('route-disruption-count');
  if (routeDisruptionCount) {
    routeDisruptionCount.textContent = routeDisruptions.total_disrupted_edges || '--';
  }
  
  const routeTimeImpact = document.getElementById('route-time-impact');
  if (routeTimeImpact) {
    const impactSeconds = routeDisruptions.total_time_impact_seconds;
    if (impactSeconds !== undefined) {
      const impactMin = routeDisruptions.total_time_impact_minutes || (impactSeconds / 60);
      routeTimeImpact.textContent = `+${impactMin.toFixed(1)} min`;
    } else {
      routeTimeImpact.textContent = '--';
    }
  }

  const routeBaseImpact = document.getElementById('route-base-time');
  if (routeBaseImpact) {
    const baselineEta = routeDisruptions.baseline_eta_seconds;
    if (baselineEta !== undefined) {
      routeBaseImpact.textContent = formatTime(baselineEta);
    } else {
      routeBaseImpact.textContent = '--';
    }
  }

  const routeTotalTime = document.getElementById('route-total-time');
  if (routeTotalTime) {
    const actualEta = routeDisruptions.actual_eta_seconds;
    if (actualEta !== undefined) {
      routeTotalTime.textContent = formatTime(actualEta);
    } else {
      routeTotalTime.textContent = '--';
    }
  }
  
  // Traffic Flow Status Breakdown (instead of Severity Breakdown)
  const flowStatuses = {
    'free_flow': 0,
    'light': 0,
    'moderate': 0,
    'heavy': 0,
    'blocked': 0,
    'default': 0
  };
  
  const totalDisruptions = routeDisruptions.total_disrupted_edges || 0;
  
  // Count disruptions by flow status from all_disruptions
  if (disruptions.all_disruptions && disruptions.all_disruptions.length > 0) {
    disruptions.all_disruptions.forEach(disruption => {
      const status = disruption.flow_status || 'default';
      if (flowStatuses.hasOwnProperty(status)) {
        flowStatuses[status]++;
      }
    });
  }
  
  // Update counts and percentages
  const flowStatusElements = {
    'free_flow': { count: 'flow-free-count', percent: 'flow-free-percent', bar: 'flow-free-bar' },
    'light': { count: 'flow-light-count', percent: 'flow-light-percent', bar: 'flow-light-bar' },
    'moderate': { count: 'flow-moderate-count', percent: 'flow-moderate-percent', bar: 'flow-moderate-bar' },
    'heavy': { count: 'flow-heavy-count', percent: 'flow-heavy-percent', bar: 'flow-heavy-bar' },
    'blocked': { count: 'flow-blocked-count', percent: 'flow-blocked-percent', bar: 'flow-blocked-bar' }
  };
  
  if (totalDisruptions > 0) {
    Object.keys(flowStatusElements).forEach(status => {
      const count = flowStatuses[status] || 0;
      const percent = ((count / totalDisruptions) * 100).toFixed(0);
      
      const countEl = document.getElementById(flowStatusElements[status].count);
      const percentEl = document.getElementById(flowStatusElements[status].percent);
      const barEl = document.getElementById(flowStatusElements[status].bar);
      
      if (countEl) countEl.textContent = count;
      if (percentEl) percentEl.textContent = `${percent}%`;
      if (barEl) barEl.style.width = `${percent}%`;
    });
  } else {
    Object.keys(flowStatusElements).forEach(status => {
      const countEl = document.getElementById(flowStatusElements[status].count);
      const percentEl = document.getElementById(flowStatusElements[status].percent);
      const barEl = document.getElementById(flowStatusElements[status].bar);
      
      if (countEl) countEl.textContent = '0';
      if (percentEl) percentEl.textContent = '0%';
      if (barEl) barEl.style.width = '0%';
    });
  }
  
  // Network Statistics
  const networkTotalEl = document.getElementById('network-total-disruptions');
  if (networkTotalEl) {
    networkTotalEl.textContent = networkDisruptions.total_incidents || '--';
  }
  
  const networkCoverageEl = document.getElementById('network-coverage');
  if (networkCoverageEl) {
    // Placeholder - coverage area not in current C++ output
    networkCoverageEl.textContent = '--';
  }
  
  // Algorithm Performance Details
  const analysisAlgorithm = document.getElementById('analysis-algorithm');
  if (analysisAlgorithm) {
    analysisAlgorithm.textContent = routeData.algorithm || '--';
  }
  
  const analysisQueryTime = document.getElementById('analysis-query-time');
  if (analysisQueryTime) {
    const queryTime = routeData.metrics?.query_time_ms;
    analysisQueryTime.textContent = queryTime !== undefined ? `${queryTime.toFixed(3)} ms` : '--';
  }
  
  const analysisDisruptedEdges = document.getElementById('analysis-disrupted-edges');
  if (analysisDisruptedEdges) {
    analysisDisruptedEdges.textContent = routeDisruptions.total_disrupted_edges || '--';
  }
  
  // Top Disruptions List
  const topDisruptionsList = document.getElementById('top-disruptions-list');
  const topDisruptionsCount = document.getElementById('top-disruptions-count');
  
  if (topDisruptionsList && disruptions.all_disruptions && disruptions.all_disruptions.length > 0) {
    const allDisruptions = disruptions.all_disruptions;
    
    // Update count
    if (topDisruptionsCount) {
      topDisruptionsCount.textContent = `${allDisruptions.length} disruptions`;
    }
    
    // Clear existing list
    topDisruptionsList.innerHTML = '';
    
    // Show top 10 disruptions (or all if less than 10)
    const displayCount = Math.min(allDisruptions.length, 10);
    
    for (let i = 0; i < displayCount; i++) {
      const disruption = allDisruptions[i];
      
      // Determine flow status color with both Tailwind classes and inline styles
      let flowColor = 'slate';
      let flowBgClass = 'bg-slate-50';
      let flowBorderClass = 'border-slate-200';
      let flowIconColor = '#64748b'; // slate-500
      let flowTextColor = '#1e293b'; // slate-900
      let flowIcon = '◑';
      const flowStatus = disruption.flow_status || 'default';
      
      if (flowStatus === 'blocked') {
        flowColor = 'red';
        flowBgClass = 'bg-red-50';
        flowBorderClass = 'border-red-500';
        flowIconColor = '#dc2626'; // red-600
        flowTextColor = '#7f1d1d'; // red-900
        flowIcon = '🚫';
      } else if (flowStatus === 'heavy') {
        flowColor = 'orange';
        flowBgClass = 'bg-orange-50';
        flowBorderClass = 'border-orange-500';
        flowIconColor = '#ea580c'; // orange-600
        flowTextColor = '#7c2d12'; // orange-900
        flowIcon = '🔴';
      } else if (flowStatus === 'moderate') {
        flowColor = 'yellow';
        flowBgClass = 'bg-yellow-50';
        flowBorderClass = 'border-yellow-500';
        flowIconColor = '#ca8a04'; // yellow-600
        flowTextColor = '#713f12'; // yellow-900
        flowIcon = '🟡';
      } else if (flowStatus === 'light') {
        flowColor = 'green';
        flowBgClass = 'bg-green-50';
        flowBorderClass = 'border-green-500';
        flowIconColor = '#16a34a'; // green-600
        flowTextColor = '#15803d'; // green-900
        flowIcon = '🟢';
      } else if (flowStatus === 'free_flow') {
        flowColor = 'blue';
        flowBgClass = 'bg-blue-50';
        flowBorderClass = 'border-blue-500';
        flowIconColor = '#2563eb'; // blue-600
        flowTextColor = '#1e40af'; // blue-900
        flowIcon = '✓';
      }
      
      const disruptionCard = document.createElement('div');
      disruptionCard.className = `${flowBgClass} border-2 ${flowBorderClass} rounded-xl p-3 cursor-pointer hover:shadow-md transition-all`;
      disruptionCard.onclick = () => showEdgeDetails(disruption);
      
      // Get road name or use fallback
      const roadName = disruption.road_name || 'Unknown Road';
      const flowStatusDisplay = flowStatus.replace(/_/g, ' ').toUpperCase();
      const disruptionType = getDisruptionField(disruption, 'type') || 'Unknown';
      const currentSpeed = getDisruptionField(disruption, 'current_speed') || 0;
      const jamFactor = getDisruptionField(disruption, 'jam_factor') || 0;
      const timeImpact = getDisruptionField(disruption, 'time_impact_seconds');
      const confidence = getDisruptionField(disruption, 'confidence');
      const description = getDisruptionField(disruption, 'description');
      const roadClosed = getDisruptionField(disruption, 'road_closed');
      
      disruptionCard.innerHTML = `
        <div class="flex items-start gap-3">
          <div class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-lg" style="background-color: ${flowIconColor};">
            ${flowIcon}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between mb-1 flex-wrap gap-1">
              <div class="font-bold text-sm" style="color: ${flowTextColor};">${roadName}</div>
              <div class="text-xs px-2 py-1 rounded-lg font-semibold uppercase" style="background-color: ${flowIconColor}20; color: ${flowIconColor};">
                ${flowStatusDisplay}
              </div>
            </div>
            <div class="text-xs text-slate-600 space-y-1">
              <div><strong>Type:</strong> ${disruptionType}</div>
              <div><strong>Edge:</strong> ${disruption.source} → ${disruption.target}</div>
              ${description ? `<div class="italic text-slate-500">"${description}"</div>` : ''}
              <div class="flex items-center gap-3 mt-2 flex-wrap">
                <div>
                  <strong>Speed:</strong> 
                  <span class="font-semibold" style="color: ${flowIconColor};">${currentSpeed.toFixed(1)} km/h</span>
                </div>
                <div>
                  <strong>Jam Factor:</strong> 
                  <span class="font-semibold" style="color: ${flowIconColor};">${jamFactor.toFixed(2)}</span>
                </div>
                ${timeImpact !== undefined ? `
                  <div>
                    <strong>Impact:</strong> 
                    <span class="font-bold" style="color: ${flowIconColor};">+${timeImpact.toFixed(0)}s</span>
                  </div>
                ` : ''}
              </div>
              ${confidence !== undefined ? `
                <div class="mt-1">
                  <strong>Confidence:</strong> 
                  <span class="font-semibold">${(confidence * 100).toFixed(0)}%</span>
                </div>
              ` : ''}
              ${roadClosed ? `
                <div class="text-red-600 font-bold mt-1">🚫 ROAD CLOSED</div>
              ` : ''}
            </div>
          </div>
        </div>
      `;
      
      topDisruptionsList.appendChild(disruptionCard);
    }
  } else if (topDisruptionsList) {
    // Show empty state
    if (topDisruptionsCount) {
      topDisruptionsCount.textContent = '0 disruptions';
    }
    
    topDisruptionsList.innerHTML = `
      <div class="text-center text-slate-400 py-8">
        <svg class="w-16 h-16 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <p class="font-medium">No disruption data available</p>
        <p class="text-sm mt-1">Calculate a route to see disruptions</p>
      </div>
    `;
  }
  
  console.log('✅ Disruption Analysis Panel populated successfully');
};

/**
 * Helper function to format time in seconds to human-readable format
 * @param {number} seconds - Time in seconds
 * @returns {string} Formatted time string (e.g., "5m 32s", "1h 23m")
 */
function formatTime(seconds) {
  if (!seconds || seconds < 0) return '0s';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}

/**
 * Show edge details popup when clicking on disruption item
 * Finds the edge on the currently displayed route and shows a popup with details
 * @param {Object} disruption - The disruption object containing edge and traffic info
 */
window.showEdgeDetails = function(disruption) {
  console.log('🔍 Showing edge details for disruption:', disruption);
  
  if (!window.map) {
    console.error('❌ Map not initialized');
    return;
  }
  
  // Try to find the edge in current route polylines
  let foundPolyline = null;
  
  // Check if we have routePolylines array (from displayRoute functions)
  if (window.routePolylines && window.routePolylines.length > 0) {
    foundPolyline = window.routePolylines.find(polyline => {
      const segment = polyline._segmentData;
      if (segment) {
        return (segment.from === disruption.source && segment.to === disruption.target) ||
               (segment.source === disruption.source && segment.target === disruption.target);
      }
      return false;
    });
  }
  
  if (foundPolyline) {
    // Found the polyline, highlight it and open popup
    console.log('✅ Found matching edge polyline, highlighting and opening popup');
    
    // Highlight this segment
    window.routePolylines.forEach((p) => {
      if (p === foundPolyline) {
        p.setStyle({ weight: 10, color: p._originalColor || '#ef4444' });
        p._isHighlighted = true;
      } else {
        p.setStyle({ weight: 6, opacity: 0.4 });
        p._isHighlighted = false;
      }
    });
    
    // Pan to this segment
    const bounds = foundPolyline.getBounds();
    window.map.fitBounds(bounds, { padding: [50, 50] });
    
    // Open popup if exists
    if (foundPolyline.getPopup()) {
      foundPolyline.openPopup();
    }
  } else {
    // Edge not found in current route, show a custom popup at map center with disruption info
    console.warn('⚠️ Edge not found in current route, showing info popup');
    
    // Get disruption data with compatibility layer
    const severityLevel = getDisruptionField(disruption, 'severity_level') || 'medium';
    const type = getDisruptionField(disruption, 'type') || 'Unknown';
    const timeImpact = getDisruptionField(disruption, 'time_impact_seconds');
    const confidence = getDisruptionField(disruption, 'confidence');
    const roadClosed = getDisruptionField(disruption, 'road_closed');
    const description = getDisruptionField(disruption, 'description');
    
    // Determine severity color
    let severityColor = '#f59e0b'; // amber for medium
    if (severityLevel === 'critical' || severityLevel === 'high') {
      severityColor = '#ef4444'; // red
    } else if (severityLevel === 'low' || severityLevel === 'none') {
      severityColor = '#10b981'; // green
    }
    
    const popupContent = `
      <div class="p-3" style="min-width: 280px;">
        <div class="font-bold text-lg mb-2 border-b pb-2" style="color: ${severityColor}">
          🚨 Disruption Details
        </div>
        
        <div class="space-y-2 text-sm">
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Road Name:</span>
            <span class="font-semibold text-indigo-700">${disruption.road_name || 'Unknown Road'}</span>
          </div>
          
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Edge:</span>
            <span class="font-mono font-semibold">${disruption.source} → ${disruption.target}</span>
          </div>
          
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Type:</span>
            <span class="px-2 py-0.5 bg-slate-100 rounded text-xs font-semibold">${type}</span>
          </div>
          
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Severity:</span>
            <span class="px-2 py-0.5 rounded text-xs font-semibold text-white" style="background-color: ${severityColor}">
              ${severityLevel.toUpperCase()}
            </span>
          </div>
          
          ${timeImpact !== undefined ? `
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Time Impact:</span>
            <span class="font-bold text-red-600">+${timeImpact.toFixed(0)}s</span>
          </div>
          ` : ''}
          
          ${confidence !== undefined ? `
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Confidence:</span>
            <span class="font-semibold">${(confidence * 100).toFixed(0)}%</span>
          </div>
          ` : ''}
          
          ${roadClosed ? `
          <div class="mt-2 p-2 bg-red-50 border border-red-200 rounded">
            <div class="flex items-center gap-2">
              <span class="text-red-600 font-bold">🚫 ROAD CLOSED</span>
            </div>
          </div>
          ` : ''}
          
          ${description ? `
          <div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded">
            <div class="text-xs text-blue-800 italic">
              "${description}"
            </div>
          </div>
          ` : ''}
        </div>
      </div>
    `;
    
    // Create a popup at the center of the map
    const mapCenter = window.map.getCenter();
    L.popup({
      maxWidth: 320,
      className: 'disruption-info-popup'
    })
    .setLatLng(mapCenter)
    .setContent(popupContent)
    .openOn(window.map);
  }
};

/**
 * Highlight an alternative route on the map when clicked
 * @param {number} routeIndex - Index of the route in alternative_routes array
 * @param {Object} altRoute - The alternative route object
 */
window.highlightAlternativeRoute = function(routeIndex, altRoute) {
  console.log(`🗺️ CLICK: Highlighting alternative route ${routeIndex}`, altRoute);
  console.log(`📊 Current state: selectedIndex=${window.currentSelectedAlternativeRouteIndex}, clickedIndex=${routeIndex}`);
  
  if (!window.alternativeRoutePolylines || window.alternativeRoutePolylines.length === 0) {
    console.warn('⚠️ No alternative route polylines found on map');
    return;
  }

  // Check if user is clicking the same route that's already selected (toggle off)
  if (window.currentSelectedAlternativeRouteIndex === routeIndex) {
    console.log(`✋ DESELECT: Clicking same route again - deselecting route ${routeIndex}`);
    window.currentSelectedAlternativeRouteIndex = null;
    resetAlternativeRoutesDisplay();
    return;
  }

  console.log(`✨ NEW SELECTION: Selecting route ${routeIndex}`);
  
  // If there was a previously selected route, first reset the entire display
  // This ensures all polylines return to baseline state
  if (window.currentSelectedAlternativeRouteIndex !== null) {
    console.log(`🔄 SWITCHING: From route ${window.currentSelectedAlternativeRouteIndex} to route ${routeIndex}`);
    
    // Reset all alternative polylines to baseline
    if (window.alternativeRoutePolylines && window.alternativeRoutePolylines.length > 0) {
      window.alternativeRoutePolylines.forEach((p) => {
        p.setStyle({
          opacity: 0.35,
          weight: 4,
          dashArray: '8, 4'
        });
        p._isHighlighted = false;
      });
    }
  }

  // Now set the new selection
  window.currentSelectedAlternativeRouteIndex = routeIndex;
  console.log(`✅ State updated: currentSelectedAlternativeRouteIndex = ${routeIndex}`);

  // Hide the primary/best route (make it completely transparent)
  if (window.routePolylines && window.routePolylines.length > 0) {
    window.routePolylines.forEach(polyline => {
      if (polyline && polyline.setStyle) {
        polyline.setStyle({ opacity: 0.15 });
      }
    });
    console.log('🙈 PRIMARY ROUTE: Hidden (opacity: 0)');
  }

  // Highlight ONLY the selected route's polylines
  if (window.alternativeRoutePolylines && window.alternativeRoutePolylines.length > 0) {
    window.alternativeRoutePolylines.forEach((p) => {
      if (p._routeIndex === routeIndex) {
        // Highlight this route
        p.setStyle({
          opacity: 0.8,
          weight: 6,
          dashArray: '4, 2'
        });
        p._isHighlighted = true;
        console.log(`✨ ROUTE ${routeIndex}: Highlighted`);
      } else {
        // Dim all other routes
        p.setStyle({
          opacity: 0.15,
          weight: 3,
          dashArray: '8, 4'
        });
        p._isHighlighted = false;
      }
    });
  }
  
  console.log(`🎨 CARD STYLING: Updating card visuals`);
  updateAlternativeRouteCardStyling();

  // Zoom to the bounds of all polylines in this route
  if (routePolylines.length > 0 && window.map) {
    try {
      // Calculate bounds from all polylines in this route
      let allBounds = null;
      routePolylines.forEach(p => {
        if (p.getBounds) {
          const bounds = p.getBounds();
          if (allBounds) {
            allBounds.extend(bounds);
          } else {
            allBounds = bounds;
          }
        }
      });
      
      if (allBounds && allBounds.isValid()) {
        window.map.fitBounds(allBounds, { padding: [50, 50], maxZoom: 16 });
        console.log(`📍 Zoomed to route ${routeIndex} bounds`);
      }
    } catch (e) {
      console.warn('Could not zoom to route bounds:', e);
    }
  }
  
  // Show a popup with route details
  const etaFormatted = altRoute.eta_formatted || formatTime(altRoute.eta_seconds);
  const distanceKm = (altRoute.distance_meters / 1000).toFixed(2);
  const jamColor = altRoute.avg_jam_factor > 5 ? '#ef4444' : '#10b981';
  
  const popupContent = `
    <div class="p-3 bg-white rounded-lg" style="min-width: 280px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
      <div class="font-bold text-lg mb-2 border-b pb-2" style="color: #8b5cf6;">
        🛣️ ${altRoute.description || `Alternative Route ${routeIndex + 1}`}
      </div>
      
      <div class="space-y-2 text-sm">
        <div class="flex justify-between items-center">
          <span class="text-gray-600 font-medium">Rank:</span>
          <span class="px-2 py-1 bg-purple-100 text-purple-800 rounded font-bold">#${altRoute.rank || (routeIndex + 1)}</span>
        </div>
        
        <div class="flex justify-between items-center">
          <span class="text-gray-600 font-medium">Distance:</span>
          <span class="font-bold text-blue-600">${distanceKm} km</span>
        </div>
        
        <div class="flex justify-between items-center">
          <span class="text-gray-600 font-medium">ETA:</span>
          <span class="font-semibold">${etaFormatted}</span>
        </div>
        
        <div class="flex justify-between items-center">
          <span class="text-gray-600 font-medium">Avg Jam Factor:</span>
          <span class="font-bold" style="color: ${jamColor};">${altRoute.avg_jam_factor.toFixed(2)}</span>
        </div>
        
        <div class="flex justify-between items-center">
          <span class="text-gray-600 font-medium">Path Segments:</span>
          <span class="font-semibold">${altRoute.path_length || 'N/A'}</span>
        </div>
      </div>
      
      <div class="mt-3 pt-3 border-t">
        <button onclick="switchToAlternativeRoute(${routeIndex})" 
          class="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold py-2 px-3 rounded-lg transition-all text-sm shadow">
          ✅ Switch to This Route
        </button>
      </div>
    </div>
  `;
  
  // Show popup on first polyline
  if (routePolylines.length > 0 && routePolylines[0].bindPopup) {
    routePolylines[0].bindPopup(popupContent, {
      maxWidth: 340,
      className: 'alternative-route-popup',
      closeButton: true
    }).openPopup();
  }
  
  showUpdateToast(`✅ Highlighted alternative route ${routeIndex + 1}`, 'success');
};

/**
 * Reset alternative routes display to normal state
 * Called when user deselects a route or needs to see the best route again
 */
window.resetAlternativeRoutesDisplay = function() {
  console.log(`🔄 RESET: Clearing selection (was: ${window.currentSelectedAlternativeRouteIndex})`);
  
  // Clear the selected route tracking FIRST
  window.currentSelectedAlternativeRouteIndex = null;
  console.log('✅ State cleared: currentSelectedAlternativeRouteIndex = null');
  
  // Show the primary/best route again (restore to original opacity)
  if (window.routePolylines && window.routePolylines.length > 0) {
    window.routePolylines.forEach(polyline => {
      if (polyline && polyline.setStyle) {
        polyline.setStyle({ opacity: 0.8 });
      }
    });
    console.log('👁️ PRIMARY ROUTE: Restored (opacity: 0.8)');
  } else {
    console.warn('⚠️ No primary route polylines found');
  }
  
  // Reset all alternative routes to baseline state
  if (window.alternativeRoutePolylines && window.alternativeRoutePolylines.length > 0) {
    window.alternativeRoutePolylines.forEach((p) => {
      if (p && p.setStyle) {
        p.setStyle({
          opacity: 0.35,
          weight: 4,
          dashArray: '8, 4'
        });
        p._isHighlighted = false;
      }
    });
    console.log(`🔀 ALTERNATIVES: Reset ${window.alternativeRoutePolylines.length} routes to baseline`);
  } else {
    console.warn('⚠️ No alternative route polylines found');
  }
  
  // Update card styling to remove all highlights
  console.log('🎨 CARD STYLING: Removing all highlights');
  updateAlternativeRouteCardStyling();
  
  showUpdateToast('✅ Best route visible', 'success');
};

/**
 * Update the visual styling of alternative route cards in the metrics panel
 * Called after selection state changes to reflect current selection
 */
function updateAlternativeRouteCardStyling() {
  console.log(`🎨 Card styling: Updating cards (currentSelectedIndex=${window.currentSelectedAlternativeRouteIndex})`);
  
  // Get the primary route color for consistency
  let primaryRouteColor = '#3b82f6'; // Default blue
  if (window.routePolylines && window.routePolylines.length > 0) {
    const mainPolyline = window.routePolylines[0];
    if (mainPolyline && mainPolyline.options && mainPolyline.options.color) {
      primaryRouteColor = mainPolyline.options.color;
    }
  }
  
  // Update each alternative route card
  const alternativeRoutesList = document.getElementById('metrics-alternative-routes-list');
  if (alternativeRoutesList) {
    const cards = alternativeRoutesList.querySelectorAll('[id^="alt-route-card-"]');
    console.log(`🎨 Found ${cards.length} route cards to style`);
    
    cards.forEach((card, index) => {
      const isSelected = window.currentSelectedAlternativeRouteIndex === index;
      console.log(`  Card ${index}: isSelected=${isSelected}`);
      
      if (isSelected) {
        // Selected state: more visible, glow effect, thicker border
        card.style.backgroundColor = primaryRouteColor + '25'; // 15% opacity
        card.style.borderColor = primaryRouteColor;
        card.style.borderWidth = '3px';
        card.style.boxShadow = `0 0 12px ${primaryRouteColor}40`; // Glow
        console.log(`    ✨ Applied SELECTED styling (glow, thicker border)`);
      } else {
        // Unselected state: normal styling
        const bgColor = primaryRouteColor + '15'; // 8% opacity
        card.style.backgroundColor = bgColor;
        card.style.borderColor = primaryRouteColor;
        card.style.borderWidth = '2px';
        card.style.boxShadow = 'none';
        console.log(`    ⚪ Applied UNSELECTED styling (normal)`);
      }
    });
  } else {
    console.warn('⚠️ Alternative routes list not found');
  }
}

// Alias for backward compatibility - functions.js calls updateDisruptionsPanel
window.updateDisruptionsPanel = window.populateDisruptionsPanel;

console.log('✅ Panel Population module loaded');

