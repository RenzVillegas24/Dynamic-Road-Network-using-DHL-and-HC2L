#!/bin/bash
# All-in-One Setup Script for Dynamic Road Network (Linux/macOS)
# Supports both automatic and manual setup with conda environment

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
MAIN_DIR="$PROJECT_ROOT/Main"
ENV_NAME="roadnet"
CONDA_ENV_PATH="$PROJECT_ROOT/.conda"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Main Menu
main_menu() {
    clear
    echo ""
    echo "  Dynamic Road Network - Setup Script"
    echo ""
    echo ""
    echo "Choose setup mode:"
    echo "  1. Automatic Setup (Recommended - Does everything)"
    echo "  2. Manual Setup (Step by step)"
    echo "  3. Exit"
    echo ""
    read -p "Enter your choice (1-3): " setup_mode
    echo ""

    case $setup_mode in
        1) auto_setup ;;
        2) manual_menu ;;
        3) exit 0 ;;
        *) echo "Invalid choice."; sleep 2; main_menu ;;
    esac
}

# 
# AUTOMATIC SETUP
# 
auto_setup() {
    clear
    echo ""
    echo "  AUTOMATIC SETUP MODE"
    echo ""
    echo ""
    echo "This will automatically:"
    echo "  [1] Check prerequisites (Python, Conda, g++)"
    echo "  [2] Create conda environment with all dependencies"
    echo "  [3] Create directory structure"
    echo "  [4] Setup .env configuration"
    echo "  [5] Build C++ executables"
    echo "  [6] Optionally generate data and indexes"
    echo ""
    read -p "Press Enter to continue..."
    echo ""

    check_prerequisites || return 1
    create_conda_env || return 1
    create_directories
    setup_env_file
    build_executables

    echo ""
    read -p "Generate OSM data and build indexes now? (y/n): " gen_data
    if [[ "$gen_data" =~ ^[Yy]$ ]]; then
        generate_data
    fi

    echo ""
    echo ""
    echo "  AUTOMATIC SETUP COMPLETE!"
    echo ""
    echo ""
    echo "Your environment is ready! To start:"
    echo "  1. Activate: conda activate .conda"
    echo "  2. Run: ./run_server.sh"
    echo ""
    read -p "Press Enter to exit..."
    exit 0
}

# 
# MANUAL SETUP MENU
# 
manual_menu() {
    while true; do
        clear
        echo ""
        echo "  MANUAL SETUP MODE"
        echo ""
        echo ""
        echo "Choose an option:"
        echo "  1. Create/Update Conda Environment"
        echo "  2. Create Directory Structure"
        echo "  3. Setup .env Configuration"
        echo "  4. Build C++ Executables"
        echo "  5. Generate Data and Indexes"
        echo "  6. Check Installation Status"
        echo "  7. Back to Main Menu"
        echo ""
        read -p "Enter your choice (1-7): " manual_choice
        echo ""

        case $manual_choice in
            1) create_conda_env; read -p "Press Enter to continue..." ;;
            2) create_directories; read -p "Press Enter to continue..." ;;
            3) setup_env_file; read -p "Press Enter to continue..." ;;
            4) build_executables; read -p "Press Enter to continue..." ;;
            5) generate_data; read -p "Press Enter to continue..." ;;
            6) check_status; read -p "Press Enter to continue..." ;;
            7) main_menu ;;
            *) echo "Invalid choice."; sleep 2 ;;
        esac
    done
}

# 
# FUNCTIONS
# 

check_prerequisites() {
    echo "[Step] Checking Prerequisites..."
    echo ""

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Python 3 not found. Install Python 3.8+ from https://www.python.org/"
        return 1
    fi
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}[OK]${NC} Python $PYTHON_VERSION found"

    # Check Conda
    if ! command -v conda &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Conda not found. Install Miniconda from https://docs.conda.io/en/latest/miniconda.html"
        return 1
    fi
    CONDA_VERSION=$(conda --version | cut -d' ' -f2)
    echo -e "${GREEN}[OK]${NC} Conda $CONDA_VERSION found"

    # Check g++
    if ! command -v g++ &> /dev/null; then
        echo -e "${YELLOW}[WARNING]${NC} g++ not found. You'll need g++ to build C++ executables."
        echo "Install: sudo apt-get install build-essential (Ubuntu/Debian)"
    else
        GCC_VERSION=$(g++ --version | head -n1)
        echo -e "${GREEN}[OK]${NC} $GCC_VERSION found"
    fi

    echo ""
    return 0
}

create_conda_env() {
    echo ""
    echo "  Creating Conda Environment"
    echo ""
    echo ""

    # Check if environment.yml exists
    if [ ! -f "$PROJECT_ROOT/environment.yml" ]; then
        echo -e "${RED}[ERROR]${NC} environment.yml not found"
        return 1
    fi

    # Check if environment already exists
    if [ -d "$CONDA_ENV_PATH" ]; then
        echo -e "${YELLOW}[INFO]${NC} Environment already exists at .conda/"
        read -p "Update existing environment? (y/n): " update_env
        if [[ "$update_env" =~ ^[Yy]$ ]]; then
            echo "[INFO] Updating environment..."
            conda env update -f "$PROJECT_ROOT/environment.yml" -p "$CONDA_ENV_PATH" || {
                echo -e "${RED}[ERROR]${NC} Failed to update environment"
                return 1
            }
            echo -e "${GREEN}[OK]${NC} Environment updated"
        fi
    else
        echo "[INFO] Creating conda environment from environment.yml..."
        echo "Environment will be created at: .conda/"
        echo "This may take 5-10 minutes..."
        echo ""
        conda env create -f "$PROJECT_ROOT/environment.yml" -p "$CONDA_ENV_PATH" || {
            echo -e "${RED}[ERROR]${NC} Failed to create environment"
            return 1
        }
        echo -e "${GREEN}[OK]${NC} Environment created successfully at .conda/"
    fi

    echo ""
    echo "Testing packages..."
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV_PATH"
    python -c "import pyogrio, geopandas, flask; print('[OK] All critical packages imported successfully')" 2>/dev/null || {
        echo -e "${YELLOW}[WARNING]${NC} Some packages may not be working correctly"
    }
    echo ""
    return 0
}

create_directories() {
    echo ""
    echo "  Creating Directory Structure"
    echo ""
    echo ""

    mkdir -p "$MAIN_DIR/data/raw"
    mkdir -p "$MAIN_DIR/data/processed"
    mkdir -p "$MAIN_DIR/data/disruptions"
    mkdir -p "$MAIN_DIR/build/dhl"
    mkdir -p "$MAIN_DIR/build/hc2l"
    mkdir -p "$MAIN_DIR/cache"

    echo -e "${GREEN}[OK]${NC} Created Main/data/raw/"
    echo -e "${GREEN}[OK]${NC} Created Main/data/processed/"
    echo -e "${GREEN}[OK]${NC} Created Main/data/disruptions/"
    echo -e "${GREEN}[OK]${NC} Created Main/build/dhl/"
    echo -e "${GREEN}[OK]${NC} Created Main/build/hc2l/"
    echo -e "${GREEN}[OK]${NC} Created Main/cache/"
    echo ""
}

setup_env_file() {
    echo ""
    echo "  Setting up .env Configuration"
    echo ""
    echo ""

    if [ -f "$MAIN_DIR/.env" ]; then
        echo "[INFO] .env file already exists"
        read -p "Overwrite existing .env? (y/n): " overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            echo "[SKIP] Keeping existing .env file"
            return 0
        fi
    fi

    if [ -f "$MAIN_DIR/.env.example" ]; then
        cp "$MAIN_DIR/.env.example" "$MAIN_DIR/.env"
        echo -e "${GREEN}[OK]${NC} Created .env from template"
    else
        echo "[INFO] Creating basic .env file"
        cat > "$MAIN_DIR/.env" << EOF
GOOGLE_MAPS_API_KEY=your_api_key_here
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
EOF
        echo -e "${GREEN}[OK]${NC} Created basic .env file"
    fi

    echo ""
    echo -e "${YELLOW}[IMPORTANT]${NC} Please edit Main/.env and add your Google Maps API key"
    read -p "Open .env file now? (y/n): " edit_now
    if [[ "$edit_now" =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} "$MAIN_DIR/.env"
    fi
    echo ""
}

build_executables() {
    echo ""
    echo "  Building C++ Executables"
    echo ""
    echo ""

    if ! command -v g++ &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} g++ not found. Cannot build executables."
        echo "Install build tools, then try again."
        return 1
    fi

    if [ -f "$PROJECT_ROOT/build_all.sh" ]; then
        chmod +x "$PROJECT_ROOT/build_all.sh"
        "$PROJECT_ROOT/build_all.sh" || {
            echo -e "${RED}[ERROR]${NC} Build failed"
            return 1
        }
        echo -e "${GREEN}[OK]${NC} Executables built successfully"
    else
        echo -e "${RED}[ERROR]${NC} build_all.sh not found"
        return 1
    fi
    echo ""
}

generate_data() {
    echo ""
    echo "  Generating Data and Indexes"
    echo ""
    echo ""
    echo "This process takes 15-20 minutes and requires:"
    echo "  - Active internet connection"
    echo "  - Conda environment activated"
    echo ""
    read -p "Continue? (y/n): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        return 0
    fi

    echo ""
    echo "[Step 1/2] Activating conda environment..."
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV_PATH"

    echo "[Step 2/2] Generating OSM data and building indexes (this takes time)..."
    cd "$MAIN_DIR"
    python request_new_datasets.py || {
        echo -e "${RED}[ERROR]${NC} Data generation and index building failed"
        cd "$PROJECT_ROOT"
        return 1
    }

    cd "$PROJECT_ROOT"
    echo ""
    echo -e "${GREEN}[OK]${NC} Data generation and indexing complete!"
    echo ""
}

check_status() {
    echo ""
    echo "  Installation Status"
    echo ""
    echo ""

    # Check conda environment
    if [ -d "$CONDA_ENV_PATH" ]; then
        echo -e "${GREEN}[OK]${NC} Conda environment exists at .conda/"
    elif conda env list | grep -q "^$ENV_NAME "; then
        echo -e "${GREEN}[OK]${NC} Conda environment '$ENV_NAME' exists (named)"
    else
        echo -e "${RED}[X]${NC} Conda environment not found"
    fi

    # Check directories
    if [ -d "$MAIN_DIR/data" ]; then
        echo -e "${GREEN}[OK]${NC} Data directories exist"
    else
        echo -e "${RED}[X]${NC} Data directories missing"
    fi

    # Check .env
    if [ -f "$MAIN_DIR/.env" ]; then
        echo -e "${GREEN}[OK]${NC} .env file exists"
    else
        echo -e "${RED}[X]${NC} .env file missing"
    fi

    # Check executables
    if [ -f "$MAIN_DIR/build/dhl/dhl_routing_api" ]; then
        echo -e "${GREEN}[OK]${NC} DHL executable exists"
    else
        echo -e "${RED}[X]${NC} DHL executable missing"
    fi

    if [ -f "$MAIN_DIR/build/hc2l/hc2l_routing_api" ]; then
        echo -e "${GREEN}[OK]${NC} HC2L executable exists"
    else
        echo -e "${RED}[X]${NC} HC2L executable missing"
    fi

    # Check data files
    if [ -f "$MAIN_DIR/data/raw/quezon_city_nodes.csv" ]; then
        echo -e "${GREEN}[OK]${NC} Data files exist"
    else
        echo -e "${RED}[X]${NC} Data files missing"
    fi

    # Check indexes
    if [ -f "$MAIN_DIR/data/processed/quezon_city.dhl.index" ]; then
        echo -e "${GREEN}[OK]${NC} Index files exist"
    else
        echo -e "${RED}[X]${NC} Index files missing"
    fi

    echo ""
    echo "Run check_gdal.py for detailed package verification"
    echo ""
}

# Start the script
main_menu