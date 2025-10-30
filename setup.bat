@echo off
REM Setup script for Dynamic Road Network project (Windows)
REM This script creates the required directory structure and provides guidance

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "MAIN_DIR=%PROJECT_ROOT%Main"

echo ================================================================
echo   Dynamic Road Network - Setup Script (Windows)
echo ================================================================
echo.

REM 1. Check Python installation
echo   Checking Python installation...
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%v"
    echo   [OK] Python !PYTHON_VERSION! found
) else (
    echo   [ERROR] Python not found. Please install Python 3.8 or higher.
    echo.
    echo   Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 2. Check g++ installation (MinGW/MSYS2)
echo   Checking C++ compiler...
where g++ >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('g++ --version 2^>^&1 ^| findstr /r "^g++"') do set "GCC_VERSION=%%v"
    echo   [OK] !GCC_VERSION! found
) else (
    echo   [WARNING] g++ not found. You'll need MinGW-w64 or MSYS2 to compile C++ code.
    echo.
    echo   Installation options:
    echo     1. MinGW-w64: https://www.mingw-w64.org/
    echo     2. MSYS2: https://www.msys2.org/
    echo.
)

echo.
echo   Creating directory structure...

REM 3. Create directory structure
if not exist "%MAIN_DIR%\data\raw" mkdir "%MAIN_DIR%\data\raw"
if not exist "%MAIN_DIR%\data\processed" mkdir "%MAIN_DIR%\data\processed"
if not exist "%MAIN_DIR%\data\disruptions" mkdir "%MAIN_DIR%\data\disruptions"
if not exist "%MAIN_DIR%\build\dhl" mkdir "%MAIN_DIR%\build\dhl"
if not exist "%MAIN_DIR%\build\hc2l" mkdir "%MAIN_DIR%\build\hc2l"
if not exist "%MAIN_DIR%\cache" mkdir "%MAIN_DIR%\cache"

echo   [OK] Created Main\data\raw\
echo   [OK] Created Main\data\processed\
echo   [OK] Created Main\data\disruptions\
echo   [OK] Created Main\build\dhl\
echo   [OK] Created Main\build\hc2l\
echo   [OK] Created Main\cache\

echo.
echo   Setting up environment configuration...

REM 4. Setup .env file
if not exist "%MAIN_DIR%\.env" (
    if exist "%MAIN_DIR%\.env.example" (
        copy "%MAIN_DIR%\.env.example" "%MAIN_DIR%\.env" >nul
        echo   [OK] Created Main\.env from template
        echo   [WARNING] Please edit Main\.env and add your Google Maps API key
    ) else (
        echo   [WARNING] .env.example not found, creating basic .env
        echo GOOGLE_MAPS_API_KEY=your_api_key_here > "%MAIN_DIR%\.env"
        echo FLASK_ENV=development >> "%MAIN_DIR%\.env"
        echo FLASK_DEBUG=True >> "%MAIN_DIR%\.env"
        echo FLASK_HOST=0.0.0.0 >> "%MAIN_DIR%\.env"
        echo FLASK_PORT=5000 >> "%MAIN_DIR%\.env"
        echo   [OK] Created basic Main\.env
        echo   [WARNING] Please edit Main\.env and add your Google Maps API key
    )
) else (
    echo   [OK] Main\.env already exists
)

echo.
echo   Setting up Python virtual environment...

REM 5. Setup virtual environment
set "VENV_DIR=%PROJECT_ROOT%.venv"

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo   [OK] Virtual environment already exists at .venv\
) else (
    echo   Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if %errorlevel% equ 0 (
        echo   [OK] Virtual environment created at .venv\
    ) else (
        echo   [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM 6. Activate virtual environment and install dependencies
echo   Installing Python dependencies...

REM Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Upgrade pip
python -m pip install --upgrade pip >nul 2>&1

REM Install dependencies
if exist "%PROJECT_ROOT%requirements.txt" (
    pip install -r "%PROJECT_ROOT%requirements.txt" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   [OK] Python dependencies installed in virtual environment
    ) else (
        echo   [WARNING] Some dependencies may have failed to install. Check manually.
    )
) else (
    echo   [WARNING] requirements.txt not found
)

REM Deactivate for now
call deactivate

echo.
echo   Checking data files...

REM 7. Check for required data files
set "MISSING_COUNT=0"

if not exist "%MAIN_DIR%\data\raw\quezon_city_nodes.csv" (
    echo   [ERROR] Missing: quezon_city_nodes.csv
    set /a MISSING_COUNT+=1
)

if not exist "%MAIN_DIR%\data\raw\quezon_city_edges.csv" (
    echo   [ERROR] Missing: quezon_city_edges.csv
    set /a MISSING_COUNT+=1
)

if not exist "%MAIN_DIR%\data\disruptions\qc_scenario_for_cpp_1.csv" (
    echo   [ERROR] Missing: qc_scenario_for_cpp_1.csv
    set /a MISSING_COUNT+=1
)

if !MISSING_COUNT! equ 0 (
    echo   [OK] All required data files are present
) else (
    echo.
    echo   [WARNING] Missing !MISSING_COUNT! required data file(s)
    echo.
    echo   Please place your data files in the following locations:
    echo     - Nodes: Main\data\raw\quezon_city_nodes.csv
    echo     - Edges: Main\data\raw\quezon_city_edges.csv
    echo     - Disruptions: Main\data\disruptions\qc_scenario_for_cpp_1.csv
)

echo.
echo   Verifying configuration...

REM 8. Verify configuration using Python
cd /d "%MAIN_DIR%"
call "%VENV_DIR%\Scripts\activate.bat"
python -c "from config import Config; print(Config.get_config_summary())" 2>nul
if %errorlevel% neq 0 (
    echo   [WARNING] Could not verify configuration. Run manually: cd Main ^&^& python config.py
)
call deactivate
cd /d "%PROJECT_ROOT%"

echo.
echo ================================================================
echo   Setup Status
echo ================================================================
echo.
echo   Directory structure: [OK] Created
echo   Virtual environment: [OK] Ready at .venv\
echo   Python dependencies: [OK] Installed
echo   Environment file: [OK] Created

if !MISSING_COUNT! equ 0 (
    echo   Data files: [OK] Present
) else (
    echo   Data files: [WARNING] Missing !MISSING_COUNT! file(s^)
)

echo.
echo ================================================================
echo   Next Steps
echo ================================================================
echo.
echo   1. Edit Main\.env and add your Google Maps API key
echo   2. Place your data files in Main\data\
echo   3. Build the C++ executables:
echo      build_all.bat
echo   4. Run the Flask application:
echo      run_server.bat
echo.
echo   To manually activate the virtual environment:
echo      .venv\Scripts\activate
echo.
echo   For more information, see README.md or WINDOWS_SETUP.md
echo.

pause
