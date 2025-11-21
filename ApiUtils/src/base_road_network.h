#pragma once

/**
 * Base Road Network Header
 * 
 * Common structures and types shared between DHL and HC2L implementations
 * This header contains all algorithm-independent data structures and utility functions
 * 
 * Each algorithm (DHL, HC2L) provides its own road_network.h that includes this file
 * and adds algorithm-specific structures and methods.
 */

#include <cstdint>
#include <climits>
#include <vector>
#include <ostream>
#include <cassert>

namespace road_network {

// ============================================================
// BASIC TYPE DEFINITIONS
// ============================================================

typedef uint32_t NodeID;
typedef uint32_t SubgraphID;
typedef uint32_t distance_t;

const distance_t infinity = UINT32_MAX >> 1;

// Special sentinel values
const NodeID NO_NODE = 0;  // null value equivalent for node IDs
const SubgraphID NO_SUBGRAPH = 0;  // used to indicate node does not belong to any active subgraph

// Forward declarations
struct Neighbor;
class Graph;

// ============================================================
// PARTITION BITVECTOR UTILITIES (PBV)
// ============================================================

/**
 * Helper functions for manipulating partition bitvectors
 * Used for hierarchical graph partitioning
 */
namespace PBV
{
    // construct partition bitvector from bit pattern and length
    uint64_t from(uint64_t bits, uint16_t length);
    // split partition bitvector into components
    uint64_t partition(uint64_t bv);
    uint16_t cut_level(uint64_t bv);
    // compute cut level of least common ancestor of given bitvectors
    uint16_t lca_level(uint64_t bv1, uint64_t bv2);
    // compute bitvector for least common ancestor of given bitvectors
    uint64_t lca(uint64_t bv1, uint64_t bv2);
    // check whether node is an ancestor of another, based on their bitvectors
    bool is_ancestor(uint64_t bv_ancestor, uint64_t bv_descendant);
}

// ============================================================
// SHARED GRAPH STRUCTURES
// ============================================================

/**
 * Neighbor structure: represents an edge with distance
 * Used in adjacency lists throughout the graph
 */
struct Neighbor
{
    NodeID node;
    distance_t distance;
    Neighbor(NodeID node, distance_t distance);
    bool operator<(const Neighbor &other) const;
};

std::ostream& operator<<(std::ostream& os, const Neighbor &n);

/**
 * Node structure: represents a vertex in the graph
 * Stores adjacency information and temporary algorithm data
 */
struct Node
{
    std::vector<Neighbor> neighbors;
    // subgraph identifier
    SubgraphID subgraph_id;
    Node(SubgraphID subgraph_id);
private:
    // temporary data used by algorithms
    distance_t distance, outcopy_distance;
#ifdef MULTI_THREAD_DISTANCES
    distance_t distances[MULTI_THREAD_DISTANCES];
#endif
    NodeID inflow, outflow;
    uint16_t landmark_level;

    friend class Graph;
};

std::ostream& operator<<(std::ostream& os, const Node &n);

/**
 * Multi-threading support for node data
 * Inherits from std::vector<Node> to store all node data
 */
class MultiThreadNodeData : public std::vector<Node>
{
public:
    void normalize()
    {
        // No special normalization needed
    }
};

/**
 * Partition structure: represents a graph partition
 * Used during hierarchical decomposition
 */
struct Partition
{
    std::vector<NodeID> left, right, cut;
    // rates quality of partition (cutsize + balance)
    double rating() const;
};

std::ostream& operator<<(std::ostream& os, const Partition &p);
std::ostream& operator<<(std::ostream& os, const Partition *p);

/**
 * Edge structure: represents an undirected edge with distance
 * Used for edge enumeration and analysis
 */
struct Edge
{
    NodeID a, b;
    distance_t d;
    Edge(NodeID a, NodeID b, distance_t d);
    bool operator<(Edge other) const;
};

/**
 * Helper structure for pre-partitioning
 * Stores difference data between distances to partition endpoints
 */
struct DiffData
{
    NodeID node;
    distance_t dist_a, dist_b;
    int32_t diff() const;
    distance_t min() const;

    DiffData(NodeID node, distance_t dist_a, distance_t dist_b);
    // comparison function for easy sorting by diff values
    static bool cmp_diff(DiffData x, DiffData y);

    friend std::ostream& operator<<(std::ostream& os, const DiffData &dd);
};

// ============================================================
// COMMON UTILITY FUNCTIONS
// ============================================================

/**
 * Generate unique subgraph IDs
 * @param reset - If true, reset the counter to 0
 * @return Next subgraph ID
 */
SubgraphID next_subgraph_id(bool reset = false);

// ============================================================
// BASE GRAPH CLASS - COMMON GRAPH OPERATIONS
// ============================================================

/**
 * BaseGraph: Common graph operations shared between DHL and HC2L
 * 
 * Provides basic graph manipulation and query operations that are identical
 * across both algorithms. Algorithm-specific functionality is implemented
 * by derived classes (DHL::Graph, HC2L::Graph).
 */
class BaseGraph
{
protected:
    std::vector<NodeID> nodes;                    // Active nodes in the graph
    SubgraphID subgraph_id;                       // ID of this subgraph
    static NodeID s, t;                           // Source and sink nodes
    // NOTE: node_data is managed by derived classes
    
public:
    virtual ~BaseGraph() = default;
    
    // ============ Helper: Get the node_data storage (must be implemented by derived class) ============
    virtual MultiThreadNodeData& get_node_data() = 0;
    virtual const MultiThreadNodeData& get_node_data() const = 0;
    
    // ============ Basic Graph Queries - IMPLEMENTED IN BASE CLASS ============
    
    /**
     * Check if a node belongs to this subgraph
     */
    virtual bool contains(NodeID node) const;
    
    /**
     * Get number of nodes in this subgraph
     */
    virtual size_t node_count() const;
    
    /**
     * Get total number of edges in this subgraph
     */
    virtual size_t edge_count() const;
    
    /**
     * Get degree (number of neighbors) of a node
     */
    virtual size_t degree(NodeID v) const;
    
    /**
     * Get a single neighbor of a node (for degree-1 nodes)
     */
    virtual Neighbor single_neighbor(NodeID v) const;
    
    // ============ Node Management - IMPLEMENTED IN BASE CLASS ============
    
    /**
     * Add a single node to the subgraph
     */
    virtual void add_node(NodeID v);
    
    /**
     * Remove a set of nodes from the subgraph
     */
    virtual void remove_nodes(const std::vector<NodeID> &node_set);
    
    /**
     * Remove all nodes with degree 0 (isolated nodes)
     */
    virtual void remove_isolated();
    
    /**
     * Reset graph to initial state, keeping only active nodes
     * Must be implemented by derived class (accesses static s and t)
     */
    virtual void reset() = 0;
    
    // ============ Edge Management - ALGORITHM SPECIFIC ============
    
    /**
     * Remove an edge between two nodes (both directions)
     * Must be implemented by derived class
     */
    virtual void remove_edge(NodeID v, NodeID w) = 0;
    
    // ============ Graph Access - IMPLEMENTED IN BASE CLASS ============
    
    /**
     * Get const reference to vector of all nodes in subgraph
     */
    virtual const std::vector<NodeID>& get_nodes() const;
    
    /**
     * Get all edges in the subgraph as a vector of Edge structures
     */
    virtual void get_edges(std::vector<Edge> &edges) const;
    
    // ============ Utility Methods - IMPLEMENTED IN BASE CLASS ============
    
    /**
     * Enable or disable progress tracking output
     */
    static void show_progress(bool state);
    
    // ============ Algorithm-Specific (Derived Classes) ============
    
    /**
     * Resize graph for specified number of nodes
     * Must be implemented by derived class
     */
    virtual void resize(size_t node_count) = 0;
    
    /**
     * Add an edge to the graph
     * Must be implemented by derived class (may differ in parameters)
     */
    virtual void add_edge(NodeID v, NodeID w, distance_t distance, bool add_reverse) = 0;
};

} // namespace road_network
