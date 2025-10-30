@echo off
REM Build script for Dynamic Road Network algorithms (Windows)
REM This script compiles both DHL and HC2L routing APIs

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "MAIN_DIR=%PROJECT_ROOT%Main"
set "BUILD_DIR=%MAIN_DIR%\build"

echo ========================================================================
echo   Building Dynamic Road Network - All Executables (Windows)
echo ========================================================================
echo.

REM Create build directories
echo Creating build directories...
if not exist "%BUILD_DIR%\dhl" mkdir "%BUILD_DIR%\dhl"
if not exist "%BUILD_DIR%\hc2l" mkdir "%BUILD_DIR%\hc2l"

REM Check if MinGW/g++ is available
where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: g++ compiler not found!
    echo.
    echo Please install MinGW-w64 or MSYS2 and add g++ to your PATH.
    echo.
    echo Installation options:
    echo   1. MinGW-w64: https://www.mingw-w64.org/
    echo   2. MSYS2: https://www.msys2.org/
    echo   3. Visual Studio Build Tools with C++ support
    echo.
    pause
    exit /b 1
)

REM Build DHL Routing API
echo.
echo ========================================================================
echo   Building DHL (Dual-Hierarchy Labelling) Routing API...
echo ========================================================================
cd /d "%PROJECT_ROOT%DualHierarchyLabelling"

REM Check if MinGW/g++ is available
where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: g++ compiler not found!
    echo.
    echo Please install MinGW-w64 or MSYS2 and add g++ to your PATH.
    echo.
    echo Installation options:
    echo   1. MinGW-w64: https://www.mingw-w64.org/
    echo   2. MSYS2: https://www.msys2.org/
    echo   3. Visual Studio Build Tools with C++ support
    echo.
    pause
    exit /b 1
)

REM Compile directly to Main\build\dhl\
g++ -std=c++2a -O3 -Wall -Wextra -pthread -o "%BUILD_DIR%\dhl\dhl_routing_api.exe" src\dhl_routing_api.cpp src\road_network.cpp src\util.cpp
if %errorlevel% equ 0 (
    echo DHL compilation successful!
    echo DHL executable created at: %BUILD_DIR%\dhl\dhl_routing_api.exe
) else (
    echo DHL compilation failed!
    pause
    exit /b 1
)

REM Build HC2L Routing API
echo.
echo ========================================================================
echo   Building HC2L (High-Cardinality Two-Level) Routing API...
echo ========================================================================
cd /d "%PROJECT_ROOT%HighCardinalityTwoLevel"

REM Compile directly to Main\build\hc2l\
g++ -std=c++20 -O3 -Wall -Wextra -o "%BUILD_DIR%\hc2l\hc2l_routing_api.exe" src\hc2l_routing_api.cpp src\road_network.cpp src\util.cpp
if %errorlevel% equ 0 (
    echo HC2L compilation successful!
    echo HC2L executable created at: %BUILD_DIR%\hc2l\hc2l_routing_api.exe
) else (
    echo HC2L compilation failed!
    pause
    exit /b 1
)

REM Build DHL Index Executable
echo.
echo ========================================================================
echo   Building DHL Index Executable...
echo ========================================================================
cd /d "%PROJECT_ROOT%DualHierarchyLabelling"

REM Compile directly to Main\build\dhl\
g++ -std=c++2a -O3 -Wall -Wextra -pthread -o "%BUILD_DIR%\dhl\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
if %errorlevel% equ 0 (
    echo DHL index executable built!
    echo Executable created at: %BUILD_DIR%\dhl\index.exe
) else (
    echo DHL index compilation failed!
    pause
    exit /b 1
)

REM Build HC2L Index Executable
echo.
echo ========================================================================
echo   Building HC2L Index Executable...
echo ========================================================================
cd /d "%PROJECT_ROOT%HighCardinalityTwoLevel"

REM Compile directly to Main\build\hc2l\
g++ -std=c++20 -O3 -Wall -Wextra -o "%BUILD_DIR%\hc2l\index.exe" src\index.cpp src\road_network.cpp src\util.cpp
if %errorlevel% equ 0 (
    echo HC2L index executable built!
    echo Executable created at: %BUILD_DIR%\hc2l\index.exe
) else (
    echo HC2L index compilation failed!
    pause
    exit /b 1
)

REM Summary
echo.
echo ========================================================================
echo   Build Complete!
echo ========================================================================
echo.
echo Routing API Executables:
echo   * DHL:  %BUILD_DIR%\dhl\dhl_routing_api.exe
echo   * HC2L: %BUILD_DIR%\hc2l\hc2l_routing_api.exe
echo.
echo Index Builder Executables:
echo   * DHL:  %BUILD_DIR%\dhl\index.exe
echo   * HC2L: %BUILD_DIR%\hc2l\index.exe
echo.
echo Next steps:
echo   1. Generate data: cd Main ^&^& python request_new_datasets.py
echo   2. Build indexes: generate_indexes.bat
echo   3. Run server: run_server.bat
echo ========================================================================
echo.

cd /d "%SCRIPT_DIR%"
pause
