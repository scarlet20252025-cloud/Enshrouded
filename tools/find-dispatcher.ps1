param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe",
    [string]$Needle = "adminSpawnCommand"
)
# Locate the admin-command DISPATCHER by cross-referencing the command name.
#
# Strategy
# --------
# The engine keeps a table of admin command names in .rdata. Somewhere there is
# also a table of {name, handler} pairs. Finding a pointer TO the name string
# tells us where that table lives; the neighbouring qword is then a strong
# candidate for the handler function.
#
# This is the static half of what an interactive debugger would do, and it can
# be done entirely offline.

$bytes = [System.IO.File]::ReadAllBytes($Exe)
Write-Host ("file {0:N0} bytes" -f $bytes.Length)

# ---- PE headers ------------------------------------------------------------
$peOff = [BitConverter]::ToInt32($bytes, 0x3C)
$optStart = $peOff + 24
$magic = [BitConverter]::ToUInt16($bytes, $optStart)
$is64 = ($magic -eq 0x20B)
Write-Host ("PE32+ = {0}" -f $is64)

# ImageBase lives at optional-header offset 24 for PE32+ (8 bytes).
$imageBase = [BitConverter]::ToUInt64($bytes, $optStart + 24)
Write-Host ("ImageBase = 0x{0:X}" -f $imageBase)

$numSections = [BitConverter]::ToUInt16($bytes, $peOff + 6)
$sizeOpt = [BitConverter]::ToUInt16($bytes, $peOff + 20)
$secTable = $optStart + $sizeOpt

$sections = @()
for ($i = 0; $i -lt $numSections; $i++) {
    $o = $secTable + $i * 40
    $name = [System.Text.Encoding]::ASCII.GetString($bytes, $o, 8).TrimEnd([char]0)
    $vsize = [BitConverter]::ToUInt32($bytes, $o + 8)
    $va    = [BitConverter]::ToUInt32($bytes, $o + 12)
    $rsize = [BitConverter]::ToUInt32($bytes, $o + 16)
    $raw   = [BitConverter]::ToUInt32($bytes, $o + 20)
    $sections += [pscustomobject]@{ Name=$name; VA=$va; VSize=$vsize; Raw=$raw; RawSize=$rsize }
}
Write-Host "sections:"
foreach ($s in $sections) {
    Write-Host ("  {0,-9} VA=0x{1:X8} VSize=0x{2:X8} Raw=0x{3:X8} RawSize=0x{4:X8}" -f `
        $s.Name, $s.VA, $s.VSize, $s.Raw, $s.RawSize)
}

function RawToRva([int]$off) {
    foreach ($s in $sections) {
        if ($s.RawSize -gt 0 -and $off -ge $s.Raw -and $off -lt ($s.Raw + $s.RawSize)) {
            return $s.VA + ($off - $s.Raw)
        }
    }
    return -1
}
function RvaToRaw([int]$rva) {
    foreach ($s in $sections) {
        $span = [math]::Max($s.VSize, $s.RawSize)
        if ($rva -ge $s.VA -and $rva -lt ($s.VA + $span)) {
            $d = $rva - $s.VA
            if ($s.RawSize -gt 0 -and $d -lt $s.RawSize) { return $s.Raw + $d }
            return -1
        }
    }
    return -1
}

# ---- find the string -------------------------------------------------------
$needleBytes = [System.Text.Encoding]::ASCII.GetBytes($Needle)
$strOff = -1
for ($i = 0; $i -le $bytes.Length - $needleBytes.Length; $i++) {
    if ($bytes[$i] -ne $needleBytes[0]) { continue }
    $ok = $true
    for ($j = 1; $j -lt $needleBytes.Length; $j++) {
        if ($bytes[$i+$j] -ne $needleBytes[$j]) { $ok = $false; break }
    }
    if ($ok) { $strOff = $i; break }
}

if ($strOff -lt 0) { Write-Host "string not found"; exit 1 }
$strRva = RawToRva $strOff
$strVa  = $imageBase + $strRva
Write-Host ""
Write-Host ("string '{0}'" -f $Needle)
Write-Host ("  file offset = 0x{0:X}" -f $strOff)
Write-Host ("  rva         = 0x{0:X}" -f $strRva)
Write-Host ("  va          = 0x{0:X}" -f $strVa)

# ---- look for pointers to the string --------------------------------------
$target = [BitConverter]::GetBytes([uint64]$strVa)
Write-Host ""
Write-Host ("=== qword references to the string VA (0x{0:X}) ===" -f $strVa)

$hits = New-Object System.Collections.Generic.List[object]
foreach ($s in $sections) {
    if ($s.Name -notin @('.rdata', '.data')) { continue }
    $limit = $s.Raw + $s.RawSize - 8
    if ($limit -gt $bytes.Length - 8) { $limit = $bytes.Length - 8 }
    for ($i = $s.Raw; $i -le $limit; $i += 8) {
        if ($bytes[$i]   -ne $target[0]) { continue }
        if ($bytes[$i+1] -ne $target[1]) { continue }
        if ($bytes[$i+2] -ne $target[2]) { continue }
        if ($bytes[$i+3] -ne $target[3]) { continue }
        if ($bytes[$i+4] -ne $target[4]) { continue }
        if ($bytes[$i+5] -ne $target[5]) { continue }
        if ($bytes[$i+6] -ne $target[6]) { continue }
        if ($bytes[$i+7] -ne $target[7]) { continue }

        $hits.Add([pscustomobject]@{
            FileOff = $i
            Rva     = (RawToRva $i)
            Section = $s.Name
        })
    }
}

Write-Host ("  {0} reference(s)" -f $hits.Count)
foreach ($h in $hits) {
    Write-Host ("  file=0x{0:X}  rva=0x{1:X}  [{2}]" -f $h.FileOff, $h.Rva, $h.Section)

    # Dump the surrounding table entries: a {name, handler} pair is 16 bytes.
    Write-Host "    surrounding qwords:"
    for ($k = -3; $k -le 3; $k++) {
        $o = $h.FileOff + ($k * 8)
        if ($o -lt 0 -or $o -gt $bytes.Length - 8) { continue }
        $q = [BitConverter]::ToUInt64($bytes, $o)
        $mark = if ($k -eq 0) { ' <== this string' } else { '' }
        Write-Host ("      [{0,3}] 0x{1:X16}{2}" -f $k, $q, $mark)
    }
}
