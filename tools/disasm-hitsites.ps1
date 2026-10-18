param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Disassemble the two HitEvent .text references to find the send site.
#
# 0x1403E93A2 and 0x1403EFA7D (image addresses). One of them should be a
# `mov edx, 0xCC0D57E0` immediately before a call to the event writer
# (0x140955400) — that is where HitEvent is dispatched.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

foreach ($site in @(0x1403E9200, 0x1403EF900)) {
    $start = $site
    $stop  = $site + 0x120
    Write-Host "################ window 0x{0:X} .. 0x{1:X}" -f $start, $stop
    & $objdump -d --start-address=$start --stop-address=$stop $Exe 2>&1 |
        ForEach-Object { Write-Host ("  " + $_) }
    Write-Host ""
}
