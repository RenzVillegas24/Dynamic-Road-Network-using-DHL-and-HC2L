/**
 * Disruption Utilities Module
 * 
 * Unified color and style mapping for traffic disruptions across all contexts:
 * - Route display (DHL/HC2L routes)
 * - Traffic overlay visualization
 * - Demo Creator disruption preview
 * - Demo Runner disruption display
 * - HERE API disruption display
 * 
 * SINGLE SOURCE OF TRUTH for disruption colors and styles
 */

const TrafficUtils = {
    // =========================================================================
    // COLOR CONSTANTS - Unified color palette for all disruption displays
    // =========================================================================
    COLORS: {
        // Severity-based colors (for jam_factor based coloring)
        BLOCKED: '#000000',     // Black - Road closed/blocked
        HEAVY: '#ef4444',       // Red - Heavy congestion (jam_factor >= 7.0)
        MEDIUM: '#f59e0b',      // Amber/Orange - Medium congestion (jam_factor >= 4.0)
        LIGHT: '#10b981',       // Green - Light congestion (jam_factor < 4.0)
        FREE_FLOW: '#22c55e',   // Bright green - Free flow (jam_factor < 2.0)
        
        // Route-specific default colors (when no traffic data)
        DHL_DEFAULT: '#8b5cf6', // Purple - DHL route default
        HC2L_DEFAULT: '#3b82f6', // Blue - HC2L route default
        
        // Incident type colors (for circle markers)
        INCIDENT_CRITICAL: '#dc2626',  // Dark red
        INCIDENT_MAJOR: '#ef4444',     // Red
        INCIDENT_MINOR: '#f59e0b',     // Amber
    },

    // =========================================================================
    // JAM FACTOR THRESHOLDS - Consistent thresholds across all modules
    // Based on HERE API jam_factor scale (0.0 = free flow, 10.0 = blocked)
    // =========================================================================
    THRESHOLDS: {
        BLOCKED: 10.0,   // Road blocked (or is_closed flag)
        HEAVY: 7.0,      // Heavy congestion
        MEDIUM: 4.0,     // Medium congestion
        LIGHT: 2.0,      // Light congestion (below this is free flow)
    },

    // =========================================================================
    // CORE UTILITY FUNCTIONS
    // =========================================================================

    /**
     * Get severity level from jam_factor value
     * @param {number} jamFactor - Jam factor value (0.0 - 10.0)
     * @param {boolean} isClosed - Whether the road is closed
     * @returns {string} Severity level: 'Blocked', 'Heavy', 'Medium', 'Light', 'FreeFlow'
     */
    getSeverityFromJamFactor(jamFactor, isClosed = false) {
        if (isClosed) return 'Blocked';
        const jf = parseFloat(jamFactor) || 0;
        if (jf >= this.THRESHOLDS.BLOCKED) return 'Blocked';
        if (jf >= this.THRESHOLDS.HEAVY) return 'Heavy';
        if (jf >= this.THRESHOLDS.MEDIUM) return 'Medium';
        if (jf >= this.THRESHOLDS.LIGHT) return 'Light';
        return 'FreeFlow';
    },

    /**
     * Get color for disruption based on jam_factor
     * This is the PRIMARY color function - use this for all traffic coloring
     * 
     * @param {number} jamFactor - Jam factor value (0.0 - 10.0)
     * @param {boolean} isClosed - Whether the road is closed
     * @param {string} defaultColor - Optional default color if no disruption (for route display)
     * @returns {string} Hex color code
     */
    getDisruptionColor(jamFactor, isClosed = false, defaultColor = null) {
        // Road closed takes precedence
        if (isClosed) return this.COLORS.BLOCKED;
        
        const jf = parseFloat(jamFactor) || 0;
        
        // If jam factor is very low and we have a default, use it
        if (jf < this.THRESHOLDS.LIGHT && defaultColor) {
            return defaultColor;
        }
        
        // Determine color based on jam_factor
        if (jf >= this.THRESHOLDS.BLOCKED) return this.COLORS.BLOCKED;
        if (jf >= this.THRESHOLDS.HEAVY) return this.COLORS.HEAVY;
        if (jf >= this.THRESHOLDS.MEDIUM) return this.COLORS.MEDIUM;
        if (jf >= this.THRESHOLDS.LIGHT) return this.COLORS.LIGHT;
        return this.COLORS.FREE_FLOW;
    },

    /**
     * Get color for incident based on criticality
     * Used for incident circle markers
     * 
     * @param {string} criticality - Incident criticality (critical, major, minor)
     * @param {boolean} isClosed - Whether the road is closed
     * @returns {string} Hex color code
     */
    getIncidentColor(criticality, isClosed = false) {
        if (isClosed) return this.COLORS.BLOCKED;
        
        const crit = (criticality || 'minor').toLowerCase();
        switch (crit) {
            case 'critical':
            case 'severe':
                return this.COLORS.INCIDENT_CRITICAL;
            case 'major':
                return this.COLORS.INCIDENT_MAJOR;
            case 'minor':
            default:
                return this.COLORS.INCIDENT_MINOR;
        }
    },

    /**
     * Get severity level from criticality string (for incidents)
     * @param {string} criticality - Incident criticality (critical, major, minor)
     * @param {boolean} isClosed - Whether the road is closed
     * @returns {string} Severity level: 'Blocked', 'Heavy', 'Medium', 'Light'
     */
    getSeverityFromCriticality(criticality, isClosed = false) {
        if (isClosed) return 'Blocked';
        const crit = (criticality || 'minor').toLowerCase();
        switch (crit) {
            case 'critical':
            case 'severe':
                return 'Heavy';
            case 'major':
                return 'Medium';
            case 'minor':
            default:
                return 'Light';
        }
    },

    /**
     * Get Tailwind CSS text color class based on jam factor
     * Used for text styling in UI panels
     * @param {number} jamFactor - Jam factor value (0.0 - 10.0)
     * @returns {string} Tailwind CSS class
     */
    getSeverityTextClass(jamFactor) {
        const jf = parseFloat(jamFactor) || 0;
        if (jf >= this.THRESHOLDS.HEAVY) return 'text-red-600';
        if (jf >= this.THRESHOLDS.MEDIUM) return 'text-amber-600';
        return 'text-green-600';
    },

    /**
     * Get complete style object for a disruption polyline
     * 
     * @param {number} jamFactor - Jam factor value (0.0 - 10.0)
     * @param {boolean} isClosed - Whether the road is closed
     * @param {string} defaultColor - Optional default color for non-disrupted segments
     * @returns {Object} Style object with color, weight, opacity
     */
    getDisruptionStyle(jamFactor, isClosed = false, defaultColor = null) {
        const color = this.getDisruptionColor(jamFactor, isClosed, defaultColor);
        const severity = this.getSeverityFromJamFactor(jamFactor, isClosed);
        
        // Weight and opacity based on severity
        switch (severity) {
            case 'Blocked':
                return { color, weight: 7, opacity: 1 };
            case 'Heavy':
                return { color, weight: 6, opacity: 1};
            case 'Medium':
                return { color, weight: 5, opacity: 1 };
            case 'Light':
                return { color, weight: 4, opacity: 1 };
            case 'FreeFlow':
            default:
                return { color, weight: 4, opacity: 1};
        }
    },

    /**
     * Get style for incident circle marker
     * 
     * @param {string} criticality - Incident criticality
     * @param {boolean} isClosed - Whether the road is closed
     * @returns {Object} Style object for L.circleMarker
     */
    getIncidentMarkerStyle(criticality, isClosed = false) {
        const fillColor = this.getIncidentColor(criticality, isClosed);
        
        let radius = 8;
        if (isClosed) {
            radius = 12;
        } else if ((criticality || '').toLowerCase() === 'critical') {
            radius = 10;
        }
        
        return {
            radius,
            fillColor,
            color: '#ffffff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.9
        };
    },

    // =========================================================================
    // ROUTE DISPLAY HELPERS
    // =========================================================================

    /**
     * Get color for a route segment considering traffic flow
     * Used by displayDHLRoute and displayDHC2LRoute
     * 
     * @param {Object} segment - Route segment with flow data
     * @param {string} routeType - 'DHL' or 'HC2L'
     * @returns {string} Hex color code
     */
    getRouteSegmentColor(segment, routeType = 'DHL') {
        const defaultColor = routeType === 'DHL' ? this.COLORS.DHL_DEFAULT : this.COLORS.HC2L_DEFAULT;
        
        // Extract flow info from segment
        const flowInfo = segment.flow || {};
        const jamFactor = flowInfo.jam_factor ?? segment.jam_factor ?? 0;
        const isClosed = segment.is_closed || flowInfo.traversability === 'closed';
        
        // If there's significant traffic, use traffic color
        if (jamFactor >= this.THRESHOLDS.LIGHT || isClosed) {
            return this.getDisruptionColor(jamFactor, isClosed);
        }
        
        // Otherwise use route default
        return defaultColor;
    },

    /**
     * Get style for a route segment
     * 
     * @param {Object} segment - Route segment with flow data
     * @param {string} routeType - 'DHL' or 'HC2L'
     * @returns {Object} Style object with color, weight, opacity
     */
    getRouteSegmentStyle(segment, routeType = 'DHL') {
        const defaultColor = routeType === 'DHL' ? this.COLORS.DHL_DEFAULT : this.COLORS.HC2L_DEFAULT;
        
        const flowInfo = segment.flow || {};
        const jamFactor = flowInfo.jam_factor ?? segment.jam_factor ?? 0;
        const isClosed = segment.is_closed || flowInfo.traversability === 'closed';
        
        // If there's traffic disruption, use traffic styling
        if (jamFactor >= this.THRESHOLDS.LIGHT || isClosed) {
            return this.getDisruptionStyle(jamFactor, isClosed);
        }
        
        // Default route styling
        return {
            color: defaultColor,
            weight: 5,
            opacity: 1.0
        };
    },

    // =========================================================================
    // UNIFIED DISRUPTION PLOTTING
    // =========================================================================

    /**
     * Create a disruption polyline on the map
     * Unified function for all disruption display contexts
     * 
     * @param {Object} options - Polyline options
     * @param {Array} options.geometry - Array of [lat, lng] coordinates
     * @param {number} options.jamFactor - Jam factor value
     * @param {boolean} options.isClosed - Whether road is closed
     * @param {string} options.defaultColor - Optional default color
     * @param {string} options.className - Optional CSS class
     * @param {L.Map} targetMap - Leaflet map instance (defaults to global map)
     * @returns {L.Polyline} The created polyline
     */
    createDisruptionPolyline(options, targetMap = null) {
        const {
            geometry,
            jamFactor = 0,
            isClosed = false,
            defaultColor = null,
            className = 'disruption-segment'
        } = options;
        
        const mapInstance = targetMap || (typeof map !== 'undefined' ? map : null);
        if (!mapInstance) {
            console.error('TrafficUtils: No map instance available');
            return null;
        }
        
        if (!geometry || geometry.length < 2) {
            console.warn('TrafficUtils: Invalid geometry for polyline');
            return null;
        }
        
        const style = this.getDisruptionStyle(jamFactor, isClosed, defaultColor);
        const severity = this.getSeverityFromJamFactor(jamFactor, isClosed);
        
        const polyline = L.polyline(geometry, {
            color: style.color,
            weight: style.weight,
            opacity: style.opacity,
            className: 'route-segment-clickable'
        });
        
        // Add hover effects
        polyline.on('mouseover', function() {
            this.setStyle({
                weight: style.weight + 2,
                opacity: Math.min(style.opacity + 0.15, 1)
            });
        });
        
        polyline.on('mouseout', function() {
            this.setStyle({
                weight: style.weight,
                opacity: style.opacity
            });
        });
        
        return polyline;
    },

    /**
     * Create an incident circle marker on the map
     * Unified function for incident marker display
     * 
     * @param {Object} options - Marker options
     * @param {number} options.lat - Latitude
     * @param {number} options.lng - Longitude
     * @param {string} options.criticality - Incident criticality
     * @param {boolean} options.isClosed - Whether road is closed
     * @param {string} options.type - Incident type (for icon)
     * @param {L.Map} targetMap - Leaflet map instance
     * @returns {L.CircleMarker} The created marker
     */
    createIncidentMarker(options, targetMap = null) {
        const {
            lat,
            lng,
            criticality = 'minor',
            isClosed = false,
            type = 'default'
        } = options;
        
        const mapInstance = targetMap || (typeof map !== 'undefined' ? map : null);
        if (!mapInstance) {
            console.error('TrafficUtils: No map instance available');
            return null;
        }
        
        const style = this.getIncidentMarkerStyle(criticality, isClosed);
        
        return L.circleMarker([lat, lng], style);
    },

    // =========================================================================
    // INCIDENT TYPE ICONS
    // =========================================================================
    INCIDENT_ICONS: {
        'Accident': '🚗',
        'accident': '🚗',
        'Road Closure': '🚧',
        'roadClosure': '🚧',
        'Construction': '🏗️',
        'construction': '🏗️',
        'Congestion': '🚦',
        'congestion': '🚦',
        'Weather': '🌧️',
        'weather': '🌧️',
        'Road Hazard': '⚠️',
        'hazard': '⚠️',
        'Disabled Vehicle': '🚙',
        'disabledVehicle': '🚙',
        'Other': '📍',
        'default': '📍'
    },

    /**
     * Get icon for incident type
     * @param {string} incidentType - The incident type
     * @returns {string} Emoji icon
     */
    getIncidentIcon(incidentType) {
        return this.INCIDENT_ICONS[incidentType] || this.INCIDENT_ICONS['default'];
    },

    // =========================================================================
    // LEGACY COMPATIBILITY - Map old field names to new unified approach
    // =========================================================================

    /**
     * Extract jam_factor from various data formats
     * Handles different field names used across the codebase
     * 
     * @param {Object} data - Data object that may contain jam factor
     * @returns {number} Jam factor value
     */
    extractJamFactor(data) {
        if (!data) return 0;
        
        // Try various field locations
        return parseFloat(
            data.jam_factor ??
            data.jamFactor ??
            data.flow?.jam_factor ??
            data.flow?.jamFactor ??
            0
        );
    },

    /**
     * Extract closed status from various data formats
     * 
     * @param {Object} data - Data object
     * @returns {boolean} Whether road is closed
     */
    extractIsClosed(data) {
        if (!data) return false;
        
        return Boolean(
            data.is_closed ||
            data.isClosed ||
            data.road_closed ||
            data.roadClosed ||
            data.incident?.road_closed ||
            data.flow?.traversability === 'closed'
        );
    },

    // =========================================================================
    // UNIFIED DISRUPTION DISPLAY FUNCTIONS
    // These functions create map elements for disruptions consistently
    // =========================================================================

    /**
     * Create a flow/traffic polyline on the map
     * Use this for traffic congestion segments
     * 
     * @param {Object} options - Options object
     * @param {Array} options.geometry - Array of [lat, lng] coordinates, or null to use source/target
     * @param {number} options.sourceLat - Source latitude
     * @param {number} options.sourceLng - Source longitude  
     * @param {number} options.targetLat - Target latitude
     * @param {number} options.targetLng - Target longitude
     * @param {number} options.jamFactor - Jam factor (0-10)
     * @param {boolean} options.isClosed - Whether road is closed
     * @param {string} options.roadName - Road name for popup
     * @param {string} options.highwayType - Highway type
     * @param {L.Map} targetMap - Map instance (defaults to global 'map')
     * @returns {L.Polyline} The created polyline (not added to map yet)
     */
    createFlowPolyline(options, targetMap = null) {
        const mapInstance = targetMap || (typeof map !== 'undefined' ? map : null);
        if (!mapInstance) return null;

        let geometry = options.geometry;
        if (!geometry || geometry.length < 2) {
            geometry = [
                [parseFloat(options.sourceLat), parseFloat(options.sourceLng)],
                [parseFloat(options.targetLat), parseFloat(options.targetLng)]
            ];
        }

        const jamFactor = parseFloat(options.jamFactor) || 0;
        const isClosed = options.isClosed || false;
        const style = this.getDisruptionStyle(jamFactor, isClosed);
        const severity = this.getSeverityFromJamFactor(jamFactor, isClosed);

        const polyline = L.polyline(geometry, {
            color: style.color,
            weight: style.weight,
            opacity: style.opacity,
            className: 'route-segment-clickable'
        });

        // Create popup
        const popup = typeof PopupStyles !== 'undefined' ?
            PopupStyles.createTrafficPopup({
                road_name: options.roadName || 'Unknown Road',
                incident_type: 'Congestion',
                severity: severity,
                speed_kph: options.speedKph || 0,
                free_flow_kph: options.freeFlowKph || 50,
                jam_factor: jamFactor,
                is_closed: isClosed
            }) :
            `<div class="p-3">
                <b>🚦 Traffic Congestion</b><br>
                <b>Road:</b> ${options.roadName || 'Unknown'}<br>
                <b>Severity:</b> <span style="color:${style.color}">${severity}</span><br>
                <b>Jam Factor:</b> ${jamFactor.toFixed(1)}/10
            </div>`;

        polyline.bindPopup(popup);

        // Hover effects
        polyline.on('mouseover', function() {
            this.setStyle({ weight: style.weight + 2, opacity: Math.min(style.opacity + 0.15, 1) });
        });
        polyline.on('mouseout', function() {
            this.setStyle({ weight: style.weight, opacity: style.opacity });
        });

        return polyline;
    },

    /**
     * Create an incident marker with icon inside
     * Use this for accidents, road closures, construction, etc.
     * These markers should be added AFTER flow polylines so they appear on top
     * 
     * @param {Object} options - Options object
     * @param {number} options.lat - Marker latitude (or use sourceLat/targetLat for midpoint)
     * @param {number} options.lng - Marker longitude
     * @param {number} options.sourceLat - Source latitude (for midpoint calculation)
     * @param {number} options.sourceLng - Source longitude
     * @param {number} options.targetLat - Target latitude
     * @param {number} options.targetLng - Target longitude
     * @param {string} options.type - Incident type (accident, construction, roadClosure, etc.)
     * @param {string} options.criticality - Criticality level (critical, major, minor)
     * @param {boolean} options.isClosed - Whether road is closed
     * @param {string} options.roadName - Road name
     * @param {string} options.description - Incident description
     * @param {L.Map} targetMap - Map instance
     * @returns {L.Marker} The created marker with div icon (not added to map yet)
     */
    createIncidentMarkerWithIcon(options, targetMap = null) {
        const mapInstance = targetMap || (typeof map !== 'undefined' ? map : null);
        if (!mapInstance) return null;

        // Calculate position - use provided lat/lng or midpoint
        let lat = options.lat;
        let lng = options.lng;
        if (!lat || !lng) {
            lat = (parseFloat(options.sourceLat) + parseFloat(options.targetLat)) / 2;
            lng = (parseFloat(options.sourceLng) + parseFloat(options.targetLng)) / 2;
        }

        const type = options.type || 'default';
        const criticality = (options.criticality || 'minor').toLowerCase();
        const isClosed = options.isClosed || false;
        
        const fillColor = this.getIncidentColor(criticality, isClosed);
        const icon = this.getIncidentIcon(type);

        // Create div icon with emoji inside colored circle
        const divIcon = L.divIcon({
            className: 'disruption-incident-marker',
            html: `<div style="
                background: ${fillColor};
                color: white;
                width: 28px;
                height: 28px;
                border-radius: 50%;
                border: 2px solid white;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.4);
                cursor: pointer;
            ">${icon}</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });

        const marker = L.marker([lat, lng], { 
            icon: divIcon,
            zIndexOffset: 1000  // Ensure incidents appear on top of flow lines
        });

        // Create popup
        const popup = typeof PopupStyles !== 'undefined' ?
            PopupStyles.createIncidentPopup({
                road_name: options.roadName || 'Unknown Road',
                incident_type: type,
                incident_criticality: criticality,
                incident_road_closed: isClosed,
                incident_description: options.description || '',
                incident_start_time: options.startTime || '',
                incident_end_time: options.endTime || '',
                highway_type: options.highwayType || ''
            }) :
            `<div class="p-3 min-w-[200px]">
                <div class="font-bold text-lg mb-2">${icon} ${type}</div>
                <div class="text-sm text-slate-600 mb-1">📍 ${options.roadName || 'Unknown'}</div>
                <div class="text-sm"><b>Criticality:</b> <span style="color:${fillColor}">${criticality}</span></div>
                ${isClosed ? '<div class="text-sm font-bold text-red-600 mt-1">🚫 Road Closed</div>' : ''}
                ${options.description ? `<div class="text-sm mt-1">${options.description}</div>` : ''}
            </div>`;

        marker.bindPopup(popup);

        return marker;
    },

    /**
     * Display disruptions on a map - UNIFIED FUNCTION
     * Call this from disruptions.js, demo-creator.js, demo-runner.js
     * 
     * @param {Object} options - Display options
     * @param {Array} options.flowSegments - Array of flow/traffic segments
     * @param {Array} options.incidents - Array of incident objects
     * @param {L.Map} options.map - Leaflet map instance
     * @param {Array} options.layerStorage - Array to store created layers for later cleanup
     * @param {boolean} options.showFlow - Whether to show flow polylines (default true)
     * @param {boolean} options.showIncidents - Whether to show incident markers (default true)
     * @returns {Object} { flowLayers: [], incidentLayers: [], total: number }
     */
    displayDisruptionsOnMap(options) {
        const {
            flowSegments = [],
            incidents = [],
            map: targetMap,
            layerStorage = [],
            showFlow = true,
            showIncidents = true
        } = options;

        const mapInstance = targetMap || (typeof map !== 'undefined' ? map : null);
        if (!mapInstance) {
            console.error('TrafficUtils.displayDisruptionsOnMap: No map instance');
            return { flowLayers: [], incidentLayers: [], total: 0 };
        }

        const flowLayers = [];
        const incidentLayers = [];

        // FIRST: Add flow polylines (these go underneath)
        if (showFlow && flowSegments.length > 0) {
            flowSegments.forEach(f => {
                const polyline = this.createFlowPolyline({
                    geometry: f.geometry,
                    sourceLat: f.source_lat,
                    sourceLng: f.source_lng || f.source_lon,
                    targetLat: f.target_lat,
                    targetLng: f.target_lng || f.target_lon,
                    jamFactor: f.jam_factor,
                    isClosed: f.is_closed || f.road_closed,
                    roadName: f.road_name,
                    highwayType: f.highway_type,
                    speedKph: f.speed_kph || f.current_speed,
                    freeFlowKph: f.free_flow_kph || f.free_flow_speed
                }, mapInstance);

                if (polyline) {
                    polyline.addTo(mapInstance);
                    flowLayers.push(polyline);
                    layerStorage.push(polyline);
                }
            });
        }

        // SECOND: Add incident markers (these go on top with zIndexOffset)
        if (showIncidents && incidents.length > 0) {
            incidents.forEach(inc => {
                const marker = this.createIncidentMarkerWithIcon({
                    sourceLat: inc.source_lat,
                    sourceLng: inc.source_lng || inc.source_lon,
                    targetLat: inc.target_lat,
                    targetLng: inc.target_lng || inc.target_lon,
                    lat: inc.lat,
                    lng: inc.lng,
                    type: inc.type || inc.incident_type,
                    criticality: inc.criticality || inc.incident_criticality,
                    isClosed: inc.road_closed || inc.incident_road_closed || inc.is_closed,
                    roadName: inc.road_name,
                    description: inc.description || inc.incident_description,
                    startTime: inc.start_time || inc.incident_start_time,
                    endTime: inc.end_time || inc.incident_end_time,
                    highwayType: inc.highway_type
                }, mapInstance);

                if (marker) {
                    marker.addTo(mapInstance);
                    incidentLayers.push(marker);
                    layerStorage.push(marker);
                }
            });
        }

        const total = flowLayers.length + incidentLayers.length;
        console.log(`✅ TrafficUtils: Added ${flowLayers.length} flow + ${incidentLayers.length} incidents = ${total} layers`);

        return { flowLayers, incidentLayers, total };
    },

    /**
     * Clear disruption layers from map
     * @param {Array} layers - Array of Leaflet layers to remove
     * @param {L.Map} targetMap - Map instance
     */
    clearDisruptionLayers(layers, targetMap = null) {
        const mapInstance = targetMap || (typeof map !== 'undefined' ? map : null);
        if (!mapInstance || !layers) return;

        layers.forEach(layer => {
            if (mapInstance.hasLayer(layer)) {
                mapInstance.removeLayer(layer);
            }
        });
        layers.length = 0; // Clear the array
    }
};

// Export for global use
window.TrafficUtils = TrafficUtils;

// Also export individual commonly used functions for convenience
window.getDisruptionColor = (jamFactor, isClosed, defaultColor) => 
    TrafficUtils.getDisruptionColor(jamFactor, isClosed, defaultColor);
window.getSeverityFromJamFactor = (jamFactor, isClosed) => 
    TrafficUtils.getSeverityFromJamFactor(jamFactor, isClosed);
window.getDisruptionStyle = (jamFactor, isClosed, defaultColor) => 
    TrafficUtils.getDisruptionStyle(jamFactor, isClosed, defaultColor);

console.log('✅ TrafficUtils module loaded - Unified disruption color/style utilities');
