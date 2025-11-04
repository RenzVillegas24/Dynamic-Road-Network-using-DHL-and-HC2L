#!/bin/bash
################################################################################
# Dynamic Road Network - Complete Setup Script
################################################################################
# This script handles the complete workflow:
# 1. Setup & validation
# 2. Build C++ algorithms (DHL and HC2L)
# 3. Generate data (network + traffic scenarios)
# 4. Build indexes
# 5. Run the Flask web server with real-time traffic updates
#
# Usage:
#   ./setup.sh                    # Interactive menu
#   ./setup.sh --build            # Build only
#   ./setup.sh --data             # Generate data only
#   ./setup.sh --full             # Complete setup
#   ./setup.sh --server           # Run server only
#   ./setup.sh --clean            # Remove generated files
################################################################################

set -e  # Exit on error

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script metadata
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
MAIN_DIR="$PROJECT_ROOT/Main"
BUILD_DIR="$MAIN_DIR/build"
DATA_DIR="$MAIN_DIR/data"
PROCESSED_DATA_DIR="$DATA_DIR/processed"
DISRUPTIONS_DIR="$DATA_DIR/disruptions"

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

print_menu() {
    echo -e "\n${BLUE}Available commands:${NC}"
    echo -e "  ${GREEN}./setup.sh --full${NC}        Complete setup (build + data + indexes + server)"
    echo -e "  ${GREEN}./setup.sh --build${NC}       Build C++ algorithms only"
    echo -e "  ${GREEN}./setup.sh --data${NC}        Generate traffic data and base network"
    echo -e "  ${GREEN}./setup.sh --indexes${NC}     Build routing indexes"
    echo -e "  ${GREEN}./setup.sh --server${NC}      Run Flask web server"
    echo -e "  ${GREEN}./setup.sh --clean${NC}       Remove all generated files"
    echo -e "  ${GREEN}./setup.sh --help${NC}        Show this help message"
    echo ""
}

check_requirements() {
    print_header "Step 1/5: Checking Requirements"

    # Check g++ compiler
    if ! command -v g++ &> /dev/null; then
        print_error "g++ compiler not found!"
        echo ""
        echo "Please install g++ (build-essential):"
        echo "  Ubuntu/Debian: sudo apt-get install build-essential"
        echo "  Fedora: sudo dnf install gcc-c++"
        echo "  macOS: xcode-select --install"
        exit 1
    fi
    print_success "g++ compiler found"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found!"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"

    # Check conda environment (optional but recommended)
    if [ -f "$PROJECT_ROOT/.conda/pyvenv.cfg" ] || [ -f "$PROJECT_ROOT/.conda/bin/python" ]; then
        print_success "Conda environment detected"
    else
        print_warning "Conda environment not found (using system Python)"
    fi

    # Create necessary directories
    mkdir -p "$BUILD_DIR/dhl"
    mkdir -p "$BUILD_DIR/hc2l"
    mkdir -p "$DATA_DIR/raw"
    mkdir -p "$PROCESSED_DATA_DIR"
    mkdir -p "$DISRUPTIONS_DIR"
    print_success "Data directories created"
}

build_dhl() {
    print_header "Building DHL (Dual-Hierarchy Labelling)"

    cd "$PROJECT_ROOT/DualHierarchyLabelling"

    # Build routing API
    print_info "Compiling DHL routing API..."
    if g++ -std=c++2a -O3 -Wall -Wextra -pthread \
        -o "$BUILD_DIR/dhl/dhl_routing_api" \
        src/dhl_routing_api.cpp src/road_network.cpp src/util.cpp; then
        print_success "DHL routing API compiled"
    else
        print_error "DHL routing API compilation failed!"
        return 1
    fi

    # Build index executable
    print_info "Compiling DHL index builder..."
    if g++ -std=c++2a -O3 -Wall -Wextra -pthread \
        -o "$BUILD_DIR/dhl/index" \
        src/index.cpp src/road_network.cpp src/util.cpp; then
        print_success "DHL index builder compiled"
    else
        print_error "DHL index builder compilation failed!"
        return 1
    fi
}

build_hc2l() {
    print_header "Building HC2L (Hierarchical Cut 2-Hop Labelling)"

    cd "$PROJECT_ROOT/HierarchicalCutLabelling"

    # Build routing API
    print_info "Compiling HC2L routing API..."
    if g++ -std=c++20 -O3 -Wall -Wextra \
        -o "$BUILD_DIR/hc2l/hc2l_routing_api" \
        src/hc2l_routing_api.cpp src/road_network.cpp src/util.cpp; then
        print_success "HC2L routing API compiled"
    else
        print_error "HC2L routing API compilation failed!"
        return 1
    fi

    # Build index executable
    print_info "Compiling HC2L index builder..."
    if g++ -std=c++20 -O3 -Wall -Wextra \
        -o "$BUILD_DIR/hc2l/index" \
        src/index.cpp src/road_network.cpp src/util.cpp; then
        print_success "HC2L index builder compiled"
    else
        print_error "HC2L index builder compilation failed!"
        return 1
    fi
}

generate_data() {
    print_header "Step 2/5: Generating Traffic Data & Network"

    cd "$MAIN_DIR"

    # Generate unified data (base network + 1 scenario)
    print_info "Generating base network and traffic scenario..."
    python3 ../unified_data_generator.py --mode both --scenarios 1 --place "Quezon City, Philippines" || {
        print_error "Data generation failed!"
        return 1
    }

    print_success "Data generation complete"
    print_info "Output files:"
    echo "  - Nodes: $DATA_DIR/raw/quezon_city_nodes.csv"
    echo "  - Edges: $DATA_DIR/raw/quezon_city_edges.csv"
    echo "  - Scenario: $DISRUPTIONS_DIR/qc_scenario_for_cpp_1.csv"
}

build_indexes() {
    print_header "Step 3/5: Building Routing Indexes"

    cd "$MAIN_DIR"

    # Check if graph files exist
    if [ ! -f "$PROCESSED_DATA_DIR/quezon_city.graph" ]; then
        print_warning "Graph file not found. Have you run data generation?"
        return 1
    fi

    # Build DHL index
    # DHL index requires: <input_graph> <output_base_path>
    # Output files: quezon_city_dhl, quezon_city_ch
    print_info "Building DHL index..."
    if "$BUILD_DIR/dhl/index" "$PROCESSED_DATA_DIR/quezon_city.graph" "$PROCESSED_DATA_DIR/quezon_city" 2>&1; then
        print_success "DHL index built"
        print_info "  - DHL index: $PROCESSED_DATA_DIR/quezon_city_dhl"
        print_info "  - CH data:   $PROCESSED_DATA_DIR/quezon_city_ch"
    else
        print_error "DHL index build failed!"
        print_error "Make sure graph file exists: $PROCESSED_DATA_DIR/quezon_city.graph"
        return 1
    fi

    # Build HC2L index
    # HC2L reads from stdin and writes to stdout
    print_info "Building HC2L index..."
    if cat "$PROCESSED_DATA_DIR/quezon_city.graph" | "$BUILD_DIR/hc2l/index" > "$PROCESSED_DATA_DIR/quezon_city.hc2l.index" 2>&1; then
        print_success "HC2L index built"
        print_info "  - HC2L index: $PROCESSED_DATA_DIR/quezon_city.hc2l.index"
    else
        print_error "HC2L index build failed!"
        return 1
    fi

    print_success "All indexes built successfully"
    print_info "Index files created in: $PROCESSED_DATA_DIR/"    # Build HC2L index
    # HC2L reads from stdin and writes to stdout
    # Output file: quezon_city.hc2l.index
    print_info "Building HC2L index..."
    if cat "$PROCESSED_DATA_DIR/quezon_city.graph" | "$BUILD_DIR/hc2l/index" > "$PROCESSED_DATA_DIR/quezon_city.hc2l.index"; then
        print_success "HC2L index built"
        print_info "  - HC2L index: $PROCESSED_DATA_DIR/quezon_city.hc2l.index"
    else
        print_error "HC2L index build failed!"
        return 1
    fi

    print_success "All indexes built successfully"
    print_info "Index files created in: $PROCESSED_DATA_DIR/"
}

run_server() {
    print_header "Step 5/5: Starting Flask Server"

    cd "$MAIN_DIR"

    print_info "Cleaning up any existing processes..."
    pkill -f "flask_server.py" 2>/dev/null || true
    pkill -f "unified_data_generator.py" 2>/dev/null || true
    sleep 1

    print_info "Starting Flask web server..."
    print_info "Server URL: http://localhost:5000"
    print_info "Press Ctrl+C to stop"
    echo ""

    # Start Flask in foreground
    python3 flask_server.py
}

run_full_setup() {
    print_header "DYNAMIC ROAD NETWORK - COMPLETE SETUP"

    # Step 1: Check requirements
    check_requirements

    # Step 2: Build C++ algorithms
    print_header "Step 2/5: Building C++ Algorithms"
    build_dhl || exit 1
    build_hc2l || exit 1
    print_success "All algorithms compiled successfully"

    # Step 3: Generate data
    generate_data || exit 1

    # Step 4: Build indexes
    build_indexes || exit 1

    # Success
    print_header "✓ SETUP COMPLETE!"
    echo -e "${GREEN}The system is ready to use!${NC}\n"
    echo "Next step: Run the server"
    echo -e "  ${GREEN}./setup.sh --server${NC}\n"
}

clean_generated_files() {
    print_header "Cleaning Generated Files"

    print_warning "This will remove all generated data and indexes."
    echo "Files to be removed:"
    echo "  - $DATA_DIR/"
    echo "  - $BUILD_DIR/"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$DATA_DIR"
        rm -rf "$BUILD_DIR"
        print_success "Cleaned successfully"
    else
        print_info "Cleanup cancelled"
    fi
}

show_help() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║   Dynamic Road Network - Complete Setup Script                    ║"
    echo "║   Handles: Build, Data Generation, Index Building, Server Run     ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo ""
    print_menu
    echo -e "Modes:"
    echo -e "  ${YELLOW}--flow${NC}        Use only flow data (no incidents)"
    echo -e "  ${YELLOW}--incidents${NC}   Use only incidents (no flow)"
    echo -e "  ${YELLOW}--both${NC}        Use both flow and incidents (default)"
    echo -e "  ${YELLOW}--synthetic${NC}   Use synthetic data (no HERE API)"
    echo ""
    echo -e "Examples:"
    echo -e "  ${GREEN}./setup.sh --full${NC}              # Complete workflow"
    echo -e "  ${GREEN}./setup.sh --full --flow${NC}       # Build & run with flow data only"
    echo -e "  ${GREEN}./setup.sh --build${NC}             # Compile C++ only"
    echo -e "  ${GREEN}./setup.sh --data --synthetic${NC}  # Generate synthetic data"
    echo ""
}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

# Default mode
MODE="both"
ACTION="menu"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            ACTION="full"
            ;;
        --build)
            ACTION="build"
            ;;
        --data)
            ACTION="data"
            ;;
        --indexes)
            ACTION="indexes"
            ;;
        --server)
            ACTION="server"
            ;;
        --clean)
            ACTION="clean"
            ;;
        --help|-h)
            ACTION="help"
            ;;
        --flow)
            MODE="flow"
            ;;
        --incidents)
            MODE="incidents"
            ;;
        --both)
            MODE="both"
            ;;
        --synthetic)
            MODE="synthetic"
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
    shift
done

# Execute actions
case $ACTION in
    help)
        show_help
        ;;
    full)
        run_full_setup
        ;;
    build)
        check_requirements
        print_header "Building C++ Algorithms"
        build_dhl || exit 1
        build_hc2l || exit 1
        print_success "Build complete"
        ;;
    data)
        mkdir -p "$DATA_DIR/raw" "$PROCESSED_DATA_DIR" "$DISRUPTIONS_DIR"
        cd "$MAIN_DIR"
        python3 ../unified_data_generator.py --mode "$MODE" --scenarios 1 --place "Quezon City, Philippines" || exit 1
        ;;
    indexes)
        build_indexes || exit 1
        ;;
    server)
        run_server
        ;;
    clean)
        clean_generated_files
        ;;
    menu)
        show_help
        ;;
esac

exit 0
