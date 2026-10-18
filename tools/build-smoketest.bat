@echo off
REM  EnableDelayedExpansion: the toolchain block tests a variable it just set.
setlocal EnableDelayedExpansion

REM ---------------------------------------------------------------------------
REM  Builds and runs the Vulkan layer smoke test.
REM  Proves the registry + manifest + export chain works, without the game.
REM ---------------------------------------------------------------------------

REM  Same toolchain discovery as build.bat, so this works on any machine.
set TOOLCHAIN=
if defined WOLFMOUNT_LLVM set TOOLCHAIN=%WOLFMOUNT_LLVM%
if not defined TOOLCHAIN (
    for %%C in (clang.exe) do if not "%%~$PATH:C"=="" set TOOLCHAIN=%%~dp$PATH:C
)
set ROOT=%~dp0..
set BUILD=%ROOT%\build

if not exist "%TOOLCHAIN%\clang.exe" (
    echo [ERROR] clang not found. Set WOLFMOUNT_LLVM to your llvm-mingw bin directory.
    exit /b 1
)

echo [1/2] compiling smoketest.exe
REM  Statically link libc++/libunwind so the exe runs without the toolchain
REM  DLLs sitting next to it. -fuse-ld=lld and the libpthread probe are the same
REM  two portability fixes build.bat carries; without them this fails under a
REM  POSIX-threaded toolchain, or anywhere the checkout path is non-ASCII.
set TFLAGS=-fuse-ld=lld -static-libstdc++ -static-libgcc
if exist "%TOOLCHAIN%\..\x86_64-w64-mingw32\lib\libpthread.a" set TFLAGS=%TFLAGS% -lpthread
"%TOOLCHAIN%\clang++.exe" -std=c++17 -O1 ^
    %TFLAGS% ^
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
