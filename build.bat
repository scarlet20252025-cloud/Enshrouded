@echo off
setlocal

REM ---------------------------------------------------------------------------
REM  WolfMount build script
REM  Produces build\wolfmount_layer.dll from src\*.cpp + ImGui + Vulkan headers
REM ---------------------------------------------------------------------------

set TOOLCHAIN=C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin
set ROOT=%~dp0
set BUILD=%ROOT%build
set TP=%ROOT%third_party

if not exist "%TOOLCHAIN%\clang.exe" (
    echo [ERROR] clang not found at %TOOLCHAIN%
    exit /b 1
)

if not exist "%BUILD%" mkdir "%BUILD%"

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

REM --- link -----------------------------------------------------------------
REM  lld's -l<name> expands to lib<name>.a or <name>.lib, but our generated
REM  import archive is named vulkan-1.a, so reference it explicitly with -l:.
set LIBS=-l:vulkan-1.a -luser32 -lgdi32 -lshell32 -lole32 -ldwmapi -limm32 -ldxgi
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

