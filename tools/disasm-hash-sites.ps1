param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Disassemble the neighbourhood of each hash hit to understand the context.
# We use the bundled llvm-objdump on the FILE, addressing by RVA.

$tc = "C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin"
$objdump = Join-Path $tc "llvm-objdump.exe"

$sites = @(
    @{ Name='EntityDiedEvent'; Rva=0x25F7FC },
    @{ Name='EntityDiedEvent'; Rva=0x273768 },
    @{ Name='EntityDiedEvent'; Rva=0x16DF240 },
    @{ Name='TameWildlifeEvent'; Rva=0x47D71A },
    @{ Name='TameWildlifeEvent'; Rva=0x1B01110 },
    @{ Name='AdminSpawnCommand'; Rva=0x174B210 },
    @{ Name='AdminKillFactionCommand'; Rva=0x174BF10 }
)

foreach ($s in $sites) {
    # Disassemble a window around the hit. The hit RVA points at the 4-byte
    # hash immediate, which is usually 3-4 bytes into an instruction.
    $start = $s.Rva - 32
    $stop  = $s.Rva + 32
    Write-Host ("################ {0}  around rva 0x{1:X}" -f $s.Name, $s.Rva)

    # llvm-objdump uses image addresses for a PE. The image base is 0x140000000.
    $imgStart = 0x140000000 + $start
    $imgStop  = 0x140000000 + $stop
    $out = & $objdump -d --start-address=$imgStart --stop-address=$imgStop $Exe 2>&1
    $out | ForEach-Object { Write-Host ("  " + $_) }
    Write-Host ""
}
