# Establishment Routing Fix - Implementation Plan

## Problem Description

### Current Issue
When users click on locations that are **not directly on road nodes** (e.g., establishments, buildings, points of interest), the routing system exhibits problematic behavior:

1. **"Jumping Back" Problem**: Routes show zigzag patterns or backtracking because the clicked location is between nodes
2. **Straight Line Segments**: The system draws direct lines from the clicked point to the nearest node, which may not follow actual walkable paths
3. **No Establishment Support**: Cannot search for or select establishments as start/destination points

### Visual Evidence
- **Image 1** (Google Maps reference): Shows proper handling of establishment selection with snap-to-road
- **Image 2** (Current implementation): Shows incorrect "jumping back" behavior when clicking between nodes

### Root Cause
The current implementation in `coordinate_mapper.py` only finds the **nearest node** using haversine distance, but:
- Doesn't project the point onto the actual road segment
- Doesn't handle locations that are off the road network
- Doesn't provide visual feedback for the snap-to-road process

## Solution Architecture

### Three Main Components

#### 1. **Snap-to-Road Functionality** (TODOs 1, 3, 6)
Instead of finding just the nearest node, we need to:
- Find the nearest **road segment** (edge between two nodes)
- **Project** the clicked point onto that segment geometrically
- Calculate the exact entry point on the road network

**Example**:
```
Establishment (clicked):  📍
                          |
                    (100m perpendicular)
                          |
Road Segment: 🔵========⭕========🔵
              Node A    Entry   Node B
                        Point
```

#### 2. **Visual Feedback System** (TODOs 2, 7)
Users need to see:
- **Original marker**: Where they actually clicked (establishment location)
- **Snapped marker**: Where the route will start on the road
- **Connector line**: Dotted/dashed line showing walking distance
- **Distance label**: "100m walk to road entry"

#### 3. **Establishment Search & Selection** (TODOs 5, 9, 10)
Add ability to:
- Search for establishments by name (e.g., "BAZZITO Wine & Liquor")
- Show autocomplete suggestions from Nominatim/OSM
- Display establishment metadata (name, type, address)
- Cache frequently accessed locations

## Implementation Tasks

### Phase 1: Core Snap-to-Road (Priority: HIGH)
**Files to modify**: `coordinate_mapper.py`, `flask_server.py`

1. **TODO #1**: Implement snap-to-road algorithm
   - Create `snap_to_nearest_road(lat, lng)` function
   - Project point onto nearest road segment
   - Return: snap point coordinates, distance, road name

2. **TODO #3**: Create Flask endpoint
   - Add `/find_nearest_road_segment` endpoint
   - Return: edge info, projection point, distance, road name
   - Replace `/find_nearest_node` usage

3. **TODO #6**: Road segment utilities
   - Create `road_segment_utils.py`
   - Implement point-to-line-segment projection
   - Add edge finding and validation functions

**Expected Result**: When clicking off-road, system finds correct road entry point

### Phase 2: Visual Improvements (Priority: HIGH)
**Files to modify**: `index.html`, `functions.js`, `event-handlers.js`

4. **TODO #2**: Update map click handler
   - Show dual markers (clicked + snapped)
   - Add connector line visualization
   - Update location text with establishment info

5. **TODO #7**: Enhance route polylines
   - Add connector segments (dotted gray lines)
   - Style main route differently (solid colored lines)
   - Add distance tooltips

**Expected Result**: Users can see exactly where route connects to road

### Phase 3: Route Computation Updates (Priority: HIGH)
**Files to modify**: `gps_hc2l_router.py`, `dhl_router.py`

6. **TODO #4**: Handle off-road start/end points
   - Accept both exact GPS and snapped coordinates
   - Add connector segments to route
   - Draw straight lines for walking portions

7. **TODO #11**: Update metrics
   - Separate walking vs driving distance
   - Calculate walking time (assume 5 km/h)
   - Add total trip time = walking + driving

**Expected Result**: Routes correctly show off-road segments

### Phase 4: Establishment Features (Priority: MEDIUM)
**Files to modify**: `index.html`, `flask_server.py`

8. **TODO #5**: Implement establishment search
   - Add search input UI
   - Integrate Nominatim geocoding
   - Add autocomplete dropdown

9. **TODO #9**: Store establishment metadata
   - Enhance route data structure
   - Display "From: [Establishment] via [Road]"
   - Show in turn-by-turn directions

10. **TODO #10**: Establishment cache
    - Create `establishment_cache.json`
    - Pre-load common POIs from OSM
    - Add quick-select buttons

**Expected Result**: Users can search and select establishments

### Phase 5: Validation & Safety (Priority: MEDIUM)
**Files to modify**: `flask_server.py`, `coordinate_mapper.py`

11. **TODO #8**: Location validation
    - Check max distance from road (>1km warning)
    - Detect inaccessible areas
    - Suggest alternatives

12. **TODO #12**: Accessibility checks
    - Validate pedestrian access
    - Check for obstacles (buildings, water)
    - Use OSM landuse data

**Expected Result**: System prevents invalid location selections

## Technical Details

### Point-to-Segment Projection Algorithm
```python
def project_point_to_segment(point, seg_start, seg_end):
    """
    Project a point onto a line segment and return the closest point
    
    point: (lat, lng)
    seg_start: (lat, lng) - start of road segment
    seg_end: (lat, lng) - end of road segment
    
    Returns: (projected_lat, projected_lng, distance_m)
    """
    # Convert to Cartesian coordinates
    # Calculate projection using dot product
    # Clamp to segment endpoints
    # Return closest point on segment
```

### Connector Line Styling
```javascript
// Walking segment (establishment to road)
const connectorLine = L.polyline(path, {
    color: '#808080',        // Gray
    weight: 2,               // Thin
    dashArray: '5, 10',      // Dashed
    opacity: 0.7
});

// Main route (on road network)
const routeLine = L.polyline(path, {
    color: '#FF0000',        // Red/Blue depending on algorithm
    weight: 5,               // Thick
    opacity: 0.9             // Solid
});
```

### Route Data Structure Enhancement
```json
{
  "route": {
    "establishment_start": {
      "name": "BAZZITO Wine & Liquor",
      "type": "shop",
      "exact_coords": {"lat": 14.6500, "lng": 121.0450},
      "road_entry_point": {"lat": 14.6498, "lng": 121.0452},
      "snap_distance_m": 85,
      "road_name": "C. Benitez Street"
    },
    "establishment_end": {
      "name": "UYB Printing Press Corp.",
      "type": "office",
      "exact_coords": {"lat": 14.6350, "lng": 121.0480},
      "road_entry_point": {"lat": 14.6352, "lng": 121.0478},
      "snap_distance_m": 45,
      "road_name": "San Martin De Porres Boulevard"
    },
    "walking_distance_m": 130,
    "driving_distance_m": 2450,
    "total_distance_m": 2580,
    "walking_time_s": 156,  // 130m / 5km/h
    "driving_time_s": 420,
    "total_time_s": 576
  }
}
```

## Testing Plan

### Test Cases

1. **Test: Establishment exactly on road**
   - Click directly on a road node
   - Expected: No connector line, snap distance = 0

2. **Test: Establishment 50m from road**
   - Click on building 50m perpendicular from road
   - Expected: Connector line shown, distance label displays "50m"

3. **Test: Establishment >500m from road**
   - Click in remote area
   - Expected: Warning displayed, suggest nearest road

4. **Test: Establishment search**
   - Search "BAZZITO Wine"
   - Expected: Autocomplete shows result, clicking sets start location

5. **Test: Route with two establishments**
   - Set start: "BAZZITO Wine & Liquor"
   - Set end: "UYB Printing Press"
   - Expected: Route shows two connector segments + main route

## Files to Create/Modify

### New Files
- `road_segment_utils.py` - Geometry utilities
- `establishment_cache.json` - POI database
- `ESTABLISHMENT_ROUTING_FIX.md` - This documentation

### Modified Files
- `coordinate_mapper.py` - Add snap-to-road logic
- `flask_server.py` - New endpoints, validation
- `gps_hc2l_router.py` - Handle off-road points
- `dhl_router.py` - Handle off-road points
- `index.html` - Search UI, map handlers
- `functions.js` - Route visualization
- `event-handlers.js` - Click handling

## Success Criteria

✅ **No more "jumping back" behavior** - Routes follow logical paths
✅ **Visual clarity** - Users see exactly where route connects to road
✅ **Establishment support** - Can search and select POIs as start/end
✅ **Accurate metrics** - Distance/time includes walking portions
✅ **Validation** - System prevents invalid location selections

## Dependencies

- **Nominatim API**: For establishment geocoding
- **OSM building/landuse data**: For accessibility validation
- **Numpy**: For geometric calculations (if not already installed)

## Estimated Implementation Time

- Phase 1 (Core): 4-6 hours
- Phase 2 (Visual): 3-4 hours
- Phase 3 (Route computation): 3-4 hours
- Phase 4 (Establishments): 4-5 hours
- Phase 5 (Validation): 2-3 hours

**Total**: ~16-22 hours

## Notes

- Start with Phase 1 as it's the foundation for all other features
- Phases 2-3 should be done together for complete user experience
- Phase 4-5 can be done later as enhancements
- Test each phase thoroughly before moving to next
- Consider performance impact of snap-to-road calculations (may need caching)
