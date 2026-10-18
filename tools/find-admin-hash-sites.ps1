param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Locate the call site that constructs `AdminDebugEnemyAction` (the command that
# carries EnemyDebugAction::SetTamed) and the site that constructs
# `AdminSpawnCommand`. Both are reachable from the game's admin-command console.
#
# The events/commands are dispatched through a hash-keyed table. In the shipped
# exe the writer is:
#     rcx = command buffer
#     edx = type hash
#     r8d = size
#     r9d = ??? (often 0 for commands, entityId for events)
#
# We already know the writer is at RVA 0x955400. Here we find the call sites
# that pass the two admin hashes, so we know where to synthesise from.
#
# Type hashes (qualifiedHash from reflection_data.json):
#   keen::ecs::AdminSpawnCommand      size 80  -> 0x06DBFCA2
#   keen::ecs::AdminDebugEnemyAction  size 56  -> 0x14CC3955
$targets = @(
    @{ Name = 'AdminSpawnCommand';        Hash = 0x06DBFCA2; Size = 80 },
    @{ Name = 'AdminDebugEnemyAction';    Hash = 0x14CC3955; Size = 56 }
)

$bytes = [System.IO.File]::ReadAllBytes($Exe)
$peOff  = [BitConverter]::ToInt32($bytes, 0x3C)
$opt    = $peOff + 24
$numSec = [BitConverter]::ToUInt16($bytes, $peOff + 6)
$sizeOpt= [BitConverter]::ToUInt16($bytes, $peOff + 20)
$secTab = $opt + $sizeOpt

$secs = @()
for ($i = 0; $i -lt $numSec; $i++) {
    $o = $secTab + $i * 40
    $secs += [pscustomobject]@{
        Name = [Text.Encoding]::ASCII.GetString($bytes, $o, 8).TrimEnd([char]0)
        VA   = [BitConverter]::ToUInt32($bytes, $o + 12)
        RawSize = [BitConverter]::ToUInt32($bytes, $o + 16)
        Raw  = [BitConverter]::ToUInt32($bytes, $o + 20)
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

foreach ($t in $targets) {
    $v = [uint32]$t.Hash
    $pat = [BitConverter]::GetBytes($v)
    Write-Host ("=== {0}  hash 0x{1:X8}  size {2} ===" -f $t.Name, $v, $t.Size)

    $found = 0
    for ($i = 0; $i -le $bytes.Length - 4; $i++) {
        if ($bytes[$i]   -ne $pat[0]) { continue }
        if ($bytes[$i+1] -ne $pat[1]) { continue }
        if ($bytes[$i+2] -ne $pat[2]) { continue }
        if ($bytes[$i+3] -ne $pat[3]) { continue }

        $rva = RawToRva $i
        $sec = ($secs | Where-Object { $_.RawSize -gt 0 -and $i -ge $_.Raw -and $i -lt ($_.Raw + $_.RawSize) }).Name
        Write-Host ("    file=0x{0:X}  rva=0x{1:X}  [{2}]" -f $i, $rva, $sec)
        $found++
    }
    Write-Host ("  -> {0} hit(s)" -f $found)
    Write-Host ""
}
