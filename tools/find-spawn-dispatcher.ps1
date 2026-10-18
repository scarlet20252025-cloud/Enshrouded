param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Find the AdminSpawnCommand dispatcher and trace where the ECS world pointer
# comes from.
#
# AdminSpawnCommand qualifiedHash = 0x06DBFCA2 (from reflection_data.json).
# A command dispatcher will reference that hash to route the command, and the
# handler it calls will need the ECS world.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

$bytes = [System.IO.File]::ReadAllBytes($Exe)
$peOff = [BitConverter]::ToInt32($bytes, 0x3C)
$optStart = $peOff + 24
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

# 1. locate the AdminSpawnCommand hash in the binary
$hash = [uint32]115080354      # 0x06DBFCA2
$pat = [BitConverter]::GetBytes($hash)
$sites = @()
for ($i = 0; $i -le $bytes.Length - 4; $i++) {
    if ($bytes[$i] -eq $pat[0] -and $bytes[$i+1] -eq $pat[1] -and
        $bytes[$i+2] -eq $pat[2] -and $bytes[$i+3] -eq $pat[3]) {
        $sites += $i
    }
}

Write-Host ("AdminSpawnCommand hash 0x{0:X8}: {1} site(s)" -f $hash, $sites.Count)
foreach ($s in $sites) {
    $rva = RawToRva $s
    $sec = $secs | Where-Object { $s -ge $_.Raw -and $s -lt ($_.Raw + $_.RawSize) } | Select-Object -First 1
    Write-Host ("  file=0x{0:X} rva=0x{1:X} [{2}]" -f $s, $rva, $sec.Name)
}
Write-Host ""

# 2. disassemble around each .text site
foreach ($s in $sites) {
    $rva = RawToRva $s
    $sec = $secs | Where-Object { $s -ge $_.Raw -and $s -lt ($_.Raw + $_.RawSize) } | Select-Object -First 1
    if ($sec.Name -ne '.text') { continue }

    $va = 0x140000000 + $rva
    Write-Host "################ around rva 0x{0:X} (va 0x{1:X})" -f $rva, $va
    & $objdump -d --start-address=($va - 0x60) --stop-address=($va + 0xC0) $Exe 2>&1 |
        ForEach-Object { Write-Host ("  " + $_) }
    Write-Host ""
}
