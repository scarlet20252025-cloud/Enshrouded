@echo off
setlocal

REM ---------------------------------------------------------------------------
REM  Run every WolfMount test and print a single summary line.
REM  Safe to run repeatedly; nothing here touches the game.
REM ---------------------------------------------------------------------------

set ROOT=%~dp0..
set BUILD=%ROOT%\build
set TOOLCHAIN=C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin

if not exist "%TOOLCHAIN%\clang++.exe" (
    echo [ERROR] clang not found
    exit /b 1
)

echo ============================================================
echo  WolfMount test suite
echo ============================================================
echo.

set FAILED=0

echo --- [1/9] ECS probe self test -----------------------------------------
set EXE=notfound
for %%G in (
    "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
    "D:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
    "C:\Program Files (x86)\Steam\steamapps\common\Enshrouded\enshrouded.exe"
    "D:\Steam\steamapps\common\Enshrouded\enshrouded.exe"
) do if exist %%G set EXE=%%~G

if "%EXE%"=="notfound" (
    echo     SKIP -- enshrouded.exe not found
) else (
    "%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 -static-libstdc++ -static-libgcc ^
        "%ROOT%\tools\ecs-selftest.cpp" -o "%BUILD%\ecs-selftest.exe" >nul 2>&1
    "%BUILD%\ecs-selftest.exe" "%EXE%" > "%BUILD%\ecs.out" 2>&1
    findstr /C:"RESULT: PASS" "%BUILD%\ecs.out" > nul
    if errorlevel 1 (
        echo     FAIL
        type "%BUILD%\ecs.out"
        set FAILED=1
    ) else (
        echo     PASS -- 7/7 ECS signatures in the shipped exe
    )
)
echo.

echo --- [2/9] taming rules ------------------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 -static-libstdc++ -static-libgcc ^
    -I"%ROOT%\src" "%ROOT%\tools\tame-test.cpp" "%ROOT%\src\tame.cpp" ^
    -o "%BUILD%\tame-test.exe" >nul 2>&1
"%BUILD%\tame-test.exe" > "%BUILD%\tame.out" 2>&1
findstr /C:"RESULT: PASS" "%BUILD%\tame.out" > nul
if errorlevel 1 (
    echo     FAIL
    type "%BUILD%\tame.out"
    set FAILED=1
) else (
    echo     PASS -- all taming rules ^(wolf+torch, uniqueness, re-block^)
)
echo.

echo --- [3/9] combat follow plan -----------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 -static-libstdc++ -static-libgcc ^
    -I"%ROOT%\src" "%ROOT%\tools\follow-test.cpp" "%ROOT%\src\follow.cpp" ^
    -o "%BUILD%\follow-test.exe" >nul 2>&1
"%BUILD%\follow-test.exe" > "%BUILD%\follow.out" 2>&1
findstr /C:"RESULT: PASS" "%BUILD%\follow.out" > nul
if errorlevel 1 (
    echo     FAIL
    type "%BUILD%\follow.out"
    set FAILED=1
) else (
    echo     PASS -- faction/IsTame/Animal plan matches shipped data
)
echo.

echo --- [4/9] mount state machine ----------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 -static-libstdc++ -static-libgcc ^
    -I"%ROOT%\src" "%ROOT%\tools\mount-test.cpp" "%ROOT%\src\mount.cpp" ^
    -o "%BUILD%\mount-test.exe" >nul 2>&1
"%BUILD%\mount-test.exe" > "%BUILD%\mount.out" 2>&1
findstr /C:"RESULT: PASS" "%BUILD%\mount.out" > nul
if errorlevel 1 (
    echo     FAIL
    type "%BUILD%\mount.out"
    set FAILED=1
) else (
    echo     PASS -- attachment/camera/pose + enter-exit transitions
)
echo.

echo --- [5/9] detour engine ----------------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 -static-libstdc++ -static-libgcc ^
    -I"%ROOT%\src" "%ROOT%\tools\detour-test.cpp" "%ROOT%\src\detour.cpp" ^
    -o "%BUILD%\detour-test.exe" >nul 2>&1
"%BUILD%\detour-test.exe" > "%BUILD%\detour.out" 2>&1
findstr /C:"RESULT: PASS" "%BUILD%\detour.out" > nul
if errorlevel 1 (
    echo     FAIL
    type "%BUILD%\detour.out"
    set FAILED=1
) else (
    echo     PASS -- inline hook install/call/remove round-trip
)
echo.

echo --- [6/9] console command honesty ------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 -static-libstdc++ -static-libgcc ^
    -I"%ROOT%\src" "%ROOT%\tools\console-test.cpp" "%ROOT%\src\console.cpp" ^
    -o "%BUILD%\console-test.exe" > "%BUILD%\console-build.out" 2>&1
if errorlevel 1 (
    echo     FAIL -- compile
    type "%BUILD%\console-build.out"
    set FAILED=1
) else (
    "%BUILD%\console-test.exe" > "%BUILD%\console.out" 2>&1
    findstr /C:"RESULT: PASS" "%BUILD%\console.out" > nul
    if errorlevel 1 (
        echo     FAIL
        type "%BUILD%\console.out"
        set FAILED=1
    ) else (
        echo     PASS -- missing backends report NotAvailable, never Ok
    )
)
echo.

echo --- [7/9] entity backend --------------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 -static-libstdc++ -static-libgcc ^
    -I"%ROOT%\src" "%ROOT%\tools\entityops-test.cpp" ^
    "%ROOT%\tools\gamehooks-stub.cpp" "%ROOT%\src\entityops.cpp" ^
    -o "%BUILD%\entityops-test.exe" > "%BUILD%\entityops-build.out" 2>&1
if errorlevel 1 (
    echo     FAIL -- compile
    type "%BUILD%\entityops-build.out"
    set FAILED=1
) else (
    "%BUILD%\entityops-test.exe" > "%BUILD%\entityops.out" 2>&1
    findstr /C:"RESULT: PASS" "%BUILD%\entityops.out" > nul
    if errorlevel 1 (
        echo     FAIL
        type "%BUILD%\entityops.out"
        set FAILED=1
    ) else (
        echo     PASS -- GUID parse/format + template table
    )
)
echo.

echo --- [8/9] layer build -------------------------------------------------
call "%ROOT%\build.bat" > "%BUILD%\build.out" 2>&1
if errorlevel 1 (
    echo     FAIL
    type "%BUILD%\build.out"
    set FAILED=1
) else (
    echo     PASS -- wolfmount_layer.dll built
)
echo.

echo --- [9/9] vulkan loader sees the layer -------------------------------
cmd /c "%ROOT%\tools\build-smoketest.bat" > "%BUILD%\smoke.out" 2>&1
findstr /C:"RESULT: PASS" "%BUILD%\smoke.out" > nul
if errorlevel 1 (
    echo     FAIL
    type "%BUILD%\smoke.out"
    set FAILED=1
) else (
    echo     PASS -- layer registered and enumerated by the loader
)
echo.

echo ============================================================
if "%FAILED%"=="0" (
    echo  ALL TESTS PASSED
) else (
    echo  SOME TESTS FAILED -- see output above
)
echo ============================================================
exit /b %FAILED%
