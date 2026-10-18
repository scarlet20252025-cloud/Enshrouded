param(
    [string]$Unpacked = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked"
)
# Find the tameable companion animals (dog, cat) and compare them against the
# wolf, to see exactly which components make an animal a friendly companion.

$tmpl = Join-Path $Unpacked "TemplateResource"
$files = Get-ChildItem $tmpl -File -Filter "*.json"

Write-Host "=== templates whose name mentions Dog / Cat / Tame ==="
foreach ($f in $files) {
    $head = [System.IO.File]::ReadAllText($f.FullName)
    $m = [regex]::Match($head, '"name"\s*:\s*"([^"]*)"')
    if (-not $m.Success) { continue }
    $name = $m.Groups[1].Value
    if ($name -match '(?i)\b(dog|cat)\b' -or $name -match '(?i)tame') {
        $comps = [regex]::Matches($head, '\$type"\s*:\s*"([^"]+)"') |
                 ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
        $interesting = $comps | Where-Object {
            $_ -match '(?i)tame|animal|faction|companion|pet|follow|friend|livestock|interaction'
        }
        Write-Host ("--- {0}" -f $name)
        Write-Host ("    guid : {0}" -f ($f.Name -split '_')[0])
        Write-Host ("    comps: {0}" -f ($comps.Count))
        if ($interesting) {
            Write-Host ("    KEY  : {0}" -f ($interesting -join ', '))
        }
    }
}
