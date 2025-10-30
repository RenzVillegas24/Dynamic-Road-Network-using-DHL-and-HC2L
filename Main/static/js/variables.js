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
