#!/bin/bash
# Build script for Dynamic Road Network algorithms
# This script compiles both DHL and HC2L routing APIs

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
MAIN_DIR="$PROJECT_ROOT/Main"
BUILD_DIR="$MAIN_DIR/build"

echo "🔨 Building Dynamic Road Network - All Executables"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create build directories
echo "📁 Creating build directories..."
mkdir -p "$BUILD_DIR/dhl"
mkdir -p "$BUILD_DIR/hc2l"

# Check if g++ is available
if ! command -v g++ &> /dev/null; then
    echo "❌ Error: g++ compiler not found!"
    echo ""
    echo "Please install g++ (build-essential):"
    echo "  Ubuntu/Debian: sudo apt-get install build-essential"
    echo "  Fedora: sudo dnf install gcc-c++"
    echo "  macOS: xcode-select --install"
    exit 1
fi

# Build DHL Routing API
echo ""
echo "🏗️  Building DHL (Dual-Hierarchy Labelling) Routing API..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/DualHierarchyLabelling"

# Compile directly to Main/build/dhl/
if g++ -std=c++2a -O3 -Wall -Wextra -pthread -o "$BUILD_DIR/dhl/dhl_routing_api" \
    src/dhl_routing_api.cpp src/road_network.cpp src/util.cpp; then
    echo "✅ DHL compilation successful!"
    echo "📦 DHL executable created at: $BUILD_DIR/dhl/dhl_routing_api"
else
    echo "❌ DHL compilation failed!"
    exit 1
fi

# Build HC2L Routing API
echo ""
echo "🏗️  Building HC2L (Hierarchical Cut 2-Hop Labelling) Routing API..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/HierarchicalCutLabelling"

# Compile directly to Main/build/hc2l/
if g++ -std=c++20 -O3 -Wall -Wextra -o "$BUILD_DIR/hc2l/hc2l_routing_api" \
    src/hc2l_routing_api.cpp src/road_network.cpp src/util.cpp; then
    echo "✅ HC2L compilation successful!"
    echo "📦 HC2L executable created at: $BUILD_DIR/hc2l/hc2l_routing_api"
else
    echo "❌ HC2L compilation failed!"
    exit 1
fi

# Build DHL Index Executable
echo ""
echo "🏗️  Building DHL Index Executable..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/DualHierarchyLabelling"

# Compile directly to Main/build/dhl/
if g++ -std=c++2a -O3 -Wall -Wextra -pthread -o "$BUILD_DIR/dhl/index" \
    src/index.cpp src/road_network.cpp src/util.cpp; then
    echo "✅ DHL index executable built!"
    echo "📦 Executable created at: $BUILD_DIR/dhl/index"
else
    echo "❌ DHL index compilation failed!"
    exit 1
fi

# Build HC2L Index Executable
echo ""
echo "🔧 Building HC2L Index Executable..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/HierarchicalCutLabelling"

# Compile directly to Main/build/hc2l/
if g++ -std=c++20 -O3 -Wall -Wextra -o "$BUILD_DIR/hc2l/index" \
    src/index.cpp src/road_network.cpp src/util.cpp; then
    echo "✅ HC2L index executable built!"
    echo "📦 Executable created at: $BUILD_DIR/hc2l/index"
else
    echo "❌ HC2L index compilation failed!"
    exit 1
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Build Complete!"
echo ""
echo "Routing API Executables:"
echo "  📍 DHL:  $BUILD_DIR/dhl/dhl_routing_api"
echo "  📍 HC2L: $BUILD_DIR/hc2l/hc2l_routing_api"
echo ""
echo "Index Builder Executables:"
echo "  📍 DHL:  $BUILD_DIR/dhl/index"
echo "  📍 HC2L: $BUILD_DIR/hc2l/index"
echo ""
echo "Next steps:"
echo "  1. Generate data: cd Main && python request_new_datasets.py"
echo "  2. Build indexes: ./generate_data.sh"
echo "  3. Run server: ./run_server.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
