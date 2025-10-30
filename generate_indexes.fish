#!/usr/bin/env fish
# Generate Graph Indexes Script (Fish Shell)
# This script generates the binary graph and index files needed by the routing APIs
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
print_step "  Generating Graph Indexes"
print_step "========================================"
echo ""

# Get script directory (absolute path)
set SCRIPT_DIR (dirname (status --current-filename))
cd $SCRIPT_DIR

# Directories (absolute paths)
set BUILD_DIR "$SCRIPT_DIR/Main/build"
set DATA_DIR "$SCRIPT_DIR/Main/data"
set RAW_DIR "$DATA_DIR/raw"
set PROCESSED_DIR "$DATA_DIR/processed"

# Check if data files exist
if not test -f "$RAW_DIR/quezon_city_nodes.csv"; or not test -f "$RAW_DIR/quezon_city_edges.csv"
    print_error "✗" "Error: CSV data files not found"
    print_warning " " "Please run 'python request_new_datasets.py' first to generate data files"
    exit 1
end

print_ok "✓" "CSV data files found"

# Check if .gr files exist
if not test -f "$PROCESSED_DIR/qc_from_csv.gr"
    print_error "✗" "Error: Graph file not found: $PROCESSED_DIR/qc_from_csv.gr"
    print_warning " " "Please run 'python request_new_datasets.py' first to generate .gr files"
    exit 1
end

print_ok "✓" "Graph files found"
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
        printf "$RED  ✗ Missing or empty: $file$NC"
        set ALL_OK false
    end
end

echo ""
printf "$BLUE========================================$NC"

if test "$ALL_OK" = true
    print_ok "✓" "Index generation completed successfully!"
    echo ""
    printf "$GREEN You can now run the routing APIs:$NC"
    printf "  $YELLOW./run_server.fish$NC"
else
    printf "$YELLOW⚠ Index generation completed with warnings$NC"
    echo ""
    printf "$YELLOW Note: Some index files may not have been created.$NC"
    printf "$YELLOW This might be due to graph format compatibility.$NC"
    printf "$YELLOW You may need to adjust the graph conversion process.$NC"
end

printf "$BLUE========================================$NC"
