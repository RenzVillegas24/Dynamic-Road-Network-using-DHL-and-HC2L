DHL#!/bin/bash
# Flask Server Runner Script
# This script starts the Flask application with proper configuration
#
# Usage:
#   ./run_server.sh              # Interactive mode
#   ./run_server.sh --generate   # Auto-generate data and indexes
#   ./run_server.sh --skip       # Skip data checks and start server

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MAIN_DIR="$SCRIPT_DIR/Main"

# Parse command-line arguments
AUTO_GENERATE=false
SKIP_CHECKS=false

for arg in "$@"; do
    case $arg in
        --generate)
            AUTO_GENERATE=true
            ;;
        --skip)
            SKIP_CHECKS=true
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --generate    Automatically generate data and build indexes if missing"
            echo "  --skip        Skip data checks and start server anyway"
            echo "  --help        Show this help message"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "════════════════════════════════════════════════════════════════"
echo "  Dynamic Road Network - Flask Server"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if .env exists
if [ ! -f "$MAIN_DIR/.env" ]; then
    echo "  ✗ Error: Main/.env file not found"
    echo ""
    echo "  Please configure your environment first:"
    echo "    1. Copy Main/.env.example to Main/.env"
    echo "    2. Add your Google Maps API key"
    echo ""
    exit 1
fi

# Function to generate data
:generate_data
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Generating OSM Data and Building Indexes (15-20 minutes)"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Activate virtual environment if it exists
CONDA_ENV_PATH="$SCRIPT_DIR/.conda"
if [ -d "$CONDA_ENV_PATH" ]; then
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV_PATH"
elif [ -d "$SCRIPT_DIR/.venv" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

cd "$MAIN_DIR"
python request_new_datasets.py

if [ $? -ne 0 ]; then
    echo ""
    echo "  ✗ Error: Data generation and index building failed"
    exit 1
fi

cd "$SCRIPT_DIR"

echo ""
echo "  ✓ Data generation and index building completed!"
echo ""

# Check if data files exist
DATA_EXISTS=true
if [ ! -f "$MAIN_DIR/data/raw/quezon_city_nodes.csv" ] || \
   [ ! -f "$MAIN_DIR/data/raw/quezon_city_edges.csv" ]; then
    DATA_EXISTS=false
fi

# Check if index files exist
INDEX_EXISTS=true
if [ ! -f "$MAIN_DIR/data/processed/quezon_city.graph" ] || \
   [ ! -f "$MAIN_DIR/data/processed/quezon_city.dhl.index" ] || \
   [ ! -f "$MAIN_DIR/data/processed/quezon_city.hc2l.index" ]; then
    INDEX_EXISTS=false
fi

# Offer to generate data if missing
if [ "$DATA_EXISTS" = false ] || [ "$INDEX_EXISTS" = false ]; then
    if [ "$SKIP_CHECKS" = true ]; then
        echo "  ⚠ Warning: Data or index files are missing (--skip mode)"
        echo ""
    elif [ "$AUTO_GENERATE" = true ]; then
        echo "  ℹ Auto-generating data and indexes (--generate mode)..."
        generate_data
    else
        echo "  ⚠ Warning: Data or index files are missing"
        echo ""
        if [ "$DATA_EXISTS" = false ]; then
            echo "    Missing: CSV data files (quezon_city_nodes.csv, quezon_city_edges.csv)"
        fi
        if [ "$INDEX_EXISTS" = false ]; then
            echo "    Missing: Graph index files (.graph, .dhl.index, .hc2l.index)"
        fi
        echo ""
        echo "  Would you like to:"
        echo "    1) Generate data and build indexes now (recommended, takes 15-20 min)"
        echo "    2) Continue without data (server will start but routing won't work)"
        echo "    3) Exit"
        echo ""
        read -p "  Enter your choice (1-3): " choice
        echo ""
        
        case $choice in
            1)
                generate_data
                ;;
            2)
                echo "  ⚠ Continuing without data - routing will not work!"
                echo ""
                ;;
            3)
                echo "  Exiting..."
                exit 0
                ;;
            *)
                echo "  ✗ Invalid choice. Exiting..."
                exit 1
                ;;
        esac
    fi
fi

echo "  Starting Flask server..."
echo ""

# Change to Main directory and run Flask
cd "$MAIN_DIR"

# Check if virtual environment exists and activate it
CONDA_ENV_PATH="$SCRIPT_DIR/.conda"
if [ -d "$CONDA_ENV_PATH" ]; then
    echo "  ✓ Activating conda environment at .conda/..."
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV_PATH"
elif [ -d "$SCRIPT_DIR/.venv" ]; then
    echo "  ✓ Activating virtual environment..."
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Run Flask server
python flask_server.py

# Deactivate virtual environment on exit
if [ -d "$SCRIPT_DIR/.venv" ]; then
    deactivate 2>/dev/null || true
fi
