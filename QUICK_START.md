# Quick Start Guide

Get up and running in **5 minutes**!

## Prerequisites

1. **Python 3.8+** - [Download](https://www.python.org/downloads/)
2. **Conda** - [Download Miniconda](https://docs.conda.io/en/latest/miniconda.html)
3. **C++ Compiler** - g++ (Linux/macOS) or MinGW (Windows)

## Installation

### Windows

```cmd
REM Run the setup script
setup.bat

REM Choose: 1 (Automatic Setup)
REM The script will do everything automatically!
```

### Linux/macOS

```bash
# Make script executable and run
chmod +x setup.sh
./setup.sh

# Choose: 1 (Automatic Setup)
# The script will do everything automatically!
```

## What Happens Automatically

The setup script will:

-  Create conda environment in `.conda/` folder (local to project)
-  Install all dependencies (including GDAL)
-  Set up directory structure
-  Configure .env file (you'll need to add your API key)
-  Build C++ executables

## Configure API Key

Edit `Main/.env` and add your Google Maps API key:

```
GOOGLE_MAPS_API_KEY=your_actual_key_here
```

Get a key: https://developers.google.com/maps/documentation/javascript/get-api-key

## Generate Data (Optional)

During setup, you'll be asked if you want to generate data. Choose:

- **Yes** - Downloads OSM data and builds indexes (~15-20 minutes)
- **No** - You can do this later

To generate data later:

**Windows:**
```cmd
conda activate .conda
run_server.bat
REM Choose: 1 (Generate data and build indexes)
```

**Linux/macOS:**
```bash
conda activate .conda
./run_server.sh
# Choose: 1 (Generate data and build indexes)
```

## Run the Application

**Windows:**
```cmd
conda activate .conda
run_server.bat
```

**Linux/macOS:**
```bash
conda activate .conda
./run_server.sh
```

Open browser: **http://localhost:5000**

## Running the Flask Server

The `run_server.bat` (Windows) or `run_server.sh` (Linux/macOS) script includes intelligent data loading!

### Usage Options

#### 1. Interactive Mode (Recommended)

**Windows:**
```cmd
run_server.bat
```

**Linux/macOS:**
```bash
./run_server.sh
```

When data or indexes are missing, you'll see an interactive menu:

```
 Warning: Data or index files are missing

Would you like to:
  1) Generate data and build indexes now (recommended, takes 15-20 min)
  2) Build indexes only (if CSV files already exist)
  3) Continue without data (server will start but routing won't work)
  4) Exit

Enter your choice (1-4):
```

#### 2. Auto-Generate Mode

**Windows:**
```cmd
run_server.bat --generate
```

**Linux/macOS:**
```bash
./run_server.sh --generate
```

Automatically generates data and builds indexes if missing (no prompts).

#### 3. Skip Checks Mode

**Windows:**
```cmd
run_server.bat --skip
```

**Linux/macOS:**
```bash
./run_server.sh --skip
```

Starts the server immediately without checking for data files.

#### 4. Help

**Windows:**
```cmd
run_server.bat --help
```

**Linux/macOS:**
```bash
./run_server.sh --help
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
 raw/
    quezon_city_nodes.csv        (353K) - Node coordinates
    quezon_city_edges.csv        (1.5M) - Road segments with oneway info
    node_id_mapping.csv          (212K) - OSM to sequential ID mapping
 processed/
    quezon_city.graph            (500K) - Binary graph file
    quezon_city.dhl.index        (2.9M) - DHL routing index
    quezon_city.dhl.ch           (796K) - DHL contraction hierarchy
    quezon_city.hc2l.index       (3.3M) - HC2L routing index
    qc_from_csv.gr               (500K) - DIMACS graph format
    qc_disrupted_scenario_1.gr   (659K) - Disrupted graph
 disruptions/
     qc_scenario_for_cpp_1.csv
     qc_scenario_for_cpp_2.csv
```

## Manual Setup (Step by Step)

If you prefer manual control, run the setup script and choose **Option 2: Manual Setup**.

You'll get a menu to:

1. Create/Update Conda Environment
2. Create Directory Structure
3. Setup .env Configuration
4. Build C++ Executables
5. Generate Data and Indexes
6. Check Installation Status

## Manual Data Management

### Generate Data Only

**Windows:**
```cmd
conda activate .conda
cd Main
python request_new_datasets.py
```

**Linux/macOS:**
```bash
conda activate .conda
cd Main
python request_new_datasets.py
```

### Build Indexes Only

**Windows:**
```cmd
build_indexes.bat
```

**Linux/macOS:**
```bash
./build_indexes.sh
```

### Build C++ APIs

**Windows:**
```cmd
build_all.bat
```

**Linux/macOS:**
```bash
./build_all.sh
```

## Complete Automation Flow

**Windows:**
```cmd
REM 1. Initial setup (creates .conda environment)
setup.bat

REM 2. Build C++ routing APIs (done automatically in setup)
REM    Or manually: build_all.bat

REM 3. Run server (will prompt to load data if missing)
run_server.bat
```

**Linux/macOS:**
```bash
# 1. Initial setup (creates .conda environment)
./setup.sh

# 2. Build C++ routing APIs (done automatically in setup)
#    Or manually: ./build_all.sh

# 3. Run server (will prompt to load data if missing)
./run_server.sh
```

## Troubleshooting

### "Conda not found"

Install Miniconda and restart your terminal.

### Build errors

Make sure g++ (or MinGW on Windows) is installed and in PATH.

### Missing dependencies

The conda environment should handle everything. If issues persist:

**Windows:**
```cmd
conda activate .conda
conda env update -f environment.yml -p .conda
```

**Linux/macOS:**
```bash
conda activate .conda
conda env update -f environment.yml -p .conda
```

### Port 5000 in use

Change port in `Main/config.py` or stop the process using port 5000.

### "Data files not found"

- Choose option 1 in interactive mode, or
- Run with `--generate` flag, or
- Manually run `python Main/request_new_datasets.py`

### "Index files not found"

- Choose option 2 in interactive mode (if CSV files exist), or
- Run `./build_indexes.sh` or `build_indexes.bat` manually

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

## Project Structure

```
Project-Root/
 .conda/                           Conda environment (created by setup)
 Main/
    .env                          Configuration (API keys)
    data/
       raw/                      OSM CSV files
       processed/                Graph indexes
    build/
       dhl/                      DHL routing API
       hc2l/                     HC2L routing API
    flask_server.py               Main server
 setup.bat / setup.sh              All-in-one setup
 run_server.bat / run_server.sh    Server launcher
 build_all.bat / build_all.sh      Build C++ APIs
```

## Workflow

```
setup script
    
     Create .conda/ environment
     Install dependencies (GDAL, geopandas, etc.)
     Build C++ executables
     Optionally generate data

run_server script
    
     Activate .conda environment
     Check .env file
     Check data files
        [Missing]  Interactive menu or --generate
            Option 1: Generate data + build indexes
            Option 2: Build indexes only
            Option 3: Continue anyway
            Option 4: Exit
     Start Flask server
         Load routing APIs (DHL and HC2L)
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

## Environment Activation

The conda environment is created locally in the `.conda/` folder. To activate:

**Windows:**
```cmd
conda activate .conda
```

**Linux/macOS:**
```bash
conda activate .conda
```

**Note:** The `run_server` scripts automatically detect and activate the `.conda` environment!

## Support

For issues or questions:
- **Windows Setup:** See [WINDOWS_SETUP.md](WINDOWS_SETUP.md)
- **Full Documentation:** See [README.md](README.md)
- **Check Status:** Run `setup.bat` or `./setup.sh`  Option 2  Option 6

---

**That's it!** You should now have a working Dynamic Road Network system. 