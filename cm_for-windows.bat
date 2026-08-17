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

    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    if not exist "%CLOUDMESH_DIR%" mkdir "%CLOUDMESH_DIR%"
    if not exist "%CLOUDMESH_DIR%\core" mkdir "%CLOUDMESH_DIR%\core"
    if not exist "%CLOUDMESH_DIR%\node" mkdir "%CLOUDMESH_DIR%\node"

    echo [1/2] Downloading ZIP from GitHub...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; $zipUrl = 'https://github.com/%GITHUB_USER%/%GITHUB_REPO%/archive/refs/heads/%GITHUB_BRANCH%.zip'; $zipFile = '%TEMP%\cloudmesh.zip'; Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing; if (!(Test-Path $zipFile) -or (Get-Item $zipFile).Length -eq 0) { Write-Host '[ERROR] Download failed!'; exit 1 }"

    if not exist "%TEMP%\cloudmesh.zip" (
        echo [ERROR] Download failed! Check your internet connection.
        pause
        exit /b 1
    )

    echo [2/2] Extracting files...
    powershell -Command "$ProgressPreference = 'SilentlyContinue'; $zip = '%TEMP%\cloudmesh.zip'; $extract = '%TEMP%\cloudmesh_extract'; if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }; Expand-Archive -Path $zip -DestinationPath $extract -Force; $src = Get-ChildItem -Path $extract -Directory | Select-Object -First 1; if (!$src) { Write-Host '[ERROR] Extract failed!'; exit 1 }; Copy-Item -Path (Join-Path $src.FullName 'cloudmesh\*') -Destination '%CLOUDMESH_DIR%' -Recurse -Force; Copy-Item -Path (Join-Path $src.FullName 'cloudmesh\node\*') -Destination '%CLOUDMESH_DIR%\node' -Recurse -Force; Remove-Item -Recurse -Force $extract; Remove-Item -Force $zip"

    if not exist "%CLOUDMESH_DIR%\main.py" (
        echo [ERROR] Extract failed!
        pause
        exit /b 1
    )

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

:: Try multiple Python commands
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

py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do echo [OK] Python (py) found: %%v
    goto :py_ok
)

:: Check common install paths
for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%p (
        set "PATH=%%~dp0;%PATH%"
        echo [OK] Python found: %%p
        goto :py_ok
    )
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
echo [ERROR] Python not found and cannot auto-install.
echo [INFO] Please install Python manually from: https://www.python.org/downloads/
echo [INFO] Make sure "Add Python to PATH" is checked!
start https://www.python.org/downloads/
pause
exit /b 1

:refresh_path
set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\
set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\
set PATH=%PATH%;C:\Python312\
set PATH=%PATH%;C:\Python312\Scripts\

:: Verify Python works after install
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python installation failed. Please install manually.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

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
