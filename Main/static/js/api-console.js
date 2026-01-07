/**
 * API Console Parser Module
 * Parses raw API responses and displays them in a console-like interface
 * Excludes geometry data for cleaner readability
 */

class APIConsole {
  constructor() {
    this.logs = [];
    this.maxLogs = 500;
    this.consoleElement = null;
    this.isRawMode = false;
  }

  /**
   * Initialize the console
   */
  init() {
    this.consoleElement = document.getElementById('api-console-output');
    if (!this.consoleElement) {
      console.warn('API Console output element not found');
      return false;
    }
    
    this.setupEventListeners();
    this.clear();
    console.log('✅ API Console initialized');
    return true;
  }

  /**
   * Setup event listeners for console controls
   */
  setupEventListeners() {
    const clearBtn = document.getElementById('api-console-clear');
    const copyBtn = document.getElementById('api-console-copy');
    const toggleViewBtn = document.getElementById('api-console-toggle-view');

    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.clear());
    }

    if (copyBtn) {
      copyBtn.addEventListener('click', () => this.copyToClipboard());
    }

    if (toggleViewBtn) {
      toggleViewBtn.addEventListener('click', () => this.toggleView());
    }
  }

  /**
   * Log an entry to the console
   */
  log(level, message, data = null) {
    const logEntry = {
      level,
      message,
      data
    };

    this.logs.push(logEntry);

    // Keep only the last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }

    this.render();
  }

  /**
   * Parse API response and log formatted output
   */
  parseAPIResponse(response, algorithm = 'Unknown') {
    if (!response) {
      this.log('ERROR', 'Empty response received', null);
      return;
    }

    // Clear previous logs to show only current API output
    this.logs = [];

    this.log('INFO', `╔════════════════════════════════════════════════════════╗`);
    this.log('INFO', `║ API Response: ${algorithm.padEnd(46)}║`);
    this.log('INFO', `╚════════════════════════════════════════════════════════╝`);

    // Success status
    if (response.success !== undefined) {
      const status = response.success ? '✓ SUCCESS' : '✗ FAILED';
      this.log(response.success ? 'SUCCESS' : 'ERROR', `[Status] ${status}`);
    }

    // Error if present
    if (response.error) {
      this.log('ERROR', `[Error] ${response.error}`);
    }

    // Algorithm information
    if (response.algorithm) {
      this.log('INFO', `[Algorithm] ${response.algorithm}`);
    }

    // Input coordinates
    if (response.input) {
      this.log('INFO', `\n📍 Input Coordinates:`);
      this.parseInputInfo(response.input);
    }

    // GPS mapping
    if (response.gps_mapping) {
      this.log('INFO', `\n🗺️  GPS Mapping:`);
      this.parseGPSMapping(response.gps_mapping);
    }

    // Route metrics (excluding geometry)
    if (response.metrics) {
      this.log('INFO', `\n📊 Metrics:`);
      this.parseMetrics(response.metrics);
    }

    // Route information (excluding coordinates and geometry)
    if (response.route) {
      this.log('INFO', `\n🛣️  Route Details:`);
      this.parseRoute(response.route);
    }

    // Alternative routes summary
    if (response.alternative_routes && Array.isArray(response.alternative_routes) && response.alternative_routes.length > 0) {
      this.log('INFO', `\n🔀 Alternative Routes: ${response.alternative_routes.length} found`);
      response.alternative_routes.forEach((alt, index) => {
        this.parseAlternativeRoute(alt, index + 1);
      });
    }

    // Disruption info
    if (response.disruptions_summary) {
      this.log('INFO', `\n⚠️  Disruptions Summary:`);
      this.parseDisruptionsSummary(response.disruptions_summary);
    }

    // Disruption configuration
    if (response.disruption_config) {
      this.log('INFO', `\n⚙️  Disruption Configuration:`);
      this.parseDisruptionConfig(response.disruption_config);
    }

    // Lazy HC2L info
    if (response.lazy_hc2l) {
      this.log('INFO', `\n🔄 Lazy HC2L Strategy:`);
      this.parseLazyHC2LInfo(response.lazy_hc2l);
    }

    // DHL update info
    if (response.dhl_update_info) {
      this.log('INFO', `\n🔄 DHL Update Strategy:`);
      this.parseDHLUpdateInfo(response.dhl_update_info);
    }

    // HC2L specific info
    if (response.hc2l_labeling_info) {
      this.log('INFO', `\n📚 HC2L Labeling Info:`);
      this.parseHC2LLabelingInfo(response.hc2l_labeling_info);
    }

    // DHL specific info
    if (response.dhl_info) {
      this.log('INFO', `\n📋 DHL Info:`);
      this.parseDHLInfo(response.dhl_info);
    }

    // Snap edges
    if (response.snap_edges) {
      this.log('INFO', `\n🔗 Snap Edges:`);
      this.parseSnapEdges(response.snap_edges);
    }

    this.log('INFO', `\n╔════════════════════════════════════════════════════════╗`);
    this.log('INFO', `║ End of API Response`.padEnd(56) + `║`);
    this.log('INFO', `╚════════════════════════════════════════════════════════╝`);
  }

  /**
   * Parse input information
   */
  parseInputInfo(input) {
    const indent = '  ';
    if (input.start_pin_lat && input.start_pin_lng) {
      this.log('INFO', `${indent}[Start Pin] ${input.start_pin_lat.toFixed(6)}, ${input.start_pin_lng.toFixed(6)}`);
    }
    if (input.dest_pin_lat && input.dest_pin_lng) {
      this.log('INFO', `${indent}[Destination Pin] ${input.dest_pin_lat.toFixed(6)}, ${input.dest_pin_lng.toFixed(6)}`);
    }
    if (input.use_disruptions !== undefined) {
      this.log('INFO', `${indent}[Use Disruptions] ${input.use_disruptions ? 'Yes' : 'No'}`);
    }
  }

  /**
   * Parse GPS mapping information
   */
  parseGPSMapping(mapping) {
    const indent = '  ';
    if (mapping.start_node) {
      this.log('INFO', `${indent}[Start Node] ${mapping.start_node}`);
    }
    if (mapping.start_node_lat && mapping.start_node_lng) {
      this.log('INFO', `${indent}[Start Coords] ${mapping.start_node_lat.toFixed(6)}, ${mapping.start_node_lng.toFixed(6)}`);
    }
    if (mapping.dest_node) {
      this.log('INFO', `${indent}[Destination Node] ${mapping.dest_node}`);
    }
    if (mapping.dest_node_lat && mapping.dest_node_lng) {
      this.log('INFO', `${indent}[Destination Coords] ${mapping.dest_node_lat.toFixed(6)}, ${mapping.dest_node_lng.toFixed(6)}`);
    }
  }

  /**
   * Parse snap edges information
   */
  parseSnapEdges(edges) {
    const indent = '  ';
    if (edges.start_edge) {
      const se = edges.start_edge;
      this.log('INFO', `${indent}[Start Edge] ${se.source} → ${se.target} (${se.oneway ? 'OneWay' : 'TwoWay'})`);
    }
    if (edges.dest_edge) {
      const de = edges.dest_edge;
      this.log('INFO', `${indent}[Dest Edge] ${de.source} → ${de.target} (${de.oneway ? 'OneWay' : 'TwoWay'})`);
    }
  }

  /**
   * Parse disruption configuration
   */
  parseDisruptionConfig(config) {
    const indent = '  ';
    if (config.use_disruptions !== undefined) {
      this.log('INFO', `${indent}[Use Disruptions] ${config.use_disruptions ? 'Yes' : 'No'}`);
    }
    if (config.tau_threshold !== undefined) {
      this.log('INFO', `${indent}[Tau Threshold] ${config.tau_threshold}`);
    }
    if (config.tau_used_for) {
      this.log('INFO', `${indent}[Tau Purpose] ${config.tau_used_for}`);
    }
  }

  /**
   * Parse disruptions summary
   */
  parseDisruptionsSummary(summary) {
    const indent = '  ';
    
    if (summary.route) {
      this.log('INFO', `${indent}🚗 Route Disruptions:`);
      const route = summary.route;
      if (route.total_disrupted_edges !== undefined) {
        this.log('INFO', `${indent}  [Disrupted Edges] ${route.total_disrupted_edges}`);
      }
      if (route.critical !== undefined || route.high !== undefined || route.medium !== undefined || route.low !== undefined) {
        const severity = `Critical: ${route.critical || 0}, High: ${route.high || 0}, Medium: ${route.medium || 0}, Low: ${route.low || 0}`;
        this.log('INFO', `${indent}  [By Severity] ${severity}`);
      }
      if (route.total_time_impact_minutes !== undefined) {
        this.log('INFO', `${indent}  [Time Impact] ${route.total_time_impact_minutes.toFixed(2)} min`);
      }
      if (route.percentage_increase !== undefined) {
        this.log('INFO', `${indent}  [ETA Increase] ${route.percentage_increase.toFixed(2)}%`);
      }
    }

    if (summary.network) {
      this.log('INFO', `${indent}🌐 Network Disruptions:`);
      const network = summary.network;
      if (network.total_incidents !== undefined) {
        this.log('INFO', `${indent}  [Total Incidents] ${network.total_incidents}`);
      }
      if (network.active_disruptions !== undefined) {
        this.log('INFO', `${indent}  [Active Disruptions] ${network.active_disruptions}`);
      }
    }
  }

  /**
   * Parse DHL update information
   */
  parseDHLUpdateInfo(info) {
    const indent = '  ';
    if (info.algorithm_type) {
      this.log('INFO', `${indent}[Algorithm Type] ${info.algorithm_type}`);
    }
    if (info.update_strategy) {
      this.log('INFO', `${indent}[Update Strategy] ${info.update_strategy}`);
    }
    if (info.reason) {
      this.log('INFO', `${indent}[Reason] ${info.reason}`);
    }
    if (info.disruption_impact_score !== undefined) {
      this.log('INFO', `${indent}[Impact Score] ${info.disruption_impact_score.toFixed(3)}`);
    }
    if (info.nodes_updated !== undefined) {
      this.log('INFO', `${indent}[Nodes Updated] ${info.nodes_updated}`);
    }
  }

  /**
   * Parse and display metrics (excluding geometry)
   */
  parseMetrics(metrics) {
    const excluded = ['geometry', 'coordinates', 'path_geometry', 'road_geometries', 'labeling_info'];
    const indent = '  ';

    Object.entries(metrics).forEach(([key, value]) => {
      // Skip excluded fields
      if (excluded.some(ex => key.toLowerCase().includes(ex))) {
        return;
      }

      // Format the value based on type
      let displayValue = value;
      if (typeof value === 'number') {
        if (key.toLowerCase().includes('distance') || key.toLowerCase().includes('length')) {
          if (key.toLowerCase().includes('_km') || key.includes('km')) {
            displayValue = `${value.toFixed(2)} km`;
          } else {
            displayValue = `${value.toFixed(2)} m`;
          }
        } else if (key.toLowerCase().includes('time') || key.toLowerCase().includes('duration')) {
          if (key.toLowerCase().includes('_ms') || key.includes('ms')) {
            displayValue = `${value.toFixed(3)} ms`;
          } else {
            displayValue = `${value.toFixed(2)}s`;
          }
        } else if (typeof value === 'boolean') {
          displayValue = value ? 'Yes' : 'No';
        } else {
          displayValue = value.toFixed(2);
        }
      }

      this.log('INFO', `${indent}[${key}] ${displayValue}`);
    });

    // Parse labeling_info separately with more details
    if (metrics.labeling_info && typeof metrics.labeling_info === 'object') {
      this.log('INFO', `${indent}📦 Labeling Details:`);
      this.parseHC2LLabelingInfo(metrics.labeling_info);
    }
  }

  /**
   * Parse and display route information
   */
  parseRoute(route) {
    const indent = '  ';
    const excluded = ['coordinates', 'geometry', 'path_geometry', 'geom'];

    // Path nodes summary
    if (route.path_nodes && Array.isArray(route.path_nodes)) {
      this.log('INFO', `${indent}[Path Nodes] ${route.path_nodes.length} nodes: ${route.path_nodes.join(' → ')}`);
    }

    // Basic route info
    if (route.distance) {
      this.log('INFO', `${indent}[Distance] ${(route.distance / 1000).toFixed(2)} km`);
    }
    if (route.calculated_distance_meters) {
      this.log('INFO', `${indent}[Calculated Distance] ${(route.calculated_distance_meters / 1000).toFixed(2)} km`);
    }
    if (route.duration) {
      const mins = Math.round(route.duration / 60);
      this.log('INFO', `${indent}[Duration] ${mins} min`);
    }
    if (route.eta_seconds) {
      const hours = Math.floor(route.eta_seconds / 3600);
      const mins = Math.floor((route.eta_seconds % 3600) / 60);
      this.log('INFO', `${indent}[ETA] ${hours > 0 ? hours + 'h ' : ''}${mins}m`);
    }

    // Road segments count
    if (route.road_segments && Array.isArray(route.road_segments)) {
      this.log('INFO', `${indent}[Road Segments] ${route.road_segments.length} segments`);
      
      // Summary of segments by type
      const typeCount = {};
      route.road_segments.forEach(seg => {
        const type = seg.road_type || seg.type || 'unknown';
        typeCount[type] = (typeCount[type] || 0) + 1;
      });
      
      Object.entries(typeCount).forEach(([type, count]) => {
        this.log('INFO', `${indent}  ├─ ${type}: ${count}`);
      });
    }

    // Turn directions count
    if (route.turn_by_turn_directions && Array.isArray(route.turn_by_turn_directions)) {
      this.log('INFO', `${indent}[Turn Instructions] ${route.turn_by_turn_directions.length} turns`);
    }

    // Complete trace (node path with coordinates) - single line format
    if (route.complete_trace) {
      if (typeof route.complete_trace === 'string') {
        this.logSingleLine('INFO', `${indent}[Complete Trace]`, route.complete_trace);
      } else if (Array.isArray(route.complete_trace)) {
        const traceStr = this.formatCompletePath(route.complete_trace);
        this.logSingleLine('INFO', `${indent}[Complete Trace]`, traceStr);
      }
    }

    // Route summary from geometry (road_name (distance) → road_name (distance))
    if (route.geometry && Array.isArray(route.geometry)) {
      const routeSummary = this.formatRouteSummaryFromGeometry(route.geometry);
      if (routeSummary) {
        this.logSingleLine('INFO', `${indent}[Route Summary]`, routeSummary);
      }
    }

    // Route summary (alternative format of complete trace)
    if (route.route_summary && Array.isArray(route.route_summary)) {
      const summaryStr = this.formatCompletePath(route.route_summary);
      this.logSingleLine('INFO', `${indent}[Route Summary]`, summaryStr);
    }

    // Other route properties (excluding geometry)
    Object.entries(route).forEach(([key, value]) => {
      if (excluded.some(ex => key.toLowerCase().includes(ex))) {
        return;
      }

      // Skip already logged properties
      if (['distance', 'calculated_distance_meters', 'duration', 'eta_seconds', 'road_segments', 'turn_by_turn_directions', 'complete_trace', 'route_summary', 'path_nodes'].includes(key)) {
        return;
      }

      // Skip arrays and objects (already handled)
      if (typeof value === 'object' && value !== null) {
        return;
      }

      this.log('INFO', `${indent}[${key}] ${value}`);
    });
  }

  /**
   * Parse alternative route details
   */
  parseAlternativeRoute(alt, index) {
    const indent = '  ';
    this.log('INFO', `${indent}Route #${index}:`);
    
    if (alt.rank) {
      this.log('INFO', `${indent}  [Rank] ${alt.rank}`);
    }
    if (alt.description) {
      this.log('INFO', `${indent}  [Description] ${alt.description}`);
    }
    if (alt.distance_meters) {
      this.log('INFO', `${indent}  [Distance] ${(alt.distance_meters / 1000).toFixed(2)} km`);
    }
    if (alt.eta_seconds) {
      const hours = Math.floor(alt.eta_seconds / 3600);
      const mins = Math.floor((alt.eta_seconds % 3600) / 60);
      this.log('INFO', `${indent}  [ETA] ${hours > 0 ? hours + 'h ' : ''}${mins}m`);
    }
    if (alt.eta_formatted) {
      this.log('INFO', `${indent}  [ETA Formatted] ${alt.eta_formatted}`);
    }
    if (alt.path_length) {
      this.log('INFO', `${indent}  [Path Length] ${alt.path_length} nodes`);
    }
    if (alt.avg_jam_factor !== undefined) {
      this.log('INFO', `${indent}  [Avg Jam Factor] ${alt.avg_jam_factor.toFixed(2)}`);
    }
  }

  /**
   * Format complete path/trace as a single line
   * Format: 3940 @ 14.661307,121.038188 → 3886 @ 14.661792,121.038045 → ...
   */
  formatCompletePath(pathArray) {
    if (!Array.isArray(pathArray) || pathArray.length === 0) {
      return '[]';
    }

    // Format each node: "ID @ lat,lon"
    const formatted = pathArray.map(item => {
      if (typeof item === 'object' && item !== null) {
        // If it has id/lat/lon properties
        if (item.id !== undefined && item.lat !== undefined && item.lon !== undefined) {
          return `${item.id} @ ${item.lat},${item.lon}`;
        }
        // If it's an array [id, lat, lon]
        if (Array.isArray(item) && item.length >= 3) {
          return `${item[0]} @ ${item[1]},${item[2]}`;
        }
        // Fallback to JSON
        return JSON.stringify(item);
      }
      return String(item);
    }).join(' → ');

    return formatted;
  }

  /**
   * Format route summary from geometry data
   * Format: Alley 4 (55m) → Alley 2 (100m) → Alley 2 (174m) → ...
   */
  formatRouteSummaryFromGeometry(geometry) {
    if (!Array.isArray(geometry) || geometry.length === 0) {
      return null;
    }

    const routeSegments = geometry.map(segment => {
      const roadName = segment.road_name || 'Unknown';
      const distance = segment.distance_meters || 0;
      return `${roadName} (${distance}m)`;
    }).join(' → ');

    return routeSegments;
  }

  /**
   * Log a message with a value that should not be wrapped (single line)
   * This is used for complete_trace and route_summary which need horizontal scrolling
   */
  logSingleLine(level, label, value) {
    // Create a special log entry marked for single-line rendering
    const logEntry = {
      level,
      message: label,
      data: value,
      isSingleLine: true  // Mark for special rendering
    };

    this.logs.push(logEntry);

    // Keep only the last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs.shift();
    }

    this.render();
  }

  /**
   * Summarize alternative route
   */
  summarizeAlternative(alt, index) {
    const indent = '  ';
    let summary = `${indent}[Route ${index}]`;
    
    if (alt.distance) {
      summary += ` • Distance: ${(alt.distance / 1000).toFixed(2)}km`;
    } else if (alt.path_distance) {
      summary += ` • Distance: ${(alt.path_distance / 1000).toFixed(2)}km`;
    }

    if (alt.eta_seconds) {
      const hours = Math.floor(alt.eta_seconds / 3600);
      const mins = Math.floor((alt.eta_seconds % 3600) / 60);
      summary += ` • ETA: ${hours}h ${mins}m`;
    } else if (alt.duration) {
      summary += ` • Duration: ${Math.round(alt.duration / 60)}min`;
    }

    if (alt.path_length !== undefined) {
      summary += ` • Nodes: ${alt.path_length}`;
    }

    return summary;
  }

  /**
   * Parse disruption information
   */
  parseDisruptionInfo(info) {
    const indent = '  ';

    if (info.total_disrupted_edges) {
      this.log('INFO', `${indent}[Disrupted Edges] ${info.total_disrupted_edges}`);
    }
    if (info.incident_count) {
      this.log('INFO', `${indent}[Incidents] ${info.incident_count}`);
    }
    if (info.incident_types) {
      Object.entries(info.incident_types).forEach(([type, count]) => {
        this.log('INFO', `${indent}  [${type}] ${count}`);
      });
    }
    if (info.closed_roads) {
      this.log('INFO', `${indent}[Closed Roads] ${info.closed_roads}`);
    }
    if (info.congested_segments) {
      this.log('INFO', `${indent}[Congested Segments] ${info.congested_segments}`);
    }
  }

  /**
   * Parse Lazy HC2L update information
   */
  parseLazyHC2LInfo(info) {
    const indent = '  ';

    if (info.enabled !== undefined) {
      this.log('INFO', `${indent}[Enabled] ${info.enabled ? 'Yes' : 'No'}`);
    }
    if (info.disruption_impact_score !== undefined) {
      this.log('INFO', `${indent}[Impact Score] ${info.disruption_impact_score.toFixed(4)}`);
    }
    if (info.tau_threshold !== undefined) {
      this.log('INFO', `${indent}[Tau Threshold] ${info.tau_threshold}`);
    }
    if (info.update_strategy) {
      this.log('INFO', `${indent}[Update Strategy] ${info.update_strategy}`);
    }
    if (info.reason) {
      this.log('INFO', `${indent}[Reason] ${info.reason}`);
    }
    if (info.dirty_nodes_marked !== undefined) {
      this.log('INFO', `${indent}[Dirty Nodes Marked] ${info.dirty_nodes_marked}`);
    }
    if (info.total_updates !== undefined) {
      this.log('INFO', `${indent}[Total Updates] ${info.total_updates}`);
    }
    if (info.dirty_nodes_affected_path !== undefined) {
      this.log('INFO', `${indent}[Dirty Nodes on Path] ${info.dirty_nodes_affected_path}`);
    }
    if (info.lazy_repair_time_ms !== undefined) {
      this.log('INFO', `${indent}[Repair Time] ${info.lazy_repair_time_ms.toFixed(3)}ms`);
    }
    if (info.nodes_repaired !== undefined) {
      this.log('INFO', `${indent}[Nodes Repaired] ${info.nodes_repaired}`);
    }
    if (info.cache_hit !== undefined) {
      this.log('INFO', `${indent}[Cache Hit] ${info.cache_hit ? 'Yes' : 'No'}`);
    }
  }

  /**
   * Parse update information (DHL/HC2L)
   */
  parseUpdateInfo(info) {
    const indent = '  ';

    if (info.update_mode) {
      this.log('INFO', `${indent}[Update Mode] ${info.update_mode}`);
    }
    if (info.nodes_updated) {
      this.log('INFO', `${indent}[Nodes Updated] ${info.nodes_updated}`);
    }
    if (info.edges_affected) {
      this.log('INFO', `${indent}[Edges Affected] ${info.edges_affected}`);
    }
    if (info.time_spent_ms) {
      this.log('INFO', `${indent}[Update Time] ${info.time_spent_ms.toFixed(2)}ms`);
    }
  }

  /**
   * Parse HC2L labeling information
   */
  parseHC2LLabelingInfo(info) {
    const indent = '  ';

    if (info.total_labels) {
      this.log('INFO', `${indent}[Total Labels] ${info.total_labels.toLocaleString()}`);
    }
    if (info.infinite_labels !== undefined) {
      this.log('INFO', `${indent}[Infinite Labels] ${info.infinite_labels}`);
    }
    if (info.index_size_bytes) {
      const sizeMB = (info.index_size_bytes / (1024 * 1024)).toFixed(2);
      this.log('INFO', `${indent}[Index Size] ${sizeMB} MB`);
    }
    if (info.index_size_mb) {
      this.log('INFO', `${indent}[Index Size MB] ${info.index_size_mb.toFixed(2)} MB`);
    }
    if (info.hierarchy_height) {
      this.log('INFO', `${indent}[Hierarchy Height] ${info.hierarchy_height} levels`);
    }
    if (info.max_label_count_per_node) {
      this.log('INFO', `${indent}[Max Labels per Node] ${info.max_label_count_per_node}`);
    }
    if (info.max_cut_size) {
      this.log('INFO', `${indent}[Max Cut Size] ${info.max_cut_size}`);
    }
    if (info.average_cut_size) {
      this.log('INFO', `${indent}[Average Cut Size] ${info.average_cut_size.toFixed(2)}`);
    }
    if (info.non_empty_cuts) {
      this.log('INFO', `${indent}[Non-Empty Cuts] ${info.non_empty_cuts}`);
    }
    if (info.index_load_time_ms) {
      this.log('INFO', `${indent}[Load Time] ${info.index_load_time_ms.toFixed(3)}ms`);
    }
  }

  /**
   * Parse DHL information
   */
  parseDHLInfo(info) {
    const indent = '  ';

    if (info.hoplinks_examined) {
      this.log('INFO', `${indent}[Hoplinks Examined] ${info.hoplinks_examined}`);
    }
    if (info.nodes_visited) {
      this.log('INFO', `${indent}[Nodes Visited] ${info.nodes_visited}`);
    }
    if (info.preprocessing_time_ms) {
      this.log('INFO', `${indent}[Preprocessing Time] ${info.preprocessing_time_ms.toFixed(3)}ms`);
    }
    if (info.edges_relaxed) {
      this.log('INFO', `${indent}[Edges Relaxed] ${info.edges_relaxed}`);
    }
    if (info.query_time_us) {
      this.log('INFO', `${indent}[Query Time] ${(info.query_time_us / 1000).toFixed(3)}ms`);
    }
  }

  /**
   * Render all logs to the console element
   */
  render() {
    if (!this.consoleElement) return;

    if (this.isRawMode) {
      // Raw JSON view
      this.consoleElement.innerHTML = `<pre>${JSON.stringify(this.logs, null, 2)}</pre>`;
    } else {
      // Formatted view
      let html = '';
      this.logs.forEach(entry => {
        const levelClass = this.getLevelClass(entry.level);
        const levelIcon = this.getLevelIcon(entry.level);
        
        // Handle single-line entries (complete_trace, route_summary)
        if (entry.isSingleLine) {
          html += `<div class="console-line console-single-line ${levelClass}">
            <span class="console-level">${levelIcon}</span>
            <span class="console-message console-single-line-text">${this.escapeHtml(entry.message)}</span>
            <span class="console-single-line-value">${this.escapeHtml(entry.data)}</span>
          </div>`;
        } else {
          html += `<div class="console-line ${levelClass}">
            <span class="console-level">${levelIcon}</span>
            <span class="console-message">${this.escapeHtml(entry.message)}</span>
          </div>`;
        }
      });
      this.consoleElement.innerHTML = html;
    }

    // Auto-scroll to bottom
    this.consoleElement.scrollTop = this.consoleElement.scrollHeight;
  }

  /**
   * Get CSS class for log level
   */
  getLevelClass(level) {
    const classes = {
      'INFO': 'console-info',
      'WARN': 'console-warn',
      'ERROR': 'console-error',
      'SUCCESS': 'console-success',
      'DEBUG': 'console-debug'
    };
    return classes[level] || 'console-info';
  }

  /**
   * Get icon for log level
   */
  getLevelIcon(level) {
    const icons = {
      'INFO': 'ℹ️',
      'WARN': '⚠️',
      'ERROR': '❌',
      'SUCCESS': '✅',
      'DEBUG': '🐛'
    };
    return icons[level] || '';
  }

  /**
   * Clear the console
   */
  clear() {
    this.logs = [];
    this.log('INFO', 'Console cleared');
  }

  /**
   * Copy console output to clipboard
   */
  copyToClipboard() {
    let text = '';
    this.logs.forEach(entry => {
      if (entry.isSingleLine) {
        text += `${entry.message} ${entry.data}\n`;
      } else {
        text += `${entry.message}\n`;
      }
    });

    navigator.clipboard.writeText(text).then(() => {
      console.log('✅ Console output copied to clipboard');
      // Show visual feedback
      const copyBtn = document.getElementById('api-console-copy');
      if (copyBtn) {
        // store the html content
        const original = copyBtn.innerHTML;
        // Lucid check mark
        copyBtn.innerHTML = `<i data-lucide="check-circle" class="w-5 h-5 text-green-500"></i>`;
        lucide.createIcons();
        // revert after 2 seconds
        setTimeout(() => {
          copyBtn.innerHTML = original;
        }, 2000);
      }
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  }

  /**
   * Toggle between formatted and raw view
   */
  toggleView() {
    this.isRawMode = !this.isRawMode;
    const toggleBtn = document.getElementById('api-console-toggle-view');
    if (toggleBtn) {
      toggleBtn.innerHTML =
        this.isRawMode ? 
        '<i data-lucide="list" class="w-5 h-5"></i>' :
        '<i data-lucide="code" class="w-5 h-5"></i>';
      lucide.createIcons();
    }
    this.render();
  }

  /**
   * Escape HTML special characters
   */
  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
  }
}

// Global console instance
let apiConsole = null;

/**
 * Initialize API Console when DOM is ready
 */
function initializeAPIConsole() {
  apiConsole = new APIConsole();
  if (apiConsole.init()) {
    console.log('✅ API Console initialized and ready');
    return true;
  }
  return false;
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeAPIConsole);
} else {
  initializeAPIConsole();
}
