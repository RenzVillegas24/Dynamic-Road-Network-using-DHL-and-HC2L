@echo off
REM All-in-One Setup Script for Dynamic Road Network (Windows)
REM Supports both automatic and manual setup with conda environment

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "MAIN_DIR=%PROJECT_ROOT%Main"
set "ENV_NAME=roadnet"
set "CONDA_ENV_PATH=%PROJECT_ROOT%.conda"

:main_menu
cls
echo ================================================================
echo   Dynamic Road Network - Setup Script (Windows)
echo ================================================================
echo.
echo Choose setup mode:
echo   1. Automatic Setup (Recommended - Does everything)
echo   2. Manual Setup (Step by step)
echo   3. Exit
echo.
set /p "setup_mode=Enter your choice (1-3): "
echo.

if "%setup_mode%"=="1" goto auto_setup
if "%setup_mode%"=="2" goto manual_menu
if "%setup_mode%"=="3" exit /b 0
echo Invalid choice.
timeout /t 2 >nul
goto main_menu

REM ================================================================
REM AUTOMATIC SETUP
REM ================================================================
:auto_setup
cls
echo ================================================================
echo   AUTOMATIC SETUP MODE
echo ================================================================
echo.
echo This will automatically:
echo   [1] Check prerequisites (Python, Conda, g++)
echo   [2] Create conda environment with all dependencies
echo   [3] Create directory structure
echo   [4] Setup .env configuration
echo   [5] Build C++ executables
echo   [6] Optionally generate data and indexes
echo.
pause
echo.

call :check_prerequisites
if %errorlevel% neq 0 goto end

call :create_conda_env
if %errorlevel% neq 0 goto end

call :create_directories

call :setup_env_file

call :build_executables

echo.
set /p "gen_data=Generate OSM data and build indexes now? (y/n): "
if /i "!gen_data!"=="y" (
    call :generate_data
)

echo.
echo ================================================================
echo   AUTOMATIC SETUP COMPLETE!
echo ================================================================
echo.
echo Your environment is ready! To start:
echo   1. Activate: conda activate .conda
echo   2. Run: run_server.bat
echo.
pause
goto end

REM ================================================================
REM MANUAL SETUP MENU
REM ================================================================
:manual_menu
cls
echo ================================================================
echo   MANUAL SETUP MODE
echo ================================================================
echo.
echo Choose an option:
echo   1. Create/Update Conda Environment
echo   2. Create Directory Structure
echo   3. Setup .env Configuration
echo   4. Build C++ Executables
echo   5. Generate Data and Indexes
echo   6. Check Installation Status
echo   7. Back to Main Menu
echo.
set /p "manual_choice=Enter your choice (1-7): "
echo.

if "%manual_choice%"=="1" (
    call :create_conda_env
    pause
    goto manual_menu
)
if "%manual_choice%"=="2" (
    call :create_directories
    pause
    goto manual_menu
)
if "%manual_choice%"=="3" (
    call :setup_env_file
    pause
    goto manual_menu
)
if "%manual_choice%"=="4" (
    call :build_executables
    pause
    goto manual_menu
)
if "%manual_choice%"=="5" (
    call :generate_data
    pause
    goto manual_menu
)
if "%manual_choice%"=="6" (
    call :check_status
    pause
    goto manual_menu
)
if "%manual_choice%"=="7" goto main_menu
echo Invalid choice.
timeout /t 2 >nul
goto manual_menu

REM ================================================================
REM FUNCTIONS
REM ================================================================

:check_prerequisites
echo [Step] Checking Prerequisites...
echo.

REM Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.8+ from https://www.python.org/
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo [OK] Python %%v found

REM Check Conda
where conda >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Conda not found. Install Miniconda from https://docs.conda.io/en/latest/miniconda.html
    exit /b 1
)
for /f "tokens=2" %%v in ('conda --version 2^>^&1') do echo [OK] Conda %%v found

REM Check g++
where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] g++ not found. You'll need MinGW or MSYS2 to build C++ executables.
    echo Download from: https://www.mingw-w64.org/ or https://www.msys2.org/
) else (
    for /f "tokens=*" %%v in ('g++ --version 2^>^&1 ^| findstr /r "^g++"') do echo [OK] %%v found
)

echo.
exit /b 0

:create_conda_env
echo ================================================================
echo   Creating Conda Environment
echo ================================================================
echo.

REM Check if environment.yml exists
if not exist "%PROJECT_ROOT%environment.yml" (
    echo [ERROR] environment.yml not found
    exit /b 1
)

REM Check if environment already exists
if exist "%CONDA_ENV_PATH%" (
    echo [INFO] Environment already exists at .conda\
    set /p "update_env=Update existing environment? (y/n): "
    if /i "!update_env!"=="y" (
        echo [INFO] Updating environment...
        conda env update -f "%PROJECT_ROOT%environment.yml" -p "%CONDA_ENV_PATH%"
        if %errorlevel% neq 0 (
            echo [ERROR] Failed to update environment
            exit /b 1
        )
        echo [OK] Environment updated
    )
) else (
    echo [INFO] Creating conda environment from environment.yml...
    echo Environment will be created at: .conda\
    echo This may take 5-10 minutes...
    echo.
    conda env create -f "%PROJECT_ROOT%environment.yml" -p "%CONDA_ENV_PATH%"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create environment
        exit /b 1
    )
    echo [OK] Environment created successfully at .conda\
)

echo.
echo Testing packages...
call conda activate "%CONDA_ENV_PATH%"
python -c "import pyogrio, geopandas, flask; print('[OK] All critical packages imported successfully')" 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Some packages may not be working correctly
)
echo.
exit /b 0

:create_directories
echo ================================================================
echo   Creating Directory Structure
echo ================================================================
echo.

if not exist "%MAIN_DIR%\data\raw" mkdir "%MAIN_DIR%\data\raw"
if not exist "%MAIN_DIR%\data\processed" mkdir "%MAIN_DIR%\data\processed"
if not exist "%MAIN_DIR%\data\disruptions" mkdir "%MAIN_DIR%\data\disruptions"
if not exist "%MAIN_DIR%\build\dhl" mkdir "%MAIN_DIR%\build\dhl"
if not exist "%MAIN_DIR%\build\hc2l" mkdir "%MAIN_DIR%\build\hc2l"
if not exist "%MAIN_DIR%\cache" mkdir "%MAIN_DIR%\cache"

echo [OK] Created Main\data\raw\
echo [OK] Created Main\data\processed\
echo [OK] Created Main\data\disruptions\
echo [OK] Created Main\build\dhl\
echo [OK] Created Main\build\hc2l\
echo [OK] Created Main\cache\
echo.
exit /b 0

:setup_env_file
echo ================================================================
echo   Setting up .env Configuration
echo ================================================================
echo.

if exist "%MAIN_DIR%\.env" (
    echo [INFO] .env file already exists
    set /p "overwrite=Overwrite existing .env? (y/n): "
    if /i not "!overwrite!"=="y" (
        echo [SKIP] Keeping existing .env file
        exit /b 0
    )
)

if exist "%MAIN_DIR%\.env.example" (
    copy "%MAIN_DIR%\.env.example" "%MAIN_DIR%\.env" >nul
    echo [OK] Created .env from template
) else (
    echo [INFO] Creating basic .env file
    (
        echo GOOGLE_MAPS_API_KEY=your_api_key_here
        echo FLASK_ENV=development
        echo FLASK_DEBUG=True
        echo FLASK_HOST=0.0.0.0
        echo FLASK_PORT=5000
    ) > "%MAIN_DIR%\.env"
    echo [OK] Created basic .env file
)

echo.
echo [IMPORTANT] Please edit Main\.env and add your Google Maps API key
set /p "edit_now=Open .env file now? (y/n): "
if /i "!edit_now!"=="y" (
    notepad "%MAIN_DIR%\.env"
)
echo.
exit /b 0

:build_executables
echo ================================================================
echo   Building C++ Executables
echo ================================================================
echo.

where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] g++ not found. Cannot build executables.
    echo Install MinGW or MSYS2, then try again.
    exit /b 1
)

if exist "%PROJECT_ROOT%build_all.bat" (
    call "%PROJECT_ROOT%build_all.bat"
    if %errorlevel% neq 0 (
        echo [ERROR] Build failed
        exit /b 1
    )
    echo [OK] Executables built successfully
) else (
    echo [ERROR] build_all.bat not found
    exit /b 1
)
echo.
exit /b 0

:generate_data
echo ================================================================
echo   Generating Data and Indexes
echo ================================================================
echo.
echo This process takes 15-20 minutes and requires:
echo   - Active internet connection
echo   - Conda environment activated
echo.
set /p "confirm=Continue? (y/n): "
if /i not "!confirm!"=="y" exit /b 0

echo.
echo [Step 1/3] Activating conda environment...
call conda activate "%CONDA_ENV_PATH%"

echo [Step 2/3] Generating OSM data (this takes time)...
cd /d "%MAIN_DIR%"
python request_new_datasets.py
if %errorlevel% neq 0 (
    echo [ERROR] Data generation failed
    cd /d "%PROJECT_ROOT%"
    exit /b 1
)

cd /d "%PROJECT_ROOT%"
echo [Step 3/3] Building indexes...
call generate_indexes.bat
if %errorlevel% neq 0 (
    echo [ERROR] Index building failed
    exit /b 1
)

echo.
echo [OK] Data generation and indexing complete!
echo.
exit /b 0

:check_status
echo ================================================================
echo   Installation Status
echo ================================================================
echo.

REM Check conda environment
if exist "%CONDA_ENV_PATH%" (
    echo [OK] Conda environment exists at .conda\
) else (
    conda env list | findstr /C:"%ENV_NAME%" >nul 2>&1
    if %errorlevel% equ 0 (
        echo [OK] Conda environment "%ENV_NAME%" exists (named)
    ) else (
        echo [X] Conda environment not found
    )
)

REM Check directories
if exist "%MAIN_DIR%\data" (
    echo [OK] Data directories exist
) else (
    echo [X] Data directories missing
)

REM Check .env
if exist "%MAIN_DIR%\.env" (
    echo [OK] .env file exists
) else (
    echo [X] .env file missing
)

REM Check executables
if exist "%MAIN_DIR%\build\dhl\dhl_routing_api.exe" (
    echo [OK] DHL executable exists
) else (
    echo [X] DHL executable missing
)

if exist "%MAIN_DIR%\build\hc2l\hc2l_routing_api.exe" (
    echo [OK] HC2L executable exists
) else (
    echo [X] HC2L executable missing
)

REM Check data files
if exist "%MAIN_DIR%\data\raw\quezon_city_nodes.csv" (
    echo [OK] Data files exist
) else (
    echo [X] Data files missing
)

REM Check indexes
if exist "%MAIN_DIR%\data\processed\quezon_city.dhl.index" (
    echo [OK] Index files exist
) else (
    echo [X] Index files missing
)

echo.
echo Run python check_gdal.py for detailed package verification
echo.
exit /b 0

:end
endlocal