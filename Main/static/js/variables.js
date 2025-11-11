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
