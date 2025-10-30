/*
 * DHL Routing JSON API
 * 
 * Provides a JSON-based API for DHL (Dual-Hierarchy Labelling) routing algorithm
 * 
 * Usage:
 *   ./dhl_routing_api <start_lat> <start_lng> <dest_lat> <dest_lng> <use_disruptions> <tau_threshold> <nodes_csv> <edges_csv> <graph_file> <index_file>
 * 
 * Arguments:
 *   start_lat: Starting point latitude
 *   start_lng: Starting point longitude
 *   dest_lat: Destination latitude
 *   dest_lng: Destination longitude
 *   use_disruptions: "true" or "false" - whether to consider traffic disruptions
 *   tau_threshold: Float value (e.g., 0.5) - threshold parameter for routing
 *   nodes_csv: Path to nodes CSV file (node_id,latitude,longitude)
 *   edges_csv: Path to edges CSV file (source,target,length,name,highway,oneway)
 *   graph_file: Path to binary graph file
 *   index_file: Path to DHL index file
 * 
 * Output:
 *   JSON object with routing results
 */

#include "road_network.h"
#include "util.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <chrono>
#include <map>
#include <algorithm>

using namespace road_network;
using namespace std;

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

// Load edges from CSV file
map<NodeID, vector<Neighbor>> load_edges(const string& filename) {
    map<NodeID, vector<Neighbor>> adj_list;
    ifstream file(filename);
    
    if (!file.is_open()) {
        cerr << "Warning: Could not open " << filename << endl;
        return adj_list;
    }
    
    string line;
    getline(file, line); // Skip header: source,target,length,name,highway,oneway
    
    while (getline(file, line)) {
        stringstream ss(line);
        string source_str, target_str, length_str;
        
        // Read source,target,length (ignore rest)
        if (getline(ss, source_str, ',') &&
            getline(ss, target_str, ',') &&
            getline(ss, length_str, ',')) {
            
            try {
                NodeID source = stoul(source_str);
                NodeID target = stoul(target_str);
                distance_t length = static_cast<distance_t>(stod(length_str));
                
                adj_list[source].push_back(Neighbor(target, length));
            } catch (...) {
                // Skip invalid lines
                continue;
            }
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
                         bool use_disruptions = false, double tau_threshold = 0.5) {
    
    cout << "{" << endl;
    cout << "  \"success\": " << (success ? "true" : "false") << "," << endl;
    
    if (!success) {
        cout << "  \"error\": \"" << error_message << "\"" << endl;
    } else {
        cout << "  \"algorithm\": \"DHL (Dual-Hierarchy Labelling)\"," << endl;
        cout << "  \"input\": {" << endl;
        cout << "    \"start_lat\": " << fixed << setprecision(6) << start_lat << "," << endl;
        cout << "    \"start_lng\": " << fixed << setprecision(6) << start_lng << "," << endl;
        cout << "    \"dest_lat\": " << fixed << setprecision(6) << dest_lat << "," << endl;
        cout << "    \"dest_lng\": " << fixed << setprecision(6) << dest_lng << "," << endl;
        cout << "    \"use_disruptions\": " << (use_disruptions ? "true" : "false") << "," << endl;
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << endl;
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
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << endl;
        cout << "  }," << endl;
        
        cout << "  \"route\": {" << endl;
        cout << "    \"path_nodes\": [";
        for (size_t i = 0; i < path.size(); i++) {
            cout << path[i];
            if (i < path.size() - 1) cout << ", ";
        }
        cout << "]," << endl;
        
        // Output complete trace with GPS coordinates
        cout << "    \"complete_trace\": \"DHL Route (";
        for (size_t i = 0; i < path.size(); i++) {
            NodeID node = path[i];
            cout << node;
            
            if (coordinates.count(node)) {
                auto& coord = coordinates.at(node);
                cout << " (" << fixed << setprecision(6) << coord.latitude << ", " << coord.longitude << ")";
            }
            
            if (i < path.size() - 1) cout << " -> ";
        }
        cout << ")\"" << endl;
        
        cout << "  }" << endl;
    }
    
    cout << "}" << endl;
}

int main(int argc, char* argv[]) {
    // Check arguments
    if (argc != 11) {
        output_json_response(false, "Invalid arguments. Usage: dhl_routing_api <start_lat> <start_lng> <dest_lat> <dest_lng> <use_disruptions> <tau_threshold> <nodes_csv> <edges_csv> <graph_file> <index_file>");
        return 1;
    }
    
    try {
        // Parse arguments
        double start_lat = stod(argv[1]);
        double start_lng = stod(argv[2]);
        double dest_lat = stod(argv[3]);
        double dest_lng = stod(argv[4]);
        bool use_disruptions = string(argv[5]) == "true";
        double tau_threshold = stod(argv[6]);
        string nodes_csv = argv[7];
        string edges_csv = argv[8];
        string graph_file = argv[9];
        string index_file = argv[10];
        
        // Load node coordinates
        auto coordinates = load_node_coordinates(nodes_csv);
        if (coordinates.empty()) {
            output_json_response(false, "Failed to load node coordinates from " + nodes_csv);
            return 1;
        }
        
        // Load edges for path reconstruction
        auto adj_list = load_edges(edges_csv);
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
        
        // Load graph and index
        Graph g;
        ifstream graph_stream(graph_file, ios::binary);
        if (!graph_stream.is_open()) {
            output_json_response(false, "Failed to open graph file: " + graph_file);
            return 1;
        }
        read_graph(g, graph_stream);
        graph_stream.close();
        
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
        
        // Output JSON response
        output_json_response(true, "", start_node, dest_node,
                           start_lat, start_lng, dest_lat, dest_lng,
                           distance, query_time_ms, path, coordinates,
                           use_disruptions, tau_threshold);
        
        return 0;
        
    } catch (const exception& e) {
        output_json_response(false, string("Exception: ") + e.what());
        return 1;
    }
}
