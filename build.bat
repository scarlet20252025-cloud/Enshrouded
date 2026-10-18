@echo off
REM  EnableDelayedExpansion is required: the toolchain block below tests a
REM  variable it just assigned inside the same parenthesised block, and plain
REM  %VAR% is expanded before the block runs.
setlocal EnableDelayedExpansion

REM ---------------------------------------------------------------------------
REM  WolfMount build script
REM  Produces build\wolfmount_layer.dll from src\*.cpp + ImGui + Vulkan headers
REM ---------------------------------------------------------------------------

REM --- locate the toolchain -----------------------------------------------------
REM  Order of preference:
REM    1. WOLFMOUNT_LLVM env var, so CI or a contributor can pin one.
REM    2. clang already on PATH (the common case: llvm-mingw, or a full LLVM).
REM    3. The development machine's llvm-mingw, for whoever wrote this.
REM
REM  Hardcoding only (3) is what made this repo un-buildable for anyone else, so
REM  it is last and it is overridable.
set TOOLCHAIN=
if defined WOLFMOUNT_LLVM set TOOLCHAIN=%WOLFMOUNT_LLVM%

if not defined TOOLCHAIN (
    for %%C in (clang.exe) do if not "%%~$PATH:C"=="" set TOOLCHAIN=%%~dp$PATH:C
)

if not defined TOOLCHAIN (
    set CANDIDATE=C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin
    if exist "!CANDIDATE!\clang.exe" set TOOLCHAIN=!CANDIDATE!
)

if not defined TOOLCHAIN (
    echo [ERROR] clang not found.
    echo         Install llvm-mingw, or set WOLFMOUNT_LLVM to its bin directory, e.g.
    echo           set WOLFMOUNT_LLVM=C:\llvm-mingw\bin
    exit /b 1
)

if not exist "%TOOLCHAIN%\clang.exe" (
    echo [ERROR] clang not found at %TOOLCHAIN%
    exit /b 1
)
echo [0/2] toolchain: %TOOLCHAIN%
set ROOT=%~dp0
set BUILD=%ROOT%build
set TP=%ROOT%third_party

if not exist "%TOOLCHAIN%\clang.exe" (
    echo [ERROR] clang not found at %TOOLCHAIN%
    exit /b 1
)

if not exist "%BUILD%" mkdir "%BUILD%"

REM --- generate the Vulkan import library --------------------------------------
REM  The layer links against vulkan-1.a, which is NOT in the repository and is
REM  not shipped with the toolchain. It is an import library for the system
REM  vulkan-1.dll, and we build it here from that DLL's own export table.
REM
REM  Why generate instead of committing it: the import library has to match the
REM  loader the game actually loads, and committing a binary that nobody can
REM  regenerate is exactly the kind of opaque dependency that makes a mod hard to
REM  trust. This takes under a second and needs nothing but the toolchain.
REM
REM  A fresh clone used to fail here with
REM      lld: error: unable to find library -l:vulkan-1.a
REM  because the only copy lived in build\, which is gitignored.
if not exist "%BUILD%\vulkan-1.a" (
    echo [1/2] generating vulkan-1.a from the system loader
    "%TOOLCHAIN%\llvm-readobj.exe" --coff-exports "%SystemRoot%\System32\vulkan-1.dll" > "%BUILD%\vk-exports.txt" 2>nul
    if errorlevel 1 (
        echo [ERROR] could not read exports from %SystemRoot%\System32\vulkan-1.dll
        exit /b 1
    )
    REM  Keep the Vulkan entry points (there are ~265) and write a .def file.
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$n = Get-Content '%BUILD%\vk-exports.txt' | ForEach-Object { if ($_ -match '^\s+Name:\s+(\S+)') { $Matches[1] } } | Where-Object { $_ -match '^(vk|VK)' } | Sort-Object -Unique; @('LIBRARY vulkan-1.dll','EXPORTS') + $n | Set-Content -Path '%BUILD%\vulkan-1.def' -Encoding ASCII"
    if errorlevel 1 (
        echo [ERROR] could not build vulkan-1.def
        exit /b 1
    )
    "%TOOLCHAIN%\llvm-dlltool.exe" -d "%BUILD%\vulkan-1.def" -l "%BUILD%\vulkan-1.a" -m i386:x86-64
    if errorlevel 1 (
        echo [ERROR] llvm-dlltool could not create vulkan-1.a
        exit /b 1
    )
    del /Q "%BUILD%\vk-exports.txt" "%BUILD%\vulkan-1.def" 2>nul
)

REM --- include paths --------------------------------------------------------
set INC=-I"%ROOT%src" -I"%TP%\imgui" -I"%TP%\imgui\backends" -I"%TP%\Vulkan-Headers\include"

REM --- sources --------------------------------------------------------------
set SRC=%ROOT%src\entry.cpp %ROOT%src\layer.cpp %ROOT%src\mod.cpp %ROOT%src\ecs.cpp %ROOT%src\tame.cpp %ROOT%src\follow.cpp %ROOT%src\mount.cpp %ROOT%src\detour.cpp %ROOT%src\gamehooks.cpp %ROOT%src\reflect.cpp %ROOT%src\console.cpp %ROOT%src\console_ui.cpp %ROOT%src\entityops.cpp
set IMGUI=%TP%\imgui\imgui.cpp %TP%\imgui\imgui_draw.cpp %TP%\imgui\imgui_tables.cpp %TP%\imgui\imgui_widgets.cpp %TP%\imgui\backends\imgui_impl_vulkan.cpp %TP%\imgui\backends\imgui_impl_win32.cpp

if not exist "%TP%\imgui\backends\imgui_impl_vulkan.cpp" (
    echo [ERROR] ImGui backends missing. Did you clone the full imgui repo?
    exit /b 1
)

REM --- flags ----------------------------------------------------------------
REM  -shared              : build a DLL
REM  -DWOLFMOUNT_EXPORTS  : export the layer entry points
REM  -std=c++20           : ImGui 1.92 needs this
REM  -O2                  : release optimisation
REM  -static-libstdc++ -static-libgcc : bundle the C++ runtime so the DLL
REM    runs from any directory without toolchain DLLs next to it.
REM
REM  -DVK_NO_PROTOTYPES : CRITICAL for a layer.
REM    Without it, ImGui's Vulkan backend links directly against the exported
REM    vk* symbols from vulkan-1.dll ??i.e. it calls the LOADER from inside the
REM    layer. The loader's own state is mid-flight at that point, and the
REM    re-entry corrupts it: Windows reports
REM        Faulting module: vulkan-1.dll
REM        Exception code : 0xC0000409  (STATUS_STACK_BUFFER_OVERRUN)
REM    which is a __fastfail, so no crash dump is written and no exception
REM    handler sees it. The game dies silently.
REM    With VK_NO_PROTOTYPES the backend takes every entry point from
REM    ImGui_ImplVulkan_LoadFunctions, which we point at our chain-down table.
REM
REM  -include wm_imgui_assert.h : force our IM_ASSERT into EVERY translation
REM    unit, including imgui_impl_vulkan.cpp. Without this the backend's own
REM    asserts call abort(), which also terminates the game silently.
set FLAGS=-shared -DWOLFMOUNT_EXPORTS -std=c++20 -O2 -DWIN32 -D_WIN32 -D_WINDOWS
set FLAGS=%FLAGS% -DVK_NO_PROTOTYPES
set FLAGS=%FLAGS% -static-libstdc++ -static-libgcc
set FLAGS=%FLAGS% -include "%ROOT%src\wm_imgui_assert.h"
set FLAGS=%FLAGS% -Wno-unused-parameter -Wno-missing-field-initializers

REM  Force lld rather than whatever linker the toolchain defaults to.
REM  GNU ld (the default in some mingw builds) cannot write an output path that
REM  contains non-ASCII characters, which turns a working toolchain into
REM      ld: cannot open output file ...: No such file or directory
REM  for anyone whose checkout lives under a non-English directory name.
set FLAGS=%FLAGS% -fuse-ld=lld

REM --- link -----------------------------------------------------------------
REM  lld's -l<name> expands to lib<name>.a or <name>.lib, but our generated
REM  import archive is named vulkan-1.a, so reference it explicitly with -l:.
set LIBS=-l:vulkan-1.a -luser32 -lgdi32 -lshell32 -lole32 -ldwmapi -limm32 -ldxgi

REM  A POSIX-threaded toolchain (e.g. WinLibs POSIX/UCRT) routes std::mutex and
REM  libstdc++'s guard variables through pthreads, so it needs libpthread at
REM  link time. A win32-threaded toolchain (llvm-mingw) has no such library and
REM  does not need it. Probe for the archive rather than decide by toolchain name.
if exist "%TOOLCHAIN%\..\x86_64-w64-mingw32\lib\libpthread.a" set LIBS=%LIBS% -lpthread
set LIBDIR=-L"%BUILD%"

echo [1/1] compiling wolfmount_layer.dll
"%TOOLCHAIN%\clang++.exe" %FLAGS% %INC% %SRC% %IMGUI% "%ROOT%wolfmount.def" -o "%BUILD%\wolfmount_layer.dll" %LIBDIR% %LIBS%

if errorlevel 1 (
    echo [ERROR] build failed
    exit /b 1
)

copy /Y "%ROOT%VK_LAYER_WOLFMOUNT_wolfmount.json" "%BUILD%\" >nul

echo [OK] build\wolfmount_layer.dll
exit /b 0

