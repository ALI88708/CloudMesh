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
:: MAIN MENU LOOP
:: ============================================
:menu
cls
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║        CloudMesh Installer v2.0          ║
echo  ╚══════════════════════════════════════════╝
echo.

if "!IS_INSTALLED!"=="1" (
    echo   [✓] CloudMesh is already installed
    echo.
    echo   [1] Fresh Install (overwrite)
    echo   [2] Update (keep config)
    echo   [3] Factory Reset
    echo   [4] Uninstall
    echo   [5] Exit
    echo.
    set /p "CHOICE=   Choose [1-5]: "
    if "!CHOICE!"=="1" goto :do_fresh
    if "!CHOICE!"=="2" goto :do_update
    if "!CHOICE!"=="3" goto :do_reset
    if "!CHOICE!"=="4" goto :do_uninstall
    if "!CHOICE!"=="5" goto :do_exit
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
echo   [ERROR] Invalid choice! Try again.
timeout /t 2 >nul
goto :menu

:: ============================================
:: EXIT
:: ============================================
:do_exit
cls
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║           Goodbye! 👋                    ║
echo  ╚══════════════════════════════════════════╝
echo.
endlocal
exit /b 0

:: ============================================
:: UNINSTALL
:: ============================================
:do_uninstall
cls
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║         Uninstalling CloudMesh           ║
echo  ╚══════════════════════════════════════════╝
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
echo  ╔══════════════════════════════════════════╗
echo  ║     CloudMesh has been uninstalled!      ║
echo  ╚══════════════════════════════════════════╝
echo.
set IS_INSTALLED=0
pause
goto :menu

:: ============================================
:: FACTORY RESET
:: ============================================
:do_reset
cls
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║           Factory Reset                  ║
echo  ╚══════════════════════════════════════════╝
echo.
echo   [WARNING] This will delete ALL data:
echo     - Auth keys
echo     - Server config
echo     - Backups
echo     - Everything
echo.
set /p "CONFIRM=   Are you sure? (y/n): "
if /i not "!CONFIRM!"=="y" goto :menu

echo.
echo   Removing old installation...
if exist "%CLOUDMESH_DIR%" rmdir /s /q "%CLOUDMESH_DIR%" 2>nul
if exist "%NODE_DIR%" rmdir /s /q "%NODE_DIR%" 2>nul
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%" 2>nul
echo   [OK] Old files removed
echo.
goto :do_fresh

:: ============================================
:: UPDATE (keep config)
:: ============================================
:do_update
cls
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║          Updating CloudMesh              ║
echo  ╚══════════════════════════════════════════╝
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
echo  ╔══════════════════════════════════════════╗
echo  ║          Fresh Install                   ║
echo  ╚══════════════════════════════════════════╝
echo.
goto :do_download_only

:: ============================================
:: DOWNLOAD ONLY (no setup yet)
:: ============================================
:do_download_only
echo   [1/3] Creating directories...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%CLOUDMESH_DIR%" mkdir "%CLOUDMESH_DIR%"
if not exist "%CLOUDMESH_DIR%\core" mkdir "%CLOUDMESH_DIR%\core"
if not exist "%CLOUDMESH_DIR%\node" mkdir "%CLOUDMESH_DIR%\node"

echo   [2/3] Downloading from GitHub...
echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 > "%TEMP%\cm_dl.ps1"
echo $ProgressPreference = 'SilentlyContinue' >> "%TEMP%\cm_dl.ps1"
echo $url = 'https://github.com/!GITHUB_USER!/!GITHUB_REPO!/archive/refs/heads/!GITHUB_BRANCH!.zip' >> "%TEMP%\cm_dl.ps1"
echo $dest = Join-Path $env:TEMP 'cloudmesh.zip' >> "%TEMP%\cm_dl.ps1"
echo if (Test-Path $dest) { Remove-Item -Force $dest } >> "%TEMP%\cm_dl.ps1"
echo try { >> "%TEMP%\cm_dl.ps1"
echo   Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing >> "%TEMP%\cm_dl.ps1"
echo   if (-not (Test-Path $dest) -or (Get-Item $dest).Length -eq 0) { throw 'empty' } >> "%TEMP%\cm_dl.ps1"
echo } catch { >> "%TEMP%\cm_dl.ps1"
echo   Write-Host 'ERROR: Download failed' >> "%TEMP%\cm_dl.ps1"
echo   exit 1 >> "%TEMP%\cm_dl.ps1"
echo } >> "%TEMP%\cm_dl.ps1"

powershell -ExecutionPolicy Bypass -File "%TEMP%\cm_dl.ps1" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo   [ERROR] Download failed! Check internet connection.
    echo.
    del "%TEMP%\cm_dl.ps1" 2>nul
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

echo   [3/3] Extracting files...
echo $ProgressPreference = 'SilentlyContinue' > "%TEMP%\cm_ex.ps1"
echo $zip = Join-Path $env:TEMP 'cloudmesh.zip' >> "%TEMP%\cm_ex.ps1"
echo $out = Join-Path $env:TEMP 'cloudmesh_extract' >> "%TEMP%\cm_ex.ps1"
echo if (Test-Path $out) { Remove-Item -Recurse -Force $out } >> "%TEMP%\cm_ex.ps1"
echo Expand-Archive -Path $zip -DestinationPath $out -Force >> "%TEMP%\cm_ex.ps1"
echo $d = Get-ChildItem -Path $out -Directory ^| Select-Object -First 1 >> "%TEMP%\cm_ex.ps1"
echo $destPath = '%CLOUDMESH_DIR%' >> "%TEMP%\cm_ex.ps1"
echo if (Test-Path $destPath) { Remove-Item -Recurse -Force $destPath } >> "%TEMP%\cm_ex.ps1"
echo Copy-Item -Path (Join-Path $d.FullName 'cloudmesh') -Destination $destPath -Recurse -Force >> "%TEMP%\cm_ex.ps1"
echo Remove-Item -Recurse -Force $out >> "%TEMP%\cm_ex.ps1"
echo Remove-Item -Force $zip >> "%TEMP%\cm_ex.ps1"

powershell -ExecutionPolicy Bypass -File "%TEMP%\cm_ex.ps1" 2>nul

del "%TEMP%\cm_dl.ps1" 2>nul
del "%TEMP%\cm_ex.ps1" 2>nul

if not exist "%CLOUDMESH_DIR%\main.py" (
    echo.
    echo   [ERROR] Extract failed!
    echo.
    pause
    goto :menu
)

echo. > "%CLOUDMESH_DIR%\core\__init__.py"
echo   [OK] Download complete!
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
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║        Setting up CloudMesh              ║
echo  ╚══════════════════════════════════════════╝
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
    echo   [WARNING] cloudmesh_node.py not found, skipping node
    goto :controller_setup
)

echo   [5/6] Generating TLS certificate...
set TLS_CERT=%NODE_DIR%\cert.pem
set TLS_KEY=%NODE_DIR%\key.pem
if not exist "!TLS_CERT!" (
    where openssl >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        openssl req -x509 -newkey rsa:2048 -nodes -keyout "!TLS_KEY!" -out "!TLS_CERT!" -days 3650 -subj "/CN=cloudmesh-node-%COMPUTERNAME%" 2>nul
        echo   [OK] TLS certificate generated (10 years^)
    ) else (
        echo   [WARNING] openssl not found, running without TLS
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

echo   [6/6] Node setup complete!
echo.
set AUTH_KEY=N/A
if exist "%NODE_DIR%\.node_key" (
    set /p AUTH_KEY=<"%NODE_DIR%\.node_key"
)
set IP_ADDRESS=YOUR_IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=1" %%b in ("%%a") do set IP_ADDRESS=%%b
)

echo   [OK] Node Location: %NODE_DIR%
echo   [OK] Auth Key: !AUTH_KEY!
echo   [OK] TLS: enabled
echo   [OK] Bind: 127.0.0.1 (local only)
echo.
echo   === Add from Controller ===
echo   cm add -n %COMPUTERNAME% -H !IP_ADDRESS! -p 9999 -k !AUTH_KEY!
echo.

set /p "START_NODE=   Start node now? (y/n): "
if /i "!START_NODE!"=="y" (
    call "%NODE_DIR%\start.bat"
)
echo.

:controller_setup
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║      Controller Setup Complete!          ║
echo  ╚══════════════════════════════════════════╝
echo.

if not exist "%VENV_PYTHON%" (
    echo   Creating virtual environment...
    python -m venv "%VENV_DIR%"
    "%VENV_PYTHON%" -m pip install -q -r "%CLOUDMESH_DIR%\requirements.txt"
    echo   [OK] Environment ready!
) else (
    echo   [OK] Virtual environment exists
)
echo.

echo   Creating cm shortcut...

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

echo   [OK] cm command available!
echo.

set IS_INSTALLED=1

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║    CloudMesh Installed Successfully!     ║
echo  ╚══════════════════════════════════════════╝
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
