#!/usr/bin/env fish
# Flask Server Runner Script (Fish Shell)
# This script starts the Flask application with proper configuration
#
# Usage:
#   ./run_server.fish              # Interactive mode
#   ./run_server.fish --generate   # Auto-generate data and indexes
#   ./run_server.fish --skip       # Skip data checks and start server

set SCRIPT_DIR (dirname (status --current-filename))
set MAIN_DIR "$SCRIPT_DIR/Main"

# Parse command-line arguments
set AUTO_GENERATE false
set SKIP_CHECKS false

for arg in $argv
    switch $arg
        case --generate
            set AUTO_GENERATE true
        case --skip
            set SKIP_CHECKS true
        case --help
            echo "Usage: "(status --current-filename)" [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --generate    Automatically generate data and build indexes if missing"
            echo "  --skip        Skip data checks and start server anyway"
            echo "  --help        Show this help message"
            echo ""
            exit 0
        case '*'
            echo "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
    end
end

echo "════════════════════════════════════════════════════════════════"
echo "  Dynamic Road Network - Flask Server"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if .env exists
if not test -f "$MAIN_DIR/.env"
    echo "  ✗ Error: Main/.env file not found"
    echo ""
    echo "  Please configure your environment first:"
    echo "    1. Copy Main/.env.example to Main/.env"
    echo "    2. Add your Google Maps API key"
    echo ""
    exit 1
end

# Function to generate data
function generate_data
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  Generating OSM Data and Building Indexes (15-20 minutes)"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    
    # Activate conda environment if it exists
    set CONDA_ENV_PATH "$SCRIPT_DIR/.conda"
    if test -d "$CONDA_ENV_PATH"
        # Source conda for fish
        source (conda info --base)/etc/fish/conf.d/conda.fish
        conda activate "$CONDA_ENV_PATH"
    else if test -d "$SCRIPT_DIR/.venv"
        source "$SCRIPT_DIR/.venv/bin/activate.fish"
    end
    
    cd "$MAIN_DIR"
    python request_new_datasets.py
    
    if test $status -ne 0
        echo ""
        echo "  ✗ Error: Data generation and index building failed"
        exit 1
    end
    
    cd "$SCRIPT_DIR"
    
    echo ""
    echo "  ✓ Data generation and index building completed!"
    echo ""
end

# Check if data files exist
set DATA_EXISTS true
if not test -f "$MAIN_DIR/data/raw/quezon_city_nodes.csv"; or not test -f "$MAIN_DIR/data/raw/quezon_city_edges.csv"
    set DATA_EXISTS false
end

# Check if index files exist
set INDEX_EXISTS true
if not test -f "$MAIN_DIR/data/processed/quezon_city.graph"; or \
   not test -f "$MAIN_DIR/data/processed/quezon_city.dhl.index"; or \
   not test -f "$MAIN_DIR/data/processed/quezon_city.hc2l.index"
    set INDEX_EXISTS false
end

# Offer to generate data if missing
if test "$DATA_EXISTS" = false; or test "$INDEX_EXISTS" = false
    if test "$SKIP_CHECKS" = true
        echo "  ⚠ Warning: Data or index files are missing (--skip mode)"
        echo ""
    else if test "$AUTO_GENERATE" = true
        echo "  ℹ Auto-generating data and indexes (--generate mode)..."
        generate_data
    else
        echo "  ⚠ Warning: Data or index files are missing"
        echo ""
        if test "$DATA_EXISTS" = false
            echo "    Missing: CSV data files (quezon_city_nodes.csv, quezon_city_edges.csv)"
        end
        if test "$INDEX_EXISTS" = false
            echo "    Missing: Graph index files (.graph, .dhl.index, .hc2l.index)"
        end
        echo ""
        echo "  Would you like to:"
        echo "    1) Generate data and build indexes now (recommended, takes 15-20 min)"
        echo "    2) Continue without data (server will start but routing won't work)"
        echo "    3) Exit"
        echo ""
        read -P "  Enter your choice (1-3): " choice
        echo ""
        
        switch $choice
            case 1
                generate_data
            case 2
                echo "  ⚠ Continuing without data - routing will not work!"
                echo ""
            case 3
                echo "  Exiting..."
                exit 0
            case '*'
                echo "  ✗ Invalid choice. Exiting..."
                exit 1
        end
    end
end

echo "  Starting Flask server..."
echo ""

# Change to Main directory and run Flask
cd "$MAIN_DIR"

# Check if conda environment exists and activate it
set CONDA_ENV_PATH "$SCRIPT_DIR/.conda"
if test -d "$CONDA_ENV_PATH"
    echo "  ✓ Activating conda environment at .conda/..."
    source (conda info --base)/etc/fish/conf.d/conda.fish
    conda activate "$CONDA_ENV_PATH"
else if test -d "$SCRIPT_DIR/.venv"
    echo "  ✓ Activating virtual environment..."
    source "$SCRIPT_DIR/.venv/bin/activate.fish"
end

# Run Flask server
python flask_server.py

# Deactivate virtual environment on exit
if test -d "$SCRIPT_DIR/.venv"
    deactivate 2>/dev/null; or true
end
