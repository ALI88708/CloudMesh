@echo off
setlocal enabledelayedexpansion
title CloudMesh Installer - MRSX PRO

set GITHUB_USER=ALI88708
set GITHUB_REPO=CloudMesh
set GITHUB_BRANCH=main

set INSTALL_DIR=%USERPROFILE%\CloudMesh
set CLOUDMESH_DIR=%INSTALL_DIR%\cloudmesh
set NODE_DIR=%USERPROFILE%\.cloudmesh-node
set VENV_DIR=%INSTALL_DIR%\venv
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe
set CM_BAT=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\cm.bat

set LOG=%TEMP%\cm_install_log.txt
echo [%date% %time%] Installer started > "!LOG!"
echo [%date% %time%] USERPROFILE=!USERPROFILE! >> "!LOG!"
echo [%date% %time%] INSTALL_DIR=!INSTALL_DIR! >> "!LOG!"
echo [%date% %time%] CLOUDMESH_DIR=!CLOUDMESH_DIR! >> "!LOG!"
echo [%date% %time%] CM_BAT=!CM_BAT! >> "!LOG!"

set IS_INSTALLED=0
if exist "!CLOUDMESH_DIR!\main.py" (
    set IS_INSTALLED=1
    echo [%date% %time%] Detected: main.py exists >> "!LOG!"
)
if exist "!VENV_DIR!\Scripts\python.exe" (
    set IS_INSTALLED=1
    echo [%date% %time%] Detected: venv exists >> "!LOG!"
)
if exist "!CM_BAT!" (
    set IS_INSTALLED=1
    echo [%date% %time%] Detected: cm.bat exists >> "!LOG!"
)
echo [%date% %time%] IS_INSTALLED=!IS_INSTALLED! >> "!LOG!"

:menu
cls
echo.
echo   +==========================================+
echo   ^|        CloudMesh Installer v2.0         ^|
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
    echo [%date% %time%] User chose: !CHOICE! >> "!LOG!"
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
    echo [%date% %time%] User chose: !CHOICE! >> "!LOG!"
    if "!CHOICE!"=="1" goto :do_fresh
    if "!CHOICE!"=="2" goto :do_exit
)

echo.
echo   [!] Invalid choice.
timeout /t 2 >nul
goto :menu

:do_exit
echo [%date% %time%] Exiting >> "!LOG!"
exit /b 0

:do_uninstall
cls
echo.
echo   Uninstalling CloudMesh...
echo.
set /p "CONFIRM=   Are you sure? (y/n): "
if /i not "!CONFIRM!"=="y" goto :menu

if exist "%CLOUDMESH_DIR%" rmdir /s /q "%CLOUDMESH_DIR%" 2>nul
if exist "%NODE_DIR%" rmdir /s /q "%NODE_DIR%" 2>nul
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%" 2>nul
if exist "%CM_BAT%" del "%CM_BAT%" 2>nul
del "%TEMP%\cloudmesh.zip" 2>nul
echo   [OK] CloudMesh removed.
echo.
set IS_INSTALLED=0
pause
goto :menu

:do_update
cls
echo.
echo   Updating CloudMesh...
echo.
echo [%date% %time%] Starting update >> "!LOG!"

set BACKUP_DIR=%TEMP%\cloudmesh_backup
if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"
if exist "%CLOUDMESH_DIR%\.node_keys.json" copy /Y "%CLOUDMESH_DIR%\.node_keys.json" "!BACKUP_DIR!\" >nul 2>&1
if exist "%INSTALL_DIR%\cloudmesh.json" copy /Y "%INSTALL_DIR%\cloudmesh.json" "!BACKUP_DIR!\" >nul 2>&1
if exist "%INSTALL_DIR%\config.json" copy /Y "%INSTALL_DIR%\config.json" "!BACKUP_DIR!\" >nul 2>&1
echo   [OK] Config backed up
goto :do_download

:do_fresh
cls
echo.
echo   Fresh Install - Downloading CloudMesh...
echo.
echo [%date% %time%] Starting fresh install >> "!LOG!"
if "!IS_INSTALLED!"=="1" (
    if exist "%CLOUDMESH_DIR%" rmdir /s /q "%CLOUDMESH_DIR%" 2>nul
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
    echo   [OK] Old files removed
)
goto :do_download

:do_download
echo [%date% %time%] In do_download >> "!LOG!"
echo   Creating directories...

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%CLOUDMESH_DIR%" mkdir "%CLOUDMESH_DIR%"
echo   [OK] Dirs created >> "!LOG!"

echo.
echo   [1/4] Downloading from GitHub...

echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 > "%TEMP%\cm_dl.ps1"
echo $ProgressPreference = 'SilentlyContinue' >> "%TEMP%\cm_dl.ps1"
echo try { >> "%TEMP%\cm_dl.ps1"
echo     $url = 'https://github.com/!GITHUB_USER!/!GITHUB_REPO!/archive/refs/heads/!GITHUB_BRANCH!.zip' >> "%TEMP%\cm_dl.ps1"
echo     $dest = Join-Path $env:TEMP 'cloudmesh.zip' >> "%TEMP%\cm_dl.ps1"
echo     if (Test-Path $dest) { Remove-Item -Force $dest } >> "%TEMP%\cm_dl.ps1"
echo     Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing >> "%TEMP%\cm_dl.ps1"
echo     if (-not (Test-Path $dest) -or (Get-Item $dest).Length -eq 0) { throw 'empty download' } >> "%TEMP%\cm_dl.ps1"
echo     Write-Host '[OK] Downloaded' (Get-Item $dest).Length 'bytes' >> "%TEMP%\cm_dl.ps1"
echo } catch { >> "%TEMP%\cm_dl.ps1"
echo     Write-Host '[ERROR] Download failed:' $_.Exception.Message >> "%TEMP%\cm_dl.ps1"
echo     exit 1 >> "%TEMP%\cm_dl.ps1"
echo } >> "%TEMP%\cm_dl.ps1"
echo [%date% %time%] cm_dl.ps1 written >> "!LOG!"

powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\cm_dl.ps1"
echo [%date% %time%] Download result: !ERRORLEVEL! >> "!LOG!"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo   [ERROR] Download failed! Check internet.
    echo [%date% %time%] Download FAILED >> "!LOG!"
    del "%TEMP%\cm_dl.ps1" 2>nul
    pause
    goto :menu
)
del "%TEMP%\cm_dl.ps1" 2>nul
echo   [OK] Downloaded
echo.

echo   [2/4] Extracting files...
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
echo [%date% %time%] cm_ex.ps1 written >> "!LOG!"

powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\cm_ex.ps1"
echo [%date% %time%] Extract result: !ERRORLEVEL! >> "!LOG!"
del "%TEMP%\cm_ex.ps1" 2>nul

if not exist "%CLOUDMESH_DIR%\main.py" (
    echo   [ERROR] Extract failed!
    echo [%date% %time%] Extract FAILED - main.py missing >> "!LOG!"
    pause
    goto :menu
)
echo   [OK] Files extracted
echo.

echo   [3/4] Setting up...
echo. > "%CLOUDMESH_DIR%\core\__init__.py"

:: Restore config if update
if exist "!BACKUP_DIR!" (
    if exist "!BACKUP_DIR!\.node_keys.json" copy /Y "!BACKUP_DIR!\.node_keys.json" "%CLOUDMESH_DIR%\" >nul 2>&1
    if exist "!BACKUP_DIR!\cloudmesh.json" copy /Y "!BACKUP_DIR!\cloudmesh.json" "%INSTALL_DIR%\" >nul 2>&1
    if exist "!BACKUP_DIR!\config.json" copy /Y "!BACKUP_DIR!\config.json" "%INSTALL_DIR%\" >nul 2>&1
    rmdir /s /q "!BACKUP_DIR!" 2>nul
    echo   [OK] Config restored
)

:: Node setup
if not exist "%NODE_DIR%" mkdir "%NODE_DIR%"
if not exist "%NODE_DIR%\logs" mkdir "%NODE_DIR%\logs"
if not exist "%NODE_DIR%\data" mkdir "%NODE_DIR%\data"
if exist "%CLOUDMESH_DIR%\node\cloudmesh_node.py" (
    copy /Y "%CLOUDMESH_DIR%\node\cloudmesh_node.py" "%NODE_DIR%\cloudmesh_node.py" >nul 2>&1
    echo   [OK] Node agent installed
)
echo.

echo   [4/4] Creating venv and cm shortcut...
echo [%date% %time%] Checking Python >> "!LOG!"
python --version >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    python3 --version >nul 2>&1
)
if !ERRORLEVEL! NEQ 0 (
    echo   [WARNING] Python not found. Install Python to use CloudMesh.
    echo   [INFO] https://www.python.org/downloads/
    echo [%date% %time%] Python NOT found >> "!LOG!"
    set IS_INSTALLED=1
    pause
    goto :menu
)
echo [%date% %time%] Python found >> "!LOG!"

if not exist "%VENV_DIR%" (
    echo [%date% %time%] Creating venv... >> "!LOG!"
    python -m venv "%VENV_DIR%" 2>nul
    if !ERRORLEVEL! NEQ 0 (
        python3 -m venv "%VENV_DIR%" 2>nul
    )
    echo [%date% %time%] Venv created: !ERRORLEVEL! >> "!LOG!"
)

if exist "%VENV_PYTHON%" (
    echo [%date% %time%] Installing deps... >> "!LOG!"
    "%VENV_PYTHON%" -m pip install -q psutil rich paramiko cryptography pycryptodome 2>nul
    echo   [OK] Dependencies installed
    echo [%date% %time%] Deps installed >> "!LOG!"
) else (
    echo   [WARNING] Could not create Python environment
    echo [%date% %time%] VENV_PYTHON NOT found >> "!LOG!"
)
echo.

(
echo @echo off
echo setlocal
echo set "CLOUDMESH_DIR=%CLOUDMESH_DIR%"
echo set "VENV_PYTHON=%VENV_PYTHON%"
echo if not exist "%%VENV_PYTHON%%" (
echo     echo [ERROR] Virtual environment not found. Reinstall CloudMesh.
echo     exit /b 1
echo ^)
echo "%%VENV_PYTHON%%" "%%CLOUDMESH_DIR%%\main.py" %%*
) > "%CM_BAT%"
echo   [OK] cm command ready
echo.

set IS_INSTALLED=1
echo [%date% %time%] Installation complete! >> "!LOG!"

echo   +==========================================+
echo   ^|    CloudMesh Installed Successfully!    ^|
echo   +==========================================+
echo.
echo   Quick Start:
echo   cm --help              Show commands
echo   cm interactive         Interactive TUI
echo   cm version             Show version
echo.
echo   Location: %CLOUDMESH_DIR%
echo.
echo   Log file: !LOG!
echo.
pause
goto :menu