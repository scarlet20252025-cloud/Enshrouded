param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [string[]]$Terms
)
# Scan the game exe for admin/console command strings and the ECS entry points
# we would need in order to synthesise an AdminSpawnCommand at runtime.

$b = [System.IO.File]::ReadAllBytes($Exe)
Write-Host ("exe size = {0:N0} bytes" -f $b.Length)
Write-Host ""

function Find-Ascii([byte[]]$hay, [string]$needle) {
    $n = [System.Text.Encoding]::ASCII.GetBytes($needle)
    $hits = New-Object System.Collections.Generic.List[int]
    $limit = $hay.Length - $n.Length
    for ($i = 0; $i -le $limit; $i++) {
        if ($hay[$i] -ne $n[0]) { continue }
        $ok = $true
        for ($j = 1; $j -lt $n.Length; $j++) {
            if ($hay[$i+$j] -ne $n[$j]) { $ok = $false; break }
        }
        if ($ok) { $hits.Add($i) }
    }
    return $hits
}

foreach ($t in $Terms) {
    $hits = Find-Ascii $b $t
    Write-Host ("=== '{0}' : {1} hit(s)" -f $t, $hits.Count)
    foreach ($h in ($hits | Select-Object -First 6)) {
        $s = [math]::Max(0, $h - 90)
        $len = [math]::Min(230, $b.Length - $s)
        $seg = $b[$s..($s+$len-1)]
        $txt = -join ($seg | ForEach-Object { if ($_ -ge 32 -and $_ -lt 127) { [char]$_ } else { ' ' } })
        Write-Host ("    0x{0:X6}  {1}" -f $h, ($txt -replace '\s+',' '))
    }
    Write-Host ""
}
