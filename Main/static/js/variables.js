// Google Maps variables
const adminPanel = document.getElementById("admin-panel");
const disruptionsPanel = document.getElementById("disruptions-panel");
const reportPanel = document.getElementById("report-panel");
const currentPathPanel = document.getElementById("current-path-panel");
const alertBanner = document.getElementById("alert-banner");
const thresholdValue = document.getElementById("threshold-value");
const updateModeBadge = document.getElementById("update-mode-badge");
const comparisonButtons = document.getElementById("comparison-buttons");
const comparisonModal = document.getElementById("comparison-modal");
// const similarityModal = document.getElementById("similarity-modal");
const mapContainer = document.getElementById("map-container");
const newDatasetButtonText = document.getElementById("new-dataset-text");

let currentThreshold = 0.5;
let isComparisonMode = false;
let pinningMode = null;
let startLocation = null;
let destLocation = null;
let reportLocation = null;
let currentRouteData = null; // Store the latest route data
let useDisruptions = false; // Track whether to use disruptions (default: false)
let map;
let startMarker, destMarker, reportMarker;
let directionsService, directionsRenderer;
let routePolylines = []; // Store D-HC2L route polylines
let disruptionMarkers = []; // Store disruption markers
let allNodesLayer = null; // Leaflet layer for displaying all nodes (toggleable)
window.alternativeRoutePolylines = []; // Store alternative route polylines
window.currentSelectedAlternativeRouteIndex = null; // Track which alternative route is currently selected (null = none)
if (typeof window.currentRouteData === 'undefined') {
  window.currentRouteData = currentRouteData;
} else {
  currentRouteData = window.currentRouteData;
}
window.currentRouteGeometry = window.currentRouteGeometry || [];
window.currentDisruptionsSummary = window.currentDisruptionsSummary || null;
window.currentDisruptions = window.currentDisruptions || [];
if (typeof window.disruptionMarkers === 'undefined') {
  window.disruptionMarkers = disruptionMarkers;
} else {
  disruptionMarkers = window.disruptionMarkers;
}

// ============================================================================
// DISRUPTION DATA STRUCTURE HELPERS
// ============================================================================
// These functions provide backward compatibility for the new separated
// data structure (incident, flow, disruption_metrics) coming from C++ APIs

/**
 * Map new severity_level to old severity format for UI consistency
 * @param {string} severity_level - New format: critical|high|medium|low|none
 * @returns {string} Old format: Heavy|Medium|Light
 */
function mapSeverityToOld(severity_level) {
  const mapping = {
    'critical': 'Heavy',
    'high': 'Heavy',
    'medium': 'Medium',
    'low': 'Light',
    'none': 'Light'
  };
  return mapping[severity_level?.toLowerCase()] || 'Medium';
}

/**
 * Safe accessor for nested disruption data with backward compatibility
 * Supports both old flat structure and new nested structure
 * @param {Object} disruption - The disruption object
 * @param {string} field - Field name to retrieve
 * @returns {*} The field value or undefined
 */
function getDisruptionField(disruption, field) {
  if (!disruption) return undefined;
  
  const fieldMap = {
    // Incident fields
    'incident_id': disruption.incident?.id || disruption.incident_id,
    'incident_type': disruption.incident?.type || disruption.incident_type || disruption.type,
    'type': disruption.incident?.type || disruption.type,
    'criticality': disruption.incident?.criticality || disruption.criticality,
    'description': disruption.incident?.description || disruption.description,
    'road_closed': disruption.incident?.road_closed ?? (disruption.is_closed ? true : false),
    'start_time': disruption.incident?.start_time || disruption.start_time,
    'end_time': disruption.incident?.end_time || disruption.end_time,
    
    // Flow fields
    'current_speed': disruption.flow?.speed_kph ?? disruption.current_speed,
    'speed_kph': disruption.flow?.speed_kph ?? disruption.current_speed,
    'jam_factor': disruption.flow?.jam_factor ?? disruption.jam_factor,
    'confidence': disruption.flow?.confidence ?? disruption.confidence,
    'flow_status': disruption.flow?.status || disruption.flow_status,
    
    // Disruption metrics fields
    'severity': mapSeverityToOld(disruption.disruption_metrics?.severity_level || disruption.severity_level || disruption.severity),
    'severity_level': disruption.disruption_metrics?.severity_level || disruption.severity_level || disruption.severity,
    'severity_score': disruption.disruption_metrics?.severity_score ?? disruption.severity_score,
    'weight_multiplier': disruption.disruption_metrics?.weight_multiplier ?? disruption.weight_multiplier,
    'time_impact_seconds': disruption.disruption_metrics?.time_impact_seconds ?? disruption.time_impact_seconds,
    'impact_score': disruption.disruption_metrics?.impact_score ?? disruption.impact_score,
    'old_weight': disruption.disruption_metrics?.old_weight ?? disruption.old_weight,
    'new_weight': disruption.disruption_metrics?.new_weight ?? disruption.new_weight,
    
    // Top-level fields (unchanged)
    'source': disruption.source,
    'target': disruption.target,
    'road_name': disruption.road_name,
    'highway_type': disruption.highway_type
  };
  
  return fieldMap[field] !== undefined ? fieldMap[field] : disruption[field];
}

/**
 * Check if disruption uses new nested structure
 * @param {Object} disruption - The disruption object to check
 * @returns {boolean} True if new structure, false if old flat structure
 */
function isNewStructure(disruption) {
  return !!(disruption && (disruption.incident || disruption.flow || disruption.disruption_metrics));
}

function resolveDisruptionEdge(disruption) {
  if (!disruption) return { source: undefined, target: undefined };
  const edgeArray = Array.isArray(disruption.edge) ? disruption.edge : null;
  const source = disruption.source ?? disruption.source_id ?? edgeArray?.[0];
  const target = disruption.target ?? disruption.target_id ?? edgeArray?.[1];
  return { source, target };
}

function normalizeCoordinateList(rawCoords) {
  if (!rawCoords) return [];
  let coords = rawCoords;
  if (typeof coords === 'string') {
    try {
      coords = JSON.parse(coords);
    } catch (err) {
      console.warn('Failed to parse coordinates string:', err);
      return [];
    }
  }
  if (!Array.isArray(coords)) return [];
  return coords
    .map((coord) => {
      if (!coord) return null;
      if (Array.isArray(coord)) {
        if (coord.length < 2) return null;
        const [first, second] = coord;
        // Detect whether format is [lat, lng] or [lng, lat]
        if (Math.abs(first) <= 90 && Math.abs(second) <= 180) {
          return { lat: Number(first), lng: Number(second) };
        }
        return { lat: Number(second), lng: Number(first) };
      }
      if (typeof coord === 'object') {
        const lat = coord.lat ?? coord.latitude ?? (Array.isArray(coord.coordinates) ? coord.coordinates[1] : undefined);
        const lng = coord.lng ?? coord.longitude ?? (Array.isArray(coord.coordinates) ? coord.coordinates[0] : undefined);
        if (typeof lat === 'number' && typeof lng === 'number') {
          return { lat, lng };
        }
      }
      return null;
    })
    .filter(Boolean);
}

function getMidpointLatLng(latLngs) {
  if (!latLngs || latLngs.length === 0) return null;
  const midIndex = Math.floor(latLngs.length / 2);
  return latLngs[midIndex];
}

function getActiveRouteGeometry() {
  if (window.currentRouteData?.route?.geometry?.length) {
    return window.currentRouteData.route.geometry;
  }
  if (currentRouteData?.route?.geometry?.length) {
    return currentRouteData.route.geometry;
  }
  if (Array.isArray(window.currentRouteGeometry) && window.currentRouteGeometry.length) {
    return window.currentRouteGeometry;
  }
  return [];
}

function matchesEdge(segment, source, target) {
  if (!segment || source === undefined || target === undefined) return false;
  const segFrom = Number(segment.from ?? segment.source);
  const segTo = Number(segment.to ?? segment.target);
  if (Number.isNaN(segFrom) || Number.isNaN(segTo)) return false;
  const src = Number(source);
  const dst = Number(target);
  return (segFrom === src && segTo === dst) || (segFrom === dst && segTo === src);
}

function getLatLngFromGeometry(source, target) {
  const geometrySegments = getActiveRouteGeometry();
  if (!geometrySegments || geometrySegments.length === 0) return null;
  const segment = geometrySegments.find((seg) => matchesEdge(seg, source, target));
  if (!segment || !segment.coordinates) return null;
  const latLngs = normalizeCoordinateList(segment.coordinates);
  return getMidpointLatLng(latLngs);
}

function getLatLngFromPolylines(source, target) {
  if (!window.routePolylines || window.routePolylines.length === 0) return null;
  for (const polyline of window.routePolylines) {
    const seg = polyline?._segmentData;
    if (seg && matchesEdge(seg, source, target)) {
      let latLngs = polyline.getLatLngs();
      if (!Array.isArray(latLngs)) continue;
      if (Array.isArray(latLngs[0])) {
        latLngs = latLngs.flat(Infinity);
      }
      if (latLngs.length === 0) continue;
      const mid = getMidpointLatLng(latLngs);
      if (mid) {
        return { lat: mid.lat, lng: mid.lng };
      }
    }
  }
  return null;
}

function getDisruptionLatLng(disruption) {
  if (!disruption) return null;

  // Direct lat/lng on object
  if (typeof disruption.lat === 'number' && typeof disruption.lng === 'number') {
    return { lat: disruption.lat, lng: disruption.lng };
  }
  if (typeof disruption.latitude === 'number' && typeof disruption.longitude === 'number') {
    return { lat: disruption.latitude, lng: disruption.longitude };
  }

  // Average of source/target coordinates if provided
  if (
    typeof disruption.source_lat === 'number' &&
    typeof disruption.target_lat === 'number' &&
    typeof disruption.source_lng === 'number' &&
    typeof disruption.target_lng === 'number'
  ) {
    return {
      lat: (disruption.source_lat + disruption.target_lat) / 2,
      lng: (disruption.source_lng + disruption.target_lng) / 2
    };
  }

  // Coordinates array on disruption (e.g., HERE raw data)
  if (disruption.coordinates) {
    const points = normalizeCoordinateList(disruption.coordinates);
    const mid = getMidpointLatLng(points);
    if (mid) return mid;
  }

  const { source, target } = resolveDisruptionEdge(disruption);
  const geometryLatLng = getLatLngFromGeometry(source, target);
  if (geometryLatLng) return geometryLatLng;

  const polylineLatLng = getLatLngFromPolylines(source, target);
  if (polylineLatLng) return polylineLatLng;

  return null;
}

window.getDisruptionLatLng = getDisruptionLatLng;
