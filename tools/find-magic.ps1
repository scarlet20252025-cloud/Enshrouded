param(
    [Parameter(Mandatory=$true)][string]$Path
)
# Search a binary for the ASCII magics KFC2/KFC3/KFC4 and print nearby strings,
# which reveals how the tool validates the container version.
$b = [System.IO.File]::ReadAllBytes($Path)
Write-Host ("file size = {0:N0} bytes" -f $b.Length)
Write-Host ""

$magics = @(
    @{ Name='KFC2'; Bytes=[byte[]](0x4B,0x46,0x43,0x32) },
    @{ Name='KFC3'; Bytes=[byte[]](0x4B,0x46,0x43,0x33) },
    @{ Name='KFC4'; Bytes=[byte[]](0x4B,0x46,0x43,0x34) }
)

foreach ($m in $magics) {
    $pat = $m.Bytes
    $hits = New-Object System.Collections.Generic.List[int]
    for ($i = 0; $i -le $b.Length - 4; $i++) {
        if ($b[$i] -eq $pat[0] -and $b[$i+1] -eq $pat[1] -and
            $b[$i+2] -eq $pat[2] -and $b[$i+3] -eq $pat[3]) {
            $hits.Add($i)
        }
    }
    Write-Host ("=== {0}: {1} hit(s) ===" -f $m.Name, $hits.Count)
    foreach ($h in ($hits | Select-Object -First 10)) {
        Write-Host ("  offset 0x{0:X6}" -f $h)
    }
    Write-Host ""
}

# Look for the error text the tool printed, to find the validation site.
Write-Host "=== searching for 'Invalid magic number' ==="
$needle = [System.Text.Encoding]::ASCII.GetBytes("Invalid magic number")
for ($i = 0; $i -le $b.Length - $needle.Length; $i++) {
    $ok = $true
    for ($j = 0; $j -lt $needle.Length; $j++) {
        if ($b[$i+$j] -ne $needle[$j]) { $ok = $false; break }
    }
    if ($ok) {
        Write-Host ("  found at 0x{0:X6}" -f $i)
    }
}
