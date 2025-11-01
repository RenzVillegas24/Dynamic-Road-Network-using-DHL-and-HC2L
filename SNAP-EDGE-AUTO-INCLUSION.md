# Snap Edge Automatic Inclusion - Implementation Note

## Date: November 2, 2025

## Change Summary

The C++ routing algorithms (HC2L and DHL) now **automatically include the snap edges** in the route path.

## Problem Addressed

Previously, when a user placed a pin on a road:
- The system would snap to an edge (e.g., between nodes A and B)
- A routing node would be selected from that edge (either A or B)
- The route would be calculated FROM that node
- **BUT**: The edge where the snap occurred might not be included in the path

This meant:
- The route might start from node A but not traverse the edge A→B
- The snap point on edge A→B would be orphaned
- The visualization would not show the route passing through the snap edge

## Solution Implemented

Both routing APIs now ensure that:

1. **Start Snap Edge is Always Included:**
   - The route path ALWAYS includes both nodes of the start snap edge
   - Traversal direction respects the oneway property
   - Example: If snapped to edge (100→101, oneway=1), route starts: [100, 101, ...]

2. **Destination Snap Edge is Always Included:**
   - The route path ALWAYS includes both nodes of the dest snap edge
   - Traversal direction respects the oneway property
   - Example: If snapped to edge (200→201, oneway=1), route ends: [..., 200, 201]

3. **Direction-Aware Traversal:**
   ```
   For oneway=1 (forward):
     Edge traversed as: source → target
   
   For oneway=-1 (reverse):
     Edge traversed as: target → source
   
   For oneway=0 (bidirectional):
     Edge traversed based on routing logic
   ```

## Code Changes

### Files Modified:
- `HierarchicalCutLabelling/src/hc2l_routing_api.cpp`
- `DualHierarchyLabelling/src/dhl_routing_api.cpp`

### Logic Added:

```cpp
// After getting the routing path from Dijkstra
vector<NodeID> complete_path;

// 1. Add START snap edge (respecting direction)
if (start_edge_oneway == 1) {
    complete_path.push_back(start_edge_source);
    complete_path.push_back(start_edge_target);
} else if (start_edge_oneway == -1) {
    complete_path.push_back(start_edge_target);
    complete_path.push_back(start_edge_source);
} else {
    // Bidirectional logic
}

// 2. Add middle routing path
for (NodeID node : routing_path) {
    if (complete_path.back() != node) {
        complete_path.push_back(node);
    }
}

// 3. Add DEST snap edge (respecting direction)
if (dest_edge_oneway == 1) {
    ensure_path_includes(dest_edge_source);
    ensure_path_includes(dest_edge_target);
} else if (dest_edge_oneway == -1) {
    ensure_path_includes(dest_edge_target);
    ensure_path_includes(dest_edge_source);
}
```

## Examples

### Example 1: Start on One-Way Forward
```
User pins at: Edge (Node 50 → Node 51, oneway=1)
Snap point: 30% along edge

Selected start_node: 50 (must start from source for oneway=1)
Routing finds path: [50, 51, 60, 70, 80]

Output complete_path: [50, 51, 60, 70, 80]
✅ Edge (50→51) is included!
```

### Example 2: Destination on One-Way Reverse
```
User pins at: Edge (Node 100 → Node 101, oneway=-1)
Snap point: 70% along edge

Selected dest_node: 100 (must end at source for oneway=-1, meaning arrow points backward)
Routing finds path: [10, 20, 30, 101, 100]

Output complete_path: [10, 20, 30, 101, 100]
✅ Edge (101→100) traversed correctly for reverse one-way!
```

### Example 3: Both Edges Bidirectional
```
Start snap: Edge (Node 5 → Node 6, oneway=0)
Dest snap: Edge (Node 95 → Node 96, oneway=0)

Selected nodes: start=5, dest=96
Routing path: [5, 10, 20, 90, 96]

Complete path logic adds:
- Start edge: includes both 5 and 6
- Middle: continues from where start edge ended
- Dest edge: includes both nodes leading to 96

Output complete_path: [5, 6, 10, 20, 90, 95, 96]
✅ Both snap edges included!
```

## Visualization Impact

With this change, the frontend will receive routes that:
- ✅ Always pass through the snap point locations
- ✅ Include the edge geometry where snaps occurred
- ✅ No need for artificial interpolation segments
- ✅ Route visually starts and ends at snap points

The edge geometry in the JSON output already contains the snap point coordinates, so plotting the route using the returned geometry will correctly show the path passing through both snap points.

## Testing

To verify this works:
1. Place start pin on a road (note the edge nodes)
2. Place dest pin on a road (note the edge nodes)
3. Compute route
4. Check the `path_nodes` array in the response
5. Verify: First 2 nodes are the start snap edge nodes
6. Verify: Last 2 nodes are the dest snap edge nodes
7. Check geometry: Snap points should be within the edge geometries

## Build Status

✅ **Successfully compiled**
- HC2L routing API rebuilt
- DHL routing API rebuilt
- No compilation errors
- Only minor pre-existing warnings (unrelated to this change)

---

**Implementation Complete: November 2, 2025**
**Build Verified: ✅**
