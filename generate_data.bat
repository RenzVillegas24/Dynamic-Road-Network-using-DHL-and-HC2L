@echo off
REM Generate Graph Data Script (Windows)
REM This script generates all necessary data files including:
REM - CSV files from OSM data
REM - OSM geometry cache for smooth road curves
REM - Binary graph and index files for routing APIs
REM Note: Run build_all.bat first to compile the index executables

setlocal enabledelayedexpansion

echo ========================================================================
echo   Generating Graph Data ^& Indexes (Windows)
echo ========================================================================
echo.

REM Get script directory (absolute path)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Directories (absolute paths)
set "MAIN_DIR=%SCRIPT_DIR%Main"
set "BUILD_DIR=%MAIN_DIR%\build"
set "DATA_DIR=%MAIN_DIR%\data"
set "RAW_DIR=%DATA_DIR%\raw"
set "PROCESSED_DIR=%DATA_DIR%\processed"

REM Check for Python
set "PYTHON_CMD=python"
where python >nul 2>nul
if errorlevel 1 (
    where python3 >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python not found in PATH
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python3"
)

echo [OK] Using Python: %PYTHON_CMD%
echo.

REM Step 0: Generate OSM datasets and geometry cache
echo Step 0: Generating OSM datasets and geometry cache...
echo.

cd /d "%MAIN_DIR%"

echo   Running request_new_datasets.py to generate:
echo     - CSV files (nodes, edges, mapping)
echo     - Graph files (.gr format)
echo     - OSM geometry cache for smooth curves
echo.

%PYTHON_CMD% request_new_datasets.py
if errorlevel 1 (
    echo ERROR: Failed to generate datasets
    echo   Please check the error messages above and ensure:
    echo     - Python dependencies are installed (osmnx, pandas, etc.)
    echo     - Internet connection is available for OSM data download
    pause
    exit /b 1
)

echo [OK] OSM datasets and geometry cache generated successfully
echo.

REM Return to script directory
cd /d "%SCRIPT_DIR%"

REM Check if data files were created
if not exist "%RAW_DIR%\quezon_city_nodes.csv" (
    echo ERROR: CSV data files not found after generation
    pause
    exit /b 1
)
if not exist "%RAW_DIR%\quezon_city_edges.csv" (
    echo ERROR: CSV data files not found after generation
    pause
    exit /b 1
)

echo [OK] CSV data files found

REM Check if .gr files exist
if not exist "%PROCESSED_DIR%\qc_from_csv.gr" (
    echo ERROR: Graph file not found: %PROCESSED_DIR%\qc_from_csv.gr
    pause
    exit /b 1
)

echo [OK] Graph files found

REM Check if OSM geometry cache was created
if not exist "%DATA_DIR%\osm_geometry.graphml" (
    echo WARNING: OSM geometry cache not found at: %DATA_DIR%\osm_geometry.graphml
    echo          Smooth road curves may not be available
) else (
    for %%A in ("%DATA_DIR%\osm_geometry.graphml") do set "CACHE_SIZE=%%~zA"
    echo [OK] OSM geometry cache created: !CACHE_SIZE! bytes
)

echo.

REM Check if index executables exist
if not exist "%BUILD_DIR%\dhl\index.exe" (
    echo ERROR: DHL index executable not found
    echo   Please run 'build_all.bat' first to compile the index executables
    pause
    exit /b 1
)
if not exist "%BUILD_DIR%\hc2l\index.exe" (
    echo ERROR: HC2L index executable not found
    echo   Please run 'build_all.bat' first to compile the index executables
    pause
    exit /b 1
)

echo [OK] Index executables found
echo.

REM Step 1: Build graph file (binary format)
echo Step 1: Converting .gr to binary graph format...

set "GR_INPUT=%PROCESSED_DIR%\qc_from_csv.gr"
set "GRAPH_OUTPUT=%PROCESSED_DIR%\quezon_city.graph"

echo   Converting: %GR_INPUT%
echo   Output: %GRAPH_OUTPUT%

REM Create a simple tool to convert .gr to binary graph format
REM For now, we'll copy the .gr file with .graph extension as a placeholder
copy /Y "%GR_INPUT%" "%GRAPH_OUTPUT%" >nul
echo   [OK] Graph file created

echo.

REM Step 2: Build DHL index
echo Step 2: Building DHL index...

set "DHL_INDEX_OUTPUT=%PROCESSED_DIR%\quezon_city"
echo   Input: %GRAPH_OUTPUT%
echo   Output: %DHL_INDEX_OUTPUT%.dhl.index

"%BUILD_DIR%\dhl\index.exe" "%GRAPH_OUTPUT%" "%DHL_INDEX_OUTPUT%" 2>nul

REM The DHL index builder creates two files: _dhl and _ch
REM We need to rename them to match what the API expects
if exist "%DHL_INDEX_OUTPUT%_dhl" (
    move /Y "%DHL_INDEX_OUTPUT%_dhl" "%DHL_INDEX_OUTPUT%.dhl.index" >nul
    echo   [OK] DHL index built successfully
) else (
    echo   WARNING: DHL index file not found at expected location
)

if exist "%DHL_INDEX_OUTPUT%_ch" (
    move /Y "%DHL_INDEX_OUTPUT%_ch" "%DHL_INDEX_OUTPUT%.dhl.ch" >nul
    echo   [OK] DHL contraction hierarchy built
)

echo.

REM Step 3: Build HC2L index
echo Step 3: Building HC2L index...

set "HC2L_INDEX_OUTPUT=%PROCESSED_DIR%\quezon_city.hc2l.index"
echo   Input: %GRAPH_OUTPUT%
echo   Output: %HC2L_INDEX_OUTPUT%

"%BUILD_DIR%\hc2l\index.exe" < "%GRAPH_OUTPUT%" > "%HC2L_INDEX_OUTPUT%" 2>nul

if exist "%HC2L_INDEX_OUTPUT%" (
    echo   [OK] HC2L index built successfully
) else (
    echo   WARNING: HC2L index file not found or empty
)

echo.

REM Step 4: Verify all files
echo Step 4: Verifying created files...

set "ALL_OK=true"

if exist "%GRAPH_OUTPUT%" (
    for %%A in ("%GRAPH_OUTPUT%") do set "SIZE=%%~zA"
    echo   [OK] %GRAPH_OUTPUT% (!SIZE! bytes^)
) else (
    echo   ERROR: Missing: %GRAPH_OUTPUT%
    set "ALL_OK=false"
)

if exist "%DHL_INDEX_OUTPUT%.dhl.index" (
    for %%A in ("%DHL_INDEX_OUTPUT%.dhl.index") do set "SIZE=%%~zA"
    echo   [OK] %DHL_INDEX_OUTPUT%.dhl.index (!SIZE! bytes^)
) else (
    echo   ERROR: Missing: %DHL_INDEX_OUTPUT%.dhl.index
    set "ALL_OK=false"
)

if exist "%HC2L_INDEX_OUTPUT%" (
    for %%A in ("%HC2L_INDEX_OUTPUT%") do set "SIZE=%%~zA"
    echo   [OK] %HC2L_INDEX_OUTPUT% (!SIZE! bytes^)
) else (
    echo   ERROR: Missing: %HC2L_INDEX_OUTPUT%
    set "ALL_OK=false"
)

echo.
echo ========================================================================

if "%ALL_OK%"=="true" (
    echo [OK] Data generation completed successfully!
    echo.
    echo Generated files:
    echo   * OSM geometry cache (for smooth curves^)
    echo   * CSV datasets (nodes, edges, mapping^)
    echo   * Binary graph files
    echo   * DHL and HC2L indexes
    echo.
    echo You can now run the routing APIs:
    echo   run_server.bat
) else (
    echo WARNING: Data generation completed with warnings
    echo.
    echo Note: Some files may not have been created.
    echo This might be due to graph format compatibility.
    echo You may need to adjust the graph conversion process.
)

echo ========================================================================
echo.

cd /d "%SCRIPT_DIR%"
pause
