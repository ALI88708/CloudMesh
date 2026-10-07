@echo off
setlocal enabledelayedexpansion
title CloudMesh Installer - MRSX PRO

set GITHUB_USER=ALI88708
set GITHUB_REPO=CloudMesh
set GITHUB_BRANCH=main

REM ============================================
REM NON-INTERACTIVE MODE
REM ============================================
REM The interactive menu cannot be driven by CI, so this installer has a
REM scripted path: pass /Y (or set CM_NONINTERACTIVE=1) to install with no
REM prompts and then verify the result works.
REM
REM   /Y              install with no prompts
REM   /S=DIR          install from a local checkout instead of downloading
REM   /SKIPNODE       controller only; do not install the node agent
REM   /VERIFYONLY     do not install; only run the checks
set "NONINTERACTIVE=%CM_NONINTERACTIVE%"
set "SOURCE_DIR=%CM_SOURCE_DIR%"
set "SKIP_NODE=%CM_SKIP_NODE%"
set "VERIFY_ONLY=%CM_VERIFY_ONLY%"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="/Y"        set "NONINTERACTIVE=1" & shift & goto parse_args
if /I "%~1"=="-Y"        set "NONINTERACTIVE=1" & shift & goto parse_args
if /I "%~1"=="/SKIPNODE" set "SKIP_NODE=1" & shift & goto parse_args
if /I "%~1"=="/VERIFYONLY" set "VERIFY_ONLY=1" & shift & goto parse_args
if /I "%~1"=="/?"        goto usage
if /I "%~1"=="-h"        goto usage
if /I "%~1"=="/HELP"     goto usage
echo /S=DIR "%~1" & set "SOURCE_DIR=%~2" & shift & shift & goto parse_args
echo Unknown option: %~1 1>&2
exit /b 2

:args_done
if not defined NONINTERACTIVE set "NONINTERACTIVE=0"
if not defined SKIP_NODE   set "SKIP_NODE=0"
if not defined VERIFY_ONLY set "VERIFY_ONLY=0"
REM /VERIFYONLY on its own would otherwise drop into the interactive menu and
REM sit there waiting for a keypress.
if not "%VERIFY_ONLY%"=="0" set "NONINTERACTIVE=1"
REM Skip over the :usage block below; falling into it printed usage for every
REM invocation, including a perfectly good /Y install.
goto :after_usage

:usage
echo CloudMesh Installer - Windows (MRSX PRO)
echo.
echo   cm_for-windows.bat             interactive menu
echo   cm_for-windows.bat /Y          install with no prompts ^(used by CI^)
echo   cm_for-windows.bat /VERIFYONLY assert the current install works
echo.
echo Options:
echo   /Y              install without prompting
echo   /S=DIR          install from a local checkout instead of downloading
echo   /SKIPNODE       controller only; do not install the node agent
echo   /VERIFYONLY     do not install; only run the checks
exit /b 0

:after_usage
set INSTALL_DIR=%USERPROFILE%\CloudMesh
REM pyproject.toml declares `packages = ["cloudmesh", ...]`, so the directory
REM handed to pip has to CONTAIN the cloudmesh\ package. Laying the package out
REM at the install root instead installs nothing and produces no `cm` script.
set "PROJECT_DIR=%INSTALL_DIR%\project"
set "CLOUDMESH_DIR=%PROJECT_DIR%\cloudmesh"
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
set "GIT_AVAILABLE=0"
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
where git >nul 2>&1 && set "GIT_AVAILABLE=1"

REM Jump over the subroutine definitions below; without this the setup block
REM fell straight into :verify_install and nothing was ever installed.
goto :menu

REM ============================================
REM GIT
REM ============================================
REM `cm update` is git-based (fetch + pull), and pushing your own work needs git
REM too. Nothing used to check for it, so a user could install CloudMesh, read
REM "cm update (recommended)" in the README, and only find out at the worst moment.
:check_git
set "GIT_AVAILABLE=0"
where git >nul 2>&1
if not !ERRORLEVEL! NEQ 0 goto :git_missing

set "GIT_AVAILABLE=1"
for /f "tokens=3" %%v in ('git --version 2^>nul') do set "GIT_VERSION=%%v"
echo   [OK] Git found !GIT_VERSION!
echo [%date% %time%] Git already present >> "!LOG!"
exit /b 0

:git_missing
set "GIT_AVAILABLE=0"
echo   [!] Git not found. Without it 'cm update' cannot pull, and git push will not work.
echo [%date% %time%] Git MISSING >> "!LOG!"

REM A prompt would hang CI, so --default n and no read under non-interactive.
if not "%NONINTERACTIVE%"=="0" (
    echo   [OK] Skipping Git ^(non-interactive^). cm update will need pip instead.
    exit /b 0
)

set "CHOICE="
set /p "CHOICE=   Install Git now? (y/n): "
if /i not "!CHOICE!"=="y" (
    echo   [OK] Skipping Git. CloudMesh still works; cm update needs pip instead.
    exit /b 0
)

set "INSTALLER="
where winget >nul 2>&1 && set "INSTALLER=winget"
if not defined INSTALLER (
    where choco >nul 2>&1 && set "INSTALLER=choco"
)
if not defined INSTALLER (
    echo   [!] Neither winget nor Chocolatey found. Install Git from https://git-scm.com/download/win
    exit /b 0
)

echo   Installing Git via !INSTALLER! ...
if /i "!INSTALLER!"=="winget" (
    winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements --silent
) else (
    choco install git -y --no-progress
)

where git >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo   [!] Git install did not complete. cm update will need pip instead.
    echo [%date% %time%] Git install FAILED >> "!LOG!"
    exit /b 0
)

set "GIT_AVAILABLE=1"
for /f "tokens=3" %%v in ('git --version 2^>nul') do set "GIT_VERSION=%%v"
echo   [OK] Git installed !GIT_VERSION!
echo [%date% %time%] Git installed >> "!LOG!"
exit /b 0

REM ============================================
REM VERIFY THE INSTALL ACTUALLY WORKS
REM ============================================
REM The installer used to report success as soon as files landed on disk, so a
REM missing dependency or a missing console script looked like a clean install.
REM CI calls this; /VERIFYONLY re-runs it against an existing install.
:verify_install
echo.
echo   ============================================
echo      Verifying the install...
echo   ============================================
set "VFAILED=0"
set "CORE_INIT_SIZE=0"

if exist "%VENV_DIR%\Scripts\cm.exe" (
    echo   [OK] cm console script present
) else (
    echo   [FAIL] cm console script missing 1>&2
    set "VFAILED=1"
)

if "%GIT_AVAILABLE%"=="1" (
    echo   [OK] git available
) else (
    echo   [WARN] git not available; cm update will need pip
)

"%VENV_PYTHON%" -c "import cloudmesh, rich, paramiko, psutil, cryptography, Crypto, bcrypt" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo   [FAIL] one or more runtime dependencies are missing 1>&2
    set "VFAILED=1"
) else (
    echo   [OK] all runtime dependencies import
)

"%VENV_DIR%\Scripts\cm.exe" --version >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo   [FAIL] 'cm --version' failed 1>&2
    set "VFAILED=1"
) else (
    echo   [OK] cm --version works
)

"%VENV_DIR%\Scripts\cm.exe" --help >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo   [FAIL] 'cm --help' failed 1>&2
    set "VFAILED=1"
) else (
    echo   [OK] cm --help works
)

if not "%SKIP_NODE%"=="1" (
    if exist "%NODE_DIR%\cloudmesh_node.py" (
        echo   [OK] node agent present
    ) else (
        echo   [FAIL] node agent missing 1>&2
        set "VFAILED=1"
    )
)

REM The installer used to blank this file out; core/__init__.py carries the
REM package re-exports that "from cloudmesh.core import ..." relies on.
if exist "%CLOUDMESH_DIR%\core\__init__.py" (
    for %%A in ("%CLOUDMESH_DIR%\core\__init__.py") do set "CORE_INIT_SIZE=%%~zA"
) else (
    set "CORE_INIT_SIZE=0"
)
if !CORE_INIT_SIZE! LSS 10 (
    echo   [FAIL] core\__init__.py missing or truncated ^(!CORE_INIT_SIZE! bytes^) 1>&2
    set "VFAILED=1"
) else (
    echo   [OK] core\__init__.py intact ^(!CORE_INIT_SIZE! bytes^)
)

echo.
if not "%VFAILED%"=="0" (
    echo   [FAIL] install verification failed 1>&2
    exit /b 1
)
echo   [OK] install verified
echo.
exit /b 0

REM ============================================
REM SCRIPTED PATH
REM ============================================
REM Runs the install with no prompts and then asserts the result works.
:run_scripted
if not "%VERIFY_ONLY%"=="0" goto :do_verify_only

REM Git first: `cm update` and `git push` both need it, and a user who will
REM push their own work wants to know before the install finishes.
call :check_git

if "!IS_INSTALLED!"=="1" (
    echo   Reinstalling over the existing install...
    if exist "%CLOUDMESH_DIR%" rmdir /s /q "%CLOUDMESH_DIR%" 2>nul
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
)

REM do_payload copies the tree first when CM_SOURCE_DIR is set; do_download
REM skips its own download if the payload is already in place.
if not "%SOURCE_DIR%"=="" call :do_copy_payload
if !ERRORLEVEL! NEQ 0 exit /b !ERRORLEVEL!
goto :do_download

:do_verify_only
call :verify_install
exit /b !ERRORLEVEL!

:menu
if not "%NONINTERACTIVE%"=="0" goto :run_scripted
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
if not "%NONINTERACTIVE%"=="0" exit /b 0
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

:do_copy_payload
REM Install from a local checkout instead of downloading, so CI verifies the
REM branch under test rather than whatever happens to be on main.
echo   Copying source from %SOURCE_DIR%
if not exist "%SOURCE_DIR%\cloudmesh\main.py" (
    echo   [FAIL] %SOURCE_DIR% has no cloudmesh\main.py 1>&2
    exit /b 1
)
if exist "%PROJECT_DIR%" rmdir /s /q "%PROJECT_DIR%" 2>nul
mkdir "%PROJECT_DIR%" 2>nul
xcopy /E /I /Q /Y "%SOURCE_DIR%\cloudmesh" "%CLOUDMESH_DIR%" >nul 2>&1
for %%F in (pyproject.toml README.md License) do (
    if exist "%SOURCE_DIR%\%%F" copy /Y "%SOURCE_DIR%\%%F" "%PROJECT_DIR%\%%F" >nul 2>&1
)
if not exist "%PROJECT_DIR%\pyproject.toml" (
    echo   [FAIL] pyproject.toml missing from %SOURCE_DIR% 1>&2
    exit /b 1
)
echo   [OK] Source copied
exit /b 0

:do_download
echo [%date% %time%] In do_download >> "!LOG!"
echo   Creating directories...

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%PROJECT_DIR%" mkdir "%PROJECT_DIR%"
echo   [OK] Dirs created >> "!LOG!"

REM Already staged (CM_SOURCE_DIR path): skip straight to the extract check.
if exist "%CLOUDMESH_DIR%\main.py" goto :have_payload

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
    REM Under /Y the menu routes straight back into the scripted path, turning
    REM a failed download into an endless loop instead of a failed build.
    if not "%NONINTERACTIVE%"=="0" exit /b 1
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
echo $destPath = '%PROJECT_DIR%' >> "%TEMP%\cm_ex.ps1"
echo if (Test-Path $destPath) { Remove-Item -Recurse -Force $destPath } >> "%TEMP%\cm_ex.ps1"
echo Copy-Item -Path (Join-Path $d.FullName 'cloudmesh') -Destination $destPath -Recurse -Force >> "%TEMP%\cm_ex.ps1"
REM pyproject.toml is what makes the directory an installable project.
echo foreach ($f in @('pyproject.toml','README.md','License')) { >> "%TEMP%\cm_ex.ps1"
echo     $src = Join-Path $d.FullName $f >> "%TEMP%\cm_ex.ps1"
echo     if (Test-Path $src) { Copy-Item -Force $src (Join-Path $destPath $f) } >> "%TEMP%\cm_ex.ps1"
echo } >> "%TEMP%\cm_ex.ps1"
echo Remove-Item -Recurse -Force $out >> "%TEMP%\cm_ex.ps1"
echo Remove-Item -Force $zip >> "%TEMP%\cm_ex.ps1"
echo [%date% %time%] cm_ex.ps1 written >> "!LOG!"

powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\cm_ex.ps1"
echo [%date% %time%] Extract result: !ERRORLEVEL! >> "!LOG!"
del "%TEMP%\cm_ex.ps1" 2>nul

:have_payload
if not exist "%CLOUDMESH_DIR%\main.py" (
    echo   [ERROR] Extract failed!
    echo [%date% %time%] Extract FAILED - main.py missing >> "!LOG!"
    if not "%NONINTERACTIVE%"=="0" exit /b 1
    pause
    goto :menu
)
echo   [OK] Files extracted
echo.

echo   [3/4] Setting up...

:: core/__init__.py is deliberately left alone. It used to be overwritten with
:: `echo. >`, blanking the package re-exports that
:: `from cloudmesh.core import ServerManager` and friends depend on.

:: Restore config if update
if exist "!BACKUP_DIR!" (
    if exist "!BACKUP_DIR!\.node_keys.json" copy /Y "!BACKUP_DIR!\.node_keys.json" "%CLOUDMESH_DIR%\" >nul 2>&1
    if exist "!BACKUP_DIR!\cloudmesh.json" copy /Y "!BACKUP_DIR!\cloudmesh.json" "%INSTALL_DIR%\" >nul 2>&1
    if exist "!BACKUP_DIR!\config.json" copy /Y "!BACKUP_DIR!\config.json" "%INSTALL_DIR%\" >nul 2>&1
    rmdir /s /q "!BACKUP_DIR!" 2>nul
    echo   [OK] Config restored
)

:: Node setup
if not "%SKIP_NODE%"=="1" (
    if not exist "%NODE_DIR%" mkdir "%NODE_DIR%"
    if not exist "%NODE_DIR%\logs" mkdir "%NODE_DIR%\logs"
    if not exist "%NODE_DIR%\data" mkdir "%NODE_DIR%\data"
    if exist "%CLOUDMESH_DIR%\node\cloudmesh_node.py" (
        copy /Y "%CLOUDMESH_DIR%\node\cloudmesh_node.py" "%NODE_DIR%\cloudmesh_node.py" >nul 2>&1
        echo   [OK] Node agent installed
    )
) else (
    echo   [OK] Node agent skipped
)
echo.

echo   [4/4] Creating venv and cm shortcut...
echo [%date% %time%] Checking Python >> "!LOG!"
set "BOOT_PY="
where python >nul 2>&1 && set "BOOT_PY=python"
if not defined BOOT_PY (
    where py >nul 2>&1 && set "BOOT_PY=py"
)
if not defined BOOT_PY (
    where python3 >nul 2>&1 && set "BOOT_PY=python3"
)
if not defined BOOT_PY (
    echo   [FAIL] Python not found. Install Python from https://www.python.org/downloads/ 1>&2
    echo [%date% %time%] Python NOT found >> "!LOG!"
    exit /b 1
)
echo [%date% %time%] Python found: !BOOT_PY! >> "!LOG!"

if not exist "%VENV_DIR%" (
    echo [%date% %time%] Creating venv... >> "!LOG!"
    !BOOT_PY! -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo   [FAIL] could not create the virtual environment 1>&2
        exit /b 1
    )
)

if not exist "%VENV_PYTHON%" (
    echo   [FAIL] virtual environment python missing at %VENV_PYTHON% 1>&2
    exit /b 1
)

REM Install the project, not a hand-written dependency list. The old list named
REM five packages and omitted bcrypt, so ACL commands raised ImportError on any
REM machine that installed this way. `pip install .` also produces the real
REM `cm` console script instead of a wrapper that runs main.py directly.
echo [%date% %time%] Installing CloudMesh into the venv... >> "!LOG!"
"%VENV_PYTHON%" -m pip install --quiet --upgrade pip
"%VENV_PYTHON%" -m pip install --quiet "%PROJECT_DIR%"
if !ERRORLEVEL! NEQ 0 (
    echo   [FAIL] pip install failed 1>&2
    echo [%date% %time%] pip install FAILED >> "!LOG!"
    exit /b 1
)
echo   [OK] CloudMesh installed
echo [%date% %time%] Deps installed >> "!LOG!"
echo.

(
echo @echo off
echo setlocal
echo set "CLOUDMESH_DIR=%CLOUDMESH_DIR%"
echo set "VENV_PYTHON=%VENV_PYTHON%"
echo set "VENV_CM=%VENV_DIR%\Scripts\cm.exe"
echo if exist "%%VENV_CM%%" (
echo     "%%VENV_CM%%" %%* ^& exit /b %%ERRORLEVEL%%
echo ^)
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

if not "%NONINTERACTIVE%"=="0" (
    call :verify_install
    exit /b !ERRORLEVEL!
)

pause
goto :menu