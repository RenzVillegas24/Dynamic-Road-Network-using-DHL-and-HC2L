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
 * Based on: https://github.com/mufarhan/Dual-Hierarchy-Labelling
 */
 
#define _USE_MATH_DEFINES
#define ROUTING_API_DHL

#include "road_network.h"
#include "util.h"
#include "../../ApiUtils/src/routing_utils.h"
#include <iomanip>
#include <chrono>
#include <cmath>
#include <algorithm>

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
// (MOVED TO: ApiUtils/src/shared_routing_structures.h)

// Global disruption cache (persists across requests)
DisruptionCache g_disruption_cache;

// Global highway type map: stores highway_type for each edge (loaded from CSV)
map<pair<NodeID, NodeID>, string> g_highway_types;

// Forward declarations
vector<string> parse_csv_line(const string& line);

// ============================================================
// DISRUPTION METRICS COMPUTATION
// ============================================================
// Routing-specific implementations now rely on the shared
// compute_disruption_metrics and calculate_disruption_weight
// defined in ApiUtils/src/routing_utils.h

// ============================================================
// DISRUPTION CACHE MANAGEMENT
// ============================================================
// Function moved to ApiUtils/src/routing_utils.h:
//   - load_disruptions_with_cache()
// This function is now included via the routing_utils.h header
// and is shared by both DHL and HC2L routing APIs

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
    const map<pair<NodeID, NodeID>, IncidentInfo>& incident_data) {
    
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
                
                // Use the disruption-aware weight that was already set in neighbor.distance
                // This weight incorporates: flow penalties and incident costs
                distance_t edge_weight = neighbor.distance;
                
                // Skip impassable edges (from closed roads)
                if (edge_weight >= infinity) {
                    continue;
                }
                
                distance_t new_dist = dist[u] + edge_weight;
                
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
            
            // Get highway type from global map
            string hw_type = "unknown";
            if (g_highway_types.count(edge_key)) {
                hw_type = g_highway_types[edge_key];
            }
            cerr << "Highway=" << hw_type << " ";
            
            if (incident_data.count(edge_key)) {
                const auto& inc = incident_data.at(edge_key);
                if (inc.road_closed) cerr << "[CLOSED] ";
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
        // Always include at least one more point for visualization, even if we're near the end
        size_t start_from = (closest_idx + 1 < coords.size()) ? closest_idx + 1 : closest_idx;
        for (size_t i = start_from; i < coords.size(); i++) {
            clipped.push_back(coords[i]);
        }
        // If we only have the snap point, add the closest original coordinate for context
        if (clipped.size() == 1 && closest_idx < coords.size()) {
            clipped.push_back(coords[closest_idx]);
        }
    } else {
        // Keep geometry up to closest point, then STRICTLY end at snap point
        // Include points before closest
        size_t end_at = (closest_idx > 0) ? closest_idx : 0;
        for (size_t i = 0; i <= end_at && i < coords.size(); i++) {
            clipped.push_back(coords[i]);
        }
        clipped.push_back({snap_lng, snap_lat});
        // If we only have snap point, include a previous point for context
        if (clipped.size() == 2 && closest_idx < coords.size()) {
            clipped.insert(clipped.end() - 1, coords[closest_idx]);
        }
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


// Disruption analysis result structure
struct DisruptionAnalysisResult {
    int total_disruptions_on_route;
    int road_closures_count;
    int high_severity_count;
    int medium_severity_count;
    int low_severity_count;
    double baseline_eta_seconds;
    double actual_eta_seconds;
    double added_delay_seconds;
    double delay_percentage;
    int total_network_disruptions;
    int total_network_closures;
    int active_disruptions;
};

// Analyze route disruptions and calculate time impact
DisruptionAnalysisResult analyze_route_disruptions(
    const vector<NodeID>& path,
    const map<pair<NodeID, NodeID>, IncidentInfo>& incident_data,
    const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data,
    const map<NodeID, GPSCoordinate>& coordinates,
    const map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries) {
    
    DisruptionAnalysisResult result = {};
    
    if (path.size() < 2) {
        return result;
    }
    
    // Count severity levels on route
    map<string, int> severity_counts;
    severity_counts["critical"] = 0;
    severity_counts["high"] = 0;
    severity_counts["medium"] = 0;
    severity_counts["low"] = 0;
    
    double baseline_travel_time = 0.0;
    double actual_travel_time = 0.0;
    
    // Analyze each edge in the path
    for (size_t i = 0; i < path.size() - 1; i++) {
        NodeID from = path[i];
        NodeID to = path[i + 1];
        auto edge_key = make_pair(from, to);
        
        // Calculate edge distance
        double edge_distance = 0.0;
        if (edge_geometries.count(edge_key)) {
            edge_distance = edge_geometries.at(edge_key).length;
        } else if (coordinates.count(from) && coordinates.count(to)) {
            const auto& coord_from = coordinates.at(from);
            const auto& coord_to = coordinates.at(to);
            edge_distance = haversine_distance(
                coord_from.latitude, coord_from.longitude,
                coord_to.latitude, coord_to.longitude
            );
        }
        
        // Get free-flow speed (baseline)
        string highway_type = "unknown";
        if (g_highway_types.count(edge_key)) {
            highway_type = g_highway_types.at(edge_key);
        }
        double free_flow_speed = get_highway_speed(highway_type);
        
        // Calculate baseline time (no disruptions)
        double baseline_time = edge_distance / (free_flow_speed / 3.6);
        baseline_travel_time += baseline_time;
        
        // Check for disruptions on this edge
        bool has_disruption = false;
        bool is_closed = false;
        string incident_type = "congestion";
        double jam_factor = 0.0;
        double current_speed = free_flow_speed;
        
        if (flow_data.count(edge_key)) {
            const auto& flow = flow_data.at(edge_key);
            has_disruption = true;
            jam_factor = flow.jam_factor;
            current_speed = flow.current_speed > 0 ? flow.current_speed : free_flow_speed;
        }
        
        if (incident_data.count(edge_key)) {
            const auto& incident = incident_data.at(edge_key);
            has_disruption = true;
            is_closed = incident.road_closed;
            incident_type = incident.type.empty() ? incident_type : incident.type;
            
            string severity = get_severity_level(jam_factor, incident_type, is_closed);
            severity_counts[severity]++;
            
            if (is_closed) {
                result.road_closures_count++;
            }
            
            result.total_disruptions_on_route++;
        } else if (has_disruption) {
            string severity = get_severity_level(jam_factor, incident_type, is_closed);
            severity_counts[severity]++;
        }
        
        if (has_disruption) {
            actual_travel_time += calculate_edge_duration(edge_distance, current_speed, free_flow_speed, is_closed);
        } else {
            actual_travel_time += baseline_time;
        }
    }
    
    // Store severity breakdowns
    result.high_severity_count = severity_counts["critical"] + severity_counts["high"];
    result.medium_severity_count = severity_counts["medium"];
    result.low_severity_count = severity_counts["low"];
    
    // Calculate time impact
    result.baseline_eta_seconds = baseline_travel_time;
    result.actual_eta_seconds = actual_travel_time;
    result.added_delay_seconds = actual_travel_time - baseline_travel_time;
    result.delay_percentage = (baseline_travel_time > 0) 
        ? (result.added_delay_seconds / baseline_travel_time) * 100.0 
        : 0.0;
    
    // Count total network disruptions
    result.total_network_disruptions = g_disruption_cache.total_incidents;
    result.total_network_closures = g_disruption_cache.closures;
    result.active_disruptions = g_disruption_cache.active_disruptions;
    
    return result;
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
                         distance_t distance = 0, double query_time_ms = 0, double index_load_time_ms = 0,
                         double index_size_mb = 0.0, double index_size_bytes = 0.0,
                         const vector<NodeID>& path = vector<NodeID>(),
                         const map<NodeID, GPSCoordinate>& coordinates = map<NodeID, GPSCoordinate>(),
                         const map<pair<NodeID, NodeID>, EdgeGeometry>& edge_geometries = map<pair<NodeID, NodeID>, EdgeGeometry>(),
                         bool use_disruptions = false, double tau_threshold = 0.5,
                         const string& disruption_file = "",
                         double disruption_impact_score = 0.0,
                         const string& update_strategy = "",
                         const string& update_reason = "",
                         int nodes_updated = 0,
                         const map<pair<NodeID, NodeID>, TrafficFlowData>& flow_data = map<pair<NodeID, NodeID>, TrafficFlowData>(),
                         const map<pair<NodeID, NodeID>, IncidentInfo>& disruption_map = map<pair<NodeID, NodeID>, IncidentInfo>(),
                         const ContractionIndex* ci = nullptr,
                         const map<NodeID, vector<Neighbor>>& adj_list = map<NodeID, vector<Neighbor>>() ,
                         bool generate_alternatives = true) {
    
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
        cout << "    \"interpolation_used\": false," << endl;
        
        // Calculate and add distance and ETA metrics using ACTUAL traffic data
        double calculated_distance = calculate_route_distance(path, coordinates);
        
        // CRITICAL FIX: Use actual traffic speeds from flow_data instead of jam_factor estimate
        double eta_seconds = calculate_eta_with_disruption(path, flow_data, coordinates);
        string eta_formatted = format_eta_time(eta_seconds);
        
        cout << "    \"calculated_distance_meters\": " << fixed << setprecision(1) << calculated_distance << "," << endl;
        cout << "    \"calculated_distance_km\": " << fixed << setprecision(2) << (calculated_distance / 1000.0) << "," << endl;
        cout << "    \"eta_seconds\": " << fixed << setprecision(0) << eta_seconds << "," << endl;
        cout << "    \"eta_formatted\": \"" << eta_formatted << "\"," << endl;
        
        // DHL Labeling Information (nested object matching HC2L structure)
        if (ci != nullptr) {
            size_t label_count = ci->label_count();
            size_t index_size = ci->size();
            size_t height = ci->height();
            size_t max_label_count = ci->max_label_count();
            size_t max_cut_size = ci->max_cut_size();
            size_t non_empty_cuts = ci->non_empty_cuts();
            double avg_cut_size = ci->avg_cut_size();
            
            cout << "    \"labeling_info\": {" << endl;
            cout << "      \"total_labels\": " << label_count << "," << endl;
            cout << "      \"infinite_labels\": 0," << endl;  // DHL doesn't track infinite labels separately
            cout << "      \"index_size_bytes\": " << index_size << "," << endl;
            cout << "      \"index_size_mb\": " << fixed << setprecision(2) << (index_size / (1024.0 * 1024.0)) << "," << endl;
            cout << "      \"hierarchy_height\": " << height << "," << endl;
            cout << "      \"max_label_count_per_node\": " << max_label_count << "," << endl;
            cout << "      \"max_cut_size\": " << max_cut_size << "," << endl;
            cout << "      \"average_cut_size\": " << fixed << setprecision(2) << avg_cut_size << "," << endl;
            cout << "      \"non_empty_cuts\": " << non_empty_cuts << "," << endl;
            cout << "      \"index_load_time_ms\": " << fixed << setprecision(3) << index_load_time_ms << endl;
            cout << "    }," << endl;
        } else {
            cout << "    \"labeling_info\": {" << endl;
            cout << "      \"total_labels\": 0," << endl;
            cout << "      \"infinite_labels\": 0," << endl;
            cout << "      \"index_size_bytes\": " << fixed << setprecision(0) << index_size_bytes << "," << endl;
            cout << "      \"index_size_mb\": " << fixed << setprecision(2) << index_size_mb << "," << endl;
            cout << "      \"hierarchy_height\": 0," << endl;
            cout << "      \"max_label_count_per_node\": 0," << endl;
            cout << "      \"max_cut_size\": 0," << endl;
            cout << "      \"average_cut_size\": 0.0," << endl;
            cout << "      \"non_empty_cuts\": 0," << endl;
            cout << "      \"index_load_time_ms\": " << fixed << setprecision(3) << index_load_time_ms << endl;
            cout << "    }," << endl;
        }
        
        // Keep backward compatibility fields at top level
        cout << "    \"labeling_time_ms\": " << fixed << setprecision(3) << index_load_time_ms << "," << endl;
        cout << "    \"labeling_size_mb\": " << fixed << setprecision(2) << index_size_mb << "," << endl;
        cout << "    \"labeling_size_bytes\": " << fixed << setprecision(0) << index_size_bytes << endl;
        cout << "  }," << endl;
        
        // Disruption configuration section
        cout << "  \"disruption_config\": {" << endl;
        cout << "    \"use_disruptions\": " << (use_disruptions ? "true" : "false") << "," << endl;
        cout << "    \"disruption_file\": \"" << disruption_file << "\"," << endl;
        cout << "    \"tau_threshold\": " << fixed << setprecision(2) << tau_threshold << "," << endl;
        cout << "    \"tau_used_for\": \"Comparison only - DHL always performs immediate update\"" << endl;
        cout << "  }," << endl;
        
        // DHL update info (for comparison with LazyHC2L)
        cout << "  \"dhl_update_info\": {" << endl;
        cout << "    \"algorithm_type\": \"baseline\"," << endl;
        cout << "    \"update_strategy\": \"" << update_strategy << "\"," << endl;
        cout << "    \"reason\": \"" << update_reason << "\"," << endl;
        cout << "    \"disruption_impact_score\": " << fixed << setprecision(3) << disruption_impact_score << "," << endl;
        cout << "    \"nodes_updated\": " << nodes_updated << "," << endl;
        cout << "    \"note\": \"DHL performs immediate update for all disruptions (no lazy marking)\"" << endl;
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
            cout << "]," << endl;
            cout << "        \"color\": \"#8b5cf6\"," << endl;
            cout << "        \"flow_status\": \"default\"," << endl;
            cout << "        \"jam_factor\": 0.0," << endl;
            cout << "        \"speed_kmh\": 0.0," << endl;
            cout << "        \"speed_reduction\": 0.0," << endl;
            cout << "        \"duration_seconds\": 0.0" << endl;
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
                
                // Clip at snap points - CRITICAL: For same edge cases, always include intermediate geometry
                if (same_edge && can_meet_on_same_edge) {
                    // Same edge, can travel directly between snaps - clip both ends to show path
                    // IMPORTANT: Ensure we preserve the actual edge geometry, not collapse it
                    vector<pair<double, double>> full_geom = coords_to_output;
                    coords_to_output = clip_geometry_between_snaps(full_geom, 
                                                                   start_snap_lat, start_snap_lng,
                                                                   dest_snap_lat, dest_snap_lng);
                    
                    // If clipping resulted in too few points, use original geometry
                    // This handles cases where snaps are very close together
                    if (coords_to_output.size() < 2) {
                        coords_to_output = full_geom;
                    }
                } else if (is_first_edge) {
                    // First edge of multi-edge path: clip from snap point to edge end
                    coords_to_output = clip_geometry_at_snap(coords_to_output, start_snap_lat, start_snap_lng, true);
                } else if (is_last_edge) {
                    // Last edge of multi-edge path: clip from edge start to snap point
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
            
            // Add comprehensive edge details
            // 1. Get road name
            string edge_road_name = "";
            if (edge_geometries.count(edge_key)) {
                edge_road_name = edge_geometries.at(edge_key).road_name;
            }
            
            // 2. Get highway type
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
            
            // 5. Get incident info and compute disruption metrics
            const IncidentInfo* incident_ptr = nullptr;
            const TrafficFlowData* flow_ptr = nullptr;
            
            if (disruption_map.count(edge_key)) {
                incident_ptr = &disruption_map.at(edge_key);
            }
            if (flow_data.count(edge_key)) {
                flow_ptr = &flow_data.at(edge_key);
            }
            
            // Compute disruption metrics combining flow + incident
            EdgeDisruptionMetrics metrics = compute_disruption_metrics(
                incident_ptr, 
                flow_ptr, 
                edge_highway_type, 
                static_cast<distance_t>(edge_distance)  // Use actual edge distance for weight calculations
            );
            
            bool is_closed = incident_ptr ? incident_ptr->road_closed : false;
            
            // CRITICAL FIX: Calculate actual distance for clipped edges BEFORE computing duration
            // For first/last edges, use clipped distance instead of full edge distance
            double actual_distance = edge_distance;  // Default to full distance
            bool edge_is_clipped = false;
            
            if (is_first_edge && !same_edge) {
                // First edge: clipped from start snap to edge end
                if (edge_geometries.count(edge_key)) {
                    actual_distance = calculate_clipped_segment_distance(
                        edge_geometries.at(edge_key).coords,
                        start_snap_lat, start_snap_lng,
                        true  // from_start = true: measure from snap to end
                    );
                    edge_is_clipped = true;
                }
            } else if (is_last_edge && !same_edge) {
                // Last edge: clipped from edge start to dest snap
                if (edge_geometries.count(edge_key)) {
                    actual_distance = calculate_clipped_segment_distance(
                        edge_geometries.at(edge_key).coords,
                        dest_snap_lat, dest_snap_lng,
                        false  // from_start = false: measure from start to snap
                    );
                    edge_is_clipped = true;
                }
            } else if (same_edge && can_meet_on_same_edge) {
                // Same edge case: clipped from start snap to dest snap
                if (edge_geometries.count(edge_key)) {
                    // For same-edge, measure the distance between two snaps
                    // We need to calculate distance of the segment between the two snap points
                    double snap_start_dist = calculate_clipped_segment_distance(
                        edge_geometries.at(edge_key).coords,
                        start_snap_lat, start_snap_lng,
                        true
                    );
                    double snap_end_dist = calculate_clipped_segment_distance(
                        edge_geometries.at(edge_key).coords,
                        dest_snap_lat, dest_snap_lng,
                        false
                    );
                    // The actual distance between snaps is full_edge - (distance_to_start + distance_from_end)
                    actual_distance = edge_distance - (edge_distance - snap_start_dist) - (edge_distance - snap_end_dist);
                    actual_distance = max(0.0, actual_distance);
                    edge_is_clipped = true;
                }
            }
            
            // 6. Calculate edge duration based on traffic conditions using ACTUAL (clipped) distance
            double current_speed_kmh = 0.0;
            double edge_duration_seconds = 0.0;
            
            if (flow_ptr) {
                current_speed_kmh = flow_ptr->current_speed;
                edge_duration_seconds = calculate_edge_duration(actual_distance, current_speed_kmh, free_flow_speed, is_closed);
            } else {
                // Default values when no flow data available - use free-flow speed
                current_speed_kmh = free_flow_speed;
                edge_duration_seconds = calculate_edge_duration(actual_distance, 0.0, free_flow_speed, is_closed);
            }
            
            // Add duration field (CRITICAL FIX: now includes flow-based travel time with clipped distance)
            cout << "        \"duration_seconds\": " << fixed << setprecision(1) << sanitize_json_number(edge_duration_seconds) << "," << endl;
            
            // 7. Add edge metadata
            cout << "        \"road_name\": \"" << escape_json_string(edge_road_name) << "\"," << endl;
            // CRITICAL FIX: Output actual (clipped) distance for first/last edges instead of full edge distance
            cout << "        \"distance_meters\": " << fixed << setprecision(1) << actual_distance << "," << endl;
            cout << "        \"highway_type\": \"" << edge_highway_type << "\"," << endl;
            
            // 8. Output separated incident data (pure CSV data)
            cout << "        \"incident\": {" << endl;
            if (incident_ptr) {
                cout << "          \"id\": \"" << escape_json_string(incident_ptr->id) << "\"," << endl;
                cout << "          \"type\": \"" << escape_json_string(incident_ptr->type) << "\"," << endl;
                cout << "          \"criticality\": \"" << escape_json_string(incident_ptr->criticality) << "\"," << endl;
                cout << "          \"description\": \"" << escape_json_string(incident_ptr->description) << "\"," << endl;
                cout << "          \"road_closed\": " << (incident_ptr->road_closed ? "true" : "false") << "," << endl;
                cout << "          \"start_time\": \"" << escape_json_string(incident_ptr->start_time) << "\"," << endl;
                cout << "          \"end_time\": \"" << escape_json_string(incident_ptr->end_time) << "\"" << endl;
            } else {
                cout << "          \"id\": \"\"," << endl;
                cout << "          \"type\": \"none\"," << endl;
                cout << "          \"criticality\": \"\"," << endl;
                cout << "          \"description\": \"\"," << endl;
                cout << "          \"road_closed\": false," << endl;
                cout << "          \"start_time\": \"\"," << endl;
                cout << "          \"end_time\": \"\"" << endl;
            }
            cout << "        }," << endl;
            
            // 9. Output separated traffic flow data (pure CSV data)
            cout << "        \"flow\": {" << endl;
            if (flow_ptr) {
                // CRITICAL FIX: Use Flow Overlay logic - jam_factor determines severity and color
                string flow_severity = get_flow_overlay_severity(flow_ptr->jam_factor, is_closed);
                string flow_color = get_flow_color_code(flow_ptr->jam_factor, is_closed);
                
                cout << "          \"speed_kph\": " << fixed << setprecision(1) << sanitize_json_number(flow_ptr->current_speed) << "," << endl;
                cout << "          \"free_flow_kph\": " << fixed << setprecision(1) << sanitize_json_number(flow_ptr->free_flow_speed) << "," << endl;
                cout << "          \"jam_factor\": " << fixed << setprecision(2) << sanitize_json_number(flow_ptr->jam_factor) << "," << endl;
                cout << "          \"confidence\": " << fixed << setprecision(3) << sanitize_json_number(flow_ptr->confidence) << "," << endl;
                cout << "          \"traversability\": \"" << escape_json_string(flow_ptr->traversability) << "\"," << endl;
                cout << "          \"status\": \"" << escape_json_string(flow_ptr->flow_status) << "\"," << endl;
                // CRITICAL FIX: Output severity matching Flow Overlay format (Heavy/Medium/Light)
                cout << "          \"severity\": \"" << flow_severity << "\"," << endl;
                // CRITICAL FIX: Output color based on jam_factor, not on computed metrics
                cout << "          \"color\": \"" << flow_color << "\"" << endl;
            } else {
                // Default flow data - use free-flow values when no meaningful disruption
                cout << "          \"speed_kph\": " << fixed << setprecision(1) << free_flow_speed << "," << endl;
                cout << "          \"free_flow_kph\": " << fixed << setprecision(1) << free_flow_speed << "," << endl;
                cout << "          \"jam_factor\": 0.0," << endl;
                cout << "          \"confidence\": 0.99," << endl;
                cout << "          \"traversability\": \"open\"," << endl;
                cout << "          \"status\": \"default\"," << endl;
                cout << "          \"color\": \"#8b5cf6\"" << endl;
            }
            cout << "        }," << endl;
            
            // 10. Output computed disruption metrics (ONLY for edges with meaningful disruption)
            // FIX: Don't output disruption_metrics for non-disrupted edges (severity_score < 0.1)
            if (metrics.severity_score > 0) {
                cout << "        \"disruption_metrics\": {" << endl;
                cout << "          \"severity_level\": \"" << metrics.severity_level << "\"," << endl;
                cout << "          \"severity_score\": " << fixed << setprecision(2) << sanitize_json_number(metrics.severity_score) << "," << endl;
                cout << "          \"weight_multiplier\": " << fixed << setprecision(2) << sanitize_json_number(metrics.weight_multiplier) << "," << endl;
                cout << "          \"impact_score\": " << fixed << setprecision(2) << sanitize_json_number(metrics.impact_score) << "," << endl;
                cout << "          \"time_impact_seconds\": " << fixed << setprecision(1) << sanitize_json_number(metrics.time_impact_seconds) << "," << endl;
                cout << "          \"old_weight\": " << metrics.old_weight << "," << endl;
                cout << "          \"new_weight\": " << metrics.new_weight << endl;
                cout << "        }" << endl;
            } else {
                cout << "        \"disruption_metrics\": {}" << endl;
            }
            
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
            cout << "        \"color\": \"#8b5cf6\"," << endl;
            cout << "        \"flow_status\": \"default\"," << endl;
            cout << "        \"jam_factor\": 0.0," << endl;
            cout << "        \"speed_kmh\": 0.0," << endl;
            cout << "        \"speed_reduction\": 0.0," << endl;
            cout << "        \"duration_seconds\": 0.0" << endl;
            cout << "      }" << endl;
        }
        
        cout << "    ]" << endl;
        
        cout << "  }," << endl;
        
        // ============================================================
        // DISRUPTIONS SUMMARY - Consolidated disruption metrics
        // ============================================================
        cout << "  \"disruptions_summary\": {" << endl;
        
        // Perform disruption analysis on the route
        DisruptionAnalysisResult analysis = analyze_route_disruptions(
            path, disruption_map, flow_data, coordinates, edge_geometries
        );
        
        struct RouteDisruptionDetail {
            pair<NodeID, NodeID> edge;
            EdgeDisruptionMetrics metrics;
            const IncidentInfo* incident;
            const TrafficFlowData* flow;
        };
        vector<RouteDisruptionDetail> route_disruptions;
        map<string, int> route_severity_counts{{"critical", 0}, {"high", 0}, {"medium", 0}, {"low", 0}};
        double total_time_impact = 0.0;
        int route_closures = 0;
        
        for (size_t i = 0; i + 1 < path.size(); i++) {
            auto edge_key = make_pair(path[i], path[i + 1]);
            const IncidentInfo* incident_ptr = nullptr;
            const TrafficFlowData* flow_ptr = nullptr;
            if (disruption_map.count(edge_key)) {
                incident_ptr = &disruption_map.at(edge_key);
            } else if (g_disruption_cache.incidents.count(edge_key)) {
                incident_ptr = &g_disruption_cache.incidents.at(edge_key);
            }
            if (flow_data.count(edge_key)) {
                flow_ptr = &flow_data.at(edge_key);
            } else if (g_disruption_cache.flow_data.count(edge_key)) {
                flow_ptr = &g_disruption_cache.flow_data.at(edge_key);
            }
            auto metrics_it = g_disruption_cache.disruption_metrics.find(edge_key);
            EdgeDisruptionMetrics metrics;
            bool has_metrics = (metrics_it != g_disruption_cache.disruption_metrics.end());
            if (has_metrics) {
                metrics = metrics_it->second;
            } else if (incident_ptr || flow_ptr) {
                string highway_type = "unknown";
                if (g_highway_types.count(edge_key)) {
                    highway_type = g_highway_types.at(edge_key);
                }
                double edge_distance = 0.0;
                if (edge_geometries.count(edge_key)) {
                    edge_distance = edge_geometries.at(edge_key).length;
                }
                metrics = compute_disruption_metrics(
                    incident_ptr,
                    flow_ptr,
                    highway_type,
                    static_cast<distance_t>(edge_distance)
                );
            }
            bool has_data = incident_ptr || flow_ptr || has_metrics;
            if (!has_data) continue;
            bool impactful = (incident_ptr && incident_ptr->road_closed) ||
                             (flow_ptr && flow_ptr->jam_factor > 0.0) ||
                             (metrics.severity_level != "none");
            if (!impactful) continue;
            route_disruptions.push_back({edge_key, metrics, incident_ptr, flow_ptr});
            total_time_impact += metrics.time_impact_seconds;
            if (route_severity_counts.count(metrics.severity_level)) {
                route_severity_counts[metrics.severity_level]++;
            } else if (metrics.severity_level == "critical") {
                route_severity_counts["critical"]++;
            }
            if (incident_ptr && incident_ptr->road_closed) {
                route_closures++;
            }
        }
        
        int route_disruptions_critical = route_severity_counts["critical"];
        int route_disruptions_high = route_severity_counts["high"];
        int route_disruptions_medium = route_severity_counts["medium"];
        int route_disruptions_low = route_severity_counts["low"];
        double route_time_impact = max(total_time_impact, analysis.added_delay_seconds);
        
        cout << "    \"route\": {" << endl;
        cout << "      \"total_disrupted_edges\": " << route_disruptions.size() << "," << endl;
        cout << "      \"critical\": " << route_disruptions_critical << "," << endl;
        cout << "      \"high\": " << route_disruptions_high << "," << endl;
        cout << "      \"medium\": " << route_disruptions_medium << "," << endl;
        cout << "      \"low\": " << route_disruptions_low << "," << endl;
        cout << "      \"closures\": " << route_closures << "," << endl;
        cout << "      \"total_time_impact_seconds\": " << fixed << setprecision(1) << route_time_impact << "," << endl;
        cout << "      \"total_time_impact_minutes\": " << fixed << setprecision(1) << (route_time_impact / 60.0) << "," << endl;
        cout << "      \"baseline_eta_seconds\": " << fixed << setprecision(1) << analysis.baseline_eta_seconds << "," << endl;
        cout << "      \"actual_eta_seconds\": " << fixed << setprecision(1) << analysis.actual_eta_seconds << "," << endl;
        cout << "      \"percentage_increase\": " << fixed << setprecision(1) << analysis.delay_percentage << endl;
        cout << "    }," << endl;
        
        int network_total = 0;
        int network_critical = 0;
        int network_high = 0;
        int network_medium = 0;
        int network_low = 0;
        int network_closures = 0;
        int network_active = 0;
        
        if (use_disruptions) {
            for (const auto& [edge_key, metrics] : g_disruption_cache.disruption_metrics) {
                const IncidentInfo* incident_ptr = nullptr;
                if (g_disruption_cache.incidents.count(edge_key)) {
                    incident_ptr = &g_disruption_cache.incidents.at(edge_key);
                }
                const TrafficFlowData* flow_ptr = nullptr;
                if (g_disruption_cache.flow_data.count(edge_key)) {
                    flow_ptr = &g_disruption_cache.flow_data.at(edge_key);
                }
                bool has_data = incident_ptr || flow_ptr;
                if (!has_data) continue;
                bool active = (metrics.severity_level != "none") ||
                              (flow_ptr && flow_ptr->jam_factor > 0.0) ||
                              (incident_ptr && incident_ptr->road_closed);
                if (!active) continue;
                network_total++;
                if (incident_ptr && incident_ptr->road_closed) {
                    network_closures++;
                } else {
                    network_active++;
                }
                if (metrics.severity_level == "critical") network_critical++;
                else if (metrics.severity_level == "high") network_high++;
                else if (metrics.severity_level == "medium") network_medium++;
                else if (metrics.severity_level == "low") network_low++;
            }
        }
        
        cout << "    \"network\": {" << endl;
        cout << "      \"total_incidents\": " << network_total << "," << endl;
        cout << "      \"critical\": " << network_critical << "," << endl;
        cout << "      \"high\": " << network_high << "," << endl;
        cout << "      \"medium\": " << network_medium << "," << endl;
        cout << "      \"low\": " << network_low << "," << endl;
        cout << "      \"closures\": " << network_closures << "," << endl;
        cout << "      \"active_disruptions\": " << network_active << endl;
        cout << "    }," << endl;
        
        sort(route_disruptions.begin(), route_disruptions.end(),
             [](const RouteDisruptionDetail& a, const RouteDisruptionDetail& b) {
                 bool a_closed = a.incident && a.incident->road_closed;
                 bool b_closed = b.incident && b.incident->road_closed;
                 if (a_closed != b_closed) return a_closed > b_closed;
                 if (std::abs(a.metrics.severity_score - b.metrics.severity_score) > 1e-6) {
                     return a.metrics.severity_score > b.metrics.severity_score;
                 }
                 return a.edge < b.edge;
             });
        
        cout << "    \"all_disruptions\": [" << endl;
        for (size_t i = 0; i < route_disruptions.size(); i++) {
            const auto& detail = route_disruptions[i];
            const auto& edge = detail.edge;
            const auto* incident = detail.incident;
            const auto* flow_ptr = detail.flow;
            const auto& metrics = detail.metrics;
            
            string road_name = "";
            if (edge_geometries.count(edge)) {
                road_name = edge_geometries.at(edge).road_name;
            }
            string highway_type = "unknown";
            if (g_highway_types.count(edge)) {
                highway_type = g_highway_types.at(edge);
            }
            
            cout << "      {" << endl;
            cout << "        \"source\": " << edge.first << "," << endl;
            cout << "        \"target\": " << edge.second << "," << endl;
            cout << "        \"road_name\": \"" << escape_json_string(road_name) << "\"," << endl;
            cout << "        \"highway_type\": \"" << highway_type << "\"," << endl;
            
            cout << "        \"incident\": {" << endl;
            if (incident) {
                cout << "          \"id\": \"" << escape_json_string(incident->id) << "\"," << endl;
                cout << "          \"type\": \"" << escape_json_string(incident->type) << "\"," << endl;
                cout << "          \"criticality\": \"" << escape_json_string(incident->criticality) << "\"," << endl;
                cout << "          \"description\": \"" << escape_json_string(incident->description) << "\"," << endl;
                cout << "          \"road_closed\": " << (incident->road_closed ? "true" : "false") << "," << endl;
                cout << "          \"start_time\": \"" << escape_json_string(incident->start_time) << "\"," << endl;
                cout << "          \"end_time\": \"" << escape_json_string(incident->end_time) << "\"" << endl;
            } else {
                cout << "          \"id\": \"\"," << endl;
                cout << "          \"type\": \"\"," << endl;
                cout << "          \"criticality\": \"\"," << endl;
                cout << "          \"description\": \"\"," << endl;
                cout << "          \"road_closed\": false," << endl;
                cout << "          \"start_time\": \"\"," << endl;
                cout << "          \"end_time\": \"\"" << endl;
            }
            cout << "        }," << endl;
            
            cout << "        \"flow\": {" << endl;
            if (flow_ptr) {
                cout << "          \"status\": \"" << escape_json_string(flow_ptr->flow_status) << "\"," << endl;
                cout << "          \"speed_kph\": " << fixed << setprecision(1) << sanitize_json_number(flow_ptr->current_speed) << "," << endl;
                cout << "          \"jam_factor\": " << fixed << setprecision(2) << sanitize_json_number(flow_ptr->jam_factor) << endl;
            } else {
                cout << "          \"status\": \"default\"," << endl;
                cout << "          \"speed_kph\": 0.0," << endl;
                cout << "          \"jam_factor\": 0.0" << endl;
            }
            cout << "        }," << endl;
            
            cout << "        \"disruption_metrics\": {" << endl;
            cout << "          \"severity_level\": \"" << metrics.severity_level << "\"," << endl;
            cout << "          \"severity_score\": " << fixed << setprecision(2) << sanitize_json_number(metrics.severity_score) << "," << endl;
            cout << "          \"weight_multiplier\": " << fixed << setprecision(2) << sanitize_json_number(metrics.weight_multiplier) << "," << endl;
            cout << "          \"time_impact_seconds\": " << fixed << setprecision(1) << sanitize_json_number(metrics.time_impact_seconds) << "," << endl;
            cout << "          \"old_weight\": " << metrics.old_weight << "," << endl;
            cout << "          \"new_weight\": " << metrics.new_weight << endl;
            cout << "        }" << endl;
            
            cout << "      }";
            if (i < route_disruptions.size() - 1) cout << ",";
            cout << endl;
        }
        cout << "    ]" << endl;
        
        cout << "  }," << endl;
        
        // Generate alternative routes (k-shortest paths) with disruption awareness
        vector<AlternativeRoute> alternatives;
        if (generate_alternatives && use_disruptions && !path.empty() && path.size() >= 2 && !adj_list.empty() && (!flow_data.empty() || !disruption_map.empty())) {
            cerr << "\n🔀 Generating alternative routes with disruption awareness (Flow + Incidents)..." << endl;
            NodeID route_start = path.front();
            NodeID route_dest = path.back();
            alternatives = generate_alternative_routes(
                route_start, route_dest, adj_list, flow_data, disruption_map, coordinates, 3
            );
        }
        
        // Output alternative routes
        cout << "  \"alternative_routes\": [" << endl;
        for (size_t i = 0; i < alternatives.size(); i++) {
            const auto& alt = alternatives[i];
            
            // Build detailed geometry segments from edges
            vector<map<string, string>> geometry_segments;
            for (size_t k = 0; k < alt.path.size() - 1; k++) {
                NodeID u = alt.path[k];
                NodeID v = alt.path[k + 1];
                auto edge_key = make_pair(u, v);
                
                // Look up edge geometry
                vector<pair<double, double>> edge_coords;
                string highway_type = "unknown";
                if (edge_geometries.count(edge_key)) {
                    const auto& geom = edge_geometries.at(edge_key);
                    edge_coords = geom.coords;  // Use coords from EdgeGeometry
                }
                
                // Get actual highway type from road data
                if (g_highway_types.count(edge_key)) {
                    highway_type = g_highway_types.at(edge_key);
                }
                
                // Create geometry segment with edge metadata
                map<string, string> segment;
                segment["source"] = to_string(u);
                segment["target"] = to_string(v);
                segment["color"] = "#9333ea";  // Purple for alternatives
                segment["highway_type"] = highway_type;
                
                // Store coordinates as GeoJSON format [lng, lat]
                string coords_str = "[";
                for (size_t j = 0; j < edge_coords.size(); j++) {
                    if (j > 0) coords_str += ", ";
                    coords_str += "[" + to_string(edge_coords[j].first) + ", " + to_string(edge_coords[j].second) + "]";
                }
                coords_str += "]";
                segment["coordinates"] = coords_str;
                
                geometry_segments.push_back(segment);
            }
            
            cout << "    {" << endl;
            cout << "      \"rank\": " << alt.rank << "," << endl;
            cout << "      \"description\": \"" << escape_json_string(alt.description) << "\"," << endl;
            cout << "      \"distance_meters\": " << alt.distance << "," << endl;
            cout << "      \"eta_seconds\": " << fixed << setprecision(1) << alt.eta_seconds << "," << endl;
            cout << "      \"eta_formatted\": \"" << format_eta_time(alt.eta_seconds) << "\"," << endl;
            cout << "      \"avg_jam_factor\": " << fixed << setprecision(2) << alt.avg_jam_factor << "," << endl;
            cout << "      \"path_length\": " << alt.path.size() << "," << endl;
            
            // Output detailed geometry segments with edge metadata (no path_nodes, no path_node_ids, no redundant edge field)
            cout << "      \"geometry\": [" << endl;
            for (size_t k = 0; k < geometry_segments.size(); k++) {
                cout << "        {" << endl;
                cout << "          \"source\": " << geometry_segments[k]["source"] << "," << endl;
                cout << "          \"target\": " << geometry_segments[k]["target"] << "," << endl;
                cout << "          \"coordinates\": " << geometry_segments[k]["coordinates"] << "," << endl;
                cout << "          \"color\": \"" << geometry_segments[k]["color"] << "\"," << endl;
                cout << "          \"highway_type\": \"" << geometry_segments[k]["highway_type"] << "\"" << endl;
                cout << "        }";
                if (k < geometry_segments.size() - 1) cout << ",";
                cout << endl;
            }
            cout << "      ]" << endl;
            
            cout << "    }";
            if (i < alternatives.size() - 1) cout << ",";
            cout << endl;
        }
        cout << "  ]" << endl;
    }
    
    cout << "}" << endl;
}

int main(int argc, char* argv[]) {
    // Optimize I/O for large JSON output
    setup_fast_io();
    
    // Accept 18 args (no disruption), 19 args (with disruption file), 20 args (with disruption + tau), or 21 args (with generate_alternatives)
    // Args: 14 routing params + 3 data files + optional disruption_file + optional tau_threshold + optional generate_alternatives
    // argc includes argv[0] (program name), so:
    //   - argc=18: argv[0-17] = program + 14 params + 3 files
    //   - argc=19: argv[0-18] = program + 14 params + 3 files + disruption
    //   - argc=20: argv[0-19] = program + 14 params + 3 files + disruption + tau
    //   - argc=21: argv[0-20] = program + 14 params + 3 files + disruption + tau + generate_alternatives
    if (argc != 18 && argc != 19 && argc != 20 && argc != 21) {
        output_json_response(false, "Invalid arguments. Usage: dhl_routing_api <start_pin_lat> <start_pin_lng> <start_snap_lat> <start_snap_lng> <start_edge_source> <start_edge_target> <start_edge_oneway> <dest_pin_lat> <dest_pin_lng> <dest_snap_lat> <dest_snap_lng> <dest_edge_source> <dest_edge_target> <dest_edge_oneway> <nodes_csv> <edges_csv> <index_file> [disruption_file] [tau_threshold] [generate_alternatives]");
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
        
        // Parse optional generate_alternatives flag (arg 20)
        bool generate_alternatives = true; // Default to true for backward compatibility
        if (argc >= 21) {
            generate_alternatives = (stoi(argv[20]) == 1);
        }
        
        // DHL always performs immediate update (no lazy marking)
        double disruption_impact_score = 0.0;
        string update_strategy = "none";
        string update_reason = "No disruptions loaded";
        
        // Derive node ID mapping file path from nodes_csv path
        // nodes_csv is like "/path/to/data/raw/quezon_city_nodes.csv"
        // mapping file is "/path/to/data/raw/node_id_mapping.csv"
        string mapping_file = nodes_csv.substr(0, nodes_csv.find_last_of('/') + 1) + "node_id_mapping.csv";
        
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

        map<pair<NodeID, NodeID>, distance_t> base_weights;
        for (const auto& [source, neighbors] : adj_list) {
            for (const auto& neighbor : neighbors) {
                base_weights[{source, neighbor.node}] = neighbor.distance;
            }
        }
        
        // Load DHL index and measure time
        auto index_load_start = chrono::high_resolution_clock::now();
        
        // Get index file size for metrics
        struct stat index_stat;
        double index_size_bytes = 0.0;
        double index_size_mb = 0.0;
        if (stat(index_file.c_str(), &index_stat) == 0) {
            index_size_bytes = static_cast<double>(index_stat.st_size);
            index_size_mb = index_size_bytes / (1024.0 * 1024.0);
            cerr << "📦 DHL Index file size: " << index_size_mb << " MB" << endl;
        }
        
        ifstream index_stream(index_file, ios::binary);
        if (!index_stream.is_open()) {
            output_json_response(false, "Failed to open index file");
            return 1;
        }
        ContractionIndex ci(index_stream);
        index_stream.close();
        
        auto index_load_end = chrono::high_resolution_clock::now();
        chrono::duration<double, milli> index_load_duration = index_load_end - index_load_start;
        double index_load_time_ms = index_load_duration.count();
        
        // ============================================================
        // DHL: Process disruptions if provided (WITH CACHING)
        // ============================================================
        map<pair<NodeID, NodeID>, TrafficFlowData> flow_data;
        map<pair<NodeID, NodeID>, IncidentInfo> incident_data;
        int nodes_updated = 0;
        
        if (use_disruptions) {
            cerr << "🔧 DHL Processing disruptions from: " << disruption_file << endl;
            cerr << "   DHL always performs immediate update (no lazy marking)" << endl;
            cerr << "   Tau threshold (for comparison): " << tau_threshold << endl;
            
            // *** LOAD HERE API DISRUPTION DATA (flow and incidents) ***
            bool load_success = load_disruptions_with_cache(
                disruption_file, incident_data, flow_data, adj_list, edge_geometries
            );
            
            if (!load_success) {
                cerr << "⚠️  Failed to load disruptions" << endl;
                use_disruptions = false;
            } else {
                // *** LOAD USER-REPORTED DISRUPTIONS ***
                // User disruptions are stored in timestamped files in disruptions/user_incident/
                // Function will find and load the latest user_incident_*.csv file
                int user_count = load_user_reported_disruptions(
                    disruption_file, flow_data, incident_data
                );
                
                if (user_count > 0) {
                    cerr << "   ✅ Merged " << user_count << " user-reported disruptions into routing data" << endl;
                }
                
                set<pair<NodeID, NodeID>> disruption_edges;
                for (const auto& [edge_key, _] : incident_data) {
                    disruption_edges.insert(edge_key);
                }
                for (const auto& [edge_key, _] : flow_data) {
                    disruption_edges.insert(edge_key);
                }
                
                int disruption_count = 0;
                int closed_roads_count = 0;
                set<NodeID> affected_nodes;
                
                for (const auto& edge_key : disruption_edges) {
                    NodeID source = edge_key.first;
                    NodeID target = edge_key.second;
                    const IncidentInfo* incident_ptr = nullptr;
                    const TrafficFlowData* flow_ptr = nullptr;
                    
                    if (incident_data.count(edge_key)) {
                        incident_ptr = &incident_data.at(edge_key);
                    }
                    if (flow_data.count(edge_key)) {
                        flow_ptr = &flow_data.at(edge_key);
                    }
                    if (!incident_ptr && !flow_ptr) continue;
                    
                    string highway_type = "unknown";
                    if (g_highway_types.count(edge_key)) {
                        highway_type = g_highway_types.at(edge_key);
                    }
                    
                    distance_t base_weight = 0;
                    if (base_weights.count(edge_key)) {
                        base_weight = base_weights.at(edge_key);
                    } else if (adj_list.count(source)) {
                        for (const auto& neighbor : adj_list.at(source)) {
                            if (neighbor.node == target) {
                                base_weight = neighbor.distance;
                                break;
                            }
                        }
                    }
                    
                    distance_t new_weight = calculate_disruption_weight(
                        source, target,
                        base_weight,
                        flow_ptr,
                        incident_ptr,
                        highway_type
                    );
                    
                    bool flow_closure = flow_ptr && (flow_ptr->traversability == "closed" || flow_ptr->jam_factor >= 9.5);
                    bool incident_closure = incident_ptr && incident_ptr->road_closed;
                    bool is_closed = flow_closure || incident_closure || new_weight >= infinity;
                    
                    if (is_closed) {
                        cerr << "   🚧 Road CLOSED: Edge " << source << "->" << target;
                        if (incident_ptr && !incident_ptr->type.empty()) {
                            cerr << " (Type: " << incident_ptr->type << ")";
                        }
                        cerr << endl;
                        closed_roads_count++;
                        
                        // Block ALL occurrences of the primary direction (handle duplicates)
                        int blocked_count = 0;
                        if (adj_list.count(source)) {
                            for (auto& neighbor : adj_list[source]) {
                                if (neighbor.node == target) {
                                    neighbor.distance = infinity;
                                    blocked_count++;
                                }
                            }
                        }
                        cerr << "   🚫 Blocked: " << source << " → " << target << " (" << blocked_count << " occurrence(s), weight=infinity)" << endl;
                        
                        // IMPORTANT: Also block ALL occurrences of reverse direction for road closures!
                        int blocked_reverse_count = 0;
                        if (adj_list.count(target)) {
                            for (auto& neighbor : adj_list[target]) {
                                if (neighbor.node == source) {
                                    neighbor.distance = infinity;
                                    blocked_reverse_count++;
                                }
                            }
                        }
                        if (blocked_reverse_count > 0) {
                            cerr << "   🚫 Blocked (reverse): " << target << " → " << source << " (" << blocked_reverse_count << " occurrence(s), weight=infinity)" << endl;
                        }
                        
                        disruption_impact_score = 1.0;
                    } else {
                        // Update ALL occurrences of this edge (handle duplicates)
                        int updated_count = 0;
                        if (adj_list.count(source)) {
                            for (auto& neighbor : adj_list[source]) {
                                if (neighbor.node == target) {
                                    neighbor.distance = new_weight;
                                    updated_count++;
                                }
                            }
                        }
                        double impact = 0.0;
                        if (base_weight > 0) {
                            impact = min(1.0, max(0.0, (static_cast<double>(new_weight) - base_weight) / static_cast<double>(base_weight)));
                        }
                        disruption_impact_score = max(disruption_impact_score, impact);
                    }
                    
                    affected_nodes.insert(source);
                    affected_nodes.insert(target);
                    if (adj_list.count(source)) {
                        for (const auto& neighbor : adj_list.at(source)) {
                            affected_nodes.insert(neighbor.node);
                        }
                    }
                    if (adj_list.count(target)) {
                        for (const auto& neighbor : adj_list.at(target)) {
                            affected_nodes.insert(neighbor.node);
                        }
                    }
                    
                    double jam_factor_val = flow_ptr ? flow_ptr->jam_factor : 0.0;
                    string type_label = incident_ptr ? incident_ptr->type : (flow_ptr ? "flow" : "unknown");
                    cerr << "   ⚡ Immediate update for edge " << source << "->" << target 
                         << " (Weight=" << new_weight << ", Jam=" << jam_factor_val 
                         << ", Highway=" << highway_type << ", Type=" << type_label << ")" << endl;
                    
                    disruption_count++;
                }
                
                nodes_updated = affected_nodes.size();
                update_strategy = "immediate_update";
                update_reason = "DHL baseline: always immediate update for all disruptions";
                
                cerr << "✅ DHL processed " << disruption_count << " disruptions with caching" << endl;
                cerr << "   - Closed roads: " << closed_roads_count << endl;
                cerr << "   - Active disruptions: " << (disruption_count - closed_roads_count) << endl;
                cerr << "   - Nodes updated: " << nodes_updated << endl;
            }
        }
        
        // Determine routing endpoints based on one-way constraints
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
        
        // Input IDs are already sequential IDs (not OSM IDs anymore)
        // Just use them directly without conversion
        vector<NodeID> start_candidates = start_candidates_osm;
        vector<NodeID> dest_candidates = dest_candidates_osm;
        
        if (start_candidates.empty() || dest_candidates.empty()) {
            cerr << "⚠️  No valid routing endpoints provided" << endl;
            output_json_response(false, "No valid start/dest nodes for routing");
            return 1;
        }
        
        // Find best route using DHL labels
        auto start_time = chrono::high_resolution_clock::now();
        
        distance_t best_distance = numeric_limits<distance_t>::max();
        NodeID best_start_seq = 0, best_dest_seq = 0;
        
        for (NodeID s : start_candidates) {
            for (NodeID d : dest_candidates) {
                distance_t dist = ci.get_distance(s, d);
                if (dist < best_distance) {
                    best_distance = dist;
                    best_start_seq = s;
                    best_dest_seq = d;
                }
            }
        }
        
        auto end_time = chrono::high_resolution_clock::now();
        double query_time_ms = chrono::duration<double, milli>(end_time - start_time).count();
        
        if (best_start_seq == 0 || best_dest_seq == 0) {
            output_json_response(false, "No valid path found");
            return 1;
        }
        
        // IDs are already sequential, no need to convert
        NodeID best_start = best_start_seq;
        NodeID best_dest = best_dest_seq;
        
        // Find actual path using Dijkstra with comprehensive cost calculation
        // *** USES ENHANCED VERSION WITH HIGHWAY, FLOW, AND INCIDENT DATA ***
        vector<NodeID> path = find_shortest_path(best_start, best_dest, adj_list, 
                                                  coordinates, flow_data, incident_data);
        
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
            // CRITICAL: Respect one-way direction when setting path
            path.clear();
            
            // For one-way edges, only allow travel in valid direction
            if (start_edge_oneway == 1) {
                // Forward only: must be source→target
                path.push_back(start_edge_source);
                path.push_back(start_edge_target);
            } else if (start_edge_oneway == -1) {
                // Reverse only: must be target→source (reverse direction)
                path.push_back(start_edge_target);
                path.push_back(start_edge_source);
            } else {
                // Bidirectional: prefer logical direction (start→dest in edge order)
                path.push_back(start_edge_source);
                path.push_back(start_edge_target);
            }
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
                           best_distance, query_time_ms, index_load_time_ms,
                           index_size_mb, index_size_bytes,
                           path, coordinates,
                           edge_geometries, use_disruptions, tau_threshold,
                           disruption_file, disruption_impact_score,
                           update_strategy, update_reason, nodes_updated, flow_data, incident_data, &ci, adj_list, generate_alternatives);
        
        return 0;
        
    } catch (const exception& e) {
        output_json_response(false, string("Exception: ") + e.what());
        return 1;
    }
}
