param(
    [string]$Unpacked = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked",
    [string]$Out = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\companion-facts.txt"
)
# Extract the component sets of the companion / dog / wildlife-companion
# templates. This is the key to making the wolf a fighting follower.

$tmpl = Join-Path $Unpacked "TemplateResource"
$sb = New-Object System.Text.StringBuilder
function W([string]$s) { [void]$sb.AppendLine($s) }

$targets = [ordered]@{
    'Base_Companion'              = '2a931d54-81e9-4ee4-86c4-27271b0ea5a3'
    'Enemy_Companion_Wildlife'    = 'f2358637-5ce7-4925-bda5-ca68fab94700'
    'Companion_Test'              = '83fa0d96-c6bc-4c0a-a9bc-88494938fa19'
    'Dog_01_bright'               = '5d9c1829-69fc-4339-8bcc-5e62e63e9a31'
    'Cat_01_black'                = '1ce5ac27-d8b1-4fa8-92db-f568994d080f'
    'Base_Tameable'               = '4cbd184f-3236-481d-8862-f9dd264766d3'
}

function Get-Block([string]$json, [string]$typeName) {
    $needle = '"$type": "' + $typeName + '"'
    $i = $json.IndexOf($needle)
    if ($i -lt 0) { return $null }
    $start = $json.LastIndexOf('{', $i)
    $depth = 0; $j = $start
    while ($j -lt $json.Length) {
        $c = $json[$j]
        if ($c -eq '{') { $depth++ }
        elseif ($c -eq '}') { $depth--; if ($depth -eq 0) { break } }
        $j++
    }
    return $json.Substring($start, $j - $start + 1)
}

foreach ($k in $targets.Keys) {
    $f = Join-Path $tmpl ($targets[$k] + '_39768775_0.json')
    if (-not (Test-Path $f)) { W "MISSING $k"; continue }
    $t = [System.IO.File]::ReadAllText($f)
    $nm = [regex]::Match($t, '"name"\s*:\s*"([^"]*)"').Groups[1].Value

    W ("################################################################")
    W ("# {0}" -f $k)
    W ("# name : {0}" -f $nm)
    W ("# guid : {0}" -f $targets[$k])
    W ("################################################################")

    $comps = [regex]::Matches($t, '\$type"\s*:\s*"([^"]+)"') |
             ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
    W ("COMPONENTS ({0}):" -f $comps.Count)
    foreach ($c in ($comps | Sort-Object)) { W ("  " + $c) }

    W ""
    W "KEY FIELDS:"
    foreach ($comp in @('keen::ecs::Faction','keen::ecs::Animal','keen::ecs::IsTame',
                        'keen::ecs::AnimalSaved','keen::ecs::NetworkAnimal',
                        'keen::ecs::Companion','keen::ecs::FollowTarget',
                        'keen::ecs::HookShotAnchorSubEntity','keen::ecs::Aggro',
                        'keen::ecs::FriendSensor','keen::ecs::CombatTargetActor',
                        'keen::ecs::Enemy01BehaviorState','keen::ecs::InteractionOfferRuntime',
                        'keen::ecs::ClientInteractionOffer')) {
        $b = Get-Block $t $comp
        if ($b) {
            $short = ($b -replace '\s+',' ')
            if ($short.Length -gt 300) { $short = $short.Substring(0,300) + ' ...' }
            W ("  [{0}]" -f $comp)
            W ("    {0}" -f $short)
        }
    }
    W ""
}

[System.IO.File]::WriteAllText($Out, $sb.ToString())
Write-Host ("written {0:N0} bytes to {1}" -f $sb.Length, $Out)
