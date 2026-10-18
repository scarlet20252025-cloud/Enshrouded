#!/usr/bin/env pwsh
# Read a PE export directory by brute-force byte scanning, bypassing the
# section table entirely. Robust against odd linker layouts.
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
$br.ReadUInt32() | Out-Null
$machine = U16; $numSections = U16
$br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null
$sizeOptHdr = U16; $br.ReadUInt16()|Out-Null
$optHdrStart = $br.BaseStream.Position
$magic = U16
$is64 = ($magic -eq 0x20B)

# Read the data directories with the correct offset for the PE flavour.
if ($is64) { $br.ReadBytes(110) | Out-Null } else { $br.ReadBytes(94) | Out-Null }
$exportRVA = U32; $exportSize = U32

# Build an RVA -> file offset map. For images where sections are declared
# with raw size 0 but a real virtual size, fall back to the section's virtual
# address mapped onto the raw layout of the previous populated section.
$secTableStart = $optHdrStart + $sizeOptHdr
$br.BaseStream.Seek($secTableStart,'Begin') | Out-Null
$sections = @()
for ($i=0; $i -lt $numSections; $i++) {
    $nb = $br.ReadBytes(8)
    $nm = [System.Text.Encoding]::ASCII.GetString($nb).TrimEnd([char]0)
    $vsz = U32; $va = U32; $rsz = U32; $ra = U32
    $br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null; $br.ReadUInt16()|Out-Null
    $br.ReadUInt16()|Out-Null; $br.ReadUInt32()|Out-Null; $br.ReadUInt32()|Out-Null
    if ($nm.Length -gt 0 -and $rsz -gt 0 -and $ra -gt 0) {
        $sections += [pscustomobject]@{ Name=$nm; VA=$va; VSize=$vsz; RawAddr=$ra; RawSize=$rsz }
    }
}

function R2O([uint32]$rva) {
    foreach ($s in $sections) {
        $span = [math]::Max($s.VSize, $s.RawSize)
        if ($rva -ge $s.VA -and $rva -lt ($s.VA + $span)) {
            return $s.RawAddr + ($rva - $s.VA)
        }
    }
    # Unmapped: assume the section is backed by raw data at its own VA.
    return [int]$rva
}

Write-Host "PE32+=$is64  export RVA=0x{0:X8} size=0x{1:X8}" -f $exportRVA, $exportSize
if ($exportRVA -eq 0) { Write-Host "NO EXPORT TABLE"; exit 1 }

$off = R2O $exportRVA
Write-Host "export dir file offset = $off (0x{0:X})" -f $off

# IMAGE_EXPORT_DIRECTORY: 40 bytes
$br.BaseStream.Seek($off,'Begin') | Out-Null
$chars = U32; $ts = U32; $ver = U32
$nameRVA = U32
$ordBase = U32
$numFuncs = U32
$numNames = U32
$funcsRVA = U32
$namesRVA = U32
$ordsRVA  = U32

Write-Host "numFuncs=$numFuncs numNames=$numNames nameRVA=0x{0:X8} funcsRVA=0x{1:X8} namesRVA=0x{2:X8}" -f $nameRVA,$funcsRVA,$namesRVA
if ($numFuncs -gt 100000 -or $numNames -gt 100000) {
    Write-Host "malformed"
    exit 1
}

function ReadCStrAt([int]$o) {
    $save = $br.BaseStream.Position
    $br.BaseStream.Seek($o,'Begin') | Out-Null
    $sb = New-Object System.Text.StringBuilder
    while (($b = $br.ReadByte()) -ne 0) { [void]$sb.Append([char]$b) }
    $br.BaseStream.Seek($save,'Begin') | Out-Null
    return $sb.ToString()
}

$dllName = ReadCStrAt (R2O $nameRVA)
Write-Host "DLL name: $dllName"
Write-Host ""

$namesOff = R2O $namesRVA
$br.BaseStream.Seek($namesOff,'Begin') | Out-Null
$namePtrs = @()
for ($i=0; $i -lt $numNames; $i++) { $namePtrs += U32 }

$exports = @()
for ($i=0; $i -lt $numNames; $i++) {
    $nm = ReadCStrAt (R2O $namePtrs[$i])
    $exports += $nm
}

Write-Host "=== EXPORTS ($($exports.Count)) ==="
$exports | Sort-Object | ForEach-Object { Write-Host "  $_" }

$required = @(
    'vkNegotiateLoaderLayerInterfaceVersion',
    'vkEnumerateInstanceLayerProperties',
    'vkEnumerateInstanceExtensionProperties',
    'vkEnumerateDeviceLayerProperties',
    'vkEnumerateDeviceExtensionProperties',
    'wolfmount_GetInstanceProcAddr',
    'wolfmount_GetDeviceProcAddr'
)
Write-Host "`n=== REQUIRED CHECK ==="
$fail = 0
foreach ($r in $required) {
    if ($exports -contains $r) { Write-Host "  OK    $r" }
    else { Write-Host "  MISS  $r"; $fail++ }
}
if ($fail -gt 0) { Write-Host "`nRESULT: FAIL"; exit 1 }
Write-Host "`nRESULT: PASS"
