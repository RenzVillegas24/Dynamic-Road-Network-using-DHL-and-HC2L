# Testing Polyline Accuracy

## Quick Test Guide

### 1. Start the Server

```bash
cd /home/renecuten/Codes/Projects/Dynamic-Road-Network-using-DHL-and-HC2L
source .venv/bin/activate.fish  # or activate for bash
cd Main
python flask_server.py
```

**Expected Output:**
```
✅ Loaded 13620 node coordinates
✅ Loaded 33606 edges
✅ Road geometry loader initialized
✅ GPS HC2L Router initialized successfully
✅ DHL Router initialized successfully
 * Running on http://127.0.0.1:5000
```

### 2. Open the Web Interface

Navigate to: `http://localhost:5000`

### 3. Test a Route

**Example Coordinates (from your images):**

**Test Route 1:**
- Start: `14.676, 121.0437` (near Commonwealth Avenue)
- End: `14.6542, 121.079` (near UP Diliman)

**Test Route 2:**
- Start: `14.642, 121.058` (Quezon Memorial Circle area)
- End: `14.6455, 121.0572` (nearby destination)

### 4. What to Look For

#### ✅ **Good Signs (Fixed Issues)**

1. **Route Follows Roads**: The polyline should follow visible streets on the map
2. **No Straight Line Jumps**: Route shouldn't cut across areas where there are no roads
3. **Smooth Transitions**: Turns should follow intersections, not cut corners
4. **Consistent Direction**: Route shouldn't appear to "jump back" through already-passed areas

#### ⚠️ **Console Validation**

Check the Python console output when computing a route:

```bash
📍 Getting road network coordinates for 25 nodes
📍 Route has 25 points following road network
✅ Path is valid
📊 Path summary: 1234.5m over 24 segments
✅ Enhanced route with 45 GPS coordinates (from 25 road points)
```

**What Each Line Means:**

- `Getting road network coordinates` - Loading actual edge data
- `Route has X points following road network` - Using real road connections (not interpolated)
- `✅ Path is valid` - All edges in path exist in the road network
- `📊 Path summary` - Total distance calculated from actual edges
- `Enhanced route with X coordinates` - Final polyline with smart interpolation

### 5. Comparing Algorithms

**Test Both Algorithms:**

1. Click "D-HC2L Route" button
2. Click "DHL Route" button  
3. Click "Compare Algorithms" button

**Both should:**
- Follow the same road network
- Show accurate paths on the map
- Not have straight-line artifacts

### 6. Testing Edge Cases

#### Test 1: Very Short Route (adjacent nodes)
- Should show minimal or no interpolation
- Should use direct edge connection

#### Test 2: Long Route (across city)
- Should follow major roads
- May have more interpolation on long highway segments
- Should still follow road topology

#### Test 3: Route with Disruptions
- Toggle "Use Traffic Disruptions"
- Route might change to avoid blocked roads
- New route should also follow road network accurately

## Debug Mode

### Enable Detailed Logging

In `flask_server.py`, the routers already have extensive logging. Watch the console for:

```python
# HC2L Router Output
📍 Getting road network coordinates for X nodes
⚠️  Warning: Node 12345 not found in coordinates  # Should NOT see this
⚠️  Warning: No edge from 123 to 456  # Should NOT see this
✅ Enhanced route with X GPS coordinates

# DHL Router Output  
📍 DHL route has X points following road network
⚠️  Warning: DHL path validation: Missing edges: [...]  # Should NOT see this
📊 DHL path summary: XXX.Xm over X segments
```

### Validation Errors

If you see validation warnings:

```
⚠️  Warning: Path validation: Missing edges: [(1234, 5678), ...]
```

**This means:**
- The C++ Dijkstra found a path using edges not in your edges CSV
- Possible data inconsistency between graph file and edges CSV
- The path exists but edge data is missing

**To fix:** Re-generate the graph files with the same edges CSV

## Performance Metrics

### Expected Performance

**Route Computation:**
- Query time: < 10ms (typical)
- Path enhancement: < 50ms
- Total response time: < 100ms

**Polyline Points:**
- Short route (< 1km): 10-30 points
- Medium route (1-5km): 30-100 points  
- Long route (> 5km): 100-500 points

### Memory Usage

The road geometry loader caches all edges:

```
✅ Loaded 13620 node coordinates (~400 KB)
✅ Loaded 33606 edges (~2-3 MB)
```

This is minimal and loaded once at startup.

## Common Issues and Solutions

### Issue 1: Routes Still Look Straight

**Symptoms:**
- Polylines appear as straight lines between nodes
- Routes cut across areas without roads

**Solution:**
- Check console for "Road geometry loader initialized"
- Verify `road_geometry_loader.py` was imported
- Restart Flask server

### Issue 2: "Missing edges" Warnings

**Symptoms:**
```
⚠️  Warning: No edge from 123 to 456
⚠️  Warning: DHL path validation: Missing edges: [...]
```

**Solution:**
- Your graph file and edges CSV may be out of sync
- Rebuild indexes: `./build_indexes.sh`
- Check that path is using correct edges CSV

### Issue 3: Routes Jump Around

**Symptoms:**
- Route appears to backtrack
- Path goes in circles
- Route doesn't reach destination

**Solution:**
- This might be the actual shortest path!
- Check if there are one-way streets
- Verify disruptions aren't blocking direct paths
- Use "Compare Algorithms" to see if both give same result

### Issue 4: Over-smoothed Routes

**Symptoms:**
- Routes look too smooth, cutting corners
- Path doesn't follow roads at intersections

**Solution:**
- Check `max_distance` parameter in `enhance_route_geometry()`
- Should be 50.0 or higher (meters)
- Lower values = more interpolation = smoother but less accurate

## Verification Checklist

- [ ] Server starts without errors
- [ ] Road geometry loader initializes
- [ ] Can compute D-HC2L routes
- [ ] Can compute DHL routes
- [ ] Routes follow visible streets
- [ ] No "missing edges" warnings
- [ ] Path validation shows "✅ Path is valid"
- [ ] Routes update when using disruptions
- [ ] Both algorithms show similar paths (for same conditions)

## Success Criteria

Your polylines are working correctly if:

1. ✅ Routes visibly follow the street network on the map
2. ✅ Console shows path validation passing
3. ✅ No missing edge warnings
4. ✅ Routes make logical sense (don't backtrack unnecessarily)
5. ✅ Smooth transitions at intersections
6. ✅ Both HC2L and DHL show comparable quality polylines

## Next Steps

If everything is working:

1. Test with various origin-destination pairs
2. Compare with/without disruptions
3. Test algorithm comparison feature
4. Verify turn-by-turn directions match the visual route
5. Check route distance calculations are accurate

## Contact/Support

If issues persist:
- Check `POLYLINE_FIX_SUMMARY.md` for implementation details
- Review server console logs
- Verify all files were updated correctly
- Check that graph files match the current edges CSV
