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
#include <dirent.h>
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
        {"road-closure", 999.0},        // User-reported road closure
        {"road_closure", 999.0},        // Alternative format
        {"accident", 5.0},              // Major incident - avoid heavily
        {"construction", 2.5},          // Work zone - avoid moderately
        {"congestion", 1.8},            // Heavy traffic - avoid if alternatives exist
        {"heavy_traffic", 1.6},         // Heavy congestion
        {"moderate_traffic", 1.3},      // Moderate congestion
        {"weather", 1.5},               // Weather impact - minor avoidance
        {"light_traffic", 1.1},         // Light congestion
        {"user-incident", 2.0},         // Generic user-reported incident
        {"traffic", 1.5},               // Generic traffic incident
        {"hazard", 3.0},                // Road hazard
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
 * Find the latest file matching a pattern in a directory
 * @param directory - Directory path to search
 * @param prefix - File prefix pattern (e.g., "flow_" or "incident_")
 * @return Full path to latest file, or empty string if not found
 */
inline string find_latest_file(const string& directory, const string& prefix) {
    string latest_file = "";
    time_t latest_time = 0;
    
    // Use system command to find files (portable across Linux/Unix)
    string cmd = "ls -t " + directory + "/" + prefix + "*.csv 2>/dev/null | head -n 1";
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) return "";
    
    char buffer[512];
    if (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        latest_file = string(buffer);
        // Remove trailing newline
        if (!latest_file.empty() && latest_file[latest_file.length() - 1] == '\n') {
            latest_file.erase(latest_file.length() - 1);
        }
    }
    pclose(pipe);
    
    return latest_file;
}

/**
 * Get disruption directory from a base path
 * Extracts the directory containing the data files
 * @param base_path - Path like "/path/to/Main/data/raw/quezon_city_nodes.csv"
 * @return Directory path like "/path/to/Main/data/disruptions"
 */
inline string get_disruptions_base_dir(const string& base_path) {
    size_t last_slash = base_path.find_last_of('/');
    if (last_slash == string::npos) return "";
    
    string parent_dir = base_path.substr(0, last_slash);  // /path/to/Main/data/raw
    last_slash = parent_dir.find_last_of('/');
    if (last_slash == string::npos) return "";
    
    string data_dir = parent_dir.substr(0, last_slash);  // /path/to/Main/data
    return data_dir + "/disruptions";
}

/**
 * Compute disruption metrics based on Table 8 from LazyHC2L Team Guide
 * Priority: Incident data overrides flow data when both exist
 * 
 * Table 8 Logic:
 * - If incident exists: Use incident criticality + jam_factor (if available)
 * - If only flow exists: Use jam_factor only
 * - Speed: Prefer flow_speed_kph > flow_free_flow_kph > highway default
 * - Severity mapping: minor/major/severe/critical → low/medium/high/critical
 */
inline EdgeDisruptionMetrics compute_disruption_metrics(
    const IncidentInfo* incident,
    const TrafficFlowData* flow,
    const string& highway_type,
    distance_t base_distance) {
    
    EdgeDisruptionMetrics metrics;
    metrics.old_weight = base_distance;
    
    // PRIORITY: Incident data overrides flow data
    if (incident && incident->has_incident()) {
        // === INCIDENT-BASED SEVERITY ===
        // Map incident criticality (minor/major/severe/critical) to severity level
        string criticality = incident->criticality;
        
        if (incident->road_closed) {
            // Road closure - effectively block this edge
            metrics.severity_level = "critical";
            metrics.severity_score = 1.0;
            metrics.weight_multiplier = 10000.0;  // Extremely high weight to prevent routing through
        } else if (criticality == "critical") {
            metrics.severity_level = "critical";
            metrics.severity_score = 1.0;
            metrics.weight_multiplier = 100.0;  // Very high weight - strongly avoid
        } else if (criticality == "severe") {
            metrics.severity_level = "high";
            metrics.severity_score = 0.75;
            metrics.weight_multiplier = 10.0;
        } else if (criticality == "major") {
            metrics.severity_level = "medium";
            metrics.severity_score = 0.5;
            metrics.weight_multiplier = 5.0;
        } else if (criticality == "minor") {
            metrics.severity_level = "low";
            metrics.severity_score = 0.25;
            metrics.weight_multiplier = 2.0;
        } else {
            // Unknown criticality - use conservative medium severity
            metrics.severity_level = "medium";
            metrics.severity_score = 0.5;
            metrics.weight_multiplier = 3.0;
        }
        
        // If flow data also available, adjust severity based on jam_factor
        if (flow && flow->jam_factor > 0.0) {
            double jam_factor = flow->jam_factor;
            if (jam_factor >= 8.0) {
                // Heavy traffic + incident = escalate severity
                if (metrics.severity_score < 0.75) metrics.severity_score = 0.75;
                if (metrics.severity_level == "low" || metrics.severity_level == "medium") {
                    metrics.severity_level = "high";
                    metrics.weight_multiplier = max(metrics.weight_multiplier, 5.0);
                }
            } else if (jam_factor >= 5.0) {
                // Medium traffic + incident
                if (metrics.severity_score < 0.5) metrics.severity_score = 0.5;
            }
        }
        
    } else if (flow && flow->jam_factor > 0.0) {
        // === FLOW-ONLY SEVERITY (no incident) ===
        double jam_factor = flow->jam_factor;
        
        if (jam_factor >= 8.0) {
            metrics.severity_level = "high";
            metrics.severity_score = 0.75;
            metrics.weight_multiplier = 4.0;
        } else if (jam_factor >= 5.0) {
            metrics.severity_level = "medium";
            metrics.severity_score = 0.5;
            metrics.weight_multiplier = 2.0;
        } else if (jam_factor >= 2.0) {
            metrics.severity_level = "low";
            metrics.severity_score = 0.25;
            metrics.weight_multiplier = 1.3;
        } else {
            metrics.severity_level = "none";
            metrics.severity_score = 0.0;
            metrics.weight_multiplier = 1.0;
        }
    } else {
        // No disruption data
        metrics.severity_level = "none";
        metrics.severity_score = 0.0;
        metrics.weight_multiplier = 1.0;
    }
    
    // Compute impact metrics
    metrics.new_weight = static_cast<distance_t>(base_distance * metrics.weight_multiplier);
    metrics.impact_score = metrics.severity_score;
    
    // Estimate time impact based on speed reduction
    // Assume default highway speed and compute extra time from multiplier
    double default_speed_kph = get_highway_speed(highway_type);
    double distance_km = base_distance / 1000.0;
    double base_time_seconds = (distance_km / default_speed_kph) * 3600.0;
    double new_time_seconds = base_time_seconds * metrics.weight_multiplier;
    metrics.time_impact_seconds = new_time_seconds - base_time_seconds;
    
    return metrics;
}

/**
 * Load and cache disruption data from flow and incident CSV files
 * NEW: Reads from separate flow/ and incidents/ directories
 * Uses file modification time to detect changes
 */
extern map<pair<NodeID, NodeID>, string> g_highway_types;  // Highway types (defined in routing API files)

inline bool load_disruptions_with_cache(
    const string& disruption_file,
    map<pair<NodeID, NodeID>, IncidentInfo>& incidents_out,
    map<pair<NodeID, NodeID>, TrafficFlowData>& flow_out,
    const map<NodeID, vector<Neighbor>>& adj_list,
    const map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries = map<pair<NodeID, NodeID>, EdgeGeometry>()) {
    
    // NEW: disruption_file is now the base directory path
    // We find the latest flow and incident files from their respective directories
    string disruptions_base = disruption_file;
    
    // If disruption_file points to an old file format, extract base directory
    if (disruptions_base.find("traffic_") != string::npos || 
        disruptions_base.find(".csv") != string::npos ||
        disruptions_base.find(".gr") != string::npos) {
        disruptions_base = get_disruptions_base_dir(disruptions_base);
    }
    
    string flow_dir = disruptions_base + "/flow";
    string incidents_dir = disruptions_base + "/incidents";
    
    cerr << "🔍 Loading disruptions from:" << endl;
    cerr << "   Flow dir: " << flow_dir << endl;
    cerr << "   Incidents dir: " << incidents_dir << endl;
    
    // Find latest flow and incident files
    string latest_flow_file = find_latest_file(flow_dir, "flow_");
    string latest_incident_file = find_latest_file(incidents_dir, "incident_");
    
    cerr << "   Latest flow: " << (latest_flow_file.empty() ? "none" : latest_flow_file) << endl;
    cerr << "   Latest incident: " << (latest_incident_file.empty() ? "none" : latest_incident_file) << endl;
    
    // Build cache key from both files
    string cache_key = latest_flow_file + "|" + latest_incident_file;
    
    // Check if cache is valid for both files
    if (g_disruption_cache.is_valid(cache_key)) {
        // SILENT CACHE HIT - don't spam logs on every route calculation
        incidents_out = g_disruption_cache.incidents;
        flow_out = g_disruption_cache.flow_data;
        return true;
    }
    
    // Cache invalid or files changed - reload
    cerr << "🔄 Loading new flow and incident data" << endl;
    
    incidents_out.clear();
    flow_out.clear();
    
    int total_flow = 0;
    int total_incidents = 0;
    int closures = 0;
    
    // === LOAD FLOW DATA ===
    if (!latest_flow_file.empty()) {
        ifstream flow_file(latest_flow_file);
        if (flow_file.is_open()) {
            cerr << "📊 Loading flow data from: " << latest_flow_file << endl;
            string line;
            int source_col = -1, target_col = -1, speed_col = -1, freeflow_col = -1, jam_col = -1;
            int flow_confidence_col = -1, flow_traversability_col = -1;
            
            // Parse flow CSV header
            if (getline(flow_file, line)) {
                vector<string> headers = parse_csv_line(line);
                for (size_t i = 0; i < headers.size(); i++) {
                    string h = headers[i];
                    h.erase(0, h.find_first_not_of(" \t\n\r"));
                    h.erase(h.find_last_not_of(" \t\n\r") + 1);
                    
                    if (h == "source") source_col = i;
                    else if (h == "target") target_col = i;
                    else if (h == "flow_speed_kph") speed_col = i;
                    else if (h == "flow_free_flow_kph") freeflow_col = i;
                    else if (h == "flow_jam_factor") jam_col = i;
                    else if (h == "flow_confidence") flow_confidence_col = i;
                    else if (h == "flow_traversability") flow_traversability_col = i;
                }
            }
            
            // Parse flow data rows
            while (getline(flow_file, line)) {
                if (line.empty()) continue;
                
                vector<string> fields = parse_csv_line(line);
                if (source_col < 0 || target_col < 0 || 
                    (int)fields.size() <= max(source_col, target_col)) continue;
                
                try {
                    NodeID source = stoul(fields[source_col]);
                    NodeID target = stoul(fields[target_col]);
                    
                    double current_speed = (speed_col >= 0 && speed_col < (int)fields.size()) 
                        ? stod(fields[speed_col]) : 0.0;
                    double free_flow_speed = (freeflow_col >= 0 && freeflow_col < (int)fields.size()) 
                        ? stod(fields[freeflow_col]) : 50.0;
                    double jam_factor = (jam_col >= 0 && jam_col < (int)fields.size()) 
                        ? stod(fields[jam_col]) : 0.0;
                    double flow_confidence = (flow_confidence_col >= 0 && flow_confidence_col < (int)fields.size()) 
                        ? stod(fields[flow_confidence_col]) : 0.99;
                    string flow_traversability = (flow_traversability_col >= 0 && flow_traversability_col < (int)fields.size()) 
                        ? fields[flow_traversability_col] : "open";
                    
                    auto edge_key = make_pair(source, target);
                    TrafficFlowData flow = get_flow_color(jam_factor, current_speed, free_flow_speed);
                    flow.confidence = flow_confidence;
                    flow.traversability = flow_traversability;
                    flow_out[edge_key] = flow;
                    total_flow++;
                } catch (const exception& e) {
                    continue;
                }
            }
            flow_file.close();
            cerr << "   ✅ Loaded " << total_flow << " flow edges" << endl;
        }
    }
    
    // === LOAD INCIDENT DATA ===
    if (!latest_incident_file.empty()) {
        ifstream incident_file(latest_incident_file);
        if (incident_file.is_open()) {
            cerr << "🚨 Loading incident data from: " << latest_incident_file << endl;
            string line;
            int source_col = -1, target_col = -1;
            int incident_id_col = -1, incident_type_col = -1, incident_criticality_col = -1;
            int incident_description_col = -1, incident_road_closed_col = -1;
            int incident_start_time_col = -1, incident_end_time_col = -1;
            
            // Parse incident CSV header
            if (getline(incident_file, line)) {
                vector<string> headers = parse_csv_line(line);
                for (size_t i = 0; i < headers.size(); i++) {
                    string h = headers[i];
                    h.erase(0, h.find_first_not_of(" \t\n\r"));
                    h.erase(h.find_last_not_of(" \t\n\r") + 1);
                    
                    if (h == "source") source_col = i;
                    else if (h == "target") target_col = i;
                    else if (h == "incident_id") incident_id_col = i;
                    else if (h == "incident_type") incident_type_col = i;
                    else if (h == "incident_criticality") incident_criticality_col = i;
                    else if (h == "incident_description") incident_description_col = i;
                    else if (h == "incident_road_closed") incident_road_closed_col = i;
                    else if (h == "incident_start_time") incident_start_time_col = i;
                    else if (h == "incident_end_time") incident_end_time_col = i;
                }
            }
            
            // Parse incident data rows
            while (getline(incident_file, line)) {
                if (line.empty()) continue;
                
                vector<string> fields = parse_csv_line(line);
                if (source_col < 0 || target_col < 0 || 
                    (int)fields.size() <= max(source_col, target_col)) continue;
                
                try {
                    NodeID source = stoul(fields[source_col]);
                    NodeID target = stoul(fields[target_col]);
                    
                    IncidentInfo incident;
                    incident.id = (incident_id_col >= 0 && incident_id_col < (int)fields.size()) 
                        ? fields[incident_id_col] : "";
                    incident.type = (incident_type_col >= 0 && incident_type_col < (int)fields.size()) 
                        ? fields[incident_type_col] : "";
                    incident.criticality = (incident_criticality_col >= 0 && incident_criticality_col < (int)fields.size()) 
                        ? fields[incident_criticality_col] : "";
                    incident.description = (incident_description_col >= 0 && incident_description_col < (int)fields.size()) 
                        ? fields[incident_description_col] : "";
                    incident.start_time = (incident_start_time_col >= 0 && incident_start_time_col < (int)fields.size()) 
                        ? fields[incident_start_time_col] : "";
                    incident.end_time = (incident_end_time_col >= 0 && incident_end_time_col < (int)fields.size()) 
                        ? fields[incident_end_time_col] : "";
                    
                    if (incident_road_closed_col >= 0 && incident_road_closed_col < (int)fields.size()) {
                        string closed_str = fields[incident_road_closed_col];
                        incident.road_closed = (closed_str == "True" || closed_str == "true" || closed_str == "1");
                    }
                    
                    auto edge_key = make_pair(source, target);
                    if (incident.has_incident() || incident.road_closed) {
                        incidents_out[edge_key] = incident;
                        total_incidents++;
                        if (incident.road_closed) closures++;
                    }
                } catch (const exception& e) {
                    continue;
                }
            }
            incident_file.close();
            cerr << "   ✅ Loaded " << total_incidents << " incidents (" << closures << " closures)" << endl;
        }
    }
    
    // === COMPUTE DISRUPTION METRICS ===
    // PRIORITY: Incidents override flow data on the same edge
    map<pair<NodeID, NodeID>, EdgeDisruptionMetrics> disruption_metrics_out;
    
    // Process incidents first (higher priority)
    for (const auto& [edge_key, incident] : incidents_out) {
        const IncidentInfo* incident_ptr = &incident;
        
        // Check if flow data also exists for this edge
        // If yes, pass it to help refine severity, but incident takes priority
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
    
    // Process flow data ONLY for edges without incidents
    for (const auto& [edge_key, flow] : flow_out) {
        // Skip if incident already processed for this edge (incident priority)
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
    
    // Update cache
    g_disruption_cache.file_path = cache_key;
    g_disruption_cache.file_modified_time = time(nullptr);
    g_disruption_cache.incidents = incidents_out;
    g_disruption_cache.flow_data = flow_out;
    g_disruption_cache.disruption_metrics = disruption_metrics_out;
    g_disruption_cache.total_incidents = total_flow + total_incidents;
    g_disruption_cache.closures = closures;
    g_disruption_cache.active_disruptions = total_flow + total_incidents - closures;
    
    cerr << "✅ Loaded flow (" << total_flow << ") + incidents (" << total_incidents 
         << " with " << closures << " closures)" << endl;
    
    return true;
}


// ============================================================
// ETA CALCULATION FUNCTIONS
// ============================================================

// Calculate ETA in seconds using actual traffic flow data from edges
double calculate_eta_with_disruption(
    const vector<NodeID>& path,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<pair<NodeID, NodeID>, IncidentInfo>& incident_data,
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
        
        // Check if edge is closed by incident (impassable = infinite time)
        if (incident_data.count(edge_key)) {
            const auto& incident = incident_data.at(edge_key);
            if (incident.road_closed) {
                // Edge is closed, add extreme penalty
                total_eta += 999999.0; // Very large time to discourage route
                continue;
            }
        }
        
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

// Overload for backward compatibility (without incident_data)
inline double calculate_eta_with_disruption(
   const vector<NodeID>& path,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<NodeID, GPSCoordinate>& coordinates,
    int hour_of_day = -1) {
    
    // Create empty incident_data map for backward compatibility
    map<pair<NodeID, NodeID>, IncidentInfo> empty_incident_data;
    return calculate_eta_with_disruption(path, flow_data, empty_incident_data, coordinates, hour_of_day);
}


// ============================================================
// DISRUPTION WEIGHT CALCULATION
// ============================================================

/**
 * Calculate disruption-aware weight for routing algorithms
 * Combines traffic flow and incident data to compute edge cost
 * 
 * @param from Source node ID
 * @param to Target node ID
 * @param base_distance Base edge distance/weight
 * @param flow Traffic flow data (optional)
 * @param incident Incident data (optional)
 * @param highway_type Highway classification
 * @param tau_threshold Sensitivity threshold (0.0-1.0, default 1.0)
 *                      1.0 = full weight, <1.0 = reduced impact
 * @return Adjusted edge weight considering disruptions
 */
inline distance_t calculate_disruption_weight(
    NodeID from, NodeID to,
    distance_t base_distance,
    const TrafficFlowData* flow,
    const IncidentInfo* incident,
    const string& highway_type,
    double tau_threshold = 1.0) {
    
    // PRIORITY 0: Closed roads - return infinity to block routing
    if (incident && incident->road_closed) {
        return road_network::infinity;
    }
    
    // Start with base distance
    double weight = static_cast<double>(base_distance);
    
    // PRIORITY 1: Check incident severity - critical incidents should be heavily penalized
    if (incident && incident->has_incident()) {
        // Use compute_disruption_metrics for proper severity calculation
        EdgeDisruptionMetrics metrics = compute_disruption_metrics(
            incident, flow, highway_type, base_distance
        );
        
        // For critical severity or very high weight multipliers, return near-infinity
        if (metrics.severity_level == "critical" || metrics.weight_multiplier >= 100.0) {
            return road_network::infinity;
        }
        
        // Apply the computed weight multiplier
        weight = static_cast<double>(metrics.new_weight);
        
    } else if (flow && flow->jam_factor > 0.0) {
        // PRIORITY 2: Flow-only penalty (no incident)
        // jam_factor: 0.0 = free, 10.0 = blocked
        double jam_factor_normalized = flow->jam_factor / 10.0;  // 0.0 to 1.0
        double flow_multiplier = 1.0 + (jam_factor_normalized * 4.0);  // 1.0x to 5.0x
        weight *= flow_multiplier;
    }
    
    // Apply tau threshold as sensitivity multiplier (for HC2L adaptive routing)
    // tau = 0.0: Use only base distance (ignore traffic)
    // tau = 1.0: Use full traffic-adjusted weight
    if (tau_threshold < 1.0) {
        double adjustment = base_distance + (weight - base_distance) * tau_threshold;
        weight = adjustment;
    }
    
    // Ensure weight doesn't exceed infinity
    if (weight >= road_network::infinity) {
        return road_network::infinity;
    }
    
    return static_cast<distance_t>(weight);
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
    const map<pair<NodeID, NodeID>, IncidentInfo>& incident_data,
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
                    
                    // *** APPLY DISRUPTION WEIGHTS (FLOW + INCIDENTS) ***
                    auto edge_key = make_pair(u, v);
                    const TrafficFlowData* flow_ptr = nullptr;
                    const IncidentInfo* incident_ptr = nullptr;
                    
                    if (flow_data.count(edge_key)) {
                        flow_ptr = &flow_data.at(edge_key);
                    }
                    if (incident_data.count(edge_key)) {
                        incident_ptr = &incident_data.at(edge_key);
                    }
                    
                    // Apply disruption weight (accounts for both flow and incidents)
                    if (flow_ptr || incident_ptr) {
                        string highway_type = "unknown";
                        if (g_highway_types.count(edge_key)) {
                            highway_type = g_highway_types.at(edge_key);
                        }
                        edge_cost = calculate_disruption_weight(
                            u, v,
                            neighbor.distance,
                            flow_ptr,
                            incident_ptr,
                            highway_type
                        );
                    }
                    
                    // Apply penalty to used edges (encourages diverse alternatives)
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
        route.eta_seconds = calculate_eta_with_disruption(path, flow_data, incident_data, coordinates);
        
        // Calculate average jam factor (only from flow data)
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


// ============================================================
// USER-REPORTED DISRUPTIONS LOADER
// ============================================================

/**
 * Load user-reported disruptions from CSV file
 * 
 * This function loads custom disruptions created by users via the UI.
 * User disruptions are stored in timestamped files (user_incident_YYYYMMDDTHHMMSS.csv)
 * in the disruptions/user_incident/ folder, similar to flow and incident files.
 * 
 * The function automatically finds and loads the LATEST user_incident_*.csv file.
 * 
 * CSV Format (from Main/data/disruptions/user_incident/user_incident_*.csv):
 * source,target,lat,lng,snapped_lat,snapped_lng,target_lat,target_lon,
 * road_name,highway_type,speed_kph,freeFlow_kph,jamFactor,isClosed,
 * incident_type,severity,description,report_id,timestamp
 * 
 * @param disruption_dir - Path to disruptions directory (contains user_incident/ subfolder)
 * @param flow_out - Output map for flow data (will be merged)
 * @param incident_out - Output map for incident data (will be merged)
 * @return Number of user disruptions loaded
 */
inline int load_user_reported_disruptions(
    const string& disruption_dir,
    map<pair<NodeID, NodeID>, TrafficFlowData>& flow_out,
    map<pair<NodeID, NodeID>, IncidentInfo>& incident_out) {
    
    if (disruption_dir.empty()) {
        cerr << "   ℹ️  No disruption directory specified" << endl;
        return 0;
    }
    
    // Find latest user_incident_*.csv file in user_incident subfolder
    string user_incident_dir = disruption_dir + "/user_incident";
    
    // Check if user_incident directory exists
    struct stat dir_stat;
    if (stat(user_incident_dir.c_str(), &dir_stat) != 0 || !S_ISDIR(dir_stat.st_mode)) {
        cerr << "   ℹ️  User incident directory not found: " << user_incident_dir << endl;
        return 0;
    }
    
    // Find all user_incident_*.csv files and get the latest one
    string latest_file = "";
    time_t latest_time = 0;
    
    DIR* dir = opendir(user_incident_dir.c_str());
    if (dir != nullptr) {
        struct dirent* entry;
        while ((entry = readdir(dir)) != nullptr) {
            string filename = entry->d_name;
            if (filename.find("user_incident_") == 0 && filename.find(".csv") != string::npos) {
                string full_path = user_incident_dir + "/" + filename;
                struct stat file_stat;
                if (stat(full_path.c_str(), &file_stat) == 0) {
                    if (file_stat.st_mtime > latest_time) {
                        latest_time = file_stat.st_mtime;
                        latest_file = full_path;
                    }
                }
            }
        }
        closedir(dir);
    }
    
    if (latest_file.empty()) {
        cerr << "   ℹ️  No user_incident files found in: " << user_incident_dir << endl;
        return 0;
    }
    
    // Check if file exists
    struct stat buffer;
    if (stat(latest_file.c_str(), &buffer) != 0) {
        cerr << "   ⚠️  User disruption file not found: " << latest_file << endl;
        return 0;
    }
    
    ifstream file(latest_file);
    if (!file.is_open()) {
        cerr << "   ⚠️  Cannot open user disruption file: " << latest_file << endl;
        return 0;
    }
    
    cerr << "👤 Loading user-reported disruptions from: " << latest_file << endl;
    
    string line;
    int source_col = -1, target_col = -1;
    int source_lat_col = -1, source_lon_col = -1;
    int target_lat_col = -1, target_lon_col = -1;
    int incident_id_col = -1, incident_type_col = -1, incident_criticality_col = -1;
    int incident_description_col = -1, incident_road_closed_col = -1;
    int incident_start_time_col = -1, incident_end_time_col = -1;
    int highway_type_col = -1, road_name_col = -1;
    
    // Parse CSV header
    if (getline(file, line)) {
        vector<string> headers = parse_csv_line(line);
        for (size_t i = 0; i < headers.size(); i++) {
            string h = headers[i];
            // Trim whitespace
            h.erase(0, h.find_first_not_of(" \t\n\r"));
            h.erase(h.find_last_not_of(" \t\n\r") + 1);
            
            if (h == "source") source_col = i;
            else if (h == "target") target_col = i;
            else if (h == "source_lat") source_lat_col = i;
            else if (h == "source_lon") source_lon_col = i;
            else if (h == "target_lat") target_lat_col = i;
            else if (h == "target_lon") target_lon_col = i;
            else if (h == "incident_id") incident_id_col = i;
            else if (h == "incident_type") incident_type_col = i;
            else if (h == "incident_criticality") incident_criticality_col = i;
            else if (h == "incident_description") incident_description_col = i;
            else if (h == "incident_road_closed") incident_road_closed_col = i;
            else if (h == "incident_start_time") incident_start_time_col = i;
            else if (h == "incident_end_time") incident_end_time_col = i;
            else if (h == "highway_type") highway_type_col = i;
            else if (h == "road_name") road_name_col = i;
        }
    }
    
    if (source_col < 0 || target_col < 0) {
        cerr << "   ❌ Invalid user disruption CSV: missing 'source' or 'target' columns" << endl;
        file.close();
        return 0;
    }
    
    int loaded_count = 0;
    int closures_count = 0;
    
    // Parse data rows
    while (getline(file, line)) {
        if (line.empty()) continue;
        
        vector<string> fields = parse_csv_line(line);
        if ((int)fields.size() <= max(source_col, target_col)) continue;
        
        try {
            NodeID source = stoul(fields[source_col]);
            NodeID target = stoul(fields[target_col]);
            
            if (source == 0 || target == 0) continue; // Skip invalid edges
            
            auto edge_key = make_pair(source, target);
            
            // Extract incident data from user report
            bool is_closed = false;
            if (incident_road_closed_col >= 0 && incident_road_closed_col < (int)fields.size()) {
                string closed_str = fields[incident_road_closed_col];
                is_closed = (closed_str == "true" || closed_str == "True" || closed_str == "1");
            }
            
            string incident_type = (incident_type_col >= 0 && incident_type_col < (int)fields.size()) 
                ? fields[incident_type_col] : "user-incident";
            string criticality = (incident_criticality_col >= 0 && incident_criticality_col < (int)fields.size()) 
                ? fields[incident_criticality_col] : "minor";
            string description = (incident_description_col >= 0 && incident_description_col < (int)fields.size()) 
                ? fields[incident_description_col] : "User reported incident";
            string incident_id = (incident_id_col >= 0 && incident_id_col < (int)fields.size()) 
                ? fields[incident_id_col] : "";
            string road_name = (road_name_col >= 0 && road_name_col < (int)fields.size()) 
                ? fields[road_name_col] : "Unknown Road";
            string start_time = (incident_start_time_col >= 0 && incident_start_time_col < (int)fields.size()) 
                ? fields[incident_start_time_col] : "";
            string end_time = (incident_end_time_col >= 0 && incident_end_time_col < (int)fields.size()) 
                ? fields[incident_end_time_col] : "";
            
            // Trim whitespace from string fields
            incident_type.erase(0, incident_type.find_first_not_of(" \t\n\r"));
            incident_type.erase(incident_type.find_last_not_of(" \t\n\r") + 1);
            criticality.erase(0, criticality.find_first_not_of(" \t\n\r"));
            criticality.erase(criticality.find_last_not_of(" \t\n\r") + 1);
            
            // Create incident info for this user incident
            IncidentInfo incident;
            incident.id = incident_id;
            incident.type = incident_type;
            incident.criticality = criticality;
            incident.description = description;
            incident.road_closed = is_closed;
            incident.start_time = start_time;
            incident.end_time = end_time;
            
            // MERGE STRATEGY: If an incident already exists for this edge (from HERE API),
            // keep the MORE CRITICAL one or merge them
            if (incident_out.count(edge_key)) {
                IncidentInfo& existing = incident_out[edge_key];
                
                // Priority 1: Road closure always takes precedence
                if (is_closed || existing.road_closed) {
                    incident.road_closed = true;
                }
                
                // Priority 2: Keep higher criticality
                map<string, int> criticality_rank = {
                    {"critical", 4}, {"severe", 3}, {"major", 2}, {"minor", 1}, {"", 0}
                };
                int existing_rank = criticality_rank.count(existing.criticality) 
                    ? criticality_rank[existing.criticality] : 0;
                int new_rank = criticality_rank.count(criticality) 
                    ? criticality_rank[criticality] : 0;
                
                if (new_rank > existing_rank) {
                    // User incident is more critical - use it but keep existing ID if present
                    if (existing.id.empty()) {
                        existing.id = incident.id;
                    }
                    existing.type = incident.type;
                    existing.criticality = incident.criticality;
                    existing.description = incident.description;
                    existing.road_closed = incident.road_closed;
                } else if (new_rank == existing_rank) {
                    // Same criticality - combine descriptions
                    if (!incident.description.empty() && existing.description.find(incident.description) == string::npos) {
                        existing.description += " | " + incident.description;
                    }
                    existing.road_closed = existing.road_closed || incident.road_closed;
                }
                // If new_rank < existing_rank, keep existing (more critical)
            } else {
                // No existing incident - add this one
                incident_out[edge_key] = incident;
            }
            
            loaded_count++;
            if (is_closed) {
                closures_count++;
            }
            
        } catch (const exception& e) {
            cerr << "   ⚠️  Skipping invalid user disruption row: " << e.what() << endl;
            continue;
        }
    }
    
    file.close();
    
    // Update global cache with user disruption counts
    if (loaded_count > 0) {
        g_disruption_cache.total_incidents += loaded_count;
        g_disruption_cache.closures += closures_count;
        g_disruption_cache.active_disruptions += (loaded_count - closures_count);
        
        cerr << "   ✅ Loaded " << loaded_count << " user-reported disruptions";
        if (closures_count > 0) {
            cerr << " (" << closures_count << " closures)";
        }
        cerr << endl;
    } else {
        cerr << "   ℹ️  No user disruptions found in file" << endl;
    }
    
    return loaded_count;
}


#endif // ROUTING_UTILS_H
