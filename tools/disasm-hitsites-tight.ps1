param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Zoom in tightly on the two HitEvent hash sites (0x3E93A2 and 0x3EFA7D) to
# read the exact instruction that references the hash.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

# Each site: show 64 bytes before and after the 4-byte hash immediate.
$sites = @(0x3E93A2, 0x3EFA7D)

foreach ($rva in $sites) {
    $va = 0x140000000 + $rva
    $start = $va - 64
    $stop  = $va + 32
    Write-Host "################ HitEvent hash at rva 0x{0:X} (va 0x{1:X})" -f $rva, $va
    & $objdump -d --start-address=$start --stop-address=$stop $Exe 2>&1 |
        ForEach-Object { Write-Host ("  " + $_) }
    Write-Host ""
}
