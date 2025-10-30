// Function to update performance metrics in admin panel
function updateAdminPerformanceMetrics(routeData) {
    if (!routeData || !routeData.success) return;
    
    const metrics = routeData.metrics || {};
    const algorithm = routeData.algorithm || metrics.algorithm || 'Unknown';
    
    // Check if this is comparison mode - set all metrics to "--"
    if (algorithm.includes('Comparison')) {
        console.log('Comparison mode detected - setting Performance Metrics to "--"');
        
        document.getElementById('perf-labeling-time').textContent = '--';
        document.getElementById('perf-labeling-size').textContent = '--';
        document.getElementById('perf-query-time').textContent = '--';
        
        // Reset mode badge for comparison mode
        const modeBadge = document.getElementById('update-mode-badge');
        if (modeBadge) {
          modeBadge.textContent = '--';
          modeBadge.className = 'px-4 py-2 bg-gray-400 text-white rounded-xl text-sm font-bold shadow-md';
        }
        
        console.log('✅ Performance Metrics set to "--" for comparison mode');
        return; // Exit early for comparison mode
    }
    
    // Update based on algorithm type for individual algorithms
    if (metrics.algorithm && metrics.algorithm.includes('DHL')) {
      // DHL metrics
      document.getElementById('perf-labeling-time').textContent = 
        metrics.labeling_time_ms ? `${(metrics.labeling_time_ms / 1000).toFixed(1)}s` : 'N/A';
      
      document.getElementById('perf-labeling-size').textContent = 
        metrics.labeling_size_mb ? `${metrics.labeling_size_mb.toFixed(1)} MB` : 'N/A';
      
      document.getElementById('perf-query-time').textContent = 
        metrics.query_time_microseconds ? `${(metrics.query_time_microseconds / 1000).toFixed(3)}μs` : 'N/A';
        
      // Reset mode badge for DHL (not applicable)
      const modeBadge = document.getElementById('update-mode-badge');
      if (modeBadge) {
        modeBadge.textContent = 'N/A';
        modeBadge.className = 'px-4 py-2 bg-gray-400 text-white rounded-xl text-sm font-bold shadow-md';
      }
        
      // DHL specific metrics
    //   document.getElementById('perf-route-similarity').textContent = 
    //     `${metrics.path_length || 0} nodes`;
      
    //   document.getElementById('perf-frechet-distance').textContent = 
    //     `${metrics.total_distance_units || 0} units`;
        
    //   document.getElementById('perf-segment-overlap').textContent = 
    //     `${metrics.hoplinks_examined || 0} hops`;
      
    } else {
      // D-HC2L metrics
      document.getElementById('perf-labeling-time').textContent = 
        metrics.labeling_time_ms ? `${metrics.labeling_time_ms.toFixed(1)}s` : 'N/A';
      
      document.getElementById('perf-labeling-size').textContent = 
        metrics.labeling_size_mb ? `${metrics.labeling_size_mb.toFixed(1)} MB` : 'N/A';
      
      document.getElementById('perf-query-time').textContent = 
        metrics.query_time_ms ? `${metrics.query_time_ms.toFixed(3)}μs` : 'N/A';
        
      // Update D-HC2L mode badge
      const modeBadge = document.getElementById('update-mode-badge');
      if (modeBadge) {
        const routingMode = metrics.routing_mode || 'BASE';
        const updateStrategy = metrics.update_strategy || 'none';
        
        // Determine display text and styling based on mode
        let displayText = 'Base Mode';
        let bgClass = 'bg-gray-500';
        
        if (routingMode === 'IMMEDIATE_UPDATE') {
          displayText = 'Immediate Update';
          bgClass = 'bg-red-500';
        } else if (routingMode === 'LAZY_UPDATE') {
          displayText = 'Lazy Update';
          bgClass = 'bg-orange-500';
        } else if (routingMode === 'DISRUPTED') {
          displayText = 'Disrupted';
          bgClass = 'bg-yellow-500';
        }
        
        modeBadge.textContent = displayText;
        modeBadge.className = `px-4 py-2 ${bgClass} text-white rounded-xl text-sm font-bold shadow-md`;
        
        console.log(`🔄 Updated mode badge: ${displayText} (${routingMode})`);
      }
        
    //   document.getElementById('perf-route-similarity').textContent = 
    //     metrics.uses_disruptions ? 'Yes' : 'No';
        
    //   document.getElementById('perf-frechet-distance').textContent = 
    //     metrics.total_distance_m ? `${(metrics.total_distance_m / 1000).toFixed(1)}km` : 'N/A';
        
    //   document.getElementById('perf-segment-overlap').textContent = 
    //     `${metrics.edge_count || 0} edges`;
    }
}

// Function to update algorithm comparison modal with DHL and D-HC2L route data
function updateAlgorithmComparisonModal(dhlRouteData, dhc2lRouteData) {
    try {
        console.log('🔄 Updating algorithm comparison modal...');
        console.log('DHL Route Data:', dhlRouteData);
        console.log('D-HC2L Route Data:', dhc2lRouteData);
        
        // Extract metrics from both algorithms using the same pattern as updateRouteMetrics
        // First try direct summary property, then fallback to metrics property
        const dhlMetrics = dhlRouteData?.summary || dhlRouteData?.metrics || {};
        const dhc2lMetrics = dhc2lRouteData?.summary || dhc2lRouteData?.metrics || {};
        
        console.log('Extracted DHL metrics:', dhlMetrics);
        console.log('Extracted D-HC2L metrics:', dhc2lMetrics);
        
        // Update DHL metrics in the modal
        updateDHLComparisonMetrics(dhlMetrics);
        
        // Update D-HC2L metrics in the modal
        updateDHC2LComparisonMetrics(dhc2lMetrics, dhlMetrics);
        
        console.log('✅ Algorithm comparison modal updated successfully');
        
    } catch (error) {
        console.error('❌ Error updating algorithm comparison modal:', error);
    }
}

// Helper function to update DHL metrics in comparison modal
function updateDHLComparisonMetrics(dhlMetrics) {
    console.log('Updating DHL metrics:', dhlMetrics);
    
    // Update DHL Labeling Time (handle both formats like updateRouteMetrics)
    const dhlLabelingElement = document.getElementById('dhl-labeling-time');
    if (dhlLabelingElement) {
        // Try different field names for labeling time
        const labelingTime = dhlMetrics.labeling_time_ms || 
                            (dhlMetrics.labeling_time_ms ? dhlMetrics.labeling_time_ms * 1000 : 0);
        dhlLabelingElement.textContent = labelingTime > 0 ? `${labelingTime.toFixed(1)}s` : 'N/A';
        console.log('DHL Labeling Time:', labelingTime);
    }
    
    // Update DHL Labeling Size
    const dhlSizeElement = document.getElementById('dhl-labeling-size');
    if (dhlSizeElement) {
        const labelingSize = dhlMetrics.labeling_size_mb || 0;
        dhlSizeElement.textContent = labelingSize > 0 ? `${labelingSize.toFixed(1)} MB` : 'N/A';
        console.log('DHL Labeling Size:', labelingSize);
    }
    
    // Update DHL Query Time
    const dhlQueryElement = document.getElementById('dhl-query-time');
    if (dhlQueryElement) {
        const queryTime = dhlMetrics.query_time_microseconds || 0;
        dhlQueryElement.textContent = queryTime > 0 ? `${queryTime.toFixed(3)}μs` : 'N/A';
        console.log('DHL Query Time:', queryTime);
    }
}

// Helper function to update D-HC2L metrics in comparison modal with percentage improvements
function updateDHC2LComparisonMetrics(dhc2lMetrics, dhlMetrics) {
    console.log('Updating D-HC2L metrics:', dhc2lMetrics);
    console.log('Comparing against DHL metrics:', dhlMetrics);
    
    // Update D-HC2L Labeling Time with comparison
    const dhc2lLabelingElement = document.getElementById('dhc2l-labeling-time');
    if (dhc2lLabelingElement) {
        // Handle both formats like updateRouteMetrics - note the different calculation for D-HC2L
        const dhc2lLabelingTime = dhc2lMetrics.labeling_time_ms || 
                                 (dhc2lMetrics.labeling_time_ms ? dhc2lMetrics.labeling_time_ms * 1000 : 0);
        const dhlLabelingTime = dhlMetrics.labeling_time_ms || 
                               (dhlMetrics.labeling_time_ms ? dhlMetrics.labeling_time_ms * 1000 : 0);
        
        console.log('D-HC2L Labeling Time:', dhc2lLabelingTime, 'DHL Labeling Time:', dhlLabelingTime);
        
        if (dhc2lLabelingTime > 0) {
            let displayText = `${dhc2lLabelingTime.toFixed(1)}ms`;
            
            // Calculate percentage difference if both values exist
            if (dhlLabelingTime > 0) {
                const percentDiff = ((dhc2lLabelingTime - dhlLabelingTime) / dhlLabelingTime) * 100;
                const arrow = percentDiff < 0 ? '↓' : '↑';
                const color = percentDiff < 0 ? 'text-emerald-600' : 'text-red-600';
                displayText = `${dhc2lLabelingTime.toFixed(1)}ms ${arrow} ${Math.abs(percentDiff).toFixed(0)}%`;
                dhc2lLabelingElement.className = `font-bold ${color}`;
            }
            
            dhc2lLabelingElement.textContent = displayText;
        } else {
            dhc2lLabelingElement.textContent = 'N/A';
        }
    }
    
    // Update D-HC2L Labeling Size with comparison
    const dhc2lSizeElement = document.getElementById('dhc2l-labeling-size');
    if (dhc2lSizeElement) {
        const dhc2lLabelingSize = dhc2lMetrics.labeling_size_mb || 0;
        const dhlLabelingSize = dhlMetrics.labeling_size_mb || 0;
        
        console.log('D-HC2L Labeling Size:', dhc2lLabelingSize, 'DHL Labeling Size:', dhlLabelingSize);
        
        if (dhc2lLabelingSize > 0) {
            let displayText = `${dhc2lLabelingSize.toFixed(1)} MB`;
            
            // Calculate percentage difference if both values exist
            if (dhlLabelingSize > 0) {
                const percentDiff = ((dhc2lLabelingSize - dhlLabelingSize) / dhlLabelingSize) * 100;
                const arrow = percentDiff < 0 ? '↓' : '↑';
                const color = percentDiff < 0 ? 'text-emerald-600' : 'text-red-600';
                displayText = `${dhc2lLabelingSize.toFixed(1)} MB ${arrow} ${Math.abs(percentDiff).toFixed(0)}%`;
                dhc2lSizeElement.className = `font-bold ${color}`;
            }
            
            dhc2lSizeElement.textContent = displayText;
        } else {
            dhc2lSizeElement.textContent = 'N/A';
        }
    }
    
    // Update D-HC2L Query Time with comparison
    const dhc2lQueryElement = document.getElementById('dhc2l-query-time');
    if (dhc2lQueryElement) {
        const dhc2lQueryTime = dhc2lMetrics.query_time_ms || 0;
        const dhlQueryTime = dhlMetrics.query_time_microseconds || 0;
        
        console.log('D-HC2L Query Time:', dhc2lQueryTime, 'DHL Query Time:', dhlQueryTime);
        
        if (dhc2lQueryTime > 0) {
            let displayText = `${dhc2lQueryTime.toFixed(3)}μs`;
            
            // Calculate percentage difference if both values exist
            if (dhlQueryTime > 0) {
                const percentDiff = ((dhc2lQueryTime - dhlQueryTime) / dhlQueryTime) * 100;
                const arrow = percentDiff < 0 ? '↓' : '↑';
                const color = percentDiff < 0 ? 'text-emerald-600' : 'text-red-600';
                displayText = `${dhc2lQueryTime.toFixed(1)}μs ${arrow} ${Math.abs(percentDiff).toFixed(0)}%`;
                dhc2lQueryElement.className = `font-bold ${color}`;
            }
            
            dhc2lQueryElement.textContent = displayText;
        } else {
            dhc2lQueryElement.textContent = 'N/A';
        }
    }
}

// function updateComparisonMetrics(routeData) {
//     try {
//       // Update Fréchet Distance (placeholder - would need actual calculation)
//       const frechetElement = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-blue-700');
//       if (frechetElement) {
//         frechetElement.textContent = '8.2'; // Placeholder
//       }
      
//       // Update Segment Overlap (placeholder - would need actual calculation)
//       const overlapElement = document.querySelector('#current-path-panel .flex.justify-between .font-bold.text-emerald-700');
//       if (overlapElement) {
//         overlapElement.textContent = '92%'; // Placeholder
//       }
      
//     } catch (error) {
//       console.error('Error updating comparison metrics:', error);
//     }
// }


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

  
function updateBottomInfoBar(distanceKm, estimatedMinutes, routeData) {
    const etaElement = document.getElementById('bottom-info-eta');
    const distanceElement = document.getElementById('bottom-info-distance');
    const metricLabelElement = document.getElementById('bottom-info-metric-label');
    const metricValueElement = document.getElementById('bottom-info-metric-value');
    
    // Update ETA
    if (etaElement) {
      if (estimatedMinutes > 0) {
        etaElement.textContent = `${estimatedMinutes} min`;
        etaElement.classList.remove('text-slate-400');
        etaElement.classList.add('text-slate-800');
      } else {
        etaElement.textContent = '--';
        etaElement.classList.remove('text-slate-800');
        etaElement.classList.add('text-slate-400');
      }
    }
    
    // Update Distance
    if (distanceElement) {
      if (distanceKm > 0) {
        distanceElement.textContent = `${distanceKm.toFixed(1)} km`;
        distanceElement.classList.remove('text-slate-400');
        distanceElement.classList.add('text-slate-800');
      } else {
        distanceElement.textContent = '--';
        distanceElement.classList.remove('text-slate-800');
        distanceElement.classList.add('text-slate-400');
      }
    }
    
    // Update third metric based on algorithm type and available data
    const metrics = routeData.metrics || {};
    const algorithm = routeData.algorithm || metrics.algorithm || 'Unknown';
    
    if (metricLabelElement && metricValueElement) {
      if (algorithm.includes('Comparison')) {
        // Comparison mode - show route count
        metricLabelElement.textContent = 'Routes Compared';
        const routeCount = (routeData.routes && Object.keys(routeData.routes).length) || 2;
        metricValueElement.textContent = `${routeCount}`;
        metricValueElement.classList.remove('text-slate-400');
        metricValueElement.classList.add('text-slate-800');
        
      } else if (algorithm.includes('DHL')) {
        // DHL algorithm - show query time
        metricLabelElement.textContent = 'Query Time';
        if (metrics.query_time_microseconds !== undefined) {
          const queryTime = metrics.query_time_microseconds;
          metricValueElement.textContent = `${(queryTime / 1000).toFixed(3)}μs`;
          metricValueElement.classList.remove('text-slate-400');
          metricValueElement.classList.add('text-slate-800');
        } else {
          metricValueElement.textContent = '--';
          metricValueElement.classList.remove('text-slate-800');
          metricValueElement.classList.add('text-slate-400');
        }
        
      } else if (algorithm.includes('HC2L') || algorithm.includes('D-HC2L')) {
        // D-HC2L algorithm - show edge count or query time
        metricLabelElement.textContent = 'Edges Used';
        if (metrics.edge_count !== undefined) {
          metricValueElement.textContent = `${metrics.edge_count}`;
          metricValueElement.classList.remove('text-slate-400');
          metricValueElement.classList.add('text-slate-800');
        } else if (metrics.query_time_ms !== undefined) {
          // Fallback to query time
          metricLabelElement.textContent = 'Query Time';
          const queryTime = metrics.query_time_ms;
          if (queryTime < 1000) {
            metricValueElement.textContent = `${queryTime.toFixed(3)}μs`;
          } else {
            metricValueElement.textContent = `${(queryTime / 1000).toFixed(3)}μs`;
          }
          metricValueElement.classList.remove('text-slate-400');
          metricValueElement.classList.add('text-slate-800');
        } else {
          metricValueElement.textContent = '--';
          metricValueElement.classList.remove('text-slate-800');
          metricValueElement.classList.add('text-slate-400');
        }
        
      } else {
        // Default/Unknown algorithm
        metricLabelElement.textContent = 'Performance';
        metricValueElement.textContent = '--';
        metricValueElement.classList.remove('text-slate-800');
        metricValueElement.classList.add('text-slate-400');
      }
    }
    
    console.log(`📊 Bottom info updated: ${distanceKm.toFixed(1)}km, ${estimatedMinutes}min, ${algorithm}`);
}
  

function updatePerformanceMetrics(metrics) {
    // Update admin panel metrics using the new IDs
    if (!metrics) return;
    
    // Detect algorithm type
    const algorithm = metrics.algorithm || 'Unknown';
    const isDHL = algorithm.includes('DHL');
    const isComparison = algorithm.includes('Comparison');

    // Check if this is comparison mode - set all metrics to "--"
    if (isComparison) {
        console.log('Comparison mode detected in updatePerformanceMetrics - setting metrics to "--"');
        
        document.getElementById('perf-labeling-time').textContent = '--';
        document.getElementById('perf-labeling-size').textContent = '--';
        document.getElementById('perf-query-time').textContent = '--';
        
        console.log('✅ Performance Metrics set to "--" for comparison mode');
        return; // Exit early for comparison mode
    }

    if (isDHL) {
      // DHL metrics - update labels
      // document.getElementById('perf-metric-4-label').textContent = 'Path Length';
      // document.getElementById('perf-metric-5-label').textContent = 'Distance (units)';
      // document.getElementById('perf-metric-6-label').textContent = 'Hoplinks Examined';
      
      // DHL values
      document.getElementById('perf-labeling-time').textContent = 
        metrics.labeling_time_ms ? `${metrics.labeling_time_ms.toFixed(1)}s` : 'N/A';
      
      document.getElementById('perf-labeling-size').textContent = 
        metrics.labeling_size_mb ? `${metrics.labeling_size_mb.toFixed(1)} MB` : 'N/A';
      
      document.getElementById('perf-query-time').textContent = 
        metrics.query_time_microseconds ? `${(metrics.query_time_microseconds / 1000).toFixed(3)}μs` : 'N/A';
        
      // document.getElementById('perf-route-similarity').textContent = 
      //   `${metrics.path_length || 0} nodes`;
      
      // document.getElementById('perf-frechet-distance').textContent = 
      //   `${metrics.total_distance_units || 0}`;
        
      // document.getElementById('perf-segment-overlap').textContent = 
      //   `${metrics.hoplinks_examined || 0} hops`;
        
    } else {
      // D-HC2L metrics - update labels
      // document.getElementById('perf-metric-4-label').textContent = 'Uses Disruptions';
      // document.getElementById('perf-metric-5-label').textContent = 'Distance (km)';
      // document.getElementById('perf-metric-6-label').textContent = 'Edge Count';
      
      // D-HC2L values
      document.getElementById('perf-labeling-time').textContent = 
        metrics.labeling_time_ms ? `${metrics.labeling_time_ms.toFixed(1)}s` : 'N/A';
      
      document.getElementById('perf-labeling-size').textContent = 
        metrics.labeling_size_mb ? `${metrics.labeling_size_mb.toFixed(1)} MB` : 'N/A';
      
      document.getElementById('perf-query-time').textContent = 
        metrics.query_time_ms ? `${metrics.query_time_ms.toFixed(3)}μs` : 'N/A';
        
      // document.getElementById('perf-route-similarity').textContent = 
      //   metrics.uses_disruptions ? 'Yes' : 'No';
        
      // document.getElementById('perf-frechet-distance').textContent = 
      //   metrics.total_distance_m ? `${(metrics.total_distance_m / 1000).toFixed(1)}km` : 'N/A';
        
      // document.getElementById('perf-segment-overlap').textContent = 
      //   `${metrics.edge_count || 0} edges`;
    }
    
    
    console.log('Performance metrics updated:', metrics);
}
  

function updateRouteMetrics(routeData) {
    if (!routeData.metrics && !routeData.route) {
      resetBottomInfoBar();
      return;
    }
    
    const metrics = routeData.metrics || {};
    const route = routeData.route || {};
    
    // Calculate distance and time using the same strategy as Route Panel
    let distanceM = 0;
    let estimatedMinutes = 0;
    let distanceSource = 'unknown';
    
    // Try to get distance from multiple sources (same order as Route Panel)
    // 1. First try road segments (most accurate)
    if (route && route.road_segments && route.road_segments.length > 0) {
      let segmentTotal = 0;
      route.road_segments.forEach((segment, index) => {
        const segmentLength = segment.length_meters || segment.length || 0;
        segmentTotal += segmentLength;
      });
      
      if (segmentTotal > 0) {
        distanceM = segmentTotal;
        distanceSource = 'road_segments';
        console.log('📊 Bottom info using distance from road segments:', distanceM, 'meters');
      }
    }
    
    // 2. Fallback to metrics if road segments calculation failed
    if (distanceM === 0) {
      if (metrics.total_distance_meters && metrics.total_distance_meters > 0) {
        distanceM = metrics.total_distance_meters;
        distanceSource = 'metrics.total_distance_meters';
      } else if (metrics.distance_meters && metrics.distance_meters > 0) {
        distanceM = metrics.distance_meters;
        distanceSource = 'metrics.distance_meters';
      } else if (route.total_distance_meters && route.total_distance_meters > 0) {
        distanceM = route.total_distance_meters;
        distanceSource = 'route.total_distance_meters';
      } else if (route.distance && route.distance > 0) {
        distanceM = route.distance * 1000; // Convert km to meters if needed
        distanceSource = 'route.distance';
      }
    }
    
    // 3. Final fallback: estimate from coordinates
    if (distanceM === 0) {
      console.warn('No distance data found in metrics or route segments for bottom info');
      if (route && route.coordinates && route.coordinates.length >= 2) {
        const start = route.coordinates[0];
        const end = route.coordinates[route.coordinates.length - 1];
        if (start && end && start.lat && start.lng && end.lat && end.lng) {
          distanceM = calculateHaversineDistance(start.lat, start.lng, end.lat, end.lng);
          distanceSource = 'coordinate_estimation';
          console.log('📊 Bottom info estimated distance from coordinates:', distanceM);
        }
      }
    }
    
    const distanceKm = distanceM / 1000;
    
    // Calculate estimated time
    if (metrics.estimated_time_minutes) {
      estimatedMinutes = metrics.estimated_time_minutes;
    } else if (distanceKm > 0) {
      // Estimate: 30 km/h average in urban areas
      estimatedMinutes = Math.round((distanceKm / 30) * 60);
    }
    
    console.log(`📊 Bottom info final: ${distanceKm.toFixed(1)}km (${distanceM}m) from ${distanceSource}, ${estimatedMinutes}min`);
    
    // Update bottom info bar
    updateBottomInfoBar(distanceKm, estimatedMinutes, routeData);
    
    // Update performance metrics in admin panel
    updatePerformanceMetrics(metrics);
}
  


