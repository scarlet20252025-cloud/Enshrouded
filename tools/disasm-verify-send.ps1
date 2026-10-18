param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Re-examine what 0x140955400 actually does. Earlier I labelled it "send event"
# but the surrounding code is FNV hashing. Disassemble it and its callers to
# get the real picture before writing any hook.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

Write-Host "=== 0x140955400 (called with rcx=buf, edx=hash, r8d=size, r9d=id) ==="
& $objdump -d --start-address=0x140955400 --stop-address=0x140955500 $Exe 2>&1 |
    ForEach-Object { Write-Host ("  " + $_) }
Write-Host ""

Write-Host "=== the OTHER call target 0x140954250 (tame handler calls it too) ==="
& $objdump -d --start-address=0x140954250 --stop-address=0x140954300 $Exe 2>&1 |
    ForEach-Object { Write-Host ("  " + $_) }
