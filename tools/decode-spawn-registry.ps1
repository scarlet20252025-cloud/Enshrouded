param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Decode the admin-command registry entry for AdminSpawnCommand.
#
# The qualifiedHash 0x06DBFCA2 sits at file offset 0x1749C10 in .rdata. The
# bytes that follow are NOT a string pointer: 0x17499D0 holds another pointer
# plus a small count, so this is a two-level dispatch table:
#
#   0x1749C10:  hash(4)  hash2(4)  -> 0x17499D0: {ptr, count=11, ...}
#
# This script decodes both levels and prints the table entries so the layout
# can be confirmed before anything is called at runtime.
$ErrorActionPreference = 'Stop'
$b = [IO.File]::ReadAllBytes($Exe)

$RDATA_VA   = 0x13B0000
$RDATA_RAW  = 0x13AEA00
$IMAGE_BASE = 0x140000000

function RvaToFile([uint64]$rva) { return [uint64]$RDATA_RAW + ($rva - [uint64]$RDATA_VA) }
function PtrToRva([uint64]$p)   { return $p - [uint64]$IMAGE_BASE }

function HexRow([uint64]$off, [int]$len) {
    $o = [long]$off
    $bytes = $b[$o..($o + $len - 1)]
    $hex = ($bytes | ForEach-Object { $_.ToString('x2') }) -join ' '
    $asc = ($bytes | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } }) -join ''
    "{0:X8}  {1}  {2}" -f $off, $hex, $asc
}

$entryFo = 0x1749C10
$hash    = [BitConverter]::ToUInt32($b, $entryFo)
$hash2   = [BitConverter]::ToUInt32($b, $entryFo + 4)
$lvl1Ptr = [BitConverter]::ToUInt64($b, $entryFo + 8)

Write-Host ("AdminSpawnCommand registry entry at file 0x{0:X}" -f $entryFo)
Write-Host ("  hash      = 0x{0:X8}" -f $hash)
Write-Host ("  hash2     = 0x{0:X8}" -f $hash2)
Write-Host ("  level1 ptr= 0x{0:X}  (rva 0x{1:X})" -f $lvl1Ptr, (PtrToRva $lvl1Ptr))

$l1Rva = PtrToRva $lvl1Ptr
$l1Fo  = RvaToFile $l1Rva
Write-Host ""
Write-Host ("level1 record at rva 0x{0:X} (file 0x{1:X}):" -f $l1Rva, $l1Fo)
for ($o = $l1Fo; $o -lt ($l1Fo + 0x30); $o += 16) { HexRow ([uint64]$o) 16 }

$l2Ptr = [BitConverter]::ToUInt64($b, [long]$l1Fo)
$count = [BitConverter]::ToUInt32($b, [long]($l1Fo + 8))
Write-Host ""
Write-Host ("  level2 ptr = 0x{0:X} (rva 0x{1:X})" -f $l2Ptr, (PtrToRva $l2Ptr))
Write-Host ("  count      = {0}" -f $count)

$l2Rva = PtrToRva $l2Ptr
$l2Fo  = RvaToFile $l2Rva
Write-Host ("level2 table at rva 0x{0:X} (file 0x{1:X}):" -f $l2Rva, $l2Fo)
for ($o = $l2Fo; $o -lt ($l2Fo + 0x90); $o += 16) { HexRow ([uint64]$o) 16 }
