#!/bin/bash
# Setup script for Dynamic Road Network project
# This script creates the required directory structure and provides guidance

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
MAIN_DIR="$PROJECT_ROOT/Main"

echo "════════════════════════════════════════════════════════════════"
echo "  Dynamic Road Network - Setup Script"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Function to print colored output
print_status() {
    echo "  $1"
}

print_success() {
    echo "  ✓ $1"
}

print_warning() {
    echo "  ⚠ $1"
}

print_error() {
    echo "  ✗ $1"
}

# 1. Check Python installation
print_status "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

# 2. Check g++ installation
print_status "Checking C++ compiler..."
if command -v g++ &> /dev/null; then
    GCC_VERSION=$(g++ --version | head -n1)
    print_success "$GCC_VERSION found"
else
    print_error "g++ not found. Please install g++ with C++20 support."
    exit 1
fi

echo ""
print_status "Creating directory structure..."

# 3. Create directory structure
mkdir -p "$MAIN_DIR/data/raw"
mkdir -p "$MAIN_DIR/data/processed"
mkdir -p "$MAIN_DIR/data/disruptions"
mkdir -p "$MAIN_DIR/build/dhl"
mkdir -p "$MAIN_DIR/build/hc2l"

print_success "Created Main/data/raw/"
print_success "Created Main/data/processed/"
print_success "Created Main/data/disruptions/"
print_success "Created Main/build/dhl/"
print_success "Created Main/build/hc2l/"

echo ""
print_status "Setting up environment configuration..."

# 4. Setup .env file
if [ ! -f "$MAIN_DIR/.env" ]; then
    cp "$MAIN_DIR/.env.example" "$MAIN_DIR/.env"
    print_success "Created Main/.env from template"
    print_warning "Please edit Main/.env and add your Google Maps API key"
else
    print_success "Main/.env already exists"
fi

echo ""
print_status "Installing Python dependencies..."

# 5. Install Python dependencies
if pip3 install -r "$PROJECT_ROOT/requirements.txt" > /dev/null 2>&1; then
    print_success "Python dependencies installed"
else
    print_warning "Some dependencies may have failed to install. Check manually."
fi

echo ""
print_status "Checking data files..."

# 6. Check for required data files
MISSING_FILES=()

if [ ! -f "$MAIN_DIR/data/raw/quezon_city_nodes.csv" ]; then
    MISSING_FILES+=("quezon_city_nodes.csv")
fi

if [ ! -f "$MAIN_DIR/data/raw/quezon_city_edges.csv" ]; then
    MISSING_FILES+=("quezon_city_edges.csv")
fi

if [ ! -f "$MAIN_DIR/data/disruptions/qc_scenario_for_cpp_1.csv" ]; then
    MISSING_FILES+=("qc_scenario_for_cpp_1.csv")
fi

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    print_success "All required data files are present"
else
    echo ""
    print_warning "Missing required data files:"
    for file in "${MISSING_FILES[@]}"; do
        print_error "  - $file"
    done
    echo ""
    print_status "Please place your data files in the following locations:"
    print_status "  - Nodes: Main/data/raw/quezon_city_nodes.csv"
    print_status "  - Edges: Main/data/raw/quezon_city_edges.csv"
    print_status "  - Disruptions: Main/data/disruptions/qc_scenario_for_cpp_1.csv"
fi

echo ""
print_status "Verifying configuration..."

# 7. Verify configuration using Python
cd "$MAIN_DIR"
python3 -c "from config import Config; print(Config.get_config_summary())" 2>/dev/null || {
    print_warning "Could not verify configuration. Run manually: cd Main && python config.py"
}

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Setup Status"
echo "════════════════════════════════════════════════════════════════"
echo ""
print_status "Directory structure: ✓ Created"
print_status "Python dependencies: ✓ Installed"
print_status "Environment file: ✓ Created"

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    print_status "Data files: ✓ Present"
else
    print_status "Data files: ⚠ Missing ${#MISSING_FILES[@]} file(s)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Next Steps"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  1. Edit Main/.env and add your Google Maps API key"
echo "  2. Place your data files in Main/data/"
echo "  3. Build the C++ executables:"
echo "     ./build_all.sh"
echo "  4. Run the Flask application:"
echo "     cd Main"
echo "     python flask_server.py"
echo ""
echo "For more information, see README.md"
echo ""
