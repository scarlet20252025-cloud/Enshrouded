param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Resolve the admin-command name table into (name -> id) pairs and find the
# dispatcher that consumes it.
#
# Observed layout at RVA 0x179E0F0 and 0x18D3410:
#     [0] -> char*   name
#     [1] = 0x11     length (17 = strlen("adminSpawnCommand"))
#     [2] -> ptr     payload
#     [3] = 0x18     payload size (24)
#
# So the record is 32 bytes and starts 16 bytes BEFORE the name pointer.
# Dumping a run of these records gives the neighbouring commands, and any table
# that references them is the dispatcher.

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

function RvaToRaw([long]$rva) {
    foreach ($s in $sections) {
        $span = [math]::Max($s.VSize, $s.RawSize)
        if ($rva -ge $s.VA -and $rva -lt ($s.VA + $span)) {
            $d = $rva - $s.VA
            if ($s.RawSize -gt 0 -and $d -lt $s.RawSize) { return [int]($s.Raw + $d) }
        }
    }
    return -1
}
function RawToRva([long]$off) {
    foreach ($s in $sections) {
        if ($s.RawSize -gt 0 -and $off -ge $s.Raw -and $off -lt ($s.Raw + $s.RawSize)) {
            return [int]($s.VA + ($off - $s.Raw))
        }
    }
    return -1
}
function ReadCStr([long]$rawOff) {
    if ($rawOff -lt 0 -or $rawOff -ge $bytes.Length) { return $null }
    $sb = New-Object System.Text.StringBuilder
    for ($i = $rawOff; $i -lt [math]::Min($rawOff + 128, $bytes.Length); $i++) {
        $b = $bytes[$i]
        if ($b -eq 0) { break }
        if ($b -lt 32 -or $b -ge 127) { return $null }
        [void]$sb.Append([char]$b)
    }
    return $sb.ToString()
}

# Dump the record table around each reference found earlier.
$anchors = @(0x179E0F0, 0x18D3410)

foreach ($anchorRva in $anchors) {
    Write-Host ("################ table anchored at RVA 0x{0:X}" -f $anchorRva)

    # The name pointer sits at the anchor; the record begins 16 bytes earlier.
    $recStartRva = $anchorRva - 16
    $recRaw = RvaToRaw $recStartRva
    if ($recRaw -lt 0) { Write-Host "  (unmapped)"; continue }

    # Walk backwards to find the start of the table, then forward through it.
    # Each record: qword ptr, qword len, qword ptr, qword size = 32 bytes.
    $startRaw = $recRaw
    for ($i = 0; $i -lt 40; $i++) {
        $probe = $startRaw - 32
        if ($probe -lt 0) { break }
        $p = [BitConverter]::ToUInt64($bytes, $probe)
        $l = [BitConverter]::ToUInt64($bytes, $probe + 8)
        if ($p -lt $imageBase -or $p -gt ($imageBase + 0x3000000)) { break }
        if ($l -eq 0 -or $l -gt 64) { break }
        $s = ReadCStr (RvaToRaw ([long]($p - $imageBase)))
        if (-not $s) { break }
        $startRaw = $probe
    }

    Write-Host ("  table begins near file offset 0x{0:X} (rva 0x{1:X})" -f $startRaw, (RawToRva $startRaw))
    Write-Host ""
    Write-Host ("  {0,-34} {1,5}  {2}" -f 'command', 'len', 'payload ptr')
    Write-Host "  ----------------------------------------------------------------"

    $off = $startRaw
    $count = 0
    while ($count -lt 80 -and ($off + 32) -le $bytes.Length) {
        $p = [BitConverter]::ToUInt64($bytes, $off)
        $l = [BitConverter]::ToUInt64($bytes, $off + 8)
        $pay = [BitConverter]::ToUInt64($bytes, $off + 16)
        $psz = [BitConverter]::ToUInt64($bytes, $off + 24)

        if ($p -lt $imageBase -or $p -gt ($imageBase + 0x3000000)) { break }
        if ($l -eq 0 -or $l -gt 64) { break }

        $name = ReadCStr (RvaToRaw ([long]($p - $imageBase)))
        if (-not $name) { break }

        $mark = if ($name -eq 'adminSpawnCommand') { '   <== TARGET' } else { '' }
        Write-Host ("  {0,-34} {1,5}  0x{2:X}{3}" -f $name, $l, $pay, $mark)

        $off += 32
        $count++
    }
    Write-Host ""
}
