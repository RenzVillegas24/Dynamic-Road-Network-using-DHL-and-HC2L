################################################################################
# Dynamic Road Network - Complete Setup Script (Windows PowerShell)
################################################################################
# This script handles the complete workflow:
# 1. Setup & validation
# 2. Build C++ algorithms (DHL and HC2L)
# 3. Generate data (network + traffic scenarios)
# 4. Build indexes
# 5. Run the Flask web server with real-time traffic updates
#
# Usage:
#   .\setup.ps1                    # Interactive menu
#   .\setup.ps1 -Full              # Complete setup
#   .\setup.ps1 -CondaSetup        # Create conda environment
#   .\setup.ps1 -Build             # Build only
#   .\setup.ps1 -Data              # Generate data only
#   .\setup.ps1 -Indexes           # Build indexes only
#   .\setup.ps1 -Server            # Run server only
#   .\setup.ps1 -Clean             # Remove generated files
#   .\setup.ps1 -Help              # Show help
################################################################################

[CmdletBinding()]
param(
    [switch]$Full,
    [switch]$CondaSetup,
    [switch]$Build,
    [switch]$Data,
    [switch]$Indexes,
    [switch]$Server,
    [switch]$Clean,
    [switch]$Help,
    [ValidateSet("flow", "incidents", "both", "synthetic")]
    [string]$Mode = "both"
)

# Stop on errors
$ErrorActionPreference = "Stop"

# Script metadata
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = $ScriptDir
$MainDir = Join-Path $ProjectRoot "Main"
$BuildDir = Join-Path $MainDir "build"
$DataDir = Join-Path $MainDir "data"
$ProcessedDataDir = Join-Path $DataDir "processed"
$DisruptionsDir = Join-Path $DataDir "disruptions"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Write-Warning2 {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error2 {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Show-Menu {
    Write-Host ""
    Write-Host "Available commands:" -ForegroundColor Cyan
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Full" -ForegroundColor Green -NoNewline
    Write-Host "        Complete setup (build + data + indexes + server)"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -CondaSetup" -ForegroundColor Green -NoNewline
    Write-Host "   Create conda environment"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Build" -ForegroundColor Green -NoNewline
    Write-Host "       Build C++ algorithms only"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Data" -ForegroundColor Green -NoNewline
    Write-Host "        Generate traffic data and base network"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Indexes" -ForegroundColor Green -NoNewline
    Write-Host "     Build routing indexes"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Server" -ForegroundColor Green -NoNewline
    Write-Host "      Run Flask web server"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Clean" -ForegroundColor Green -NoNewline
    Write-Host "       Remove all generated files"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Help" -ForegroundColor Green -NoNewline
    Write-Host "        Show this help message"
    Write-Host ""
}

function Test-Requirements {
    Write-Header "Step 1/5: Checking Requirements"

    # Check for g++ or clang++ (MinGW or Visual Studio)
    $CppCompiler = $null
    
    # Try to find g++ (MinGW)
    if (Get-Command g++ -ErrorAction SilentlyContinue) {
        $CppCompiler = "g++"
        Write-Success "g++ compiler found (MinGW)"
    }
    # Try to find cl (MSVC)
    elseif (Get-Command cl -ErrorAction SilentlyContinue) {
        $CppCompiler = "cl"
        Write-Success "MSVC compiler found"
    }
    # Try to find clang++
    elseif (Get-Command clang++ -ErrorAction SilentlyContinue) {
        $CppCompiler = "clang++"
        Write-Success "clang++ compiler found"
    }
    else {
        Write-Error2 "C++ compiler not found!"
        Write-Host ""
        Write-Host "Please install one of the following:" -ForegroundColor Yellow
        Write-Host "  1. MinGW-w64: https://www.mingw-w64.org/"
        Write-Host "  2. Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/"
        Write-Host "  3. LLVM/Clang: https://releases.llvm.org/"
        Write-Host ""
        Write-Host "For MinGW installation:" -ForegroundColor Cyan
        Write-Host "  - Download from: https://winlibs.com/"
        Write-Host "  - Add bin directory to PATH"
        exit 1
    }
    
    $script:CppCompiler = $CppCompiler

    # Check Python
    $PythonCmd = $null
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonCmd = "python"
        $pythonVersion = & python --version 2>&1
        Write-Success "Python found: $pythonVersion"
    }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        $PythonCmd = "python3"
        $pythonVersion = & python3 --version 2>&1
        Write-Success "Python found: $pythonVersion"
    }
    else {
        Write-Error2 "Python not found!"
        Write-Host ""
        Write-Host "Please install Python 3.8 or higher:" -ForegroundColor Yellow
        Write-Host "  Download from: https://www.python.org/downloads/"
        Write-Host "  Make sure to check 'Add Python to PATH' during installation"
        exit 1
    }

    # Check conda environment (optional but recommended)
    $CondaPython = Join-Path $ProjectRoot ".conda\Scripts\python.exe"
    if (Test-Path $CondaPython) {
        Write-Success "Conda environment detected"
        $script:PythonCmd = $CondaPython
    }
    else {
        Write-Warning2 "Conda environment not found (using system Python)"
        $script:PythonCmd = $PythonCmd
    }

    # Check required Python packages
    Write-Info "Checking Python dependencies..."
    $rtreeCheck = & $script:PythonCmd -c "import rtree" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning2 "rtree not found - required for optimized edge matching"
        Write-Info "Installing rtree..."
        & $script:PythonCmd -m pip install rtree
        if ($LASTEXITCODE -ne 0) {
            Write-Error2 "Failed to install rtree. Please install manually:"
            Write-Host "  pip install rtree"
            exit 1
        }
    }
    Write-Success "rtree package available (optimized matching enabled)"

    # Create necessary directories
    $dirs = @(
        (Join-Path $BuildDir "dhl"),
        (Join-Path $BuildDir "hc2l"),
        (Join-Path $DataDir "raw"),
        $ProcessedDataDir,
        $DisruptionsDir,
        (Join-Path $MainDir "cache")
    )
    
    foreach ($dir in $dirs) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    Write-Success "Data directories created"
}

function Create-CondaEnvironment {
    Write-Header "Creating Conda Environment"

    # Check if conda is installed
    if (!(Get-Command conda -ErrorAction SilentlyContinue)) {
        Write-Error2 "conda not found!"
        Write-Host ""
        Write-Host "Please install Miniconda or Anaconda:" -ForegroundColor Yellow
        Write-Host "  Miniconda (Recommended): https://docs.conda.io/projects/miniconda/en/latest/"
        Write-Host "  Anaconda: https://www.anaconda.com/download"
        return $false
    }
    Write-Success "conda found: $(conda --version)"

    # Check if environment.yml exists
    $envFile = Join-Path $ProjectRoot "environment.yml"
    if (!(Test-Path $envFile)) {
        Write-Error2 "environment.yml not found in $ProjectRoot"
        return $false
    }

    # Create the conda environment
    Write-Info "Creating conda environment from environment.yml..."
    Write-Info "This may take several minutes..."
    Write-Host ""
    
    $condaEnvPath = Join-Path $ProjectRoot ".conda"
    
    try {
        & conda env create --prefix $condaEnvPath --file $envFile --force-reinstall 2>&1 | Out-Host
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Conda environment created successfully"
            Write-Info "Location: $condaEnvPath"
            Write-Host ""
            Write-Info "To activate the environment, run:"
            Write-Host "  conda activate $condaEnvPath" -ForegroundColor Green
            Write-Host ""
            return $true
        }
        else {
            Write-Error2 "Failed to create conda environment"
            return $false
        }
    }
    catch {
        Write-Error2 "Error creating conda environment: $_"
        return $false
    }
}

function Build-DHL {
    Write-Header "Building DHL (Dual-Hierarchy Labelling)"

    Push-Location (Join-Path $ProjectRoot "DualHierarchyLabelling")

    try {
        # Build routing API
        Write-Info "Compiling DHL routing API..."
        $apiOutput = Join-Path $BuildDir "dhl\dhl_routing_api.exe"
        
        if ($script:CppCompiler -eq "g++") {
            $result = & g++ -std=c++2a -O3 -Wall -Wextra -pthread `
                -o $apiOutput `
                src\dhl_routing_api.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        elseif ($script:CppCompiler -eq "clang++") {
            $result = & clang++ -std=c++2a -O3 -Wall -Wextra `
                -o $apiOutput `
                src\dhl_routing_api.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        else {
            # MSVC
            $result = & cl /std:c++20 /O2 /EHsc /Fe:$apiOutput `
                src\dhl_routing_api.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "DHL routing API compiled"
        }
        else {
            Write-Error2 "DHL routing API compilation failed!"
            Write-Host $result
            return $false
        }

        # Build index executable
        Write-Info "Compiling DHL index builder..."
        $indexOutput = Join-Path $BuildDir "dhl\index.exe"
        
        if ($script:CppCompiler -eq "g++") {
            $result = & g++ -std=c++2a -O3 -Wall -Wextra -pthread `
                -o $indexOutput `
                src\index.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        elseif ($script:CppCompiler -eq "clang++") {
            $result = & clang++ -std=c++2a -O3 -Wall -Wextra `
                -o $indexOutput `
                src\index.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        else {
            # MSVC
            $result = & cl /std:c++20 /O2 /EHsc /Fe:$indexOutput `
                src\index.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "DHL index builder compiled"
        }
        else {
            Write-Error2 "DHL index builder compilation failed!"
            Write-Host $result
            return $false
        }
    }
    finally {
        Pop-Location
    }
    
    return $true
}

function Build-HC2L {
    Write-Header "Building HC2L (Hierarchical Cut 2-Hop Labelling)"

    Push-Location (Join-Path $ProjectRoot "HierarchicalCutLabelling")

    try {
        # Build routing API
        Write-Info "Compiling HC2L routing API..."
        $apiOutput = Join-Path $BuildDir "hc2l\hc2l_routing_api.exe"
        
        if ($script:CppCompiler -eq "g++") {
            $result = & g++ -std=c++20 -O3 -Wall -Wextra `
                -o $apiOutput `
                src\hc2l_routing_api.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        elseif ($script:CppCompiler -eq "clang++") {
            $result = & clang++ -std=c++20 -O3 -Wall -Wextra `
                -o $apiOutput `
                src\hc2l_routing_api.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        else {
            # MSVC
            $result = & cl /std:c++20 /O2 /EHsc /Fe:$apiOutput `
                src\hc2l_routing_api.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "HC2L routing API compiled"
        }
        else {
            Write-Error2 "HC2L routing API compilation failed!"
            Write-Host $result
            return $false
        }

        # Build index executable
        Write-Info "Compiling HC2L index builder..."
        $indexOutput = Join-Path $BuildDir "hc2l\index.exe"
        
        if ($script:CppCompiler -eq "g++") {
            $result = & g++ -std=c++20 -O3 -Wall -Wextra `
                -o $indexOutput `
                src\index.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        elseif ($script:CppCompiler -eq "clang++") {
            $result = & clang++ -std=c++20 -O3 -Wall -Wextra `
                -o $indexOutput `
                src\index.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        else {
            # MSVC
            $result = & cl /std:c++20 /O2 /EHsc /Fe:$indexOutput `
                src\index.cpp src\road_network.cpp src\util.cpp 2>&1
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "HC2L index builder compiled"
        }
        else {
            Write-Error2 "HC2L index builder compilation failed!"
            Write-Host $result
            return $false
        }
    }
    finally {
        Pop-Location
    }
    
    return $true
}

function Generate-Data {
    Write-Header "Step 2/5: Generating Traffic Data & Network"

    Push-Location $ProjectRoot

    try {
        # Check if OSM graph files exist, generate if needed
        $graphFile = Join-Path $ProcessedDataDir "quezon_city.graph"
        $edgesFile = Join-Path $DataDir "raw\quezon_city_edges.csv"
        
        if (!(Test-Path $graphFile) -or !(Test-Path $edgesFile)) {
            Write-Info "OSM graph files not found. Generating from OpenStreetMap..."
            Write-Warning2 "This will download OSM data for Quezon City (may take 5-10 minutes)"
            
            & $script:PythonCmd osm_graph_generator.py
            
            if ($LASTEXITCODE -ne 0) {
                Write-Error2 "OSM graph generation failed!"
                return $false
            }
            
            Write-Success "OSM graph generated successfully"
        }
        else {
            Write-Success "OSM graph files found"
        }
        
        # Generate traffic data using new hash-based matching system
        Write-Info "Generating traffic data using hash-based matching..."
        Write-Info "Mode: $Mode (flow/incidents/both)"
        
        & $script:PythonCmd unified_data_generator.py --mode $Mode
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error2 "Traffic data generation failed!"
            return $false
        }

        Write-Success "Traffic data generation complete"
        Write-Info "Output files:"
        Write-Host "  - Traffic CSV: $DisruptionsDir\current_traffic_$Mode.csv"
        Write-Host "  - Traffic GR: $DisruptionsDir\current_traffic_$Mode.gr"
        Write-Host "  - Base graph: $ProcessedDataDir\quezon_city.graph"
        Write-Host "  - OSM edges: $DataDir\raw\quezon_city_edges.csv"
        Write-Host "  - OSM nodes: $DataDir\raw\quezon_city_nodes.csv"
        Write-Host "  - Matched edges: Main\here_osm\matched_edges.csv (732 hashes)"
    }
    finally {
        Pop-Location
    }
    
    return $true
}

function Build-Indexes {
    Write-Header "Step 3/5: Building Routing Indexes"

    Push-Location $MainDir

    try {
        # Check if graph files exist
        $graphFile = Join-Path $ProcessedDataDir "quezon_city.graph"
        if (!(Test-Path $graphFile)) {
            Write-Warning2 "Graph file not found. Have you run data generation?"
            return $false
        }

        # Build DHL index
        Write-Info "Building DHL index..."
        $dhlIndex = Join-Path $BuildDir "dhl\index.exe"
        $outputBase = Join-Path $ProcessedDataDir "quezon_city"
        
        & $dhlIndex $graphFile $outputBase 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "DHL index built"
            Write-Info "  - DHL index: $ProcessedDataDir\quezon_city_dhl"
            Write-Info "  - CH data:   $ProcessedDataDir\quezon_city_ch"
        }
        else {
            Write-Error2 "DHL index build failed!"
            Write-Error2 "Make sure graph file exists: $graphFile"
            return $false
        }

        # Build HC2L index
        Write-Info "Building HC2L index..."
        $hc2lIndex = Join-Path $BuildDir "hc2l\index.exe"
        $hc2lOutput = Join-Path $ProcessedDataDir "quezon_city.hc2l.index"
        
        Get-Content $graphFile | & $hc2lIndex | Set-Content $hc2lOutput
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "HC2L index built"
            Write-Info "  - HC2L index: $hc2lOutput"
        }
        else {
            Write-Error2 "HC2L index build failed!"
            return $false
        }

        Write-Success "All indexes built successfully"
        Write-Info "Index files created in: $ProcessedDataDir\"
    }
    finally {
        Pop-Location
    }
    
    return $true
}

function Start-Server {
    Write-Header "Step 5/5: Starting Flask Server"

    Push-Location $MainDir

    try {
        Write-Info "Cleaning up any existing processes..."
        Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*flask_server.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue
        Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*unified_data_generator.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1

        Write-Info "Starting Flask web server..."
        Write-Info "Server URL: http://localhost:5000"
        Write-Info "Press Ctrl+C to stop"
        Write-Host ""

        # Start Flask in foreground
        & $script:PythonCmd flask_server.py
    }
    finally {
        Pop-Location
    }
}

function Invoke-FullSetup {
    Write-Header "DYNAMIC ROAD NETWORK - COMPLETE SETUP"

    # Step 1: Check requirements
    Test-Requirements

    # Step 2: Build C++ algorithms
    Write-Header "Step 2/5: Building C++ Algorithms"
    if (!(Build-DHL)) { exit 1 }
    if (!(Build-HC2L)) { exit 1 }
    Write-Success "All algorithms compiled successfully"

    # Step 3: Generate data
    if (!(Generate-Data)) { exit 1 }

    # Step 4: Build indexes
    if (!(Build-Indexes)) { exit 1 }

    # Success
    Write-Header "✓ SETUP COMPLETE!"
    Write-Host "The system is ready to use!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next step: Run the server"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Server" -ForegroundColor Green
    Write-Host ""
}

function Remove-GeneratedFiles {
    Write-Header "Cleaning Generated Files"

    Write-Warning2 "This will remove all generated data and indexes."
    Write-Host "Files to be removed:"
    Write-Host "  - $DataDir\"
    Write-Host "  - $BuildDir\"
    Write-Host ""
    
    $response = Read-Host "Continue? (y/N)"
    if ($response -eq 'y' -or $response -eq 'Y') {
        if (Test-Path $DataDir) {
            Remove-Item -Path $DataDir -Recurse -Force
        }
        if (Test-Path $BuildDir) {
            Remove-Item -Path $BuildDir -Recurse -Force
        }
        Write-Success "Cleaned successfully"
    }
    else {
        Write-Info "Cleanup cancelled"
    }
}

function Show-Help {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║   Dynamic Road Network - Complete Setup Script                    ║" -ForegroundColor Cyan
    Write-Host "║   Features: Optimized Edge Matching, R-tree Indexing, Caching     ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Show-Menu
    Write-Host "Traffic Data Modes:"
    Write-Host "  " -NoNewline
    Write-Host "-Mode flow" -ForegroundColor Yellow -NoNewline
    Write-Host "        Use only flow data (no incidents)"
    Write-Host "  " -NoNewline
    Write-Host "-Mode incidents" -ForegroundColor Yellow -NoNewline
    Write-Host "   Use only incidents (no flow)"
    Write-Host "  " -NoNewline
    Write-Host "-Mode both" -ForegroundColor Yellow -NoNewline
    Write-Host "        Use both flow and incidents (default)"
    Write-Host "  " -NoNewline
    Write-Host "-Mode synthetic" -ForegroundColor Yellow -NoNewline
    Write-Host "   Use synthetic data (no HERE API)"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Full" -ForegroundColor Green -NoNewline
    Write-Host "              # Complete workflow with optimized matching"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -CondaSetup" -ForegroundColor Green -NoNewline
    Write-Host "          # Setup conda environment"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Full -Mode flow" -ForegroundColor Green -NoNewline
    Write-Host "   # Build & run with flow data only"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Build" -ForegroundColor Green -NoNewline
    Write-Host "             # Compile C++ only"
    Write-Host "  " -NoNewline
    Write-Host ".\setup.ps1 -Data -Mode synthetic" -ForegroundColor Green -NoNewline
    Write-Host "  # Generate synthetic data"
    Write-Host ""
    Write-Host "Optimized Matching Features:"
    Write-Host "  • R-tree spatial indexing for O(log n) edge lookup"
    Write-Host "  • Hausdorff distance for accurate shape matching"
    Write-Host "  • Persistent caching (18x speedup on re-run)"
    Write-Host "  • Handles dynamic HERE API segment ordering"
    Write-Host ""
}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

# Execute based on parameters
if ($Help) {
    Show-Help
}
elseif ($Full) {
    Invoke-FullSetup
}
elseif ($CondaSetup) {
    Create-CondaEnvironment | Out-Null
}
elseif ($Build) {
    Test-Requirements
    Write-Header "Building C++ Algorithms"
    if (!(Build-DHL)) { exit 1 }
    if (!(Build-HC2L)) { exit 1 }
    Write-Success "Build complete"
}
elseif ($Data) {
    # Create directories
    $dirs = @(
        (Join-Path $DataDir "raw"),
        $ProcessedDataDir,
        $DisruptionsDir,
        (Join-Path $MainDir "cache")
    )
    foreach ($dir in $dirs) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    Push-Location $ProjectRoot
    try {
        # Determine Python command
        $CondaPython = Join-Path $ProjectRoot ".conda\Scripts\python.exe"
        if (Test-Path $CondaPython) {
            $PythonCmd = $CondaPython
        }
        elseif (Get-Command python -ErrorAction SilentlyContinue) {
            $PythonCmd = "python"
        }
        else {
            $PythonCmd = "python3"
        }
        
        Write-Info "Generating traffic data with mode: $Mode"
        Write-Info "Using hash-based matching system (90x faster)"
        & $PythonCmd unified_data_generator.py --mode $Mode
        if ($LASTEXITCODE -ne 0) { exit 1 }
    }
    finally {
        Pop-Location
    }
}
elseif ($Indexes) {
    if (!(Build-Indexes)) { exit 1 }
}
elseif ($Server) {
    Start-Server
}
elseif ($Clean) {
    Remove-GeneratedFiles
}
else {
    Show-Help
}

exit 0
