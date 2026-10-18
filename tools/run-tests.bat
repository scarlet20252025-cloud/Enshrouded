@echo off
REM  EnableDelayedExpansion: the toolchain block tests a variable it just set
REM  inside the same parenthesised block.
setlocal EnableDelayedExpansion

REM ---------------------------------------------------------------------------
REM  Run every WolfMount test and print a single summary line.
REM  Safe to run repeatedly; nothing here touches the game.
REM ---------------------------------------------------------------------------

set ROOT=%~dp0..
set BUILD=%ROOT%\build

REM  Same toolchain discovery as build.bat, so the tests run against the same
REM  clang the DLL was built with.
set TOOLCHAIN=
if defined WOLFMOUNT_LLVM set TOOLCHAIN=%WOLFMOUNT_LLVM%
if not defined TOOLCHAIN (
    for %%C in (clang.exe) do if not "%%~$PATH:C"=="" set TOOLCHAIN=%%~dp$PATH:C
)

if not exist "%TOOLCHAIN%\clang++.exe" (
    echo [ERROR] clang not found. Set WOLFMOUNT_LLVM to your llvm-mingw bin directory.
    exit /b 1
)

echo ============================================================
echo  WolfMount test suite

REM  Shared compile+link flags. -fuse-ld=lld matters for the same reason it
REM  does in build.bat: GNU ld cannot write an output path containing non-ASCII
REM  characters. TFLAGS also carries -lpthread when the toolchain is
REM  POSIX-threaded (WinLibs); llvm-mingw is win32-threaded and has no such
REM  archive, so linking it there would fail.
set TFLAGS=-fuse-ld=lld -static-libstdc++ -static-libgcc
if exist "%TOOLCHAIN%\..\x86_64-w64-mingw32\lib\libpthread.a" set TFLAGS=%TFLAGS% -lpthread
echo ============================================================
echo.

set FAILED=0

echo --- [1/10] ECS probe self test -----------------------------------------
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
    "%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 %TFLAGS% ^
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

echo --- [2/10] taming rules ------------------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 %TFLAGS% ^
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

echo --- [3/10] combat follow plan -----------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 %TFLAGS% ^
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

echo --- [4/10] mount state machine ----------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 %TFLAGS% ^
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

echo --- [5/10] detour engine ----------------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 %TFLAGS% ^
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

echo --- [6/10] console command honesty ------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 %TFLAGS% ^
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

echo --- [7/10] entity backend --------------------------------------------
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 %TFLAGS% ^
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

echo --- [8/10] layer build -------------------------------------------------
call "%ROOT%\build.bat" > "%BUILD%\build.out" 2>&1
if errorlevel 1 (
    echo     FAIL
    type "%BUILD%\build.out"
    set FAILED=1
) else (
    echo     PASS -- wolfmount_layer.dll built
)
echo.

echo --- [9/10] vulkan loader sees the layer -------------------------------
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
echo --- [10/10] source hygiene -------------------------------------------
REM  Angle brackets are redirection operators to cmd.exe, so <cstdint> in an
REM  echo line must be escaped. Writing the literal characters reads as a
REM  redirect into a file named cstdint, and cmd aborts the whole script.
python "%ROOT%\tools\check_includes.py" > "%BUILD%\includes.out" 2>&1
findstr /C:"RESULT: PASS" "%BUILD%\includes.out" > nul
if errorlevel 1 (
    echo     FAIL -- a file uses fixed-width ints without ^<cstdint^>
    type "%BUILD%\includes.out"
    set FAILED=1
) else (
    echo     PASS -- every uintN_t user includes ^<cstdint^>
)
python "%ROOT%\tools\check_dup_includes.py" > "%BUILD%\dupinc.out" 2>&1
findstr /C:"RESULT: PASS" "%BUILD%\dupinc.out" > nul
if errorlevel 1 (
    echo     FAIL -- duplicate ^<cstdint^> includes
    type "%BUILD%\dupinc.out"
    set FAILED=1
)
echo.

if "%FAILED%"=="0" (
    echo  ALL TESTS PASSED
) else (
    echo  SOME TESTS FAILED -- see output above
)
echo ============================================================
exit /b %FAILED%
