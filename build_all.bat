@echo off
REM Build script for Dynamic Road Network algorithms (Windows)
REM This script compiles both DHL and HC2L routing APIs

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "MAIN_DIR=%PROJECT_ROOT%Main"
set "BUILD_DIR=%MAIN_DIR%\build"

echo ========================================================================
echo   Building Dynamic Road Network Routing APIs (Windows)
echo ========================================================================
echo.

REM Create build directories
echo Creating build directories...
if not exist "%BUILD_DIR%\dhl" mkdir "%BUILD_DIR%\dhl"
if not exist "%BUILD_DIR%\hc2l" mkdir "%BUILD_DIR%\hc2l"

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

mingw32-make dhl_routing_api
if %errorlevel% equ 0 (
    echo DHL compilation successful!
    
    REM Copy executable to Main/build/dhl/
    copy /Y dhl_routing_api.exe "%BUILD_DIR%\dhl\" >nul
    echo Copied DHL executable to: %BUILD_DIR%\dhl\dhl_routing_api.exe
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

mingw32-make hc2l_routing_api
if %errorlevel% equ 0 (
    echo HC2L compilation successful!
    
    REM Copy executable to Main/build/hc2l/
    copy /Y hc2l_routing_api.exe "%BUILD_DIR%\hc2l\" >nul
    echo Copied HC2L executable to: %BUILD_DIR%\hc2l\hc2l_routing_api.exe
) else (
    echo HC2L compilation failed!
    pause
    exit /b 1
)

REM Summary
echo.
echo ========================================================================
echo   Build Complete!
echo ========================================================================
echo.
echo Executables are located in:
echo   * DHL:  %BUILD_DIR%\dhl\dhl_routing_api.exe
echo   * HC2L: %BUILD_DIR%\hc2l\hc2l_routing_api.exe
echo.
echo You can now run the Flask application:
echo   cd %MAIN_DIR%
echo   python flask_server.py
echo ========================================================================
echo.

cd /d "%SCRIPT_DIR%"
pause
