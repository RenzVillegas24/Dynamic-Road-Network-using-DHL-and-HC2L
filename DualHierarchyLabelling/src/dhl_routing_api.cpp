/*
 * DHL Routing JSON API - REWRITTEN CLEAN VERSION
 * 
 * SIMPLIFIED ALGORITHM:
 *   1. Use DHL labels to compute distance between all candidate node pairs
 *   2. Select best routing endpoints based on one-way constraints
 *   3. Use simple Dijkstra to find the path
 *   4. Ensure snap edges are included in output
 *   5. Clip geometry at snap points
 * 
 * Algorithm: Dual-Hierarchy Labelling
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

using namespace road_network;
using namespace std;

// Helper structure for edge with geometry
struct EdgeGeometry {
    NodeID source;
    NodeID target;
    distance_t length;
    vector<pair<double, double>> coords; // lon, lat pairs
    
    EdgeGeometry() : source(0), target(0), length(0) {}
};

// Helper structure for GPS coordinates
struct GPSCoordinate {
    double latitude;
    double longitude;
    NodeID node_id;
    
    GPSCoordinate() : latitude(0), longitude(0), node_id(0) {}
    GPSCoordinate(double lat, double lng, NodeID id) : latitude(lat), longitude(lng), node_id(id) {}
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
map<NodeID, GPSCoordinate> load_node_coordinates(const string& filename) {
    map<NodeID, GPSCoordinate> coordinates;
    ifstream file(filename);
    
    if (!file.is_open()) {
        cerr << "Warning: Could not open " << filename << endl;
        return coordinates;
    }
    
    string line;
    getline(file, line); // Skip header
    
    while (getline(file, line)) {
        stringstream ss(line);
        string node_id_str, lat_str, lng_str;
        
        if (getline(ss, node_id_str, ',') &&
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
        
        if (fields.size() < 7) {
            continue;
        }
        
        try {
            NodeID source = stoul(fields[0]);
            NodeID target = stoul(fields[1]);
            distance_t length = static_cast<distance_t>(stod(fields[2]));
            string oneway_str = fields[5];
            string geometry_json = fields[6];
            
            // DEBUG: Log raw geometry field for first few edges
            static int edge_count = 0;
            if (edge_count < 3) {
                cerr << "DEBUG: Raw geometry field for edge " << source << "→" << target << ":" << endl;
                cerr << "  Length: " << geometry_json.length() << " chars" << endl;
                cerr << "  First 100 chars: " << geometry_json.substr(0, min(size_t(100), geometry_json.length())) << endl;
                cerr << "  First char: '" << geometry_json.front() << "' (code " << (int)geometry_json.front() << ")" << endl;
                cerr << "  Last char: '" << geometry_json.back() << "' (code " << (int)geometry_json.back() << ")" << endl;
                edge_count++;
            }
            
            // Remove surrounding quotes from geometry JSON if present
            if (!geometry_json.empty() && geometry_json.front() == '"' && geometry_json.back() == '"') {
                geometry_json = geometry_json.substr(1, geometry_json.length() - 2);
                cerr << "  After quote removal: " << geometry_json.substr(0, min(size_t(100), geometry_json.length())) << endl;
            }
            
            // Parse geometry JSON - WITH VALIDATION AND DEBUGGING
            vector<pair<double, double>> coords;
            int parse_error_count = 0;
            int success_count = 0;
            
            if (!geometry_json.empty() && geometry_json != "[]") {
                // Format is: [[lon1, lat1], [lon2, lat2], ...]
                // Find all inner coordinate pairs [lon, lat]
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
                    
                    // Parse "lon, lat" or "lon,lat" 
                    size_t comma = pair_str.find(',');
                    if (comma != string::npos) {
                        try {
                            string lon_str = pair_str.substr(0, comma);
                            string lat_str = pair_str.substr(comma + 1);
                            
                            // Trim whitespace
                            lon_str.erase(0, lon_str.find_first_not_of(" \t"));
                            lon_str.erase(lon_str.find_last_not_of(" \t") + 1);
                            lat_str.erase(0, lat_str.find_first_not_of(" \t"));
                            lat_str.erase(lat_str.find_last_not_of(" \t") + 1);
                            
                            double lon = stod(lon_str);
                            double lat = stod(lat_str);
                            
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
            } else if (oneway == -1) {
                // One-way reverse only
                adj_list[target].push_back(Neighbor(source, length));
                // Also store reverse geometry
                EdgeGeometry rev_geom = geom;
                rev_geom.source = target;
                rev_geom.target = source;
                reverse(rev_geom.coords.begin(), rev_geom.coords.end());
                edge_geometries[{target, source}] = rev_geom;
            } else {
                // Bidirectional
                adj_list[source].push_back(Neighbor(target, length));
                adj_list[target].push_back(Neighbor(source, length));
                
                // Store reverse geometry
                EdgeGeometry rev_geom = geom;
                rev_geom.source = target;
                rev_geom.target = source;
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

// SIMPLIFIED PATH FINDING: Just use Dijkstra with the road network
// CRITICAL: This function MUST return ALL intermediate nodes on the shortest path
// including intersection nodes at sharp turns and road junctions
vector<NodeID> find_shortest_path(NodeID start, NodeID dest, const map<NodeID, vector<Neighbor>>& adj_list) {
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
                distance_t new_dist = dist[u] + neighbor.distance;
                
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
    
    // DEBUG: Log the path for verification
    if (path.size() > 0) {
        cerr << "✓ Path found with " << path.size() << " nodes: ";
        for (size_t i = 0; i < path.size() && i < 10; i++) {
            cerr << path[i];
            if (i < min(size_t(9), path.size() - 1)) cerr << " → ";
        }
        if (path.size() > 10) cerr << " ... (" << (path.size() - 10) << " more nodes)";
        cerr << endl;
    }
    
    return path;
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
                         const string& disruption_dir = "", double tau_threshold = 0.5) {
    
    cout << "{" << endl;
    cout << "  \"success\": " << (success ? "true" : "false") << "," << endl;
    
    if (!success) {
        cout << "  \"error\": \"" << error_message << "\"" << endl;
    } else {
        cout << "  \"algorithm\": \"DHL (Dual-Hierarchy Labelling)\"," << endl;
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
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << endl;
        cout << "  }," << endl;
        
        cout << "  \"snap_edges\": {" << endl;
        cout << "    \"start_edge\": {" << endl;
        cout << "    \"source\": " << start_edge_source << "," << endl;
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
        cout << "    \"dest_node\": " << dest_node << "," << endl;
        
        if (coordinates.count(start_node)) {
            auto& coord = coordinates.at(start_node);
            cout << "    \"start_node_lat\": " << fixed << setprecision(6) << coord.latitude << "," << endl;
            cout << "    \"start_node_lng\": " << fixed << setprecision(6) << coord.longitude << "," << endl;
        }
        
        if (coordinates.count(dest_node)) {
            auto& coord = coordinates.at(dest_node);
            cout << "    \"dest_node_lat\": " << fixed << setprecision(6) << coord.latitude << "," << endl;
            cout << "    \"dest_node_lng\": " << fixed << setprecision(6) << coord.longitude << endl;
        }
        
        cout << "  }," << endl;
        
        cout << "  \"metrics\": {" << endl;
        cout << "    \"total_distance_units\": " << distance << "," << endl;
        cout << "    \"query_time_ms\": " << fixed << setprecision(3) << query_time_ms << "," << endl;
        cout << "    \"path_length\": " << path.size() << "," << endl;
        cout << "    \"disruption_dir\": \"" << disruption_dir << "\"," << endl;
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << "," << endl;
        cout << "    \"interpolation_used\": false," << endl;
        
        // Calculate and add distance and ETA metrics
        double calculated_distance = calculate_route_distance(path, coordinates);
        double eta_seconds = calculate_eta_seconds(calculated_distance, 5.0);
        string eta_formatted = format_eta_time(eta_seconds);
        
        cout << "    \"calculated_distance_meters\": " << fixed << setprecision(1) << calculated_distance << "," << endl;
        cout << "    \"calculated_distance_km\": " << fixed << setprecision(2) << (calculated_distance / 1000.0) << "," << endl;
        cout << "    \"eta_seconds\": " << fixed << setprecision(0) << eta_seconds << "," << endl;
        cout << "    \"eta_formatted\": \"" << eta_formatted << "\"" << endl;
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
        
        cout << "    \"complete_trace\": \"DHL Route (";
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
            cout << "]" << endl;
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
            cout << "        \"coordinates\": [";
            
            auto edge_key = make_pair(from, to);
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
            
            cout << "]" << endl;
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
            cout << "]" << endl;
            cout << "      }" << endl;
        }
        
        cout << "    ]" << endl;
        
        cout << "  }" << endl;
    }
    
    cout << "}" << endl;
}

int main(int argc, char* argv[]) {
    if (argc != 20) {
        output_json_response(false, "Invalid arguments. Usage: dhl_routing_api <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> <start_edge_source> <start_edge_target> <start_edge_oneway> <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> <dest_edge_source> <dest_edge_target> <dest_edge_oneway> <disruption_dir> <tau_threshold> <nodes_csv> <edges_csv> <index_file>");
        return 1;
    }
    
    try {
        // Parse arguments
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
        
        string disruption_dir = argv[15];
        double tau_threshold = stod(argv[16]);
        string nodes_csv = argv[17];
        string edges_csv = argv[18];
        string index_file = argv[19];
        
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
        
        // Load DHL index
        ifstream index_stream(index_file, ios::binary);
        if (!index_stream.is_open()) {
            output_json_response(false, "Failed to open index file");
            return 1;
        }
        ContractionIndex ci(index_stream);
        index_stream.close();
        
        // Determine routing endpoints based on one-way constraints
        vector<NodeID> start_candidates, dest_candidates;
        
        // Start edge candidates
        if (start_edge_oneway == 1) {
            start_candidates.push_back(start_edge_target); // Exit from target
        } else if (start_edge_oneway == -1) {
            start_candidates.push_back(start_edge_source); // Exit from source
        } else {
            start_candidates.push_back(start_edge_source);
            start_candidates.push_back(start_edge_target);
        }
        
        // Dest edge candidates
        if (dest_edge_oneway == 1) {
            dest_candidates.push_back(dest_edge_source); // Arrive at source
        } else if (dest_edge_oneway == -1) {
            dest_candidates.push_back(dest_edge_target); // Arrive at target
        } else {
            dest_candidates.push_back(dest_edge_source);
            dest_candidates.push_back(dest_edge_target);
        }
        
        // Find best route using DHL labels
        auto start_time = chrono::high_resolution_clock::now();
        
        distance_t best_distance = numeric_limits<distance_t>::max();
        NodeID best_start = 0, best_dest = 0;
        
        for (NodeID s : start_candidates) {
            for (NodeID d : dest_candidates) {
                distance_t dist = ci.get_distance(s, d);
                if (dist < best_distance) {
                    best_distance = dist;
                    best_start = s;
                    best_dest = d;
                }
            }
        }
        
        auto end_time = chrono::high_resolution_clock::now();
        double query_time_ms = chrono::duration<double, milli>(end_time - start_time).count();
        
        if (best_start == 0 || best_dest == 0) {
            output_json_response(false, "No valid path found");
            return 1;
        }
        
        // Find actual path using Dijkstra
        vector<NodeID> path = find_shortest_path(best_start, best_dest, adj_list);
        
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
            
            // Prepend start edge if needed
            NodeID first = path[0];
            bool start_edge_present = false;
            if (path.size() >= 2) {
                NodeID second = path[1];
                start_edge_present = (first == start_edge_source && second == start_edge_target) ||
                                   (first == start_edge_target && second == start_edge_source);
            }
            
            if (!start_edge_present) {
                // Add the other endpoint to create the edge
                if (first == start_edge_source) {
                    path.insert(path.begin(), start_edge_target);
                } else if (first == start_edge_target) {
                    path.insert(path.begin(), start_edge_source);
                } else {
                    // Path doesn't start on snap edge - add both nodes
                    path.insert(path.begin(), start_edge_target);
                    path.insert(path.begin(), start_edge_source);
                }
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
                // Add the other endpoint to create the edge
                if (last == dest_edge_source) {
                    path.push_back(dest_edge_target);
                } else if (last == dest_edge_target) {
                    path.push_back(dest_edge_source);
                } else {
                    // Path doesn't end on snap edge - add both nodes
                    path.push_back(dest_edge_source);
                    path.push_back(dest_edge_target);
                }
            }
        }
        
        // Output result
        output_json_response(true, "", best_start, best_dest,
                           start_pin_lat, start_pin_lng, start_snap_lat, start_snap_lng,
                           dest_pin_lat, dest_pin_lng, dest_snap_lat, dest_snap_lng,
                           start_edge_source, start_edge_target, start_edge_oneway,
                           dest_edge_source, dest_edge_target, dest_edge_oneway,
                           best_distance, query_time_ms, path, coordinates,
                           edge_geometries, disruption_dir, tau_threshold);
        
        return 0;
        
    } catch (const exception& e) {
        output_json_response(false, string("Exception: ") + e.what());
        return 1;
    }
}
