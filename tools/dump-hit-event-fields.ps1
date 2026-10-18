param(
    [string]$Reflection = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
)
# Dump the struct fields of the hit/damage events to find where the attacking
# weapon itemId is recorded.

$t = [System.IO.File]::ReadAllText($Reflection)
$j = $t | ConvertFrom-Json
$types = $j.types

$wanted = @(
    'keen::ds::ecs::HitEvent',
    'keen::ds::ecs::BaseHitEvent',
    'keen::ecs::EntityDiedEvent',
    'keen::actor::SyncAttackEvent',
    'keen::ds::ecs::SyncedAttackEvent',
    'keen::ds::impact_nodes::SendBaseHitEvent'
)

function DumpType($name) {
    $hit = $types | Where-Object { $_.qualifiedName -eq $name } | Select-Object -First 1
    if (-not $hit) { Write-Host ("  {0,-44} NOT FOUND" -f $name); return }

    Write-Host ("=== {0}  (size={1}, qualifiedHash=0x{2:X8}) ===" -f `
        $name, $hit.size, $hit.qualifiedHash)

    $fields = $hit.structFields
    if ($fields) {
        foreach ($fp in $fields.PSObject.Properties) {
            $f = $fp.Value
            Write-Host ("    {0,-30} type={1,-6} offset={2}" -f $f.name, $f.type, $f.dataOffset)
        }
    } else {
        Write-Host "    (no structFields; primitive or empty)"
    }
    Write-Host ""
}

foreach ($w in $wanted) { DumpType $w }
