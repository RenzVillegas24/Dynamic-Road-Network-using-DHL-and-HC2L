#!/usr/bin/env fish
# Build script for Dynamic Road Network algorithms
# This script compiles both DHL and HC2L routing APIs

set SCRIPT_DIR (dirname (status --current-filename))
set PROJECT_ROOT (cd "$SCRIPT_DIR/.." && pwd)
set MAIN_DIR "$PROJECT_ROOT/Main"
set BUILD_DIR "$MAIN_DIR/build"

echo "🔨 Building Dynamic Road Network Routing APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create build directories
echo "📁 Creating build directories..."
mkdir -p "$BUILD_DIR/dhl"
mkdir -p "$BUILD_DIR/hc2l"

# Build DHL Routing API
echo ""
echo "🏗️  Building DHL (Dual-Hierarchy Labelling) Routing API..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/DualHierarchyLabelling"

if make dhl_routing_api
    echo "✅ DHL compilation successful!"
    
    # Copy executable to Main/build/dhl/
    cp dhl_routing_api "$BUILD_DIR/dhl/"
    echo "📦 Copied DHL executable to: $BUILD_DIR/dhl/dhl_routing_api"
else
    echo "❌ DHL compilation failed!"
    exit 1
end

# Build HC2L Routing API
echo ""
echo "🏗️  Building HC2L (High-Cardinality Two-Level) Routing API..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/HighCardinalityTwoLevel"

if make hc2l_routing_api
    echo "✅ HC2L compilation successful!"
    
    # Copy executable to Main/build/hc2l/
    cp hc2l_routing_api "$BUILD_DIR/hc2l/"
    echo "📦 Copied HC2L executable to: $BUILD_DIR/hc2l/hc2l_routing_api"
else
    echo "❌ HC2L compilation failed!"
    exit 1
end

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Build Complete!"
echo ""
echo "Executables are located in:"
echo "  📍 DHL:  $BUILD_DIR/dhl/dhl_routing_api"
echo "  📍 HC2L: $BUILD_DIR/hc2l/hc2l_routing_api"
echo ""
echo "You can now run the Flask application:"
echo "  cd $MAIN_DIR"
echo "  python flask_server.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
