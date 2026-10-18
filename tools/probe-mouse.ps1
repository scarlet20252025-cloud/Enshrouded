# Exercise the mod's mouse input path and capture the result.
#
# The layer forwards window messages to ImGui, and ImGui is configured with
# io.MouseDrawCursor = true. So if mouse messages reach the UI, a software
# cursor is drawn at the posted position. Capturing the window and finding that
# cursor proves the input path works end to end.
#
# Also posts a click on a checkbox so we can confirm interactive widgets react.

param(
    [Parameter(Mandatory=$true)][long]$Hwnd,
    [int]$MoveX = 0,
    [int]$MoveY = 0,
    [string]$Out = "E:\DSH\肥鱼乐园\WolfMount\build\overlay_mouse.png",
    [switch]$Click
)

Add-Type -AssemblyName System.Drawing

$sig = @'
using System;
using System.Runtime.InteropServices;
public class MZ {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);

    // LPARAM for a mouse message is (y << 16) | x, in client coordinates.
    public static IntPtr MakeLParam(int x, int y) {
        return (IntPtr)((y << 16) | (x & 0xFFFF));
    }
}
'@
if (-not ("MZ" -as [type])) { Add-Type -TypeDefinition $sig }

$h = [IntPtr]$Hwnd

if ([MZ]::IsIconic($h)) { [MZ]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 500 }
[MZ]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 800

# WM_MOUSEMOVE = 0x0200. A few moves so ImGui latches the position.
Write-Host ("mouse move -> ({0},{1})" -f $MoveX, $MoveY)
for ($i = 0; $i -lt 4; $i++) {
    [MZ]::PostMessage($h, 0x0200, [IntPtr]0, [MZ]::MakeLParam($MoveX, $MoveY)) | Out-Null
    Start-Sleep -Milliseconds 60
}

if ($Click) {
    # WM_LBUTTONDOWN 0x0201 / WM_LBUTTONUP 0x0202, MK_LBUTTON = 0x0001
    Write-Host "left click"
    [MZ]::PostMessage($h, 0x0201, [IntPtr]1, [MZ]::MakeLParam($MoveX, $MoveY)) | Out-Null
    Start-Sleep -Milliseconds 220
    [MZ]::PostMessage($h, 0x0202, [IntPtr]0, [MZ]::MakeLParam($MoveX, $MoveY)) | Out-Null
    Start-Sleep -Milliseconds 400
}

Start-Sleep -Milliseconds 600

$r = New-Object MZ+RECT
[MZ]::GetClientRect($h, [ref]$r) | Out-Null
$w = $r.R - $r.L; $hgt = $r.B - $r.T
Write-Host ("client {0}x{1}" -f $w, $hgt)
if ($w -le 0 -or $hgt -le 0) { Write-Host "FAIL: bad client rect"; exit 1 }

$bmp = New-Object System.Drawing.Bitmap($w, $hgt)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $gfx.GetHdc()
$ok = [MZ]::PrintWindow($h, $hdc, 0x00000002)
$gfx.ReleaseHdc($hdc); $gfx.Dispose()
if (-not $ok) {
    Write-Host "PrintWindow failed; falling back to screen copy"
    $g2 = [System.Drawing.Graphics]::FromImage($bmp)
    $g2.CopyFromScreen(0, 0, 0, 0, (New-Object System.Drawing.Size($w, $hgt)))
    $g2.Dispose()
}
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host ("saved {0} ({1:N0} bytes)" -f $Out, (Get-Item $Out).Length)
