/**
 * Base Road Network Implementation
 * 
 * Common implementations shared between DHL and HC2L algorithms
 * This file contains implementations for all shared structures, types, and utilities
 * defined in base_road_network.h
 */

#include "base_road_network.h"
#include <algorithm>
#include <vector>
#include <unordered_set>
#include <ostream>
#include <cstdint>

namespace road_network {

// ============================================================
// PARTITION BITVECTOR UTILITIES (PBV NAMESPACE)
// ============================================================

namespace PBV
{
    uint64_t from(uint64_t bits, uint16_t length)
    {
        if (length == 0)
            return 0;
        return (bits << (64 - length) >> (58 - length)) | length;
    }

    uint64_t partition(uint64_t bv)
    {
        // cutlevel is stored in lowest 6 bits
        return bv >> 6;
    }

    uint16_t cut_level(uint64_t bv)
    {
        // cutlevel is stored in lowest 6 bits
        return bv & 63ul;
    }

    uint16_t lca_level(uint64_t bv1, uint64_t bv2)
    {
        // find lowest level at which partitions differ
        uint16_t lca_level_val = std::min(cut_level(bv1), cut_level(bv2));
        uint64_t p1 = partition(bv1), p2 = partition(bv2);
        if (p1 != p2)
        {
            uint16_t diff_level = __builtin_ctzll(p1 ^ p2); // count trailing zeros
            if (diff_level < lca_level_val)
                lca_level_val = diff_level;
        }
        return lca_level_val;
    }

    uint64_t lca(uint64_t bv1, uint64_t bv2)
    {
        uint64_t cut_level_val = lca_level(bv1, bv2);
        // shifting by 64 does not work
        if (cut_level_val == 0)
            return 0;
        return (bv1 >> 6) << (64 - cut_level_val) >> (58 - cut_level_val) | cut_level_val;
    }

    bool is_ancestor(uint64_t bv_ancestor, uint64_t bv_descendant)
    {
        uint16_t cla = cut_level(bv_ancestor), cld = cut_level(bv_descendant);
        // shifting by 64 does not work, so need to check for cla == 0
        return cla == 0 || (cla <= cld && (bv_ancestor ^ bv_descendant) >> 6 << (64 - cla) == 0);
    }
}

// ============================================================
// NEIGHBOR STRUCTURE
// ============================================================

Neighbor::Neighbor(NodeID node, distance_t distance) : node(node), distance(distance)
{
}

bool Neighbor::operator<(const Neighbor &other) const
{
    return node < other.node;
}

std::ostream& operator<<(std::ostream& os, const Neighbor &n)
{
    if (n.distance == 1)
        return os << n.node;
    else
        return os << n.node << "@" << n.distance;
}

// ============================================================
// NODE STRUCTURE
// ============================================================

Node::Node(SubgraphID subgraph_id) : subgraph_id(subgraph_id)
{
    distance = outcopy_distance = 0;
    inflow = outflow = 0;  // NO_NODE = 0
    landmark_level = 0;
}

std::ostream& operator<<(std::ostream& os, const Node &n)
{
    return os << "N(" << n.subgraph_id << ")";
}

// ============================================================
// MULTI-THREADED NODE DATA
// ============================================================

Node& MultiThreadNodeData::operator[](size_type pos)
{
    // This assumes Graph has static members s and t
    // For now, use fixed values 0 and 1 as placeholders
    // In actual usage, this will be properly initialized
    if (pos == 0)  // Graph::s
        return s_data;
    if (pos == 1)  // Graph::t
        return t_data;
    return std::vector<Node>::operator[](pos);
}

const Node& MultiThreadNodeData::operator[](size_type pos) const
{
    if (pos == 0)  // Graph::s
        return s_data;
    if (pos == 1)  // Graph::t
        return t_data;
    return std::vector<Node>::operator[](pos);
}

void MultiThreadNodeData::normalize()
{
    // Copy thread-local data back to vector if needed
    if (size() > 0) {
        std::vector<Node>::operator[](0) = s_data;
        if (size() > 1) {
            std::vector<Node>::operator[](1) = t_data;
        }
    }
}

// ============================================================
// PARTITION STRUCTURE
// ============================================================

double Partition::rating() const
{
    size_t l = left.size(), r = right.size(), c = cut.size();
    return std::min(l, r) / (c * c + 1.0);
}

std::ostream& operator<<(std::ostream& os, const Partition &p)
{
    return os << "P(" << p.left.size() << "|" << p.cut.size() << "|" << p.right.size() << ")";
}

std::ostream& operator<<(std::ostream& os, const Partition *p)
{
    if (p == nullptr)
        return os << "nullptr";
    return os << (*p);
}

// ============================================================
// EDGE STRUCTURE
// ============================================================

Edge::Edge(NodeID a, NodeID b, distance_t d) : a(a), b(b), d(d)
{
}

bool Edge::operator<(Edge other) const
{
    return a < other.a
        || (a == other.a && b < other.b)
        || (a == other.a && b == other.b && d < other.d);
}

// ============================================================
// DIFFDATA STRUCTURE
// ============================================================

DiffData::DiffData(NodeID node, distance_t dist_a, distance_t dist_b)
    : node(node), dist_a(dist_a), dist_b(dist_b)
{
}

int32_t DiffData::diff() const
{
    return static_cast<int32_t>(dist_a) - static_cast<int32_t>(dist_b);
}

distance_t DiffData::min() const
{
    return std::min(dist_a, dist_b);
}

bool DiffData::cmp_diff(DiffData x, DiffData y)
{
    return x.diff() < y.diff();
}

std::ostream& operator<<(std::ostream& os, const DiffData &dd)
{
    return os << "D(" << dd.node << "@" << dd.dist_a << "-" << dd.dist_b << "=" << dd.diff() << ")";
}

// ============================================================
// BASEGRAPH IMPLEMENTATIONS (Common to all algorithms)
// ============================================================

/**
 * Check if a node belongs to this subgraph
 * A node is considered part of the subgraph if its subgraph_id matches
 */
bool BaseGraph::contains(NodeID node) const
{
    return get_node_data()[node].subgraph_id == subgraph_id;
}

/**
 * Get the number of nodes in this subgraph
 */
size_t BaseGraph::node_count() const
{
    return nodes.size();
}

/**
 * Get the total number of edges in this subgraph
 * Each edge is counted once (edges are undirected)
 */
size_t BaseGraph::edge_count() const
{
    size_t ecount = 0;
    for (NodeID node : nodes)
        for (const Neighbor &n : get_node_data()[node].neighbors)
            if (contains(n.node))
                ecount++;
    return ecount / 2;
}

/**
 * Get degree (number of neighbors) of a node
 * Only counts neighbors that are in the same subgraph
 */
size_t BaseGraph::degree(NodeID v) const
{
    assert(contains(v));
    size_t deg = 0;
    for (const Neighbor &n : get_node_data()[v].neighbors)
        if (contains(n.node))
            deg++;
    return deg;
}

/**
 * Get a single neighbor of a node
 * Returns NO_NODE if degree != 1, or if node has 0 or >1 neighbors
 */
Neighbor BaseGraph::single_neighbor(NodeID v) const
{
    assert(contains(v));
    Neighbor neighbor(NO_NODE, 0);
    for (const Neighbor &n : get_node_data()[v].neighbors)
        if (contains(n.node))
        {
            if (neighbor.node == NO_NODE)
                neighbor = n;
            else
                return Neighbor(NO_NODE, 0);  // More than one neighbor
        }
    return neighbor;
}

/**
 * Add a single node to the subgraph
 */
void BaseGraph::add_node(NodeID v)
{
    assert(v < get_node_data().size());
    nodes.push_back(v);
    get_node_data()[v].subgraph_id = subgraph_id;
}

/**
 * Remove a set of nodes from the subgraph
 */
void BaseGraph::remove_nodes(const std::vector<NodeID> &node_set)
{
    // Remove nodes from the nodes vector
    std::erase_if(nodes, [&node_set](NodeID node) {
        return std::find(node_set.begin(), node_set.end(), node) != node_set.end();
    });
    for (NodeID node : node_set)
        get_node_data()[node].subgraph_id = NO_NODE;
}

/**
 * Remove all isolated nodes (degree 0) from the subgraph
 */
void BaseGraph::remove_isolated()
{
    std::unordered_set<NodeID> isolated;
    for (NodeID node : nodes)
        if (degree(node) == 0)
        {
            isolated.insert(node);
            get_node_data()[node].subgraph_id = NO_SUBGRAPH;
        }
    std::erase_if(nodes, [&isolated](NodeID node) { return isolated.contains(node); });
}

/**
 * Get const reference to the vector of all nodes in this subgraph
 */
const std::vector<NodeID>& BaseGraph::get_nodes() const
{
    return nodes;
}

/**
 * Get all edges in the subgraph as a vector of Edge structures
 * Each edge is represented once (for undirected graphs)
 */
void BaseGraph::get_edges(std::vector<Edge> &edges) const
{
    edges.clear();
    for (NodeID a : nodes)
        for (const Neighbor &n : get_node_data()[a].neighbors)
            if (n.node > a && contains(n.node))
                edges.push_back(Edge(a, n.node, n.distance));
}

// ============================================================
// STATIC UTILITY METHODS (Common to all algorithms)
// ============================================================

// Global flag for progress tracking
static bool log_progress_on = false;

/**
 * Enable/disable progress tracking output
 * This is a static method available to all Graph implementations
 */
void BaseGraph::show_progress(bool state)
{
    log_progress_on = state;
}

} // namespace road_network
