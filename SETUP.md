# Simplified Setup - Summary of Changes

## Overview

The setup process has been **completely simplified** into a single unified script for both Windows and Linux that handles everything automatically or provides granular manual control.

## What Changed

### 🎯 New All-in-One Setup Scripts

**Windows:** `setup.bat`  
**Linux/macOS:** `setup.sh`

Both scripts now offer:
- **Option 1: Automatic Setup** - Does everything with one command
- **Option 2: Manual Setup** - Step-by-step control with menu

### ✅ Files Kept

Essential files that remain:
- ✅ `setup.bat` - All-in-one Windows setup
- ✅ `setup.sh` - All-in-one Linux/macOS setup  
- ✅ `build_all.bat/sh` - Build C++ executables
- ✅ `build_indexes.bat/sh` - Build graph indexes
- ✅ `run_server.bat/sh` - Run Flask server
- ✅ `environment.yml` - Conda environment definition
- ✅ `requirements.txt` - Python packages list
- ✅ `QUICK_START.md` - Universal quick start guide
- ✅ `README.md` - Main documentation
- ✅ `WINDOWS_SETUP.md` - Windows-specific details

### ❌ Files Removed

Redundant files that were removed:
- ❌ `setup_conda_env.bat` - Integrated into `setup.bat`
- ❌ `install_gdal_windows.bat` - No longer needed (conda handles GDAL)
- ❌ `check_gdal.py` - Functionality in setup script
- ❌ `requirements-windows-conda.txt` - Use `environment.yml` instead
- ❌ `GDAL_WINDOWS_GUIDE.md` - No longer needed (conda handles it)
- ❌ `QUICK_START_WINDOWS.md` - Merged into universal `QUICK_START.md`
- ❌ `WINDOWS_GDAL_SETUP_SUMMARY.md` - No longer relevant

## New Setup Features

### Automatic Mode (Option 1)

Runs all steps automatically:
1. ✅ Checks prerequisites (Python, Conda, g++)
2. ✅ Creates conda environment from `environment.yml`
3. ✅ Creates directory structure
4. ✅ Sets up `.env` configuration
5. ✅ Builds C++ executables
6. ✅ Optionally generates data and indexes

### Manual Mode (Option 2)

Interactive menu for step-by-step control:
1. Create/Update Conda Environment
2. Create Directory Structure
3. Setup .env Configuration
4. Build C++ Executables
5. Generate Data and Indexes
6. Check Installation Status
7. Back to Main Menu

## Environment Management

### Windows
- Uses **conda environment** (named `roadnet`)
- Falls back to `.venv` if conda not available
- GDAL automatically installed via conda

### Linux/macOS
- Uses **conda environment** (named `roadnet`)  
- Falls back to `.venv` if conda not available
- GDAL typically auto-detected or installed via conda

## Usage Examples

### Quickest Setup (Recommended)

**Windows:**
```cmd
setup.bat
REM Choose: 1
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
# Choose: 1
```

### Step-by-Step Setup

**Windows:**
```cmd
setup.bat
REM Choose: 2
REM Then select individual steps from menu
```

**Linux/macOS:**
```bash
./setup.sh
# Choose: 2
# Then select individual steps from menu
```

### Running the Server

**Windows:**
```cmd
conda activate roadnet
run_server.bat
```

**Linux/macOS:**
```bash
conda activate roadnet
./run_server.sh
```

## Benefits

### ✨ Simplicity
- **1 script** instead of 5+ helper scripts
- **2 modes** (auto/manual) cover all use cases
- **No GDAL complexity** - conda handles it automatically

### 🔄 Consistency
- Same menu interface on Windows and Linux
- Same conda environment approach
- Same directory structure

### 🎯 User-Friendly
- Clear step-by-step feedback
- Color-coded messages (Linux/macOS)
- Status checks built-in
- Helpful error messages

### 🚀 Fast
- Automatic mode: ~10 minutes for full setup
- Manual mode: As quick as you need
- Conda caching speeds up re-runs

## File Structure

```
Project Root/
├── setup.bat              # All-in-one Windows setup
├── setup.sh               # All-in-one Linux/macOS setup
├── build_all.bat/sh       # Build C++ binaries
├── build_indexes.bat/sh   # Build graph indexes
├── run_server.bat/sh      # Run Flask server
├── environment.yml        # Conda environment definition
├── requirements.txt       # Python packages
├── QUICK_START.md         # Universal quick start
├── README.md              # Main documentation
├── WINDOWS_SETUP.md       # Windows-specific guide
└── Main/
    ├── data/              # Data directories
    ├── build/             # Built executables
    ├── cache/             # Cache directory
    └── .env               # Environment configuration
```

## Migration from Old Setup

If you previously used the old setup scripts:

1. **Remove old environment** (optional):
   ```bash
   conda env remove -n roadnet
   ```

2. **Run new setup**:
   ```bash
   ./setup.sh  # or setup.bat on Windows
   ```

3. **Choose automatic setup** (Option 1)

4. **Done!** Everything is reconfigured

## Common Workflows

### First Time Setup
```bash
setup.sh → Option 1 → Yes to generate data → Done!
```

### Update Environment
```bash
setup.sh → Option 2 → Option 1 (Create/Update Conda Environment)
```

### Rebuild Binaries
```bash
setup.sh → Option 2 → Option 4 (Build C++ Executables)
```

### Check Status
```bash
setup.sh → Option 2 → Option 6 (Check Installation Status)
```

### Generate New Data
```bash
setup.sh → Option 2 → Option 5 (Generate Data and Indexes)
```

## Technical Details

### Conda Environment (roadnet)

**Packages Installed:**
- Python 3.10
- GDAL (geographic data library)
- pyogrio, geopandas, shapely, pyproj (geo packages)
- osmnx (OpenStreetMap)
- Flask, Werkzeug (web framework)
- pandas, numpy (data processing)
- matplotlib (visualization)
- networkx (graph algorithms)

### Build Process

1. **DHL Routing API**
   - Compiles from `DualHierarchyLabelling/src/`
   - Outputs to `Main/build/dhl/`

2. **HC2L Routing API**
   - Compiles from `HierarchicalCutLabelling/src/`
   - Outputs to `Main/build/hc2l/`

### Server Integration

`run_server.bat` and `run_server.sh` now:
- Automatically detect conda environment
- Fall back to `.venv` if conda not available
- Check for data/index files
- Offer to generate missing files
- Activate environment before running

## Troubleshooting

### Setup script not found
Make sure you're in the project root directory.

### Conda not found
Install Miniconda and restart terminal.

### Permission denied (Linux/macOS)
```bash
chmod +x setup.sh run_server.sh build_all.sh build_indexes.sh
```

### Build failures
Ensure g++ (or MinGW on Windows) is installed and in PATH.

### Environment creation fails
Check internet connection and disk space (~2GB needed).

## Documentation Updates

- ✅ `README.md` - Updated with new simplified setup
- ✅ `QUICK_START.md` - Universal guide for all platforms
- ✅ `WINDOWS_SETUP.md` - Simplified for conda-based setup
- ✅ All references to old scripts removed

---

**Result:** Setup is now **10x simpler** and works consistently across all platforms! 🎉
