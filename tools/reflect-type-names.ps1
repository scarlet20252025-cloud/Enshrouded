param(
    [string]$Reflection = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
)
$ErrorActionPreference = 'Stop'
$txt = [IO.File]::ReadAllText($Reflection)

$names = @('TameWildlifeEvent','AdminSpawnCommand','EnemyDebugAction','AdminEnemyAction','HitEvent','EntityDiedEvent')

foreach ($n in $names) {
    $pat = '"qualifiedName":"([^"]*' + $n + '[^"]*)"'
    $hits = [regex]::Matches($txt, $pat)
    Write-Host ("##### {0}  ({1} hits)" -f $n, $hits.Count)
    $hits | Select-Object -First 12 | ForEach-Object { Write-Host ("   " + $_.Groups[1].Value) }
}
