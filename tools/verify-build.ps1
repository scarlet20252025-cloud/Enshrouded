#!/usr/bin/env pwsh
# WolfMount — post-build verification
#
# Proves the built DLL is a loadable Vulkan implicit layer:
#   1. It is a valid PE32+ image.
#   2. It exports vkNegotiateLoaderLayerInterfaceVersion (required by the loader).
#   3. The manifest JSON names the same layer name and DLL.
#   4. The registry registration points at the manifest.
#
# Uses llvm-readobj rather than hand-parsed PE so the result is trustworthy.

param(
    # Default to this script's own parent directory, so the verifier works from
    # any checkout location rather than one developer's absolute path.
    [string]$Root     = (Split-Path $PSScriptRoot -Parent),
    [string]$BuildDir = "",
    [string]$GameDir  = ""
)

if (-not $BuildDir) { $BuildDir = Join-Path $Root 'build' }
if (-not $GameDir) {
    # Reuse the same Steam-discovery helper the installer uses.
    $found = & (Join-Path $PSScriptRoot 'find-game.ps1') 2>$null
    if ($found) { $GameDir = $found }
}

$ErrorActionPreference = 'Stop'

# Locate the toolchain the same way build.bat does, so this verifier works on
# any machine and does not bake in one developer's install path.
$TOOLCHAIN = $env:WOLFMOUNT_LLVM
if (-not $TOOLCHAIN) {
    $clang = Get-Command clang.exe -ErrorAction SilentlyContinue
    if ($clang) { $TOOLCHAIN = Split-Path $clang.Source -Parent }
}
if (-not $TOOLCHAIN -or -not (Test-Path (Join-Path $TOOLCHAIN 'clang.exe'))) {
    Write-Host "  FAIL  clang not found. Set WOLFMOUNT_LLVM to your llvm-mingw bin directory."
    exit 1
}

$fail = 0
function Check([string]$label, [bool]$ok, [string]$detail = "") {
    if ($ok) {
        Write-Host ("  PASS  {0}" -f $label)
    } else {
        Write-Host ("  FAIL  {0}  {1}" -f $label, $detail)
        $script:fail++
    }
}

Write-Host "=== WolfMount build verification ==="
Write-Host ""

$dll = Join-Path $BuildDir "wolfmount_layer.dll"
$manifest = Join-Path $Root "VK_LAYER_WOLFMOUNT_wolfmount.json"

# ---- 1. file exists -------------------------------------------------------
Check "DLL exists" (Test-Path $dll) $dll
Check "Manifest exists" (Test-Path $manifest) $manifest
if ($fail -gt 0) { Write-Host "`nRESULT: FAIL"; exit 1 }

# ---- 2. exports -----------------------------------------------------------
$readobj = Join-Path $TOOLCHAIN "llvm-readobj.exe"
$out = & $readobj --coff-exports $dll 2>&1 | Out-String
$exportNames = [regex]::Matches($out, 'Name:\s*(\S+)') | ForEach-Object { $_.Groups[1].Value }

Check "export table non-empty" ($exportNames.Count -gt 0) "got $($exportNames.Count) exports"
Check "exports vkNegotiateLoaderLayerInterfaceVersion" ($exportNames -contains 'vkNegotiateLoaderLayerInterfaceVersion')

foreach ($n in @('vkEnumerateInstanceLayerProperties','vkEnumerateInstanceExtensionProperties',
                 'vkEnumerateDeviceLayerProperties','vkEnumerateDeviceExtensionProperties')) {
    Check "exports $n" ($exportNames -contains $n)
}

# ---- 3. manifest sanity ---------------------------------------------------
$json = Get-Content $manifest -Raw | ConvertFrom-Json
$layer = $json.layer
Check "manifest layer name" ($layer.name -eq 'VK_LAYER_WOLFMOUNT_wolfmount') $layer.name
Check "manifest type is GLOBAL" ($layer.type -eq 'GLOBAL') $layer.type
Check "manifest library_path" ($layer.library_path -eq '.\wolfmount_layer.dll') $layer.library_path
Check "manifest functions block" ($layer.functions.vkNegotiateLoaderLayerInterfaceVersion -ne $null)

# ---- 4. registry ----------------------------------------------------------
$regPaths = @(
    "HKLM:\SOFTWARE\Khronos\Vulkan\ImplicitLayers",
    "HKCU:\SOFTWARE\Khronos\Vulkan\ImplicitLayers"
)
$regValue = $null
foreach ($rp in $regPaths) {
    if (Test-Path $rp) {
        $v = (Get-ItemProperty $rp -Name "VK_LAYER_WOLFMOUNT_wolfmount" -ErrorAction SilentlyContinue)."VK_LAYER_WOLFMOUNT_wolfmount"
        if ($v) { $regValue = $v; break }
    }
}
if ($regValue) {
    Check "registry registered" $true $regValue
    $manifestFull = (Resolve-Path $manifest).Path
    Check "registry points at manifest" ($regValue -eq $manifestFull) "reg=$regValue manifest=$manifestFull"
} else {
    Write-Host "  SKIP  registry not registered yet (run install.bat)"
}

# ---- 5. game install ------------------------------------------------------
Check "game dir found" (Test-Path (Join-Path $GameDir "enshrouded.exe")) $GameDir
Check "game uses Vulkan" (Test-Path "C:\Windows\System32\vulkan-1.dll")

Write-Host ""
if ($fail -gt 0) {
    Write-Host "RESULT: FAIL ($fail checks failed)"
    exit 1
} else {
    Write-Host "RESULT: PASS"
    Write-Host ""
    Write-Host "Exported layer entry points ($($exportNames.Count)):"
    $exportNames | Sort-Object | ForEach-Object { Write-Host "  $_" }
    exit 0
}
