param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Disassemble the "send event" function (0x140955400) and the tame-event
# handler, to understand the call signature we would hook.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

Write-Host "=== 0x140955400 (event dispatch, ~80 bytes) ==="
& $objdump -d --start-address=0x140955400 --stop-address=0x140955460 $Exe 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
Write-Host ""

Write-Host "=== 0x14047D718 tame handler (wider window) ==="
& $objdump -d --start-address=0x14047D6F0 --stop-address=0x14047D7D0 $Exe 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
Write-Host ""

# Also disassemble the call sites to the event-send function to see the
# full argument pattern. The EntityDiedEvent send sites were at 0x25F7FB and
# 0x273767; the caller sets edx=hash, r8d=size, rcx=??, r9d=??
Write-Host "=== caller of send-event at 0x25F7E0 (full block) ==="
& $objdump -d --start-address=0x14025F7C0 --stop-address=0x14025F840 $Exe 2>&1 | ForEach-Object { Write-Host ("  " + $_) }
