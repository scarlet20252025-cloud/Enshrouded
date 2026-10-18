@echo off
setlocal

REM ---------------------------------------------------------------------------
REM  WolfMount uninstall script
REM
REM  Removes the registry entry, the layer DLL and the manifest. The layer
REM  never modifies any game file, so this is a complete removal.
REM
REM  No administrator rights required: the normal install lives in HKCU. A
REM  leftover HKLM entry from an older install is reported, not silently
REM  ignored, because a half-removed layer is worse than no layer.
REM
REM  Usage: uninstall.bat [game-directory]
REM         If omitted, the game is located through the Steam library.
REM ---------------------------------------------------------------------------

set ROOT=%~dp0
set GAMEDIR=%~1

echo.
echo  WolfMount uninstaller
echo  ---------------------

REM ---- locate the game ------------------------------------------------------
if "%GAMEDIR%"=="" (
    for /f "usebackq delims=" %%D in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%tools\find-game.ps1"`) do set GAMEDIR=%%D
    if not defined GAMEDIR (
        echo [ERROR] Enshrouded not found in any Steam library.
        echo         Pass the game directory explicitly:
        echo           uninstall.bat "C:\Path\To\Enshrouded"
        exit /b 1
    )
)
echo       %GAMEDIR%

set MANIFEST=%GAMEDIR%\VK_LAYER_WOLFMOUNT_wolfmount.json

REM ---- registry -------------------------------------------------------------
echo [1/3] removing registry entries
reg delete "HKCU\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "%MANIFEST%" /f >nul 2>&1
if errorlevel 1 (
    echo       no per-user entry ^(already removed^)
) else (
    echo       removed per-user entry
)

REM Only report; do not attempt elevation. If we cannot remove it we say so.
reg query "HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "%MANIFEST%" >nul 2>&1
if not errorlevel 1 (
    reg delete "HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "%MANIFEST%" /f >nul 2>&1
    if errorlevel 1 (
        echo [WARN] a machine-wide entry still exists and needs elevation:
        echo          reg delete "HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "%MANIFEST%" /f
    ) else (
        echo       removed machine-wide entry
    )
)

REM ---- files ----------------------------------------------------------------
echo [2/3] removing files
del /Q "%GAMEDIR%\wolfmount_layer.dll" 2>nul
del /Q "%GAMEDIR%\wolfmount_layer.dll.log" 2>nul
del /Q "%GAMEDIR%\wolfmount_layer.dll.settings.json" 2>nul
del /Q "%MANIFEST%" 2>nul
echo       done

echo [3/3] verifying removal
if exist "%GAMEDIR%\wolfmount_layer.dll" (
    echo [WARN] wolfmount_layer.dll is still present - is the game running?
    echo        Close Enshrouded and run this again.
) else (
    echo       wolfmount_layer.dll removed
)
if exist "%MANIFEST%" (
    echo [WARN] manifest is still present.
) else (
    echo       manifest removed
)

echo.
echo [OK] uninstalled. No game file was ever modified.
exit /b 0
