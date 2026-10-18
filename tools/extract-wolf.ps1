param(
    [string]$Unpacked = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked"
)
# Extract the fields that matter for taming / faction / mounting from the
# wolf and dog entity templates.

$tmpl = Join-Path $Unpacked "TemplateResource"

function Get-ComponentBlock([string]$json, [string]$typeName) {
    # Find the component object whose $type equals $typeName and return its
    # "$value" body (brace-balanced).
    $needle = '"$type": "' + $typeName + '"'
    $i = $json.IndexOf($needle)
    if ($i -lt 0) { return $null }
    # Walk back to the enclosing '{'
    $start = $json.LastIndexOf('{', $i)
    # Now brace-match forward from $start
    $depth = 0
    $j = $start
    while ($j -lt $json.Length) {
        $c = $json[$j]
        if ($c -eq '{') { $depth++ }
        elseif ($c -eq '}') { $depth--; if ($depth -eq 0) { break } }
        $j++
    }
    return $json.Substring($start, $j - $start + 1)
}

$targets = @(
    @{ Label = 'WOLF earlygame'; Guid = '478381c5-585f-4264-b373-dbb1ea596eca' },
    @{ Label = 'WOLF Heavy';     Guid = 'f6a96b72-6da4-4e04-ab62-40e8d0feeac7' },
    @{ Label = 'WOLF AutoTest';  Guid = '0d75b9a9-7e48-4f3a-bf2a-19bf6021f531' }
)

foreach ($t in $targets) {
    $f = Join-Path $tmpl ($t.Guid + '_39768775_0.json')
    if (-not (Test-Path $f)) { Write-Host "MISSING $($t.Label)"; continue }
    $json = [System.IO.File]::ReadAllText($f)
    Write-Host ("================ {0}" -f $t.Label)
    Write-Host ("guid: {0}" -f $t.Guid)

    foreach ($comp in @('keen::ecs::Faction', 'keen::ecs::HookShotAnchorSubEntity',
                        'keen::ecs::SubEntities', 'keen::ecs::Health',
                        'keen::ecs::CombatTargetActor', 'keen::ecs::EnemyScaling')) {
        $blk = Get-ComponentBlock $json $comp
        if ($blk) {
            $short = $blk -replace '\s+', ' '
            if ($short.Length -gt 420) { $short = $short.Substring(0, 420) + ' ...' }
            Write-Host ("  [{0}]" -f $comp)
            Write-Host ("     {0}" -f $short)
        } else {
            Write-Host ("  [{0}] (absent)" -f $comp)
        }
    }
    Write-Host ""
}
