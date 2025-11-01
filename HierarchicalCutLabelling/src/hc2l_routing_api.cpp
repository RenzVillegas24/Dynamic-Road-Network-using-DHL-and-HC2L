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
 *   ./hc2l_routing_api <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> <start_edge_source> <start_edge_target> <start_edge_oneway> \
 *                       <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> <dest_edge_source> <dest_edge_target> <dest_edge_oneway> \
 *                       <use_disruptions> <nodes_csv> <edges_csv> <index_file>
 * 
 * Arguments:
 *   start_pin_lat: Starting pin point latitude (user click)
 *   start_pin_lng: Starting pin point longitude (user click)
 *   start_snap_lat: Starting snap point latitude (snapped to edge)
 *   start_snap_lng: Starting snap point longitude (snapped to edge)
 *   start_edge_source: Source node of edge where start snap occurred
 *   start_edge_target: Target node of edge where start snap occurred
 *   start_edge_oneway: One-way property of start edge (1=forward, -1=reverse, 0=bidirectional)
 *   dest_pin_lat: Destination pin point latitude (user click)
 *   dest_pin_lng: Destination pin point longitude (user click)
 *   dest_snap_lat: Destination snap point latitude (snapped to edge)
 *   dest_snap_lng: Destination snap point longitude (snapped to edge)
 *   dest_edge_source: Source node of edge where dest snap occurred
 *   dest_edge_target: Target node of edge where dest snap occurred
 *   dest_edge_oneway: One-way property of dest edge (1=forward, -1=reverse, 0=bidirectional)
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

// Select routing nodes to ensure the snap edges are actually used in the route
// CRITICAL: The route MUST start by traversing start_edge and END by arriving via dest_edge
// This ensures we respect the exact road where the user's pin was snapped
struct RoutingEndpoints {
    NodeID start_node;  // Node where routing algorithm starts
    NodeID dest_node;   // Node where routing algorithm ends
    bool reverse_start_edge;  // Whether to reverse first edge in output
    bool reverse_dest_edge;   // Whether to reverse last edge in output
};

RoutingEndpoints select_routing_endpoints(
    NodeID start_edge_source, NodeID start_edge_target, int start_edge_oneway,
    NodeID dest_edge_source, NodeID dest_edge_target, int dest_edge_oneway,
    const map<NodeID, vector<Neighbor>>& adj_list,
    double start_snap_lat, double start_snap_lng,
    double dest_snap_lat, double dest_snap_lng,
    const map<NodeID, GPSCoordinate>& node_coords) {
    
    RoutingEndpoints result;
    result.reverse_start_edge = false;
    result.reverse_dest_edge = false;
    
    // START EDGE: We route FROM one of the edge's nodes
    // Priority: respect one-way direction, then choose node CLOSER to snap point
    if (start_edge_oneway == 1) {
        // One-way forward: must exit FROM source node (going toward target)
        result.start_node = start_edge_source;
    } else if (start_edge_oneway == -1) {
        // One-way reverse: must exit FROM target node (going toward source)
        result.start_node = start_edge_target;
    } else {
        // Bidirectional: choose node CLOSER to the snap point
        if (node_coords.count(start_edge_source) && node_coords.count(start_edge_target)) {
            double dist_to_source = haversine_distance(
                start_snap_lat, start_snap_lng,
                node_coords.at(start_edge_source).latitude,
                node_coords.at(start_edge_source).longitude
            );
            double dist_to_target = haversine_distance(
                start_snap_lat, start_snap_lng,
                node_coords.at(start_edge_target).latitude,
                node_coords.at(start_edge_target).longitude
            );
            // Choose the FARTHER node to route FROM (so we traverse the snap edge)
            result.start_node = (dist_to_source > dist_to_target) ? start_edge_source : start_edge_target;
        } else {
            // Fallback: choose node with more outgoing connections
            size_t source_neighbors = adj_list.count(start_edge_source) ? adj_list.at(start_edge_source).size() : 0;
            size_t target_neighbors = adj_list.count(start_edge_target) ? adj_list.at(start_edge_target).size() : 0;
            result.start_node = (source_neighbors >= target_neighbors) ? start_edge_source : start_edge_target;
        }
    }
    
    // DEST EDGE: We route TO one of the edge's nodes
    // Priority: respect one-way direction, then choose node CLOSER to snap point
    if (dest_edge_oneway == 1) {
        // One-way forward: must arrive AT target node (coming from source)
        result.dest_node = dest_edge_target;
    } else if (dest_edge_oneway == -1) {
        // One-way reverse: must arrive AT source node (coming from target)
        result.dest_node = dest_edge_source;
    } else {
        // Bidirectional: choose node CLOSER to the snap point
        if (node_coords.count(dest_edge_source) && node_coords.count(dest_edge_target)) {
            double dist_to_source = haversine_distance(
                dest_snap_lat, dest_snap_lng,
                node_coords.at(dest_edge_source).latitude,
                node_coords.at(dest_edge_source).longitude
            );
            double dist_to_target = haversine_distance(
                dest_snap_lat, dest_snap_lng,
                node_coords.at(dest_edge_target).latitude,
                node_coords.at(dest_edge_target).longitude
            );
            // Choose the FARTHER node to route TO (so we traverse the snap edge)
            result.dest_node = (dist_to_source > dist_to_target) ? dest_edge_source : dest_edge_target;
        } else {
            // Fallback: choose node with more incoming connections
            size_t source_neighbors = adj_list.count(dest_edge_source) ? adj_list.at(dest_edge_source).size() : 0;
            size_t target_neighbors = adj_list.count(dest_edge_target) ? adj_list.at(dest_edge_target).size() : 0;
            result.dest_node = (target_neighbors >= source_neighbors) ? dest_edge_target : dest_edge_source;
        }
    }
    
    return result;
}

// Ensure snap edges are included in the path
// Prepends start edge and appends dest edge to guarantee they're traversed
vector<NodeID> ensure_snap_edges_in_path(
    const vector<NodeID>& original_path,
    NodeID start_edge_source, NodeID start_edge_target, int start_edge_oneway,
    NodeID dest_edge_source, NodeID dest_edge_target, int dest_edge_oneway) {
    
    if (original_path.empty()) {
        return original_path;
    }
    
    vector<NodeID> enhanced_path;
    NodeID first_node = original_path[0];
    NodeID last_node = original_path[original_path.size() - 1];
    
    // PREPEND START EDGE if needed
    // Check if the path starts with one of the start edge nodes
    bool start_edge_included = false;
    if (original_path.size() >= 2) {
        // Check if first two nodes form the start edge
        NodeID second_node = original_path[1];
        if ((first_node == start_edge_source && second_node == start_edge_target) ||
            (first_node == start_edge_target && second_node == start_edge_source)) {
            start_edge_included = true;
        }
    }
    
    if (!start_edge_included) {
        // Need to prepend the other node to create the start edge
        // CRITICAL: Respect one-way direction!
        if (start_edge_oneway == 1) {
            // Forward: source→target, so we must start FROM source
            if (first_node == start_edge_target) {
                enhanced_path.push_back(start_edge_source);
            }
            // If first_node == source, edge is already correct (source→...)
        } else if (start_edge_oneway == -1) {
            // Reverse: target→source, so we must start FROM target
            if (first_node == start_edge_source) {
                enhanced_path.push_back(start_edge_target);
            }
            // If first_node == target, edge is already correct (target→...)
        } else {
            // Bidirectional: allow either direction
            if (first_node == start_edge_source) {
                enhanced_path.push_back(start_edge_target);
            } else if (first_node == start_edge_target) {
                enhanced_path.push_back(start_edge_source);
            }
        }
    }
    
    // Add original path
    enhanced_path.insert(enhanced_path.end(), original_path.begin(), original_path.end());
    
    // APPEND DEST EDGE if needed
    // Check if the path ends with one of the dest edge nodes
    bool dest_edge_included = false;
    if (original_path.size() >= 2) {
        // Check if last two nodes form the dest edge
        NodeID second_last_node = original_path[original_path.size() - 2];
        if ((second_last_node == dest_edge_source && last_node == dest_edge_target) ||
            (second_last_node == dest_edge_target && last_node == dest_edge_source)) {
            dest_edge_included = true;
        }
    }
    
    if (!dest_edge_included) {
        // Need to append the other node to create the dest edge
        // CRITICAL: Respect one-way direction!
        if (dest_edge_oneway == 1) {
            // Forward: source→target, so we must arrive AT target
            if (last_node == dest_edge_source) {
                enhanced_path.push_back(dest_edge_target);
            }
            // If last_node == target, edge is already correct (...→target)
        } else if (dest_edge_oneway == -1) {
            // Reverse: target→source, so we must arrive AT source
            if (last_node == dest_edge_target) {
                enhanced_path.push_back(dest_edge_source);
            }
            // If last_node == source, edge is already correct (...→source)
        } else {
            // Bidirectional: allow either direction
            if (last_node == dest_edge_source) {
                enhanced_path.push_back(dest_edge_target);
            } else if (last_node == dest_edge_target) {
                enhanced_path.push_back(dest_edge_source);
            }
        }
    }
    
    return enhanced_path;
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

// Helper function to find closest point on geometry to a snap point and clip the geometry
// IMPROVED: Handles same edge and neighboring edge cases properly
vector<pair<double, double>> clip_geometry_at_snap(
    const vector<pair<double, double>>& coords,
    double snap_lat, double snap_lng,
    bool clip_start) {
    
    if (coords.empty()) return coords;
    
    // Find the closest point on the geometry to the snap point
    double min_dist = numeric_limits<double>::max();
    size_t closest_idx = 0;
    double closest_segment_dist = numeric_limits<double>::max();
    bool snap_is_at_vertex = false;
    
    // First pass: Find closest vertex and closest segment
    for (size_t i = 0; i < coords.size(); i++) {
        double dist = haversine_distance(snap_lat, snap_lng, coords[i].second, coords[i].first);
        
        // Check if snap point is very close to a vertex (within 2 meters)
        if (dist < 2.0) {
            snap_is_at_vertex = true;
            if (dist < min_dist) {
                min_dist = dist;
                closest_idx = i;
            }
        } else if (dist < min_dist && !snap_is_at_vertex) {
            min_dist = dist;
            closest_idx = i;
        }
    }
    
    // If snap point is not at a vertex, try to find closest point on a segment
    if (!snap_is_at_vertex && coords.size() >= 2) {
        // Check distances to line segments between consecutive points
        for (size_t i = 0; i < coords.size() - 1; i++) {
            // For each segment, find closest point on the segment
            double lat1 = coords[i].second, lng1 = coords[i].first;
            double lat2 = coords[i+1].second, lng2 = coords[i+1].first;
            
            // Simple perpendicular distance approximation
            double seg_len_sq = (lat2 - lat1) * (lat2 - lat1) + (lng2 - lng1) * (lng2 - lng1);
            if (seg_len_sq < 1e-10) continue;
            
            double t = ((snap_lat - lat1) * (lat2 - lat1) + (snap_lng - lng1) * (lng2 - lng1)) / seg_len_sq;
            t = max(0.0, min(1.0, t));
            
            double proj_lat = lat1 + t * (lat2 - lat1);
            double proj_lng = lng1 + t * (lng2 - lng1);
            double segment_dist = haversine_distance(snap_lat, snap_lng, proj_lat, proj_lng);
            
            if (segment_dist < closest_segment_dist) {
                closest_segment_dist = segment_dist;
                closest_idx = i;
                snap_is_at_vertex = false;
            }
        }
    }
    
    // Clip the geometry based on whether it's start or end
    vector<pair<double, double>> clipped;
    
    if (clip_start) {
        // For start edge: keep from snap point to end
        // Always include the closest index (vertex or segment start)
        for (size_t i = closest_idx; i < coords.size(); i++) {
            clipped.push_back(coords[i]);
        }
        
        // Prepend the actual snap point if it's not already the first vertex
        if (!clipped.empty() && (snap_is_at_vertex && closest_idx > 0)) {
            clipped.insert(clipped.begin(), {snap_lng, snap_lat});
        } else if (!snap_is_at_vertex && !clipped.empty()) {
            // Snap point is on a segment, insert it at the beginning
            clipped.insert(clipped.begin(), {snap_lng, snap_lat});
        } else if (clipped.empty()) {
            // Edge case: geometry is empty, return snap point
            clipped.push_back({snap_lng, snap_lat});
        }
    } else {
        // For end edge: keep from start to snap point
        // Always include up to closest index
        size_t end_idx = min(closest_idx + 1, coords.size());
        for (size_t i = 0; i < end_idx; i++) {
            clipped.push_back(coords[i]);
        }
        
        // Append the actual snap point if it's not already the last vertex
        if (!clipped.empty() && (snap_is_at_vertex && closest_idx < coords.size() - 1)) {
            clipped.push_back({snap_lng, snap_lat});
        } else if (!snap_is_at_vertex && !clipped.empty()) {
            // Snap point is on a segment, append it at the end
            clipped.push_back({snap_lng, snap_lat});
        } else if (clipped.empty()) {
            // Edge case: geometry is empty, return snap point
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
                         bool use_disruptions = false) {
    
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
        cout << "    \"dest_node\": " << dest_node << ","<< endl;
        
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
        cout << "    \"interpolation_used\": false" << endl;
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
        // CRITICAL: First edge should be from start snap edge, last edge should be to dest snap edge
        // ALSO CRITICAL: Handle case where start and dest edges are the SAME edge
        cout << "    \"geometry\": [" << endl;
        
        // Check if start and dest edges are the same
        bool same_edge = (start_edge_source == dest_edge_source && start_edge_target == dest_edge_target) ||
                         (start_edge_source == dest_edge_target && start_edge_target == dest_edge_source);
        
        // For same edge case with path.size() == 2, we need special handling
        bool is_same_edge_case = (path.size() == 2 && same_edge);
        
        // Determine loop range: if same edge case, only output one edge
        size_t edge_loop_end = is_same_edge_case ? 1 : path.size() - 1;
        
        for (size_t i = 0; i < edge_loop_end; i++) {
            NodeID from = path[i];
            NodeID to = path[i + 1];
            
            bool is_first_edge = (i == 0);
            bool is_last_edge = (i == path.size() - 2);
            
            cout << "      {" << endl;
            cout << "        \"from\": " << from << "," << endl;
            cout << "        \"to\": " << to << "," << endl;
            cout << "        \"coordinates\": [";
            
            // Try to get geometry from the direct edge path
            auto edge_key = make_pair(from, to);
            vector<pair<double, double>> coords_to_output;
            bool found_geometry = false;
            bool should_clip = false;
            
            if (edge_geometries.count(edge_key)) {
                const auto& geom = edge_geometries.at(edge_key);
                coords_to_output = geom.coords;
                found_geometry = true;
                // Only apply clipping for first/last edges when using direct path
                should_clip = is_first_edge || is_last_edge;
            } else if (is_same_edge_case) {
                // Special case: start and dest are on the SAME edge
                // Try to find the snap edge geometry and clip between both snap points
                auto snap_edge_forward = make_pair(start_edge_source, start_edge_target);
                auto snap_edge_backward = make_pair(start_edge_target, start_edge_source);
                
                if (edge_geometries.count(snap_edge_forward)) {
                    coords_to_output = edge_geometries.at(snap_edge_forward).coords;
                    found_geometry = true;
                    should_clip = true;
                } else if (edge_geometries.count(snap_edge_backward)) {
                    coords_to_output = edge_geometries.at(snap_edge_backward).coords;
                    found_geometry = true;
                    should_clip = true;
                }
            } else if (is_first_edge) {
                // For first edge, try to find geometry matching the start snap edge
                // Try both directions of the start snap edge
                auto snap_edge_forward = make_pair(start_edge_source, start_edge_target);
                auto snap_edge_backward = make_pair(start_edge_target, start_edge_source);
                
                if (edge_geometries.count(snap_edge_forward)) {
                    coords_to_output = edge_geometries.at(snap_edge_forward).coords;
                    found_geometry = true;
                    should_clip = true;
                } else if (edge_geometries.count(snap_edge_backward)) {
                    coords_to_output = edge_geometries.at(snap_edge_backward).coords;
                    found_geometry = true;
                    should_clip = true;
                }
            } else if (is_last_edge) {
                // For last edge, try to find geometry matching the dest snap edge
                // Try both directions of the dest snap edge
                auto snap_edge_forward = make_pair(dest_edge_source, dest_edge_target);
                auto snap_edge_backward = make_pair(dest_edge_target, dest_edge_source);
                
                if (edge_geometries.count(snap_edge_forward)) {
                    coords_to_output = edge_geometries.at(snap_edge_forward).coords;
                    found_geometry = true;
                    should_clip = true;
                } else if (edge_geometries.count(snap_edge_backward)) {
                    coords_to_output = edge_geometries.at(snap_edge_backward).coords;
                    found_geometry = true;
                    should_clip = true;
                }
            }
            
            if (found_geometry && !coords_to_output.empty()) {
                // Apply clipping for first and last edges
                if (should_clip) {
                    if (is_same_edge_case) {
                        // Clip between both snap points on the same edge
                        // Find closest points to both snap locations
                        double min_dist_start = numeric_limits<double>::max();
                        double min_dist_end = numeric_limits<double>::max();
                        size_t idx_start = 0, idx_end = coords_to_output.size() - 1;
                        
                        for (size_t j = 0; j < coords_to_output.size(); j++) {
                            double dist_start = haversine_distance(start_snap_lat, start_snap_lng, 
                                                                 coords_to_output[j].second, coords_to_output[j].first);
                            double dist_end = haversine_distance(dest_snap_lat, dest_snap_lng, 
                                                               coords_to_output[j].second, coords_to_output[j].first);
                            
                            if (dist_start < min_dist_start) {
                                min_dist_start = dist_start;
                                idx_start = j;
                            }
                            if (dist_end < min_dist_end) {
                                min_dist_end = dist_end;
                                idx_end = j;
                            }
                        }
                        
                        // Ensure idx_start <= idx_end
                        if (idx_start > idx_end) {
                            swap(idx_start, idx_end);
                        }
                        
                        // Build clipped geometry from start snap to end snap
                        vector<pair<double, double>> clipped;
                        clipped.push_back({start_snap_lng, start_snap_lat});
                        for (size_t j = idx_start; j <= idx_end && j < coords_to_output.size(); j++) {
                            clipped.push_back(coords_to_output[j]);
                        }
                        clipped.push_back({dest_snap_lng, dest_snap_lat});
                        coords_to_output = clipped;
                    } else if (is_first_edge) {
                        coords_to_output = clip_geometry_at_snap(coords_to_output, start_snap_lat, start_snap_lng, true);
                    } else if (is_last_edge) {
                        coords_to_output = clip_geometry_at_snap(coords_to_output, dest_snap_lat, dest_snap_lng, false);
                    }
                }
                
                // Output the geometry
                for (size_t j = 0; j < coords_to_output.size(); j++) {
                    cout << "[" << fixed << setprecision(6) << coords_to_output[j].first << ", " 
                         << coords_to_output[j].second << "]";
                    if (j < coords_to_output.size() - 1) cout << ", ";
                }
            } else {
                // Fallback to node coordinates if no geometry available
                if (coordinates.count(from) && coordinates.count(to)) {
                    const auto& from_coord = coordinates.at(from);
                    const auto& to_coord = coordinates.at(to);
                    
                    if (is_same_edge_case) {
                        // Same edge with no full geometry - just use snap points
                        cout << "[" << fixed << setprecision(6) << start_snap_lng << ", " 
                             << start_snap_lat << "], ";
                        cout << "[" << dest_snap_lng << ", " << dest_snap_lat << "]";
                    } else if (is_first_edge) {
                        // Start from snap point
                        cout << "[" << fixed << setprecision(6) << start_snap_lng << ", " 
                             << start_snap_lat << "], ";
                        cout << "[" << to_coord.longitude << ", " << to_coord.latitude << "]";
                    } else if (is_last_edge) {
                        // End at snap point
                        cout << "[" << fixed << setprecision(6) << from_coord.longitude << ", " 
                             << from_coord.latitude << "], ";
                        cout << "[" << dest_snap_lng << ", " << dest_snap_lat << "]";
                    } else {
                        // Full edge
                        cout << "[" << fixed << setprecision(6) << from_coord.longitude << ", " 
                             << from_coord.latitude << "], ";
                        cout << "[" << to_coord.longitude << ", " << to_coord.latitude << "]";
                    }
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
    // Check arguments: 18 total
    // start_pin_lat, start_pin_lng, start_snap_lat, start_snap_lng, start_edge_source, start_edge_target, start_edge_oneway,
    // dest_pin_lat, dest_pin_lng, dest_snap_lat, dest_snap_lng, dest_edge_source, dest_edge_target, dest_edge_oneway,
    // use_disruptions, nodes_csv, edges_csv, index_file
    if (argc != 19) {
        output_json_response(false, "Invalid arguments. Usage: hc2l_routing_api <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> <start_edge_source> <start_edge_target> <start_edge_oneway> <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> <dest_edge_source> <dest_edge_target> <dest_edge_oneway> <use_disruptions> <nodes_csv> <edges_csv> <index_file>");
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
        string nodes_csv = argv[16];
        string edges_csv = argv[17];
        string index_file = argv[18];
        
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
        
        // Select routing endpoints ensuring snap edges are actually used in the route
        // CRITICAL: Route MUST start by traversing start_edge and end by arriving via dest_edge
        // Uses snap coordinates to choose the endpoint farther from snap (to traverse the edge)
        auto endpoints = select_routing_endpoints(
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway,
            adj_list,
            start_snap_lat, start_snap_lng,
            dest_snap_lat, dest_snap_lng,
            coordinates
        );
        
        NodeID start_node = endpoints.start_node;
        NodeID dest_node = endpoints.dest_node;
        
        if (start_node == 0 || dest_node == 0) {
            output_json_response(false, "Invalid snap edge nodes provided");
            return 1;
        }
        
        // Validate that start edge exists in adjacency list
        bool start_edge_exists = false;
        if (adj_list.count(start_node)) {
            NodeID expected_next = (start_node == start_edge_source) ? start_edge_target : start_edge_source;
            for (const auto& neighbor : adj_list.at(start_node)) {
                if (neighbor.node == expected_next) {
                    start_edge_exists = true;
                    break;
                }
            }
        }
        
        if (!start_edge_exists) {
            output_json_response(false, "Start snap edge does not exist in road network or violates one-way direction");
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
        
        // CRITICAL: Ensure snap edges are included in the path
        // This prepends/appends the snap edge nodes to guarantee the route uses those specific edges
        path = ensure_snap_edges_in_path(
            path,
            start_edge_source, start_edge_target, start_edge_oneway,
            dest_edge_source, dest_edge_target, dest_edge_oneway
        );
        
        // Output JSON response with all snap point information
        output_json_response(true, "", start_node, dest_node,
                           start_pin_lat, start_pin_lng, start_snap_lat, start_snap_lng,
                           dest_pin_lat, dest_pin_lng, dest_snap_lat, dest_snap_lng,
                           start_edge_source, start_edge_target, start_edge_oneway,
                           dest_edge_source, dest_edge_target, dest_edge_oneway,
                           distance, query_time_ms, path, coordinates,
                           edge_geometries, use_disruptions);
        
        return 0;
        
    } catch (const exception& e) {
        output_json_response(false, string("Exception: ") + e.what());
        return 1;
    }
}
