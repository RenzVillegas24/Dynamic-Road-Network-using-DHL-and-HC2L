# Dynamic Road Network Setup Guide

Complete platform-specific setup instructions for the Dynamic Road Network project with DHL and HC2L routing algorithms.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Platform-Specific Setup](#platform-specific-setup)
  - [Linux (Ubuntu/Debian)](#linux-ubuntudebian)
  - [Linux (Fedora/RHEL)](#linux-fedorarhel)
  - [macOS](#macos)
  - [Windows](#windows)
- [Conda Environment Setup](#conda-environment-setup)
- [Quick Start](#quick-start)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have the following installed:

### System Requirements

- **RAM**: Minimum 4GB (8GB+ recommended)
- **Disk Space**: 5GB for code, dependencies, and generated data
- **Internet Connection**: Required for downloading packages and HERE API data

### Base Requirements

All platforms require:
1. **C++ Compiler** (g++, clang++, or MSVC)
2. **Python 3.8+**
3. **Conda** or **Miniconda** (recommended) or **Anaconda**
4. **Git** (for version control)

---

## Platform-Specific Setup

### Linux (Ubuntu/Debian)

#### Step 1: Install System Dependencies

```bash
# Update package manager
sudo apt-get update
sudo apt-get upgrade -y

# Install build tools
sudo apt-get install -y \
    build-essential \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    libgdal-dev

# Install Miniconda (Recommended)
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm -rf ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init bash
# Restart your shell or source ~/.bashrc
source ~/.bashrc
```

#### Step 2: Clone and Navigate to Project

```bash
git clone https://github.com/RenzVillegas24/Dynamic-Road-Network-using-DHL-and-HC2L.git
cd Dynamic-Road-Network-using-DHL-and-HC2L
```

#### Step 3: Create Conda Environment

**Option A: Automatic Setup (Recommended)**

```bash
# Make setup script executable
chmod +x setup.sh

# Create conda environment
./setup.sh --conda-setup

# Activate the environment
conda activate ./.conda
```

**Option B: Manual Setup**

```bash
# Create conda environment from environment.yml
conda env create --prefix ./.conda --file environment.yml

# Activate the environment
conda activate ./.conda

# Install additional packages if needed
pip install rtree
```

#### Step 4: Run Full Setup

```bash
# Run complete setup (build + data + indexes + server)
./setup.sh --full

# Or run individual steps:
./setup.sh --build              # Compile C++ algorithms
./setup.sh --data --both        # Generate traffic data
./setup.sh --indexes            # Build routing indexes
./setup.sh --server             # Start Flask server
```

#### Step 5: Access the Web Interface

Open your browser and navigate to:

```
http://localhost:5000
```

---

### Linux (Fedora/RHEL)

#### Step 1: Install System Dependencies

```bash
# Update package manager
sudo dnf update -y
sudo dnf groupinstall "Development Tools" -y

# Install additional packages
sudo dnf install -y \
    gcc-c++ \
    git \
    wget \
    curl \
    python3 \
    python3-devel \
    gdal-devel

# Install Miniconda (Recommended)
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm -rf ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init bash
source ~/.bashrc
```

#### Step 2-5: Same as Ubuntu/Debian

Follow the same steps as Ubuntu/Debian from "Step 2: Clone and Navigate to Project" onwards.

---

### macOS

#### Step 1: Install System Dependencies

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required packages
brew install \
    gcc \
    git \
    wget \
    curl \
    gdal

# Install Miniconda (Recommended)
mkdir -p ~/miniconda3
curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh -o ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm -rf ~/miniconda3/miniconda.sh
~/miniconda3/bin/conda init zsh  # For Zsh shell (default on macOS Catalina+)
# Or use: ~/miniconda3/bin/conda init bash  # For Bash
source ~/.zshrc  # or ~/.bashrc
```

#### Step 2: Clone and Navigate to Project

```bash
git clone https://github.com/RenzVillegas24/Dynamic-Road-Network-using-DHL-and-HC2L.git
cd Dynamic-Road-Network-using-DHL-and-HC2L
```

#### Step 3: Create Conda Environment

```bash
# Make setup script executable
chmod +x setup.sh

# Create conda environment
./setup.sh --conda-setup

# Activate the environment
conda activate ./.conda
```

#### Step 4: Run Full Setup

```bash
# Run complete setup
./setup.sh --full
```

#### Step 5: Access the Web Interface

Open your browser and navigate to:

```
http://localhost:5000
```

---

### Windows

#### Step 1: Install System Dependencies

**Option A: Using Windows Package Manager (Recommended)**

```powershell
# Install Chocolatey (if not installed)
Set-ExecutionPolicy Bypass -Scope Process -Force; `
[System.Net.ServicePointManager]::SecurityProtocol = `
[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; `
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install required packages
choco install -y ^
    mingw ^
    git ^
    python ^
    miniconda3
```

**Option B: Manual Installation**

1. **MinGW (C++ Compiler)**
   - Download from: https://winlibs.com/
   - Extract and add `bin` directory to PATH environment variable

2. **Python**
   - Download from: https://www.python.org/downloads/
   - **Important**: Check "Add Python to PATH" during installation

3. **Git**
   - Download from: https://git-scm.com/download/win

4. **Miniconda (Recommended)**
   - Download from: https://docs.conda.io/projects/miniconda/en/latest/
   - Run installer and follow instructions

#### Step 2: Clone and Navigate to Project

```powershell
# Open PowerShell or Command Prompt
git clone https://github.com/RenzVillegas24/Dynamic-Road-Network-using-DHL-and-HC2L.git
cd Dynamic-Road-Network-using-DHL-and-HC2L
```

#### Step 3: Create Conda Environment

**Option A: Using PowerShell (Recommended)**

```powershell
# Create conda environment
.\setup.ps1 -CondaSetup

# Activate the environment
conda activate .\.conda
```

**Option B: Using Command Prompt (Batch)**

```batch
# Create conda environment
setup.bat --conda-setup

# Activate the environment
conda activate .\.conda
```

**Option C: Manual Setup**

```powershell
# Create conda environment from environment.yml
conda env create --prefix .\.conda --file environment.yml

# Activate the environment
conda activate .\.conda
```

#### Step 4: Run Full Setup

**Using PowerShell (Recommended)**

```powershell
# Run complete setup
.\setup.ps1 -Full

# Or individual steps:
.\setup.ps1 -Build              # Build C++ algorithms
.\setup.ps1 -Data -Mode both    # Generate traffic data
.\setup.ps1 -Indexes            # Build routing indexes
.\setup.ps1 -Server             # Start Flask server
```

**Using Command Prompt (Batch)**

```batch
REM Run complete setup
setup.bat --full

REM Or individual steps:
setup.bat --build
setup.bat --data
setup.bat --indexes
setup.bat --server
```

#### Step 5: Access the Web Interface

Open your browser and navigate to:

```
http://localhost:5000
```

---

## Conda Environment Setup

### What is Conda?

Conda is a package manager that helps manage dependencies and create isolated Python environments. This project uses conda to ensure all dependencies are correctly installed.

### Creating the Conda Environment

The conda environment is defined in `environment.yml` and includes:

- Python 3.11
- Geographic libraries (GDAL, GeoPandas, Shapely, PyProj, OSMnx)
- Data processing tools (Pandas, NumPy, NetworkX)
- Visualization tools (Matplotlib)
- Flask for the web server

#### Automatic Setup (All Platforms)

```bash
# Linux/macOS
./setup.sh --conda-setup

# Windows PowerShell
.\setup.ps1 -CondaSetup

# Windows Command Prompt
setup.bat --conda-setup
```

#### Manual Setup

```bash
# Create environment with a specific name or location
conda env create --prefix ./.conda --file environment.yml

# Or create with environment name instead of location
conda env create -n drn-env --file environment.yml
```

#### Activating the Environment

```bash
# Using ./.conda location (created in project directory)
conda activate ./.conda

# Or if you used environment name
conda activate drn-env
```

#### Deactivating the Environment

```bash
conda deactivate
```

#### Verifying Installation

```bash
# Check if environment is activated (you should see (.conda) or (drn-env) in your prompt)
python --version
pip list
```

---

## Quick Start

### Quick Setup (All Platforms)

**1. After conda environment is activated:**

```bash
# Complete setup in one command
# Linux/macOS:
./setup.sh --full

# Windows PowerShell:
.\setup.ps1 -Full

# Windows Command Prompt:
setup.bat --full
```

**2. Wait for completion** (usually 10-20 minutes)

**3. Start the server:**

```bash
# Linux/macOS:
./setup.sh --server

# Windows PowerShell:
.\setup.ps1 -Server

# Windows Command Prompt:
setup.bat --server
```

**4. Open browser to `http://localhost:5000`**

### Setup Individual Components

#### Build C++ Algorithms Only

```bash
# Linux/macOS:
./setup.sh --build

# Windows PowerShell:
.\setup.ps1 -Build

# Windows Command Prompt:
setup.bat --build
```

#### Generate Traffic Data Only

```bash
# Linux/macOS (with different modes):
./setup.sh --data --both        # Both flow and incidents
./setup.sh --data --flow        # Flow only
./setup.sh --data --incidents   # Incidents only
./setup.sh --data --synthetic   # Synthetic data

# Windows PowerShell:
.\setup.ps1 -Data -Mode both
.\setup.ps1 -Data -Mode flow

# Windows Command Prompt:
setup.bat --data --both
setup.bat --data --flow
```

#### Build Indexes Only

```bash
# Linux/macOS:
./setup.sh --indexes

# Windows PowerShell:
.\setup.ps1 -Indexes

# Windows Command Prompt:
setup.bat --indexes
```

#### Start Flask Server

```bash
# Linux/macOS:
./setup.sh --server

# Windows PowerShell:
.\setup.ps1 -Server

# Windows Command Prompt:
setup.bat --server
```

---

## Troubleshooting

### Conda Environment Issues

#### "conda not found" Error

**Problem**: Conda is not installed or not in PATH

**Solutions**:

```bash
# Add Miniconda to PATH (Linux/macOS)
export PATH="$HOME/miniconda3/bin:$PATH"
source ~/.bashrc  # or ~/.zshrc for macOS

# Or reinstall Miniconda and select "Add to PATH" option
```

For Windows, ensure Miniconda is added to PATH in System Environment Variables.

#### "Failed to create conda environment" Error

**Problem**: Network issue or corrupted package cache

**Solutions**:

```bash
# Clear conda cache
conda clean --all

# Try again with verbose output
conda env create --prefix ./.conda --file environment.yml -v

# Or remove and recreate
conda env remove --prefix ./.conda
conda env create --prefix ./.conda --file environment.yml
```

### C++ Compiler Issues

#### "g++ compiler not found" Error

**Linux (Ubuntu/Debian)**:

```bash
sudo apt-get install -y build-essential
```

**Linux (Fedora/RHEL)**:

```bash
sudo dnf groupinstall "Development Tools" -y
```

**macOS**:

```bash
xcode-select --install
```

**Windows**:

- Install MinGW from https://winlibs.com/
- Add MinGW `bin` directory to PATH
- Or use setup.ps1 which has better compiler detection

### Python Issues

#### "Python 3 not found" Error

**All Platforms**:

1. Install Python 3.8+ from https://www.python.org/downloads/
2. Add Python to PATH
3. Verify: `python --version` or `python3 --version`

#### Module Not Found Errors

**All Platforms**:

```bash
# Ensure conda environment is activated
conda activate ./.conda

# Try to reinstall the package
pip install <package-name>

# For rtree specifically:
pip install rtree

# For geographic packages:
pip install geopandas geodal pyproj
```

### Build Issues

#### "Compilation Failed" Error

**Possible causes**:

1. **Missing C++ compiler** - See "C++ Compiler Issues" above
2. **Missing dependencies** - Ensure conda environment is activated
3. **Insufficient RAM** - Some C++ compilations need 2GB+ RAM

**Solutions**:

```bash
# Clean previous builds
rm -rf Main/build
./setup.sh --build  # or .\setup.ps1 -Build

# Or try with fewer parallel jobs
cd DualHierarchyLabelling
g++ -std=c++2a -O3 src/dhl_routing_api.cpp src/road_network.cpp src/util.cpp -o ../Main/build/dhl/dhl_routing_api
```

### Server Issues

#### "Port 5000 already in use" Error

**Solution - Change Port**:

```bash
# Edit Main/flask_server.py
# Find: app.run(host='0.0.0.0', port=5000)
# Change: app.run(host='0.0.0.0', port=5001)

# Or kill existing process:
# Linux/macOS:
pkill -f flask_server.py

# Windows PowerShell:
Stop-Process -Name python -Force
```

#### Cannot Connect to Server

**Troubleshooting**:

```bash
# 1. Check if server is running
ps aux | grep flask_server.py  # Linux/macOS
Get-Process python | Select-Object ProcessName, Id  # Windows

# 2. Check server logs for errors
# Look at console output when starting the server

# 3. Try accessing from different URL
# http://localhost:5000 (local machine)
# http://<your-ip>:5000 (from other machine, if firewall allows)

# 4. Check firewall settings
# Ensure port 5000 is not blocked by firewall
```

### Data Generation Issues

#### "HERE API key not found" Error

**Solution**:

1. Add your HERE API credentials to `.env` file:

```bash
# Create .env file in project root
echo "HERE_API_KEY=your_key_here" > .env
```

2. Or use synthetic data mode:

```bash
./setup.sh --data --synthetic
```

#### "Graph file not found" Error

**Problem**: Data generation didn't complete successfully

**Solution**:

```bash
# Run data generation again
./setup.sh --data --synthetic  # Use synthetic data (no API needed)

# Or check for errors:
tail -100 Main/data/disruptions/  # Check generated files
```

### macOS Specific Issues

#### "clang: error: unsupported option" Error

**Problem**: Compiler version mismatch

**Solutions**:

```bash
# Update Xcode Command Line Tools
xcode-select --install
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
sudo xcode-select --reset

# Or specify compiler explicitly
export CXX=g++
export CC=gcc
./setup.sh --build
```

#### "GDAL not found" Error

**Solution**:

```bash
brew install gdal
conda install -c conda-forge gdal geopandas pyogrio
```

### Windows Specific Issues

#### "Python is not recognized" Error

**Solution**:

1. Ensure Python is installed
2. Add Python to PATH:
   - Right-click This PC > Properties
   - Advanced system settings > Environment Variables
   - Add Python installation directory to PATH
3. Restart PowerShell/Command Prompt

#### "Access Denied" Error in PowerShell

**Solution**:

```powershell
# Enable script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then run setup script
.\setup.ps1 -Full
```

#### MinGW Not Found

**Solution**:

1. Download from https://winlibs.com/
2. Extract to a known location (e.g., `C:\MinGW`)
3. Add to PATH:
   - Add `C:\MinGW\bin` to environment variables
4. Verify:
   ```powershell
   g++ --version
   ```

---

## Performance Tips

### Speed Up Installation

```bash
# Use faster internet connection if available
# Disable antivirus temporarily during package installation
# Use SSD for better I/O performance
```

### Speed Up Building

```bash
# Ensure conda environment is activated
conda activate ./.conda

# Use parallel compilation (if supported)
export MAKEFLAGS="-j$(nproc)"  # Linux/macOS
# or
set MAKEFLAGS=-j%NUMBER_OF_PROCESSORS%  # Windows
```

### Speed Up Data Generation

```bash
# Use synthetic data (faster, no API calls)
./setup.sh --data --synthetic

# Or use specific mode
./setup.sh --data --flow  # Flow data only
```

---

## Next Steps

After successful setup:

1. **Access the web interface**: http://localhost:5000
2. **Run routing queries**: Use the map interface to plan routes
3. **View traffic data**: See real-time traffic incidents
4. **Check logs**: See `Main/` directory for logs and cache files
5. **Read documentation**: See `Documentation/` folder for detailed guides

---

## Support and Resources

- **Documentation**: See `Documentation/` folder
- **Issues**: Report problems on GitHub
- **API Docs**: Check inline comments in code
- **HERE API**: https://developer.here.com/

---

## Version Information

- **Python**: 3.11
- **C++ Standard**: C++20 (HC2L), C++2a (DHL)
- **Last Updated**: November 2025

---

## License

See LICENSE file in project root.
