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
            
            // Parse geometry JSON
            vector<pair<double, double>> coords;
            if (!geometry_json.empty() && geometry_json != "[]") {
                size_t start = 0;
                while ((start = geometry_json.find('[', start)) != string::npos) {
                    size_t end = geometry_json.find(']', start);
                    if (end == string::npos) break;
                    
                    string pair_str = geometry_json.substr(start + 1, end - start - 1);
                    size_t comma = pair_str.find(',');
                    if (comma != string::npos) {
                        try {
                            double lon = stod(pair_str.substr(0, comma));
                            double lat = stod(pair_str.substr(comma + 1));
                            coords.push_back({lon, lat});
                        } catch (...) {}
                    }
                    start = end + 1;
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
    return adj_list;
}

// SIMPLIFIED PATH FINDING: Just use Dijkstra with the road network
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
    
    // Reconstruct path
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
    
    return path;
}

// Clip geometry at snap point
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
        // Keep from snap point to end
        for (size_t i = closest_idx; i < coords.size(); i++) {
            clipped.push_back(coords[i]);
        }
        if (!clipped.empty() && closest_idx > 0) {
            clipped.insert(clipped.begin(), {snap_lng, snap_lat});
        }
    } else {
        // Keep from start to snap point
        size_t end_idx = min(closest_idx + 1, coords.size());
        for (size_t i = 0; i < end_idx; i++) {
            clipped.push_back(coords[i]);
        }
        if (!clipped.empty() && closest_idx < coords.size() - 1) {
            clipped.push_back({snap_lng, snap_lat});
        }
    }
    
    return clipped.empty() ? coords : clipped;
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
                         bool use_disruptions = false, double tau_threshold = 0.5) {
    
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
        cout << "    \"use_disruptions\": " << (use_disruptions ? "true" : "false") << "," << endl;
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
        cout << "    \"uses_disruptions\": " << (use_disruptions ? "true" : "false") << "," << endl;
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << "," << endl;
        cout << "    \"interpolation_used\": false" << endl;
        cout << "  }," << endl;
        
        cout << "  \"route\": {" << endl;
        cout << "    \"path_nodes\": [";
        for (size_t i = 0; i < path.size(); i++) {
            cout << path[i];
            if (i < path.size() - 1) cout << ", ";
        }
        cout << "]," << endl;
        
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
        
        size_t edge_loop_end = (path.size() == 2 && same_edge) ? 1 : path.size() - 1;
        
        for (size_t i = 0; i < edge_loop_end; i++) {
            NodeID from = path[i];
            NodeID to = path[i + 1];
            
            bool is_first_edge = (i == 0);
            bool is_last_edge = (i == path.size() - 2) && !same_edge;
            bool is_same_edge_case = (path.size() == 2 && same_edge);
            
            cout << "      {" << endl;
            cout << "        \"from\": " << from << "," << endl;
            cout << "        \"to\": " << to << "," << endl;
            cout << "        \"coordinates\": [";
            
            auto edge_key = make_pair(from, to);
            vector<pair<double, double>> coords_to_output;
            
            if (edge_geometries.count(edge_key)) {
                coords_to_output = edge_geometries.at(edge_key).coords;
                
                // Clip at snap points
                if (is_same_edge_case) {
                    // Clip both ends
                    coords_to_output = clip_geometry_at_snap(coords_to_output, start_snap_lat, start_snap_lng, true);
                    coords_to_output = clip_geometry_at_snap(coords_to_output, dest_snap_lat, dest_snap_lng, false);
                } else if (is_first_edge) {
                    coords_to_output = clip_geometry_at_snap(coords_to_output, start_snap_lat, start_snap_lng, true);
                } else if (is_last_edge) {
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
            if (i < edge_loop_end - 1) cout << ",";
            cout << endl;
        }
        cout << "    ]" << endl;
        
        cout << "  }" << endl;
    }
    
    cout << "}" << endl;
}

int main(int argc, char* argv[]) {
    if (argc != 20) {
        output_json_response(false, "Invalid arguments. Usage: dhl_routing_api <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> <start_edge_source> <start_edge_target> <start_edge_oneway> <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> <dest_edge_source> <dest_edge_target> <dest_edge_oneway> <use_disruptions> <tau_threshold> <nodes_csv> <edges_csv> <index_file>");
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
        
        bool use_disruptions = string(argv[15]) == "true";
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
        
        // Ensure snap edges are included
        bool same_edge = (start_edge_source == dest_edge_source && start_edge_target == dest_edge_target) ||
                         (start_edge_source == dest_edge_target && start_edge_target == dest_edge_source);
        
        if (same_edge) {
            // Same edge case: ALWAYS ensure both endpoints are in path for proper geometry
            // This guarantees the snap edge geometry will be output
            path.clear();
            path.push_back(start_edge_source);
            path.push_back(start_edge_target);
        } else if (!path.empty()) {
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
                           edge_geometries, use_disruptions, tau_threshold);
        
        return 0;
        
    } catch (const exception& e) {
        output_json_response(false, string("Exception: ") + e.what());
        return 1;
    }
}
