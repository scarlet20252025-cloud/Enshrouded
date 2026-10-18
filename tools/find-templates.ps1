param(
    [string]$Dir = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked\TemplateResource",
    [string]$Pattern = 'wolf'
)
# Scan TemplateResource JSONs for a name matching $Pattern and report the
# component types present, so we can tell tamable animals from enemies.

$files = Get-ChildItem $Dir -File -Filter "*.json"
Write-Host ("scanning {0} template resources for /{1}/i" -f $files.Count, $Pattern)
Write-Host ""

$rows = @()
foreach ($f in $files) {
    $t = [System.IO.File]::ReadAllText($f.FullName)
    # Template name is the first string field.
    $m = [regex]::Match($t, '"name"\s*:\s*"([^"]*)"')
    if (-not $m.Success) { continue }
    $name = $m.Groups[1].Value
    if ($name -notmatch $Pattern) { continue }

    # Which components does this template carry?
    $comps = [regex]::Matches($t, '\$type"\s*:\s*"([^"]+)"') |
             ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique

    $rows += [pscustomobject]@{
        Name = $name
        File = $f.Name
        Guid = ($f.Name -split '_')[0]
        Components = ($comps -join ',')
    }
}

Write-Host ("matched {0} template(s)" -f $rows.Count)
Write-Host ""
$rows | Sort-Object Name | ForEach-Object {
    Write-Host ("--- {0}" -f $_.Name)
    Write-Host ("    guid: {0}" -f $_.Guid)
    Write-Host ("    file: {0}" -f $_.File)
    Write-Host ("    comps: {0}" -f $_.Components)
}
