@echo off
setlocal

REM ---------------------------------------------------------------------------
REM  Builds and runs the Vulkan layer smoke test.
REM  Proves the registry + manifest + export chain works, without the game.
REM ---------------------------------------------------------------------------

set TOOLCHAIN=C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin
set ROOT=%~dp0..
set BUILD=%ROOT%\build

if not exist "%TOOLCHAIN%\clang.exe" (
    echo [ERROR] clang not found
    exit /b 1
)

echo [1/2] compiling smoketest.exe
REM  Statically link libc++/libunwind so the exe runs without the toolchain
REM  DLLs sitting next to it.
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 ^
    -static-libstdc++ -static-libgcc ^
    -I"%ROOT%\third_party\Vulkan-Headers\include" ^
    "%ROOT%\tools\smoketest.cpp" ^
    -o "%BUILD%\smoketest.exe" ^
    -L"%BUILD%" -l:vulkan-1.a -luser32

if errorlevel 1 (
    echo [ERROR] smoketest build failed
    exit /b 1
)

echo [2/2] running smoke test
"%BUILD%\smoketest.exe"
exit /b %errorlevel%
