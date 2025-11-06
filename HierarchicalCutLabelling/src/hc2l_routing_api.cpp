/*
 * HC2L Routing JSON API - REWRITTEN CLEAN VERSION
 * 
 * SIMPLIFIED ALGORITHM:
 *   1. Use HC2L labels to compute distance between all candidate node pairs
 *   2. Select best routing endpoints based on one-way constraints
 *   3. Use simple Dijkstra to find the path
 *   4. Ensure snap edges are included in output
 *   5. Clip geometry at snap points
 * 
 * Algorithm: Hierarchical Cut Labelling
 * Based on: https://github.com/henningkoehlernz/road-networks
 */
 
#define _USE_MATH_DEFINES

#include "road_network.h"
#include "util.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <ctime>
#include <chrono>
#include <map>
#include <set>
#include <queue>
#include <algorithm>
#include <sys/stat.h>

using namespace road_network;
using namespace std;

// Optimize I/O for large outputs
inline void setup_fast_io() {
    ios_base::sync_with_stdio(false);
    cout.tie(nullptr);
    // Reserve buffer size for large JSON output (increased from 256KB to 2MB)
    cout.rdbuf()->pubsetbuf(nullptr, 2 * 1024 * 1024);  // 2MB buffer
}

// Sanitize numeric values for JSON output (convert NaN/Inf to 0)
inline double sanitize_json_number(double value) {
    if (std::isnan(value) || std::isinf(value)) {
        return 0.0;
    }
    return value;
}

// Escape string for JSON output (escape quotes and backslashes)
inline string escape_json_string(const string& input) {
    string output;
    output.reserve(input.size() + 10); // Reserve extra space for escapes
    
    for (char c : input) {
        switch (c) {
            case '"':  output += "\\\""; break;
            case '\\': output += "\\\\"; break;
            case '\b': output += "\\b"; break;
            case '\f': output += "\\f"; break;
            case '\n': output += "\\n"; break;
            case '\r': output += "\\r"; break;
            case '\t': output += "\\t"; break;
            default:
                if (c < 32) {
                    // Control characters - output as \u00XX
                    char buf[7];
                    snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned char>(c));
                    output += buf;
                } else {
                    output += c;
                }
                break;
        }
    }
    
    return output;
}

// Helper structure for edge with geometry
struct EdgeGeometry {
    NodeID source;
    NodeID target;
    distance_t length;
    string road_name;  // Road name from OSM data
    vector<pair<double, double>> coords; // lon, lat pairs
    
    EdgeGeometry() : source(0), target(0), length(0), road_name("") {}
};

// Helper structure for GPS coordinates
struct GPSCoordinate {
    double latitude;
    double longitude;
    NodeID node_id;
    
    GPSCoordinate() : latitude(0), longitude(0), node_id(0) {}
    GPSCoordinate(double lat, double lng, NodeID id) : latitude(lat), longitude(lng), node_id(id) {}
};

// LazyHC2L State: tracks dirty labels and impact scores for adaptive updates
struct LazyHC2LState {
    set<NodeID> dirty_labels;           // Nodes with outdated labels
    map<NodeID, double> impact_scores;  // Per-node impact values
    time_t last_update_time;            // Timestamp of last update
    int update_count;                   // Counter for number of updates
    
    LazyHC2LState() : last_update_time(time(nullptr)), update_count(0) {}
};

// Traffic Flow Data: stores HERE API flow metrics per edge
struct TrafficFlowData {
    double jam_factor;          // 0.0 to 10.0 (HERE API format)
    double current_speed;       // Current speed in km/h
    double free_flow_speed;     // Free flow speed in km/h
    double speed_reduction;     // Percentage: 0.0 to 1.0
    string flow_status;         // "free_flow", "light", "moderate", "heavy", "blocked"
    string color_code;          // "green", "yellow", "orange", "red", "black"
    
    TrafficFlowData() : jam_factor(0.0), current_speed(0.0), free_flow_speed(50.0), 
                       speed_reduction(0.0), flow_status("free_flow"), color_code("green") {}
};

// Incident/Disruption Data: stores disruption details per edge
struct IncidentData {
    string type;                // "accident", "construction", "closure", "congestion", "weather"
    double severity;            // 0.0 to 1.0 (higher = more severe)
    double weight_multiplier;   // Cost multiplier for routing (1.0 = normal, >1.0 = avoid)
    int is_closed;              // 1 = road closed, 0 = passable
    double confidence;          // 0.0 to 1.0 (data reliability)
    string highway_type;        // "motorway", "trunk", "primary", "secondary", "tertiary", "residential"
    double impact_score;        // Combined impact metric
    distance_t old_weight;      // Original edge weight
    distance_t new_weight;      // Updated weight with disruption
    
    IncidentData() : type("unknown"), severity(0.0), weight_multiplier(1.0), 
                     is_closed(0), confidence(1.0), highway_type("unknown"),
                     impact_score(0.0), old_weight(0), new_weight(0) {}
};

// Disruption Cache: stores parsed disruption data to avoid re-parsing
struct DisruptionCache {
    map<pair<NodeID, NodeID>, IncidentData> incidents;
    map<pair<NodeID, NodeID>, TrafficFlowData> flow_data;
    time_t file_modified_time;
    string file_path;
    int total_incidents;
    int closures;
    int active_disruptions;
    
    DisruptionCache() : file_modified_time(0), total_incidents(0), 
                       closures(0), active_disruptions(0) {}
    
    bool is_valid(const string& filepath) const {
        if (filepath != file_path) return false;
        
        struct stat file_stat;
        if (stat(filepath.c_str(), &file_stat) != 0) return false;
        
        return file_stat.st_mtime == file_modified_time;
    }
};

// Global disruption cache (persists across requests)
static DisruptionCache g_disruption_cache;

// Global highway type map: stores highway_type for each edge (loaded from CSV)
static map<pair<NodeID, NodeID>, string> g_highway_types;

// Forward declarations
vector<string> parse_csv_line(const string& line);

// Alternative Route: stores route candidates with ETA metrics
struct AlternativeRoute {
    vector<NodeID> path;
    distance_t distance;
    double eta_seconds;
    double avg_jam_factor;
    string description;
    int rank;
    
    AlternativeRoute() : distance(0), eta_seconds(0.0), avg_jam_factor(0.0), rank(0) {}
};

// Calculate Haversine distance between two GPS coordinates
double haversine_distance(double lat1, double lon1, double lat2, double lon2) {
    const double R = 6371000.0; // Earth's radius in meters
    double phi1 = lat1 * M_PI / 180.0;
    double phi2 = lat2 * M_PI / 180.0;
    double delta_phi = (lat2 - lat1) * M_PI / 180.0;
    double delta_lambda = (lon2 - lon1) * M_PI / 180.0;
    
    double a = sin(delta_phi/2) * sin(delta_phi/2) +
               cos(phi1) * cos(phi2) *
               sin(delta_lambda/2) * sin(delta_lambda/2);
    double c = 2 * atan2(sqrt(a), sqrt(1-a));
    
    return R * c;
}

// Determine flow status and color code from jam factor
// Reference: HERE API jam_factor scale (0.0 = free flow, 10.0 = blocked)
TrafficFlowData get_flow_color(double jam_factor, double current_speed, double free_flow_speed) {
    TrafficFlowData flow;
    flow.jam_factor = jam_factor;
    flow.current_speed = current_speed;
    flow.free_flow_speed = free_flow_speed;
    
    if (free_flow_speed > 0) {
        flow.speed_reduction = 1.0 - (current_speed / free_flow_speed);
    } else {
        flow.speed_reduction = 0.0;
    }
    
    // Color coding based on jam_factor (HERE API scale)
    if (jam_factor < 2.0) {
        flow.flow_status = "free_flow";
        flow.color_code = "#10b981";    // Green (emerald)
    } else if (jam_factor < 4.0) {
        flow.flow_status = "light";
        flow.color_code = "#fbbf24";    // Yellow (amber)
    } else if (jam_factor < 7.0) {
        flow.flow_status = "moderate";
        flow.color_code = "#f59e0b";    // Orange
    } else if (jam_factor < 9.0) {
        flow.flow_status = "heavy";
        flow.color_code = "#ef4444";    // Red
    } else {
        flow.flow_status = "blocked";
        flow.color_code = "#000000";    // Black
    }
    
    return flow;
}

// Calculate total route distance from path nodes using coordinates
double calculate_route_distance(
    const vector<NodeID>& path,
    const map<NodeID, GPSCoordinate>& coordinates) {
    
    if (path.size() < 2) return 0.0;
    
    double total_distance = 0.0;
    
    for (size_t i = 0; i < path.size() - 1; i++) {
        NodeID from = path[i];
        NodeID to = path[i + 1];
        
        if (coordinates.count(from) && coordinates.count(to)) {
            const auto& coord_from = coordinates.at(from);
            const auto& coord_to = coordinates.at(to);
            
            double segment_distance = haversine_distance(
                coord_from.latitude, coord_from.longitude,
                coord_to.latitude, coord_to.longitude
            );
            
            total_distance += segment_distance;
        }
    }
    
    return total_distance;
}

// Calculate ETA in seconds based on route distance and traffic conditions
// Table 8 reference: Speed profiles for different incident types
struct SpeedProfile {
    const char* time_period;  // "morning", "noon", "evening"
    double baseline_speed_kmh;  // Free-flow speed
    double congestion_factor;   // Multiplier for congestion slowdown
};

// Speed profiles based on Quezon City traffic patterns (Table 8 reference)
map<string, SpeedProfile> get_speed_profiles() {
    return {
        // Morning rush (6am-10am): Moderate to heavy congestion
        {"morning", {"Morning Rush", 25.0, 0.4}},
        // Noon (11am-2pm): Moderate congestion, lighter than morning
        {"noon", {"Noon", 35.0, 0.65}},
        // Evening rush (4pm-8pm): Heaviest congestion
        {"evening", {"Evening Rush", 20.0, 0.35}},
        // Off-peak (other times): Light traffic
        {"off_peak", {"Off-Peak", 45.0, 0.85}}
    };
}

// Get current speed profile based on hour of day
SpeedProfile get_current_speed_profile(int hour = -1) {
    if (hour < 0) {
        // Use current time if not specified
        time_t now = time(nullptr);
        struct tm* timeinfo = localtime(&now);
        hour = timeinfo->tm_hour;
    }
    
    // Classification based on Table 8 patterns
    if (hour >= 6 && hour < 10) {
        return {"Morning Rush", 25.0, 0.4};  // Morning: 6am-10am
    } else if (hour >= 10 && hour < 14) {
        return {"Noon", 35.0, 0.65};          // Noon: 10am-2pm
    } else if (hour >= 14 && hour < 20) {
        return {"Evening Rush", 20.0, 0.35};  // Evening: 2pm-8pm (peak at 5pm-7pm)
    } else {
        return {"Off-Peak", 45.0, 0.85};      // Night/early morning
    }
}

// Calculate ETA in seconds from distance and jam factor
double calculate_eta_seconds(
    double distance_m,
    double jam_factor = 5.0,  // 0-10 scale
    int hour_of_day = -1) {
    
    if (distance_m <= 0) return 0.0;
    
    // Get speed profile based on time of day
    SpeedProfile profile = get_current_speed_profile(hour_of_day);
    
    // Adjust baseline speed based on jam factor (0=free flow, 10=standstill)
    // jam_factor > 7 indicates heavy congestion
    double jam_factor_normalized = jam_factor / 10.0;  // 0.0 to 1.0
    double actual_speed_kmh = profile.baseline_speed_kmh * 
                              (profile.congestion_factor + 
                               (1.0 - profile.congestion_factor) * (1.0 - jam_factor_normalized));
    
    // Ensure minimum speed (don't divide by zero)
    actual_speed_kmh = max(actual_speed_kmh, 1.0);
    
    // Convert to m/s: speed_kmh * 1000 / 3600 = speed_kmh / 3.6
    double actual_speed_ms = actual_speed_kmh / 3.6;
    
    // Calculate time: distance (m) / speed (m/s) = time (s)
    double eta_seconds = distance_m / actual_speed_ms;
    
    return eta_seconds;
}

// Calculate ETA with detailed flow data per edge
double calculate_eta_with_flow(
    const vector<NodeID>& path,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<NodeID, GPSCoordinate>& coordinates,
    int hour_of_day = -1) {
    
    if (path.size() < 2) return 0.0;
    
    double total_eta = 0.0;
    
    for (size_t i = 0; i < path.size() - 1; i++) {
        NodeID from = path[i];
        NodeID to = path[i + 1];
        auto edge_key = make_pair(from, to);
        
        // Calculate edge distance
        double edge_distance = 0.0;
        if (coordinates.count(from) && coordinates.count(to)) {
            const auto& coord_from = coordinates.at(from);
            const auto& coord_to = coordinates.at(to);
            edge_distance = haversine_distance(
                coord_from.latitude, coord_from.longitude,
                coord_to.latitude, coord_to.longitude
            );
        }
        
        if (edge_distance <= 0) continue;
        
        // CRITICAL FIX: Use actual speed from flow data if available
        double current_speed_kmh = 0.0;
        double jam_factor = 5.0; // Default
        
        if (flow_data.count(edge_key)) {
            const auto& flow = flow_data.at(edge_key);
            jam_factor = flow.jam_factor;
            
            // Prefer actual current speed over jam factor calculation
            if (flow.current_speed > 0.1) {
                current_speed_kmh = flow.current_speed;
            } else if (flow.free_flow_speed > 0.1) {
                // Estimate from jam factor and free flow speed
                double jam_reduction = min(1.0, jam_factor / 10.0);
                current_speed_kmh = flow.free_flow_speed * (1.0 - jam_reduction * 0.9);
            }
        }
        
        // Fallback to time-based calculation if no speed data
        if (current_speed_kmh <= 0.1) {
            double segment_eta = calculate_eta_seconds(edge_distance, jam_factor, hour_of_day);
            total_eta += segment_eta;
        } else {
            // Use actual speed: time = distance / speed
            current_speed_kmh = max(current_speed_kmh, 1.0); // Ensure minimum
            double edge_eta = edge_distance / (current_speed_kmh / 3.6); // distance(m) / speed(m/s)
            total_eta += edge_eta;
        }
    }
    
    return total_eta;
}

// ============================================================
// HIGHWAY CLASSIFICATION & ROUTING COST FUNCTIONS
// ============================================================

// Get highway type priority weight (lower = better/faster road)
// Motorways are fastest (1.0x), residential slowest (3.0x)
double get_highway_weight(const string& highway_type) {
    static const map<string, double> weights = {
        {"motorway", 1.0},       // Fastest: divided highway, high speed
        {"motorway_link", 1.05}, // Highway on/off ramps
        {"trunk", 1.1},          // Major roads, high capacity
        {"trunk_link", 1.15},
        {"primary", 1.3},        // Major connecting roads
        {"primary_link", 1.35},
        {"secondary", 1.6},      // Medium importance roads
        {"secondary_link", 1.65},
        {"tertiary", 2.0},       // Local connector roads
        {"tertiary_link", 2.05},
        {"unclassified", 2.3},   // Minor roads
        {"residential", 2.8},    // Slow residential streets
        {"living_street", 3.0},  // Very low speed zones
        {"service", 2.5},        // Service roads, parking lots
        {"road", 2.0}            // Unknown type default
    };
    
    auto it = weights.find(highway_type);
    return (it != weights.end()) ? it->second : 2.0; // Default to "road" weight
}

// Get free-flow speed for highway type (km/h)
double get_highway_speed(const string& highway_type) {
    static const map<string, double> speeds = {
        {"motorway", 100.0},
        {"motorway_link", 80.0},
        {"trunk", 80.0},
        {"trunk_link", 60.0},
        {"primary", 60.0},
        {"primary_link", 50.0},
        {"secondary", 50.0},
        {"secondary_link", 40.0},
        {"tertiary", 40.0},
        {"tertiary_link", 30.0},
        {"unclassified", 30.0},
        {"residential", 25.0},
        {"living_street", 20.0},
        {"service", 20.0},
        {"road", 40.0}
    };
    
    auto it = speeds.find(highway_type);
    return (it != speeds.end()) ? it->second : 40.0;
}

// Get incident severity multiplier based on incident type
// Higher multiplier = route around this incident more aggressively
double get_incident_severity(const string& incident_type) {
    static const map<string, double> severities = {
        {"closure", 999.0},      // Impassable - effectively infinite cost
        {"accident", 5.0},       // Major incident - avoid heavily
        {"construction", 2.5},   // Work zone - avoid moderately
        {"congestion", 1.8},     // Heavy traffic - avoid if alternatives exist
        {"weather", 1.5},        // Weather impact - minor avoidance
        {"unknown", 1.3}         // Default - slight avoidance
    };
    
    auto it = severities.find(incident_type);
    return (it != severities.end()) ? it->second : 1.3;
}

// Calculate edge cost with ALL factors: distance, highway type, flow, incidents
// This is the CRITICAL function that integrates everything
distance_t calculate_edge_cost(
    NodeID from, NodeID to,
    distance_t base_distance,
    const string& highway_type,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<pair<NodeID, NodeID>, IncidentData>& incident_data,
    const map<NodeID, GPSCoordinate>& coordinates) {
    
    auto edge_key = make_pair(from, to);
    
    // Start with base distance (or GPS distance if coordinates available)
    double cost = base_distance;
    
    // Use GPS distance if available (more accurate)
    if (coordinates.count(from) && coordinates.count(to)) {
        const auto& coord_from = coordinates.at(from);
        const auto& coord_to = coordinates.at(to);
        double gps_distance = haversine_distance(
            coord_from.latitude, coord_from.longitude,
            coord_to.latitude, coord_to.longitude
        );
        cost = gps_distance;
    }
    
    // Apply highway type weight (prefer higher-class roads)
    double highway_weight = get_highway_weight(highway_type);
    cost *= highway_weight;
    
    // Apply traffic flow penalty (if flow data available)
    if (flow_data.count(edge_key)) {
        const TrafficFlowData& flow = flow_data.at(edge_key);
        
        // Use jam_factor to increase cost: 0.0 = free, 10.0 = blocked
        // Formula: cost *= (1.0 + jam_factor * 0.5)
        // At jam_factor=10, cost increases by 5x
        double flow_multiplier = 1.0 + (flow.jam_factor / 10.0) * 4.0;
        cost *= flow_multiplier;
    }
    
    // Apply incident penalty (if incident present)
    if (incident_data.count(edge_key)) {
        const IncidentData& incident = incident_data.at(edge_key);
        
        // Road closure: make effectively impassable
        if (incident.is_closed) {
            return 999999999; // Very high cost (effectively infinite)
        }
        
        // Apply incident type severity
        double incident_multiplier = get_incident_severity(incident.type);
        cost *= incident_multiplier;
        
        // Also apply custom weight multiplier if provided
        cost *= incident.weight_multiplier;
    }
    
    return static_cast<distance_t>(cost);
}

// ============================================================
// DISRUPTION CACHE MANAGEMENT
// ============================================================

// Load and cache disruption data from file
// ENHANCED: Supports both formats:
//   1. Full format: source target new_weight jam_factor current_speed free_flow_speed impact_score confidence highway is_closed type
//   2. CSV format: source,target,...,speed_kph,freeFlow_kph,jamFactor,isClosed,...
bool load_disruptions_with_cache(
    const string& disruption_file,
    map<pair<NodeID, NodeID>, IncidentData>& incidents_out,
    map<pair<NodeID, NodeID>, TrafficFlowData>& flow_out,
    const map<NodeID, vector<Neighbor>>& adj_list,
    const map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries = map<pair<NodeID, NodeID>, EdgeGeometry>()) {
    
    // FORCE CSV: Convert .gr file path to .csv
    string actual_file = disruption_file;
    if (actual_file.size() > 3 && actual_file.substr(actual_file.size() - 3) == ".gr") {
        actual_file = actual_file.substr(0, actual_file.size() - 3) + ".csv";
        cerr << "🔧 FORCE CSV: Converted .gr to .csv: " << actual_file << endl;
    }
    
    // Check if cache is valid
    if (g_disruption_cache.is_valid(actual_file)) {
        cerr << "✅ Using cached disruption data (file unchanged)" << endl;
        incidents_out = g_disruption_cache.incidents;
        flow_out = g_disruption_cache.flow_data;
        return true;
    }
    
    // Cache invalid or file changed - reload
    cerr << "🔄 Loading disruptions from CSV file (cache miss or file updated)" << endl;
    
    ifstream disrupt_file(actual_file);
    if (!disrupt_file.is_open()) {
        cerr << "⚠️  Could not open disruption file: " << actual_file << endl;
        return false;
    }
    
    incidents_out.clear();
    flow_out.clear();
    
    int total_count = 0;
    int closures = 0;
    int active_disruptions = 0;
    
    string line;
    // FORCE CSV FORMAT - always use CSV parsing
    bool is_csv_format = true;
    int source_col = -1, target_col = -1, speed_col = -1, freeflow_col = -1;
    int jam_col = -1, closed_col = -1, length_col = -1;
    
    // Read and parse CSV header
    if (getline(disrupt_file, line)) {
        cerr << "   📋 Parsing CSV header..." << endl;
        
        // Parse CSV header to find column indices
        vector<string> headers = parse_csv_line(line);
        for (size_t i = 0; i < headers.size(); i++) {
            string h = headers[i];
            // Trim whitespace
            h.erase(0, h.find_first_not_of(" \t\n\r"));
            h.erase(h.find_last_not_of(" \t\n\r") + 1);
            
            // Exact match to avoid matching "source_lat" when looking for "source"
            if (h == "source") source_col = i;
            else if (h == "target") target_col = i;
            else if (h == "speed_kph") speed_col = i;
            else if (h == "freeFlow_kph") freeflow_col = i;
            else if (h == "jamFactor") jam_col = i;
            else if (h == "isClosed") closed_col = i;
            else if (h == "segmentLength") length_col = i;
        }
        
        cerr << "   Column mapping: source=" << source_col << ", target=" << target_col 
             << ", speed=" << speed_col << ", freeflow=" << freeflow_col 
             << ", jam=" << jam_col << ", closed=" << closed_col << endl;
    }
    
    while (getline(disrupt_file, line)) {
        if (line.empty() || line[0] == 'c' || line[0] == 'p') continue;
        
        NodeID source, target;
        distance_t new_weight = 0;
        double jam_factor = 5.0, current_speed = 0.0, free_flow_speed = 50.0;
        double impact_score = 0.5, confidence = 0.7;
        string highway_type = "unknown", disruption_type = "unknown";
        int is_closed = 0;
        
        if (is_csv_format) {
            // Parse CSV line
            vector<string> fields = parse_csv_line(line);
            
            // Skip if we don't have at least source and target columns
            if (source_col < 0 || target_col < 0 || 
                (int)fields.size() <= max(source_col, target_col)) continue;
            
            try {
                source = stoul(fields[source_col]);
                target = stoul(fields[target_col]);
                
                if (speed_col >= 0 && speed_col < (int)fields.size()) 
                    current_speed = stod(fields[speed_col]);
                if (freeflow_col >= 0 && freeflow_col < (int)fields.size()) 
                    free_flow_speed = stod(fields[freeflow_col]);
                if (jam_col >= 0 && jam_col < (int)fields.size()) 
                    jam_factor = stod(fields[jam_col]);
                if (closed_col >= 0 && closed_col < (int)fields.size()) {
                    string closed_str = fields[closed_col];
                    is_closed = (closed_str == "True" || closed_str == "true" || closed_str == "1") ? 1 : 0;
                }
                if (length_col >= 0 && length_col < (int)fields.size()) {
                    new_weight = static_cast<distance_t>(stod(fields[length_col]));
                }
                
                // FIX: If freeFlow_kph is 0 (missing from traffic data), estimate from highway_type
                if (free_flow_speed == 0.0) {
                    // Look ahead to read highway_type column (index 11)
                    if (fields.size() > 11) {
                        string hw_type = fields[11];
                        if (hw_type.find("motorway") != string::npos) free_flow_speed = 110.0;
                        else if (hw_type.find("trunk") != string::npos) free_flow_speed = 90.0;
                        else if (hw_type.find("primary") != string::npos) free_flow_speed = 70.0;
                        else if (hw_type.find("secondary") != string::npos) free_flow_speed = 60.0;
                        else if (hw_type.find("tertiary") != string::npos) free_flow_speed = 50.0;
                        else if (hw_type.find("residential") != string::npos) free_flow_speed = 40.0;
                        else free_flow_speed = 50.0;  // Default
                    } else {
                        free_flow_speed = 50.0;  // Default estimate
                    }
                }
                
                // Determine disruption type from data
                if (is_closed) {
                    disruption_type = "closure";
                } else if (jam_factor >= 8.0) {
                    disruption_type = "accident";
                } else if (jam_factor >= 5.0) {
                    disruption_type = "congestion";
                } else if (current_speed < free_flow_speed * 0.5) {
                    disruption_type = "construction";
                } else {
                    disruption_type = "congestion";
                }
                
            } catch (...) {
                continue;
            }
        } else {
            // Space-separated format (original)
            istringstream iss(line);
            if (!(iss >> source >> target >> new_weight)) continue;
            
            // Parse enhanced fields (optional)
            iss >> jam_factor >> current_speed >> free_flow_speed 
                >> impact_score >> confidence >> highway_type 
                >> is_closed >> disruption_type;
        }
        
        auto edge_key = make_pair(source, target);
        
        // Find old weight
        distance_t old_weight = 0;
        if (adj_list.count(source)) {
            for (const auto& neighbor : adj_list.at(source)) {
                if (neighbor.node == target) {
                    old_weight = neighbor.distance;
                    break;
                }
            }
        }
        
        // If new_weight not set, calculate from speed reduction
        if (new_weight == 0 && old_weight > 0) {
            if (is_closed) {
                new_weight = 999999;
            } else if (current_speed > 0.1 && free_flow_speed > 0.1) {
                // Scale weight by speed reduction: new = old * (freeflow / current)
                // Clamp ratio to reasonable range [1.0, 10.0]
                double speed_ratio = free_flow_speed / current_speed;
                speed_ratio = min(10.0, max(1.0, speed_ratio));
                new_weight = static_cast<distance_t>(old_weight * speed_ratio);
            } else if (jam_factor > 0.0) {
                // Use jam factor as fallback
                double flow_multiplier = 1.0 + (jam_factor / 10.0) * 4.0;
                new_weight = static_cast<distance_t>(old_weight * flow_multiplier);
            } else {
                new_weight = old_weight;
            }
        }
        
        // Look up highway type from edge geometries if not provided
        if (highway_type == "unknown" && edge_geometries.count(edge_key)) {
            // Edge geometries don't have highway type, so we'll need to pass it separately
            // For now, estimate from road characteristics
            if (free_flow_speed >= 80) highway_type = "motorway";
            else if (free_flow_speed >= 60) highway_type = "trunk";
            else if (free_flow_speed >= 50) highway_type = "primary";
            else if (free_flow_speed >= 40) highway_type = "secondary";
            else if (free_flow_speed >= 30) highway_type = "tertiary";
            else highway_type = "residential";
        }
        
        // Calculate impact score if not provided
        if (impact_score == 0.5) {
            double weight_change = (old_weight > 0) ? (double)(new_weight - old_weight) / old_weight : 0.0;
            double jam_impact = jam_factor / 10.0;
            double closure_factor = is_closed ? 1.0 : 0.0;
            impact_score = min(1.0, max(0.0, weight_change * 0.5 + jam_impact * 0.3 + closure_factor * 0.2));
        }
        
        // Store incident data
        IncidentData incident;
        incident.type = disruption_type;
        incident.is_closed = is_closed;
        incident.highway_type = highway_type;
        incident.confidence = confidence;
        incident.impact_score = impact_score;
        incident.old_weight = old_weight;
        incident.new_weight = new_weight;
        
        // Calculate severity
        incident.severity = (new_weight > old_weight && old_weight > 0) ? 
                           (double)(new_weight - old_weight) / old_weight : 0.0;
        incident.weight_multiplier = get_incident_severity(disruption_type);
        
        incidents_out[edge_key] = incident;
        
        // Store flow data
        flow_out[edge_key] = get_flow_color(jam_factor, current_speed, free_flow_speed);
        
        total_count++;
        if (is_closed || new_weight >= 999999.0) {
            closures++;
        } else {
            active_disruptions++;
        }
    }
    
    disrupt_file.close();
    
    // Update cache
    struct stat file_stat;
    if (stat(disruption_file.c_str(), &file_stat) == 0) {
        g_disruption_cache.file_modified_time = file_stat.st_mtime;
    }
    g_disruption_cache.file_path = disruption_file;
    g_disruption_cache.incidents = incidents_out;
    g_disruption_cache.flow_data = flow_out;
    g_disruption_cache.total_incidents = total_count;
    g_disruption_cache.closures = closures;
    g_disruption_cache.active_disruptions = active_disruptions;
    
    cerr << "✅ Loaded " << total_count << " disruptions (Closures: " << closures 
         << ", Active: " << active_disruptions << ")" << endl;
    
    return true;
}

// Generate K alternative routes using penalty-based search
vector<AlternativeRoute> generate_alternative_routes(
    NodeID start, NodeID dest,
    const map<NodeID, vector<Neighbor>>& adj_list,
    const ContractionIndex& ci,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<NodeID, GPSCoordinate>& coordinates,
    int K = 3) {
    
    vector<AlternativeRoute> alternatives;
    set<pair<NodeID, NodeID>> used_edges;
    
    for (int k = 0; k < K; k++) {
        // Find shortest path avoiding used edges (with penalty)
        map<NodeID, distance_t> dist;
        map<NodeID, NodeID> pred;
        set<NodeID> visited;
        
        priority_queue<pair<distance_t, NodeID>,
                       vector<pair<distance_t, NodeID>>,
                       greater<pair<distance_t, NodeID>>> pq;
        
        dist[start] = 0;
        pq.push({0, start});
        
        while (!pq.empty()) {
            auto [d, u] = pq.top();
            pq.pop();
            
            if (visited.count(u)) continue;
            visited.insert(u);
            
            if (u == dest) break;
            
            if (adj_list.count(u)) {
                for (const auto& neighbor : adj_list.at(u)) {
                    NodeID v = neighbor.node;
                    distance_t edge_cost = neighbor.distance;
                    
                    // Apply penalty to used edges
                    auto edge_key = make_pair(u, v);
                    if (used_edges.count(edge_key)) {
                        edge_cost *= 2; // 2x penalty for used edges
                    }
                    
                    distance_t new_dist = dist[u] + edge_cost;
                    
                    if (!dist.count(v) || new_dist < dist[v]) {
                        dist[v] = new_dist;
                        pred[v] = u;
                        pq.push({new_dist, v});
                    }
                }
            }
        }
        
        // Reconstruct path
        vector<NodeID> path;
        if (pred.count(dest) || dest == start) {
            NodeID curr = dest;
            while (curr != start) {
                path.push_back(curr);
                if (!pred.count(curr)) break;
                curr = pred[curr];
            }
            path.push_back(start);
            reverse(path.begin(), path.end());
        }
        
        if (path.empty() || path.size() < 2) break;
        
        // Calculate metrics
        AlternativeRoute route;
        route.path = path;
        route.distance = dist.count(dest) ? dist[dest] : 0;
        route.eta_seconds = calculate_eta_with_flow(path, flow_data, coordinates);
        
        // Calculate average jam factor
        double total_jam = 0.0;
        int edge_count = 0;
        for (size_t i = 0; i < path.size() - 1; i++) {
            auto edge_key = make_pair(path[i], path[i+1]);
            if (flow_data.count(edge_key)) {
                total_jam += flow_data.at(edge_key).jam_factor;
                edge_count++;
            }
        }
        route.avg_jam_factor = edge_count > 0 ? total_jam / edge_count : 5.0;
        route.rank = k + 1;
        route.description = k == 0 ? "Fastest route" : 
                           k == 1 ? "Alternative via different path" :
                           "Secondary alternative";
        
        alternatives.push_back(route);
        
        // Mark edges as used for next iteration
        for (size_t i = 0; i < path.size() - 1; i++) {
            used_edges.insert({path[i], path[i+1]});
        }
    }
    
    // Sort by ETA (best first)
    sort(alternatives.begin(), alternatives.end(),
         [](const AlternativeRoute& a, const AlternativeRoute& b) {
             return a.eta_seconds < b.eta_seconds;
         });
    
    // Update ranks
    for (size_t i = 0; i < alternatives.size(); i++) {
        alternatives[i].rank = i + 1;
    }
    
    return alternatives;
}

// Format seconds into human-readable time string (HH:mm:ss)
string format_eta_time(double seconds) {
    int total_secs = static_cast<int>(seconds + 0.5);
    int hours = total_secs / 3600;
    int minutes = (total_secs % 3600) / 60;
    int secs = total_secs % 60;
    
    stringstream ss;
    if (hours > 0) {
        ss << hours << "h " << setfill('0') << setw(2) << minutes << "m";
    } else if (minutes > 0) {
        ss << minutes << "m " << setfill('0') << setw(2) << secs << "s";
    } else {
        ss << secs << "s";
    }
    
    return ss.str();
}

// Load node GPS coordinates from CSV file
// Load OSM ID to sequential ID mapping from CSV
map<NodeID, NodeID> load_node_id_mapping(const string& filename) {
    map<NodeID, NodeID> mapping;  // osm_id -> sequential_id
    ifstream file(filename);
    
    if (!file.is_open()) {
        cerr << "Warning: Could not open node ID mapping file: " << filename << endl;
        return mapping;
    }
    
    string line;
    getline(file, line); // Skip header
    
    while (getline(file, line)) {
        stringstream ss(line);
        string osm_id_str, seq_id_str;
        
        if (getline(ss, osm_id_str, ',') && getline(ss, seq_id_str, ',')) {
            try {
                NodeID osm_id = stoul(osm_id_str);
                NodeID seq_id = stoul(seq_id_str);
                mapping[osm_id] = seq_id;
            } catch (...) {
                continue;
            }
        }
    }
    
    file.close();
    cerr << "✅ Loaded " << mapping.size() << " node ID mappings" << endl;
    return mapping;
}

// Load node coordinates from CSV
map<NodeID, GPSCoordinate> load_node_coordinates(const string& filename) {
    map<NodeID, GPSCoordinate> coordinates;
    ifstream file(filename);
    
    if (!file.is_open()) {
        cerr << "Warning: Could not open " << filename << endl;
        return coordinates;
    }
    
    string line;
    getline(file, line); // Skip header (node_id,osm_id,latitude,longitude)
    
    while (getline(file, line)) {
        stringstream ss(line);
        string node_id_str, osm_id_str, lat_str, lng_str;
        
        // FIX: Read 4 columns from nodes CSV: node_id,osm_id,latitude,longitude
        if (getline(ss, node_id_str, ',') &&
            getline(ss, osm_id_str, ',') &&
            getline(ss, lat_str, ',') &&
            getline(ss, lng_str, ',')) {
            
            try {
                NodeID node_id = stoul(node_id_str);
                double lat = stod(lat_str);
                double lng = stod(lng_str);
                coordinates[node_id] = GPSCoordinate(lat, lng, node_id);
            } catch (...) {
                continue;
            }
        }
    }
    
    file.close();
    return coordinates;
}

// Parse CSV line with proper handling of quoted fields
vector<string> parse_csv_line(const string& line) {
    vector<string> fields;
    string current_field;
    bool in_quotes = false;
    
    for (size_t i = 0; i < line.length(); i++) {
        char c = line[i];
        
        if (c == '"') {
            in_quotes = !in_quotes;
            current_field += c;
        } else if (c == ',' && !in_quotes) {
            fields.push_back(current_field);
            current_field.clear();
        } else {
            current_field += c;
        }
    }
    
    fields.push_back(current_field);
    return fields;
}

// Load edges from CSV file with one-way road support and geometry
map<NodeID, vector<Neighbor>> load_edges(const string& filename, map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries) {
    map<NodeID, vector<Neighbor>> adj_list;
    ifstream file(filename);
    
    if (!file.is_open()) {
        cerr << "Warning: Could not open " << filename << endl;
        return adj_list;
    }
    
    string line;
    getline(file, line); // Skip header
    
    while (getline(file, line)) {
        vector<string> fields = parse_csv_line(line);
        
        // CSV columns: source,target,osm_source,osm_target,source_lat,source_lon,target_lat,target_lon,length,highway_type,road_name,oneway,geometry
        // UPDATED: Added osm_source and osm_target columns (indices 2-3)
        if (fields.size() < 13) {  // Need at least 13 fields for geometry at index 12
            continue;
        }
        
        try {
            NodeID source = stoul(fields[0]);  // Column 0: source (sequential ID)
            NodeID target = stoul(fields[1]);  // Column 1: target (sequential ID)
            // fields[2] = osm_source (not used in routing)
            // fields[3] = osm_target (not used in routing)
            distance_t length = static_cast<distance_t>(stod(fields[8]));  // Column 8: length
            string oneway_str = fields[11];  // Column 11: oneway (UPDATED from 10)
            string geometry_json = fields[12];  // Column 12: geometry (UPDATED from 11)
            
            // Load road name from column 10 (UPDATED from 6)
            string road_name = "";
            if (fields.size() > 10 && !fields[10].empty()) {
                road_name = fields[10];
                // Trim whitespace
                road_name.erase(0, road_name.find_first_not_of(" \t\n\r"));
                road_name.erase(road_name.find_last_not_of(" \t\n\r") + 1);
            }
            
            // Load highway type from column 9 (UPDATED from 7)
            string highway_type = "road";  // Default
            if (fields.size() > 9 && !fields[9].empty()) {
                highway_type = fields[9];
                // Trim whitespace
                highway_type.erase(0, highway_type.find_first_not_of(" \t\n\r"));
                highway_type.erase(highway_type.find_last_not_of(" \t\n\r") + 1);
            }
            
            // Remove surrounding quotes from geometry JSON if present
            if (!geometry_json.empty() && geometry_json.front() == '"' && geometry_json.back() == '"') {
                geometry_json = geometry_json.substr(1, geometry_json.length() - 2);
            }
            
            // Parse geometry JSON - WITH VALIDATION AND DEBUGGING
            vector<pair<double, double>> coords;
            int parse_error_count = 0;
            int success_count = 0;
            
            if (!geometry_json.empty() && geometry_json != "[]") {
                // Format is: [[lat1, lon1], [lat2, lon2], ...] (CSV stores lat first!)
                // Find all inner coordinate pairs [lat, lon]
                size_t start = 0;
                while ((start = geometry_json.find('[', start)) != string::npos) {
                    // Skip if this is the outer bracket
                    if (start == 0 && geometry_json[start + 1] == '[') {
                        start++;
                        continue;
                    }
                    
                    size_t end = geometry_json.find(']', start);
                    if (end == string::npos) break;
                    
                    string pair_str = geometry_json.substr(start + 1, end - start - 1);
                    
                    // Parse "lat, lon" or "lat,lon" (CSV format has lat first!)
                    size_t comma = pair_str.find(',');
                    if (comma != string::npos) {
                        try {
                            string lat_str = pair_str.substr(0, comma);
                            string lon_str = pair_str.substr(comma + 1);
                            
                            // Trim whitespace
                            lat_str.erase(0, lat_str.find_first_not_of(" \t"));
                            lat_str.erase(lat_str.find_last_not_of(" \t") + 1);
                            lon_str.erase(0, lon_str.find_first_not_of(" \t"));
                            lon_str.erase(lon_str.find_last_not_of(" \t") + 1);
                            
                            double lat = stod(lat_str);
                            double lon = stod(lon_str);
                            
                            // Validate coordinate ranges (reasonable GPS bounds for Philippines)
                            if (lat >= 4.0 && lat <= 20.0 && lon >= 115.0 && lon <= 130.0) {
                                coords.push_back({lon, lat});
                                success_count++;
                            } else {
                                parse_error_count++;
                                cerr << "⚠️  Invalid coordinate range in edge " << source << "→" << target 
                                     << ": lat=" << lat << ", lon=" << lon << endl;
                            }
                        } catch (const exception& e) {
                            parse_error_count++;
                            cerr << "⚠️  Failed to parse coordinate in edge " << source << "→" << target 
                                 << ": [" << pair_str << "] (error: " << e.what() << ")" << endl;
                        }
                    } else {
                        parse_error_count++;
                        cerr << "⚠️  Malformed coordinate pair in edge " << source << "→" << target 
                             << ": [" << pair_str << "]" << endl;
                    }
                    start = end + 1;
                }
                
                if (parse_error_count > 0) {
                    cerr << "   Edge " << source << "→" << target << ": " << success_count 
                         << " valid coordinates, " << parse_error_count << " parse errors" << endl;
                }
            }
            
            EdgeGeometry geom;
            geom.source = source;
            geom.target = target;
            geom.length = length;
            geom.road_name = road_name;
            geom.coords = coords;
            edge_geometries[{source, target}] = geom;
            
            // Parse oneway value
            oneway_str.erase(0, oneway_str.find_first_not_of(" \t\n\r"));
            oneway_str.erase(oneway_str.find_last_not_of(" \t\n\r") + 1);
            
            int oneway = 0;
            try {
                oneway = stoi(oneway_str);
            } catch (...) {
                oneway = 0;
            }
            
            if (oneway == 1) {
                // One-way forward only
                adj_list[source].push_back(Neighbor(target, length));
                g_highway_types[{source, target}] = highway_type;
            } else if (oneway == -1) {
                // One-way reverse only
                adj_list[target].push_back(Neighbor(source, length));
                g_highway_types[{target, source}] = highway_type;
                // Also store reverse geometry
                EdgeGeometry rev_geom = geom;
                rev_geom.source = target;
                rev_geom.target = source;
                rev_geom.road_name = road_name;  // Same road name
                reverse(rev_geom.coords.begin(), rev_geom.coords.end());
                edge_geometries[{target, source}] = rev_geom;
            } else {
                // Bidirectional
                adj_list[source].push_back(Neighbor(target, length));
                adj_list[target].push_back(Neighbor(source, length));
                g_highway_types[{source, target}] = highway_type;
                g_highway_types[{target, source}] = highway_type;
                
                // Store reverse geometry
                EdgeGeometry rev_geom = geom;
                rev_geom.source = target;
                rev_geom.target = source;
                rev_geom.road_name = road_name;  // Same road name
                reverse(rev_geom.coords.begin(), rev_geom.coords.end());
                edge_geometries[{target, source}] = rev_geom;
            }
        } catch (...) {
            continue;
        }
    }
    
    file.close();
    
    // Log statistics about edge geometry
    int edges_with_geometry = 0;
    int edges_without_geometry = 0;
    for (const auto& [edge_key, geom] : edge_geometries) {
        if (geom.coords.empty()) {
            edges_without_geometry++;
        } else {
            edges_with_geometry++;
        }
    }
    cerr << "✓ Loaded edges: " << adj_list.size() << " source nodes with " << edge_geometries.size() 
         << " directed edges" << endl;
    cerr << "  Edges with geometry: " << edges_with_geometry << endl;
    cerr << "  Edges without geometry: " << edges_without_geometry << endl;
    
    return adj_list;
}

// ============================================================
// LAZYHC2L CORE FUNCTIONS
// ============================================================

// Compute impact score for a disruption
// Impact = f(Δw) × f_jam × (1.0 + f_closure)
// where closure_factor=1.0 doubles the impact
double compute_impact_score(double weight_change_ratio, double jam_factor, double closure_factor) {
    // Normalize weight change (0 to 1 scale)
    double f_delta_w = min(1.0, max(0.0, weight_change_ratio));
    
    // Normalize jam factor (already 0-1 scale from HERE API)
    double f_jam = min(1.0, max(0.0, jam_factor));
    
    // Closure multiplier (0 or 1)
    double f_closure = min(1.0, max(0.0, closure_factor));
    
    // Combined impact: base impact multiplied by closure factor
    // Closure doubles the impact
    double impact = f_delta_w * f_jam * (1.0 + f_closure);
    
    // Ensure result is in [0, 1] range
    return min(1.0, impact);
}

// Decide if immediate update should be triggered based on impact and threshold
bool should_immediate_update(double impact_score, double tau_threshold) {
    return impact_score >= tau_threshold;
}

// Mark nodes as dirty for lazy update
// Marks affected edge endpoints and their neighbors
void mark_nodes_dirty(
    NodeID source, NodeID target,
    const map<NodeID, vector<Neighbor>>& adj_list,
    LazyHC2LState& state,
    double impact_score) {
    
    // Mark the edge endpoints as dirty
    state.dirty_labels.insert(source);
    state.dirty_labels.insert(target);
    state.impact_scores[source] = max(state.impact_scores[source], impact_score);
    state.impact_scores[target] = max(state.impact_scores[target], impact_score);
    
    // Mark neighbors of source
    if (adj_list.count(source)) {
        for (const auto& neighbor : adj_list.at(source)) {
            state.dirty_labels.insert(neighbor.node);
            state.impact_scores[neighbor.node] = max(state.impact_scores[neighbor.node], impact_score * 0.5);
        }
    }
    
    // Mark neighbors of target
    if (adj_list.count(target)) {
        for (const auto& neighbor : adj_list.at(target)) {
            state.dirty_labels.insert(neighbor.node);
            state.impact_scores[neighbor.node] = max(state.impact_scores[neighbor.node], impact_score * 0.5);
        }
    }
}

// Lazy repair: check if path intersects dirty nodes
// Returns true if repair was needed, false if cache hit
bool lazy_repair_path(
    const vector<NodeID>& path,
    LazyHC2LState& state,
    double& repair_time_ms,
    int& nodes_repaired) {
    
    repair_time_ms = 0.0;
    nodes_repaired = 0;
    
    // Check if any node in path is dirty
    bool needs_repair = false;
    for (NodeID node : path) {
        if (state.dirty_labels.count(node)) {
            needs_repair = true;
            break;
        }
    }
    
    if (!needs_repair) {
        // Cache hit: no repair needed
        return false;
    }
    
    // Simulate repair time (in real implementation, would rebuild labels)
    auto repair_start = chrono::high_resolution_clock::now();
    
    // Count and clear dirty nodes in path
    for (NodeID node : path) {
        if (state.dirty_labels.count(node)) {
            nodes_repaired++;
            state.dirty_labels.erase(node);
            state.impact_scores.erase(node);
        }
    }
    
    auto repair_end = chrono::high_resolution_clock::now();
    repair_time_ms = chrono::duration<double, milli>(repair_end - repair_start).count();
    
    state.update_count++;
    state.last_update_time = time(nullptr);
    
    return true;
}

// ============================================================
// PATH FINDING
// ============================================================

// ============================================================
// PATH FINDING WITH COMPREHENSIVE COST CALCULATION
// ============================================================

// ENHANCED PATH FINDING: Dijkstra with highway, flow, and incident awareness
// This version considers: GPS distance, highway type, traffic flow, and incidents
vector<NodeID> find_shortest_path(
    NodeID start, NodeID dest, 
    const map<NodeID, vector<Neighbor>>& adj_list,
    const map<NodeID, GPSCoordinate>& coordinates,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<pair<NodeID, NodeID>, IncidentData>& incident_data) {
    
    vector<NodeID> path;
    
    if (start == dest) {
        path.push_back(start);
        return path;
    }
    
    map<NodeID, distance_t> dist;
    map<NodeID, NodeID> pred;
    set<NodeID> visited;
    
    priority_queue<pair<distance_t, NodeID>, 
                   vector<pair<distance_t, NodeID>>,
                   greater<pair<distance_t, NodeID>>> pq;
    
    dist[start] = 0;
    pq.push({0, start});
    
    while (!pq.empty()) {
        auto [d, u] = pq.top();
        pq.pop();
        
        if (visited.count(u)) continue;
        visited.insert(u);
        
        if (u == dest) break;
        
        if (adj_list.count(u)) {
            for (const auto& neighbor : adj_list.at(u)) {
                NodeID v = neighbor.node;
                
                // *** CRITICAL: Use comprehensive cost calculation ***
                // This considers: GPS distance, highway type, flow, incidents
                auto edge_key = make_pair(u, v);
                string highway_type = "road"; // Default
                
                // Get highway type from global map (loaded from CSV for ALL edges)
                if (g_highway_types.count(edge_key)) {
                    highway_type = g_highway_types[edge_key];
                }
                // Fallback to incident data if not in global map
                else if (incident_data.count(edge_key)) {
                    highway_type = incident_data.at(edge_key).highway_type;
                }
                
                // Calculate edge cost with ALL factors
                distance_t edge_cost = calculate_edge_cost(
                    u, v, neighbor.distance, highway_type,
                    flow_data, incident_data, coordinates
                );
                
                distance_t new_dist = dist[u] + edge_cost;
                
                if (!dist.count(v) || new_dist < dist[v]) {
                    dist[v] = new_dist;
                    pred[v] = u;
                    pq.push({new_dist, v});
                }
            }
        }
    }
    
    // Reconstruct path - ENSURE ALL INTERMEDIATE NODES ARE INCLUDED
    // This is critical for sharp turns and road junctions with multiple connections
    if (pred.count(dest) || dest == start) {
        NodeID curr = dest;
        while (curr != start) {
            path.push_back(curr);
            if (!pred.count(curr)) {
                // Path reconstruction failed - node unreachable
                cerr << "⚠️  Warning: Node " << curr << " has no predecessor, path may be incomplete" << endl;
                break;
            }
            curr = pred[curr];
        }
        path.push_back(start);
        reverse(path.begin(), path.end());
    }
    
    // DEBUG: Log the path for verification with cost breakdown
    if (path.size() > 0) {
        cerr << "✓ Path found with " << path.size() << " nodes: ";
        for (size_t i = 0; i < path.size() && i < 10; i++) {
            cerr << path[i];
            if (i < min(size_t(9), path.size() - 1)) cerr << " → ";
        }
        if (path.size() > 10) cerr << " ... (" << (path.size() - 10) << " more nodes)";
        cerr << endl;
        
        // Log cost breakdown for first few edges
        cerr << "   Cost breakdown (first 3 edges):" << endl;
        for (size_t i = 0; i < min(size_t(3), path.size() - 1); i++) {
            auto edge_key = make_pair(path[i], path[i+1]);
            cerr << "     Edge " << path[i] << "→" << path[i+1] << ": ";
            
            if (incident_data.count(edge_key)) {
                const auto& inc = incident_data.at(edge_key);
                cerr << "Highway=" << inc.highway_type << " ";
                if (inc.is_closed) cerr << "[CLOSED] ";
                else cerr << "Type=" << inc.type << " ";
            }
            
            if (flow_data.count(edge_key)) {
                const auto& flow = flow_data.at(edge_key);
                cerr << "Jam=" << flow.jam_factor << " Status=" << flow.flow_status;
            }
            
            cerr << endl;
        }
    }
    
    return path;
}

// Simplified version without disruption data (backward compatibility)
vector<NodeID> find_shortest_path(NodeID start, NodeID dest, const map<NodeID, vector<Neighbor>>& adj_list) {
    // Call enhanced version with empty disruption maps
    static map<NodeID, GPSCoordinate> empty_coords;
    static map<pair<NodeID, NodeID>, TrafficFlowData> empty_flow;
    static map<pair<NodeID, NodeID>, IncidentData> empty_incidents;
    
    return find_shortest_path(start, dest, adj_list, empty_coords, empty_flow, empty_incidents);
}

// Find the position of a snap point along an edge (0.0 to 1.0)
double get_snap_position_on_edge(
    const vector<pair<double, double>>& coords,
    double snap_lat, double snap_lng) {
    
    if (coords.empty()) return 0.0;
    
    double min_dist = numeric_limits<double>::max();
    size_t closest_idx = 0;
    
    for (size_t i = 0; i < coords.size(); i++) {
        double dist = haversine_distance(snap_lat, snap_lng, coords[i].second, coords[i].first);
        if (dist < min_dist) {
            min_dist = dist;
            closest_idx = i;
        }
    }
    
    // Return normalized position (0.0 at start, 1.0 at end)
    return static_cast<double>(closest_idx) / max(static_cast<double>(coords.size() - 1), 1.0);
}

// Clip geometry at snap point - STRICTLY use snap coordinates as endpoints
vector<pair<double, double>> clip_geometry_at_snap(
    const vector<pair<double, double>>& coords,
    double snap_lat, double snap_lng,
    bool clip_start) {
    
    if (coords.empty()) return coords;
    
    // Find closest point on geometry to snap
    double min_dist = numeric_limits<double>::max();
    size_t closest_idx = 0;
    
    for (size_t i = 0; i < coords.size(); i++) {
        double dist = haversine_distance(snap_lat, snap_lng, coords[i].second, coords[i].first);
        if (dist < min_dist) {
            min_dist = dist;
            closest_idx = i;
        }
    }
    
    vector<pair<double, double>> clipped;
    
    if (clip_start) {
        // STRICTLY start at snap point, then keep rest of geometry
        clipped.push_back({snap_lng, snap_lat});
        for (size_t i = closest_idx + 1; i < coords.size(); i++) {
            clipped.push_back(coords[i]);
        }
    } else {
        // Keep geometry up to closest point, then STRICTLY end at snap point
        for (size_t i = 0; i < closest_idx; i++) {
            clipped.push_back(coords[i]);
        }
        clipped.push_back({snap_lng, snap_lat});
    }
    
    // Ensure we always have at least the snap point
    if (clipped.empty()) {
        clipped.push_back({snap_lng, snap_lat});
    }
    
    return clipped;
}

// Clip geometry between two snap points on the same edge
vector<pair<double, double>> clip_geometry_between_snaps(
    const vector<pair<double, double>>& coords,
    double start_snap_lat, double start_snap_lng,
    double dest_snap_lat, double dest_snap_lng) {
    
    if (coords.empty()) {
        return {{start_snap_lng, start_snap_lat}, {dest_snap_lng, dest_snap_lat}};
    }
    
    // Find closest points for both snaps
    size_t start_idx = 0, dest_idx = 0;
    double min_start_dist = numeric_limits<double>::max();
    double min_dest_dist = numeric_limits<double>::max();
    
    for (size_t i = 0; i < coords.size(); i++) {
        double start_dist = haversine_distance(start_snap_lat, start_snap_lng, coords[i].second, coords[i].first);
        double dest_dist = haversine_distance(dest_snap_lat, dest_snap_lng, coords[i].second, coords[i].first);
        
        if (start_dist < min_start_dist) {
            min_start_dist = start_dist;
            start_idx = i;
        }
        if (dest_dist < min_dest_dist) {
            min_dest_dist = dest_dist;
            dest_idx = i;
        }
    }
    
    vector<pair<double, double>> clipped;
    clipped.push_back({start_snap_lng, start_snap_lat});
    
    // Add intermediate points
    if (start_idx < dest_idx) {
        for (size_t i = start_idx + 1; i < dest_idx; i++) {
            clipped.push_back(coords[i]);
        }
    } else if (dest_idx < start_idx) {
        for (size_t i = start_idx; i > dest_idx; i--) {
            if (i < coords.size()) {
                clipped.push_back(coords[i]);
            }
        }
    }
    
    clipped.push_back({dest_snap_lng, dest_snap_lat});
    
    return clipped;
}

// Output JSON response
void output_json_response(bool success, const string& error_message = "",
                         NodeID start_node = 0, NodeID dest_node = 0,
                         double start_pin_lat = 0, double start_pin_lng = 0,
                         double start_snap_lat = 0, double start_snap_lng = 0,
                         double dest_pin_lat = 0, double dest_pin_lng = 0,
                         double dest_snap_lat = 0, double dest_snap_lng = 0,
                         NodeID start_edge_source = 0, NodeID start_edge_target = 0, int start_edge_oneway = 0,
                         NodeID dest_edge_source = 0, NodeID dest_edge_target = 0, int dest_edge_oneway = 0,
                         distance_t distance = 0, double query_time_ms = 0,
                         const vector<NodeID>& path = vector<NodeID>(),
                         const map<NodeID, GPSCoordinate>& coordinates = map<NodeID, GPSCoordinate>(),
                         const map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries = map<pair<NodeID, NodeID>, EdgeGeometry>(),
                         bool use_disruptions = false, const string& disruption_dir = "",
                         const ContractionIndex* ci = nullptr, double index_load_time_ms = 0.0,
                         double tau_threshold = 0.5,
                         const LazyHC2LState* lazy_state = nullptr,
                         double disruption_impact_score = 0.0,
                         const string& update_strategy = "",
                         const string& lazy_reason = "",
                         int dirty_nodes_on_path = 0,
                         double lazy_repair_time_ms = 0.0,
                         int nodes_repaired = 0,
                         bool cache_hit = false,
                         const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data = map<pair<NodeID, NodeID>, TrafficFlowData>(),
                         const vector<AlternativeRoute>& alternatives = vector<AlternativeRoute>()) {
    
    cout << "{" << endl;
    cout << "  \"success\": " << (success ? "true" : "false") << "," << endl;
    
    if (!success) {
        cout << "  \"error\": \"" << error_message << "\"" << endl;
    } else {
        cout << "  \"algorithm\": \"HC2L (Hierarchical Cut 2-Hop Labelling)\"," << endl;
        cout << "  \"input\": {" << endl;
        cout << "    \"start_pin_lat\": " << fixed << setprecision(6) << start_pin_lat << "," << endl;
        cout << "    \"start_pin_lng\": " << fixed << setprecision(6) << start_pin_lng << "," << endl;
        cout << "    \"start_snap_lat\": " << fixed << setprecision(6) << start_snap_lat << "," << endl;
        cout << "    \"start_snap_lng\": " << fixed << setprecision(6) << start_snap_lng << "," << endl;
        cout << "    \"dest_pin_lat\": " << fixed << setprecision(6) << dest_pin_lat << "," << endl;
        cout << "    \"dest_pin_lng\": " << fixed << setprecision(6) << dest_pin_lng << "," << endl;
        cout << "    \"dest_snap_lat\": " << fixed << setprecision(6) << dest_snap_lat << "," << endl;
        cout << "    \"dest_snap_lng\": " << fixed << setprecision(6) << dest_snap_lng << "," << endl;
        cout << "    \"disruption_dir\": \"" << disruption_dir << "\"," << endl;
        cout << "    \"use_disruptions\": " << (use_disruptions ? "true" : "false") << endl;
        cout << "  }," << endl;
        
        cout << "  \"snap_edges\": {" << endl;
        cout << "    \"start_edge\": {" << endl;
        cout << "      \"source\": " << start_edge_source << "," << endl;
        cout << "      \"target\": " << start_edge_target << "," << endl;
        cout << "      \"oneway\": " << start_edge_oneway << endl;
        cout << "    }," << endl;
        cout << "    \"dest_edge\": {" << endl;
        cout << "      \"source\": " << dest_edge_source << "," << endl;
        cout << "      \"target\": " << dest_edge_target << "," << endl;
        cout << "      \"oneway\": " << dest_edge_oneway << endl;
        cout << "    }" << endl;
        cout << "  }," << endl;
        
        cout << "  \"gps_mapping\": {" << endl;
        cout << "    \"start_node\": " << start_node << "," << endl;
        cout << "    \"dest_node\": " << dest_node;
        
        if (coordinates.count(start_node)) {
            cout << "," << endl;
            auto& coord = coordinates.at(start_node);
            cout << "    \"start_node_lat\": " << fixed << setprecision(6) << coord.latitude << "," << endl;
            cout << "    \"start_node_lng\": " << fixed << setprecision(6) << coord.longitude;
        }
        
        if (coordinates.count(dest_node)) {
            cout << "," << endl;
            auto& coord = coordinates.at(dest_node);
            cout << "    \"dest_node_lat\": " << fixed << setprecision(6) << coord.latitude << "," << endl;
            cout << "    \"dest_node_lng\": " << fixed << setprecision(6) << coord.longitude;
        }
        
        cout << endl << "  }," << endl;
        
        cout << "  \"metrics\": {" << endl;
        cout << "    \"total_distance_units\": " << distance << "," << endl;
        cout << "    \"total_distance_meters\": " << distance << "," << endl;
        cout << "    \"query_time_ms\": " << fixed << setprecision(3) << query_time_ms << "," << endl;
        cout << "    \"path_length\": " << path.size() << "," << endl;
        cout << "    \"uses_disruptions\": " << (use_disruptions ? "true" : "false") << "," << endl;
        cout << "    \"interpolation_used\": false," << endl;
        
        // Calculate and add distance and ETA metrics using ACTUAL traffic data
        double calculated_distance = calculate_route_distance(path, coordinates);
        
        // CRITICAL FIX: Use actual traffic speeds from flow_data instead of jam_factor estimate
        double eta_seconds = calculate_eta_with_flow(path, flow_data, coordinates);
        string eta_formatted = format_eta_time(eta_seconds);
        
        cout << "    \"calculated_distance_meters\": " << fixed << setprecision(1) << calculated_distance << "," << endl;
        cout << "    \"calculated_distance_km\": " << fixed << setprecision(2) << (calculated_distance / 1000.0) << "," << endl;
        cout << "    \"eta_seconds\": " << fixed << setprecision(0) << eta_seconds << "," << endl;
        cout << "    \"eta_formatted\": \"" << eta_formatted << "\"," << endl;
        
        // Add HC2L labeling information
        if (ci != nullptr) {
            size_t label_count = ci->label_count();
            size_t inf_label_count = ci->inf_label_count();
            size_t index_size = ci->size();
            size_t height = ci->height();
            size_t max_label_count = ci->max_label_count();
            size_t max_cut_size = ci->max_cut_size();
            size_t non_empty_cuts = ci->non_empty_cuts();
            double avg_cut_size = ci->avg_cut_size();
            
            cout << "    \"labeling_info\": {" << endl;
            cout << "      \"total_labels\": " << label_count << "," << endl;
            cout << "      \"infinite_labels\": " << inf_label_count << "," << endl;
            cout << "      \"index_size_bytes\": " << index_size << "," << endl;
            cout << "      \"index_size_mb\": " << fixed << setprecision(2) << (index_size / (1024.0 * 1024.0)) << "," << endl;
            cout << "      \"hierarchy_height\": " << height << "," << endl;
            cout << "      \"max_label_count_per_node\": " << max_label_count << "," << endl;
            cout << "      \"max_cut_size\": " << max_cut_size << "," << endl;
            cout << "      \"average_cut_size\": " << fixed << setprecision(2) << avg_cut_size << "," << endl;
            cout << "      \"non_empty_cuts\": " << non_empty_cuts << "," << endl;
            cout << "      \"index_load_time_ms\": " << fixed << setprecision(3) << index_load_time_ms << endl;
            cout << "    }" << endl;
        } else {
            cout << "    \"labeling_info\": {" << endl;
            cout << "      \"note\": \"Index data unavailable\"" << endl;
            cout << "    }" << endl;
        }
        cout << "  }," << endl;
        
        // LazyHC2L diagnostics section
        cout << "  \"disruption_config\": {" << endl;
        cout << "    \"use_disruptions\": " << (use_disruptions ? "true" : "false") << "," << endl;
        cout << "    \"disruption_file\": \"" << disruption_dir << "\"," << endl;
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << "," << endl;
        cout << "    \"tau_used_for\": \"Threshold triggers immediate update if ImpactScore >= tau\"" << endl;
        cout << "  }," << endl;
        
        cout << "  \"lazy_hc2l\": {" << endl;
        cout << "    \"enabled\": " << (use_disruptions ? "true" : "false") << "," << endl;
        cout << "    \"disruption_impact_score\": " << fixed << setprecision(3) << disruption_impact_score << "," << endl;
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << "," << endl;
        cout << "    \"update_strategy\": \"" << update_strategy << "\"," << endl;
        cout << "    \"reason\": \"" << lazy_reason << "\"," << endl;
        
        if (lazy_state != nullptr) {
            cout << "    \"dirty_nodes_marked\": " << lazy_state->dirty_labels.size() << "," << endl;
            cout << "    \"total_updates\": " << lazy_state->update_count << "," << endl;
        } else {
            cout << "    \"dirty_nodes_marked\": 0," << endl;
            cout << "    \"total_updates\": 0," << endl;
        }
        
        cout << "    \"dirty_nodes_affected_path\": " << dirty_nodes_on_path << "," << endl;
        cout << "    \"lazy_repair_time_ms\": " << fixed << setprecision(3) << lazy_repair_time_ms << "," << endl;
        cout << "    \"nodes_repaired\": " << nodes_repaired << "," << endl;
        cout << "    \"cache_hit\": " << (cache_hit ? "true" : "false") << endl;
        cout << "  }," << endl;
        
        cout << "  \"route\": {" << endl;
        cout << "    \"path_nodes\": [";
        for (size_t i = 0; i < path.size(); i++) {
            cout << path[i];
            if (i < path.size() - 1) cout << ", ";
        }
        cout << "]," << endl;
        
        // DEBUG INFO: Log path with coordinates for sharp turn detection
        cerr << "📍 Complete path with " << path.size() << " nodes:" << endl;
        for (size_t i = 0; i < path.size(); i++) {
            NodeID node = path[i];
            cerr << "  [" << i << "] Node " << node;
            if (coordinates.count(node)) {
                auto& coord = coordinates.at(node);
                cerr << " @ (" << fixed << setprecision(6) << coord.latitude << ", " << coord.longitude << ")";
            } else {
                cerr << " (⚠️  NO COORDINATES)";
            }
            cerr << endl;
        }
        
        cout << "    \"complete_trace\": \"HC2L Route (";
        for (size_t i = 0; i < path.size(); i++) {
            NodeID node = path[i];
            cout << node;
            
            if (coordinates.count(node)) {
                cout << " @ " << fixed << setprecision(6) 
                     << coordinates.at(node).latitude << "," 
                     << coordinates.at(node).longitude;
            }
            
            if (i < path.size() - 1) cout << " → ";
        }
        cout << ")\"," << endl;
        
        // Output geometry with clipping
        cout << "    \"geometry\": [" << endl;
        
        bool same_edge = (start_edge_source == dest_edge_source && start_edge_target == dest_edge_target) ||
                         (start_edge_source == dest_edge_target && start_edge_target == dest_edge_source);
        
        bool can_meet_on_same_edge = false;
        
        if (same_edge) {
            // Recalculate for geometry output
            auto edge_key = make_pair(start_edge_source, start_edge_target);
            if (edge_geometries.count(edge_key)) {
                const auto& geom = edge_geometries.at(edge_key).coords;
                
                double start_pos = get_snap_position_on_edge(geom, start_snap_lat, start_snap_lng);
                double dest_pos = get_snap_position_on_edge(geom, dest_snap_lat, dest_snap_lng);
                
                if (start_edge_oneway == 1) {
                    can_meet_on_same_edge = (start_pos <= dest_pos);
                } else if (start_edge_oneway == -1) {
                    can_meet_on_same_edge = (start_pos >= dest_pos);
                } else {
                    can_meet_on_same_edge = true;
                }
            } else {
                can_meet_on_same_edge = (path.size() == 2);
            }
        }
        
        // For same edge that cannot meet, add virtual start snap segment with actual edge geometry
        if (same_edge && !can_meet_on_same_edge && path.size() > 0) {
            NodeID first_path_node = path[0];
            cout << "      {" << endl;
            cout << "        \"from\": \"VIRTUAL_START\"," << endl;
            cout << "        \"to\": " << first_path_node << "," << endl;
            cout << "        \"coordinates\": [";
            
            // Get geometry from the snap edge and clip from snap point to first_path_node
            auto start_edge_key = make_pair(start_edge_source, start_edge_target);
            if (edge_geometries.count(start_edge_key)) {
                vector<pair<double, double>> snap_edge_coords = edge_geometries.at(start_edge_key).coords;
                // Clip from start snap point towards the direction of first_path_node
                vector<pair<double, double>> clipped_coords = clip_geometry_at_snap(snap_edge_coords, start_snap_lat, start_snap_lng, true);
                
                // Output clipped geometry
                for (size_t j = 0; j < clipped_coords.size(); j++) {
                    cout << "[" << fixed << setprecision(6) 
                         << clipped_coords[j].first << ", " 
                         << clipped_coords[j].second << "]";
                    if (j < clipped_coords.size() - 1) cout << ", ";
                }
            } else {
                // Fallback to straight line
                cout << "[" << fixed << setprecision(6) << start_snap_lng << ", " << start_snap_lat << "]";
                if (coordinates.count(first_path_node)) {
                    cout << ", [" << fixed << setprecision(6) 
                         << coordinates.at(first_path_node).longitude << ", " 
                         << coordinates.at(first_path_node).latitude << "]";
                }
            }
            cout << "]," << endl;
            cout << "        \"color\": \"#3b82f6\"," << endl;
            cout << "        \"flow_status\": \"default\"," << endl;
            cout << "        \"jam_factor\": 0.0," << endl;
            cout << "        \"speed_kmh\": 0.0," << endl;
            cout << "        \"speed_reduction\": 0.0" << endl;
            cout << "      }," << endl;
        }
        
        size_t edge_loop_end = can_meet_on_same_edge ? 1 : path.size() - 1;
        
        for (size_t i = 0; i < edge_loop_end; i++) {
            NodeID from = path[i];
            NodeID to = path[i + 1];
            
            bool is_first_edge = (i == 0);
            bool is_last_edge = (i == path.size() - 2) && !can_meet_on_same_edge;
            
            cout << "      {" << endl;
            cout << "        \"from\": " << from << "," << endl;
            cout << "        \"to\": " << to << "," << endl;
            
            auto edge_key = make_pair(from, to);
            
            // 1. Get road name for this edge
            string road_name = "";
            if (edge_geometries.count(edge_key)) {
                road_name = edge_geometries.at(edge_key).road_name;
            }
            
            // 2. Get highway type for this edge
            string edge_highway_type = "unknown";
            if (g_highway_types.count(edge_key)) {
                edge_highway_type = g_highway_types.at(edge_key);
            }
            
            // 3. Get edge length (actual GPS distance)
            double edge_distance = 0.0;
            if (edge_geometries.count(edge_key)) {
                edge_distance = edge_geometries.at(edge_key).length;
            }
            
            // 4. Get free-flow speed for this highway type
            double free_flow_speed = get_highway_speed(edge_highway_type);
            
            // 4. Check if edge is closed due to incident
            bool is_closed = false;
            string incident_type = "none";
            double incident_confidence = 0.0;
            if (g_disruption_cache.incidents.count(edge_key)) {
                const auto& incident = g_disruption_cache.incidents.at(edge_key);
                is_closed = (incident.is_closed == 1);
                incident_type = incident.type;
                incident_confidence = incident.confidence;
            }
            
            // 5. Add flow/traffic information for this edge
            if (flow_data.count(edge_key)) {
                const TrafficFlowData& flow = flow_data.at(edge_key);
                cout << "        \"color\": \"" << flow.color_code << "\"," << endl;
                cout << "        \"flow_status\": \"" << flow.flow_status << "\"," << endl;
                cout << "        \"jam_factor\": " << fixed << setprecision(2) << sanitize_json_number(flow.jam_factor) << "," << endl;
                cout << "        \"speed_kmh\": " << fixed << setprecision(1) << sanitize_json_number(flow.current_speed) << "," << endl;
                cout << "        \"speed_reduction\": " << fixed << setprecision(3) << sanitize_json_number(flow.speed_reduction) << "," << endl;
            } else {
                // Default values when no flow data available - HC2L default color (blue)
                cout << "        \"color\": \"#3b82f6\"," << endl;
                cout << "        \"flow_status\": \"default\"," << endl;
                cout << "        \"jam_factor\": 0.0," << endl;
                cout << "        \"speed_kmh\": " << fixed << setprecision(1) << sanitize_json_number(free_flow_speed) << "," << endl;
                cout << "        \"speed_reduction\": 0.0," << endl;
            }
            
            cout << "        \"coordinates\": [";
            
            vector<pair<double, double>> coords_to_output;
            
            if (edge_geometries.count(edge_key)) {
                coords_to_output = edge_geometries.at(edge_key).coords;
                
                // Clip at snap points
                if (same_edge && can_meet_on_same_edge) {
                    // Clip both ends - use the new function for same-edge clipping
                    coords_to_output = clip_geometry_between_snaps(coords_to_output, 
                                                                   start_snap_lat, start_snap_lng,
                                                                   dest_snap_lat, dest_snap_lng);
                } else if (is_first_edge && !(same_edge && !can_meet_on_same_edge)) {
                    coords_to_output = clip_geometry_at_snap(coords_to_output, start_snap_lat, start_snap_lng, true);
                } else if (is_last_edge && !(same_edge && !can_meet_on_same_edge)) {
                    coords_to_output = clip_geometry_at_snap(coords_to_output, dest_snap_lat, dest_snap_lng, false);
                }
            }
            
            // Output coordinates
            if (!coords_to_output.empty()) {
                for (size_t j = 0; j < coords_to_output.size(); j++) {
                    cout << "[" << fixed << setprecision(6) 
                         << coords_to_output[j].first << ", " 
                         << coords_to_output[j].second << "]";
                    if (j < coords_to_output.size() - 1) cout << ", ";
                }
            } else {
                // Fallback: use node coordinates
                if (coordinates.count(from) && coordinates.count(to)) {
                    cout << "[" << fixed << setprecision(6) 
                         << coordinates.at(from).longitude << ", " 
                         << coordinates.at(from).latitude << "], ";
                    cout << "[" << fixed << setprecision(6) 
                         << coordinates.at(to).longitude << ", " 
                         << coordinates.at(to).latitude << "]";
                }
            }
            
            cout << "]," << endl;
            
            // 6. Add detailed edge metadata (7 fields total)
            cout << "        \"road_name\": \"" << escape_json_string(road_name) << "\"," << endl;
            cout << "        \"distance_meters\": " << fixed << setprecision(1) << edge_distance << "," << endl;
            cout << "        \"highway_type\": \"" << edge_highway_type << "\"," << endl;
            cout << "        \"free_flow_speed_kmh\": " << fixed << setprecision(1) << free_flow_speed << "," << endl;
            cout << "        \"is_closed\": " << (is_closed ? "true" : "false") << "," << endl;
            cout << "        \"incident_type\": \"" << incident_type << "\"," << endl;
            cout << "        \"incident_confidence\": " << fixed << setprecision(2) << incident_confidence << endl;
            
            cout << "      }";
            if (i < edge_loop_end - 1 || (same_edge && !can_meet_on_same_edge)) cout << ",";
            cout << endl;
        }
        
        // For same edge that cannot meet, add virtual dest snap segment with actual edge geometry
        if (same_edge && !can_meet_on_same_edge && path.size() > 0) {
            NodeID last_path_node = path[path.size() - 1];
            cout << "      {" << endl;
            cout << "        \"from\": " << last_path_node << "," << endl;
            cout << "        \"to\": \"VIRTUAL_DEST\"," << endl;
            cout << "        \"coordinates\": [";
            
            // Get geometry from the snap edge and clip from last_path_node to dest snap point
            auto dest_edge_key = make_pair(dest_edge_source, dest_edge_target);
            if (edge_geometries.count(dest_edge_key)) {
                vector<pair<double, double>> snap_edge_coords = edge_geometries.at(dest_edge_key).coords;
                // Clip from beginning to dest snap point
                vector<pair<double, double>> clipped_coords = clip_geometry_at_snap(snap_edge_coords, dest_snap_lat, dest_snap_lng, false);
                
                // Output clipped geometry
                for (size_t j = 0; j < clipped_coords.size(); j++) {
                    cout << "[" << fixed << setprecision(6) 
                         << clipped_coords[j].first << ", " 
                         << clipped_coords[j].second << "]";
                    if (j < clipped_coords.size() - 1) cout << ", ";
                }
            } else {
                // Fallback to straight line
                if (coordinates.count(last_path_node)) {
                    cout << "[" << fixed << setprecision(6) 
                         << coordinates.at(last_path_node).longitude << ", " 
                         << coordinates.at(last_path_node).latitude << "], ";
                }
                cout << "[" << fixed << setprecision(6) << dest_snap_lng << ", " << dest_snap_lat << "]";
            }
            cout << "]," << endl;
            cout << "        \"color\": \"#3b82f6\"," << endl;
            cout << "        \"flow_status\": \"default\"," << endl;
            cout << "        \"jam_factor\": 0.0," << endl;
            cout << "        \"speed_kmh\": 0.0," << endl;
            cout << "        \"speed_reduction\": 0.0" << endl;
            cout << "      }" << endl;
        }
        
        cout << "    ]" << endl;
        
        cout << "  }," << endl;
        
        // Alternative routes section
        cout << "  \"alternative_routes\": [" << endl;
        for (size_t alt_idx = 0; alt_idx < alternatives.size(); alt_idx++) {
            const AlternativeRoute& alt = alternatives[alt_idx];
            
            cout << "    {" << endl;
            cout << "      \"rank\": " << alt.rank << "," << endl;
            cout << "      \"description\": \"" << alt.description << "\"," << endl;
            cout << "      \"distance_meters\": " << fixed << setprecision(1) << alt.distance << "," << endl;
            cout << "      \"eta_seconds\": " << fixed << setprecision(0) << alt.eta_seconds << "," << endl;
            cout << "      \"eta_formatted\": \"" << format_eta_time(alt.eta_seconds) << "\"," << endl;
            cout << "      \"avg_jam_factor\": " << fixed << setprecision(2) << alt.avg_jam_factor << "," << endl;
            cout << "      \"path_length\": " << alt.path.size() << "," << endl;
            cout << "      \"path_nodes\": [";
            for (size_t j = 0; j < alt.path.size(); j++) {
                cout << alt.path[j];
                if (j < alt.path.size() - 1) cout << ", ";
            }
            cout << "]" << endl;
            cout << "    }";
            if (alt_idx < alternatives.size() - 1) cout << ",";
            cout << endl;
        }
        cout << "  ]" << endl;
    }
    
    cout << "}" << endl;
}

int main(int argc, char* argv[]) {
    // Optimize I/O for large JSON output
    setup_fast_io();
    
    // Accept 18 args (no disruption) or 19 args (with disruption file) or 20 args (with disruption + tau)
    // Args: 14 routing params + 3 data files + optional disruption_file + optional tau_threshold
    if (argc != 18 && argc != 19 && argc != 20) {
        output_json_response(false, "Invalid arguments. Usage: hc2l_routing_api <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> <start_edge_source> <start_edge_target> <start_edge_oneway> <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> <dest_edge_source> <dest_edge_target> <dest_edge_oneway> <nodes_csv> <edges_csv> <index_file> [disruption_file] [tau_threshold]");
        return 1;
    }
    
    try {
        // Parse arguments (14 routing parameters)
        double start_pin_lat = stod(argv[1]);
        double start_pin_lng = stod(argv[2]);
        double start_snap_lat = stod(argv[3]);
        double start_snap_lng = stod(argv[4]);
        NodeID start_edge_source = stoul(argv[5]);
        NodeID start_edge_target = stoul(argv[6]);
        int start_edge_oneway = stoi(argv[7]);
        
        double dest_pin_lat = stod(argv[8]);
        double dest_pin_lng = stod(argv[9]);
        double dest_snap_lat = stod(argv[10]);
        double dest_snap_lng = stod(argv[11]);
        NodeID dest_edge_source = stoul(argv[12]);
        NodeID dest_edge_target = stoul(argv[13]);
        int dest_edge_oneway = stoi(argv[14]);
        
        // Parse data file paths (3 parameters)
        string nodes_csv = argv[15];
        string edges_csv = argv[16];
        string index_file = argv[17];
        
        // Derive node ID mapping file path from nodes_csv path
        // nodes_csv is like "/path/to/data/raw/quezon_city_nodes.csv"
        // mapping file is "/path/to/data/raw/node_id_mapping.csv"
        string mapping_file = nodes_csv.substr(0, nodes_csv.find_last_of('/') + 1) + "node_id_mapping.csv";
        
        // Parse optional disruption file (arg 18)
        string disruption_file = "";
        bool use_disruptions = false;
        if (argc >= 19) {
            disruption_file = argv[18];
            use_disruptions = !disruption_file.empty() && 
                             disruption_file != "null" && 
                             disruption_file != "NULL" &&
                             disruption_file != "";
        }
        
        // Parse optional tau threshold (arg 19)
        double tau_threshold = 0.5; // Default
        if (argc >= 20) {
            tau_threshold = stod(argv[19]);
        }
        
        // Initialize LazyHC2L state
        LazyHC2LState lazy_state;
        double disruption_impact_score = 0.0;
        string update_strategy = "none";
        string lazy_reason = "No disruptions loaded";
        int dirty_nodes_on_path = 0;
        double lazy_repair_time_ms = 0.0;
        int nodes_repaired = 0;
        bool cache_hit = false;
        
        // Load node ID mapping (OSM ID -> Sequential ID)
        cerr << "📋 Loading node ID mapping from: " << mapping_file << endl;
        auto osm_to_seq = load_node_id_mapping(mapping_file);
        if (osm_to_seq.empty()) {
            output_json_response(false, "Failed to load node ID mapping");
            return 1;
        }
        
        // Create reverse mapping (Sequential ID -> OSM ID)
        map<NodeID, NodeID> seq_to_osm;
        for (const auto& [osm, seq] : osm_to_seq) {
            seq_to_osm[seq] = osm;
        }
        
        // Load data
        auto coordinates = load_node_coordinates(nodes_csv);
        if (coordinates.empty()) {
            output_json_response(false, "Failed to load node coordinates");
            return 1;
        }
        
        map<pair<NodeID, NodeID>, EdgeGeometry> edge_geometries;
        auto adj_list = load_edges(edges_csv, edge_geometries);
        if (adj_list.empty()) {
            output_json_response(false, "Failed to load edges");
            return 1;
        }
        
        // Load HC2L index
        auto index_load_start = chrono::high_resolution_clock::now();
        ifstream index_stream(index_file, ios::binary);
        if (!index_stream.is_open()) {
            output_json_response(false, "Failed to open index file");
            return 1;
        }
        cerr << "📚 Loading HC2L index..." << endl;
        ContractionIndex ci(index_stream);
        index_stream.close();
        auto index_load_end = chrono::high_resolution_clock::now();
        double index_load_time_ms = chrono::duration<double, milli>(index_load_end - index_load_start).count();
        cerr << "✅ HC2L index loaded in " << index_load_time_ms << "ms" << endl;
        
        // ============================================================
        // LAZYHC2L: Process disruptions and flow data if provided
        // ============================================================
        cerr << "🔧 Initializing LazyHC2L state..." << endl;
        map<pair<NodeID, NodeID>, TrafficFlowData> flow_data;
        map<pair<NodeID, NodeID>, IncidentData> incident_data;
        cerr << "✅ LazyHC2L state initialized" << endl;
        
        if (use_disruptions) {
            cerr << "🔧 Processing disruptions from: " << disruption_file << endl;
            cerr << "   Tau threshold: " << tau_threshold << endl;
            
            // *** USE CACHED DISRUPTION LOADER ***
            bool load_success = load_disruptions_with_cache(
                disruption_file, incident_data, flow_data, adj_list, edge_geometries
            );
            
            if (!load_success) {
                cerr << "⚠️  Failed to load disruptions" << endl;
                use_disruptions = false;
            } else {
                // Process incidents: update graph and mark dirty nodes
                int disruption_count = 0;
                int closed_roads_count = 0;
                
                for (const auto& [edge_key, incident] : incident_data) {
                    NodeID source = edge_key.first;
                    NodeID target = edge_key.second;
                    
                    // Handle road closures: remove edge from graph
                    if (incident.is_closed || incident.new_weight >= 999999.0) {
                        cerr << "   🚧 Road CLOSED: Edge " << source << "->" << target 
                             << " (Type: " << incident.type << ", Highway: " << incident.highway_type << ")" << endl;
                        closed_roads_count++;
                        
                        // Remove edge from adjacency list to make it unreachable
                        if (adj_list.count(source)) {
                            auto& neighbors = adj_list[source];
                            neighbors.erase(
                                remove_if(neighbors.begin(), neighbors.end(),
                                         [target](const Neighbor& n) { return n.node == target; }),
                                neighbors.end()
                            );
                        }
                        
                        disruption_impact_score = 1.0; // Maximum impact for closures
                    } else {
                        // Active disruption - decide update strategy
                        double final_impact = incident.impact_score;
                        disruption_impact_score = max(disruption_impact_score, final_impact);
                        
                        // Get flow data for logging
                        double jam_factor_val = 5.0;
                        if (flow_data.count(edge_key)) {
                            jam_factor_val = flow_data.at(edge_key).jam_factor;
                        }
                        
                        // Decide update strategy based on impact and threshold
                        if (should_immediate_update(final_impact, tau_threshold)) {
                            update_strategy = "immediate_update";
                            lazy_reason = "ImpactScore >= tau: " + 
                                         to_string(final_impact) + " >= " + to_string(tau_threshold);
                            cerr << "   ⚡ Immediate update for edge " << source << "->" << target 
                                 << " (Impact=" << final_impact << ", Jam=" << jam_factor_val 
                                 << ", Highway=" << incident.highway_type << ", Type=" << incident.type << ")" << endl;
                            
                            // Update edge weight in adj_list
                            if (adj_list.count(source)) {
                                for (auto& neighbor : adj_list[source]) {
                                    if (neighbor.node == target) {
                                        neighbor.distance = incident.new_weight;
                                        break;
                                    }
                                }
                            }
                            // In real implementation: rebuild labels here
                        } else {
                            if (update_strategy != "immediate_update") {
                                update_strategy = "lazy_mark";
                                lazy_reason = "ImpactScore < tau: " + 
                                             to_string(final_impact) + " < " + to_string(tau_threshold);
                            }
                            mark_nodes_dirty(source, target, adj_list, lazy_state, final_impact);
                            cerr << "   💤 Lazy mark for edge " << source << "->" << target 
                                 << " (Impact=" << final_impact << ", Jam=" << jam_factor_val 
                                 << ", Highway=" << incident.highway_type << ", Type=" << incident.type << ")" << endl;
                        }
                    }
                    
                    disruption_count++;
                }
                
                cerr << "✅ Processed " << disruption_count << " disruptions with caching" << endl;
                cerr << "   - Closed roads: " << closed_roads_count << endl;
                cerr << "   - Active disruptions: " << (disruption_count - closed_roads_count) << endl;
                cerr << "   - Strategy: " << update_strategy << endl;
                cerr << "   - Dirty nodes: " << lazy_state.dirty_labels.size() << endl;
                cerr << "   - Flow segments: " << flow_data.size() << endl;
            }
        }
        
        // Determine routing endpoints based on one-way constraints
        cerr << "🎯 Determining routing endpoints..." << endl;
        vector<NodeID> start_candidates_osm, dest_candidates_osm;
        
        // Start edge candidates (OSM IDs)
        if (start_edge_oneway == 1) {
            start_candidates_osm.push_back(start_edge_target); // Exit from target
        } else if (start_edge_oneway == -1) {
            start_candidates_osm.push_back(start_edge_source); // Exit from source
        } else {
            start_candidates_osm.push_back(start_edge_source);
            start_candidates_osm.push_back(start_edge_target);
        }
        
        // Dest edge candidates (OSM IDs)
        if (dest_edge_oneway == 1) {
            dest_candidates_osm.push_back(dest_edge_source); // Arrive at source
        } else if (dest_edge_oneway == -1) {
            dest_candidates_osm.push_back(dest_edge_target); // Arrive at target
        } else {
            dest_candidates_osm.push_back(dest_edge_source);
            dest_candidates_osm.push_back(dest_edge_target);
        }
        
        cerr << "  Start candidates (Sequential IDs passed directly): ";
        for (NodeID s : start_candidates_osm) cerr << s << " ";
        cerr << endl;
        cerr << "  Dest candidates (Sequential IDs passed directly): ";
        for (NodeID d : dest_candidates_osm) cerr << d << " ";
        cerr << endl;
        
        // Input IDs are already sequential IDs (not OSM IDs anymore)
        // Just use them directly without conversion
        vector<NodeID> start_candidates = start_candidates_osm;
        vector<NodeID> dest_candidates = dest_candidates_osm;
        
        if (start_candidates.empty() || dest_candidates.empty()) {
            output_json_response(false, "No valid routing endpoints provided");
            return 1;
        }
        
        // Find best route using HC2L labels
        // cerr << "🔍 Querying HC2L index..." << endl;
        auto start_time = chrono::high_resolution_clock::now();
        
        distance_t best_distance = numeric_limits<distance_t>::max();
        NodeID best_start = 0, best_dest = 0;
        
        for (NodeID s : start_candidates) {
            for (NodeID d : dest_candidates) {
                // cerr << "  Checking distance from " << s << " to " << d << "..." << endl;
                distance_t dist = ci.get_distance(s, d);
                // cerr << "    Distance: " << dist << endl;
                if (dist < best_distance) {
                    best_distance = dist;
                    best_start = s;
                    best_dest = d;
                }
            }
        }
        
        auto end_time = chrono::high_resolution_clock::now();
        double query_time_ms = chrono::duration<double, milli>(end_time - start_time).count();
        
        // cerr << "✅ Best route found: " << best_start << " -> " << best_dest << " (distance: " << best_distance << ")" << endl;
        
        if (best_start == 0 || best_dest == 0) {
            output_json_response(false, "No valid path found");
            return 1;
        }
        
        // IDs are already sequential, no need to convert back
        // (adj_list and coordinates use sequential IDs as keys)
        NodeID best_start_osm = best_start;
        NodeID best_dest_osm = best_dest;
        // cerr << "  Sequential IDs: " << best_start << " -> " << best_dest << endl;
        // cerr << "  OSM IDs: " << best_start_osm << " -> " << best_dest_osm << endl;
        
        // cerr << "🛣️  Finding actual path with Dijkstra..." << endl;
        // Find actual path using Dijkstra with comprehensive cost calculation
        // *** USES ENHANCED VERSION WITH HIGHWAY, FLOW, AND INCIDENT DATA ***
        vector<NodeID> path = find_shortest_path(best_start_osm, best_dest_osm, adj_list, 
                                                  coordinates, flow_data, incident_data);
        // cerr << "✅ Path found with " << path.size() << " nodes" << endl;
        
        // VALIDATION: Check for missing edges between path nodes
        // This helps detect if intermediate nodes are being missed at sharp turns
        vector<pair<NodeID, NodeID>> missing_edges;
        for (size_t i = 0; i < path.size() - 1; i++) {
            NodeID from = path[i];
            NodeID to = path[i + 1];
            
            bool edge_found = false;
            if (adj_list.count(from)) {
                for (const auto& neighbor : adj_list.at(from)) {
                    if (neighbor.node == to) {
                        edge_found = true;
                        break;
                    }
                }
            }
            
            if (!edge_found) {
                missing_edges.push_back({from, to});
                cerr << "⚠️  WARNING: Missing edge in path: " << from << " → " << to << endl;
            }
        }
        
        if (!missing_edges.empty()) {
            cerr << "❌ Found " << missing_edges.size() << " missing edges in path!" << endl;
            cerr << "   This indicates intermediate nodes may be missing at sharp turns" << endl;
        }
        
        // Determine if on same edge and if they can meet directly
        bool same_edge = (start_edge_source == dest_edge_source && start_edge_target == dest_edge_target) ||
                         (start_edge_source == dest_edge_target && start_edge_target == dest_edge_source);
        
        bool can_meet_on_same_edge = false;
        
        if (same_edge) {
            // Get edge geometry to check snap positions
            auto edge_key = make_pair(start_edge_source, start_edge_target);
            if (edge_geometries.count(edge_key)) {
                const auto& geom = edge_geometries.at(edge_key).coords;
                
                double start_pos = get_snap_position_on_edge(geom, start_snap_lat, start_snap_lng);
                double dest_pos = get_snap_position_on_edge(geom, dest_snap_lat, dest_snap_lng);
                
                // Check if we can travel from start to dest following edge direction
                if (start_edge_oneway == 1) {
                    // Forward only: can meet if start comes before dest
                    can_meet_on_same_edge = (start_pos <= dest_pos);
                } else if (start_edge_oneway == -1) {
                    // Reverse only: can meet if start comes after dest (traveling backwards)
                    can_meet_on_same_edge = (start_pos >= dest_pos);
                } else {
                    // Bidirectional: always can meet
                    can_meet_on_same_edge = true;
                }
            } else {
                // No geometry found, fallback to simple check
                can_meet_on_same_edge = (best_start == best_dest) || (start_edge_oneway == 0);
            }
        }
        
        if (same_edge && can_meet_on_same_edge) {
            // Same edge case where they CAN meet directly
            // Set path to just the edge endpoints
            path.clear();
            path.push_back(start_edge_source);
            path.push_back(start_edge_target);
        } else if (same_edge && !can_meet_on_same_edge) {
            // Same edge but CANNOT meet directly (wrong direction on one-way)
            // The path from Dijkstra will find the route through the network
            // We need to add virtual snap edge segments at start and end
            // Path already contains the network route, just ensure proper edge inclusion below
        }
        
        if (!path.empty() && !same_edge) {
            // Different edges: ensure both snap edges are included
            
            cerr << "🔍 START EDGE INCLUSION CHECK:" << endl;
            cerr << "   Start edge: " << start_edge_source << " → " << start_edge_target << endl;
            cerr << "   First path node: " << path[0] << endl;
            if (path.size() >= 2) {
                cerr << "   Second path node: " << path[1] << endl;
            }
            
            // Prepend start edge if needed
            NodeID first = path[0];
            bool start_edge_present = false;
            if (path.size() >= 2) {
                NodeID second = path[1];
                start_edge_present = (first == start_edge_source && second == start_edge_target) ||
                                   (first == start_edge_target && second == start_edge_source);
            }
            
            cerr << "   Start edge present in path: " << (start_edge_present ? "YES" : "NO") << endl;
            
            if (!start_edge_present) {
                // Add the other endpoint to create the edge
                if (first == start_edge_source) {
                    path.insert(path.begin(), start_edge_target);
                    cerr << "   ✅ Prepended target node " << start_edge_target << " to create start edge" << endl;
                } else if (first == start_edge_target) {
                    path.insert(path.begin(), start_edge_source);
                    cerr << "   ✅ Prepended source node " << start_edge_source << " to create start edge" << endl;
                } else {
                    // Path doesn't start on snap edge - add both nodes
                    path.insert(path.begin(), start_edge_target);
                    path.insert(path.begin(), start_edge_source);
                    cerr << "   ⚠️  Path doesn't start on snap edge! Added both: " << start_edge_source << " → " << start_edge_target << endl;
                }
            }
            
            cerr << "\n🔍 DEST EDGE INCLUSION CHECK:" << endl;
            cerr << "   Dest edge: " << dest_edge_source << " → " << dest_edge_target << endl;
            cerr << "   Last path node: " << path[path.size() - 1] << endl;
            if (path.size() >= 2) {
                cerr << "   Second-last path node: " << path[path.size() - 2] << endl;
            }
            
            // Append dest edge if needed
            NodeID last = path[path.size() - 1];
            bool dest_edge_present = false;
            if (path.size() >= 2) {
                NodeID second_last = path[path.size() - 2];
                dest_edge_present = (second_last == dest_edge_source && last == dest_edge_target) ||
                                  (second_last == dest_edge_target && last == dest_edge_source);
            }
            
            cerr << "   Dest edge present in path: " << (dest_edge_present ? "YES" : "NO") << endl;
            
            if (!dest_edge_present) {
                // Add the other endpoint to create the edge
                if (last == dest_edge_source) {
                    path.push_back(dest_edge_target);
                    cerr << "   ✅ Appended target node " << dest_edge_target << " to create dest edge" << endl;
                } else if (last == dest_edge_target) {
                    path.push_back(dest_edge_source);
                    cerr << "   ✅ Appended source node " << dest_edge_source << " to create dest edge" << endl;
                } else {
                    // Path doesn't end on snap edge - add both nodes
                    path.push_back(dest_edge_source);
                    path.push_back(dest_edge_target);
                    cerr << "   ⚠️  Path doesn't end on snap edge! Added both: " << dest_edge_source << " → " << dest_edge_target << endl;
                }
            }
            
            cerr << "\n✅ Final path after edge inclusion: ";
            for (size_t i = 0; i < min(path.size(), size_t(15)); i++) {
                cerr << path[i];
                if (i < min(path.size(), size_t(15)) - 1) cerr << " → ";
            }
            if (path.size() > 15) cerr << " ... (" << (path.size() - 15) << " more)";
            cerr << endl << endl;
        }
        
        // ============================================================
        // LAZYHC2L: Apply lazy repair if path touches dirty nodes
        // ============================================================
        if (use_disruptions && !lazy_state.dirty_labels.empty()) {
            // Count dirty nodes on path
            for (NodeID node : path) {
                if (lazy_state.dirty_labels.count(node)) {
                    dirty_nodes_on_path++;
                }
            }
            
            // Trigger lazy repair if needed
            bool repair_needed = lazy_repair_path(path, lazy_state, 
                                                   lazy_repair_time_ms, nodes_repaired);
            cache_hit = !repair_needed;
            
            if (repair_needed) {
                cerr << "🔧 Lazy repair triggered: " << nodes_repaired 
                     << " nodes repaired in " << lazy_repair_time_ms << " ms" << endl;
            } else {
                cerr << "✅ Cache hit: No repair needed (path doesn't touch dirty nodes)" << endl;
            }
        }
        
        // ============================================================
        // GENERATE ALTERNATIVE ROUTES with ETA comparison
        // ============================================================
        vector<AlternativeRoute> alternatives;
        
        if (use_disruptions && !flow_data.empty()) {
            cerr << "\n🔀 Generating alternative routes with ETA comparison..." << endl;
            
            // Generate up to 3 alternative routes
            alternatives = generate_alternative_routes(
                best_start, best_dest, adj_list, ci, flow_data, coordinates, 3
            );
            
            if (!alternatives.empty()) {
                cerr << "✅ Found " << alternatives.size() << " alternative routes:" << endl;
                for (const auto& alt : alternatives) {
                    cerr << "   Route " << alt.rank << ": " 
                         << alt.description 
                         << " - " << format_eta_time(alt.eta_seconds)
                         << " (Avg Jam: " << fixed << setprecision(2) << alt.avg_jam_factor << ")"
                         << endl;
                }
                
                // Update main path to best alternative if better ETA found
                if (alternatives[0].eta_seconds < calculate_eta_with_flow(path, flow_data, coordinates)) {
                    cerr << "🚀 Switching to faster alternative route (saving " 
                         << format_eta_time(calculate_eta_with_flow(path, flow_data, coordinates) - alternatives[0].eta_seconds)
                         << ")" << endl;
                    path = alternatives[0].path;
                    best_distance = alternatives[0].distance;
                }
            }
        }
        
        // ============================================================
        // FINAL EDGE INCLUSION: Re-apply after alternative route selection
        // ============================================================
        if (!path.empty() && !same_edge) {
            cerr << "\n🔧 FINAL: Re-applying start/dest edges after alternative route selection..." << endl;
            
            // Prepend start edge if needed
            NodeID first = path[0];
            bool start_edge_present = false;
            if (path.size() >= 2) {
                NodeID second = path[1];
                start_edge_present = (first == start_edge_source && second == start_edge_target) ||
                                   (first == start_edge_target && second == start_edge_source);
            }
            
            if (!start_edge_present) {
                if (first == start_edge_source) {
                    path.insert(path.begin(), start_edge_target);
                } else if (first == start_edge_target) {
                    path.insert(path.begin(), start_edge_source);
                } else {
                    path.insert(path.begin(), start_edge_target);
                    path.insert(path.begin(), start_edge_source);
                }
                cerr << "   ✅ Start edge re-added" << endl;
            }
            
            // Append dest edge if needed
            NodeID last = path[path.size() - 1];
            bool dest_edge_present = false;
            if (path.size() >= 2) {
                NodeID second_last = path[path.size() - 2];
                dest_edge_present = (second_last == dest_edge_source && last == dest_edge_target) ||
                                  (second_last == dest_edge_target && last == dest_edge_source);
            }
            
            if (!dest_edge_present) {
                if (last == dest_edge_source) {
                    path.push_back(dest_edge_target);
                } else if (last == dest_edge_target) {
                    path.push_back(dest_edge_source);
                } else {
                    path.push_back(dest_edge_source);
                    path.push_back(dest_edge_target);
                }
                cerr << "   ✅ Dest edge re-added" << endl;
            }
        }
        
        // Output result
        output_json_response(true, "", best_start, best_dest,
                           start_pin_lat, start_pin_lng, start_snap_lat, start_snap_lng,
                           dest_pin_lat, dest_pin_lng, dest_snap_lat, dest_snap_lng,
                           start_edge_source, start_edge_target, start_edge_oneway,
                           dest_edge_source, dest_edge_target, dest_edge_oneway,
                           best_distance, query_time_ms, path, coordinates,
                           edge_geometries, use_disruptions, disruption_file,
                           &ci, index_load_time_ms,
                           tau_threshold, &lazy_state, disruption_impact_score,
                           update_strategy, lazy_reason, dirty_nodes_on_path,
                           lazy_repair_time_ms, nodes_repaired, cache_hit,
                           flow_data, alternatives);
        
        return 0;
        
    } catch (const exception& e) {
        output_json_response(false, string("Exception: ") + e.what());
        return 1;
    }
}
