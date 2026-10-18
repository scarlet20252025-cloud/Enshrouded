param(
    [string]$Reflection = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
)
# Dump AdminSpawnCommand's fields so we know the struct layout, then we can find
# code that writes to it (the dispatcher).

$t = [System.IO.File]::ReadAllText($Reflection)

$i = $t.IndexOf('"name":"AdminSpawnCommand"')
if ($i -lt 0) { Write-Host "AdminSpawnCommand not found"; exit 1 }

$seg = $t.Substring($i, 2500)
Write-Host "=== AdminSpawnCommand ==="
$si = $seg.IndexOf('structFields')
if ($si -ge 0) {
    # Print fields one per line
    $fields = $seg.Substring($si)
    $m = [regex]::Matches($fields, '"(\w+)":\{"name":"(\w+)","type":(\d+),"dataOffset":(\d+)\}')
    foreach ($x in $m) {
        Write-Host ("  {0,-28} type={1,-6} offset={2}" -f $x.Groups[2].Value, $x.Groups[3].Value, $x.Groups[4].Value)
    }
} else {
    Write-Host ($seg.Substring(0, 400))
}
