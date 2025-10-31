@echo off
REM Flask Server Runner Script (Windows)
REM This script starts the Flask application with proper configuration
REM
REM Usage:
REM   run_server.bat              - Interactive mode
REM   run_server.bat --generate   - Auto-generate data and indexes
REM   run_server.bat --skip       - Skip data checks and start server

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "MAIN_DIR=%SCRIPT_DIR%Main"

REM Parse command-line arguments
set "AUTO_GENERATE=false"
set "SKIP_CHECKS=false"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--generate" (
    set "AUTO_GENERATE=true"
    shift
    goto parse_args
)
if /i "%~1"=="--skip" (
    set "SKIP_CHECKS=true"
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    echo Usage: %~nx0 [OPTIONS]
    echo.
    echo Options:
    echo   --generate    Automatically generate data and build indexes if missing
    echo   --skip        Skip data checks and start server anyway
    echo   --help        Show this help message
    echo.
    exit /b 0
)
echo Unknown option: %~1
echo Use --help for usage information
exit /b 1

:args_done

echo ========================================================================
echo   Dynamic Road Network - Flask Server (Windows)
echo ========================================================================
echo.

REM Check if .env exists
if not exist "%MAIN_DIR%\.env" (
    echo   ERROR: Main\.env file not found
    echo.
    echo   Please configure your environment first:
    echo     1. Copy Main\.env.example to Main\.env
    echo     2. Add your Google Maps API key
    echo.
    pause
    exit /b 1
)

REM Check if data files exist
set "DATA_EXISTS=true"
if not exist "%MAIN_DIR%\data\raw\quezon_city_nodes.csv" set "DATA_EXISTS=false"
if not exist "%MAIN_DIR%\data\raw\quezon_city_edges.csv" set "DATA_EXISTS=false"

REM Check if index files exist
set "INDEX_EXISTS=true"
if not exist "%MAIN_DIR%\data\processed\quezon_city.graph" set "INDEX_EXISTS=false"
if not exist "%MAIN_DIR%\data\processed\quezon_city.dhl.index" set "INDEX_EXISTS=false"
if not exist "%MAIN_DIR%\data\processed\quezon_city.hc2l.index" set "INDEX_EXISTS=false"

REM Offer to generate data if missing
if "%DATA_EXISTS%"=="false" goto check_missing
if "%INDEX_EXISTS%"=="false" goto check_missing
goto start_server

:check_missing
if "%SKIP_CHECKS%"=="true" (
    echo   WARNING: Data or index files are missing (--skip mode^)
    echo.
    goto start_server
)

if "%AUTO_GENERATE%"=="true" (
    echo   Auto-generating data and indexes (--generate mode^)...
    call :generate_data
    goto start_server
)

echo   WARNING: Data or index files are missing
echo.
if "%DATA_EXISTS%"=="false" (
    echo     Missing: CSV data files (quezon_city_nodes.csv, quezon_city_edges.csv^)
)
if "%INDEX_EXISTS%"=="false" (
    echo     Missing: Graph index files (.graph, .dhl.index, .hc2l.index^)
)
echo.
echo   Would you like to:
echo     1^) Generate data and build indexes now (recommended, takes 15-20 min^)
echo     2^) Build indexes only (if CSV files already exist^)
echo     3^) Continue without data (server will start but routing won't work^)
echo     4^) Exit
echo.
set /p "choice=  Enter your choice (1-4): "
echo.

if "%choice%"=="1" (
    call :generate_data
    goto start_server
)
if "%choice%"=="2" (
    if "%DATA_EXISTS%"=="false" (
        echo   ERROR: Cannot build indexes without CSV data files
        pause
        exit /b 1
    )
    echo ========================================================================
    echo   Building Graph Indexes
    echo ========================================================================
    echo.
    call "%SCRIPT_DIR%generate_data.bat"
    if errorlevel 1 (
        echo.
        echo   ERROR: Index building failed
        pause
        exit /b 1
    )
    echo.
    echo   Index building completed!
    echo.
    goto start_server
)
if "%choice%"=="3" (
    echo   WARNING: Continuing without data - routing will not work!
    echo.
    goto start_server
)
if "%choice%"=="4" (
    echo   Exiting...
    exit /b 0
)
echo   Invalid choice. Exiting...
pause
exit /b 1

:start_server
echo   Starting Flask server...
echo.

REM Change to Main directory
cd /d "%MAIN_DIR%"

REM Check if virtual environment exists and activate it
set "ENV_NAME=roadnet"
set "CONDA_ENV_PATH=%SCRIPT_DIR%.conda"
if exist "%CONDA_ENV_PATH%" (
    echo   Activating conda environment at .conda\...
    call conda activate "%CONDA_ENV_PATH%"
) else (
    conda env list | findstr /C:"%ENV_NAME%" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Activating conda environment "%ENV_NAME%"...
        call conda activate %ENV_NAME%
    ) else if exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
        echo   Activating virtual environment...
        call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    )
)

REM Run Flask server
python flask_server.py

REM Deactivate virtual environment on exit
if exist "%SCRIPT_DIR%.venv\Scripts\deactivate.bat" (
    call "%SCRIPT_DIR%.venv\Scripts\deactivate.bat"
)

cd /d "%SCRIPT_DIR%"
goto :eof

:generate_data
echo.
echo ========================================================================
echo   Step 1: Generating OSM Data (15-20 minutes^)
echo ========================================================================
echo.

REM Activate virtual environment if it exists
set "ENV_NAME=roadnet"
set "CONDA_ENV_PATH=%SCRIPT_DIR%.conda"
if exist "%CONDA_ENV_PATH%" (
    call conda activate "%CONDA_ENV_PATH%"
) else (
    conda env list | findstr /C:"%ENV_NAME%" >nul 2>&1
    if %errorlevel% equ 0 (
        call conda activate %ENV_NAME%
    ) else if exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
        call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
    )
)

cd /d "%MAIN_DIR%"
python request_new_datasets.py

if errorlevel 1 (
    echo.
    echo   ERROR: Data generation failed
    pause
    exit /b 1
)

cd /d "%SCRIPT_DIR%"

echo.
echo ========================================================================
echo   Step 2: Building Graph Indexes
echo ========================================================================
echo.

call "%SCRIPT_DIR%generate_data.bat"

if errorlevel 1 (
    echo.
    echo   ERROR: Index building failed
    pause
    exit /b 1
)

echo.
echo   Data generation and index building completed!
echo.
goto :eof
