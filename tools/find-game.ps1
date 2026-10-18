# Locate the Enshrouded install directory through the Steam library config.
#
# Prints the directory on stdout and exits 0 on success; prints nothing and
# exits 1 when the game cannot be found. Kept as a separate file because doing
# this inline in a .bat requires nested quotes that cmd.exe's parser cannot
# survive (see MODLOG.md).
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File find-game.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File find-game.ps1 -SteamRoot "C:\Program Files (x86)\Steam"

param(
    [string]$SteamRoot
)

$ErrorActionPreference = 'SilentlyContinue'

function Get-SteamRoot {
    if ($SteamRoot) { return $SteamRoot }
    $k = Get-ItemProperty -Path 'HKCU:\Software\Valve\Steam' -Name SteamPath
    if (-not $k.SteamPath) { return $null }
    return ($k.SteamPath -replace '/', '\')
}

$root = Get-SteamRoot
if (-not $root) { exit 1 }

# Every library root: the Steam install itself plus each "path" in
# libraryfolders.vdf. The game may live in any of them.
$libraries = New-Object System.Collections.Generic.List[string]
$libraries.Add($root)

$vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
if (Test-Path $vdf) {
    foreach ($line in Get-Content $vdf) {
        # "path"		"D:\\SteamLibrary"
        $m = [regex]::Match($line, '"path"\s+"([^"]+)"')
        if ($m.Success) {
            $p = $m.Groups[1].Value -replace '\\\\', '\'
            if (-not $libraries.Contains($p)) { $libraries.Add($p) }
        }
    }
}

foreach ($lib in $libraries) {
    $candidate = Join-Path $lib 'steamapps\common\Enshrouded'
    if (Test-Path (Join-Path $candidate 'enshrouded.exe')) {
        Write-Output $candidate
        exit 0
    }
}

exit 1
