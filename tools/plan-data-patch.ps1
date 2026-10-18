param(
    [string]$Unpacked = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked"
)
# Investigate the DATA-PATCH route to taming.
#
# Idea: instead of hooking the game at runtime, change the shipped entity
# templates so a wolf behaves like a tamed companion.
#
# The tameable base classes (Base_Animal_Wildlife_Tameable*) prove which
# components make an animal friendly. If the wolf template can simply be given
# those components, the game loads a friendly wolf with no code injection.
#
# This script measures what would have to change and whether the pieces the
# game would need (IsTame, Animal, the interaction offer) can be expressed in
# template data alone.

$tmpl = Join-Path $Unpacked "TemplateResource"

function Get-Components([string]$json) {
    [regex]::Matches($json, '\$type"\s*:\s*"([^"]+)"') |
        ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
}

$wolfGuid  = '478381c5-585f-4264-b373-dbb1ea596eca'   # Enemy_Wildbeast_wolf_earlygame
$tameGuid  = '4cbd184f-3236-481d-8862-f9dd264766d3'   # Base_Animal_Wildlife_Tameable
$dogGuid   = '5d9c1829-69fc-4339-8bcc-5e62e63e9a31'   # Animal_Wildlife_Dog_01_bright_AG2

$wolfF = Get-ChildItem $tmpl -Filter "$wolfGuid*" | Select-Object -First 1
$tameF = Get-ChildItem $tmpl -Filter "$tameGuid*" | Select-Object -First 1
$dogF  = Get-ChildItem $tmpl -Filter "$dogGuid*"  | Select-Object -First 1

foreach ($x in @(@('WOLF', $wolfF), @('TAMEABLE', $tameF), @('DOG', $dogF))) {
    if (-not $x[1]) { Write-Host ("MISSING {0}" -f $x[0]); continue }
    Write-Host ("{0,-9} {1}" -f $x[0], $x[1].Name)
}
Write-Host ""

$wolfJ = [System.IO.File]::ReadAllText($wolfF.FullName)
$tameJ = [System.IO.File]::ReadAllText($tameF.FullName)
$dogJ  = [System.IO.File]::ReadAllText($dogF.FullName)

$wc = Get-Components $wolfJ
$tc = Get-Components $tameJ
$dc = Get-Components $dogJ

Write-Host ("wolf     : {0} components" -f $wc.Count)
Write-Host ("tameable : {0} components" -f $tc.Count)
Write-Host ("dog      : {0} components" -f $dc.Count)
Write-Host ""

# Components the dog/tameable have that the wolf lacks — these are exactly the
# edits a data patch would have to add.
$need = $dc | Where-Object { $wc -notcontains $_ }
Write-Host ("=== components a wolf would need (present in DOG, missing in WOLF): {0} ===" -f $need.Count)
foreach ($c in $need) { Write-Host ("  + {0}" -f $c) }
Write-Host ""

# Components the wolf has that the dog lacks — these would have to be removed
# or neutralised for the wolf to stop behaving like a hostile enemy.
$drop = $wc | Where-Object { $dc -notcontains $_ }
Write-Host ("=== wolf-only components (absent from DOG): {0} ===" -f $drop.Count)
foreach ($c in $drop) { Write-Host ("  - {0}" -f $c) }
Write-Host ""

# The critical ones for taming specifically.
Write-Host "=== taming-critical components ==="
foreach ($c in @('keen::ecs::IsTame','keen::ecs::Animal','keen::ecs::AnimalSaved',
                 'keen::ecs::NetworkAnimal','keen::ecs::Faction',
                 'keen::ecs::ClientInteractionOffer','keen::ecs::InteractionOfferRuntime',
                 'keen::ecs::Aggro','keen::ecs::Enemy01BehaviorState')) {
    Write-Host ("  {0,-42} wolf={1,-6} dog={2,-6} tameable={3}" -f `
        $c,
        ($(if ($wc -contains $c) { 'yes' } else { 'no' })),
        ($(if ($dc -contains $c) { 'yes' } else { 'no' })),
        ($(if ($tc -contains $c) { 'yes' } else { 'no' })))
}
