param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Search the executable for the ECS type qualified hashes as immediates.
#
# A dispatcher that routes events by type will compare an incoming hash against
# a constant, typically:
#   cmp r32, imm32      (81 F8 imm32 / 3D imm32 / 81 FE imm32)
#   mov r32, imm32      (B8+B9 imm32 / C7 ...)
# or the hash is stored in a table of {hash, handler}.
#
# We search for the raw little-endian 32-bit hash bytes. Every hit is a
# candidate dispatch site to confirm under a debugger.

$bytes = [System.IO.File]::ReadAllBytes($Exe)
$peOff = [BitConverter]::ToInt32($bytes, 0x3C)
$optStart = $peOff + 24
$imageBase = [BitConverter]::ToUInt64($bytes, $optStart + 24)
$numSections = [BitConverter]::ToUInt16($bytes, $peOff + 6)
$sizeOpt = [BitConverter]::ToUInt16($bytes, $peOff + 20)
$secTable = $optStart + $sizeOpt

$sections = @()
for ($i = 0; $i -lt $numSections; $i++) {
    $o = $secTable + $i * 40
    $sections += [pscustomobject]@{
        Name = [System.Text.Encoding]::ASCII.GetString($bytes, $o, 8).TrimEnd([char]0)
        VSize = [BitConverter]::ToUInt32($bytes, $o + 8)
        VA    = [BitConverter]::ToUInt32($bytes, $o + 12)
        RawSize = [BitConverter]::ToUInt32($bytes, $o + 16)
        Raw   = [BitConverter]::ToUInt32($bytes, $o + 20)
    }
}

function RawToRva([long]$off) {
    foreach ($s in $sections) {
        if ($s.RawSize -gt 0 -and $off -ge $s.Raw -and $off -lt ($s.Raw + $s.RawSize)) {
            return [int]($s.VA + ($off - $s.Raw))
        }
    }
    return -1
}

# The hashes we care about, as decimal -> 32-bit hex.
$hashes = [ordered]@{
    'EntityDiedEvent'       = 3639384106
    'TameWildlifeEvent'     = 1400596316
    'AdminSpawnCommand'     = 115080354
    'AdminKillFactionCommand' = 2425948247
    'LootInteractionEvent'  = 1930081645
    'StartFlyingEvent'      = 2883287186
    'StopFlyingEvent'       = 780259052
    'ImpactHierarchy'       = 3443083232
    'IsTame'                = 328851642
    'Faction'               = 2717060897
    'Animal'                = 2411077011
    'HookShotAnchorSubEntity' = 2553848166
}

foreach ($name in $hashes.Keys) {
    $v = [uint32]$hashes[$name]
    $pat = [BitConverter]::GetBytes($v)   # little-endian
    $hex = "{0:X8}" -f $v
    Write-Host ("=== {0}  hash=0x{1} ===" -f $name, $hex)

    $hits = New-Object System.Collections.Generic.List[object]
    $limit = $bytes.Length - 4
    for ($i = 0; $i -le $limit; $i++) {
        if ($bytes[$i] -ne $pat[0]) { continue }
        if ($bytes[$i+1] -ne $pat[1]) { continue }
        if ($bytes[$i+2] -ne $pat[2]) { continue }
        if ($bytes[$i+3] -ne $pat[3]) { continue }
        $sec = $sections | Where-Object { $s.Raw -le $i -and $i -lt ($s.Raw + $s.RawSize) } | Select-Object -First 1
        $hits.Add([pscustomobject]@{ FileOff=$i; Rva=(RawToRva $i); Section=($(if ($sec) { $sec.Name } else { '?' })) })
    }

    Write-Host ("  {0} hit(s)" -f $hits.Count)
    $shown = 0
    foreach ($h in $hits) {
        if ($shown -ge 8) { Write-Host "  ..."; break }
        Write-Host ("  file=0x{0:X}  rva=0x{1:X}  [{2}]" -f $h.FileOff, $h.Rva, $h.Section)
        $shown++
    }
    Write-Host ""
}
