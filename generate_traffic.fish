#!/usr/bin/env fish
#
# Generate real-time traffic data using hash-based matching
# Usage:
#   ./generate_traffic.fish flow          # Generate one snapshot
#   ./generate_traffic.fish both          # Flow + incidents
#   ./generate_traffic.fish flow --live   # Continuous updates every 60s
#

set -l script_dir (dirname (status --current-filename))
set -l python_exe "$script_dir/.conda/bin/python"

# Check arguments
if test (count $argv) -eq 0
    echo "Usage: ./generate_traffic.fish <mode> [--live]"
    echo ""
    echo "Modes:"
    echo "  flow       - Traffic flow data only"
    echo "  incidents  - Incidents only"
    echo "  both       - Flow + incidents"
    echo ""
    echo "Options:"
    echo "  --live     - Continuous updates every 60s (Ctrl+C to stop)"
    exit 1
end

set -l mode $argv[1]
set -l continuous ""

# Check for --live flag
if test (count $argv) -ge 2; and test "$argv[2]" = "--live"
    set continuous "--continuous --interval 60"
end

echo "🚀 Starting Traffic Data Generator"
echo "   Mode: $mode"
if test -n "$continuous"
    echo "   Mode: Continuous (60s intervals)"
else
    echo "   Mode: Single snapshot"
end
echo ""

# Run the generator
$python_exe unified_data_generator_v2.py --mode $mode $continuous
