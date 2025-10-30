# Dynamic Road Network using DHL and HC2L

A high-performance routing system that uses two cutting-edge algorithms for dynamic road network pathfinding:
- **DHL (Dual-Hierarchy Labelling)**: Optimized for static shortest path queries with support for traffic disruptions
- **HC2L (High-Cardinality Two-Level)**: Advanced hierarchical approach for balanced partitioning

## 🌟 Features

- 🚗 **Real-time GPS-based routing** with support for traffic disruptions
- 🗺️ **Interactive web interface** built with Flask and Google Maps
- ⚡ **Ultra-fast query times** using precomputed hierarchical labels
- 📊 **Traffic simulation** with realistic disruption scenarios
- 🔄 **Dynamic updates** to handle changing road conditions
- 🛣️ **Turn-by-turn directions** with actual road names

## 📋 Prerequisites

- **C++ Compiler**: g++ with C++20 support
- **Python**: 3.8 or higher
- **Google Maps API Key**: For the web interface

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Dynamic-Road-Network-using-DHL-and-HC2L
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example environment file and add your Google Maps API key:

```bash
cd Main
cp .env.example .env
```

Edit `.env` and set your Google Maps API key:

```
GOOGLE_MAPS_API_KEY=your_actual_api_key_here
```

### 4. Prepare Data Files

Create the data directory structure:

```bash
mkdir -p Main/data/raw
mkdir -p Main/data/processed
mkdir -p Main/data/disruptions
```

Place your data files in the appropriate directories:
- `Main/data/raw/quezon_city_nodes.csv` - Node coordinates (node_id, latitude, longitude)
- `Main/data/raw/quezon_city_edges.csv` - Road network edges
- `Main/data/disruptions/qc_scenario_for_cpp_1.csv` - Traffic disruption scenarios

### 5. Build the C++ Routing APIs

```bash
# Make the build script executable
chmod +x build_all.sh

# Build both algorithms
./build_all.sh
```

This will compile both DHL and HC2L routing APIs and place the executables in `Main/build/`.

### 6. Run the Application

```bash
cd Main
python flask_server.py
```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

```
.
├── DualHierarchyLabelling/       # DHL algorithm implementation
│   ├── src/                      
│   │   ├── dhl_routing_api.cpp  # JSON API wrapper (NEW)
│   │   ├── road_network.cpp/.h   # Core algorithm
│   │   └── ...
│   └── Makefile                  # Build configuration
│
├── HighCardinalityTwoLevel/      # HC2L algorithm implementation
│   ├── src/
│   │   ├── hc2l_routing_api.cpp # JSON API wrapper (NEW)
│   │   ├── road_network.cpp/.h   # Core algorithm
│   │   └── ...
│   └── makefile                  # Build configuration
│
├── Main/                         # Flask web application
│   ├── config.py                 # Centralized configuration (NEW)
│   ├── flask_server.py           # Flask application
│   ├── dhl_router.py             # Python wrapper for DHL
│   ├── gps_hc2l_router.py        # Python wrapper for HC2L
│   ├── coordinate_mapper.py      # GPS coordinate handling
│   ├── road_name_mapper.py       # Road name extraction
│   ├── .env                      # Environment variables (create from .env.example)
│   │
│   ├── build/                    # Compiled executables (auto-created)
│   │   ├── dhl/
│   │   │   └── dhl_routing_api
│   │   └── hc2l/
│   │       └── hc2l_routing_api
│   │
│   ├── data/                     # Data files
│   │   ├── raw/                  # Original data
│   │   │   ├── quezon_city_nodes.csv
│   │   │   └── quezon_city_edges.csv
│   │   ├── processed/            # Processed indices
│   │   └── disruptions/          # Traffic scenarios
│   │       └── qc_scenario_for_cpp_1.csv
│   │
│   ├── templates/                # HTML templates
│   │   ├── index.html
│   │   ├── dhl_routing_demo.html
│   │   ├── dhc2l_routing_demo.html
│   │   └── map.html
│   │
│   └── static/                   # Static assets
│       └── js/
│           ├── functions.js
│           ├── event-handlers.js
│           └── ...
│
├── build_all.sh                  # Build script for all algorithms
└── README.md                     # This file
```

## 🔧 Configuration

The application uses a centralized configuration system via `Main/config.py`. All paths and settings are managed through this file.

### Environment Variables (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_MAPS_API_KEY` | Your Google Maps JavaScript API key | *Required* |
| `FLASK_ENV` | Flask environment (development/production) | development |
| `FLASK_DEBUG` | Enable Flask debug mode | True |
| `FLASK_HOST` | Flask server host | 0.0.0.0 |
| `FLASK_PORT` | Flask server port | 5000 |
| `DHL_EXECUTABLE` | Path to DHL executable (optional) | Auto-detected |
| `HC2L_EXECUTABLE` | Path to HC2L executable (optional) | Auto-detected |

### Data File Paths

All data file paths are configured in `Main/config.py`:

```python
# Nodes and edges
Config.NODES_CSV         # Node coordinates
Config.EDGES_CSV         # Road network edges
Config.DISRUPTIONS_CSV   # Traffic disruption scenarios

# Executables (auto-detected)
Config.get_dhl_executable()   # DHL routing API
Config.get_hc2l_executable()  # HC2L routing API
```

## 🎯 API Endpoints

### DHL Routing

**POST** `/compute_dhl_route`

Request:
```json
{
  "start_lat": 14.6760,
  "start_lng": 121.0437,
  "dest_lat": 14.6348,
  "dest_lng": 121.0480,
  "use_disruptions": true,
  "tau_threshold": 0.5
}
```

Response:
```json
{
  "success": true,
  "route": { ... },
  "metrics": {
    "total_distance_units": 1234,
    "query_time_ms": 0.523,
    "path_length": 42
  }
}
```

### HC2L Routing

**POST** `/compute_dhc2l_route`

Request:
```json
{
  "start_lat": 14.6760,
  "start_lng": 121.0437,
  "dest_lat": 14.6348,
  "dest_lng": 121.0480,
  "use_disruptions": true,
  "threshold": 0.5
}
```

### Other Endpoints

- `GET /` - Main application interface
- `GET /dhl` - DHL routing demo
- `GET /test` - HC2L routing demo
- `GET /validation` - Validation tools
- `GET /get_active_disruptions` - Current traffic disruptions
- `POST /find_nearest_node` - Find nearest graph node to GPS coordinates
- `POST /compare_routes` - Compare base vs disrupted routes
- `POST /compare_algorithms` - Compare DHL vs HC2L

## 🏗️ Building from Source

### Build DHL Only

```bash
cd DualHierarchyLabelling
make dhl_routing_api
```

### Build HC2L Only

```bash
cd HighCardinalityTwoLevel
make hc2l_routing_api
```

### Build Everything

```bash
./build_all.sh
```

## 🧪 Testing

### Test Configuration

```bash
cd Main
python config.py
```

This will print a summary of the current configuration and validate that all required files and executables are in place.

### Test DHL Router

```python
from dhl_router import DHLRouter

router = DHLRouter()
result = router.compute_route(14.6760, 121.0437, 14.6348, 121.0480, use_disruptions=False, tau_threshold=0.5)
print(result)
```

### Test HC2L Router

```python
from gps_hc2l_router import GPSRoutingService

router = GPSRoutingService()
result = router.compute_route(14.6760, 121.0437, 14.6348, 121.0480, use_disruptions=False)
print(result)
```

## 📊 Data Format

### Nodes CSV
```csv
node_id,latitude,longitude
1,14.676090,121.043758
2,14.674896,121.043668
...
```

### Edges CSV
```csv
source,target,length,name,highway
1,2,142.5,Commonwealth Avenue,primary
2,3,89.3,Elliptical Road,tertiary
...
```

### Disruptions CSV
```csv
source,target,source_lat,source_lon,target_lat,target_lon,road_name,speed_kph,freeFlow_kph,jamFactor,isClosed,segmentLength
1,2,14.676,121.044,14.675,121.044,Commonwealth Ave,15.5,60.0,7.2,False,142.5
...
```

## 🔍 Troubleshooting

### Executables Not Found

If you get "executable not found" errors:

1. Make sure you've run `./build_all.sh`
2. Check that executables exist in `Main/build/dhl/` and `Main/build/hc2l/`
3. Set explicit paths in `.env`:
   ```
   DHL_EXECUTABLE=/path/to/dhl_routing_api
   HC2L_EXECUTABLE=/path/to/hc2l_routing_api
   ```

### Data Files Missing

If you get "data file not found" errors:

1. Check your directory structure matches the expected layout
2. Run `python config.py` to see which files are missing
3. Ensure CSV files are in `Main/data/raw/` and `Main/data/disruptions/`

### Google Maps Not Loading

1. Verify your API key is set in `.env`
2. Check that the API key has the Maps JavaScript API enabled
3. Check browser console for any API errors

## 📚 Algorithm Parameters

### DHL Parameters

- **start_lat, start_lng**: Starting GPS coordinates
- **dest_lat, dest_lng**: Destination GPS coordinates
- **use_disruptions**: Whether to consider traffic disruptions (true/false)
- **tau_threshold**: Routing threshold parameter (0.0 - 1.0)

### HC2L Parameters

- **start_lat, start_lng**: Starting GPS coordinates
- **dest_lat, dest_lng**: Destination GPS coordinates
- **use_disruptions**: Whether to consider traffic disruptions (true/false)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

[Add your license information here]

## 📧 Contact

[Add your contact information here]

## 🙏 Acknowledgments

- DHL Algorithm: Based on research by [Authors]
- HC2L Algorithm: Based on research by [Authors]
- Road network data: OpenStreetMap contributors

## 📖 References

1. **Dual-Hierarchy Labelling**: [Add paper reference]
2. **High-Cardinality Two-Level**: [Add paper reference]

---

**Note**: This is a research project implementing state-of-the-art routing algorithms for academic and educational purposes.
