# TODO Summary - Fix Establishment Routing Issues

## 🎯 Problem Statement

When users select locations outside the road network (e.g., establishments like "BAZZITO Wine & Liquor"), the routing system shows **"jumping back" behavior** because:

1. ❌ Locations are snapped to nearest **node** instead of nearest **road segment**
2. ❌ No visual feedback showing where the route actually connects to the road
3. ❌ Cannot search for establishments by name
4. ❌ Route metrics don't account for walking distance from establishment to road

**Reference Images:**
- Image 1: Google Maps properly handles establishment selection (correct behavior)
- Image 2: Current implementation shows jumping back (incorrect behavior)

---

## ✅ Solution Overview

### Three Main Fixes:

1. **Snap to Road Segment** (not just nearest node)
   - Project clicked point perpendicular onto nearest road segment
   - Calculate exact entry point on the road

2. **Visual Feedback System**
   - Show dual markers: clicked location + snapped road point
   - Draw connector line showing walking distance
   - Display road name and snap distance in UI

3. **Establishment Search & Metadata**
   - Search for establishments using Nominatim API
   - Show autocomplete suggestions
   - Store establishment info in route data

---

## 📋 TODO List (12 Tasks)

### 🔴 CRITICAL - Core Functionality (Must Do First)

**TODO #1: Implement snap-to-road for start/destination points**
- File: `Main/coordinate_mapper.py`
- Add `snap_to_nearest_road()` function
- Find closest road segment and project point onto it
- Validate snap distance is reasonable (<500m)

**TODO #3: Create endpoint for finding nearest road segment**
- File: `Main/flask_server.py`
- Add `/find_nearest_road_segment` endpoint
- Return: edge info, projection point, distance, road name
- Replace `/find_nearest_node` usage

**TODO #6: Create road segment geometry utilities**
- File: `Main/road_segment_utils.py` (NEW FILE)
- `project_point_to_segment()` - geometric projection
- `find_nearest_edge()` - search all edges
- `validate_road_connection()` - safety checks

---

### 🔴 CRITICAL - Visual Feedback (Must Do Second)

**TODO #2: Add visual feedback for snapped locations**
- File: `Main/templates/index.html`
- Show two markers: exact click + snapped road point
- Draw dashed connector line between them
- Update location text: "Establishment → Road Name (Xm)"

**TODO #7: Update route visualization to show connector lines**
- File: `Main/static/js/functions.js`
- Detect off-road start/end points
- Add connector polylines (gray, dashed, 2px)
- Style main route differently (colored, solid, 5px)
- Add tooltips with walking distance

---

### 🔴 CRITICAL - Route Computation (Must Do Third)

**TODO #4: Enhance route computation for off-road points**
- Files: `Main/gps_hc2l_router.py`, `Main/dhl_router.py`
- Accept snap point data
- Add connector segments to route
- Draw straight lines for walking portions

**TODO #11: Update distance/time calculations**
- Files: `Main/gps_hc2l_router.py`, `Main/dhl_router.py`
- Separate walking vs driving distance
- Assume 5 km/h walking speed
- Show: "Walking: 130m (2 min) + Driving: 2.45km (10 min)"

---

### 🟡 IMPORTANT - Enhanced Features (Do After Core)

**TODO #5: Implement establishment geocoding and search**
- Files: `Main/templates/index.html`, `Main/flask_server.py`
- Add search input with autocomplete
- Integrate Nominatim API
- Show establishment on map when selected

**TODO #9: Store and display establishment metadata**
- Files: `Main/gps_hc2l_router.py`, `Main/dhl_router.py`
- Add establishment info to route data
- Display: "From: [Establishment] via [Road]"
- Show in turn-by-turn directions

**TODO #10: Add establishment database/cache**
- File: `Main/data/establishment_cache.json` (NEW FILE)
- Pre-load POIs from OSM
- Add quick-select buttons for common places
- Cache snap-to-road results for performance

---

### 🟢 OPTIONAL - Safety & Polish (Do Last)

**TODO #8: Add validation and error handling**
- File: `Main/flask_server.py`
- Check if location >1km from any road
- Warn about inaccessible areas
- Suggest alternative accessible points

**TODO #12: Implement accessibility checks**
- File: `Main/coordinate_mapper.py`
- Check pedestrian access from establishment to road
- Detect obstacles (buildings, water)
- Use OSM building/landuse data

---

## 📅 Implementation Phases

### Phase 1: Core Snap-to-Road (4-6 hours) ⭐ START HERE
```
Step 1: Create road_segment_utils.py
Step 2: Update coordinate_mapper.py with snap logic
Step 3: Add Flask endpoint /find_nearest_road_segment
Step 4: Test with curl - verify projection works
```

### Phase 2: Visual Feedback (3-4 hours)
```
Step 1: Update index.html map click handler
Step 2: Show dual markers + connector line
Step 3: Update functions.js polyline rendering
Step 4: Test on frontend - verify visual clarity
```

### Phase 3: Route Enhancement (3-4 hours)
```
Step 1: Update gps_hc2l_router.py
Step 2: Update dhl_router.py
Step 3: Add connector segments to routes
Step 4: Calculate walking vs driving metrics
Step 5: Test full route establishment-to-establishment
```

### Phase 4: Search & Metadata (4-5 hours)
```
Step 1: Add search UI to index.html
Step 2: Integrate Nominatim API
Step 3: Add autocomplete functionality
Step 4: Store establishment metadata
```

### Phase 5: Validation & Cache (2-3 hours)
```
Step 1: Add location validation
Step 2: Create establishment cache
Step 3: Add accessibility checks
```

**Total Estimated Time: 16-22 hours**

---

## 🧪 Testing Checklist

After implementing each phase, test:

### ✅ Phase 1 Tests
- [ ] Endpoint returns correct projection point
- [ ] Snap distance calculated correctly
- [ ] Works at road intersections
- [ ] Handles edge cases (far from road, on node, etc.)

### ✅ Phase 2 Tests
- [ ] Both markers appear on map
- [ ] Connector line is dashed and gray
- [ ] UI text shows establishment and road name
- [ ] Distance displayed correctly

### ✅ Phase 3 Tests
- [ ] Route includes walking segments
- [ ] Route includes driving segment
- [ ] No jumping back behavior
- [ ] Metrics show walking + driving separately

### ✅ Phase 4 Tests
- [ ] Search finds establishments
- [ ] Autocomplete works
- [ ] Clicking result sets location
- [ ] Metadata displayed in UI

### ✅ Phase 5 Tests
- [ ] Validation warns about far locations
- [ ] Cache improves performance
- [ ] Accessibility checks work

---

## 📁 Files to Create/Modify

### New Files to Create (2)
1. `Main/road_segment_utils.py` - Geometry utilities
2. `Main/data/establishment_cache.json` - POI cache (optional)

### Files to Modify (8)
1. `Main/coordinate_mapper.py` - Add snap-to-road logic
2. `Main/flask_server.py` - New endpoints, validation
3. `Main/gps_hc2l_router.py` - Handle off-road points
4. `Main/dhl_router.py` - Handle off-road points
5. `Main/templates/index.html` - Search UI, map handlers
6. `Main/static/js/functions.js` - Route visualization
7. `Main/static/js/event-handlers.js` - Click handling (minor)
8. `Main/static/js/variables.js` - New variables (if needed)

---

## 🔗 Documentation Files Created

1. **ESTABLISHMENT_ROUTING_FIX.md** - Full implementation plan with architecture
2. **SNAP_TO_ROAD_ALGORITHM.md** - Technical algorithm specifications
3. **IMPLEMENTATION_GUIDE.md** - Quick reference and priority order
4. **THIS FILE** - TODO summary and checklist

---

## 🚀 Getting Started

**To begin implementation right now:**

```bash
# 1. Read the documentation
open IMPLEMENTATION_GUIDE.md
open SNAP_TO_ROAD_ALGORITHM.md

# 2. Start with Phase 1
# Create the utility file
touch Main/road_segment_utils.py

# 3. Copy algorithm from SNAP_TO_ROAD_ALGORITHM.md
# Implement project_point_onto_segment() first

# 4. Then update coordinate_mapper.py
# Add snap_to_nearest_road() function

# 5. Then update flask_server.py
# Add /find_nearest_road_segment endpoint

# 6. Test the endpoint
curl -X POST http://localhost:5000/find_nearest_road_segment \
  -H "Content-Type: application/json" \
  -d '{"lat": 14.6500, "lng": 121.0450}'
```

---

## 🎯 Success Criteria

When implementation is complete, the system should:

✅ **No jumping back** - Routes follow logical paths from establishments
✅ **Clear visualization** - Users see where route connects to road  
✅ **Search capability** - Can find establishments by name
✅ **Accurate metrics** - Distance/time separated into walking + driving
✅ **Error handling** - Graceful handling of edge cases
✅ **User feedback** - Clear indication of snap distance and road

---

## 📞 Need Help?

- **Algorithm questions**: See `SNAP_TO_ROAD_ALGORITHM.md`
- **Implementation order**: See `IMPLEMENTATION_GUIDE.md`
- **Architecture overview**: See `ESTABLISHMENT_ROUTING_FIX.md`
- **API reference**: See `flask_server.py` existing endpoints

---

**Remember**: Start with Phase 1 (Core) and test thoroughly before moving forward!

Good luck! 🚀
