param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Find the AdminSpawnCommand handler by searching for the admin command name
# table reference in .text.
#
# Earlier we found the admin command NAMES ("adminSpawnCommand" etc.) live in a
# table at ~0x179E0F0 / 0x18D3410 with {ptr, len, payload, size} records.
# The dispatcher iterates that table. Find code that references those table
# entries: a `lea reg, [rip+X]` pointing into the table region.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

$bytes = [System.IO.File]::ReadAllBytes($Exe)
$peOff = [BitConverter]::ToInt32($bytes, 0x3C)
$optStart = $peOff + 24
$imageBase = [BitConverter]::ToUInt64($bytes, $optStart + 24)
$numSec = [BitConverter]::ToUInt16($bytes, $peOff + 6)
$sizeOpt = [BitConverter]::ToUInt16($bytes, $peOff + 20)
$secTab = $optStart + $sizeOpt

$secs = @()
for ($i = 0; $i -lt $numSec; $i++) {
    $o = $secTab + $i * 40
    $secs += [pscustomobject]@{
        Name = [System.Text.Encoding]::ASCII.GetString($bytes, $o, 8).TrimEnd([char]0)
        VA = [BitConverter]::ToUInt32($bytes, $o + 12)
        RawSize = [BitConverter]::ToUInt32($bytes, $o + 16)
        Raw = [BitConverter]::ToUInt32($bytes, $o + 20)
    }
}
function RawToRva([long]$off) {
    foreach ($s in $secs) {
        if ($s.RawSize -gt 0 -and $off -ge $s.Raw -and $off -lt ($s.Raw + $s.RawSize)) {
            return [int]($s.VA + ($off - $s.Raw))
        }
    }
    return -1
}

# The admin command-name table sits around rva 0x179E0C0 .. 0x18D3430.
# Any RIP-relative LEA/MOV in .text that targets that window is part of the
# dispatcher.
$tableLo = 0x179E000
$tableHi = 0x18D4000

$text = $secs | Where-Object Name -eq '.text' | Select-Object -First 1
Write-Host "scanning .text for RIP-relative refs into the admin command table"
Write-Host ("  .text raw 0x{0:X} .. 0x{1:X}" -f $text.Raw, ($text.Raw + $text.RawSize))

$hits = @()
$start = $text.Raw
$limit = $text.Raw + $text.RawSize - 8

for ($i = $start; $i -lt $limit; $i++) {
    # LEA reg, [rip+disp32] : 48 8D /r  (mod=00, rm=101)
    if ($bytes[$i] -ne 0x48 -or $bytes[$i+1] -ne 0x8D) { continue }
    $modrm = $bytes[$i+2]
    if (($modrm -band 0xC7) -ne 0x05) { continue }

    $disp = [BitConverter]::ToInt32($bytes, $i + 3)
    $siteRva = RawToRva $i
    if ($siteRva -lt 0) { continue }
    $targetRva = $siteRva + 7 + $disp

    if ($targetRva -ge $tableLo -and $targetRva -le $tableHi) {
        $hits += [pscustomobject]@{ SiteRva = $siteRva; TargetRva = $targetRva }
    }
}

Write-Host ("  -> {0} reference(s)" -f $hits.Count)
foreach ($h in ($hits | Select-Object -First 20)) {
    Write-Host ("  lea at rva 0x{0:X}  -> table+0x{1:X}" -f $h.SiteRva, ($h.TargetRva - $tableLo))
}

if ($hits.Count -gt 0) {
    $first = $hits[0].SiteRva
    $va = 0x140000000 + $first
    Write-Host ""
    Write-Host "=== disassembly of the first dispatcher reference ==="
    & $objdump -d --start-address=($va - 0x80) --stop-address=($va + 0x120) $Exe 2>&1 |
        ForEach-Object { Write-Host ("  " + $_) }
}
