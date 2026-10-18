param(
    [string]$Dir = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked",
    [string]$Out = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\wolf-spawns.csv"
)
# Extract wolf spawn world coordinates from the scene entity chunks.
#
# TRANSFORM ENCODING (confirmed by decoding real data):
#
#   transform.positionX0 / positionX1 are the LOW and HIGH halves of a
#   16.16-style fixed point pair, NOT a 64-bit integer.
#
#       world = position1 + position0 / 65536
#
#   Decoding a known wolf point gives (1751.63, 977.78, 925.33), which are
#   plausible metre-scale world coordinates. The earlier "(hi<<32|lo)/8192"
#   reading produced ~9e8 and was wrong.
#
#   scale = 8192 is a separate uniform-scale field, not the position divisor.

$sceneDir  = Join-Path $Dir "SceneEntityChunkResource"
$sceneRes  = Join-Path $Dir "SceneResource"
$chunkGrid = 40

$sceneFile = Get-ChildItem $sceneRes -File -Filter "509feadb*.json" | Select-Object -First 1
if ($sceneFile) {
    $sj = [System.IO.File]::ReadAllText($sceneFile.FullName) | ConvertFrom-Json
    if ($sj.entityChunkCount) { $chunkGrid = [int]$sj.entityChunkCount.x }
}
Write-Host ("chunk grid = {0} x {0}" -f $chunkGrid)

$wolfSpawns = [ordered]@{
    'bf4ae22e-9f66-43da-bd75-9f1c3da3b69e' = 'POI_Wolf'
    '1e0b74fd-9ea3-42ec-b495-8e72e94f6667' = 'POI_Wolf_Earlygame'
    'c2ccb01e-4051-45d6-8ee0-0498486019a3' = 'POI_Wolf_Heavy'
    '4a11bd70-ea8a-4364-8153-63fa7fae42fb' = 'Trigger_Wolf'
    '9f222e7d-3992-49e6-a271-717dbc74cb5b' = 'Trigger_Wolf_Earlygame'
    'f7f3e836-54a8-435b-b881-9c660908fdb4' = 'Trigger_Wolf_Heavy'
}

function DecodePos([int]$lo, [int]$hi) {
    # world = hi + lo / 65536   (16.16 fixed point)
    return ([double]$hi) + ([double]$lo / 65536.0)
}

$rows = New-Object System.Collections.Generic.List[object]
$files = Get-ChildItem $sceneDir -File -Filter "509feadb*.json" -ErrorAction SilentlyContinue

foreach ($f in $files) {
    $raw = [System.IO.File]::ReadAllText($f.FullName)

    $hitName = $null
    foreach ($k in $wolfSpawns.Keys) {
        if ($raw.Contains($k)) { $hitName = $wolfSpawns[$k]; break }
    }
    if (-not $hitName) { continue }

    $j = $raw | ConvertFrom-Json
    $part = [int]$j.'$part'
    $cy = [math]::Floor($part / $chunkGrid)
    $cx = $part % $chunkGrid

    $tmpl = @($j.templates)
    $wolfSlots = New-Object System.Collections.Generic.HashSet[int]
    for ($i = 0; $i -lt $tmpl.Count; $i++) {
        if ($wolfSpawns.Contains($tmpl[$i])) { [void]$wolfSlots.Add($i) }
    }
    if ($wolfSlots.Count -eq 0) { continue }

    foreach ($e in $j.entities) {
        if (-not $wolfSlots.Contains([int]$e.templateIndex)) { continue }
        $t = $e.transform
        if ($null -eq $t.positionX0) { continue }

        $x = DecodePos $t.positionX0 $t.positionX1
        $y = DecodePos $t.positionY0 $t.positionY1
        $z = DecodePos $t.positionZ0 $t.positionZ1

        $rows.Add([pscustomobject]@{
            SpawnType = $wolfSpawns[$tmpl[[int]$e.templateIndex]]
            ChunkPart = $part
            ChunkX    = $cx
            ChunkY    = $cy
            X         = [math]::Round($x, 1)
            Y         = [math]::Round($y, 1)
            Z         = [math]::Round($z, 1)
        })
    }
}

# Sanity check: the world is about 12 km across, so coordinates should sit
# within a few thousand metres of the origin.
$bad = @($rows | Where-Object { [math]::Abs($_.X) -gt 20000 -or [math]::Abs($_.Z) -gt 20000 })
Write-Host ("points: {0}   out-of-range: {1}" -f $rows.Count, $bad.Count)

$rows | Sort-Object SpawnType, Y, X | Export-Csv -Path $Out -NoTypeInformation -Encoding UTF8
Write-Host ("wrote {0}" -f $Out)
Write-Host ""

Write-Host "=== 近郊狼点(按 Y 从低到高,即地势低到高) ==="
$rows | Sort-Object Y | Select-Object -First 15 |
    Format-Table SpawnType, ChunkPart, X, Y, Z -AutoSize | Out-String -Width 130 | Write-Host

Write-Host "=== 坐标范围 ==="
$xs = $rows | Measure-Object X -Minimum -Maximum
$ys = $rows | Measure-Object Y -Minimum -Maximum
$zs = $rows | Measure-Object Z -Minimum -Maximum
Write-Host ("  X: {0:N0} .. {1:N0}" -f $xs.Minimum, $xs.Maximum)
Write-Host ("  Y: {0:N0} .. {1:N0}" -f $ys.Minimum, $ys.Maximum)
Write-Host ("  Z: {0:N0} .. {1:N0}" -f $zs.Minimum, $zs.Maximum)
