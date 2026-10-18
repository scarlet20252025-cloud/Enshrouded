param(
    [string]$Unpacked = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked",
    [string]$Out = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\animal-facts.txt"
)
# Dump everything needed to turn a wolf into a rideable companion:
#   - every Animal / wildlife template name + guid
#   - the full component list of the tameable base classes
#   - the Faction / animal Type enum values found in type metadata

$tmpl = Join-Path $Unpacked "TemplateResource"
$sb = New-Object System.Text.StringBuilder
function W([string]$s) { [void]$sb.AppendLine($s) }

W "================ ALL ANIMAL / WILDLIFE TEMPLATES ================"
foreach ($f in (Get-ChildItem $tmpl -File -Filter "*.json")) {
    $t = [System.IO.File]::ReadAllText($f.FullName)
    $m = [regex]::Match($t, '"name"\s*:\s*"([^"]*)"')
    if (-not $m.Success) { continue }
    $name = $m.Groups[1].Value
    if ($name -match '(?i)animal|wildlife|pet|companion|livestock|mount') {
        $guid = ($f.Name -split '_')[0]
        W ("{0,-58} {1}" -f $name, $guid)
    }
}

W ""
W "================ TAMEABLE BASE CLASS COMPONENTS ================"
$bases = @{
    'Base_Animal_Wildlife_Tameable'                    = '4cbd184f-3236-481d-8862-f9dd264766d3'
    'Base_Animal_Wildlife_Tameable_OnlyPetInteraction' = '095bb39c-1428-411e-ac36-a784563b4256'
    'Base_Animal_Wildlife_Tameable_Transformer'        = '08365b0a-2205-45d7-8f02-fecabd5d32db'
    'Base_Animal_Wildlife_Tameable_AG2'                = 'a2ee105d-d9d8-4a86-bffb-21a2cccd2756'
    'Base_Animal_Wildlife_NonTameable_AG1'             = 'ada12d9e-eeb5-4b28-ae88-1e34ac57c22b'
}
foreach ($k in $bases.Keys) {
    $f = Join-Path $tmpl ($bases[$k] + '_39768775_0.json')
    if (-not (Test-Path $f)) { W "MISSING $k"; continue }
    $t = [System.IO.File]::ReadAllText($f)
    $comps = [regex]::Matches($t, '\$type"\s*:\s*"([^"]+)"') |
             ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
    W ("--- {0}  ({1})" -f $k, $bases[$k])
    W ("    {0} components" -f $comps.Count)
    W ("    {0}" -f ($comps -join "`n    "))
    W ""
}

W "================ FACTION VALUES SEEN ================"
$factions = @{}
foreach ($f in (Get-ChildItem $tmpl -File -Filter "*.json")) {
    $t = [System.IO.File]::ReadAllText($f.FullName)
    foreach ($mm in [regex]::Matches($t, '"faction"\s*:\s*"([^"]+)"')) {
        $v = $mm.Groups[1].Value
        if ($factions.ContainsKey($v)) { $factions[$v]++ } else { $factions[$v] = 1 }
    }
}
foreach ($k in ($factions.Keys | Sort-Object)) {
    W ("{0,-24} {1,6} uses" -f $k, $factions[$k])
}

W ""
W "================ animal Type / TypeMask VALUES SEEN ================"
$types = @{}
foreach ($f in (Get-ChildItem $tmpl -File -Filter "*.json")) {
    $t = [System.IO.File]::ReadAllText($f.FullName)
    foreach ($mm in [regex]::Matches($t, '"(animalType|typeMask|animalTypes)"\s*:\s*(\[[^\]]*\]|"[^"]*"|\d+)')) {
        $key = $mm.Groups[1].Value + ' = ' + $mm.Groups[2].Value
        if ($types.ContainsKey($key)) { $types[$key]++ } else { $types[$key] = 1 }
    }
}
foreach ($k in ($types.Keys | Sort-Object)) {
    W ("{0,6}x  {1}" -f $types[$k], $k)
}

[System.IO.File]::WriteAllText($Out, $sb.ToString())
Write-Host ("written {0:N0} bytes to {1}" -f $sb.Length, $Out)
