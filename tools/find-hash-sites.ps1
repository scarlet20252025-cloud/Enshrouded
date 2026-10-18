param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe",
    [string]$OutFile = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\hit-hash-sites.csv"
)
# Locate the HitEvent / BaseHitEvent type hashes inside the executable.
#
# HitEvent carries the data we need for the "torch kill" rule:
#     rootTargetId   offset 160   (victim)
#     sourceId       offset 164   (attacker / player)
#     weaponPideId   offset 172   (the weapon -> torch itemIds)
#     healthChange   offset 188   (damage -> lethal?)
#
# So the hook target is the HitEvent send site, NOT EntityDiedEvent (which only
# carries deadEntityId and says nothing about the weapon).

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
function SecName([long]$off) {
    foreach ($s in $secs) {
        if ($s.RawSize -gt 0 -and $off -ge $s.Raw -and $off -lt ($s.Raw + $s.RawSize)) { return $s.Name }
    }
    return "?"
}

$targets = @(
    @{ Name = 'HitEvent';         Hash = 0xCC0D57E0 },
    @{ Name = 'BaseHitEvent';     Hash = 0x0D2F02B9 },
    @{ Name = 'SendBaseHitEvent'; Hash = 0x4E74667E },
    @{ Name = 'EntityDiedEvent';  Hash = 0xD8EC982A }
)

$rows = New-Object System.Collections.Generic.List[object]

foreach ($t in $targets) {
    $v = [uint32]$t.Hash
    $pat = [BitConverter]::GetBytes($v)
    Write-Host ("=== {0}  hash 0x{1:X8} ===" -f $t.Name, $v)

    $limit = $bytes.Length - 4
    $found = 0
    for ($i = 0; $i -le $limit; $i++) {
        if ($bytes[$i] -ne $pat[0]) { continue }
        if ($bytes[$i+1] -ne $pat[1]) { continue }
        if ($bytes[$i+2] -ne $pat[2]) { continue }
        if ($bytes[$i+3] -ne $pat[3]) { continue }

        $rva = RawToRva $i
        $sec = SecName $i
        Write-Host ("    file=0x{0:X}  rva=0x{1:X}  [{2}]" -f $i, $rva, $sec)
        $rows.Add([pscustomobject]@{
            Event = $t.Name; Hash = ("0x{0:X8}" -f $v)
            FileOffset = ("0x{0:X}" -f $i); Rva = ("0x{0:X}" -f $rva); Section = $sec
        })
        $found++
    }
    Write-Host ("  -> {0} hit(s)" -f $found)
    Write-Host ""
}

$rows | Export-Csv -Path $OutFile -NoTypeInformation -Encoding UTF8
Write-Host ("wrote {0} rows to {1}" -f $rows.Count, $OutFile)
