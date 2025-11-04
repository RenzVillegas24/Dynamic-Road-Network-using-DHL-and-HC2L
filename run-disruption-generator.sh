#!/bin/bash
################################################################################
# Dynamic Road Network - Generate Traffic Disruptions Script
################################################################################
# Purpose:
# This script generates traffic scenarios (disruptions) for testing.
# Use this when you want to generate traffic data without starting the full server.
#
# Traffic modes:
#   • flow        - Use only real-time traffic flow data from HERE API
#   • incidents   - Use only incident/accident data from HERE API
#   • both        - Use both flow and incident data (combined)
#   • synthetic   - Use simulated/random traffic (no API key needed)
#
# Usage:
#   ./run-disruption-generator.sh                  # Generate 1 scenario (default)
#   ./run-disruption-generator.sh --scenarios 3    # Generate 3 snapshots
#   ./run-disruption-generator.sh --continuous     # Keep updating (every 5 min)
#   ./run-disruption-generator.sh --flow           # Use flow data only
#   ./run-disruption-generator.sh --help           # Show help
################################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
MODE="both"
SCENARIOS=1
CONTINUOUS=false
INTERVAL=300
PLACE="Quezon City, Philippines"
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
    echo -e "\n${BLUE}Dynamic Road Network - Traffic Disruption Generator${NC}\n"
    echo "Generates traffic scenarios for testing and simulation."
    echo ""
    echo "Usage:"
    echo -e "  ${GREEN}./run-disruption-generator.sh${NC}                 Generate 1 snapshot"
    echo -e "  ${GREEN}./run-disruption-generator.sh --scenarios 5${NC}    Generate 5 snapshots"
    echo -e "  ${GREEN}./run-disruption-generator.sh --continuous${NC}    Run continuously (every 5 min)"
    echo -e "  ${GREEN}./run-disruption-generator.sh -i 120${NC}          Update every 120 seconds"
    echo -e "  ${GREEN}./run-disruption-generator.sh --flow${NC}          Use flow data only"
    echo -e "  ${GREEN}./run-disruption-generator.sh --synthetic{{NC}     Use synthetic data"
    echo -e "  ${GREEN}./run-disruption-generator.sh --help${NC}          Show this help"
    echo ""
    echo "Traffic Modes:"
    echo -e "  ${YELLOW}flow${NC}         - Real-time traffic flow from HERE API"
    echo -e "  ${YELLOW}incidents${NC}    - Road incidents/accidents from HERE API"
    echo -e "  ${YELLOW}both${NC}         - Combined flow + incidents (default)"
    echo -e "  ${YELLOW}synthetic${NC}    - Simulated traffic (no API needed)"
    echo ""
    echo "Examples:"
    echo -e "  ${GREEN}./run-disruption-generator.sh --mode flow --scenarios 10${NC}"
    echo -e "    Generate 10 snapshots using only flow data"
    echo ""
    echo -e "  ${GREEN}./run-disruption-generator.sh --mode both --continuous -i 60${NC}"
    echo -e "    Generate snapshots continuously, update every 60 seconds"
    echo ""
    echo -e "  ${GREEN}./run-disruption-generator.sh --mode synthetic --scenarios 3{{NC}"
    echo -e "    Generate 3 snapshots with simulated data (no API key needed)"
    echo ""
}

cleanup() {
    echo ""
    if [ "$CONTINUOUS" = true ]; then
        echo -e "${YELLOW}Interrupted by user${NC}"
    fi
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --flow)
            MODE="flow"
            shift
            ;;
        --incidents)
            MODE="incidents"
            shift
            ;;
        --both)
            MODE="both"
            shift
            ;;
        --synthetic)
            MODE="synthetic"
            shift
            ;;
        --scenarios)
            SCENARIOS="$2"
            shift 2
            ;;
        --continuous)
            CONTINUOUS=true
            shift
            ;;
        --interval|-i)
            INTERVAL="$2"
            shift 2
            ;;
        --place)
            PLACE="$2"
            shift 2
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

# Validate mode
case "$MODE" in
    flow|incidents|both|synthetic)
        : # Valid
        ;;
    *)
        print_error "Invalid mode: $MODE"
        echo "Valid modes: flow, incidents, both, synthetic"
        exit 1
        ;;
esac

# ============================================================================
# MAIN FLOW
# ============================================================================

print_header "🔄 Traffic Disruption Generator"

print_info "Configuration:"
echo "  Mode: $MODE"
if [ "$CONTINUOUS" = true ]; then
    echo "  Type: Continuous (update every ${INTERVAL}s)"
else
    echo "  Type: One-time (${SCENARIOS} scenario(s))"
fi
echo "  Place: $PLACE"
echo ""

cd "$MAIN_DIR"

# Set up trap for Ctrl+C
trap cleanup SIGINT SIGTERM

# Run generator
if [ "$CONTINUOUS" = true ]; then
    print_info "Starting continuous generation..."
    echo ""
    python3 ../unified_data_generator.py \
        --mode "$MODE" \
        --continuous \
        --interval "$INTERVAL" \
        --place "$PLACE"
else
    print_info "Generating ${SCENARIOS} scenario(s)..."
    echo ""
    python3 ../unified_data_generator.py \
        --mode "$MODE" \
        --scenarios "$SCENARIOS" \
        --place "$PLACE"
    
    if [ $? -eq 0 ]; then
        echo ""
        print_header "✓ Generation Complete"
        print_success "Scenarios generated successfully"
        echo ""
        print_info "Output files created in: $MAIN_DIR/data/"
        echo "  • Disruptions: $MAIN_DIR/data/disruptions/"
        echo "  • Graph files: $MAIN_DIR/data/processed/"
    fi
fi
