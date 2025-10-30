# Quick Start Guide

## Running the Flask Server

The `run_server.sh` (or `run_server.fish`) script now includes intelligent data loading!

### Usage Options

#### 1. Interactive Mode (Recommended)
```bash
./run_server.sh
# or
./run_server.fish
```

When data or indexes are missing, you'll see an interactive menu:
```
⚠ Warning: Data or index files are missing

Would you like to:
  1) Generate data and build indexes now (recommended, takes 15-20 min)
  2) Build indexes only (if CSV files already exist)
  3) Continue without data (server will start but routing won't work)
  4) Exit

Enter your choice (1-4):
```

#### 2. Auto-Generate Mode
```bash
./run_server.sh --generate
# or
./run_server.fish --generate
```
Automatically generates data and builds indexes if missing (no prompts).

#### 3. Skip Checks Mode
```bash
./run_server.sh --skip
# or
./run_server.fish --skip
```
Starts the server immediately without checking for data files.

#### 4. Help
```bash
./run_server.sh --help
# or
./run_server.fish --help
```

### What Gets Loaded

When you choose to generate data, the script will:

1. **Generate OSM Data** (15-20 minutes)
   - Downloads Quezon City road network from OpenStreetMap
   - Creates `quezon_city_nodes.csv` and `quezon_city_edges.csv`
   - Includes one-way road information
   - Generates disruption scenarios

2. **Build Graph Indexes** (1-2 minutes)
   - Compiles index builder executables
   - Converts `.gr` files to binary graph format
   - Builds DHL routing index (2.9M)
   - Builds HC2L routing index (3.3M)

### Files Created

```
Main/data/
├── raw/
│   ├── quezon_city_nodes.csv        (353K) - Node coordinates
│   ├── quezon_city_edges.csv        (1.5M) - Road segments with oneway info
│   └── node_id_mapping.csv          (212K) - OSM to sequential ID mapping
├── processed/
│   ├── quezon_city.graph            (500K) - Binary graph file
│   ├── quezon_city.dhl.index        (2.9M) - DHL routing index
│   ├── quezon_city.dhl.ch           (796K) - DHL contraction hierarchy
│   ├── quezon_city.hc2l.index       (3.3M) - HC2L routing index
│   ├── qc_from_csv.gr               (500K) - DIMACS graph format
│   └── qc_disrupted_scenario_1.gr   (659K) - Disrupted graph
└── disruptions/
    ├── qc_scenario_for_cpp_1.csv
    └── qc_scenario_for_cpp_2.csv
```

## First-Time Setup

1. **Configure Environment**
   ```bash
   cp Main/.env.example Main/.env
   # Edit Main/.env and add your Google Maps API key
   ```

2. **Run Server (with auto data loading)**
   ```bash
   ./run_server.sh --generate
   ```
   Or use interactive mode:
   ```bash
   ./run_server.sh
   # Choose option 1 when prompted
   ```

3. **Access the Application**
   - Open browser to: http://localhost:5000
   - Choose a routing algorithm (DHL or HC2L)
   - Click on the map to set start and destination points
   - View routing results with metrics

## Manual Data Management

### Generate Data Only
```bash
cd Main
python request_new_datasets.py
```

### Build Indexes Only
```bash
./build_indexes.sh
# or
./build_indexes.fish
```

### Build C++ APIs
```bash
./build_all.sh
# or
./build_all.fish
```

## Complete Automation Flow

```bash
# 1. Initial setup (if .venv doesn't exist)
./setup.sh

# 2. Build C++ routing APIs
./build_all.sh

# 3. Run server (will prompt to load data if missing)
./run_server.sh
```

## Troubleshooting

### "Data files not found"
- Choose option 1 in interactive mode, or
- Run with `--generate` flag, or
- Manually run `python Main/request_new_datasets.py`

### "Index files not found"
- Choose option 2 in interactive mode (if CSV files exist), or
- Run `./build_indexes.sh` manually

### "Graph validation failed"
- Check that CSV files are not corrupted
- Re-run data generation: `cd Main && python request_new_datasets.py`

### OSM data fetch is slow
- Normal behavior - downloading city road network takes time
- Be patient, don't interrupt the process
- Progress will be shown in the console

### Routing returns no results
- Ensure both CSV files and index files exist
- Check that Google Maps API key is set in `.env`
- Verify coordinates are within Quezon City bounds

## Performance Notes

- **Data Generation**: 15-20 minutes (one-time process)
- **Index Building**: 1-2 minutes (one-time process)
- **Server Startup**: < 5 seconds
- **Query Time**: 
  - DHL: ~0.002ms average
  - HC2L: ~0.000ms average

## Architecture

```
run_server.sh/fish
    ↓
    ├─→ Check .env file
    ├─→ Check data files
    │   └─→ [Missing] → Interactive menu or --generate
    │       ├─→ Option 1: request_new_datasets.py + build_indexes.sh
    │       ├─→ Option 2: build_indexes.sh only
    │       ├─→ Option 3: Continue anyway
    │       └─→ Option 4: Exit
    └─→ Start Flask server
        └─→ Load routing APIs (DHL and HC2L)
```

## Next Steps

After successful server start:

1. **Test Basic Routing**
   - Go to http://localhost:5000
   - Select DHL or HC2L algorithm
   - Click two points on the map
   - Verify route is displayed

2. **Test Disruption Scenarios**
   - Enable disruptions toggle
   - Compare routes with/without disruptions

3. **Explore Metrics**
   - Query time comparison (DHL vs HC2L)
   - Path length and distance
   - Node mapping accuracy

4. **Production Deployment**
   - Set `FLASK_ENV=production` in `.env`
   - Use proper WSGI server (gunicorn, uWSGI)
   - Configure nginx reverse proxy
   - Enable HTTPS

## Support

For issues or questions:
- Check `UPDATE_SUMMARY.ai.md` for recent changes
- Review `API_KEY_SECURITY_UPDATE.ai.md` for security setup
- See `FINAL_SETUP_STEPS.ai.md` for detailed instructions
