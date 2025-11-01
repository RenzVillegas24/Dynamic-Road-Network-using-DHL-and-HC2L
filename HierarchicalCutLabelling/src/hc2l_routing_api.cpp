/*
 * HC2L Routing JSON API
 * 
 * Provides a JSON-based API for HC2L (Hierarchical Cut 2-Hop Labelling) routing algorithm
 * 
 * ALGORITHM ARCHITECTURE:
 *   HC2L is a LABELING-BASED algorithm, not a search-based algorithm.
 *   It uses a two-phase approach for routing:
 * 
 *   Phase 1: DISTANCE COMPUTATION (Ultra-fast, O(1) typical)
 *     - Uses precomputed hierarchical cut labels in ContractionIndex
 *     - Computes shortest distance via 2-hop label intersection
 *     - NO graph traversal required
 * 
 *   Phase 2: PATH RECONSTRUCTION (Standard Dijkstra)
 *     - Uses actual road network edges
 *     - Finds path with distance matching the label-computed distance
 *     - Respects one-way roads and real topology
 * 
 *   This separation is INTENTIONAL and standard in labeling algorithms:
 *     - Labels provide distances (what HC2L/DHL are designed for)
 *     - Graph traversal provides paths (requires actual edges)
 * 
 * Algorithm: Hierarchical Cut Labelling
 * Based on: https://github.com/henningkoehlernz/road-networks
 * Description: Uses hierarchical graph cuts to create efficient 2-hop distance labels
 * 
 * Usage:
 *   ./hc2l_routing_api <start_lat> <start_lng> <dest_lat> <dest_lng> <use_disruptions> <nodes_csv> <edges_csv> <index_file>
 * 
 * Arguments:
 *   start_lat: Starting point latitude
 *   start_lng: Starting point longitude
 *   dest_lat: Destination latitude
 *   dest_lng: Destination longitude
 *   use_disruptions: "true" or "false" - whether to consider traffic disruptions
 *   nodes_csv: Path to nodes CSV file (node_id,latitude,longitude)
 *   edges_csv: Path to edges CSV file (source,target,length,name,highway,oneway,geometry_coords)
 *   index_file: Path to HC2L index file
 * 
 * Output:
 *   JSON object with routing results
 */
 
// Syntax for windows MSVC compiler
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
                double latitude = stod(lat_str);
                double longitude = stod(lng_str);
                
                coordinates[node_id] = GPSCoordinate(latitude, longitude, node_id);
            } catch (...) {
                // Skip invalid lines
                continue;
            }
        }
    }
    
    file.close();
    return coordinates;
}

// Helper function to parse CSV line with proper handling of quoted fields
vector<string> parse_csv_line(const string& line) {
    vector<string> fields;
    string current_field;
    bool in_quotes = false;
    
    for (size_t i = 0; i < line.length(); i++) {
        char c = line[i];
        
        if (c == '"') {
            in_quotes = !in_quotes;
            // Keep the quotes in the field for consistency
            current_field += c;
        } else if (c == ',' && !in_quotes) {
            fields.push_back(current_field);
            current_field.clear();
        } else {
            current_field += c;
        }
    }
    
    // Add the last field
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
    getline(file, line); // Skip header: source,target,length,name,highway,oneway,geometry_coords
    
    while (getline(file, line)) {
        // Use proper CSV parsing to handle quoted fields with commas
        vector<string> fields = parse_csv_line(line);
        
        // Expected: source,target,length,name,highway,oneway,geometry_coords (7 fields)
        if (fields.size() < 7) {
            continue; // Skip malformed lines
        }
        
        try {
            NodeID source = stoul(fields[0]);
            NodeID target = stoul(fields[1]);
            distance_t length = static_cast<distance_t>(stod(fields[2]));
            // fields[3] is name (ignored for routing)
            // fields[4] is highway type (ignored for routing)
            string oneway_str = fields[5];
            string geometry_json = fields[6];
            
            // Parse geometry JSON: [[lon1, lat1], [lon2, lat2], ...]
            vector<pair<double, double>> coords;
            if (!geometry_json.empty() && geometry_json != "[]") {
                // Simple JSON parsing for coordinate arrays
                size_t start_pos = 1; // Skip opening '['
                size_t end_pos = geometry_json.length() - 1; // Skip closing ']'
                
                size_t pos = start_pos;
                while (pos < end_pos) {
                    // Find next coordinate pair [lon, lat]
                    size_t pair_start = geometry_json.find('[', pos);
                    if (pair_start == string::npos) break;
                    
                    size_t pair_end = geometry_json.find(']', pair_start);
                    if (pair_end == string::npos) break;
                    
                    // Extract the pair
                    string pair_str = geometry_json.substr(pair_start + 1, pair_end - pair_start - 1);
                    size_t comma_pos = pair_str.find(',');
                    if (comma_pos != string::npos) {
                        try {
                            double lon = stod(pair_str.substr(0, comma_pos));
                            double lat = stod(pair_str.substr(comma_pos + 1));
                            coords.push_back({lon, lat});
                        } catch (...) {
                            // Skip invalid coordinate
                        }
                    }
                    
                    pos = pair_end + 1;
                }
            }
            
            // Store geometry
            EdgeGeometry geom;
            geom.source = source;
            geom.target = target;
            geom.length = length;
            geom.coords = coords;
            edge_geometries[{source, target}] = geom;
            
            // Trim whitespace from oneway value
            oneway_str.erase(0, oneway_str.find_first_not_of(" \t\n\r"));
            oneway_str.erase(oneway_str.find_last_not_of(" \t\n\r") + 1);
            
            // Parse oneway value as integer
            // 0 = bidirectional
            // 1 = one-way in direction of source -> target
            // -1 = one-way in reverse direction (target -> source only)
            int oneway = 0;
            try {
                oneway = stoi(oneway_str);
            } catch (...) {
                // If parsing fails, default to bidirectional
                oneway = 0;
            }
            
            if (oneway == 1) {
                // One-way: source -> target only
                adj_list[source].push_back(Neighbor(target, length));
            } else if (oneway == -1) {
                // One-way reverse: target -> source only
                adj_list[target].push_back(Neighbor(source, length));
                // Store reverse geometry too
                EdgeGeometry reverse_geom = geom;
                reverse_geom.source = target;
                reverse_geom.target = source;
                // Reverse the coordinates
                reverse(reverse_geom.coords.begin(), reverse_geom.coords.end());
                edge_geometries[{target, source}] = reverse_geom;
            } else {
                // Bidirectional (oneway == 0 or any other value)
                adj_list[source].push_back(Neighbor(target, length));
                adj_list[target].push_back(Neighbor(source, length));
                // Store reverse geometry too
                EdgeGeometry reverse_geom = geom;
                reverse_geom.source = target;
                reverse_geom.target = source;
                // Reverse the coordinates
                reverse(reverse_geom.coords.begin(), reverse_geom.coords.end());
                edge_geometries[{target, source}] = reverse_geom;
            }
        } catch (...) {
            // Skip invalid lines
            continue;
        }
    }
    
    file.close();
    return adj_list;
}

// Find nearest node to given GPS coordinates
NodeID find_nearest_node(double lat, double lng, const map<NodeID, GPSCoordinate>& coordinates, double max_distance = 1000.0) {
    NodeID nearest = 0;
    double min_dist = numeric_limits<double>::max();
    
    for (const auto& [node_id, coord] : coordinates) {
        double dist = haversine_distance(lat, lng, coord.latitude, coord.longitude);
        if (dist < min_dist) {
            min_dist = dist;
            nearest = node_id;
        }
    }
    
    if (min_dist > max_distance) {
        return 0; // No node within max_distance
    }
    
    return nearest;
}

// Find shortest path using Dijkstra on the adjacency list
vector<NodeID> find_shortest_path(NodeID start, NodeID dest, const map<NodeID, vector<Neighbor>>& adj_list) {
    vector<NodeID> path;
    
    if (start == dest) {
        path.push_back(start);
        return path;
    }
    
    // Distance and predecessor tracking
    map<NodeID, distance_t> dist;
    map<NodeID, NodeID> pred;
    set<NodeID> visited;
    
    // Priority queue: (distance, node)
    priority_queue<pair<distance_t, NodeID>, 
                   vector<pair<distance_t, NodeID>>,
                   greater<pair<distance_t, NodeID>>> pq;
    
    // Initialize
    dist[start] = 0;
    pq.push({0, start});
    
    // Dijkstra's algorithm
    while (!pq.empty()) {
        auto [d, u] = pq.top();
        pq.pop();
        
        if (visited.count(u)) continue;
        visited.insert(u);
        
        if (u == dest) break;
        
        // Check neighbors
        if (adj_list.count(u)) {
            for (const auto& neighbor : adj_list.at(u)) {
                NodeID v = neighbor.node;
                distance_t edge_dist = neighbor.distance;
                distance_t new_dist = dist[u] + edge_dist;
                
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
    } else {
        // No path found, return empty or just endpoints
        path.push_back(start);
        path.push_back(dest);
    }
    
    return path;
}

// Output JSON response
void output_json_response(bool success, const string& error_message = "",
                         NodeID start_node = 0, NodeID dest_node = 0,
                         double start_lat = 0, double start_lng = 0,
                         double dest_lat = 0, double dest_lng = 0,
                         distance_t distance = 0, double query_time_ms = 0,
                         const vector<NodeID>& path = vector<NodeID>(),
                         const map<NodeID, GPSCoordinate>& coordinates = map<NodeID, GPSCoordinate>(),
                         const map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries = map<pair<NodeID, NodeID>, EdgeGeometry>(),
                         bool use_disruptions = false) {
    
    cout << "{" << endl;
    cout << "  \"success\": " << (success ? "true" : "false") << "," << endl;
    
    if (!success) {
        cout << "  \"error\": \"" << error_message << "\"" << endl;
    } else {
        cout << "  \"algorithm\": \"HC2L (Hierarchical Cut 2-Hop Labelling)\"," << endl;
        cout << "  \"input\": {" << endl;
        cout << "    \"start_lat\": " << fixed << setprecision(6) << start_lat << "," << endl;
        cout << "    \"start_lng\": " << fixed << setprecision(6) << start_lng << "," << endl;
        cout << "    \"dest_lat\": " << fixed << setprecision(6) << dest_lat << "," << endl;
        cout << "    \"dest_lng\": " << fixed << setprecision(6) << dest_lng << "," << endl;
        cout << "    \"use_disruptions\": " << (use_disruptions ? "true" : "false") << endl;
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
        cout << "    \"uses_disruptions\": " << (use_disruptions ? "true" : "false") << endl;
        cout << "  }," << endl;
        
        cout << "  \"route\": {" << endl;
        cout << "    \"path_nodes\": [";
        for (size_t i = 0; i < path.size(); i++) {
            cout << path[i];
            if (i < path.size() - 1) cout << ", ";
        }
        cout << "]," << endl;
        
        // Output complete trace with GPS coordinates
        cout << "    \"complete_trace\": \"HC2L Route (";
        for (size_t i = 0; i < path.size(); i++) {
            NodeID node = path[i];
            cout << node;
            
            if (coordinates.count(node)) {
                auto& coord = coordinates.at(node);
                cout << " (" << fixed << setprecision(6) << coord.latitude << ", " << coord.longitude << ")";
            }
            
            if (i < path.size() - 1) cout << " -> ";
        }
        cout << ")\"," << endl;
        
        // Output detailed geometry for each edge in the path
        cout << "    \"geometry\": [" << endl;
        for (size_t i = 0; i < path.size() - 1; i++) {
            NodeID from = path[i];
            NodeID to = path[i + 1];
            
            cout << "      {" << endl;
            cout << "        \"from\": " << from << "," << endl;
            cout << "        \"to\": " << to << "," << endl;
            cout << "        \"coordinates\": [";
            
            // Check if we have geometry for this edge
            auto edge_key = make_pair(from, to);
            if (edge_geometries.count(edge_key)) {
                const auto& geom = edge_geometries.at(edge_key);
                for (size_t j = 0; j < geom.coords.size(); j++) {
                    cout << "[" << fixed << setprecision(6) << geom.coords[j].first << ", " 
                         << geom.coords[j].second << "]";
                    if (j < geom.coords.size() - 1) cout << ", ";
                }
            } else {
                // Fallback to node coordinates if no geometry available
                if (coordinates.count(from) && coordinates.count(to)) {
                    const auto& from_coord = coordinates.at(from);
                    const auto& to_coord = coordinates.at(to);
                    cout << "[" << fixed << setprecision(6) << from_coord.longitude << ", " 
                         << from_coord.latitude << "], ";
                    cout << "[" << to_coord.longitude << ", " << to_coord.latitude << "]";
                }
            }
            
            cout << "]" << endl;
            cout << "      }";
            if (i < path.size() - 2) cout << ",";
            cout << endl;
        }
        cout << "    ]" << endl;
        
        cout << "  }" << endl;
    }
    
    cout << "}" << endl;
}

int main(int argc, char* argv[]) {
    // Check arguments
    if (argc != 9) {
        output_json_response(false, "Invalid arguments. Usage: hc2l_routing_api <start_lat> <start_lng> <dest_lat> <dest_lng> <use_disruptions> <nodes_csv> <edges_csv> <index_file>");
        return 1;
    }
    
    try {
        // Parse arguments
        double start_lat = stod(argv[1]);
        double start_lng = stod(argv[2]);
        double dest_lat = stod(argv[3]);
        double dest_lng = stod(argv[4]);
        bool use_disruptions = string(argv[5]) == "true";
        string nodes_csv = argv[6];
        string edges_csv = argv[7];
        string index_file = argv[8];
        
        // Load node coordinates
        auto coordinates = load_node_coordinates(nodes_csv);
        if (coordinates.empty()) {
            output_json_response(false, "Failed to load node coordinates from " + nodes_csv);
            return 1;
        }
        
        // Load edges for path reconstruction and geometry
        map<pair<NodeID, NodeID>, EdgeGeometry> edge_geometries;
        auto adj_list = load_edges(edges_csv, edge_geometries);
        if (adj_list.empty()) {
            output_json_response(false, "Failed to load edges from " + edges_csv);
            return 1;
        }
        
        // Find nearest nodes to start and destination
        NodeID start_node = find_nearest_node(start_lat, start_lng, coordinates);
        NodeID dest_node = find_nearest_node(dest_lat, dest_lng, coordinates);
        
        if (start_node == 0 || dest_node == 0) {
            output_json_response(false, "Could not find nodes near given GPS coordinates");
            return 1;
        }
        
        // Load index from file (no graph file needed)
        ifstream index_stream(index_file, ios::binary);
        if (!index_stream.is_open()) {
            output_json_response(false, "Failed to open index file: " + index_file);
            return 1;
        }
        ContractionIndex ci(index_stream);
        index_stream.close();
        
        // Perform query
        auto start_time = chrono::high_resolution_clock::now();
        distance_t distance = ci.get_distance(start_node, dest_node);
        auto end_time = chrono::high_resolution_clock::now();
        
        double query_time_ms = chrono::duration<double, milli>(end_time - start_time).count();
        
        // Get path using Dijkstra on the actual road network edges
        vector<NodeID> path = find_shortest_path(start_node, dest_node, adj_list);
        
        // Output JSON response with geometry
        output_json_response(true, "", start_node, dest_node,
                           start_lat, start_lng, dest_lat, dest_lng,
                           distance, query_time_ms, path, coordinates,
                           edge_geometries, use_disruptions);
        
        return 0;
        
    } catch (const exception& e) {
        output_json_response(false, string("Exception: ") + e.what());
        return 1;
    }
}
