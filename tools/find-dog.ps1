param(
    [string]$Unpacked = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked"
)
# Narrow down: the tameable Dog companion, the Cat companion, and the
# Player_Companion entities. These tell us the exact component set that makes
# an entity a friendly, player-owned follower.

$tmpl = Join-Path $Unpacked "TemplateResource"

$want = @(
    'Spawnpoint_POI_Wildlife_Dog_01',
    'Player_Companion_Skeleton_Melee_GemOfNecromancy',
    'Base_Animal_Wildlife_Tameable',
    'Base_Animal_Wildlife_Tameable_OnlyPetInteraction'
)

Write-Host "=== templates matching Dog / Companion / Cat (playable pets) ==="
foreach ($f in (Get-ChildItem $tmpl -File -Filter "*.json")) {
    $t = [System.IO.File]::ReadAllText($f.FullName)
    $m = [regex]::Match($t, '"name"\s*:\s*"([^"]*)"')
    if (-not $m.Success) { continue }
    $name = $m.Groups[1].Value
    # Dogs and cats as actual animal entities (not placement helpers)
    if ($name -match '(?i)^(Animal|Enemy|Player|Base).*(Dog|Cat|Companion)' -or
        $name -match '(?i)Companion') {
        $guid = ($f.Name -split '_')[0]
        Write-Host ("{0,-62} {1}" -f $name, $guid)
    }
}
