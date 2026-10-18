@echo off
setlocal

REM ---------------------------------------------------------------------------
REM  WolfMount install script
REM
REM  Registers the Vulkan implicit layer and copies the DLL + manifest into the
REM  game directory.
REM
REM  NO ADMINISTRATOR RIGHTS REQUIRED. We write HKCU only. The Vulkan loader
REM  scans both HKLM and HKCU implicit-layer keys, so per-user registration is
REM  sufficient, and it is what this community should expect: a mod you can try
REM  without elevating, and remove by deleting a folder.
REM
REM  IMPORTANT registry semantics (learned the hard way):
REM    The value NAME is the full path to the JSON manifest.
REM    The value TYPE is REG_DWORD.
REM    The value DATA means:  0 = ENABLED,  1 = DISABLED.
REM  This is the opposite of the intuitive reading. See MODLOG.md.
REM
REM  Usage: install.bat [game-directory]
REM         If omitted, the game is located through the Steam library.
REM ---------------------------------------------------------------------------

set ROOT=%~dp0
set BUILD=%ROOT%build
set REGKEY=HKCU\SOFTWARE\Khronos\Vulkan\ImplicitLayers
set GAMEDIR=%~1

echo.
echo  WolfMount installer
echo  -------------------

if not exist "%BUILD%\wolfmount_layer.dll" (
    echo [ERROR] build\wolfmount_layer.dll not found.
    echo         Run build.bat first.
    exit /b 1
)

REM ---- locate the game ------------------------------------------------------
if "%GAMEDIR%"=="" (
    echo [1/4] locating Enshrouded through Steam
    for /f "usebackq delims=" %%D in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%tools\find-game.ps1"`) do set GAMEDIR=%%D
    if not defined GAMEDIR (
        echo [ERROR] Enshrouded not found in any Steam library.
        echo         Pass the game directory explicitly:
        echo           install.bat "C:\Path\To\Enshrouded"
        exit /b 1
    )
) else (
    echo [1/4] using supplied game directory
)
echo       %GAMEDIR%

if not exist "%GAMEDIR%\enshrouded.exe" (
    echo [ERROR] enshrouded.exe not found in "%GAMEDIR%"
    exit /b 1
)

REM ---- copy files -----------------------------------------------------------
set MANIFEST=%GAMEDIR%\VK_LAYER_WOLFMOUNT_wolfmount.json

echo [2/4] copying layer files
REM The overwhelmingly common failure here is that the game is still running and
REM has the DLL mapped, which looks like a permissions error but is not. Check
REM for the process so the message tells the truth.
tasklist /FI "IMAGENAME eq enshrouded.exe" 2>nul | find /I "enshrouded.exe" >nul
if not errorlevel 1 (
    echo [ERROR] Enshrouded is running. Close it first - the layer DLL is
    echo         currently loaded and cannot be replaced.
    exit /b 1
)

copy /Y "%BUILD%\wolfmount_layer.dll" "%GAMEDIR%\" >nul
if errorlevel 1 (
    echo [ERROR] could not write to "%GAMEDIR%".
    echo         If the game lives in Program Files, either move the Steam
    echo         library or run this from an account that can write there.
    exit /b 1
)
copy /Y "%ROOT%VK_LAYER_WOLFMOUNT_wolfmount.json" "%GAMEDIR%\" >nul
if errorlevel 1 exit /b 1

REM ---- register -------------------------------------------------------------
echo [3/4] registering implicit layer for the current user ^(0 = enabled^)
reg add "%REGKEY%" /v "%MANIFEST%" /t REG_DWORD /d 0 /f >nul
if errorlevel 1 (
    echo [ERROR] registry registration failed.
    exit /b 1
)

REM A stale HKLM entry from an older install would register the same manifest
REM twice. Warn rather than silently depending on elevation to clean it up.
reg query "HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "%MANIFEST%" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] a machine-wide registration for this manifest also exists.
    echo        Run uninstall.bat once from an elevated prompt to remove it,
    echo        otherwise the layer may be registered twice.
)

REM ---- verify ---------------------------------------------------------------
echo [4/4] verifying
reg query "%REGKEY%" /v "%MANIFEST%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] verification failed: the value was not written.
    exit /b 1
)
echo       registered: %MANIFEST%

echo.
echo [OK] installed.
echo.
echo   Launch Enshrouded, load a world, then press F8 for the menu
echo   or F9 for the command console.
echo.
echo   To remove: uninstall.bat
echo.
exit /b 0
