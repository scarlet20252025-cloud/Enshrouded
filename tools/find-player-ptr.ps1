param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Find where the local player's transform is read.
#
# The player position lives in the ECS world. Rather than chasing the world
# pointer, look for a *stable* global that points at it. Keen Engine games keep
# a singleton-ish "game"/"world" handle; the reliable way to find it is to look
# for code that reads player position and see what global it dereferences.
#
# Practical approach used here: find the LocalPlayer-related strings and any
# RIP-relative references near them.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

$bytes = [System.IO.File]::ReadAllText($Exe)

# Strings that likely mark player-position access.
$needles = @('localPlayerId', 'LocalPlayer', 'playerTransform', 'PlayerCharacter',
             'playerEntityId', 'localPlayer')

foreach ($n in $needles) {
    $idx = 0
    $count = 0
    while (($idx = $bytes.IndexOf("`"$n`"", $idx)) -ge 0 -and $count -lt 3) {
        Write-Host ("=== string '{0}' at char {1} ===" -f $n, $idx)
        Write-Host ("  context: {0}" -f $bytes.Substring([math]::Max(0,$idx-80), 200).Replace("`n"," "))
        $idx += $n.Length
        $count++
    }
    Write-Host ""
}
