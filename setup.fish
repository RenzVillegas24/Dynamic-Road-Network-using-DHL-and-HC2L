#!/usr/bin/env fish
# All-in-One Setup Script for Dynamic Road Network (Fish Shell)
# Supports both automatic and manual setup with conda environment

set SCRIPT_DIR (dirname (status --current-filename))
set PROJECT_ROOT $SCRIPT_DIR
set MAIN_DIR "$PROJECT_ROOT/Main"
set ENV_NAME "roadnet"
set CONDA_ENV_PATH "$PROJECT_ROOT/.conda"

# Helper functions for colored output
function print_error
    set_color red; echo "[$argv[1]]"; set_color normal; echo " $argv[2..-1]"
end

function print_ok
    set_color green; echo "[$argv[1]]"; set_color normal; echo " $argv[2..-1]"
end

function print_warning
    set_color yellow; echo "[$argv[1]]"; set_color normal; echo " $argv[2..-1]"
end

function print_info
    echo "[$argv[1]] $argv[2..-1]"
end

# Main Menu
function main_menu
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
    read -P "Enter your choice (1-3): " setup_mode
    echo ""

    switch $setup_mode
        case 1
            auto_setup
        case 2
            manual_menu
        case 3
            exit 0
        case '*'
            echo "Invalid choice."
            sleep 2
            main_menu
    end
end

# 
# AUTOMATIC SETUP
# 
function auto_setup
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
    read -P "Press Enter to continue..."
    echo ""

    check_prerequisites; or return 1
    create_conda_env; or return 1
    create_directories
    setup_env_file
    build_executables

    echo ""
    read -P "Generate OSM data and build indexes now? (y/n): " gen_data
    if string match -qi 'y*' $gen_data
        generate_data
    end

    echo ""
    echo ""
    echo "  AUTOMATIC SETUP COMPLETE!"
    echo ""
    echo ""
    echo "Your environment is ready! To start:"
    echo "  1. Activate: conda activate .conda"
    echo "  2. Run: ./run_server.fish"
    echo ""
    read -P "Press Enter to exit..."
    exit 0
end

# 
# MANUAL SETUP MENU
# 
function manual_menu
    while true
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
        read -P "Enter your choice (1-7): " manual_choice
        echo ""

        switch $manual_choice
            case 1
                create_conda_env
                read -P "Press Enter to continue..."
            case 2
                create_directories
                read -P "Press Enter to continue..."
            case 3
                setup_env_file
                read -P "Press Enter to continue..."
            case 4
                build_executables
                read -P "Press Enter to continue..."
            case 5
                generate_data
                read -P "Press Enter to continue..."
            case 6
                check_status
                read -P "Press Enter to continue..."
            case 7
                main_menu
            case '*'
                echo "Invalid choice."
                sleep 2
        end
    end
end

# 
# FUNCTIONS
# 

function check_prerequisites
    print_info "Step" "Checking Prerequisites..."
    echo ""

    # Check Python
    if not command -v python3 &> /dev/null
        print_error "ERROR" "Python 3 not found. Install Python 3.8+ from https://www.python.org/"
        return 1
    end
    set PYTHON_VERSION (python3 --version | cut -d' ' -f2)
    print_ok "OK" "Python $PYTHON_VERSION found"

    # Check Conda
    if not command -v conda &> /dev/null
        print_error "ERROR" "Conda not found. Install Miniconda from https://docs.conda.io/en/latest/miniconda.html"
        return 1
    end
    set CONDA_VERSION (conda --version | cut -d' ' -f2)
    print_ok "OK" "Conda $CONDA_VERSION found"

    # Check g++
    if not command -v g++ &> /dev/null
        print_warning "WARNING" "g++ not found. You'll need g++ to build C++ executables."
        echo "Install: sudo apt-get install build-essential (Ubuntu/Debian)"
    else
        set GCC_VERSION (g++ --version | head -n1)
        print_ok "OK" "$GCC_VERSION found"
    end

    echo ""
    return 0
end

function create_conda_env
    echo ""
    echo "  Creating Conda Environment"
    echo ""
    echo ""

    # Check if environment.yml exists
    if not test -f "$PROJECT_ROOT/environment.yml"
        printf "%b[ERROR]%b environment.yml not found\n" $RED $NC
        return 1
    end

    # Check if environment already exists
    if test -d "$CONDA_ENV_PATH"
        printf "%b[INFO]%b Environment already exists at .conda/\n" $YELLOW $NC
        read -P "Update existing environment? (y/n): " update_env
        if string match -qi 'y*' $update_env
            echo "[INFO] Updating environment..."
            conda env update -f "$PROJECT_ROOT/environment.yml" -p "$CONDA_ENV_PATH"
            if test $status -ne 0
                printf "%b[ERROR]%b Failed to update environment\n" $RED $NC
                return 1
            end
            printf "%b[OK]%b Environment updated\n" $GREEN $NC
        end
    else
        echo "[INFO] Creating conda environment from environment.yml..."
        echo "Environment will be created at: .conda/"
        echo "This may take 5-10 minutes..."
        echo ""
        conda env create -f "$PROJECT_ROOT/environment.yml" -p "$CONDA_ENV_PATH"
        if test $status -ne 0
            printf "%b[ERROR]%b Failed to create environment\n" $RED $NC
            return 1
        end
        printf "%b[OK]%b Environment created successfully at .conda/\n" $GREEN $NC
    end

    echo ""
    echo "Testing packages..."
    source (conda info --base)/etc/fish/conf.d/conda.fish
    conda activate "$CONDA_ENV_PATH"
    python -c "import pyogrio, geopandas, flask; print('[OK] All critical packages imported successfully')" 2>/dev/null
    if test $status -ne 0
        printf "%b[WARNING]%b Some packages may not be working correctly\n" $YELLOW $NC
    end
    echo ""
    return 0
end

function create_directories
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

    printf "%b[OK]%b Created Main/data/raw/\n" $GREEN $NC
    printf "%b[OK]%b Created Main/data/processed/\n" $GREEN $NC
    printf "%b[OK]%b Created Main/data/disruptions/\n" $GREEN $NC
    printf "%b[OK]%b Created Main/build/dhl/\n" $GREEN $NC
    printf "%b[OK]%b Created Main/build/hc2l/\n" $GREEN $NC
    printf "%b[OK]%b Created Main/cache/\n" $GREEN $NC
    echo ""
end

function setup_env_file
    echo ""
    echo "  Setting up .env Configuration"
    echo ""
    echo ""

    if test -f "$MAIN_DIR/.env"
        echo "[INFO] .env file already exists"
        read -P "Overwrite existing .env? (y/n): " overwrite
        if not string match -qi 'y*' $overwrite
            echo "[SKIP] Keeping existing .env file"
            return 0
        end
    end

    if test -f "$MAIN_DIR/.env.example"
        cp "$MAIN_DIR/.env.example" "$MAIN_DIR/.env"
        printf "%b[OK]%b Created .env from template\n" $GREEN $NC
    else
        echo "[INFO] Creating basic .env file"
        printf "GOOGLE_MAPS_API_KEY=your_api_key_here\nFLASK_ENV=development\nFLASK_DEBUG=True\nFLASK_HOST=0.0.0.0\nFLASK_PORT=5000\n" > "$MAIN_DIR/.env"
        printf "%b[OK]%b Created basic .env file\n" $GREEN $NC
    end

    echo ""
    printf "%b[IMPORTANT]%b Please edit Main/.env and add your Google Maps API key\n" $YELLOW $NC
    read -P "Open .env file now? (y/n): " edit_now
    if string match -qi 'y*' $edit_now
        set -q EDITOR; and eval $EDITOR "$MAIN_DIR/.env"; or nano "$MAIN_DIR/.env"
    end
    echo ""
end

function build_executables
    echo ""
    echo "  Building C++ Executables"
    echo ""
    echo ""

    if not command -v g++ &> /dev/null
        printf "%b[ERROR]%b g++ not found. Cannot build executables.\n" $RED $NC
        echo "Install build tools, then try again."
        return 1
    end

    if test -f "$PROJECT_ROOT/build_all.sh"
        chmod +x "$PROJECT_ROOT/build_all.sh"
        eval "$PROJECT_ROOT/build_all.sh"
        if test $status -ne 0
            printf "%b[ERROR]%b Build failed\n" $RED $NC
            return 1
        end
        printf "%b[OK]%b Executables built successfully\n" $GREEN $NC
    else
        printf "%b[ERROR]%b build_all.sh not found\n" $RED $NC
        return 1
    end
    echo ""
end

function generate_data
    echo ""
    echo "  Generating Data and Indexes"
    echo ""
    echo ""
    echo "This process takes 15-20 minutes and requires:"
    echo "  - Active internet connection"
    echo "  - Conda environment activated"
    echo ""
    read -P "Continue? (y/n): " confirm
    if not string match -qi 'y*' $confirm
        return 0
    end

    echo ""
    echo "[Step 1/3] Activating conda environment..."
    source (conda info --base)/etc/fish/conf.d/conda.fish
    conda activate "$CONDA_ENV_PATH"

    echo "[Step 2/3] Generating OSM data (this takes time)..."
    cd "$MAIN_DIR"
    python request_new_datasets.py
    if test $status -ne 0
        printf "%b[ERROR]%b Data generation failed\n" $RED $NC
        cd "$PROJECT_ROOT"
        return 1
    end

    cd "$PROJECT_ROOT"
    echo "[Step 3/3] Building indexes..."
    chmod +x generate_data.fish
    ./generate_data.fish
    if test $status -ne 0
        printf "%b[ERROR]%b Index building failed\n" $RED $NC
        return 1
    end

    echo ""
    printf "%b[OK]%b Data generation and indexing complete!\n" $GREEN $NC
    echo ""
end

function check_status
    echo ""
    echo "  Installation Status"
    echo ""
    echo ""

    # Check conda environment
    if test -d "$CONDA_ENV_PATH"
        printf "%b[OK]%b Conda environment exists at .conda/\n" $GREEN $NC
    else if conda env list | grep -q "^$ENV_NAME "
        printf "%b[OK]%b Conda environment '%s' exists (named)\n" $GREEN $NC $ENV_NAME
    else
        printf "%b[X]%b Conda environment not found\n" $RED $NC
    end

    # Check directories
    if test -d "$MAIN_DIR/data"
        printf "%b[OK]%b Data directories exist\n" $GREEN $NC
    else
        printf "%b[X]%b Data directories missing\n" $RED $NC
    end

    # Check .env
    if test -f "$MAIN_DIR/.env"
        printf "%b[OK]%b .env file exists\n" $GREEN $NC
    else
        printf "%b[X]%b .env file missing\n" $RED $NC
    end

    # Check executables
    if test -f "$MAIN_DIR/build/dhl/dhl_routing_api"
        printf "%b[OK]%b DHL executable exists\n" $GREEN $NC
    else
        printf "%b[X]%b DHL executable missing\n" $RED $NC
    end

    if test -f "$MAIN_DIR/build/hc2l/hc2l_routing_api"
        printf "%b[OK]%b HC2L executable exists\n" $GREEN $NC
    else
        printf "%b[X]%b HC2L executable missing\n" $RED $NC
    end

    # Check data files
    if test -f "$MAIN_DIR/data/raw/quezon_city_nodes.csv"
        printf "%b[OK]%b Data files exist\n" $GREEN $NC
    else
        printf "%b[X]%b Data files missing\n" $RED $NC
    end

    # Check indexes
    if test -f "$MAIN_DIR/data/processed/quezon_city.dhl.index"
        printf "%b[OK]%b Index files exist\n" $GREEN $NC
    else
        printf "%b[X]%b Index files missing\n" $RED $NC
    end

    echo ""
    echo "Run check_gdal.py for detailed package verification"
    echo ""
end

# Start the script
main_menu
