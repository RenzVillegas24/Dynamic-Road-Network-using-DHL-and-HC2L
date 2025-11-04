#!/bin/bash
################################################################################
# Dynamic Road Network - Start Server Script
################################################################################
# Purpose:
# This script starts the complete system with real-time traffic updates:
# 1. Unified traffic data generator (fetches from HERE API)
# 2. Flask web server for UI and routing
#
# The system continuously fetches real traffic data and updates route calculations
# automatically whenever traffic changes.
#
# Usage:
#   ./start-server.sh              # Start with default settings (90s update interval)
#   ./start-server.sh --interval 60    # Update every 60 seconds
#   ./start-server.sh --synthetic      # Use synthetic traffic (no API)
#   ./start-server.sh --help           # Show help
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
UPDATE_INTERVAL=90
TRAFFIC_MODE="both"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MAIN_DIR="$SCRIPT_DIR/Main"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

show_help() {
    echo -e "\n${BLUE}Dynamic Road Network - Start Server${NC}\n"
    echo "Starts the complete system:"
    echo "  • Unified traffic data generator (real-time traffic updates)"
    echo "  • Flask web server (UI + routing APIs)"
    echo ""
    echo "Usage:"
    echo -e "  ${GREEN}./start-server.sh${NC}                    Start with defaults (90s update)"
    echo -e "  ${GREEN}./start-server.sh --interval 60${NC}      Update every 60 seconds"
    echo -e "  ${GREEN}./start-server.sh --flow${NC}             Use flow data only"
    echo -e "  ${GREEN}./start-server.sh --incidents${NC}        Use incidents only"
    echo -e "  ${GREEN}./start-server.sh --synthetic${NC}        Use synthetic traffic"
    echo -e "  ${GREEN}./start-server.sh --help${NC}             Show this help"
    echo ""
    echo "Features:"
    echo "  • Real HERE API integration (when credentials available)"
    echo "  • Automatic route recalculation on traffic changes"
    echo "  • Both DHL and HC2L algorithms supported"
    echo "  • Web UI at http://localhost:5000"
    echo ""
}

cleanup() {
    echo ""
    print_header "Shutting Down"
    
    print_info "Stopping traffic data generator..."
    pkill -f "unified_data_generator.py" 2>/dev/null || true
    
    print_info "Stopping Flask server..."
    pkill -f "flask_server.py" 2>/dev/null || true
    
    sleep 1
    print_success "All services stopped"
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval)
            UPDATE_INTERVAL="$2"
            shift 2
            ;;
        --flow)
            TRAFFIC_MODE="flow"
            shift
            ;;
        --incidents)
            TRAFFIC_MODE="incidents"
            shift
            ;;
        --both)
            TRAFFIC_MODE="both"
            shift
            ;;
        --synthetic)
            TRAFFIC_MODE="synthetic"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# ============================================================================
# MAIN FLOW
# ============================================================================

print_header "🚀 Dynamic Road Network - System Startup"

# Check if required data exists
if [ ! -f "$MAIN_DIR/data/raw/quezon_city_edges.csv" ]; then
    print_error "Network data not found!"
    echo ""
    echo "Please run data generation first:"
    echo -e "  ${GREEN}./setup.sh --data${NC}"
    exit 1
fi

# Check if indexes exist
if [ ! -f "$MAIN_DIR/data/processed/quezon_city.dhl.index" ] || \
   [ ! -f "$MAIN_DIR/data/processed/quezon_city.hc2l.index" ]; then
    print_warning "Routing indexes not found"
    echo ""
    echo "Please build indexes first:"
    echo -e "  ${GREEN}./setup.sh --indexes${NC}"
    exit 1
fi

print_success "All prerequisites found"
echo ""

# Clean up any existing processes
print_info "Cleaning up existing processes..."
pkill -f "unified_data_generator.py" 2>/dev/null || true
pkill -f "flask_server.py" 2>/dev/null || true
sleep 1
print_success "Previous processes stopped"
echo ""

# Set up trap for Ctrl+C
trap cleanup SIGINT SIGTERM

# Start unified traffic generator in background
print_header "Starting Traffic Data Generator"
print_info "Mode: ${TRAFFIC_MODE}"
print_info "Update interval: ${UPDATE_INTERVAL} seconds"
echo ""

cd "$MAIN_DIR"
python3 ../unified_data_generator.py \
    --mode "$TRAFFIC_MODE" \
    --continuous \
    --interval "$UPDATE_INTERVAL" \
    --place "Quezon City, Philippines" \
    > "logs/traffic_generator.log" 2>&1 &

GENERATOR_PID=$!
print_success "Traffic generator started (PID: $GENERATOR_PID)"
print_info "Log: logs/traffic_generator.log"
echo ""

sleep 2

# Start Flask web server
print_header "Starting Flask Web Server"
print_info "URL: http://localhost:5000"
print_info "Press Ctrl+C to stop all services"
echo ""

python3 flask_server.py
