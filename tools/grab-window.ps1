# Capture the Enshrouded window's own client area, regardless of z-order.
#
# PrintWindow with PW_RENDERFULLCONTENT asks the window to draw itself into a
# bitmap, so the capture works even when the window is behind others. This is
# what makes it reliable for a fullscreen Vulkan game that refuses to come to
# the foreground in a headless-ish session.

param(
    [long]$Hwnd,
    [string]$Out = "E:\DSH\肥鱼乐园\WolfMount\build\overlay_proof.png",
    [int]$SendKey = 0        # optional VK code to post first (e.g. 0x77 = F8)
)

Add-Type -AssemblyName System.Drawing

$sig = @'
using System;
using System.Runtime.InteropServices;
public class PW_Api {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
}
'@
if (-not ("PW_Api" -as [type])) { Add-Type -TypeDefinition $sig }

$h = [IntPtr]$Hwnd
if (-not [PW_Api]::IsIconic($h)) {
    # HWND_TOP = 0, SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW
    [PW_Api]::SetWindowPos($h, [IntPtr]0, 0, 0, 0, 0, 0x0002 -bor 0x0040 -bor 0x0001) | Out-Null
    [PW_Api]::BringWindowToTop($h) | Out-Null
    [PW_Api]::SetForegroundWindow($h) | Out-Null
    Start-Sleep -Milliseconds 1200
}

if ($SendKey -ne 0) {
    Write-Host ("posting key 0x{0:X2}" -f $SendKey)
    [PW_Api]::PostMessage($h, 0x0100, [IntPtr]$SendKey, [IntPtr]0x00420001) | Out-Null
    Start-Sleep -Milliseconds 150
    [PW_Api]::PostMessage($h, 0x0101, [IntPtr]$SendKey, [IntPtr]0xC0420001) | Out-Null
    Start-Sleep -Milliseconds 2000
}

$r = New-Object PW_Api+RECT
[PW_Api]::GetClientRect($h, [ref]$r) | Out-Null
$w = $r.R - $r.L
$hgt = $r.B - $r.T
Write-Host ("client size {0}x{1}" -f $w, $hgt)
if ($w -le 0 -or $hgt -le 0) { Write-Host "FAIL: bad client rect"; exit 1 }

$bmp = New-Object System.Drawing.Bitmap($w, $hgt)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $gfx.GetHdc()

# PW_RENDERFULLCONTENT = 0x00000002 - required for DirectX/Vulkan surfaces.
$ok = [PW_Api]::PrintWindow($h, $hdc, 0x00000002)
$gfx.ReleaseHdc($hdc)
$gfx.Dispose()

if (-not $ok) {
    Write-Host "PrintWindow returned false; falling back to screen copy"
    $gfx2 = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx2.CopyFromScreen(0, 0, 0, 0, (New-Object System.Drawing.Size($w, $hgt)))
    $gfx2.Dispose()
}

$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host ("saved {0} ({1:N0} bytes)" -f $Out, (Get-Item $Out).Length)
