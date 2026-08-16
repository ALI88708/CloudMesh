@echo off
setlocal enabledelayedexpansion
echo ============================================
echo    CloudMesh Installer (Auto-Download)
echo ============================================
echo.

:: ============================================
:: CONFIG - CHANGE THIS TO YOUR GITHUB REPO
:: ============================================
set GITHUB_USER=MrAli88708
set GITHUB_REPO=CloudMesh
set GITHUB_BRANCH=main

:: ============================================
:: PATHS
:: ============================================
set INSTALL_DIR=%USERPROFILE%\CloudMesh
set CLOUDMESH_DIR=%INSTALL_DIR%\cloudmesh
set NODE_DIR=%USERPROFILE%\.cloudmesh-node
set VENV_DIR=%INSTALL_DIR%\venv
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe

:: ============================================
:: STEP 1: Check if cloudmesh folder exists locally
:: ============================================
set LOCAL_SOURCE=%~dp0cloudmesh
set USE_LOCAL=0

if exist "%LOCAL_SOURCE%\main.py" (
    echo [OK] Found local cloudmesh folder
    set USE_LOCAL=1
    set CLOUDMESH_DIR=%LOCAL_SOURCE%
) else (
    echo [INFO] Local cloudmesh folder not found
    echo [INFO] Will download from GitHub...
    echo.
)

:: ============================================
:: STEP 2: Download from GitHub if needed
:: ============================================
if %USE_LOCAL% EQU 0 (
    echo [INFO] Downloading CloudMesh from GitHub...
    echo.

    :: Create install directory
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    if not exist "%CLOUDMESH_DIR%" mkdir "%CLOUDMESH_DIR%"
    if not exist "%CLOUDMESH_DIR%\core" mkdir "%CLOUDMESH_DIR%\core"
    if not exist "%CLOUDMESH_DIR%\node" mkdir "%CLOUDMESH_DIR%\node"

    :: Check for curl
    curl --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] curl not found. Please install curl or download manually.
        echo [INFO] Manual download: https://github.com/%GITHUB_USER%/%GITHUB_REPO%/archive/refs/heads/%GITHUB_BRANCH%.zip
        start https://github.com/%GITHUB_USER%/%GITHUB_REPO%/archive/refs/heads/%GITHUB_BRANCH%.zip
        pause
        exit /b 1
    )

    set BASE_URL=https://raw.githubusercontent.com/%GITHUB_USER%/%GITHUB_REPO%/%GITHUB_BRANCH%

    echo [1/12] Downloading main.py...
    curl -sL "%BASE_URL%/cloudmesh/main.py" -o "%CLOUDMESH_DIR%\main.py"

    echo [2/12] Downloading requirements.txt...
    curl -sL "%BASE_URL%/requirements.txt" -o "%CLOUDMESH_DIR%\requirements.txt"

    echo [3/12] Downloading core/features.py...
    curl -sL "%BASE_URL%/cloudmesh/core/features.py" -o "%CLOUDMESH_DIR%\core\features.py"

    echo [4/12] Downloading core/advanced.py...
    curl -sL "%BASE_URL%/cloudmesh/core/advanced.py" -o "%CLOUDMESH_DIR%\core\advanced.py"

    echo [5/12] Downloading core/server.py...
    curl -sL "%BASE_URL%/cloudmesh/core/server.py" -o "%CLOUDMESH_DIR%\core\server.py"

    echo [6/12] Downloading core/monitor.py...
    curl -sL "%BASE_URL%/cloudmesh/core/monitor.py" -o "%CLOUDMESH_DIR%\core\monitor.py"

    echo [7/12] Downloading core/scheduler.py...
    curl -sL "%BASE_URL%/cloudmesh/core/scheduler.py" -o "%CLOUDMESH_DIR%\core\scheduler.py"

    echo [8/12] Downloading core/node_client.py...
    curl -sL "%BASE_URL%/cloudmesh/core/node_client.py" -o "%CLOUDMESH_DIR%\core\node_client.py"

    echo [9/12] Downloading core/gpu.py...
    curl -sL "%BASE_URL%/cloudmesh/core/gpu.py" -o "%CLOUDMESH_DIR%\core\gpu.py"

    echo [10/12] Downloading core/jobs.py...
    curl -sL "%BASE_URL%/cloudmesh/core/jobs.py" -o "%CLOUDMESH_DIR%\core\jobs.py"

    echo [11/12] Downloading remaining core files...
    for %%f in (security transfer sync deploy alerts groups dashboard tui service history cmdlog) do (
        curl -sL "%BASE_URL%/cloudmesh/core/%%f.py" -o "%CLOUDMESH_DIR%\core\%%f.py" 2>nul
    )

    echo [12/12] Downloading node agent...
    curl -sL "%BASE_URL%/cloudmesh/node/cloudmesh_node.py" -o "%CLOUDMESH_DIR%\node\cloudmesh_node.py"
    curl -sL "%BASE_URL%/cloudmesh/node/node-install.sh" -o "%CLOUDMESH_DIR%\node\node-install.sh" 2>nul

    :: Verify download
    if not exist "%CLOUDMESH_DIR%\main.py" (
        echo [ERROR] Download failed!
        echo [INFO] Check your internet connection or GitHub repo settings.
        pause
        exit /b 1
    )

    :: Create __init__.py for core
    echo. > "%CLOUDMESH_DIR%\core\__init__.py"

    echo [OK] Download complete!
    echo.
)

:: ============================================
:: STEP 3: Node Agent Installation
:: ============================================
echo ============================================
echo    Installing CloudMesh Node...
echo ============================================
echo.

:: --- Check Python ---
echo [1/6] Checking Python...

python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo [OK] Python found: %%v
    goto :py_ok
)

python3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do echo [OK] Python3 found: %%v
    goto :py_ok
)

echo [INFO] Python not found. Installing...
winget --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    winget install Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
    goto :refresh_path
)
choco --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    choco install python -y
    goto :refresh_path
)
scoop --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    scoop install python
    goto :refresh_path
)
echo [INFO] Please download Python from: https://www.python.org/downloads/
start https://www.python.org/downloads/
pause
exit /b 1

:refresh_path
set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\
set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\

:py_ok

:: --- Install psutil ---
echo [2/6] Installing node dependencies...
python -m pip install --user psutil >nul 2>&1
echo [OK] Dependencies installed

:: --- Create node directory ---
echo [3/6] Creating node directory...
if not exist "%NODE_DIR%" mkdir "%NODE_DIR%"
if not exist "%NODE_DIR%\logs" mkdir "%NODE_DIR%\logs"
if not exist "%NODE_DIR%\data" mkdir "%NODE_DIR%\data"

:: --- Install node agent ---
echo [4/6] Installing CloudMesh Node agent...
set NODE_SOURCE=%CLOUDMESH_DIR%\node\cloudmesh_node.py
if exist "%NODE_SOURCE%" (
    copy /Y "%NODE_SOURCE%" "%NODE_DIR%\cloudmesh_node.py" >nul
    echo [OK] Node agent installed
) else (
    echo [ERROR] cloudmesh_node.py not found
    exit /b 1
)

:: --- Create node helper scripts ---
echo [5/6] Creating node scripts...

(
echo @echo off
echo cd /d "%%~dp0"
echo python cloudmesh_node.py start %%*
) > "%NODE_DIR%\start.bat"

(
echo @echo off
echo cd /d "%%~dp0"
echo python cloudmesh_node.py stop
) > "%NODE_DIR%\stop.bat"

(
echo @echo off
echo cd /d "%%~dp0"
echo python cloudmesh_node.py status
) > "%NODE_DIR%\status.bat"

echo [OK] Node scripts created

:: --- Print node info ---
echo [6/6] Node setup complete!
echo.
set AUTH_KEY=N/A
if exist "%NODE_DIR%\.node_key" (
    set /p AUTH_KEY=<"%NODE_DIR%\.node_key"
)
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=1" %%b in ("%%a") do set IP_ADDRESS=%%b
)

echo  [OK] Node Location: %NODE_DIR%
echo  [OK] Auth Key: %AUTH_KEY%
echo.
echo  === Add from Controller ===
echo  cm node add -n %COMPUTERNAME% -H %IP_ADDRESS% -p 9999 -k %AUTH_KEY%
echo.

:: Ask to start node now
set /p START_NODE="Start node now? (y/n): "
if /i "%START_NODE%"=="y" (
    call "%NODE_DIR%\start.bat"
)
echo.

:: ============================================
:: STEP 4: Controller Setup
:: ============================================
echo ============================================
echo    CloudMesh Controller Setup
echo ============================================
echo.

:: Create venv
if not exist "%VENV_PYTHON%" (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    "%VENV_PYTHON%" -m pip install -q -r "%CLOUDMESH_DIR%\requirements.txt"
    echo [OK] Environment ready!
) else (
    echo [OK] Virtual environment exists
)
echo.

:: ============================================
:: STEP 5: Create cm shortcut (add to PATH)
:: ============================================
echo [INFO] Creating cm shortcut...

:: Create cm.bat in WindowsApps (already in PATH)
set CM_BAT=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\cm.bat

(
echo @echo off
echo setlocal
echo set "CLOUDMESH_DIR=%CLOUDMESH_DIR%"
echo set "VENV_PYTHON=%VENV_PYTHON%"
echo if not exist "%%VENV_PYTHON%%" (
echo     echo [ERROR] Virtual environment not found
echo     exit /b 1
echo ^)
echo "%%VENV_PYTHON%%" "%%CLOUDMESH_DIR%%\main.py" %%*
) > "%CM_BAT%"

echo [OK] cm command available!
echo.

:: ============================================
:: DONE
:: ============================================
echo ============================================
echo    CloudMesh Installed Successfully!
echo ============================================
echo.
echo === Quick Start ===
echo   cm --help           # Show all commands
echo   cm interactive      # Interactive TUI
echo   cm version          # Show version
echo   cm ping             # Test connections
echo   cm discover 192.168.1  # Scan network
echo   cm bench            # Benchmark
echo.
echo === Node Commands ===
echo   Start:    %NODE_DIR%\start.bat
echo   Status:   %NODE_DIR%\status.bat
echo   Stop:     %NODE_DIR%\stop.bat
echo.
echo === Files Installed ===
echo   Program:  %CLOUDMESH_DIR%
echo   Node:     %NODE_DIR%
echo   Shortcut: %CM_BAT%
echo.
echo Usage: cm [command] [options]
echo.
