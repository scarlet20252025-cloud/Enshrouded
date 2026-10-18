param(
    [Parameter(Mandatory=$true)][string]$Path
)
# Parse the Enshrouded .kfc container header.
# The documented KFC2 layout puts the version/container/resource tables at
# fixed offsets in the header, addressed by KFCLocation records whose
# relative_offset is measured from the location field itself.

$fs = [System.IO.File]::OpenRead($Path)
$br = New-Object System.IO.BinaryReader($fs)

function RU32([long]$off) { $br.BaseStream.Seek($off,'Begin') | Out-Null; return $br.ReadUInt32() }
function RU64([long]$off) { $br.BaseStream.Seek($off,'Begin') | Out-Null; return $br.ReadUInt64() }
function RStr([long]$off,[int]$len) {
    $br.BaseStream.Seek($off,'Begin') | Out-Null
    $b = $br.ReadBytes($len)
    return (-join ($b | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { '.' } }))
}

Write-Host "=== KFC header ==="
$magic = RStr 0 4
Write-Host "magic      : $magic"
Write-Host ("size       : 0x{0:X8}" -f (RU32 4))
Write-Host ("unknown    : {0}" -f (RU32 8))
Write-Host ("padding    : {0}" -f (RU32 12))

# --- version ---------------------------------------------------------------
$vr = RU32 16; $vc = RU32 20; $va = 16 + $vr
Write-Host ""
Write-Host ("version    : rel=0x{0:X} count={1} -> abs=0x{2:X}" -f $vr, $vc, $va)
Write-Host ("  text     : '{0}'" -f (RStr $va ([int]$vc)))

# --- containers ------------------------------------------------------------
$cr = RU32 24; $cc = RU32 28; $ca = 24 + $cr
Write-Host ""
Write-Host ("containers : rel=0x{0:X} count={1} -> abs=0x{2:X}" -f $cr, $cc, $ca)
$totalContents = 0
for ($i = 0; $i -lt $cc; $i++) {
    $o = $ca + $i * 16
    $sz = RU64 $o
    $n  = RU64 ($o + 8)
    $totalContents += $n
    if ($i -lt 8) {
        Write-Host ("  [{0,2}] size={1,14:N0}  count={2,10:N0}" -f $i, $sz, $n)
    }
}
if ($cc -gt 8) { Write-Host ("  ... {0} more" -f ($cc - 8)) }
Write-Host ("  TOTAL contents across all containers: {0:N0}" -f $totalContents)

# --- resource locations ----------------------------------------------------
$rlr = RU32 48; $rlc = RU32 52; $rla = 48 + $rlr
Write-Host ""
Write-Host ("resLocs    : rel=0x{0:X} count={1} -> abs=0x{2:X}" -f $rlr, $rlc, $rla)
for ($i = 0; $i -lt [math]::Min(4, $rlc); $i++) {
    $o = $rla + $i * 12
    Write-Host ("  [{0}] offset=0x{1:X8} size={2:N0} count={3:N0}" -f `
        $i, (RU32 $o), (RU32 ($o + 4)), (RU32 ($o + 8)))
}

# --- resource indices ------------------------------------------------------
$rir = RU32 56; $ric = RU32 60
Write-Host ""
Write-Host ("resIndices : rel=0x{0:X} count={1:N0}" -f $rir, $ric)

# --- content table ---------------------------------------------------------
Write-Host ""
Write-Host "=== content static-map tables (offsets 64..128) ==="
$labels = @('content_buckets','content_keys','content_values',
            'resource_buckets','resource_keys','resource_values',
            'resBundle_buckets','resBundle_keys','resBundle_values')
$off = 64
foreach ($lb in $labels) {
    $rel = RU32 $off; $cnt = RU32 ($off + 4)
    $abs = $off + $rel
    Write-Host ("  {0,-18} rel=0x{1,-8:X} count={2,10:N0}  abs=0x{3:X}" -f $lb, $rel, $cnt, $abs)
    $off += 8
}

$fs.Close()
