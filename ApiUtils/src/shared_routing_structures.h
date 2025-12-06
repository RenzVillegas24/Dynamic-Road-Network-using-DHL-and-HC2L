#ifndef SHARED_ROUTING_STRUCTURES_H
#define SHARED_ROUTING_STRUCTURES_H

/**
 * Shared Routing Structures
 * 
 * Common data structures used by both DHL and HC2L routing APIs
 * Centralized location for consistency and easier maintenance
 * 
 * NOTE: Types (NodeID, distance_t) are defined in road_network.h
 */

 #define _USE_MATH_DEFINES

#include <string>
#include <vector>
#include <map>
#include <ctime>
#include <sys/stat.h>

// Define types if not already defined (road_network.h defines these but this header should work standalone)
#include <cstdint>
#ifndef NODEID
#define NODEID
typedef uint32_t NodeID;
#endif

#ifndef DISTANCE_T
#define DISTANCE_T
typedef uint32_t distance_t;
#endif

// ============================================================
// BASIC STRUCTURES
// ============================================================

/**
 * Edge geometry information
 * Stores geometry coordinates and metadata for an edge
 */
struct EdgeGeometry {
    NodeID source;
    NodeID target;
    distance_t length;                          // Length in meters
    std::string road_name;                      // Road name from OSM data
    std::vector<std::pair<double, double>> coords; // [lon, lat] pairs
    
    EdgeGeometry() : source(0), target(0), length(0), road_name("") {}
};

/**
 * GPS coordinate with node reference
 */
struct GPSCoordinate {
    double latitude;
    double longitude;
    NodeID node_id;
    
    GPSCoordinate() : latitude(0), longitude(0), node_id(0) {}
    GPSCoordinate(double lat, double lng, NodeID id) 
        : latitude(lat), longitude(lng), node_id(id) {}
};

// ============================================================
// TRAFFIC & INCIDENT DATA
// ============================================================

/**
 * Traffic flow data from HERE API or other sources
 * Represents real-time traffic conditions
 * 
 * NOTE: color_code and flow_status have been REMOVED.
 * Color determination is now handled entirely by the frontend (TrafficUtils.js)
 * based on jam_factor value. This ensures consistent coloring across all displays.
 */
struct TrafficFlowData {
    double jam_factor;              // 0.0 to 10.0 (HERE API scale)
    double current_speed;           // Current speed in km/h
    double free_flow_speed;         // Free-flow speed in km/h
    double speed_reduction;         // Percentage: 0.0 to 1.0
    double confidence;              // 0.0 to 1.0 (data reliability)
    std::string traversability;     // "open", "closed", "restricted"
    
    TrafficFlowData() 
        : jam_factor(0.0), current_speed(0.0), free_flow_speed(50.0),
          speed_reduction(0.0), confidence(0.99), traversability("open") {}
};

/**
 * Incident information from external sources
 * Represents what happened on the road (pure incident data)
 */
struct IncidentInfo {
    std::string id;                 // incident_id from CSV
    std::string type;               // accident, construction, closure, etc.
    std::string criticality;        // minor, major, severe, critical
    std::string description;        // Human-readable description
    bool road_closed;               // True if road is completely closed
    std::string start_time;         // ISO 8601 format
    std::string end_time;           // ISO 8601 format
    
    IncidentInfo() 
        : id(""), type(""), criticality(""), description(""),
          road_closed(false), start_time(""), end_time("") {}
    
    // An incident exists if:
    // 1. It has a non-empty ID, OR
    // 2. It has a non-empty type, OR
    // 3. The road is closed
    bool has_incident() const { 
        return !id.empty() || !type.empty() || road_closed; 
    }
};

// ============================================================
// DISRUPTION METRICS
// ============================================================

/**
 * Computed disruption metrics for routing decisions
 * Derived from traffic flow + incident data
 * Represents how to route around disruptions
 */
struct EdgeDisruptionMetrics {
    double severity_score;          // 0.0 to 1.0 (combined severity)
    std::string severity_level;     // critical, high, medium, low, none
    double weight_multiplier;       // Cost multiplier for routing
    double impact_score;            // Combined impact metric
    double time_impact_seconds;     // Extra time added in seconds
    distance_t old_weight;          // Original edge weight
    distance_t new_weight;          // Updated weight with disruption
    double effective_jam_factor;    // CRITICAL: Actual jam_factor for consistency with Flow Overlay
                                    // 0.0-10.0 scale: 0.0=free flow, 10.0=blocked
    
    EdgeDisruptionMetrics() 
        : severity_score(0.0), severity_level("none"),
          weight_multiplier(1.0), impact_score(0.0),
          time_impact_seconds(0.0), old_weight(0), new_weight(0),
          effective_jam_factor(0.0) {}
};

// ============================================================
// CACHING & AGGREGATION
// ============================================================

/**
 * Disruption cache: stores parsed disruption data to avoid re-parsing
 * Now includes precomputed EdgeDisruptionMetrics for each edge
 */
struct DisruptionCache {
    // Raw data from CSV
    std::map<std::pair<NodeID, NodeID>, IncidentInfo> incidents;
    std::map<std::pair<NodeID, NodeID>, TrafficFlowData> flow_data;
    
    // Computed disruption metrics (NEW - precomputed in load_disruptions_with_cache)
    std::map<std::pair<NodeID, NodeID>, EdgeDisruptionMetrics> disruption_metrics;
    
    // Cache metadata
    time_t file_modified_time;
    std::string file_path;
    int total_incidents;
    int closures;
    int active_disruptions;
    
    DisruptionCache() 
        : file_modified_time(0), total_incidents(0),
          closures(0), active_disruptions(0) {}
    
    /**
     * Check if cache is valid (file hasn't changed)
     */
    bool is_valid(const std::string& filepath) const {
        if (filepath != file_path) return false;
        
        struct stat file_stat;
        if (stat(filepath.c_str(), &file_stat) != 0) return false;
        
        return file_stat.st_mtime == file_modified_time;
    }
};

// ============================================================
// ALTERNATIVE ROUTES
// ============================================================

/**
 * Alternative route structure for k-shortest paths
 * Used to provide multiple routing options
 */
struct AlternativeRoute {
    std::vector<NodeID> path;       // Node IDs in the path
    distance_t distance;            // Total distance in meters
    double eta_seconds;             // Estimated time in seconds
    double avg_jam_factor;          // Average jam factor along route
    int rank;                       // Rank (1 = best, 2 = second best, etc.)
    std::string description;        // Human-readable description
    
    AlternativeRoute() 
        : distance(0), eta_seconds(0.0), avg_jam_factor(5.0),
          rank(1), description("") {}
};

#endif // SHARED_ROUTING_STRUCTURES_H
