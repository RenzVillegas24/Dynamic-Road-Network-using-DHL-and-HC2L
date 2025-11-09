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
    // Show the section
    if (alternativeRoutesSection) {
      alternativeRoutesSection.classList.remove('hidden');
    }
    
    // Clear existing routes
    if (alternativeRoutesList) {
      alternativeRoutesList.innerHTML = '';
      
      routeData.alternative_routes.forEach((altRoute, index) => {
        // Determine color based on rank
        const colors = [
          { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', badge: 'bg-blue-500' },
          { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-800', badge: 'bg-green-500' },
          { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-800', badge: 'bg-purple-500' }
        ];
        const color = colors[index % colors.length];
        
        const routeCard = document.createElement('div');
        routeCard.className = `${color.bg} border ${color.border} rounded-xl p-3 cursor-pointer hover:shadow-md transition-all`;
        routeCard.onclick = () => highlightAlternativeRoute(index, altRoute);
        
        const etaMinutes = (altRoute.eta_seconds / 60).toFixed(1);
        const distanceKm = (altRoute.distance / 1000).toFixed(2);
        
        routeCard.innerHTML = `
          <div class="flex items-start gap-3">
            <div class="flex-shrink-0 w-10 h-10 ${color.badge} rounded-lg flex items-center justify-center text-white font-bold">
              ${altRoute.rank || (index + 1)}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-bold ${color.text} text-sm mb-1">
                ${altRoute.description || `Route ${index + 1}`}
              </div>
              <div class="text-xs text-slate-600 space-y-1">
                <div class="flex items-center justify-between">
                  <span><strong>Distance:</strong> ${distanceKm} km</span>
                  <span><strong>ETA:</strong> ${etaMinutes} min</span>
                </div>
                <div>
                  <strong>Avg Jam Factor:</strong> 
                  <span class="${altRoute.avg_jam_factor > 5 ? 'text-red-600 font-bold' : 'text-green-600'}">${altRoute.avg_jam_factor.toFixed(1)}</span>
                </div>
              </div>
            </div>
          </div>
        `;
        
        alternativeRoutesList.appendChild(routeCard);
      });
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
  
  // Severity Breakdown
  const totalDisruptions = routeDisruptions.total_disrupted_edges || 0;
  const critical = routeDisruptions.critical || 0;
  const high = routeDisruptions.high || 0;
  const medium = routeDisruptions.medium || 0;
  const low = routeDisruptions.low || 0;
  
  // Update counts
  document.getElementById('severity-critical').textContent = critical;
  document.getElementById('severity-high').textContent = high;
  document.getElementById('severity-medium').textContent = medium;
  document.getElementById('severity-low').textContent = low;
  
  // Update percentages
  if (totalDisruptions > 0) {
    const criticalPercent = ((critical / totalDisruptions) * 100).toFixed(0);
    const highPercent = ((high / totalDisruptions) * 100).toFixed(0);
    const mediumPercent = ((medium / totalDisruptions) * 100).toFixed(0);
    const lowPercent = ((low / totalDisruptions) * 100).toFixed(0);
    
    document.getElementById('severity-critical-percent').textContent = `${criticalPercent}%`;
    document.getElementById('severity-high-percent').textContent = `${highPercent}%`;
    document.getElementById('severity-medium-percent').textContent = `${mediumPercent}%`;
    document.getElementById('severity-low-percent').textContent = `${lowPercent}%`;
    
    // Update progress bars
    document.getElementById('severity-critical-bar').style.width = `${criticalPercent}%`;
    document.getElementById('severity-high-bar').style.width = `${highPercent}%`;
    document.getElementById('severity-medium-bar').style.width = `${mediumPercent}%`;
    document.getElementById('severity-low-bar').style.width = `${lowPercent}%`;
  } else {
    document.getElementById('severity-critical-percent').textContent = '0%';
    document.getElementById('severity-high-percent').textContent = '0%';
    document.getElementById('severity-medium-percent').textContent = '0%';
    document.getElementById('severity-low-percent').textContent = '0%';
    
    document.getElementById('severity-critical-bar').style.width = '0%';
    document.getElementById('severity-high-bar').style.width = '0%';
    document.getElementById('severity-medium-bar').style.width = '0%';
    document.getElementById('severity-low-bar').style.width = '0%';
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
      
      // Determine severity color
      let severityColor = 'slate';
      let severityBg = 'bg-slate-50';
      let severityBorder = 'border-slate-200';
      const severity = disruption.severity_level || '';
      
      if (severity === 'critical') {
        severityColor = 'red';
        severityBg = 'bg-red-50';
        severityBorder = 'border-red-300';
      } else if (severity === 'high') {
        severityColor = 'orange';
        severityBg = 'bg-orange-50';
        severityBorder = 'border-orange-300';
      } else if (severity === 'medium') {
        severityColor = 'yellow';
        severityBg = 'bg-yellow-50';
        severityBorder = 'border-yellow-300';
      } else if (severity === 'low') {
        severityColor = 'blue';
        severityBg = 'bg-blue-50';
        severityBorder = 'border-blue-300';
      }
      
      const disruptionCard = document.createElement('div');
      disruptionCard.className = `${severityBg} border ${severityBorder} rounded-xl p-3 cursor-pointer hover:shadow-md transition-all`;
      disruptionCard.onclick = () => showEdgeDetails(disruption);
      
      // Get road name or use fallback
      const roadName = disruption.road_name || 'Unknown Road';
      
      disruptionCard.innerHTML = `
        <div class="flex items-start gap-3">
          <div class="flex-shrink-0 w-10 h-10 bg-${severityColor}-500 rounded-lg flex items-center justify-center text-white font-bold">
            ${i + 1}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between mb-1">
              <div class="font-bold text-${severityColor}-900 text-sm">${roadName}</div>
              <div class="text-xs px-2 py-1 bg-${severityColor}-200 text-${severityColor}-800 rounded-lg font-semibold uppercase">
                ${severity}
              </div>
            </div>
            <div class="text-xs text-slate-600 space-y-1">
              <div><strong>Edge:</strong> ${disruption.source} → ${disruption.target}</div>
              <div><strong>Type:</strong> ${disruption.type || 'Unknown'}</div>
              ${disruption.description ? `<div class="italic">"${disruption.description}"</div>` : ''}
              <div class="flex items-center gap-3 mt-2">
                <div>
                  <strong>Impact:</strong> 
                  <span class="text-${severityColor}-700 font-bold">+${(disruption.time_impact_seconds || 0).toFixed(0)}s</span>
                </div>
                ${disruption.confidence !== undefined ? `
                  <div>
                    <strong>Confidence:</strong> 
                    <span class="font-semibold">${(disruption.confidence * 100).toFixed(0)}%</span>
                  </div>
                ` : ''}
                ${disruption.is_closed ? `
                  <div class="text-red-600 font-bold">🚫 CLOSED</div>
                ` : ''}
              </div>
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
    
    // Determine severity color
    const severity = disruption.severity || 'medium';
    let severityColor = '#f59e0b'; // amber for medium
    if (severity === 'critical' || severity === 'high') {
      severityColor = '#ef4444'; // red
    } else if (severity === 'low') {
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
            <span class="px-2 py-0.5 bg-slate-100 rounded text-xs font-semibold">${disruption.type || 'Unknown'}</span>
          </div>
          
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Severity:</span>
            <span class="px-2 py-0.5 rounded text-xs font-semibold text-white" style="background-color: ${severityColor}">
              ${severity.toUpperCase()}
            </span>
          </div>
          
          ${disruption.time_impact_seconds !== undefined ? `
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Time Impact:</span>
            <span class="font-bold text-red-600">+${disruption.time_impact_seconds.toFixed(0)}s</span>
          </div>
          ` : ''}
          
          ${disruption.confidence !== undefined ? `
          <div class="flex justify-between items-center">
            <span class="text-gray-600">Confidence:</span>
            <span class="font-semibold">${(disruption.confidence * 100).toFixed(0)}%</span>
          </div>
          ` : ''}
          
          ${disruption.is_closed ? `
          <div class="mt-2 p-2 bg-red-50 border border-red-200 rounded">
            <div class="flex items-center gap-2">
              <span class="text-red-600 font-bold">🚫 ROAD CLOSED</span>
            </div>
          </div>
          ` : ''}
          
          ${disruption.description ? `
          <div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded">
            <div class="text-xs text-blue-800 italic">
              "${disruption.description}"
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
  console.log(`🗺️ Highlighting alternative route ${routeIndex}:`, altRoute);
  
  if (!window.alternativeRoutePolylines || window.alternativeRoutePolylines.length === 0) {
    console.warn('⚠️ No alternative route polylines found on map');
    return;
  }
  
  // Find the corresponding polyline
  const polyline = window.alternativeRoutePolylines[routeIndex];
  
  if (!polyline) {
    console.warn(`⚠️ Alternative route polyline ${routeIndex} not found`);
    return;
  }
  
  // Reset all alternative routes to transparent
  window.alternativeRoutePolylines.forEach((p, idx) => {
    if (p && p.setStyle) {
      p.setStyle({
        opacity: idx === routeIndex ? 0.8 : 0.3,
        weight: idx === routeIndex ? 8 : 5
      });
    }
  });
  
  // Zoom to this route's bounds
  if (polyline.getBounds) {
    const bounds = polyline.getBounds();
    if (window.map) {
      window.map.fitBounds(bounds, { padding: [50, 50] });
    }
  }
  
  // Show a popup with route details
  const etaFormatted = formatTime(altRoute.eta_seconds);
  const distanceKm = (altRoute.distance / 1000).toFixed(2);
  
  const popupContent = `
    <div class="p-2" style="min-width: 250px;">
      <div class="font-bold text-base mb-2 border-b pb-2">
        🛣️ ${altRoute.description || `Route ${routeIndex + 1}`}
      </div>
      
      <div class="space-y-2 text-sm">
        <div class="flex justify-between items-center">
          <span class="text-gray-600">Rank:</span>
          <span class="font-bold text-blue-600">#${altRoute.rank || (routeIndex + 1)}</span>
        </div>
        
        <div class="flex justify-between items-center">
          <span class="text-gray-600">Distance:</span>
          <span class="font-semibold">${distanceKm} km</span>
        </div>
        
        <div class="flex justify-between items-center">
          <span class="text-gray-600">ETA:</span>
          <span class="font-bold text-green-600">${etaFormatted}</span>
        </div>
        
        <div class="flex justify-between items-center">
          <span class="text-gray-600">Avg Jam Factor:</span>
          <span class="${altRoute.avg_jam_factor > 5 ? 'text-red-600 font-bold' : 'text-green-600'}">${altRoute.avg_jam_factor.toFixed(1)}</span>
        </div>
      </div>
    </div>
  `;
  
  // Create popup at the midpoint of the route
  if (polyline.getLatLngs && window.map) {
    const latlngs = polyline.getLatLngs();
    if (latlngs.length > 0) {
      const midpoint = latlngs[Math.floor(latlngs.length / 2)];
      L.popup({
        maxWidth: 300,
        className: 'alternative-route-popup'
      })
      .setLatLng(midpoint)
      .setContent(popupContent)
      .openOn(window.map);
    }
  }
};

console.log('✅ Panel Population module loaded');

