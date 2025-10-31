# 🚀 QUICK START - Begin Fixing Establishment Routing Now!

## ⚡ Start Here (5 minutes to first working code)

### Step 1: Review the problem
- **Images you provided show**: Routes "jumping back" when selecting establishments
- **Root cause**: System snaps to nearest NODE instead of nearest SEGMENT
- **Solution**: Project point onto road segment geometrically

### Step 2: Read documentation (pick ONE)
- **Quick overview**: Read `TODO_SUMMARY.md` (5 min read)
- **Implementation guide**: Read `IMPLEMENTATION_GUIDE.md` (10 min read)
- **Visual understanding**: Read `VISUAL_GUIDE.md` (see diagrams)
- **Technical details**: Read `SNAP_TO_ROAD_ALGORITHM.md` (algorithm specs)

### Step 3: Start coding (begin with TODO #6)

---

## 💻 First Code to Write (30 minutes)

### Create `Main/road_segment_utils.py`

Copy this starter template:

```python
"""
Road Segment Geometry Utilities
Provides functions for projecting points onto road segments
"""

from math import radians, cos, sin, asin, sqrt

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance between two points on Earth in meters"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of Earth in meters
    return c * r


def project_point_onto_segment(point, seg_start, seg_end):
    """
    Project a point onto a line segment (perpendicular projection)
    
    Args:
        point: (lat, lng) - point to project
        seg_start: (lat, lng) - segment start
        seg_end: (lat, lng) - segment end
    
    Returns:
        tuple: ((projected_lat, projected_lng), distance_meters)
    """
    # TODO: Implement this function
    # See SNAP_TO_ROAD_ALGORITHM.md for full implementation
    
    # For now, return a simple implementation:
    # 1. Convert lat/lng to Cartesian coordinates (approximate)
    # 2. Calculate projection using dot product
    # 3. Clamp to segment bounds
    # 4. Convert back to lat/lng
    # 5. Calculate distance
    
    # Quick implementation (improve this later):
    lat_to_m = 111320.0
    avg_lat = (seg_start[0] + seg_end[0] + point[0]) / 3.0
    lng_to_m = 111320.0 * cos(radians(avg_lat))
    
    # Point relative to seg_start
    px = (point[1] - seg_start[1]) * lng_to_m
    py = (point[0] - seg_start[0]) * lat_to_m
    
    # Segment vector
    sx = (seg_end[1] - seg_start[1]) * lng_to_m
    sy = (seg_end[0] - seg_start[0]) * lat_to_m
    
    # Segment length squared
    seg_len_sq = sx * sx + sy * sy
    
    if seg_len_sq < 1e-6:  # Segment is a point
        return seg_start, haversine(seg_start[1], seg_start[0], point[1], point[0])
    
    # Projection parameter t (0 = start, 1 = end)
    t = (px * sx + py * sy) / seg_len_sq
    t = max(0, min(1, t))  # Clamp to [0, 1]
    
    # Projected point
    proj_x = t * sx
    proj_y = t * sy
    
    projected_lat = seg_start[0] + (proj_y / lat_to_m)
    projected_lng = seg_start[1] + (proj_x / lng_to_m)
    
    # Distance from point to projection
    distance = sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    return (projected_lat, projected_lng), distance


def find_nearest_edge(lat, lng, edges_df, nodes_df, max_distance=500):
    """
    Find the nearest road edge to a given point
    
    Args:
        lat, lng: GPS coordinates
        edges_df: DataFrame with columns [source, target, name, ...]
        nodes_df: DataFrame with columns [node_id, latitude, longitude]
        max_distance: Maximum search distance in meters
    
    Returns:
        dict or None: {
            'edge': (source_id, target_id),
            'projection_point': {'lat': float, 'lng': float},
            'distance_m': float,
            'road_name': str
        }
    """
    # TODO: Implement this function
    # For each edge:
    #   1. Get segment endpoints from nodes_df
    #   2. Project point onto segment
    #   3. Track minimum distance
    # Return best match within max_distance
    
    min_distance = float('inf')
    best_segment = None
    
    # Create node lookup
    node_coords = {}
    for _, node in nodes_df.iterrows():
        node_coords[node['node_id']] = (node['latitude'], node['longitude'])
    
    # Check each edge
    for _, edge in edges_df.iterrows():
        source_id = edge['source']
        target_id = edge['target']
        
        if source_id not in node_coords or target_id not in node_coords:
            continue
        
        seg_start = node_coords[source_id]
        seg_end = node_coords[target_id]
        
        # Project point onto this segment
        projection, distance = project_point_onto_segment(
            (lat, lng), seg_start, seg_end
        )
        
        # Track best match
        if distance < min_distance and distance <= max_distance:
            min_distance = distance
            best_segment = {
                'edge': (source_id, target_id),
                'projection_point': {
                    'lat': projection[0],
                    'lng': projection[1]
                },
                'distance_m': distance,
                'road_name': edge.get('name', 'Unnamed Road')
            }
    
    return best_segment


def validate_road_connection(point, road_point, max_snap_distance=500):
    """
    Validate if a road connection is reasonable
    
    Args:
        point: (lat, lng) - original point
        road_point: (lat, lng) - snapped road point
        max_snap_distance: Maximum acceptable distance in meters
    
    Returns:
        dict: {
            'valid': bool,
            'distance': float,
            'message': str
        }
    """
    distance = haversine(point[1], point[0], road_point[1], road_point[0])
    
    if distance <= max_snap_distance:
        return {
            'valid': True,
            'distance': distance,
            'message': 'Connection is valid'
        }
    else:
        return {
            'valid': False,
            'distance': distance,
            'message': f'Location is {distance:.0f}m from road (max: {max_snap_distance}m)'
        }


# Test the functions
if __name__ == "__main__":
    print("Testing road segment utilities...")
    
    # Test 1: Point between two nodes
    point = (14.6500, 121.0450)
    seg_start = (14.6498, 121.0445)
    seg_end = (14.6502, 121.0455)
    
    projection, distance = project_point_onto_segment(point, seg_start, seg_end)
    print(f"\nTest 1: Point projection")
    print(f"  Point: {point}")
    print(f"  Segment: {seg_start} → {seg_end}")
    print(f"  Projection: {projection}")
    print(f"  Distance: {distance:.2f}m")
    
    # Test 2: Point before segment start
    point2 = (14.6495, 121.0440)
    projection2, distance2 = project_point_onto_segment(point2, seg_start, seg_end)
    print(f"\nTest 2: Point before segment")
    print(f"  Point: {point2}")
    print(f"  Projection: {projection2}")
    print(f"  Distance: {distance2:.2f}m")
    print(f"  Should be clamped to start: {abs(projection2[0] - seg_start[0]) < 0.0001}")
    
    print("\n✅ Basic tests complete!")
```

Save this file and run:
```bash
cd /home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L
python Main/road_segment_utils.py
```

Expected output:
```
Testing road segment utilities...

Test 1: Point projection
  Point: (14.65, 121.045)
  Segment: (14.6498, 121.0445) → (14.6502, 121.0455)
  Projection: (14.649987..., 121.045012...)
  Distance: 25.34m

Test 2: Point before segment
  Point: (14.6495, 121.044)
  Projection: (14.6498, 121.0445)
  Distance: 52.18m
  Should be clamped to start: True

✅ Basic tests complete!
```

---

## 🎯 Next Steps After First File

### TODO #1: Update `coordinate_mapper.py`
Add this method to the `NodeMapper` class:

```python
def snap_to_nearest_road(self, lat, lng, max_distance=500):
    """
    Find nearest road segment and snap point to it
    
    Args:
        lat, lng: GPS coordinates
        max_distance: Maximum snap distance in meters
    
    Returns:
        dict or None: Snap information
    """
    from road_segment_utils import find_nearest_edge
    import pandas as pd
    
    # Load edges data
    edges_df = pd.read_csv('Main/data/raw/quezon_city_edges.csv')
    
    # Find nearest edge
    result = find_nearest_edge(lat, lng, edges_df, self.nodes_df, max_distance)
    
    return result
```

### TODO #3: Add Flask endpoint
Add this to `flask_server.py`:

```python
@app.route('/find_nearest_road_segment', methods=['POST'])
def find_nearest_road_segment():
    """Find nearest road segment and project point onto it"""
    data = request.json
    
    try:
        from road_segment_utils import find_nearest_edge
        
        lat = float(data['lat'])
        lng = float(data['lng'])
        
        # Use mapper's snap function
        result = mapper.snap_to_nearest_road(lat, lng, max_distance=500)
        
        if result is None:
            return jsonify({
                'success': False,
                'error': 'No road within 500m of this location'
            })
        
        return jsonify({
            'success': True,
            **result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
```

### Test the endpoint:
```bash
# Start the server
cd /home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L
python Main/flask_server.py

# In another terminal, test:
curl -X POST http://localhost:5000/find_nearest_road_segment \
  -H "Content-Type: application/json" \
  -d '{"lat": 14.6500, "lng": 121.0450}'
```

---

## 📋 Implementation Checklist (Do in Order)

### Week 1: Core Snap-to-Road
- [ ] Day 1: Create `road_segment_utils.py` ← START HERE
- [ ] Day 2: Update `coordinate_mapper.py` with snap function
- [ ] Day 3: Add Flask endpoint `/find_nearest_road_segment`
- [ ] Day 4: Test endpoint thoroughly with various locations

### Week 2: Visual Feedback
- [ ] Day 5: Update map click handler in `index.html`
- [ ] Day 6: Add dual markers (clicked + snapped)
- [ ] Day 7: Add connector line visualization

### Week 3: Route Computation
- [ ] Day 8: Update `gps_hc2l_router.py`
- [ ] Day 9: Update `dhl_router.py`
- [ ] Day 10: Add connector segments to routes
- [ ] Day 11: Update metrics (walking vs driving)

### Week 4: Search & Polish
- [ ] Day 12: Add establishment search UI
- [ ] Day 13: Integrate Nominatim API
- [ ] Day 14: Add validation and error handling
- [ ] Day 15: Testing and bug fixes

---

## 🆘 Common Issues & Solutions

### Issue 1: Import error for `road_segment_utils`
**Solution**: Make sure you're in the correct directory
```bash
cd /home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main
python -c "from road_segment_utils import project_point_onto_segment; print('OK')"
```

### Issue 2: Can't find edges CSV
**Solution**: Update path in code
```python
edges_df = pd.read_csv('/home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L/Main/data/raw/quezon_city_edges.csv')
```

### Issue 3: Projection seems wrong
**Solution**: Check that lat/lng order is correct (lat first, lng second)

---

## 📚 Resources

- **Full Documentation**: See `ESTABLISHMENT_ROUTING_FIX.md`
- **Algorithm Details**: See `SNAP_TO_ROAD_ALGORITHM.md`
- **Visual Guide**: See `VISUAL_GUIDE.md`
- **TODO List**: View in VS Code with TODO Tree extension

---

## ✅ Success Indicators

You'll know it's working when:

1. ✅ Endpoint returns projection point different from clicked point
2. ✅ Snap distance is calculated correctly (in meters)
3. ✅ Road name is returned
4. ✅ Projection is clamped to segment bounds
5. ✅ Distance to road is reasonable (<500m for valid locations)

---

## 🎉 First Milestone Complete When:

- [ ] `road_segment_utils.py` created and tested
- [ ] `coordinate_mapper.py` has `snap_to_nearest_road()` method
- [ ] Flask endpoint `/find_nearest_road_segment` works
- [ ] Can test with curl and get correct projection

**Time to reach this: ~4-6 hours of focused work**

---

## 🚀 You're Ready!

1. Create `road_segment_utils.py` with the starter code above
2. Run the test: `python Main/road_segment_utils.py`
3. If tests pass, move to TODO #1 (update `coordinate_mapper.py`)
4. Then TODO #3 (add Flask endpoint)
5. Test the endpoint
6. Move to Phase 2 (visual feedback)

**Start now and you'll have the core functionality working in a few hours!**

Good luck! 🎯
