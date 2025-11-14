#ifndef ROUTING_UTILS_H
#define ROUTING_UTILS_H

/**
 * Routing Utility Functions
 * 
 * Common utility functions used by both DHL and HC2L routing APIs
 * Includes: distance calculations, speed profiles, ETA calculations, severity levels
 */

#include <string>
#include <vector>
#include <map>
#include <set>
#include <queue>
#include <cmath>
#include <ctime>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <exception>
#include <iostream>
#include <sys/stat.h>
#include "shared_routing_structures.h"
#include "base_road_network.h"

using namespace std;
using namespace road_network;


// ============================================================
// DISTANCE & COORDINATE CALCULATIONS
// ============================================================

/**
 * Calculate Haversine distance between two GPS coordinates
 * @param lat1, lon1, lat2, lon2 - Latitude and longitude in degrees
 * @return Distance in meters
 */
inline double haversine_distance(double lat1, double lon1, double lat2, double lon2) {
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

/**
 * Calculate total route distance from path nodes using coordinates
 * @param path - Vector of node IDs in the path
 * @param coordinates - Map of node coordinates
 * @return Total route distance in meters
 */
inline double calculate_route_distance(
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

// ============================================================
// SPEED PROFILES & TRAFFIC CALCULATIONS
// ============================================================

/**
 * Speed profile structure for time-based speed adjustments
 */
struct SpeedProfile {
    const char* time_period;        // "morning", "noon", "evening"
    double baseline_speed_kmh;      // Free-flow speed in km/h
    double congestion_factor;       // Multiplier for congestion slowdown (0.0-1.0)
};

/**
 * Get speed profiles based on Quezon City traffic patterns
 * Reference: Table 8 in project documentation
 */
inline map<string, SpeedProfile> get_speed_profiles() {
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

/**
 * Get current speed profile based on hour of day
 * Uses local system time if hour not specified
 */
inline SpeedProfile get_current_speed_profile(int hour = -1) {
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
        return {"Evening Rush", 20.0, 0.35};  // Evening: 2pm-8pm
    } else {
        return {"Off-Peak", 45.0, 0.85};      // Night/early morning
    }
}

/**
 * Calculate travel duration for a single edge in seconds
 * Uses actual traffic speed if available, otherwise uses free-flow speed
 */
inline double calculate_edge_duration(
    double edge_distance_meters,
    double current_speed_kmh,
    double free_flow_speed_kmh,
    bool is_closed = false) {
    
    // Closed roads are impassable
    if (is_closed) {
        return 999999.0; // Effectively infinite duration
    }
    
    // Use current speed if available and valid, otherwise use free-flow speed
    double effective_speed_kmh = 0.0;
    if (current_speed_kmh > 0.1) {
        effective_speed_kmh = current_speed_kmh;
    } else if (free_flow_speed_kmh > 0.1) {
        effective_speed_kmh = free_flow_speed_kmh;
    } else {
        // Fallback to default urban speed
        effective_speed_kmh = 40.0;
    }
    
    // Ensure minimum speed (1 km/h to avoid division by zero)
    effective_speed_kmh = max(effective_speed_kmh, 1.0);
    
    // Calculate duration: distance (m) / (speed_kmh / 3.6) = time (s)
    double speed_ms = effective_speed_kmh / 3.6;
    double duration_seconds = edge_distance_meters / speed_ms;
    
    return duration_seconds;
}

// ============================================================
// ETA CALCULATIONS
// ============================================================

/**
 * Calculate ETA in seconds from distance and jam factor
 * Uses time-of-day based speed profiles (Table 8)
 */
inline double calculate_eta_seconds(
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
    
    // Convert to m/s: speed_kmh / 3.6
    double actual_speed_ms = actual_speed_kmh / 3.6;
    
    // Calculate time: distance (m) / speed (m/s) = time (s)
    double eta_seconds = distance_m / actual_speed_ms;
    
    return eta_seconds;
}

/**
 * Format seconds into human-readable time string (HH:mm:ss)
 */
inline string format_eta_time(double seconds) {
    int total_secs = static_cast<int>(seconds + 0.5);
    int hours = total_secs / 3600;
    int minutes = (total_secs % 3600) / 60;
    int secs = total_secs % 60;
    
    stringstream ss;
    if (hours > 0) {
        ss << hours << "h " << minutes << "m " << secs << "s";
    } else if (minutes > 0) {
        ss << minutes << "m " << secs << "s";
    } else {
        ss << secs << "s";
    }
    
    return ss.str();
}

// ============================================================
// TRAFFIC FLOW & SEVERITY FUNCTIONS
// ============================================================

/**
 * Determine flow status and color code from jam factor
 * Reference: HERE API jam_factor scale (0.0 = free flow, 10.0 = blocked)
 * ALIGNED with Python traffic overlay severity mapping
 */
inline TrafficFlowData get_flow_color(double jam_factor, double current_speed, double free_flow_speed) {
    TrafficFlowData flow;
    flow.jam_factor = jam_factor;
    flow.current_speed = current_speed;
    flow.free_flow_speed = free_flow_speed;
    
    if (free_flow_speed > 0) {
        flow.speed_reduction = 1.0 - (current_speed / free_flow_speed);
    } else {
        flow.speed_reduction = 0.0;
    }
    
    if (jam_factor >= 8.0) {
        flow.flow_status = "heavy";      // Severity: Heavy
        flow.color_code = "#ef4444";     // Red (matches Python overlay)
    } else if (jam_factor >= 5.0) {
        flow.flow_status = "medium";     // Severity: Medium
        flow.color_code = "#f59e0b";     // Orange (matches Python overlay)
    } else {
        flow.flow_status = "light";      // Severity: Light
        flow.color_code = "#10b981";     // Green (matches Python overlay)
    }
    
    return flow;
}


// ============================================================
// DISRUPTION ANALYSIS FUNCTIONS
// ============================================================

/**
 * Get severity level based on jam factor and incident type
 * Used for JSON output classification
 */
inline string get_severity_level(double jam_factor, const string& incident_type, bool is_closed) {
    if (is_closed) return "critical";
    if (jam_factor >= 8.0) return "high";
    if (jam_factor >= 5.0) return "medium";
    if (jam_factor >= 2.0) return "low";
    return "none";
}

// ============================================================
// HIGHWAY CLASSIFICATION
// ============================================================

/**
 * Get highway type priority weight for routing cost calculation
 * Lower weight = better/faster road, higher weight = slower/less preferred
 * Motorways: 1.0x (fastest)
 * Residential: 2.8x (slowest)
 */
inline double get_highway_weight(const string& highway_type) {
    static const map<string, double> weights = {
        {"motorway", 1.0},              // Fastest: divided highway, high speed
        {"motorway_link", 1.05},        // Highway on/off ramps
        {"trunk", 1.1},                 // Major roads, high capacity
        {"trunk_link", 1.15},
        {"primary", 1.3},               // Major connecting roads
        {"primary_link", 1.35},
        {"secondary", 1.6},             // Medium importance roads
        {"secondary_link", 1.65},
        {"tertiary", 2.0},              // Local connector roads
        {"tertiary_link", 2.05},
        {"unclassified", 2.3},          // Minor roads
        {"residential", 2.8},           // Slow residential streets
        {"living_street", 3.0},         // Very low speed zones
        {"service", 2.5},               // Service roads, parking lots
        {"road", 2.0}                   // Unknown type default
    };
    
    auto it = weights.find(highway_type);
    return (it != weights.end()) ? it->second : 2.0;
}

/**
 * Get free-flow speed for highway type in km/h
 */
inline double get_highway_speed(const string& highway_type) {
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

/**
 * Get incident severity multiplier based on incident type
 * Higher multiplier = route around this incident more aggressively
 */
inline double get_incident_severity(const string& incident_type) {
    static const map<string, double> severities = {
        {"closure", 999.0},             // Impassable - effectively infinite cost
        {"accident", 5.0},              // Major incident - avoid heavily
        {"construction", 2.5},          // Work zone - avoid moderately
        {"congestion", 1.8},            // Heavy traffic - avoid if alternatives exist
        {"heavy_traffic", 1.6},         // Heavy congestion
        {"moderate_traffic", 1.3},      // Moderate congestion
        {"weather", 1.5},               // Weather impact - minor avoidance
        {"light_traffic", 1.1},         // Light congestion
        {"unknown", 1.3}                // Default - slight avoidance
    };
    
    auto it = severities.find(incident_type);
    return (it != severities.end()) ? it->second : 1.3;
}

// ============================================================
// GEOMETRY & SNAP POINT FUNCTIONS
// ============================================================

/**
 * Find the position of a snap point along an edge (0.0 to 1.0)
 * 0.0 = at source node, 1.0 = at target node
 */
inline double get_snap_position_on_edge(
    const vector<pair<double, double>>& coords,
    double snap_lat, double snap_lng) {
    
    if (coords.size() < 2) return 0.5; // Default to midpoint
    
    double min_distance = 1e9;
    double best_position = 0.0;
    double total_distance = 0.0;
    double distance_to_snap = 0.0;
    
    // Calculate total distance along edge
    for (size_t i = 0; i < coords.size() - 1; i++) {
        double segment_dist = haversine_distance(
            coords[i].first, coords[i].second,
            coords[i + 1].first, coords[i + 1].second
        );
        
        // Check closest point to snap
        double snap_dist = haversine_distance(
            coords[i].first, coords[i].second,
            snap_lat, snap_lng
        );
        
        if (snap_dist < min_distance) {
            min_distance = snap_dist;
            distance_to_snap = total_distance;
            best_position = distance_to_snap / (total_distance + segment_dist);
        }
        
        total_distance += segment_dist;
    }
    
    // Clamp to [0, 1]
    best_position = max(0.0, min(1.0, best_position));
    return best_position;
}

/*
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
*/


// ============================================================
// NODE ID MAPPING FUNCTIONS
// ============================================================

/**
 * Load node ID mapping from CSV file
 * CSV format: osm_id,sequential_id
 */

inline map<NodeID, NodeID> load_node_id_mapping(const string& filename) {
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

// ============================================================
// COORDINATE LOADING FUNCTIONS
// ============================================================

/**
 * Load node coordinates from CSV file
 * CSV format: node_id,osm_id,latitude,longitude
 */

inline map<NodeID, GPSCoordinate> load_node_coordinates(const string& filename) {
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

// ============================================================
// CSV PARSING UTILITIES
// ============================================================

/**
 * Simple CSV line parser
 * Splits a CSV line into fields, handling quoted fields
 */
inline vector<string> parse_csv_line(const string& line) {
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


// ============================================================
// EDGE LOADING FUNCTIONS
// ============================================================

// Forward declare external globals that load_edges needs
extern DisruptionCache g_disruption_cache;  // Global cache (defined in routing API files)
extern map<pair<NodeID, NodeID>, string> g_highway_types;  // Highway types (defined in routing API files)

/**
 * Load edges from CSV file with one-way road support and geometry
 */
inline map<NodeID, vector<Neighbor>> load_edges(const string& filename, map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries) {
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
// DISRUPTION DATA LOADING & CACHING
// ============================================================

/**
 * Load and cache disruption data from CSV file
 * Supports both flow data and incident data
 * Uses file modification time to detect changes
 */
extern map<pair<NodeID, NodeID>, string> g_highway_types;  // Highway types (defined in routing API files)

// Forward declaration of compute_disruption_metrics
// (defined in each routing API implementation: dhl_routing_api.cpp, hc2l_routing_api.cpp)
EdgeDisruptionMetrics compute_disruption_metrics(
    const IncidentInfo* incident,
    const TrafficFlowData* flow,
    const string& highway_type,
    distance_t base_distance);

inline bool load_disruptions_with_cache(
    const string& disruption_file,
    map<pair<NodeID, NodeID>, IncidentInfo>& incidents_out,
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
        // SILENT CACHE HIT - don't spam logs on every route calculation
        incidents_out = g_disruption_cache.incidents;
        flow_out = g_disruption_cache.flow_data;
        return true;
    }
    
    // Cache invalid or file changed - reload
    cerr << "🔄 Traffic data updated - Loading new disruptions from CSV file" << endl;
    
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
    bool is_csv_format = true;
    int source_col = -1, target_col = -1, speed_col = -1, freeflow_col = -1;
    int jam_col = -1, closed_col = -1, length_col = -1;
    int flow_confidence_col = -1, flow_traversability_col = -1;
    int incident_id_col = -1, incident_type_col = -1, incident_criticality_col = -1;
    int incident_description_col = -1, incident_road_closed_col = -1;
    int incident_start_time_col = -1, incident_end_time_col = -1;
    
    // Read and parse CSV header
    if (getline(disrupt_file, line)) {
        cerr << "   📋 Parsing CSV header..." << endl;
        
        vector<string> headers = parse_csv_line(line);
        for (size_t i = 0; i < headers.size(); i++) {
            string h = headers[i];
            h.erase(0, h.find_first_not_of(" \t\n\r"));
            h.erase(h.find_last_not_of(" \t\n\r") + 1);
            
            if (h == "source") source_col = i;
            else if (h == "target") target_col = i;
            else if (h == "flow_speed_kph") speed_col = i;
            else if (h == "speed_kph") speed_col = i;
            else if (h == "flow_free_flow_kph") freeflow_col = i;
            else if (h == "freeFlow_kph") freeflow_col = i;
            else if (h == "flow_jam_factor") jam_col = i;
            else if (h == "jamFactor") jam_col = i;
            else if (h == "flow_confidence") flow_confidence_col = i;
            else if (h == "flow_traversability") flow_traversability_col = i;
            else if (h == "isClosed") closed_col = i;
            else if (h == "segmentLength") length_col = i;
            else if (h == "incident_id") incident_id_col = i;
            else if (h == "incident_type") incident_type_col = i;
            else if (h == "incident_criticality") incident_criticality_col = i;
            else if (h == "incident_description") incident_description_col = i;
            else if (h == "incident_road_closed") incident_road_closed_col = i;
            else if (h == "incident_start_time") incident_start_time_col = i;
            else if (h == "incident_end_time") incident_end_time_col = i;
        }
        
        cerr << "   Column mapping: source=" << source_col << ", target=" << target_col 
             << ", speed=" << speed_col << ", freeflow=" << freeflow_col << endl;
    }
    
    while (getline(disrupt_file, line)) {
        if (line.empty() || line[0] == 'c' || line[0] == 'p') continue;
        
        NodeID source, target;
        distance_t new_weight = 0;
        double jam_factor = 5.0, current_speed = 0.0, free_flow_speed = 50.0;
        double impact_score = 0.5;
        string highway_type = "unknown", disruption_type = "unknown";
        int is_closed = 0;
        
        string incident_id_val = "";
        string incident_type_val = "";
        string incident_criticality_val = "";
        string incident_description_val = "";
        string incident_start_time_val = "";
        string incident_end_time_val = "";
        int incident_road_closed = 0;
        double flow_confidence_val = 0.99;
        string flow_traversability_val = "open";
        
        if (is_csv_format) {
            vector<string> fields = parse_csv_line(line);
            
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
                
                if (incident_id_col >= 0 && incident_id_col < (int)fields.size() && !fields[incident_id_col].empty()) {
                    incident_id_val = fields[incident_id_col];
                }
                if (incident_type_col >= 0 && incident_type_col < (int)fields.size() && !fields[incident_type_col].empty()) {
                    incident_type_val = fields[incident_type_col];
                }
                if (incident_criticality_col >= 0 && incident_criticality_col < (int)fields.size()) {
                    incident_criticality_val = fields[incident_criticality_col];
                }
                if (incident_description_col >= 0 && incident_description_col < (int)fields.size()) {
                    incident_description_val = fields[incident_description_col];
                }
                if (incident_road_closed_col >= 0 && incident_road_closed_col < (int)fields.size()) {
                    string closed_str = fields[incident_road_closed_col];
                    incident_road_closed = (closed_str == "True" || closed_str == "true" || closed_str == "1") ? 1 : 0;
                }
                if (incident_start_time_col >= 0 && incident_start_time_col < (int)fields.size()) {
                    incident_start_time_val = fields[incident_start_time_col];
                }
                if (incident_end_time_col >= 0 && incident_end_time_col < (int)fields.size()) {
                    incident_end_time_val = fields[incident_end_time_col];
                }
                
                if (flow_confidence_col >= 0 && flow_confidence_col < (int)fields.size() && !fields[flow_confidence_col].empty()) {
                    flow_confidence_val = stod(fields[flow_confidence_col]);
                }
                if (flow_traversability_col >= 0 && flow_traversability_col < (int)fields.size() && !fields[flow_traversability_col].empty()) {
                    flow_traversability_val = fields[flow_traversability_col];
                }
                
                if (!incident_type_val.empty() && incident_road_closed) {
                    is_closed = 1;
                    disruption_type = incident_type_val;
                    
                    string crit_lower = incident_criticality_val;
                    transform(crit_lower.begin(), crit_lower.end(), crit_lower.begin(), ::tolower);
                    
                    if (crit_lower.find("critical") != string::npos) {
                        jam_factor = max(jam_factor, 9.0);
                    } else if (crit_lower.find("severe") != string::npos) {
                        jam_factor = max(jam_factor, 7.0);
                    } else if (crit_lower.find("major") != string::npos) {
                        jam_factor = max(jam_factor, 5.0);
                    } else if (crit_lower.find("minor") != string::npos) {
                        jam_factor = max(jam_factor, 2.0);
                    }
                } else if (closed_col >= 0 && closed_col < (int)fields.size()) {
                    string closed_str = fields[closed_col];
                    is_closed = (closed_str == "True" || closed_str == "true" || closed_str == "1") ? 1 : 0;
                }
                
                if (length_col >= 0 && length_col < (int)fields.size()) {
                    new_weight = static_cast<distance_t>(stod(fields[length_col]));
                }
                
                if (free_flow_speed == 0.0) {
                    if (fields.size() > 11) {
                        string hw_type = fields[11];
                        if (hw_type.find("motorway") != string::npos) free_flow_speed = 110.0;
                        else if (hw_type.find("trunk") != string::npos) free_flow_speed = 90.0;
                        else if (hw_type.find("primary") != string::npos) free_flow_speed = 70.0;
                        else if (hw_type.find("secondary") != string::npos) free_flow_speed = 60.0;
                        else if (hw_type.find("tertiary") != string::npos) free_flow_speed = 50.0;
                        else if (hw_type.find("residential") != string::npos) free_flow_speed = 40.0;
                        else free_flow_speed = 50.0;
                    } else {
                        free_flow_speed = 50.0;
                    }
                }
                
                if (is_closed) {
                    disruption_type = "road_closure";
                    new_weight = 999999.0;
                } else if (jam_factor >= 8.0) {
                    disruption_type = "accident";
                } else if (jam_factor >= 5.0) {
                    disruption_type = "congestion";
                } else {
                    disruption_type = "normal";
                }
                
                if (free_flow_speed >= 80) {
                    highway_type = "motorway";
                } else if (free_flow_speed >= 60) {
                    highway_type = "trunk";
                } else if (free_flow_speed >= 50) {
                    highway_type = "primary";
                } else if (free_flow_speed >= 40) {
                    highway_type = "secondary";
                } else {
                    highway_type = "residential";
                }
                
                double speed_reduction = (free_flow_speed > 0) ? 
                    (free_flow_speed - current_speed) / free_flow_speed : 0.0;
                impact_score = min(1.0, max(0.0, jam_factor / 10.0 * 0.5 + speed_reduction * 0.5));
                
                if (!is_closed) {
                    distance_t old_weight = 0;
                    if (adj_list.count(source)) {
                        for (const auto& neighbor : adj_list.at(source)) {
                            if (neighbor.node == target) {
                                old_weight = neighbor.distance;
                                break;
                            }
                        }
                    }
                    
                    if (current_speed > 0.1 && free_flow_speed > 0.1) {
                        double speed_ratio = free_flow_speed / current_speed;
                        speed_ratio = min(10.0, max(1.0, speed_ratio));
                        new_weight = static_cast<distance_t>(old_weight * speed_ratio);
                    } else {
                        double flow_multiplier = 1.0 + (jam_factor / 10.0) * 4.0;
                        new_weight = static_cast<distance_t>(old_weight * flow_multiplier);
                    }
                }
                
            } catch (const exception& e) {
                cerr << "⚠️  Error parsing CSV line: " << e.what() << endl;
                continue;
            }
        } else {
            istringstream iss(line);
            if (!(iss >> source >> target >> new_weight)) continue;
            iss >> jam_factor >> current_speed >> free_flow_speed 
                >> impact_score >> highway_type >> is_closed >> disruption_type;
        }
        
        auto edge_key = make_pair(source, target);
        
        IncidentInfo incident;
        incident.id = incident_id_val;
        incident.type = incident_type_val;
        incident.criticality = incident_criticality_val;
        incident.description = incident_description_val;
        incident.road_closed = (incident_road_closed == 1);
        incident.start_time = incident_start_time_val;
        incident.end_time = incident_end_time_val;
        
        if (incident.has_incident() || incident.road_closed) {
            incidents_out[edge_key] = incident;
        }
        
        TrafficFlowData flow = get_flow_color(jam_factor, current_speed, free_flow_speed);
        
        if (is_csv_format) {
            flow.confidence = flow_confidence_val;
            flow.traversability = flow_traversability_val;
        }
        
        flow_out[edge_key] = flow;
        
        total_count++;
        if (is_closed || new_weight >= 999999.0) {
            closures++;
        } else {
            active_disruptions++;
        }
    }
    
    disrupt_file.close();
    
    map<pair<NodeID, NodeID>, EdgeDisruptionMetrics> disruption_metrics_out;
    
    for (const auto& [edge_key, incident] : incidents_out) {
        const IncidentInfo* incident_ptr = &incident;
        const TrafficFlowData* flow_ptr = flow_out.count(edge_key) ? &flow_out.at(edge_key) : nullptr;
        
        string edge_highway_type = "unknown";
        if (g_highway_types.count(edge_key)) {
            edge_highway_type = g_highway_types.at(edge_key);
        }
        
        double edge_distance = 0.0;
        if (edge_geometries.count(edge_key)) {
            edge_distance = edge_geometries.at(edge_key).length;
        }
        
        EdgeDisruptionMetrics metrics = compute_disruption_metrics(
            incident_ptr, flow_ptr, edge_highway_type, 
            static_cast<distance_t>(edge_distance)
        );
        disruption_metrics_out[edge_key] = metrics;
    }
    
    for (const auto& [edge_key, flow] : flow_out) {
        if (disruption_metrics_out.count(edge_key) > 0) continue;
        
        const IncidentInfo* incident_ptr = nullptr;
        const TrafficFlowData* flow_ptr = &flow;
        
        string edge_highway_type = "unknown";
        if (g_highway_types.count(edge_key)) {
            edge_highway_type = g_highway_types.at(edge_key);
        }
        
        double edge_distance = 0.0;
        if (edge_geometries.count(edge_key)) {
            edge_distance = edge_geometries.at(edge_key).length;
        }
        
        EdgeDisruptionMetrics metrics = compute_disruption_metrics(
            incident_ptr, flow_ptr, edge_highway_type,
            static_cast<distance_t>(edge_distance)
        );
        disruption_metrics_out[edge_key] = metrics;
    }
    
    struct stat file_stat;
    if (stat(disruption_file.c_str(), &file_stat) == 0) {
        g_disruption_cache.file_modified_time = file_stat.st_mtime;
    }
    g_disruption_cache.file_path = disruption_file;
    g_disruption_cache.incidents = incidents_out;
    g_disruption_cache.flow_data = flow_out;
    g_disruption_cache.disruption_metrics = disruption_metrics_out;
    g_disruption_cache.total_incidents = total_count;
    g_disruption_cache.closures = closures;
    g_disruption_cache.active_disruptions = active_disruptions;
    
    cerr << "✅ Loaded " << total_count << " disruptions (Closures: " << closures 
         << ", Active: " << active_disruptions << ")" << endl;
    
    return true;
}


// ============================================================
// ETA CALCULATION FUNCTIONS
// ============================================================

// Calculate ETA in seconds using actual traffic flow data from edges
double calculate_eta_with_disruption(
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
// ALTERNATIVE ROUTE GENERATION
// ============================================================

// Generate K alternative routes using penalty-based k-shortest paths
// NOTE: Generates K+1 routes internally, but only returns routes with rank >= 2
// (skips the fastest route which is already the primary route)
vector<AlternativeRoute> generate_alternative_routes(
    NodeID start, NodeID dest,
    const map<NodeID, vector<Neighbor>>& adj_list,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<NodeID, GPSCoordinate>& coordinates,
    int K = 3) {
    
    vector<AlternativeRoute> all_alternatives;
    vector<AlternativeRoute> alternatives; // Will only contain ranks 2+
    set<pair<NodeID, NodeID>> used_edges;
    
    // Generate K+1 routes to ensure we have at least 2 alternatives after removing rank 1
    for (int k = 0; k < K + 1; k++) {
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
        route.eta_seconds = calculate_eta_with_disruption(path, flow_data, coordinates);
        
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
        
        all_alternatives.push_back(route);
        
        // Mark edges as used for next iteration
        for (size_t i = 0; i < path.size() - 1; i++) {
            used_edges.insert({path[i], path[i+1]});
        }
    }
    
    // Sort all alternatives by ETA (best first)
    sort(all_alternatives.begin(), all_alternatives.end(),
         [](const AlternativeRoute& a, const AlternativeRoute& b) {
             return a.eta_seconds < b.eta_seconds;
         });
    
    // Filter: skip rank 1 (fastest), only return ranks 2 and beyond
    // This way the fastest route (already returned as main route) is not duplicated
    for (size_t i = 1; i < all_alternatives.size(); i++) {  // Start from index 1 (rank 2)
        AlternativeRoute& route = all_alternatives[i];
        route.rank = i;  // Re-rank starting from 1 for the alternatives
        route.description = i == 1 ? "Alternative via different path" : "Secondary alternative";
        alternatives.push_back(route);
    }
    
    return alternatives;
}


#endif // ROUTING_UTILS_H
