param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Dump the admin-command registry table around the AdminSpawnCommand entry.
#
# The hash 0x06DBFCA2 (AdminSpawnCommand) sits at file offset 0x1749C10 in
# .rdata. The 8 bytes that follow are a pointer to a name string, so this is a
# `{hash, size, name}` registry entry. Dumping the neighbourhood reveals the
# table layout and its neighbours, which is how we confirm the record stride.
$ErrorActionPreference = 'Stop'
$b = [IO.File]::ReadAllBytes($Exe)

function HexRow([long]$off, [int]$len) {
    $bytes = $b[$off..($off + $len - 1)]
    $hex = ($bytes | ForEach-Object { $_.ToString('x2') }) -join ' '
    $asc = ($bytes | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } }) -join ''
    "{0:X8}  {1}  {2}" -f $off, $hex, $asc
}

function U32([long]$off) { return [BitConverter]::ToUInt32($b, $off) }
function U64([long]$off) { return [BitConverter]::ToUInt64($b, $off) }

$fo = 0x1749C10
Write-Host ("AdminSpawnCommand hash at file 0x{0:X}" -f $fo)
Write-Host ("  hash        = 0x{0:X8}" -f (U32 $fo))
Write-Host ("  next u32    = 0x{0:X8}" -f (U32 ($fo + 4)))
Write-Host ("  next u64    = 0x{0:X}  (rva 0x{1:X})" -f (U64 ($fo + 8)), ((U64 ($fo + 8)) - 0x140000000))
Write-Host ""
Write-Host "--- 0x80 before .. 0x80 after ---"
$start = $fo - 0x80
for ($o = $start; $o -lt ($fo + 0x80); $o += 16) { HexRow $o 16 }
