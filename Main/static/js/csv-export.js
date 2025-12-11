/**
 * CSV Export Module
 * Export performance metrics and route data as CSV files
 * Includes: algorithm, query time, preprocessing time, label size,
 * nodes updated, route distance, Fréchet distance, overlap, etc.
 */

// Storage for export data
window.exportData = {
    routes: [],
    comparisons: [],
    currentSession: {
        startTime: new Date(),
        routeCount: 0
    }
};

/**
 * Add route data to export buffer
 * @param {Object} routeData - Complete route calculation response
 */
function addRouteToExport(routeData) {
    if (!routeData || !routeData.success) {
        return;
    }
    
    const metrics = routeData.metrics || {};
    const algorithm = routeData.algorithm || metrics.algorithm || 'Unknown';
    
    // Extract common metrics
    const exportEntry = {
        timestamp: new Date().toISOString(),
        algorithm: algorithm,
        query_time_ms: metrics.query_time_ms || 0,
        path_length: metrics.path_length || 0,
        edge_count: metrics.edge_count || 0,
        distance_km: metrics.total_distance_meters ? (metrics.total_distance_meters / 1000).toFixed(2) : 0,
        calculated_distance_km: metrics.calculated_distance_km || 0,
        eta_seconds: metrics.eta_seconds || 0,
        eta_formatted: metrics.eta_formatted || '--'
    };
    
    // Algorithm-specific metrics
    if (algorithm.includes('DHL')) {
        const dhlInfo = routeData.dhl_update_info || {};
        exportEntry.labeling_time_ms = metrics.labeling_time_ms || 0;
        exportEntry.labeling_size_kb = metrics.labeling_size_kb || 0;
        exportEntry.query_time_microseconds = metrics.query_time_microseconds || 0;
        exportEntry.update_strategy = dhlInfo.update_strategy || 'none';
        exportEntry.nodes_updated = dhlInfo.nodes_updated || 0;
        exportEntry.disruption_impact_score = dhlInfo.disruption_impact_score || 0;
    } else if (algorithm.includes('HC2L')) {
        const lazyInfo = routeData.lazy_hc2l || {};
        const labelingInfo = metrics.labeling_info || {};
        
        exportEntry.index_load_time_ms = labelingInfo.index_load_time_ms || 0;
        exportEntry.index_size_kb = labelingInfo.index_size_bytes ? labelingInfo.index_size_bytes / 1024 : 0;
        exportEntry.labeling_size_kb = metrics.labeling_size_kb || 0;
        exportEntry.update_strategy = lazyInfo.update_strategy || 'none';
        exportEntry.dirty_nodes_marked = lazyInfo.dirty_nodes_marked || 0;
        exportEntry.nodes_repaired = lazyInfo.nodes_repaired || 0;
        exportEntry.lazy_repair_time_ms = lazyInfo.lazy_repair_time_ms || 0;
        exportEntry.cache_hit = lazyInfo.cache_hit || false;
        exportEntry.disruption_impact_score = lazyInfo.disruption_impact_score || 0;
        exportEntry.tau_threshold = lazyInfo.tau_threshold || 0.5;
    }
    
    // Add to buffer
    window.exportData.routes.push(exportEntry);
    window.exportData.currentSession.routeCount++;
    
    console.log('📊 Route added to export buffer:', algorithm);
}

/**
 * Add Google Maps comparison data to export buffer
 * @param {Object} comparisonData - Google Maps comparison response
 */
function addComparisonToExport(comparisonData) {
    if (!comparisonData || !comparisonData.success) {
        return;
    }
    
    const comparison = comparisonData.comparison || {};
    const googleRoute = comparisonData.google_maps_route || {};
    
    const exportEntry = {
        timestamp: new Date().toISOString(),
        algorithm_distance_m: comparison.algorithm_distance_meters || 0,
        google_distance_m: googleRoute.distance_meters || 0,
        frechet_distance_m: comparison.frechet_distance_meters || 0,
        segment_overlap_percent: comparison.segment_overlap_percent || 0,
        google_duration_seconds: googleRoute.duration_seconds || 0,
        google_duration_minutes: Math.round((googleRoute.duration_seconds || 0) / 60),
        route_points: googleRoute.coordinates?.length || 0
    };
    
    window.exportData.comparisons.push(exportEntry);
    
    console.log('📊 Comparison added to export buffer');
}

/**
 * Convert array of objects to CSV string
 * @param {Array} data - Array of objects to convert
 * @param {Array} headers - Optional custom headers
 * @returns {string} CSV formatted string
 */
function arrayToCSV(data, headers = null) {
    if (!data || data.length === 0) {
        return '';
    }
    
    // Get headers from first object if not provided
    const keys = headers || Object.keys(data[0]);
    
    // Create header row
    const headerRow = keys.join(',');
    
    // Create data rows
    const dataRows = data.map(obj => {
        return keys.map(key => {
            const value = obj[key];
            // Handle values that might contain commas
            if (typeof value === 'string' && value.includes(',')) {
                return `"${value}"`;
            }
            return value !== undefined && value !== null ? value : '';
        }).join(',');
    });
    
    return [headerRow, ...dataRows].join('\n');
}

/**
 * Download CSV file
 * @param {string} csvContent - CSV formatted string
 * @param {string} filename - Filename for download
 */
function downloadCSV(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (navigator.msSaveBlob) {
        // IE 10+
        navigator.msSaveBlob(blob, filename);
    } else {
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    
    console.log('✅ CSV downloaded:', filename);
}

/**
 * Export all routes to CSV
 */
function exportRoutesToCSV() {
    if (window.exportData.routes.length === 0) {
        showUpdateToast('No route data to export', 'warning');
        return;
    }
    
    const csvContent = arrayToCSV(window.exportData.routes);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `route_performance_${timestamp}.csv`;
    
    downloadCSV(csvContent, filename);
    showUpdateToast(`Exported ${window.exportData.routes.length} routes to CSV`, 'success');
}

/**
 * Export comparisons to CSV
 */
function exportComparisonsToCSV() {
    if (window.exportData.comparisons.length === 0) {
        showUpdateToast('No comparison data to export', 'warning');
        return;
    }
    
    const csvContent = arrayToCSV(window.exportData.comparisons);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `google_maps_comparison_${timestamp}.csv`;
    
    downloadCSV(csvContent, filename);
    showUpdateToast(`Exported ${window.exportData.comparisons.length} comparisons to CSV`, 'success');
}

/**
 * Export current session summary
 */
function exportSessionSummary() {
    const summary = {
        session_start: window.exportData.currentSession.startTime.toISOString(),
        session_end: new Date().toISOString(),
        total_routes: window.exportData.routes.length,
        total_comparisons: window.exportData.comparisons.length
    };
    
    // Calculate averages by algorithm
    const algorithms = {};
    window.exportData.routes.forEach(route => {
        if (!algorithms[route.algorithm]) {
            algorithms[route.algorithm] = {
                count: 0,
                total_query_time: 0,
                total_distance: 0
            };
        }
        algorithms[route.algorithm].count++;
        algorithms[route.algorithm].total_query_time += parseFloat(route.query_time_ms) || 0;
        algorithms[route.algorithm].total_distance += parseFloat(route.distance_km) || 0;
    });
    
    const summaryData = [summary];
    
    // Add algorithm statistics
    Object.keys(algorithms).forEach(algo => {
        const stats = algorithms[algo];
        summaryData.push({
            algorithm: algo,
            route_count: stats.count,
            avg_query_time_ms: (stats.total_query_time / stats.count).toFixed(3),
            avg_distance_km: (stats.total_distance / stats.count).toFixed(2)
        });
    });
    
    const csvContent = arrayToCSV(summaryData);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `session_summary_${timestamp}.csv`;
    
    downloadCSV(csvContent, filename);
    showUpdateToast('Session summary exported', 'success');
}

/**
 * Export all data (routes + comparisons + summary)
 */
function exportAllData() {
    if (window.exportData.routes.length === 0 && window.exportData.comparisons.length === 0) {
        showUpdateToast('No data to export', 'warning');
        return;
    }
    
    exportRoutesToCSV();
    
    if (window.exportData.comparisons.length > 0) {
        setTimeout(() => exportComparisonsToCSV(), 500);
    }
    
    setTimeout(() => exportSessionSummary(), 1000);
}

/**
 * Clear export buffer
 */
function clearExportData() {
    const routeCount = window.exportData.routes.length;
    const comparisonCount = window.exportData.comparisons.length;
    
    window.exportData.routes = [];
    window.exportData.comparisons = [];
    window.exportData.currentSession = {
        startTime: new Date(),
        routeCount: 0
    };
    
    showUpdateToast(`Cleared ${routeCount} routes and ${comparisonCount} comparisons from buffer`, 'info');
    console.log('🗑️  Export data buffer cleared');
}

// Expose functions globally
window.addRouteToExport = addRouteToExport;
window.addComparisonToExport = addComparisonToExport;
window.exportRoutesToCSV = exportRoutesToCSV;
window.exportComparisonsToCSV = exportComparisonsToCSV;
window.exportSessionSummary = exportSessionSummary;
window.exportAllData = exportAllData;
window.clearExportData = clearExportData;

console.log('✅ CSV export module loaded');
