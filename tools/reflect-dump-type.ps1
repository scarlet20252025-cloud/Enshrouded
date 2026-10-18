param(
    [string]$Reflection = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json",
    [Parameter(Mandatory=$true)][string[]]$QualifiedNames
)
$ErrorActionPreference = 'Stop'
$txt = [IO.File]::ReadAllText($Reflection)

foreach ($qn in $QualifiedNames) {
    # Match the whole type object: from its opening brace to the matching close.
    $pat = '\{"index":\d+,"name":"[^"]*","impactName":"[^"]*","qualifiedName":"' + [regex]::Escape($qn) + '".*?\}\}'
    $m = [regex]::Match($txt, $pat)
    if (-not $m.Success) {
        # fall back: locate by qualifiedName and print a window after it
        $i = $txt.IndexOf('"qualifiedName":"' + $qn + '"')
        if ($i -lt 0) { Write-Host ("##### {0}  NOT FOUND" -f $qn); continue }
        $start = [Math]::Max(0, $i - 400)
        Write-Host ("##### {0}  (window)" -f $qn)
        Write-Host $txt.Substring($start, [Math]::Min(2600, $txt.Length - $start))
        Write-Host ""
        continue
    }
    $json = $m.Value
    $obj = $json | ConvertFrom-Json
    Write-Host ("##### {0}" -f $qn)
    Write-Host ("    size={0} align={1} fieldCount={2} hash={3}" -f $obj.size, $obj.alignment, $obj.fieldCount, $obj.qualifiedHash)
    if ($obj.PSObject.Properties.Name -contains 'structFields') {
        foreach ($p in $obj.structFields.PSObject.Properties) {
            $f = $p.Value
            Write-Host ("    +{0,4}  {1,-28} type={2} elemSize={3} flags={4}" -f $f.dataOffset, $f.name, $f.type, $f.elementSize, $f.flags)
        }
    }
    if ($obj.PSObject.Properties.Name -contains 'enumValues') {
        foreach ($p in $obj.enumValues.PSObject.Properties) {
            Write-Host ("    {0} = {1}" -f $p.Name, $p.Value)
        }
    }
    Write-Host ""
}
