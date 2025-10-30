# Windows Setup Guide

## Prerequisites for Windows

### 1. Install Python (3.8 or higher)
Download from: https://www.python.org/downloads/

**Important:** Check "Add Python to PATH" during installation

### 2. Install C++ Compiler (MinGW-w64 or MSYS2)

**Option A: MinGW-w64 (Recommended)**
1. Download from: https://www.mingw-w64.org/downloads/
2. Install to `C:\mingw-w64`
3. Add to PATH: `C:\mingw-w64\bin`

**Option B: MSYS2**
1. Download from: https://www.msys2.org/
2. Install and run MSYS2
3. Install g++: `pacman -S mingw-w64-x86_64-gcc`
4. Add to PATH: `C:\msys64\mingw64\bin`

**Option C: Visual Studio Build Tools**
1. Download from: https://visualstudio.microsoft.com/downloads/
2. Install "Desktop development with C++"
3. Use "Developer Command Prompt for VS"

### 3. Install Git (Optional)
Download from: https://git-scm.com/download/win

## Quick Start (Windows)

### 1. Clone Repository
```cmd
git clone https://github.com/RenzVillegas24/Dynamic-Road-Network-using-DHL-and-HC2L.git
cd Dynamic-Road-Network-using-DHL-and-HC2L
```

### 2. Create Virtual Environment
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies
```cmd
pip install -r requirements.txt
```

### 4. Configure Environment
```cmd
copy Main\.env.example Main\.env
notepad Main\.env
```
Add your Google Maps API key to the `.env` file.

### 5. Build Executables
```cmd
build_all.bat
```

This will compile both DHL and HC2L routing APIs.

### 6. Generate Data and Build Indexes (First Time)
```cmd
run_server.bat --generate
```

OR manually:
```cmd
cd Main
python request_new_datasets.py
cd ..
build_indexes.bat
```

### 7. Run Server
```cmd
run_server.bat
```

Open browser: http://localhost:5000

## Batch Scripts for Windows

### build_all.bat
Compiles both DHL and HC2L routing APIs
```cmd
build_all.bat
```

### build_indexes.bat
Builds graph indexes from data files
```cmd
build_indexes.bat
```

### run_server.bat
Starts the Flask server with interactive setup
```cmd
run_server.bat              :: Interactive mode
run_server.bat --generate   :: Auto-generate data if missing
run_server.bat --skip       :: Skip data checks
run_server.bat --help       :: Show help
```

## Troubleshooting (Windows)

### g++ not found
**Error:** `'g++' is not recognized as an internal or external command`

**Solution:**
1. Verify MinGW/MSYS2 installation
2. Add to PATH:
   - Open "Edit the system environment variables"
   - Click "Environment Variables"
   - Edit "Path" variable
   - Add: `C:\mingw-w64\bin` or `C:\msys64\mingw64\bin`
3. Restart Command Prompt

### Python not found
**Error:** `'python' is not recognized as an internal or external command`

**Solution:**
1. Reinstall Python with "Add to PATH" option
2. Or manually add Python to PATH:
   - Add: `C:\Python39` (or your Python installation path)
   - Add: `C:\Python39\Scripts`

### MinGW make not found
**Error:** `'mingw32-make' is not recognized`

**Solution:**
Use appropriate make command:
- MinGW-w64: `mingw32-make`
- MSYS2: `make`
- Visual Studio: `nmake`

Edit the .bat files to use the correct make command for your setup.

### Virtual environment activation fails
**Error:** Script execution disabled

**Solution:**
Run PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Or use Command Prompt (cmd) instead of PowerShell.

### Port 5000 already in use
**Error:** `OSError: [WinError 10048] Only one usage of each socket address`

**Solution:**
1. Find process using port 5000:
   ```cmd
   netstat -ano | findstr :5000
   ```
2. Kill the process:
   ```cmd
   taskkill /PID <process_id> /F
   ```
3. Or change port in `Main/config.py`

## File Paths on Windows

Windows uses backslashes `\` for paths, but Python accepts both `\` and `/`.

The scripts automatically convert paths for Windows compatibility.

## Long Path Support (Windows 10+)

If you encounter path length errors:

1. Enable long paths in Windows:
   - Run as Administrator: `gpedit.msc`
   - Navigate to: Local Computer Policy > Computer Configuration > Administrative Templates > System > Filesystem
   - Enable "Enable Win32 long paths"

2. Or use shorter installation path: `C:\DRN\`

## Performance Notes (Windows)

- **Compilation**: May be slower than Linux due to antivirus scanning
- **File I/O**: Windows file operations are generally slower
- **Recommendation**: Add project folder to antivirus exclusions for better performance

## IDE Recommendations (Windows)

- **VS Code**: Lightweight, excellent Python support
- **PyCharm**: Full-featured Python IDE
- **Visual Studio**: If using Visual Studio Build Tools

## Running in WSL (Alternative)

If you prefer Linux environment:

1. Install WSL2: https://docs.microsoft.com/en-us/windows/wsl/install
2. Install Ubuntu from Microsoft Store
3. Follow Linux setup instructions in main README.md

This gives you native Linux performance on Windows!
