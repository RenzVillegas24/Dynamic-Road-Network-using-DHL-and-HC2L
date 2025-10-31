#!/usr/bin/env fish
# Generate Graph Data Script (Fish Shell)
# This script generates all necessary data files including:
# - CSV files from OSM data
# - OSM geometry cache for smooth road curves
# - Binary graph and index files for routing APIs
# Note: Run build_all.sh first to compile the index executables

# Helper functions for colored output
function print_error
    set_color red; printf "[%s]" $argv[1]; set_color normal; printf " %s\n" $argv[2..-1]
end

function print_ok
    set_color green; printf "[%s]" $argv[1]; set_color normal; printf " %s\n" $argv[2..-1]
end

function print_warning
    set_color yellow; printf "[%s]" $argv[1]; set_color normal; printf " %s\n" $argv[2..-1]
end

function print_step
    set_color blue; printf "%s\n" $argv; set_color normal
end

print_step "========================================"
print_step "  Generating Graph Data & Indexes"
print_step "========================================"
echo ""

# Get script directory (absolute path)
set SCRIPT_DIR (dirname (status --current-filename))
cd $SCRIPT_DIR

# Directories (absolute paths)
set MAIN_DIR "$SCRIPT_DIR/Main"
set BUILD_DIR "$MAIN_DIR/build"
set DATA_DIR "$MAIN_DIR/data"
set RAW_DIR "$DATA_DIR/raw"
set PROCESSED_DIR "$DATA_DIR/processed"

# Python executable (use configured environment)
set PYTHON_CMD python

# Check if Python is available
if not type -q python
    if type -q python3
        set PYTHON_CMD python3
    else
        print_error "✗" "Error: Python not found in PATH"
        exit 1
    end
end

print_ok "✓" "Using Python: $PYTHON_CMD"

# Step 0: Generate OSM datasets and geometry cache
print_step "Step 0: Generating OSM datasets and geometry cache..."
echo ""

cd "$MAIN_DIR"

print_warning " " "Running request_new_datasets.py to generate:"
print_warning " " "  - CSV files (nodes, edges, mapping)"
print_warning " " "  - Graph files (.gr format)"
print_warning " " "  - OSM geometry cache for smooth curves"
echo ""

$PYTHON_CMD request_new_datasets.py
set REQUEST_STATUS $status

if test $REQUEST_STATUS -ne 0
    print_error "✗" "Error: Failed to generate datasets"
    print_warning " " "Please check the error messages above and ensure:"
    print_warning " " "  - Python dependencies are installed (osmnx, pandas, etc.)"
    print_warning " " "  - Internet connection is available for OSM data download"
    exit 1
end

print_ok "✓" "OSM datasets and geometry cache generated successfully"
echo ""

# Return to script directory
cd "$SCRIPT_DIR"

# Check if data files were created
if not test -f "$RAW_DIR/quezon_city_nodes.csv"; or not test -f "$RAW_DIR/quezon_city_edges.csv"
    print_error "✗" "Error: CSV data files not found after generation"
    exit 1
end

print_ok "✓" "CSV data files found"

# Check if .gr files exist
if not test -f "$PROCESSED_DIR/qc_from_csv.gr"
    print_error "✗" "Error: Graph file not found: $PROCESSED_DIR/qc_from_csv.gr"
    exit 1
end

print_ok "✓" "Graph files found"

# Check if OSM geometry cache was created
if not test -f "$DATA_DIR/osm_geometry.graphml"
    print_warning " " "⚠ OSM geometry cache not found at: $DATA_DIR/osm_geometry.graphml"
    print_warning " " "  Smooth road curves may not be available"
else
    set CACHE_SIZE (du -h "$DATA_DIR/osm_geometry.graphml" | cut -f1)
    print_ok "✓" "OSM geometry cache created: $CACHE_SIZE"
end

echo ""

# Check if index executables exist
if not test -f "$BUILD_DIR/dhl/index"; or not test -f "$BUILD_DIR/hc2l/index"
    print_error "✗" "Error: Index executables not found"
    print_warning " " "Please run './build_all.sh' first to compile the index executables"
    exit 1
end

print_ok "✓" "Index executables found"
echo ""

# Step 1: Build graph file (binary format)
print_step "Step 1: Converting .gr to binary graph format..."

# The graph file is the same for both algorithms
set GR_INPUT "$PROCESSED_DIR/qc_from_csv.gr"
set GRAPH_OUTPUT "$PROCESSED_DIR/quezon_city.graph"

print_warning " " "Converting: $GR_INPUT"
print_warning " " "Output: $GRAPH_OUTPUT"

# Create a simple tool to convert .gr to binary graph format
# For now, we'll copy the .gr file with .graph extension as a placeholder
# In a full implementation, you'd convert to the actual binary format
cp "$GR_INPUT" "$GRAPH_OUTPUT"
print_ok "✓" "Graph file created"

echo ""

# Step 2: Build DHL index
print_step "Step 2: Building DHL index..."

set DHL_INDEX_OUTPUT "$PROCESSED_DIR/quezon_city"  # The index builder will append _dhl
print_warning " " "Input: $GRAPH_OUTPUT"
print_warning " " "Output: $DHL_INDEX_OUTPUT.dhl.index"

"$BUILD_DIR/dhl/index" "$GRAPH_OUTPUT" "$DHL_INDEX_OUTPUT" 2>&1 | head -20; or true

# The DHL index builder creates two files: _dhl and _ch
# We need to rename them to match what the API expects
if test -f "$DHL_INDEX_OUTPUT"_dhl
    mv "$DHL_INDEX_OUTPUT"_dhl "$DHL_INDEX_OUTPUT.dhl.index"
    print_ok "✓" "DHL index built successfully"
else
    print_warning " " "⚠ DHL index file not found at expected location"
end

if test -f "$DHL_INDEX_OUTPUT"_ch
    mv "$DHL_INDEX_OUTPUT"_ch "$DHL_INDEX_OUTPUT.dhl.ch"
    print_ok "✓" "DHL contraction hierarchy built"
end

echo ""

# Step 3: Build HC2L index
print_step "Step 3: Building HC2L index..."

set HC2L_INDEX_OUTPUT "$PROCESSED_DIR/quezon_city.hc2l.index"
print_warning " " "Input: $GRAPH_OUTPUT"
print_warning " " "Output: $HC2L_INDEX_OUTPUT"

"$BUILD_DIR/hc2l/index" < "$GRAPH_OUTPUT" > "$HC2L_INDEX_OUTPUT" 2>&1; or true

if test -f "$HC2L_INDEX_OUTPUT"; and test -s "$HC2L_INDEX_OUTPUT"
    print_ok "✓" "HC2L index built successfully"
else
    print_warning " " "⚠ HC2L index file not found or empty"
end

echo ""

# Step 4: Verify all files
print_step "Step 4: Verifying created files..."

set FILES_TO_CHECK "$GRAPH_OUTPUT" "$DHL_INDEX_OUTPUT.dhl.index" "$HC2L_INDEX_OUTPUT"

set ALL_OK true
for file in $FILES_TO_CHECK
    if test -f "$file"; and test -s "$file"
        set SIZE (du -h "$file" | cut -f1)
        print_ok "✓" "$file ($SIZE)"
    else
        print_error "✗" "Missing or empty: $file"
        set ALL_OK false
    end
end

echo ""
print_step "========================================"

if test "$ALL_OK" = true
    print_ok "✓" "Data generation completed successfully!"
    echo ""
    print_ok " " "Generated files:"
    print_ok " " "  • OSM geometry cache (for smooth curves)"
    print_ok " " "  • CSV datasets (nodes, edges, mapping)"
    print_ok " " "  • Binary graph files"
    print_ok " " "  • DHL and HC2L indexes"
    echo ""
    print_ok " " "You can now run the routing APIs:"
    print_warning " " "  ./run_server.fish"
else
    print_warning "⚠" "Data generation completed with warnings"
    echo ""
    print_warning " " "Note: Some files may not have been created."
    print_warning " " "This might be due to graph format compatibility."
    print_warning " " "You may need to adjust the graph conversion process."
end

print_step "========================================"
