#!/usr/bin/env pwsh
# Dump ALL PE data directories so we can see which RVA actually holds the
# export table. Useful when a linker emits a non-standard optional header.
param([Parameter(Mandatory=$true)][string]$Path)

$bytes = [System.IO.File]::ReadAllBytes($Path)
$ms = New-Object System.IO.MemoryStream(,$bytes)
$br = New-Object System.IO.BinaryReader($ms)

function U16 { return $br.ReadUInt16() }
function U32 { return $br.ReadUInt32() }

$br.ReadUInt16() | Out-Null
$br.BaseStream.Seek(0x3C,'Begin') | Out-Null
$peOff = U32
$br.BaseStream.Seek($peOff,'Begin') | Out-Null
$br.ReadUInt32() | Out-Null          # PE\0\0

$machine = U16
$numSections = U16
$br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null
$sizeOptHdr = U16
$br.ReadUInt16()|Out-Null

$optHdrStart = $br.BaseStream.Position
$magic = U16
$is64 = ($magic -eq 0x20B)

Write-Host "PE32+ = $is64   magic=0x{0:X4}  optHdrStart=$optHdrStart  sizeOptHdr=$sizeOptHdr" -f $magic

# Standard fields differ between PE32 and PE32+.
if ($is64) {
    $br.ReadBytes(110) | Out-Null      # up to end of standard+windows fields
} else {
    $br.ReadBytes(94) | Out-Null
}
$ddStart = $br.BaseStream.Position
Write-Host "DataDirectories start at file offset $ddStart"
Write-Host ""

$names = @('export','import','resource','exception','security','basereloc',
           'debug','architecture','globalptr','tls','loadconfig','boundimport',
           'iat','delayimport','comdescriptor','reserved')
for ($i=0; $i -lt 16; $i++) {
    $rva = U32
    $sz  = U32
    if ($rva -ne 0 -or $sz -ne 0) {
        $nm = if ($i -lt $names.Count) { $names[$i] } else { "dir$i" }
        Write-Host ("  [{0,2}] {1,-14} RVA=0x{2:X8}  size=0x{3:X8}" -f $i, $nm, $rva, $sz)
    }
}

# Also dump section names so we can spot .edata
$secTableStart = $optHdrStart + $sizeOptHdr
$br.BaseStream.Seek($secTableStart,'Begin') | Out-Null
Write-Host "`nSections:"
for ($i=0; $i -lt $numSections; $i++) {
    $nb = $br.ReadBytes(8)
    $nm = [System.Text.Encoding]::ASCII.GetString($nb).TrimEnd([char]0)
    $vsz = U32; $va = U32; $rsz = U32; $ra = U32
    $br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null; $br.ReadUInt16()|Out-Null
    $br.ReadUInt16()|Out-Null; $br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null
    Write-Host ("  {0,-9} VA=0x{1:X8} VSZ=0x{2:X8} RAW=0x{3:X8} RSZ=0x{4:X8}" -f $nm,$va,$vsz,$ra,$rsz)
}
