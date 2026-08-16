@echo off
echo ============================================
echo    CloudMesh Node Installer (Windows)
echo ============================================
echo.

set INSTALL_DIR=%USERPROFILE%\.cloudmesh-node
set PROGRAMS_DIR=%USERPROFILE%\CloudMesh

:: ============================================
:: 1. Check Python
:: ============================================
echo [1/5] Checking Python...

python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python found:
    python --version
    goto :python_ok
)

python3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python3 found:
    python3 --version
    goto :python_ok
)

echo [INFO] Python not found. Installing...

:: Try winget first
winget --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Installing Python via winget...
    winget install Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
    goto :refresh_path
)

:: Try chocolatey
choco --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Installing Python via Chocolatey...
    choco install python -y
    goto :refresh_path
)

:: Try scoop
scoop --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Installing Python via Scoop...
    scoop install python
    goto :refresh_path
)

:: Manual download
echo [INFO] Downloading Python installer...
echo.
echo Please download Python from: https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation!
echo.
echo Press any key to open download page...
pause >nul
start https://www.python.org/downloads/
echo.
echo After installing Python, run this script again.
pause
exit /b 1

:refresh_path
echo [INFO] Refreshing PATH...
call :set_path

:python_ok

:: Verify Python works
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    python3 --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Python installation failed or not in PATH.
        echo [INFO] Please restart your terminal and try again.
        pause
        exit /b 1
    )
)

echo.

:: ============================================
:: 2. Install psutil
:: ============================================
echo [2/5] Installing dependencies...

python -m pip install --user psutil 2>nul
if %ERRORLEVEL% NEQ 0 (
    python3 -m pip install --user psutil 2>nul
)
echo [OK] Dependencies installed

:: ============================================
:: 3. Create install directory
:: ============================================
echo [3/5] Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"

:: ============================================
:: 4. Install CloudMesh Node (COMPLETE)
:: ============================================
echo [4/5] Installing CloudMesh Node...

:: Copy standalone node agent (with GPU + async jobs)
set NODE_SOURCE=%~dp0cloudmesh_node.py
if exist "%NODE_SOURCE%" (
    copy /Y "%NODE_SOURCE%" "%INSTALL_DIR%\cloudmesh_node.py" >nul
    echo [OK] Node agent installed (with GPU + async jobs)
) else (
    echo [ERROR] cloudmesh_node.py not found at %NODE_SOURCE%
    exit /b 1
)

:: ============================================
:: 5. Create helper scripts
:: ============================================
echo [5/5] Creating scripts...

(
echo @echo off
echo cd /d "%%~dp0"
echo python cloudmesh_node.py start %%*
) > "%INSTALL_DIR%\start.bat"

(
echo @echo off
echo cd /d "%%~dp0"
echo python cloudmesh_node.py stop
) > "%INSTALL_DIR%\stop.bat"

(
echo @echo off
echo cd /d "%%~dp0"
echo python cloudmesh_node.py status
) > "%INSTALL_DIR%\status.bat"

(
echo @echo off
echo cd /d "%%~dp0"
echo call stop.bat
echo timeout /t 2 /nobreak ^>nul
echo call start.bat
) > "%INSTALL_DIR%\restart.bat"

echo [OK] Scripts created

:: ============================================
:: Print summary
:: ============================================
echo.
echo ============================================
echo    CloudMesh Node Installed!
echo ============================================
echo.
echo  [OK] Location: %INSTALL_DIR%
echo.

:: Get auth key
set AUTH_KEY=N/A
if exist "%INSTALL_DIR%\.node_key" (
    set /p AUTH_KEY=<"%INSTALL_DIR%\.node_key"
)

:: Get IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4" ^| findstr /v "127.0.0.1"') do (
    for /f "tokens=1" %%b in ("%%a") do set IP_ADDRESS=%%b
)

echo  [OK] Auth Key: %AUTH_KEY%
echo.
echo  === Commands ===
echo  Start:    %INSTALL_DIR%\start.bat
echo  Stop:     %INSTALL_DIR%\stop.bat
echo  Status:   %INSTALL_DIR%\status.bat
echo  Restart:  %INSTALL_DIR%\restart.bat
echo.
echo  === Add from Controller (your laptop) ===
echo  cloudmesh node add -n %COMPUTERNAME% -H %IP_ADDRESS% -p 9999 -k %AUTH_KEY%
echo.
echo  === Test connection ===
echo  cloudmesh node test -n %COMPUTERNAME%
echo.

:: Ask to start now
set /p START_NOW="Start node now? (y/n): "
if /i "%START_NOW%"=="y" (
    echo.
    echo Starting CloudMesh Node...
    call "%INSTALL_DIR%\start.bat"
)

pause

:set_path
:: Helper to refresh PATH
set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\
set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312\
set PATH=%PATH%;C:\Python312\
set PATH=%PATH%;C:\Python312\Scripts\
goto :eof
