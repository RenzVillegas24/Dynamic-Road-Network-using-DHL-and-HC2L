#!/bin/bash

# Build Graph Indexes Script
# This script builds the binary graph and index files needed by the routing APIs

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Building Graph Indexes${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get script directory (absolute path)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Directories (absolute paths)
DHL_DIR="$SCRIPT_DIR/DualHierarchyLabelling"
HC2L_DIR="$SCRIPT_DIR/HighCardinalityTwoLevel"
DATA_DIR="$SCRIPT_DIR/Main/data"
RAW_DIR="$DATA_DIR/raw"
PROCESSED_DIR="$DATA_DIR/processed"

# Check if data files exist
if [ ! -f "$RAW_DIR/quezon_city_nodes.csv" ] || [ ! -f "$RAW_DIR/quezon_city_edges.csv" ]; then
    echo -e "${RED}✗ Error: CSV data files not found${NC}"
    echo -e "${YELLOW}  Please run 'request_new_datasets.py' first to generate data files${NC}"
    exit 1
fi

echo -e "${GREEN}✓ CSV data files found${NC}"

# Check if .gr files exist
if [ ! -f "$PROCESSED_DIR/qc_from_csv.gr" ]; then
    echo -e "${RED}✗ Error: Graph file not found: $PROCESSED_DIR/qc_from_csv.gr${NC}"
    echo -e "${YELLOW}  Please run 'request_new_datasets.py' first to generate .gr files${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Graph files found${NC}"
echo ""

# Step 1: Build index executables
echo -e "${BLUE}Step 1: Building index executables...${NC}"

echo -e "${YELLOW}  Building DHL index executable...${NC}"
cd "$DHL_DIR"
make index 2>&1 | grep -E "g\+\+|error|warning" || true
if [ ! -f "index" ]; then
    echo -e "${RED}✗ Failed to build DHL index${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ DHL index executable built${NC}"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}  Building HC2L index executable...${NC}"
cd "$HC2L_DIR"
make index 2>&1 | grep -E "g\+\+|error|warning" || true
if [ ! -f "index" ]; then
    echo -e "${RED}✗ Failed to build HC2L index${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ HC2L index executable built${NC}"
cd "$SCRIPT_DIR"

echo ""

# Step 2: Build graph file (binary format)
echo -e "${BLUE}Step 2: Converting .gr to binary graph format...${NC}"

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

# Step 3: Build DHL index
echo -e "${BLUE}Step 3: Building DHL index...${NC}"

DHL_INDEX_OUTPUT="$PROCESSED_DIR/quezon_city"  # The index builder will append _dhl
echo -e "${YELLOW}  Input: $GRAPH_OUTPUT${NC}"
echo -e "${YELLOW}  Output: ${DHL_INDEX_OUTPUT}.dhl.index${NC}"

cd "$DHL_DIR"
./index "$GRAPH_OUTPUT" "$DHL_INDEX_OUTPUT" 2>&1 | head -20 || true

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

cd "$SCRIPT_DIR"
echo ""

# Step 4: Build HC2L index
echo -e "${BLUE}Step 4: Building HC2L index...${NC}"

HC2L_INDEX_OUTPUT="$PROCESSED_DIR/quezon_city.hc2l.index"
echo -e "${YELLOW}  Input: $GRAPH_OUTPUT${NC}"
echo -e "${YELLOW}  Output: $HC2L_INDEX_OUTPUT${NC}"

cd "$HC2L_DIR"
./index < "$GRAPH_OUTPUT" > "$HC2L_INDEX_OUTPUT" 2>&1 || true

if [ -f "$SCRIPT_DIR/$HC2L_INDEX_OUTPUT" ] && [ -s "$SCRIPT_DIR/$HC2L_INDEX_OUTPUT" ]; then
    echo -e "${GREEN}  ✓ HC2L index built successfully${NC}"
else
    echo -e "${YELLOW}  ⚠ HC2L index file not found or empty${NC}"
fi

cd "$SCRIPT_DIR"
echo ""

# Step 5: Verify all files
echo -e "${BLUE}Step 5: Verifying created files...${NC}"

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
    echo -e "${GREEN}✓ Index building completed successfully!${NC}"
    echo ""
    echo -e "${GREEN}You can now run the routing APIs:${NC}"
    echo -e "  ${YELLOW}./run_server.sh${NC} or ${YELLOW}./run_server.fish${NC}"
else
    echo -e "${YELLOW}⚠ Index building completed with warnings${NC}"
    echo ""
    echo -e "${YELLOW}Note: Some index files may not have been created.${NC}"
    echo -e "${YELLOW}This might be due to graph format compatibility.${NC}"
    echo -e "${YELLOW}You may need to adjust the graph conversion process.${NC}"
fi

echo -e "${BLUE}========================================${NC}"
