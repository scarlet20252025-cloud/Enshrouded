param(
    [string]$Dir = "E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked\ItemInfo",
    [string]$Pattern = 'torch'
)
# Find item definitions whose debugName or locaTag mentions a torch, and dump
# the fields that identify the item at runtime.

$files = Get-ChildItem $Dir -File -Filter "*.json"
Write-Host ("scanning {0} ItemInfo resources for /{1}/i" -f $files.Count, $Pattern)
Write-Host ""

$n = 0
foreach ($f in $files) {
    $t = [System.IO.File]::ReadAllText($f.FullName)
    $m = [regex]::Match($t, '"debugName"\s*:\s*"([^"]*)"')
    $name = if ($m.Success) { $m.Groups[1].Value } else { "" }
    if ($name -notmatch $Pattern) { continue }
    $guid = ($f.Name -split '_')[0]
    Write-Host ("--- {0}" -f $name)
    Write-Host ("    guid: {0}" -f $guid)

    foreach ($field in @('"itemId"','"locaName"','"name"','"itemType"',
                         '"category"','"rarity"','"stackSize"','"slotId"',
                         '"equipmentSlot"','"weaponCategory"')) {
        $mm = [regex]::Match($t, $field + '\s*:\s*([^\n,]*)')
        if ($mm.Success) {
            Write-Host ("    {0,-18} {1}" -f $field.Trim('"') + ':', ($mm.Groups[1].Value.Trim()))
        }
    }
    Write-Host ""
    $n++
    if ($n -ge 25) { Write-Host "... truncated"; break }
}
Write-Host ("matched {0}" -f $n)
