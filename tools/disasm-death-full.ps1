param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Precisely disassemble the whole death-handling function, not just the send
# site, to find where the victim entity id and the killing weapon come from.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

# The send site is at 0x14025F7FB. Disassemble a wide window around it.
$start = 0x14025F600
$stop  = 0x14025FA00
Write-Host "=== death handler, 0x14025F600 .. 0x14025FA00 ==="
& $objdump -d --start-address=$start --stop-address=$stop $Exe 2>&1 |
    ForEach-Object { Write-Host ("  " + $_) }
