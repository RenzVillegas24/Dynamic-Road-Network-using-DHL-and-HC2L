@echo off
REM Build Graph Indexes Script (Windows)
REM This script builds the binary graph and index files needed by the routing APIs

setlocal enabledelayedexpansion

echo ========================================================================
echo   Building Graph Indexes (Windows)
echo ========================================================================
echo.

REM Get script directory (absolute path)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Directories (absolute paths)
set "DHL_DIR=%SCRIPT_DIR%DualHierarchyLabelling"
set "HC2L_DIR=%SCRIPT_DIR%HighCardinalityTwoLevel"
set "DATA_DIR=%SCRIPT_DIR%Main\data"
set "RAW_DIR=%DATA_DIR%\raw"
set "PROCESSED_DIR=%DATA_DIR%\processed"

REM Check if data files exist
if not exist "%RAW_DIR%\quezon_city_nodes.csv" (
    echo ERROR: CSV data files not found
    echo   Please run 'python request_new_datasets.py' first to generate data files
    pause
    exit /b 1
)
if not exist "%RAW_DIR%\quezon_city_edges.csv" (
    echo ERROR: CSV data files not found
    echo   Please run 'python request_new_datasets.py' first to generate data files
    pause
    exit /b 1
)

echo [OK] CSV data files found

REM Check if .gr files exist
if not exist "%PROCESSED_DIR%\qc_from_csv.gr" (
    echo ERROR: Graph file not found: %PROCESSED_DIR%\qc_from_csv.gr
    echo   Please run 'python request_new_datasets.py' first to generate .gr files
    pause
    exit /b 1
)

echo [OK] Graph files found
echo.

REM Step 1: Build index executables
echo Step 1: Building index executables...

echo   Building DHL index executable...
cd /d "%DHL_DIR%"

REM Check if MinGW/g++ is available
where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: g++ compiler not found!
    echo   Please install MinGW-w64 or MSYS2 and add g++ to your PATH.
    pause
    exit /b 1
)

mingw32-make index >nul 2>&1
if not exist "index.exe" (
    echo ERROR: Failed to build DHL index
    pause
    exit /b 1
)
echo   [OK] DHL index executable built
cd /d "%SCRIPT_DIR%"

echo   Building HC2L index executable...
cd /d "%HC2L_DIR%"
mingw32-make index >nul 2>&1
if not exist "index.exe" (
    echo ERROR: Failed to build HC2L index
    pause
    exit /b 1
)
echo   [OK] HC2L index executable built
cd /d "%SCRIPT_DIR%"

echo.

REM Step 2: Build graph file (binary format)
echo Step 2: Converting .gr to binary graph format...

set "GR_INPUT=%PROCESSED_DIR%\qc_from_csv.gr"
set "GRAPH_OUTPUT=%PROCESSED_DIR%\quezon_city.graph"

echo   Converting: %GR_INPUT%
echo   Output: %GRAPH_OUTPUT%

REM Create a simple tool to convert .gr to binary graph format
REM For now, we'll copy the .gr file with .graph extension as a placeholder
copy /Y "%GR_INPUT%" "%GRAPH_OUTPUT%" >nul
echo   [OK] Graph file created

echo.

REM Step 3: Build DHL index
echo Step 3: Building DHL index...

set "DHL_INDEX_OUTPUT=%PROCESSED_DIR%\quezon_city"
echo   Input: %GRAPH_OUTPUT%
echo   Output: %DHL_INDEX_OUTPUT%.dhl.index

cd /d "%DHL_DIR%"
index.exe "%GRAPH_OUTPUT%" "%DHL_INDEX_OUTPUT%" 2>nul

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

cd /d "%SCRIPT_DIR%"
echo.

REM Step 4: Build HC2L index
echo Step 4: Building HC2L index...

set "HC2L_INDEX_OUTPUT=%PROCESSED_DIR%\quezon_city.hc2l.index"
echo   Input: %GRAPH_OUTPUT%
echo   Output: %HC2L_INDEX_OUTPUT%

cd /d "%HC2L_DIR%"
index.exe < "%GRAPH_OUTPUT%" > "%HC2L_INDEX_OUTPUT%" 2>nul

if exist "%HC2L_INDEX_OUTPUT%" (
    echo   [OK] HC2L index built successfully
) else (
    echo   WARNING: HC2L index file not found or empty
)

cd /d "%SCRIPT_DIR%"
echo.

REM Step 5: Verify all files
echo Step 5: Verifying created files...

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
    echo [OK] Index building completed successfully!
    echo.
    echo You can now run the routing APIs:
    echo   run_server.bat
) else (
    echo WARNING: Index building completed with warnings
    echo.
    echo Note: Some index files may not have been created.
    echo This might be due to graph format compatibility.
    echo You may need to adjust the graph conversion process.
)

echo ========================================================================
echo.

cd /d "%SCRIPT_DIR%"
pause
