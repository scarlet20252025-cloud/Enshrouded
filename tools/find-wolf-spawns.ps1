param(
    [string]$Dir = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked",
    [string[]]$WolfGuids = @(
        'bf4ae22e-9f66-43da-bd75-9f1c3da3b69e',   # Spawnpoint_POI_Wildbeast_Wolf
        '1e0b74fd-9ea3-42ec-b495-8e72e94f6667',   # Spawnpoint_POI_Wildlife_Wolf_Earlygame
        'c2ccb01e-4051-45d6-8ee0-0498486019a3',   # Spawnpoint_POI_Wildbeast_Wolf_Heavy
        '4a11bd70-ea8a-4364-8153-63fa7fae42fb',   # Spawnpoint_Trigger_Wildbeast_Wolf
        '9f222e7d-3992-49e6-a271-717dbc74cb5b'    # Spawnpoint_Trigger_Wildbeast_Wolf_earlygame
    )
)
# Extract the world positions of wolf spawn points from the scene entity chunks.
#
# The scene stores every placed entity in a chunk file. Each chunk knows its own
# grid coordinates, and each entity carries a transform. Combining the two gives
# an in-game position a player can navigate to.

$sceneDir = Join-Path $Dir "SceneEntityChunkResource"
$sceneRes = Join-Path $Dir "SceneResource"
$entityDir = Join-Path $Dir "SceneEntityChunkResource"

Write-Host "=== wolf spawn points ==="
Write-Host ""

$files = Get-ChildItem $sceneDir -File -Filter "*.json" -ErrorAction SilentlyContinue
Write-Host ("scanning {0} entity chunks" -f $files.Count)

$found = @()
foreach ($f in $files) {
    $t = [System.IO.File]::ReadAllText($f.FullName)
    foreach ($g in $WolfGuids) {
        if ($t.Contains($g)) {
            $found += [pscustomobject]@{ File = $f.FullName; Name = $f.Name; Guid = $g }
            break
        }
    }
}

Write-Host ("chunks referencing a wolf spawn point: {0}" -f $found.Count)
Write-Host ""

# The chunk grid origin lives in the SceneResource; pull it so raw entity
# coordinates can be turned into world space.
$sceneFiles = Get-ChildItem $sceneRes -File -Filter "*.json" -ErrorAction SilentlyContinue
Write-Host ("scene resource files: {0}" -f $sceneFiles.Count)
foreach ($sf in ($sceneFiles | Select-Object -First 2)) {
    Write-Host ("--- {0} ---" -f $sf.Name)
    $j = [System.IO.File]::ReadAllText($sf.FullName) | ConvertFrom-Json
    foreach ($p in $('entityChunkCount', 'entityChunkSize', 'bounds', 'origin')) {
        $v = $j.$p
        if ($null -ne $v) {
            Write-Host ("  {0} = {1}" -f $p, ($v | ConvertTo-Json -Compress -Depth 4))
        }
    }
}

Write-Host ""
Write-Host "=== first 5 chunks with wolf spawns ==="
foreach ($x in ($found | Select-Object -First 5)) {
    $j = [System.IO.File]::ReadAllText($x.File) | ConvertFrom-Json
    Write-Host ("--- {0}" -f $x.Name)
    Write-Host ("    part={0}  entities={1}" -f $j.'$part', $j.entities.Count)
}
