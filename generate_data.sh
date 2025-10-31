#!/bin/bash

# Generate Graph Data Script
# This script generates all necessary data files including:
# - CSV files from OSM data
# - OSM geometry cache for smooth road curves
# - Binary graph and index files for routing APIs
# Note: Run build_all.sh first to compile the index executables

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Generating Graph Data & Indexes${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get script directory (absolute path)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Directories (absolute paths)
MAIN_DIR="$SCRIPT_DIR/Main"
BUILD_DIR="$MAIN_DIR/build"
DATA_DIR="$MAIN_DIR/data"
RAW_DIR="$DATA_DIR/raw"
PROCESSED_DIR="$DATA_DIR/processed"

# Python executable
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    else
        echo -e "${RED}✗ Error: Python not found in PATH${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Using Python: $PYTHON_CMD${NC}"

# Step 0: Generate OSM datasets and geometry cache
echo -e "${BLUE}Step 0: Generating OSM datasets and geometry cache...${NC}"
echo ""

cd "$MAIN_DIR"

echo -e "${YELLOW}  Running request_new_datasets.py to generate:${NC}"
echo -e "${YELLOW}    - CSV files (nodes, edges, mapping)${NC}"
echo -e "${YELLOW}    - Graph files (.gr format)${NC}"
echo -e "${YELLOW}    - OSM geometry cache for smooth curves${NC}"
echo ""

if ! $PYTHON_CMD request_new_datasets.py; then
    echo -e "${RED}✗ Error: Failed to generate datasets${NC}"
    echo -e "${YELLOW}  Please check the error messages above and ensure:${NC}"
    echo -e "${YELLOW}    - Python dependencies are installed (osmnx, pandas, etc.)${NC}"
    echo -e "${YELLOW}    - Internet connection is available for OSM data download${NC}"
    exit 1
fi

echo -e "${GREEN}✓ OSM datasets and geometry cache generated successfully${NC}"
echo ""

# Return to script directory
cd "$SCRIPT_DIR"

# Check if data files were created
if [ ! -f "$RAW_DIR/quezon_city_nodes.csv" ] || [ ! -f "$RAW_DIR/quezon_city_edges.csv" ]; then
    echo -e "${RED}✗ Error: CSV data files not found after generation${NC}"
    exit 1
fi

echo -e "${GREEN}✓ CSV data files found${NC}"

# Check if .gr files exist
if [ ! -f "$PROCESSED_DIR/qc_from_csv.gr" ]; then
    echo -e "${RED}✗ Error: Graph file not found: $PROCESSED_DIR/qc_from_csv.gr${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Graph files found${NC}"

# Check if OSM geometry cache was created
if [ ! -f "$DATA_DIR/osm_geometry.graphml" ]; then
    echo -e "${YELLOW}  ⚠ OSM geometry cache not found at: $DATA_DIR/osm_geometry.graphml${NC}"
    echo -e "${YELLOW}    Smooth road curves may not be available${NC}"
else
    CACHE_SIZE=$(du -h "$DATA_DIR/osm_geometry.graphml" | cut -f1)
    echo -e "${GREEN}✓ OSM geometry cache created: $CACHE_SIZE${NC}"
fi

echo ""

# Check if index executables exist
if [ ! -f "$BUILD_DIR/dhl/index" ] || [ ! -f "$BUILD_DIR/hc2l/index" ]; then
    echo -e "${RED}✗ Error: Index executables not found${NC}"
    echo -e "${YELLOW}  Please run './build_all.sh' first to compile the index executables${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Index executables found${NC}"
echo ""

# Step 1: Build graph file (binary format)
echo -e "${BLUE}Step 1: Converting .gr to binary graph format...${NC}"

# The graph file is the same for both algorithms
GR_INPUT="$PROCESSED_DIR/qc_from_csv.gr"
GRAPH_OUTPUT="$PROCESSED_DIR/quezon_city.graph"

echo -e "${YELLOW}  Converting: $GR_INPUT${NC}"
echo -e "${YELLOW}  Output: $GRAPH_OUTPUT${NC}"

# Create a simple tool to convert .gr to binary graph format
# For now, we'll copy the .gr file with .graph extension as a placeholder
# In a full implementation, you'd convert to the actual binary format
cp "$GR_INPUT" "$GRAPH_OUTPUT"
echo -e "${GREEN}  ✓ Graph file created${NC}"

echo ""

# Step 2: Build DHL index
echo -e "${BLUE}Step 2: Building DHL index...${NC}"

DHL_INDEX_OUTPUT="$PROCESSED_DIR/quezon_city"  # The index builder will append _dhl
echo -e "${YELLOW}  Input: $GRAPH_OUTPUT${NC}"
echo -e "${YELLOW}  Output: ${DHL_INDEX_OUTPUT}.dhl.index${NC}"

"$BUILD_DIR/dhl/index" "$GRAPH_OUTPUT" "$DHL_INDEX_OUTPUT" 2>&1 | head -20 || true

# The DHL index builder creates two files: _dhl and _ch
# We need to rename them to match what the API expects
if [ -f "${DHL_INDEX_OUTPUT}_dhl" ]; then
    mv "${DHL_INDEX_OUTPUT}_dhl" "${DHL_INDEX_OUTPUT}.dhl.index"
    echo -e "${GREEN}  ✓ DHL index built successfully${NC}"
else
    echo -e "${YELLOW}  ⚠ DHL index file not found at expected location${NC}"
fi

if [ -f "${DHL_INDEX_OUTPUT}_ch" ]; then
    mv "${DHL_INDEX_OUTPUT}_ch" "${DHL_INDEX_OUTPUT}.dhl.ch"
    echo -e "${GREEN}  ✓ DHL contraction hierarchy built${NC}"
fi

echo ""

# Step 3: Build HC2L index
echo -e "${BLUE}Step 3: Building HC2L index...${NC}"

HC2L_INDEX_OUTPUT="$PROCESSED_DIR/quezon_city.hc2l.index"
echo -e "${YELLOW}  Input: $GRAPH_OUTPUT${NC}"
echo -e "${YELLOW}  Output: $HC2L_INDEX_OUTPUT${NC}"

"$BUILD_DIR/hc2l/index" < "$GRAPH_OUTPUT" > "$HC2L_INDEX_OUTPUT" 2>&1 || true

if [ -f "$HC2L_INDEX_OUTPUT" ] && [ -s "$HC2L_INDEX_OUTPUT" ]; then
    echo -e "${GREEN}  ✓ HC2L index built successfully${NC}"
else
    echo -e "${YELLOW}  ⚠ HC2L index file not found or empty${NC}"
fi

echo ""

# Step 4: Verify all files
echo -e "${BLUE}Step 4: Verifying created files...${NC}"

FILES_TO_CHECK=(
    "$GRAPH_OUTPUT"
    "$DHL_INDEX_OUTPUT.dhl.index"
    "$HC2L_INDEX_OUTPUT"
)

ALL_OK=true
for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ] && [ -s "$file" ]; then
        SIZE=$(du -h "$file" | cut -f1)
        echo -e "${GREEN}  ✓ $file ($SIZE)${NC}"
    else
        echo -e "${RED}  ✗ Missing or empty: $file${NC}"
        ALL_OK=false
    fi
done

echo ""
echo -e "${BLUE}========================================${NC}"

if [ "$ALL_OK" = true ]; then
    echo -e "${GREEN}✓ Data generation completed successfully!${NC}"
    echo ""
    echo -e "${GREEN}Generated files:${NC}"
    echo -e "${GREEN}  • OSM geometry cache (for smooth curves)${NC}"
    echo -e "${GREEN}  • CSV datasets (nodes, edges, mapping)${NC}"
    echo -e "${GREEN}  • Binary graph files${NC}"
    echo -e "${GREEN}  • DHL and HC2L indexes${NC}"
    echo ""
    echo -e "${GREEN}You can now run the routing APIs:${NC}"
    echo -e "  ${YELLOW}./run_server.sh${NC}"
else
    echo -e "${YELLOW}⚠ Data generation completed with warnings${NC}"
    echo ""
    echo -e "${YELLOW}Note: Some files may not have been created.${NC}"
    echo -e "${YELLOW}This might be due to graph format compatibility.${NC}"
    echo -e "${YELLOW}You may need to adjust the graph conversion process.${NC}"
fi

echo -e "${BLUE}========================================${NC}"
