@echo off
REM ################################################################################
REM # Dynamic Road Network - Complete Setup Script (Windows Batch)
REM ################################################################################
REM # This script handles the complete workflow:
REM # 1. Setup & validation
REM # 2. Build C++ algorithms (DHL and HC2L)
REM # 3. Generate data (network + traffic scenarios)
REM # 4. Build indexes
REM # 5. Run the Flask web server with real-time traffic updates
REM #
REM # Usage:
REM #   setup.bat                    # Interactive menu
REM #   setup.bat --build            # Build only
REM #   setup.bat --data             # Generate data only
REM #   setup.bat --full             # Complete setup
REM #   setup.bat --server           # Run server only
REM #   setup.bat --clean            # Remove generated files
REM ################################################################################

setlocal enabledelayedexpansion

REM Script metadata
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "MAIN_DIR=%PROJECT_ROOT%Main"
set "BUILD_DIR=%MAIN_DIR%\build"
set "DATA_DIR=%MAIN_DIR%\data"
set "PROCESSED_DATA_DIR=%DATA_DIR%\processed"
set "DISRUPTIONS_DIR=%DATA_DIR%\disruptions"

REM Default mode
set "MODE=both"
set "ACTION=menu"

REM Parse command line arguments
:parse_args
if "%~1"=="" goto execute
if /i "%~1"=="--full" set "ACTION=full" & shift & goto parse_args
if /i "%~1"=="--build" set "ACTION=build" & shift & goto parse_args
if /i "%~1"=="--data" set "ACTION=data" & shift & goto parse_args
if /i "%~1"=="--indexes" set "ACTION=indexes" & shift & goto parse_args
if /i "%~1"=="--server" set "ACTION=server" & shift & goto parse_args
if /i "%~1"=="--clean" set "ACTION=clean" & shift & goto parse_args
if /i "%~1"=="--help" set "ACTION=help" & shift & goto parse_args
if /i "%~1"=="-h" set "ACTION=help" & shift & goto parse_args
if /i "%~1"=="--flow" set "MODE=flow" & shift & goto parse_args
if /i "%~1"=="--incidents" set "MODE=incidents" & shift & goto parse_args
if /i "%~1"=="--both" set "MODE=both" & shift & goto parse_args
if /i "%~1"=="--synthetic" set "MODE=synthetic" & shift & goto parse_args
echo Unknown option: %~1
call :show_help
exit /b 1

:execute
if "%ACTION%"=="help" call :show_help & exit /b 0
if "%ACTION%"=="full" call :run_full_setup & exit /b %errorlevel%
if "%ACTION%"=="build" call :build_only & exit /b %errorlevel%
if "%ACTION%"=="data" call :data_only & exit /b %errorlevel%
if "%ACTION%"=="indexes" call :indexes_only & exit /b %errorlevel%
if "%ACTION%"=="server" call :run_server & exit /b %errorlevel%
if "%ACTION%"=="clean" call :clean_files & exit /b %errorlevel%
if "%ACTION%"=="menu" call :show_help & exit /b 0
exit /b 0

REM ============================================================================
REM HELPER FUNCTIONS
REM ============================================================================

:print_header
echo.
echo ================================================================
echo %~1
echo ================================================================
echo.
exit /b 0

:print_success
echo [92m[OK] %~1[0m
exit /b 0

:print_info
echo [96m[INFO] %~1[0m
exit /b 0

:print_warning
echo [93m[WARN] %~1[0m
exit /b 0

:print_error
echo [91m[ERROR] %~1[0m
exit /b 0

:show_help
echo.
echo ╔═══════════════════════════════════════════════════════════════════╗
echo ║   Dynamic Road Network - Complete Setup Script (Windows)          ║
echo ║   Features: Optimized Edge Matching, R-tree Indexing, Caching     ║
echo ╚═══════════════════════════════════════════════════════════════════╝
echo.
echo Available commands:
echo   setup.bat --full        Complete setup (build + data + indexes + server)
echo   setup.bat --build       Build C++ algorithms only
echo   setup.bat --data        Generate traffic data and base network
echo   setup.bat --indexes     Build routing indexes
echo   setup.bat --server      Run Flask web server
echo   setup.bat --clean       Remove all generated files
echo   setup.bat --help        Show this help message
echo.
echo Traffic Data Modes:
echo   --flow        Use only flow data (no incidents)
echo   --incidents   Use only incidents (no flow)
echo   --both        Use both flow and incidents (default)
echo   --synthetic   Use synthetic data (no HERE API)
echo.
echo Examples:
echo   setup.bat --full              # Complete workflow
echo   setup.bat --full --flow       # Build with flow data only
echo   setup.bat --build             # Compile C++ only
echo   setup.bat --data --synthetic  # Generate synthetic data
echo.
echo Note: For better experience on Windows, consider using setup.ps1 (PowerShell)
echo.
exit /b 0

:check_requirements
call :print_header "Step 1/5: Checking Requirements"

REM Check for C++ compiler
where g++ >nul 2>&1
if %errorlevel% equ 0 (
    set "CPP_COMPILER=g++"
    call :print_success "g++ compiler found (MinGW)"
    goto check_python
)

where cl >nul 2>&1
if %errorlevel% equ 0 (
    set "CPP_COMPILER=cl"
    call :print_success "MSVC compiler found"
    goto check_python
)

where clang++ >nul 2>&1
if %errorlevel% equ 0 (
    set "CPP_COMPILER=clang++"
    call :print_success "clang++ compiler found"
    goto check_python
)

call :print_error "C++ compiler not found!"
echo.
echo Please install one of the following:
echo   1. MinGW-w64: https://www.mingw-w64.org/
echo   2. Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/
echo   3. LLVM/Clang: https://releases.llvm.org/
echo.
exit /b 1

:check_python
REM Check Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%i"
    call :print_success "!PYTHON_VERSION! found"
    goto create_dirs
)

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do set "PYTHON_VERSION=%%i"
    call :print_success "!PYTHON_VERSION! found"
    goto create_dirs
)

call :print_error "Python not found!"
echo.
echo Please install Python 3.8 or higher:
echo   Download from: https://www.python.org/downloads/
echo   Make sure to check 'Add Python to PATH' during installation
echo.
exit /b 1

:create_dirs
REM Create necessary directories
if not exist "%BUILD_DIR%\dhl" mkdir "%BUILD_DIR%\dhl"
if not exist "%BUILD_DIR%\hc2l" mkdir "%BUILD_DIR%\hc2l"
if not exist "%DATA_DIR%\raw" mkdir "%DATA_DIR%\raw"
if not exist "%PROCESSED_DATA_DIR%" mkdir "%PROCESSED_DATA_DIR%"
if not exist "%DISRUPTIONS_DIR%" mkdir "%DISRUPTIONS_DIR%"
if not exist "%MAIN_DIR%\cache" mkdir "%MAIN_DIR%\cache"
call :print_success "Data directories created"
exit /b 0

:build_dhl
call :print_header "Building DHL (Dual-Hierarchy Labelling)"

pushd "%PROJECT_ROOT%DualHierarchyLabelling"

REM Build routing API
call :print_info "Compiling DHL routing API..."
if "%CPP_COMPILER%"=="g++" (
    g++ -std=c++2a -O3 -Wall -Wextra -pthread -o "%BUILD_DIR%\dhl\dhl_routing_api.exe" src\dhl_routing_api.cpp src\road_network.cpp src\util.cpp
) else if "%CPP_COMPILER%"=="clang++" (
    clang++ -std=c++2a -O3 -Wall -Wextra -o "%BUILD_DIR%\dhl\dhl_routing_api.exe" src\dhl_routing_api.cpp src\road_network.cpp src\util.cpp
) else (
    cl /std:c++20 /O2 /EHsc /Fe:"%BUILD_DIR%\dhl\dhl_routing_api.exe" src\dhl_routing_api.cpp src\road_network.cpp src\util.cpp
)

if %errorlevel% neq 0 (
    call :print_error "DHL routing API compilation failed!"
    popd
    exit /b 1
)
call :print_success "DHL routing API compiled"

REM Build index executable
call :print_info "Compiling DHL index builder..."
if "%CPP_COMPILER%"=="g++" (
    g++ -std=c++2a -O3 -Wall -Wextra -pthread -o "%BUILD_DIR%\dhl\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
) else if "%CPP_COMPILER%"=="clang++" (
    clang++ -std=c++2a -O3 -Wall -Wextra -o "%BUILD_DIR%\dhl\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
) else (
    cl /std:c++20 /O2 /EHsc /Fe:"%BUILD_DIR%\dhl\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
)

if %errorlevel% neq 0 (
    call :print_error "DHL index builder compilation failed!"
    popd
    exit /b 1
)
call :print_success "DHL index builder compiled"

popd
exit /b 0

:build_hc2l
call :print_header "Building HC2L (Hierarchical Cut 2-Hop Labelling)"

pushd "%PROJECT_ROOT%HierarchicalCutLabelling"

REM Build routing API
call :print_info "Compiling HC2L routing API..."
if "%CPP_COMPILER%"=="g++" (
    g++ -std=c++20 -O3 -Wall -Wextra -o "%BUILD_DIR%\hc2l\hc2l_routing_api.exe" src\hc2l_routing_api.cpp src\road_network.cpp src\util.cpp
) else if "%CPP_COMPILER%"=="clang++" (
    clang++ -std=c++20 -O3 -Wall -Wextra -o "%BUILD_DIR%\hc2l\hc2l_routing_api.exe" src\hc2l_routing_api.cpp src\road_network.cpp src\util.cpp
) else (
    cl /std:c++20 /O2 /EHsc /Fe:"%BUILD_DIR%\hc2l\hc2l_routing_api.exe" src\hc2l_routing_api.cpp src\road_network.cpp src\util.cpp
)

if %errorlevel% neq 0 (
    call :print_error "HC2L routing API compilation failed!"
    popd
    exit /b 1
)
call :print_success "HC2L routing API compiled"

REM Build index executable
call :print_info "Compiling HC2L index builder..."
if "%CPP_COMPILER%"=="g++" (
    g++ -std=c++20 -O3 -Wall -Wextra -o "%BUILD_DIR%\hc2l\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
) else if "%CPP_COMPILER%"=="clang++" (
    clang++ -std=c++20 -O3 -Wall -Wextra -o "%BUILD_DIR%\hc2l\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
) else (
    cl /std:c++20 /O2 /EHsc /Fe:"%BUILD_DIR%\hc2l\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
)

if %errorlevel% neq 0 (
    call :print_error "HC2L index builder compilation failed!"
    popd
    exit /b 1
)
call :print_success "HC2L index builder compiled"

popd
exit /b 0

:generate_data
call :print_header "Step 2/5: Generating Traffic Data & Network"

pushd "%PROJECT_ROOT%"

call :print_info "Generating traffic data using hash-based matching..."
call :print_info "Mode: %MODE% (flow/incidents/both)"

%PYTHON_CMD% unified_data_generator.py --mode %MODE%

if %errorlevel% neq 0 (
    call :print_error "Traffic data generation failed!"
    popd
    exit /b 1
)

call :print_success "Traffic data generation complete"
call :print_info "Output files:"
echo   - Traffic CSV: %DISRUPTIONS_DIR%\current_traffic_%MODE%.csv
echo   - Traffic GR: %DISRUPTIONS_DIR%\current_traffic_%MODE%.gr
echo   - Matched edges: Main\here_osm\matched_edges.csv

popd
exit /b 0

:build_indexes
call :print_header "Step 3/5: Building Routing Indexes"

pushd "%MAIN_DIR%"

REM Check if graph files exist
if not exist "%PROCESSED_DATA_DIR%\quezon_city.graph" (
    call :print_warning "Graph file not found. Have you run data generation?"
    popd
    exit /b 1
)

REM Build DHL index
call :print_info "Building DHL index..."
"%BUILD_DIR%\dhl\index.exe" "%PROCESSED_DATA_DIR%\quezon_city.graph" "%PROCESSED_DATA_DIR%\quezon_city"

if %errorlevel% equ 0 (
    call :print_success "DHL index built"
    call :print_info "  - DHL index: %PROCESSED_DATA_DIR%\quezon_city_dhl"
    call :print_info "  - CH data:   %PROCESSED_DATA_DIR%\quezon_city_ch"
) else (
    call :print_error "DHL index build failed!"
    popd
    exit /b 1
)

REM Build HC2L index
call :print_info "Building HC2L index..."
type "%PROCESSED_DATA_DIR%\quezon_city.graph" | "%BUILD_DIR%\hc2l\index.exe" > "%PROCESSED_DATA_DIR%\quezon_city.hc2l.index"

if %errorlevel% equ 0 (
    call :print_success "HC2L index built"
    call :print_info "  - HC2L index: %PROCESSED_DATA_DIR%\quezon_city.hc2l.index"
) else (
    call :print_error "HC2L index build failed!"
    popd
    exit /b 1
)

call :print_success "All indexes built successfully"
call :print_info "Index files created in: %PROCESSED_DATA_DIR%\"

popd
exit /b 0

:run_server
call :print_header "Step 5/5: Starting Flask Server"

pushd "%MAIN_DIR%"

call :print_info "Cleaning up any existing processes..."
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *flask_server.py*" 2>nul
timeout /t 1 /nobreak >nul

call :print_info "Starting Flask web server..."
call :print_info "Server URL: http://localhost:5000"
call :print_info "Press Ctrl+C to stop"
echo.

%PYTHON_CMD% flask_server.py

popd
exit /b 0

:run_full_setup
call :print_header "DYNAMIC ROAD NETWORK - COMPLETE SETUP"

REM Step 1: Check requirements
call :check_requirements
if %errorlevel% neq 0 exit /b 1

REM Step 2: Build C++ algorithms
call :print_header "Step 2/5: Building C++ Algorithms"
call :build_dhl
if %errorlevel% neq 0 exit /b 1
call :build_hc2l
if %errorlevel% neq 0 exit /b 1
call :print_success "All algorithms compiled successfully"

REM Step 3: Generate data
call :generate_data
if %errorlevel% neq 0 exit /b 1

REM Step 4: Build indexes
call :build_indexes
if %errorlevel% neq 0 exit /b 1

REM Success
call :print_header "SETUP COMPLETE!"
echo The system is ready to use!
echo.
echo Next step: Run the server
echo   setup.bat --server
echo.
exit /b 0

:build_only
call :check_requirements
if %errorlevel% neq 0 exit /b 1
call :print_header "Building C++ Algorithms"
call :build_dhl
if %errorlevel% neq 0 exit /b 1
call :build_hc2l
if %errorlevel% neq 0 exit /b 1
call :print_success "Build complete"
exit /b 0

:data_only
if not exist "%DATA_DIR%\raw" mkdir "%DATA_DIR%\raw"
if not exist "%PROCESSED_DATA_DIR%" mkdir "%PROCESSED_DATA_DIR%"
if not exist "%DISRUPTIONS_DIR%" mkdir "%DISRUPTIONS_DIR%"
if not exist "%MAIN_DIR%\cache" mkdir "%MAIN_DIR%\cache"

pushd "%PROJECT_ROOT%"

REM Determine Python command
if exist "%PROJECT_ROOT%\.conda\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%\.conda\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=python"
    ) else (
        set "PYTHON_CMD=python3"
    )
)

call :print_info "Generating traffic data with mode: %MODE%"
call :print_info "Using hash-based matching system (90x faster)"
%PYTHON_CMD% unified_data_generator.py --mode %MODE%

popd
exit /b %errorlevel%

:indexes_only
call :build_indexes
exit /b %errorlevel%

:clean_files
call :print_header "Cleaning Generated Files"

call :print_warning "This will remove all generated data and indexes."
echo Files to be removed:
echo   - %DATA_DIR%\
echo   - %BUILD_DIR%\
echo.
set /p "CONFIRM=Continue? (y/N) "
if /i "%CONFIRM%"=="y" (
    if exist "%DATA_DIR%" rmdir /s /q "%DATA_DIR%"
    if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
    call :print_success "Cleaned successfully"
) else (
    call :print_info "Cleanup cancelled"
)
exit /b 0
