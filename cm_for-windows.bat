@echo off
setlocal enabledelayedexpansion
title CloudMesh Installer
color 0B

:: ============================================
:: CONFIG
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
set CM_BAT=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\cm.bat

:: ============================================
:: CHECK INSTALL STATUS
:: ============================================
set IS_INSTALLED=0
if exist "%CLOUDMESH_DIR%\main.py" set IS_INSTALLED=1
if exist "%VENV_DIR%\Scripts\python.exe" set IS_INSTALLED=1

:: ============================================
:: MAIN MENU
:: ============================================
:menu
cls
echo.
echo   +==========================================+
echo   |        CloudMesh Installer v2.0          |
echo   |            Created by MRSX PRO           |
echo   +==========================================+
echo.

if "!IS_INSTALLED!"=="1" (
    echo   [OK] CloudMesh is already installed
    echo.
    echo   [1] Update        - Keep data, get latest version
    echo   [2] Reinstall     - Delete everything, install fresh
    echo   [3] Uninstall     - Remove CloudMesh completely
    echo.
    set /p "CHOICE=   Choose [1-3]: "
    if "!CHOICE!"=="1" goto :do_update
    if "!CHOICE!"=="2" goto :do_fresh
    if "!CHOICE!"=="3" goto :do_uninstall
) else (
    echo   [!] CloudMesh is NOT installed
    echo.
    echo   [1] Install CloudMesh
    echo   [2] Exit
    echo.
    set /p "CHOICE=   Choose [1-2]: "
    if "!CHOICE!"=="1" goto :do_fresh
    if "!CHOICE!"=="2" goto :do_exit
)

echo.
echo   [!] Invalid choice. Try again.
timeout /t 2 >nul
goto :menu

:: ============================================
:: EXIT
:: ============================================
:do_exit
cls
echo.
echo   Goodbye!
echo.
endlocal
exit /b 0

:: ============================================
:: UNINSTALL
:: ============================================
:do_uninstall
cls
echo.
echo   +==========================================+
echo   |         Uninstalling CloudMesh           |
echo   +==========================================+
echo.
set /p "CONFIRM=   Are you sure? (y/n): "
if /i not "!CONFIRM!"=="y" goto :menu

echo.
echo   [1/4] Removing program files...
if exist "%CLOUDMESH_DIR%" (
    rmdir /s /q "%CLOUDMESH_DIR%" 2>nul
    echo   [OK] Program files removed
) else (
    echo   [OK] Program files not found (skip)
)

echo   [2/4] Removing node agent...
if exist "%NODE_DIR%" (
    rmdir /s /q "%NODE_DIR%" 2>nul
    echo   [OK] Node agent removed
) else (
    echo   [OK] Node agent not found (skip)
)

echo   [3/4] Removing virtual environment...
if exist "%VENV_DIR%" (
    rmdir /s /q "%VENV_DIR%" 2>nul
    echo   [OK] Virtual environment removed
) else (
    echo   [OK] Virtual environment not found (skip)
)

echo   [4/4] Cleaning up...
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%" 2>nul
if exist "%CM_BAT%" del "%CM_BAT%" 2>nul
del "%TEMP%\cloudmesh.zip" 2>nul
del "%TEMP%\cm_dl.ps1" 2>nul
del "%TEMP%\cm_ex.ps1" 2>nul
echo   [OK] Cleanup complete

echo.
echo   CloudMesh has been uninstalled.
echo.
set IS_INSTALLED=0
pause
goto :menu

:: ============================================
:: UPDATE (keep config)
:: ============================================
:do_update
cls
echo.
echo   +==========================================+
echo   |          Updating CloudMesh              |
echo   +==========================================+
echo.

set BACKUP_DIR=%TEMP%\cloudmesh_backup
if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"

echo   [1/2] Backing up config...
if exist "%CLOUDMESH_DIR%\.node_keys.json" (
    copy /Y "%CLOUDMESH_DIR%\.node_keys.json" "!BACKUP_DIR!\" >nul 2>&1
    echo   [OK] Node keys backed up
)
if exist "%INSTALL_DIR%\cloudmesh.json" (
    copy /Y "%INSTALL_DIR%\cloudmesh.json" "!BACKUP_DIR!\" >nul 2>&1
    echo   [OK] Server config backed up
)
if exist "%INSTALL_DIR%\config.json" (
    copy /Y "%INSTALL_DIR%\config.json" "!BACKUP_DIR!\" >nul 2>&1
    echo   [OK] Config backed up
)

echo   [2/2] Downloading update...
goto :do_download_only

:: ============================================
:: FRESH INSTALL
:: ============================================
:do_fresh
cls
echo.
echo   +==========================================+
echo   |          Fresh Install                   |
echo   +==========================================+
echo.

if "!IS_INSTALLED!"=="1" (
    echo   Removing old installation...
    if exist "%CLOUDMESH_DIR%" rmdir /s /q "%CLOUDMESH_DIR%" 2>nul
    if exist "%NODE_DIR%" rmdir /s /q "%NODE_DIR%" 2>nul
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
    echo   [OK] Old files removed
    echo.
)

goto :do_download_only

:: ============================================
:: DOWNLOAD AND EXTRACT
:: ============================================
:do_download_only
echo   [1/4] Creating directories...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%CLOUDMESH_DIR%" mkdir "%CLOUDMESH_DIR%"
if not exist "%CLOUDMESH_DIR%\core" mkdir "%CLOUDMESH_DIR%\core"
if not exist "%CLOUDMESH_DIR%\node" mkdir "%CLOUDMESH_DIR%\node"
echo   [OK] Directories ready
echo.

echo   [2/4] Downloading from GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
     $ProgressPreference = 'SilentlyContinue'; ^
     $url = 'https://github.com/%GITHUB_USER%/%GITHUB_REPO%/archive/refs/heads/%GITHUB_BRANCH%.zip'; ^
     $dest = Join-Path $env:TEMP 'cloudmesh.zip'; ^
     if (Test-Path $dest) { Remove-Item -Force $dest }; ^
     try { ^
         Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing; ^
         if (-not (Test-Path $dest) -or (Get-Item $dest).Length -eq 0) { throw 'empty' } ^
     } catch { ^
         Write-Host '[ERROR] Download failed: ' $_.Exception.Message; ^
         exit 1 ^
     }"

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo   [ERROR] Download failed! Check internet connection.
    echo.
    pause
    goto :menu
)

if not exist "%TEMP%\cloudmesh.zip" (
    echo.
    echo   [ERROR] Download failed! Check internet connection.
    echo.
    pause
    goto :menu
)

for %%f in ("%TEMP%\cloudmesh.zip") do echo   [OK] Downloaded %%~zf bytes
echo.

echo   [3/4] Extracting files...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue'; ^
     $zip = Join-Path $env:TEMP 'cloudmesh.zip'; ^
     $out = Join-Path $env:TEMP 'cloudmesh_extract'; ^
     if (Test-Path $out) { Remove-Item -Recurse -Force $out }; ^
     Expand-Archive -Path $zip -DestinationPath $out -Force; ^
     $d = Get-ChildItem -Path $out -Directory | Select-Object -First 1; ^
     $destPath = '%CLOUDMESH_DIR%'; ^
     if (Test-Path $destPath) { Remove-Item -Recurse -Force $destPath }; ^
     Copy-Item -Path (Join-Path $d.FullName 'cloudmesh') -Destination $destPath -Recurse -Force; ^
     Remove-Item -Recurse -Force $out; ^
     Remove-Item -Force $zip"

if not exist "%CLOUDMESH_DIR%\main.py" (
    echo.
    echo   [ERROR] Extract failed!
    echo.
    pause
    goto :menu
)

echo   [OK] Extract complete
echo.

echo   [4/4] Creating init file...
echo. > "%CLOUDMESH_DIR%\core\__init__.py"
echo   [OK] Done
echo.

:: Restore config if update
if exist "%BACKUP_DIR%" (
    echo   Restoring config...
    if exist "%BACKUP_DIR%\.node_keys.json" (
        copy /Y "%BACKUP_DIR%\.node_keys.json" "%CLOUDMESH_DIR%\" >nul 2>&1
        echo   [OK] Node keys restored
    )
    if exist "%BACKUP_DIR%\cloudmesh.json" (
        copy /Y "%BACKUP_DIR%\cloudmesh.json" "%INSTALL_DIR%\" >nul 2>&1
    )
    if exist "%BACKUP_DIR%\config.json" (
        copy /Y "%BACKUP_DIR%\config.json" "%INSTALL_DIR%\" >nul 2>&1
    )
    rmdir /s /q "%BACKUP_DIR%" 2>nul
    echo   [OK] Config restored
    echo.
)

goto :setup_all

:: ============================================
:: FULL SETUP
:: ============================================
:setup_all
echo   +==========================================+
echo   |        Setting up CloudMesh              |
echo   +==========================================+
echo.

:: Check Python
echo   [1/6] Checking Python...

python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   [OK] Python found: %%v
    goto :py_ok
)

python3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do echo   [OK] Python3 found: %%v
    goto :py_ok
)

py --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do echo   [OK] Python (py) found: %%v
    goto :py_ok
)

echo   [INFO] Python not found. Installing...
winget --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    winget install Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
    goto :refresh_path
)
choco --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    choco install python -y
    goto :refresh_path
)
echo   [ERROR] Python not found and cannot auto-install.
echo   [INFO] Please install Python from: https://www.python.org/downloads/
start https://www.python.org/downloads/
pause
goto :menu

:refresh_path
set PATH=!PATH!;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\
set PATH=!PATH!;%LOCALAPPDATA%\Programs\Python\Python312\
set PATH=!PATH!;C:\Python312\
set PATH=!PATH!;C:\Python312\Scripts\

python --version >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo   [ERROR] Python installation failed. Please install manually.
    start https://www.python.org/downloads/
    pause
    goto :menu
)

:py_ok

echo   [2/6] Installing dependencies...
python -m pip install --user psutil >nul 2>&1
echo   [OK] Dependencies installed

echo   [3/6] Creating node directory...
if not exist "%NODE_DIR%" mkdir "%NODE_DIR%"
if not exist "%NODE_DIR%\logs" mkdir "%NODE_DIR%\logs"
if not exist "%NODE_DIR%\data" mkdir "%NODE_DIR%\data"

echo   [4/6] Installing node agent...
set NODE_SOURCE=%CLOUDMESH_DIR%\node\cloudmesh_node.py
if exist "!NODE_SOURCE!" (
    copy /Y "!NODE_SOURCE!" "%NODE_DIR%\cloudmesh_node.py" >nul 2>&1
    echo   [OK] Node agent installed
) else (
    echo   [INFO] cloudmesh_node.py not found, skipping node
    goto :skip_node
)

echo   [5/6] Generating TLS certificate...
set TLS_CERT=%NODE_DIR%\cert.pem
set TLS_KEY=%NODE_DIR%\key.pem
if not exist "!TLS_CERT!" (
    where openssl >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        openssl req -x509 -newkey rsa:2048 -nodes -keyout "!TLS_KEY!" -out "!TLS_CERT!" -days 3650 -subj "/CN=cloudmesh-node-%COMPUTERNAME%" 2>nul
        echo   [OK] TLS certificate generated (10 years)
    ) else (
        echo   [INFO] openssl not found, running without TLS
        set TLS_CERT=
        set TLS_KEY=
    )
) else (
    echo   [OK] TLS certificate exists
)

echo   [6/6] Creating node scripts...

(
echo @echo off
echo cd /d "%%~dp0"
echo set BIND_HOST=127.0.0.1
echo set TLS_ARGS=
echo if exist "%TLS_CERT%" if exist "%TLS_KEY%" set TLS_ARGS=--tls-cert "%TLS_CERT%" --tls-key "%TLS_KEY%"
echo python cloudmesh_node.py start --bind %%BIND_HOST%% %%TLS_ARGS%% %%*
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

echo   [OK] Node scripts created
echo.

set AUTH_KEY=N/A
if exist "%NODE_DIR%\.node_key" (
    set /p AUTH_KEY=<"%NODE_DIR%\.node_key"
)
set IP_ADDRESS=YOUR_IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=1" %%b in ("%%a") do set IP_ADDRESS=%%b
)

echo   Node Location: %NODE_DIR%
echo   Auth Key: !AUTH_KEY!
echo   Bind: 127.0.0.1 (local only)
echo.
echo   === Add from Controller ===
echo   cm add -n %COMPUTERNAME% -H !IP_ADDRESS! -p 9999 -k !AUTH_KEY!
echo.
set /p "START_NODE=   Start node now? (y/n): "
if /i "!START_NODE!"=="y" (
    call "%NODE_DIR%\start.bat"
)

:skip_node
echo.
echo   +==========================================+
echo   |      Setting up Controller...            |
echo   +==========================================+
echo.

if not exist "%VENV_DIR%" (
    echo   Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo   [ERROR] Failed to create virtual environment!
        pause
        goto :menu
    )
    echo   [OK] Virtual environment created
    echo   Installing requirements (this may take a few minutes)...
    "%VENV_PYTHON%" -m pip install -q -r "%CLOUDMESH_DIR%\requirements.txt"
    if !ERRORLEVEL! NEQ 0 (
        echo   [WARNING] Some dependencies failed to install
    )
    echo   [OK] Environment ready!
) else (
    echo   [OK] Virtual environment exists
)
echo.

if not exist "%VENV_PYTHON%" (
    echo   [ERROR] Python venv not found at: %VENV_PYTHON%
    echo   [INFO] Try running: python -m venv "%VENV_DIR%"
    pause
    goto :menu
)

echo   Creating cm shortcut...

(
echo @echo off
echo setlocal
echo set "CLOUDMESH_DIR=%CLOUDMESH_DIR%"
echo set "VENV_PYTHON=%VENV_PYTHON%"
echo if not exist "%%VENV_PYTHON%%" (
echo     echo [ERROR] Virtual environment not found
echo     echo [INFO] Reinstall CloudMesh
echo     exit /b 1
echo ^)
echo "%%VENV_PYTHON%%" "%%CLOUDMESH_DIR%%\main.py" %%*
) > "%CM_BAT%"

echo   [OK] cm command available!
echo.

set IS_INSTALLED=1

echo.
echo   +==========================================+
echo   |    CloudMesh Installed Successfully!     |
echo   +==========================================+
echo.
echo   Quick Start:
echo   cm --help              Show all commands
echo   cm interactive         Interactive TUI
echo   cm version             Show version
echo   cm ping                Test connections
echo   cm discover 192.168.1  Scan network
echo   cm bench               Benchmark
echo.
echo   Files:
echo   Program:  %CLOUDMESH_DIR%
echo   Node:     %NODE_DIR%
echo   Shortcut: %CM_BAT%
echo.
pause
goto :menu