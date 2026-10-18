# Send F8 to the Enshrouded window and capture the screen, so the WolfMount
# overlay can be inspected visually.
#
# Takes the window handle as a parameter (found by enumeration) because
# FindWindow by title is unreliable with this game's window class.

param([long]$Hwnd)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$sig = @'
using System;
using System.Runtime.InteropServices;
public class WM_Api {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
'@
if (-not ("WM_Api" -as [type])) { Add-Type -TypeDefinition $sig }

$h = [IntPtr]$Hwnd
Write-Host "hwnd = $h"

[WM_Api]::ShowWindow($h, 5) | Out-Null
[WM_Api]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 1200

# VK_F8 = 0x77. WM_KEYDOWN 0x0100, WM_KEYUP 0x0101.
$VK_F8 = 0x77
Write-Host "posting F8"
[WM_Api]::PostMessage($h, 0x0100, [IntPtr]$VK_F8, [IntPtr]0x00420001) | Out-Null
Start-Sleep -Milliseconds 200
[WM_Api]::PostMessage($h, 0x0101, [IntPtr]$VK_F8, [IntPtr]0xC0420001) | Out-Null

Start-Sleep -Milliseconds 2000

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
Write-Host ("screen {0}x{1}" -f $bounds.Width, $bounds.Height)

$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

$out = "E:\DSH\肥鱼乐园\WolfMount\build\overlay_proof.png"
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose(); $bmp.Dispose()

if (Test-Path $out) {
    Write-Host ("saved {0} ({1:N0} bytes)" -f $out, (Get-Item $out).Length)
} else {
    Write-Host "FAIL: screenshot not written"; exit 1
}
