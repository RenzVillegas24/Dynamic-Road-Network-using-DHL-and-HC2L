# Snap-to-Road Algorithm - Technical Specification

## Problem Visualization

### Current Behavior (INCORRECT)
```
Establishment:  🏪 BAZZITO Wine & Liquor
                 |
                 | (Straight line - causes "jumping back")
                 ↓
Road Network:   🔵--------🔵--------🔵--------🔵
               Node A   Node B   Node C   Node D
                            ↑
                      Nearest node (B)
                      
Issue: Creates unnatural route that jumps from establishment 
       directly to Node B, then potentially back to Node A
```

### Desired Behavior (CORRECT)
```
Establishment:  🏪 BAZZITO Wine & Liquor
                 |
                 | (Perpendicular projection - walking distance)
                 ↓
                 ⭕ Entry Point (projected onto segment)
                 |
Road Network:   🔵========|========🔵--------🔵--------🔵
               Node A  Entry Pt  Node B   Node C   Node D
                      
Solution: Projects establishment onto nearest segment AB,
         creates entry point, routes from entry point
```

## Algorithm Implementation

### Step 1: Find Nearest Road Segment

```python
def find_nearest_road_segment(lat, lng, edges_df, nodes_df, max_distance=500):
    """
    Find the nearest road segment to a given point
    
    Args:
        lat, lng: GPS coordinates of clicked location
        edges_df: DataFrame with columns [source, target, ...]
        nodes_df: DataFrame with columns [node_id, latitude, longitude]
        max_distance: Maximum search distance in meters
    
    Returns:
        {
            'edge': (source_node_id, target_node_id),
            'projection_point': {'lat': float, 'lng': float},
            'distance_m': float,
            'road_name': str,
            'segment_length_m': float
        }
        or None if no segment within max_distance
    """
    
    min_distance = float('inf')
    best_segment = None
    
    # Create node lookup for faster access
    node_coords = {}
    for _, node in nodes_df.iterrows():
        node_coords[node['node_id']] = (node['latitude'], node['longitude'])
    
    # Check each edge
    for _, edge in edges_df.iterrows():
        source_id = edge['source']
        target_id = edge['target']
        
        # Get segment endpoints
        if source_id not in node_coords or target_id not in node_coords:
            continue
            
        seg_start = node_coords[source_id]  # (lat, lng)
        seg_end = node_coords[target_id]    # (lat, lng)
        
        # Project point onto segment
        projection, distance = project_point_onto_segment(
            (lat, lng), seg_start, seg_end
        )
        
        # Track minimum distance
        if distance < min_distance and distance <= max_distance:
            min_distance = distance
            best_segment = {
                'edge': (source_id, target_id),
                'projection_point': {
                    'lat': projection[0],
                    'lng': projection[1]
                },
                'distance_m': distance,
                'road_name': edge.get('name', 'Unnamed Road'),
                'segment_length_m': haversine(
                    seg_start[1], seg_start[0],
                    seg_end[1], seg_end[0]
                )
            }
    
    return best_segment
```

### Step 2: Project Point onto Segment

```python
def project_point_onto_segment(point, seg_start, seg_end):
    """
    Project a point onto a line segment (perpendicular projection)
    
    Mathematical approach:
    1. Convert lat/lng to approximate Cartesian coordinates
    2. Calculate projection using vector dot product
    3. Clamp projection to segment bounds
    4. Convert back to lat/lng
    
    Args:
        point: (lat, lng) - point to project
        seg_start: (lat, lng) - segment start
        seg_end: (lat, lng) - segment end
    
    Returns:
        (projected_point, distance_meters)
        projected_point: (lat, lng) tuple
        distance_meters: float
    """
    
    # Convert to approximate Cartesian (meters from seg_start)
    # Use simple equirectangular projection for small distances
    lat_to_m = 111320.0  # meters per degree latitude
    
    # Calculate longitude to meters (varies by latitude)
    avg_lat = (seg_start[0] + seg_end[0] + point[0]) / 3.0
    lng_to_m = 111320.0 * cos(radians(avg_lat))
    
    # Point coordinates relative to seg_start
    px = (point[1] - seg_start[1]) * lng_to_m
    py = (point[0] - seg_start[0]) * lat_to_m
    
    # Segment vector
    sx = (seg_end[1] - seg_start[1]) * lng_to_m
    sy = (seg_end[0] - seg_start[0]) * lat_to_m
    
    # Segment length squared
    seg_len_sq = sx * sx + sy * sy
    
    if seg_len_sq < 1e-6:  # Segment is essentially a point
        return seg_start, haversine(seg_start[1], seg_start[0], point[1], point[0])
    
    # Calculate projection parameter t
    # t = 0 means projection at seg_start
    # t = 1 means projection at seg_end
    # t in (0,1) means projection is on the segment
    t = max(0, min(1, (px * sx + py * sy) / seg_len_sq))
    
    # Calculate projected point in Cartesian
    proj_x = t * sx
    proj_y = t * sy
    
    # Convert back to lat/lng
    projected_lat = seg_start[0] + (proj_y / lat_to_m)
    projected_lng = seg_start[1] + (proj_x / lng_to_m)
    
    # Calculate distance from original point to projection
    distance = sqrt((px - proj_x)**2 + (py - proj_y)**2)
    
    return (projected_lat, projected_lng), distance
```

### Step 3: Create Route with Connectors

```python
def create_route_with_establishment_connectors(
    establishment_start, establishment_end,
    start_snap, end_snap,
    main_route_coords
):
    """
    Create complete route including walking segments
    
    Args:
        establishment_start: {'lat': float, 'lng': float}
        establishment_end: {'lat': float, 'lng': float}
        start_snap: {'lat': float, 'lng': float, 'distance_m': float}
        end_snap: {'lat': float, 'lng': float, 'distance_m': float}
        main_route_coords: [{'lat': float, 'lng': float}, ...]
    
    Returns:
        {
            'segments': [
                {
                    'type': 'walking',
                    'coords': [...],
                    'distance_m': float,
                    'time_s': float,
                    'description': 'Walk to road entry'
                },
                {
                    'type': 'driving',
                    'coords': [...],
                    'distance_m': float,
                    'time_s': float,
                    'description': 'Follow road network'
                },
                {
                    'type': 'walking',
                    'coords': [...],
                    'distance_m': float,
                    'time_s': float,
                    'description': 'Walk from road to destination'
                }
            ],
            'total_distance_m': float,
            'total_time_s': float
        }
    """
    
    segments = []
    
    # Walking speed: 5 km/h = 1.39 m/s
    WALKING_SPEED_MS = 1.39
    
    # Segment 1: Walk from establishment to road entry
    if start_snap['distance_m'] > 0:
        segments.append({
            'type': 'walking',
            'coords': [establishment_start, start_snap],
            'distance_m': start_snap['distance_m'],
            'time_s': start_snap['distance_m'] / WALKING_SPEED_MS,
            'description': f"Walk {start_snap['distance_m']:.0f}m to road entry",
            'style': {
                'color': '#808080',
                'weight': 2,
                'dashArray': '5, 10',
                'opacity': 0.7
            }
        })
    
    # Segment 2: Drive on road network
    driving_distance = sum_route_distance(main_route_coords)
    segments.append({
        'type': 'driving',
        'coords': main_route_coords,
        'distance_m': driving_distance,
        'time_s': estimate_driving_time(main_route_coords),
        'description': f"Drive {driving_distance:.0f}m on road network",
        'style': {
            'color': '#FF0000',
            'weight': 5,
            'opacity': 0.9
        }
    })
    
    # Segment 3: Walk from road exit to destination
    if end_snap['distance_m'] > 0:
        segments.append({
            'type': 'walking',
            'coords': [end_snap, establishment_end],
            'distance_m': end_snap['distance_m'],
            'time_s': end_snap['distance_m'] / WALKING_SPEED_MS,
            'description': f"Walk {end_snap['distance_m']:.0f}m to destination",
            'style': {
                'color': '#808080',
                'weight': 2,
                'dashArray': '5, 10',
                'opacity': 0.7
            }
        })
    
    # Calculate totals
    total_distance = sum(seg['distance_m'] for seg in segments)
    total_time = sum(seg['time_s'] for seg in segments)
    
    return {
        'segments': segments,
        'total_distance_m': total_distance,
        'total_time_s': total_time,
        'walking_distance_m': sum(
            seg['distance_m'] for seg in segments if seg['type'] == 'walking'
        ),
        'driving_distance_m': sum(
            seg['distance_m'] for seg in segments if seg['type'] == 'driving'
        )
    }
```

## Frontend Visualization

### Leaflet Polyline Rendering

```javascript
function renderEstablishmentRoute(routeData) {
    const segments = routeData.segments;
    
    segments.forEach((segment, index) => {
        // Convert coords to Leaflet format
        const path = segment.coords.map(c => [c.lat, c.lng]);
        
        // Create polyline with appropriate styling
        const polyline = L.polyline(path, {
            color: segment.style.color,
            weight: segment.style.weight,
            opacity: segment.style.opacity,
            dashArray: segment.style.dashArray || null
        }).addTo(map);
        
        // Add popup with segment info
        const popupContent = `
            <div class="segment-info">
                <strong>${segment.type === 'walking' ? '🚶' : '🚗'} ${segment.description}</strong><br>
                Distance: ${segment.distance_m.toFixed(0)}m<br>
                Time: ${formatTime(segment.time_s)}
            </div>
        `;
        polyline.bindPopup(popupContent);
        
        // Store for cleanup
        routePolylines.push(polyline);
    });
    
    // Add markers for snap points (visual feedback)
    if (segments.length > 1) {
        // Start snap point
        const startSnap = segments[0].coords[1];  // End of walking segment
        addSnapMarker(startSnap, 'Road Entry');
        
        // End snap point (if exists)
        if (segments[segments.length - 1].type === 'walking') {
            const endSnap = segments[segments.length - 1].coords[0];
            addSnapMarker(endSnap, 'Road Exit');
        }
    }
}

function addSnapMarker(coords, label) {
    const snapIcon = L.divIcon({
        className: 'snap-marker',
        html: '<div style="background: #FFA500; border: 2px solid white; border-radius: 50%; width: 12px; height: 12px;"></div>',
        iconSize: [12, 12],
        iconAnchor: [6, 6]
    });
    
    const marker = L.marker([coords.lat, coords.lng], {
        icon: snapIcon,
        title: label
    }).addTo(map);
    
    marker.bindPopup(`<strong>${label}</strong>`);
    routeMarkers.push(marker);
}
```

## UI/UX Enhancements

### Location Selection Flow

```
User Action 1: Click "Pin Start Location"
              ↓
User Action 2: Click on establishment on map
              ↓
System: 1. Show establishment marker (🏪)
        2. Find nearest road segment
        3. Calculate projection point
        4. Show snap marker (⭕)
        5. Draw connector line (- - -)
        6. Update UI text:
           "BAZZITO Wine & Liquor"
           "Snapped to C. Benitez Street (85m)"
              ↓
User sees: Clear visual of where route will start
```

### Turn-by-Turn Directions Format

```
Route from BAZZITO Wine & Liquor to UYB Printing Press Corp.

1. 🚶 Walk 85m to C. Benitez Street (approx. 1 min)
2. 🚗 Head northeast on C. Benitez Street (200m)
3. 🚗 Turn right onto San Martin De Porres Boulevard (1.2km)
4. 🚗 Turn left onto Del Monte Avenue (800m)
5. 🚗 Continue on Eulogio Rodriguez Sr. Avenue (450m)
6. 🚶 Walk 45m to destination (approx. 30 sec)

Total Distance: 2.78 km (Walking: 130m, Driving: 2.65km)
Estimated Time: 12 minutes (Walking: 2 min, Driving: 10 min)
```

## Error Handling

### Case 1: Too Far from Road
```python
if snap_result is None or snap_result['distance_m'] > 1000:
    return {
        'success': False,
        'error': 'Location is too far from any road',
        'message': 'Please select a location within 1km of a road',
        'distance_to_nearest_road': snap_result['distance_m'] if snap_result else None,
        'suggested_location': find_nearest_accessible_point(lat, lng)
    }
```

### Case 2: Inaccessible Area
```python
def validate_accessibility(point, snap_point):
    """Check if path from point to snap_point is walkable"""
    
    # Check for obstacles (water, buildings, etc.)
    obstacles = check_osm_obstacles_between(point, snap_point)
    
    if obstacles:
        return {
            'accessible': False,
            'obstacles': obstacles,
            'message': f'Path may be blocked by: {", ".join(obstacles)}',
            'suggestion': 'Try selecting a point closer to the road'
        }
    
    return {'accessible': True}
```

## Performance Optimizations

### Spatial Indexing
Use R-tree or KD-tree for faster nearest segment lookup:

```python
from scipy.spatial import cKDTree

class RoadSegmentIndex:
    def __init__(self, edges_df, nodes_df):
        # Pre-compute segment midpoints
        self.segments = []
        self.midpoints = []
        
        node_coords = {...}  # node_id -> (lat, lng)
        
        for _, edge in edges_df.iterrows():
            seg_start = node_coords[edge['source']]
            seg_end = node_coords[edge['target']]
            midpoint = (
                (seg_start[0] + seg_end[0]) / 2,
                (seg_start[1] + seg_end[1]) / 2
            )
            
            self.segments.append({
                'edge': edge,
                'start': seg_start,
                'end': seg_end
            })
            self.midpoints.append(midpoint)
        
        # Build KD-tree for fast spatial lookup
        self.tree = cKDTree(self.midpoints)
    
    def find_nearest_segments(self, lat, lng, k=10):
        """Find k nearest segments to point"""
        distances, indices = self.tree.query([lat, lng], k=k)
        return [self.segments[i] for i in indices]
```

## Testing Scenarios

### Test 1: Establishment on Road
- Input: Click on point exactly on road node
- Expected: snap_distance = 0, no connector line

### Test 2: Establishment Near Road
- Input: Click 50m perpendicular from road
- Expected: snap_distance = 50m, connector line shown

### Test 3: Establishment Between Nodes
- Input: Click on midpoint between two nodes
- Expected: Projection onto segment, not to either node

### Test 4: Corner Case - Road Intersection
- Input: Click near intersection of 3+ roads
- Expected: Snap to closest segment, clear indication of chosen road

### Test 5: Long Distance
- Input: Click 2km from nearest road
- Expected: Error message, suggestion to pick closer location

## Integration Checklist

- [ ] Implement `project_point_onto_segment()` in `road_segment_utils.py`
- [ ] Implement `find_nearest_road_segment()` in `coordinate_mapper.py`
- [ ] Add `/find_nearest_road_segment` endpoint in `flask_server.py`
- [ ] Update map click handler in `index.html` to use new endpoint
- [ ] Add visual feedback (dual markers, connector line) in frontend
- [ ] Modify route computation to accept snap points
- [ ] Update polyline rendering to style segments differently
- [ ] Add distance/time calculations for walking segments
- [ ] Implement validation for inaccessible areas
- [ ] Add unit tests for projection algorithm
- [ ] Add integration tests for full workflow
- [ ] Update documentation and user guide

## Expected Results

**Before Fix:**
- ❌ Routes jump back to nearest node
- ❌ Straight lines from establishments
- ❌ No visual feedback on snapping
- ❌ Confusing route geometry

**After Fix:**
- ✅ Routes start from proper road entry point
- ✅ Clear visual distinction between walking and driving
- ✅ Users see exactly where route connects
- ✅ Accurate distance and time estimates
- ✅ Natural-looking route geometry
