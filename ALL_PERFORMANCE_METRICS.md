# Complete List of All Performance Metrics

## Overview
This document lists ALL performance metrics tracked and displayed in the Dynamic Road Network system using DHL and HC2L algorithms.

---

## 🎯 Core Performance Metrics (Displayed in GUI)

### 1. **Labeling Time**
- **Description**: Time to load the precomputed index structure
- **Unit**: milliseconds (ms)
- **Source**: C++ index load time measurement
- **DHL Field**: `metrics.labeling_time_ms`
- **HC2L Field**: `metrics.labeling_info.index_load_time_ms`
- **Typical Range**: 10ms - 500ms

### 2. **Labeling Size**
- **Description**: Memory size of the index structure
- **Unit**: Megabytes (MB)
- **Source**: C++ index file size / memory allocation
- **DHL Field**: `metrics.labeling_size_mb` (from file size)
- **HC2L Field**: `metrics.labeling_info.index_size_mb`
- **Typical Range**: 5MB - 50MB

### 3. **Query Time**
- **Description**: Time to compute shortest path distance
- **Unit**: milliseconds (ms)
- **Source**: C++ query execution timer
- **DHL Field**: `metrics.query_time_ms`
- **HC2L Field**: `metrics.query_time_ms`
- **Typical Range**: 0.001ms - 10ms

---

## 📊 Additional Algorithm Metrics

### DHL (Dual-Hierarchy Labelling) Specific

#### 4. **Total Distance Units**
- **Field**: `metrics.total_distance_units`
- **Description**: DHL computed distance in abstract units
- **Unit**: distance units
- **Usage**: Internal DHL calculation

#### 5. **Path Length**
- **Field**: `metrics.path_length`
- **Description**: Number of nodes in the path
- **Unit**: count
- **Usage**: Route complexity indicator

#### 6. **Hoplinks Examined** (DHL-specific)
- **Field**: `metrics.hoplinks_examined`
- **Description**: Number of hops examined during query
- **Unit**: count
- **Usage**: Query efficiency metric

#### 7. **Labeling Size (Bytes)**
- **Field**: `metrics.labeling_size_bytes`
- **Description**: Exact byte size of index
- **Unit**: bytes
- **Usage**: Precise memory tracking

---

### HC2L (Hierarchical Cut 2-Hop Labelling) Specific

#### 8. **Total Labels**
- **Field**: `metrics.labeling_info.total_labels`
- **Description**: Total number of labels in the index
- **Unit**: count
- **Usage**: Index complexity metric

#### 9. **Infinite Labels**
- **Field**: `metrics.labeling_info.infinite_labels`
- **Description**: Number of unreachable node pairs
- **Unit**: count
- **Usage**: Graph connectivity metric

#### 10. **Hierarchy Height**
- **Field**: `metrics.labeling_info.hierarchy_height`
- **Description**: Depth of the cut hierarchy
- **Unit**: levels
- **Usage**: Index structure depth

#### 11. **Max Label Count Per Node**
- **Field**: `metrics.labeling_info.max_label_count_per_node`
- **Description**: Maximum labels stored for any single node
- **Unit**: count
- **Usage**: Index balance metric

#### 12. **Max Cut Size**
- **Field**: `metrics.labeling_info.max_cut_size`
- **Description**: Largest cut in the hierarchy
- **Unit**: count
- **Usage**: Cut quality metric

#### 13. **Average Cut Size**
- **Field**: `metrics.labeling_info.average_cut_size`
- **Description**: Mean size of all cuts
- **Unit**: count (decimal)
- **Usage**: Overall cut quality

#### 14. **Non-Empty Cuts**
- **Field**: `metrics.labeling_info.non_empty_cuts`
- **Description**: Number of cuts with at least one label
- **Unit**: count
- **Usage**: Active hierarchy levels

---

## 🚗 Route Quality Metrics

### 15. **Calculated Distance (Meters)**
- **Field**: `metrics.calculated_distance_meters`
- **Description**: GPS-based route distance using Haversine
- **Unit**: meters
- **Source**: C++ Haversine calculation from coordinates
- **Typical Range**: 100m - 50km

### 16. **Calculated Distance (Kilometers)**
- **Field**: `metrics.calculated_distance_km`
- **Description**: Same as above, converted to km
- **Unit**: kilometers
- **Display**: 2 decimal places

### 17. **ETA (Seconds)**
- **Field**: `metrics.eta_seconds`
- **Description**: Estimated time of arrival in seconds
- **Unit**: seconds
- **Source**: C++ calculation using traffic speeds and road types
- **Calculation**: Based on actual traffic flow data

### 18. **ETA (Formatted)**
- **Field**: `metrics.eta_formatted`
- **Description**: Human-readable ETA
- **Unit**: string (e.g., "5m 23s", "1h 15m")
- **Display**: Friendly format

---

## 🚦 Traffic & Disruption Metrics

### 19. **Uses Disruptions**
- **Field**: `metrics.uses_disruptions`
- **Description**: Whether traffic/disruptions were considered
- **Unit**: boolean
- **Values**: `true` / `false`

### 20. **Tau Threshold**
- **Field**: `metrics.tau_threshold`
- **Description**: LazyHC2L impact score threshold
- **Unit**: 0.0 - 1.0
- **Usage**: Determines immediate vs lazy update

### 21. **Routing Mode**
- **Field**: `metrics.routing_mode`
- **Description**: HC2L update strategy
- **Values**: 
  - `"BASE"` - No disruptions
  - `"IMMEDIATE_UPDATE"` - Full relabeling
  - `"LAZY_UPDATE"` - Deferred relabeling
  - `"DISRUPTED"` - With traffic data

---

## 🔧 LazyHC2L Update Metrics

### 22. **Update Strategy**
- **Field**: `lazy_hc2l.update_strategy`
- **Description**: Chosen update approach
- **Values**: `"none"`, `"immediate_update"`, `"lazy_update"`

### 23. **Disruption Impact Score**
- **Field**: `lazy_hc2l.disruption_impact_score`
- **Description**: Severity of disruptions (0.0 - 1.0)
- **Formula**: `f(Δw) × f_jam × (1.0 + f_closure)`

### 24. **Dirty Nodes Marked**
- **Field**: `lazy_hc2l.dirty_nodes_marked`
- **Description**: Number of nodes with outdated labels
- **Unit**: count
- **Usage**: Lazy update state tracking

### 25. **Dirty Nodes on Path**
- **Field**: `lazy_hc2l.dirty_nodes_affected_path`
- **Description**: Dirty nodes intersecting current route
- **Unit**: count
- **Usage**: Cache hit/miss indicator

### 26. **Lazy Repair Time**
- **Field**: `lazy_hc2l.lazy_repair_time_ms`
- **Description**: Time spent repairing labels
- **Unit**: milliseconds
- **Usage**: Lazy update overhead

### 27. **Nodes Repaired**
- **Field**: `lazy_hc2l.nodes_repaired`
- **Description**: Number of nodes whose labels were updated
- **Unit**: count

### 28. **Cache Hit**
- **Field**: `lazy_hc2l.cache_hit`
- **Description**: Whether query used cached labels
- **Unit**: boolean
- **Values**: `true` / `false`

### 29. **Total Updates**
- **Field**: `lazy_hc2l.total_updates`
- **Description**: Cumulative update count
- **Unit**: count
- **Usage**: System state tracking

---

## 📍 Route Structure Metrics

### 30. **Path Nodes**
- **Field**: `route.path_nodes`
- **Description**: Array of node IDs in the route
- **Unit**: array of integers
- **Usage**: Route reconstruction

### 31. **Edge Count**
- **Field**: `metrics.edge_count` (derived)
- **Description**: Number of road segments
- **Calculation**: `len(route.geometry) - 1`

### 32. **Turn-by-Turn Steps**
- **Field**: Derived from `route.turn_by_turn_directions`
- **Description**: Number of navigation instructions
- **Unit**: count

---

## 🎨 Per-Edge Traffic Metrics

### For each edge in `route.geometry[]`:

#### 33. **Jam Factor**
- **Field**: `geometry[i].jam_factor`
- **Description**: HERE API traffic congestion level
- **Unit**: 0.0 - 10.0
- **Scale**: 0=free flow, 10=standstill

#### 34. **Current Speed**
- **Field**: `geometry[i].speed_kmh`
- **Description**: Current traffic speed
- **Unit**: km/h

#### 35. **Speed Reduction**
- **Field**: `geometry[i].speed_reduction`
- **Description**: Percentage speed decrease
- **Unit**: 0.0 - 1.0
- **Formula**: `1.0 - (current_speed / free_flow_speed)`

#### 36. **Flow Status**
- **Field**: `geometry[i].flow_status`
- **Description**: Traffic condition category
- **Values**: `"light"`, `"medium"`, `"heavy"`

#### 37. **Edge Color**
- **Field**: `geometry[i].color`
- **Description**: Visual indicator color
- **Values**: 
  - `"#10b981"` (green) - light traffic
  - `"#f59e0b"` (orange) - medium traffic  
  - `"#ef4444"` (red) - heavy traffic

#### 38. **Road Name**
- **Field**: `geometry[i].road_name`
- **Description**: OSM road name
- **Unit**: string

#### 39. **Highway Type**
- **Field**: `geometry[i].highway_type`
- **Description**: OSM road classification
- **Values**: `"motorway"`, `"primary"`, `"secondary"`, `"residential"`, etc.

#### 40. **Distance (Meters)**
- **Field**: `geometry[i].distance_meters`
- **Description**: Length of this road segment
- **Unit**: meters

#### 41. **Free Flow Speed**
- **Field**: `geometry[i].free_flow_speed_kmh`
- **Description**: Speed limit / optimal speed
- **Unit**: km/h

#### 42. **Is Closed**
- **Field**: `geometry[i].is_closed`
- **Description**: Road closure status
- **Unit**: boolean

#### 43. **Incident Type**
- **Field**: `geometry[i].incident_type`
- **Description**: Type of disruption
- **Values**: `"none"`, `"accident"`, `"construction"`, `"closure"`, `"congestion"`

#### 44. **Incident Confidence**
- **Field**: `geometry[i].incident_confidence`
- **Description**: Data reliability
- **Unit**: 0.0 - 1.0

---

## 🔄 Comparison Mode Metrics

### When comparing DHL vs HC2L:

#### 45. **Distance Difference**
- **Field**: `metrics.distance_difference_meters`
- **Description**: Absolute distance difference
- **Unit**: meters

#### 46. **Distance Change Percentage**
- **Field**: `metrics.distance_change_percentage`
- **Description**: Relative distance change
- **Unit**: percentage
- **Formula**: `((new - old) / old) × 100`

#### 47. **Route Comparison**
- **Field**: `metrics.route_comparison`
- **Description**: Text comparison of routes
- **Unit**: string

---

## 🎛️ Configuration Metrics

#### 48. **Interpolation Used**
- **Field**: `metrics.interpolation_used`
- **Description**: Whether coordinate interpolation was used
- **Unit**: boolean
- **Current**: Always `false`

#### 49. **Algorithm**
- **Field**: `algorithm`
- **Description**: Routing algorithm identifier
- **Values**: 
  - `"DHL (Dual-Hierarchy Labelling)"`
  - `"HC2L (Hierarchical Cut 2-Hop Labelling)"`
  - `"Comparison Mode"`

---

## 📈 Display Locations

### GUI Performance Metrics Panel:
- ✅ Labeling Time
- ✅ Labeling Size  
- ✅ Query Time

### Bottom Info Bar:
- ✅ ETA (formatted)
- ✅ Total Distance (km)
- ✅ Dynamic metric (query time or edge count)

### Route Panel Header:
- ✅ Distance (km with walking/driving breakdown)
- ✅ Duration (estimated minutes)
- ✅ Steps (turn count)

### Console Debug Output:
- ✅ All 49 metrics logged for debugging
- ✅ Traffic data validation
- ✅ Update strategy decisions
- ✅ Cache hit/miss events

---

## 📝 Metric Access Patterns

### From C++ Output:
```cpp
{
  "metrics": {
    "query_time_ms": 1.234,
    "labeling_time_ms": 45.6,
    "labeling_size_mb": 12.34,
    "calculated_distance_km": 5.67,
    "eta_formatted": "8m 42s",
    "labeling_info": { ... }  // HC2L only
  }
}
```

### In JavaScript:
```javascript
const metrics = routeData.metrics || {};
const labelingInfo = metrics.labeling_info || {};
const queryTime = metrics.query_time_ms;
const indexSize = labelingInfo.index_size_mb || metrics.labeling_size_mb;
```

### In Python:
```python
metrics = route_data.get('metrics', {})
labeling_info = metrics.get('labeling_info', {})
query_time = metrics.get('query_time_ms', 0)
index_size = labeling_info.get('index_size_mb', 0.0)
```

---

## 🎯 Summary Statistics

- **Total Metrics Tracked**: 49
- **Core Performance Metrics**: 3 (displayed prominently)
- **Algorithm-Specific Metrics**: 17
- **Route Quality Metrics**: 8
- **Traffic Metrics**: 12 (per-edge)
- **LazyHC2L Metrics**: 8
- **Comparison Metrics**: 3

---

## 🔍 Metric Categories

### By Purpose:
- **Performance**: 15 metrics
- **Route Quality**: 10 metrics
- **Traffic/Disruptions**: 15 metrics
- **System State**: 9 metrics

### By Algorithm:
- **DHL Only**: 4 metrics
- **HC2L Only**: 10 metrics
- **Both Algorithms**: 35 metrics

### By Data Type:
- **Numeric**: 39 metrics
- **Boolean**: 6 metrics
- **String**: 4 metrics

---

## 💡 Usage Tips

1. **Core Metrics** (Labeling Time/Size, Query Time) - Always displayed
2. **Route Metrics** (Distance, ETA) - Shown in route panel
3. **Traffic Metrics** - Visible on map as edge colors
4. **Debug Metrics** - Available in browser console
5. **Comparison Metrics** - Only in comparison mode

**All metrics are calculated and validated by the C++ algorithms for maximum accuracy!**
