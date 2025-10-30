#!/usr/bin/env fish

# Build Graph Indexes Script (Fish Shell)
# This script builds the binary graph and index files needed by the routing APIs

# Colors for output
set RED '\033[0;31m'
set GREEN '\033[0;32m'
set YELLOW '\033[1;33m'
set BLUE '\033[0;34m'
set NC '\033[0m' # No Color

echo -e "$BLUE========================================$NC"
echo -e "$BLUE  Building Graph Indexes$NC"
echo -e "$BLUE========================================$NC"
echo ""

# Get script directory (absolute path)
set SCRIPT_DIR (cd (dirname (status --current-filename)); and pwd)
cd $SCRIPT_DIR

# Directories (absolute paths)
set DHL_DIR "$SCRIPT_DIR/DualHierarchyLabelling"
set HC2L_DIR "$SCRIPT_DIR/HighCardinalityTwoLevel"
set DATA_DIR "$SCRIPT_DIR/Main/data"
set RAW_DIR "$DATA_DIR/raw"
set PROCESSED_DIR "$DATA_DIR/processed"

# Check if data files exist
if not test -f "$RAW_DIR/quezon_city_nodes.csv"; or not test -f "$RAW_DIR/quezon_city_edges.csv"
    echo -e "$RED✗ Error: CSV data files not found$NC"
    echo -e "$YELLOW  Please run 'request_new_datasets.py' first to generate data files$NC"
    exit 1
end

echo -e "$GREEN✓ CSV data files found$NC"

# Check if .gr files exist
if not test -f "$PROCESSED_DIR/qc_from_csv.gr"
    echo -e "$RED✗ Error: Graph file not found: $PROCESSED_DIR/qc_from_csv.gr$NC"
    echo -e "$YELLOW  Please run 'request_new_datasets.py' first to generate .gr files$NC"
    exit 1
end

echo -e "$GREEN✓ Graph files found$NC"
echo ""

# Step 1: Build index executables
echo -e "$BLUE""Step 1: Building index executables...$NC"

echo -e "$YELLOW  Building DHL index executable...$NC"
cd $DHL_DIR
make index 2>&1 | grep -E "g\\+\\+|error|warning" || true
if not test -f "index"
    echo -e "$RED✗ Failed to build DHL index$NC"
    exit 1
end
echo -e "$GREEN  ✓ DHL index executable built$NC"
cd $SCRIPT_DIR

echo -e "$YELLOW  Building HC2L index executable...$NC"
cd $HC2L_DIR
make index 2>&1 | grep -E "g\\+\\+|error|warning" || true
if not test -f "index"
    echo -e "$RED✗ Failed to build HC2L index$NC"
    exit 1
end
echo -e "$GREEN  ✓ HC2L index executable built$NC"
cd $SCRIPT_DIR

echo ""

# Step 2: Build graph file (binary format)
echo -e "$BLUE""Step 2: Converting .gr to binary graph format...$NC"

set GR_INPUT "$PROCESSED_DIR/qc_from_csv.gr"
set GRAPH_OUTPUT "$PROCESSED_DIR/quezon_city.graph"

echo -e "$YELLOW  Converting: $GR_INPUT$NC"
echo -e "$YELLOW  Output: $GRAPH_OUTPUT$NC"

cp $GR_INPUT $GRAPH_OUTPUT
echo -e "$GREEN  ✓ Graph file created$NC"

echo ""

# Step 3: Build DHL index
echo -e "$BLUE""Step 3: Building DHL index...$NC"

set DHL_INDEX_OUTPUT "$PROCESSED_DIR/quezon_city"
echo -e "$YELLOW  Input: $GRAPH_OUTPUT$NC"
echo -e "$YELLOW  Output: $DHL_INDEX_OUTPUT.dhl.index$NC"

cd $DHL_DIR
./index "$GRAPH_OUTPUT" "$DHL_INDEX_OUTPUT" 2>&1 | head -20 || true

if test -f "$DHL_INDEX_OUTPUT"_dhl
    mv "$DHL_INDEX_OUTPUT"_dhl "$DHL_INDEX_OUTPUT.dhl.index"
    echo -e "$GREEN  ✓ DHL index built successfully$NC"
else
    echo -e "$YELLOW  ⚠ DHL index file not found at expected location$NC"
end

if test -f "$DHL_INDEX_OUTPUT"_ch
    mv "$DHL_INDEX_OUTPUT"_ch "$DHL_INDEX_OUTPUT.dhl.ch"
    echo -e "$GREEN  ✓ DHL contraction hierarchy built$NC"
end

cd $SCRIPT_DIR
echo ""

# Step 4: Build HC2L index
echo -e "$BLUE""Step 4: Building HC2L index...$NC"

set HC2L_INDEX_OUTPUT "$PROCESSED_DIR/quezon_city.hc2l.index"
echo -e "$YELLOW  Input: $GRAPH_OUTPUT$NC"
echo -e "$YELLOW  Output: $HC2L_INDEX_OUTPUT$NC"

cd $HC2L_DIR
./index < "$GRAPH_OUTPUT" > "$HC2L_INDEX_OUTPUT" 2>&1 || true

if test -f "$SCRIPT_DIR/$HC2L_INDEX_OUTPUT"; and test -s "$SCRIPT_DIR/$HC2L_INDEX_OUTPUT"
    echo -e "$GREEN  ✓ HC2L index built successfully$NC"
else
    echo -e "$YELLOW  ⚠ HC2L index file not found or empty$NC"
end

cd $SCRIPT_DIR
echo ""

# Step 5: Verify all files
echo -e "$BLUE""Step 5: Verifying created files...$NC"

set ALL_OK true

for file in $GRAPH_OUTPUT "$DHL_INDEX_OUTPUT.dhl.index" $HC2L_INDEX_OUTPUT
    if test -f $file; and test -s $file
        set SIZE (du -h $file | cut -f1)
        echo -e "$GREEN  ✓ $file ($SIZE)$NC"
    else
        echo -e "$RED  ✗ Missing or empty: $file$NC"
        set ALL_OK false
    end
end

echo ""
echo -e "$BLUE========================================$NC"

if test $ALL_OK = true
    echo -e "$GREEN✓ Index building completed successfully!$NC"
    echo ""
    echo -e "$GREEN""You can now run the routing APIs:$NC"
    echo -e "  $YELLOW./run_server.sh$NC or $YELLOW./run_server.fish$NC"
else
    echo -e "$YELLOW⚠ Index building completed with warnings$NC"
    echo ""
    echo -e "$YELLOW""Note: Some index files may not have been created.$NC"
    echo -e "$YELLOW""This might be due to graph format compatibility.$NC"
    echo -e "$YELLOW""You may need to adjust the graph conversion process.$NC"
end

echo -e "$BLUE========================================$NC"
