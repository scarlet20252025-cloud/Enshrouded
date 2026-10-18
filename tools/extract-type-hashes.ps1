param(
    [string]$Reflection = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
)
# Extract the qualified hashes and sizes of the ECS types we care about.
#
# The reflection data gives each type a qualifiedHash and impactHash. The game
# dispatches events by these hashes, so knowing them lets us identify the event
# dispatcher's hash table in the binary.

$t = [System.IO.File]::ReadAllText($Reflection)
$j = $t | ConvertFrom-Json

Write-Host "reflection data root keys:"
$j.PSObject.Properties | ForEach-Object { Write-Host ("  {0}  ({1})" -f $_.Name, $(if ($_.Value -is [Array]) { "array[" + $_.Value.Count + "]" } else { $_.Value.GetType().Name })) }
Write-Host ""

# The types are usually in a top-level "types" array.
$types = $j.types
if (-not $types) { $types = $j.Types }
if (-not $types) {
    # Fall back: find the array property whose first element has "qualifiedName".
    foreach ($p in $j.PSObject.Properties) {
        if ($p.Value -is [Array] -and $p.Value.Count -gt 0 -and $p.Value[0].PSObject.Properties.Name -contains 'qualifiedName') {
            $types = $p.Value
            Write-Host ("using property '{0}' for types" -f $p.Name)
            break
        }
    }
}

if (-not $types) { Write-Host "could not find the types array"; exit 1 }
Write-Host ("total types: {0}" -f $types.Count)
Write-Host ""

$wanted = @(
    'keen::ecs::EntityDiedEvent',
    'keen::actor::TameWildlifeEvent',
    'keen::ecs::AdminSpawnCommand',
    'keen::ecs::AdminKillFactionCommand',
    'keen::ecs::LootInteractionEvent',
    'keen::ecs::StartFlyingEvent',
    'keen::ecs::StopFlyingEvent',
    'keen::ecs::ImpactHierarchy',
    'keen::ecs::IsTame',
    'keen::ecs::Faction',
    'keen::ecs::Animal',
    'keen::ecs::HookShotAnchorSubEntity'
)

Write-Host "=== wanted types ==="
foreach ($w in $wanted) {
    $hit = $types | Where-Object { $_.qualifiedName -eq $w } | Select-Object -First 1
    if ($hit) {
        Write-Host ("  {0,-44} size={1,-5} qualifiedHash={2}  impactHash={3}" -f `
            $w, $hit.size, $hit.qualifiedHash, $hit.impactHash)
    } else {
        Write-Host ("  {0,-44} NOT FOUND" -f $w)
    }
}
