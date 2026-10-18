param(
    [string]$Exe = "E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
)
# Locate the EntityDiedEvent / death dispatch so the taming hook can attach.
#
# The game is a custom ECS. Events like EntityDiedEvent are delivered by a
# dispatcher. We find the event name string in .rdata, then find code in .text
# that references it (an immediate operand in a `lea rcx, [rip+off]` or a
# `mov` of the address). Those xrefs are the dispatch sites.
#
# This is the static half of dynamic analysis: it gives us candidate addresses
# to set breakpoints on, which is what the debugger session (route B) needs.

$bytes = [System.IO.File]::ReadAllBytes($Exe)
$peOff = [BitConverter]::ToInt32($bytes, 0x3C)
$optStart = $peOff + 24
$imageBase = [BitConverter]::ToUInt64($bytes, $optStart + 24)
$numSections = [BitConverter]::ToUInt16($bytes, $peOff + 6)
$sizeOpt = [BitConverter]::ToUInt16($bytes, $peOff + 20)
$secTable = $optStart + $sizeOpt

$sections = @()
for ($i = 0; $i -lt $numSections; $i++) {
    $o = $secTable + $i * 40
    $sections += [pscustomobject]@{
        Name = [System.Text.Encoding]::ASCII.GetString($bytes, $o, 8).TrimEnd([char]0)
        VSize = [BitConverter]::ToUInt32($bytes, $o + 8)
        VA    = [BitConverter]::ToUInt32($bytes, $o + 12)
        RawSize = [BitConverter]::ToUInt32($bytes, $o + 16)
        Raw   = [BitConverter]::ToUInt32($bytes, $o + 20)
    }
}

function RawToRva([long]$off) {
    foreach ($s in $sections) {
        if ($s.RawSize -gt 0 -and $off -ge $s.Raw -and $off -lt ($s.Raw + $s.RawSize)) {
            return [int]($s.VA + ($off - $s.Raw))
        }
    }
    return -1
}
function RvaToRaw([long]$rva) {
    foreach ($s in $sections) {
        $span = [math]::Max($s.VSize, $s.RawSize)
        if ($rva -ge $s.VA -and $rva -lt ($s.VA + $span)) {
            $d = $rva - $s.VA
            if ($s.RawSize -gt 0 -and $d -lt $s.RawSize) { return [int]($s.Raw + $d) }
        }
    }
    return -1
}

# Target event type names. The dispatcher for each is what we want to hook.
$targets = @(
    'EntityDiedEvent',
    'TameWildlifeEvent',
    'AdminSpawnCommand',
    'AdminKillFactionCommand',
    'LootInteractionEvent',
    'StartFlyingEvent',
    'StopFlyingEvent'
)

foreach ($t in $targets) {
    $nb = [System.Text.Encoding]::ASCII.GetBytes($t)
    # find all occurrences of the string in the whole file
    $occurrences = @()
    for ($i = 0; $i -le $bytes.Length - $nb.Length; $i++) {
        if ($bytes[$i] -ne $nb[0]) { continue }
        $ok = $true
        for ($j = 1; $j -lt $nb.Length; $j++) {
            if ($bytes[$i+$j] -ne $nb[$j]) { $ok = $false; break }
        }
        if ($ok) { $occurrences += $i }
    }

    Write-Host ("=== '{0}' : {1} occurrence(s) ===" -f $t, $occurrences.Count)
    foreach ($so in ($occurrences | Select-Object -First 5)) {
        $rva = RawToRva $so
        $va = $imageBase + $rva
        Write-Host ("  file=0x{0:X}  rva=0x{1:X}  va=0x{2:X}" -f $so, $rva, $va)

        # Find code (in .text) that references this VA via RIP-relative LEA.
        # RIP-relative LEA: 48 8D 0D [disp32]  (lea rcx, [rip+disp])
        $text = $sections | Where-Object Name -eq '.text' | Select-Object -First 1
        if ($text) {
            $found = 0
            for ($i = $text.Raw; $i -lt $text.Raw + $text.RawSize - 7 -and $found -lt 3; $i++) {
                # LEA r64, [rip+disp32] encodings begin with 48 8D /r where /r mod=00 rm=101
                if ($bytes[$i] -eq 0x48 -and $bytes[$i+1] -eq 0x8D) {
                    $modrm = $bytes[$i+2]
                    # mod=00 (bits 7-6 == 0) and rm=101 (bits 2-0 == 5)
                    if (($modrm -band 0xC0) -eq 0 -and ($modrm -band 0x07) -eq 5) {
                        $disp = [BitConverter]::ToInt32($bytes, $i + 3)
                        $target = [uint64]($imageBase + (RawToRva $i) + 7 + $disp)
                        if ($target -eq $va) {
                            $siteRva = RawToRva $i
                            Write-Host ("      xref: lea at rva=0x{0:X} va=0x{1:X}" -f $siteRva, ($imageBase + $siteRva))
                            $found++
                        }
                    }
                }
            }
            if ($found -eq 0) {
                Write-Host "      (no RIP-relative LEA xref found in .text)"
            }
        }
    }
    Write-Host ""
}
