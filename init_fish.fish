#!/usr/bin/env fish
# Quick setup guide for Dynamic Road Network project
# Run this to set up your terminal session

echo "Dynamic Road Network - Setup Helper"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Store the directory where this script is located
set -l SCRIPT_DIR (cd (dirname (status --current-filename)); pwd)
set -l PROJECT_ROOT $SCRIPT_DIR

echo "Project Root: $PROJECT_ROOT"
echo ""

# Function to activate the project environment
function activate_env
    echo "Activating project conda environment..."
    conda activate "$PROJECT_ROOT/.conda"
    echo "✓ Environment activated"
    echo ""
    echo "You can now use:"
    echo "  ./run_server.fish     - Start the Flask server"
    echo "  ./generate_indexes.sh - Generate graph indexes"
    echo "  ./build_all.sh        - Build all executables"
    echo ""
end

# Check if the conda environment exists
if test -d "$PROJECT_ROOT/.conda"
    echo "Found conda environment at .conda/"
    echo ""
    read -l -P "Activate the project environment now? [y/N]: " response
    if string match -qi "y" $response
        activate_env
    else
        echo "To activate manually later, run:"
        echo "  source (conda info --base)/etc/fish/conf.d/conda.fish"
        echo "  conda activate .conda"
    end
else
    echo "⚠ Conda environment not found at .conda/"
    echo "Run setup.sh first to create the environment"
end
