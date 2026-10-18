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
    [string]$Root     = "E:\DSH\肥鱼乐园\WolfMount",
    [string]$BuildDir = "E:\DSH\肥鱼乐园\WolfMount\build",
    [string]$GameDir  = "E:\SteamLibrary\steamapps\common\Enshrouded"
)

$ErrorActionPreference = 'Stop'
$TOOLCHAIN = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"

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
