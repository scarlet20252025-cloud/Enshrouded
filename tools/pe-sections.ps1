$ErrorActionPreference='Continue'
# Read PE section table properly (my earlier parse drifted: optional header
# offset must be computed from the COFF header, not assumed).
$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
$fs = [IO.File]::OpenRead($Exe)
$br = [IO.BinaryReader]::New($fs)
$fs.Position = 0x3C
$peOff = $br.ReadInt32()
$fs.Position = $peOff
$sig = $br.ReadUInt32()
$machine = $br.ReadUInt16()
$numSec = $br.ReadUInt16()
$br.ReadUInt32() | Out-Null   # TimeDateStamp
$br.ReadUInt32() | Out-Null   # PointerToSymbolTable
$br.ReadUInt32() | Out-Null   # NumberOfSymbols
$sizeOpt = $br.ReadUInt16()
$chars = $br.ReadUInt16()
$optStart = $fs.Position
"PE@{0:X} machine=0x{1:X4} sections={2} optSize={3}" -f $peOff, $machine, $numSec, $sizeOpt
$magic = $br.ReadUInt16()
"optional magic=0x{0:X4}" -f $magic
$fs.Position = $optStart + $sizeOpt
$secs = @()
for ($i = 0; $i -lt $numSec; $i++) {
    $nb = $br.ReadBytes(8)
    $nm = ([Text.Encoding]::ASCII.GetString($nb)).TrimEnd([char]0)
    $vs = $br.ReadUInt32(); $va = $br.ReadUInt32(); $rs = $br.ReadUInt32(); $rp = $br.ReadUInt32()
    $br.ReadUInt32() | Out-Null; $br.ReadUInt32() | Out-Null; $br.ReadUInt16() | Out-Null; $br.ReadUInt16() | Out-Null
    $br.ReadUInt32() | Out-Null; $br.ReadUInt32() | Out-Null
    $secs += [pscustomobject]@{ Name = $nm; VA = $va; VSize = $vs; Raw = $rp; RawSize = $rs }
}
$fs.Close()
$secs | Format-Table Name, VA, VSize, Raw, RawSize -AutoSize

$IMG = 0x140000000
foreach ($f in @(0x1504C48, 0x1C10064, 0x1504D48, 0x1C105DC, 0x1505DA0, 0x1C1359C, 0x1BFDD90, 0x1749C10, 0x1502BC0)) {
    $rva = $null
    foreach ($s in $secs) { if ($f -ge $s.Raw -and $f -lt ($s.Raw + $s.RawSize)) { $rva = [uint64]$s.VA + ([uint64]$f - [uint64]$s.Raw); $sec = $s.Name; break } }
    if ($rva -ne $null) { "file 0x{0:X} -> rva 0x{1:X} [{2}]" -f $f, $rva, $sec }
    else { "file 0x{0:X} -> no section" -f $f }
}
