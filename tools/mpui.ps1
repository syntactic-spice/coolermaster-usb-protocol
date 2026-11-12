# Helpers for driving MasterPlus+ during capture sessions (Windows only).
# Dot-source:  . tools\mpui.ps1
#   MP-Shot <name> [scale]        screenshot of the MasterPlus window -> _re\shots\<name>.png
#   MP-Click <x> <y>              left click at screen coords (cursor restored afterwards)
#   MP-Keys <sendkeys-string>     SendKeys text (works for plain text fields)
#   MP-Scan <scancode...>         press+release scan codes (works for key-capture fields)
#   MP-Change <label> <x> <y> [waitMs]  capture one click into captures\<label>.pcap and decode it
#   MP-Decode <label> [filterRegex]     decode a capture, optionally filtering OUT lines
$MPRepo = Split-Path -Parent $PSScriptRoot
$MPShots = Join-Path $MPRepo '_re\shots'
$MPPython = "$env:USERPROFILE\scoop\apps\python\current\python.exe"
New-Item -ItemType Directory -Force $MPShots | Out-Null

if (-not ('MPUI' -as [type])) {
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MPUI {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int dx, dy; public uint data, flags, time; public IntPtr extra; }
  [StructLayout(LayoutKind.Explicit)] public struct U { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public U u; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern uint SendInput(uint n, INPUT[] i, int size);
  public static void Scan(ushort scan, bool up) {
    var i = new INPUT[1]; i[0].type = 1; i[0].u.ki.wScan = scan; i[0].u.ki.dwFlags = 0x0008u | (up ? 0x0002u : 0u);
    SendInput(1, i, Marshal.SizeOf(typeof(INPUT)));
  }
}
"@
}
Add-Type -AssemblyName System.Drawing

function MP-Hwnd { [IntPtr](Get-Process MasterPlusApp | Select-Object -First 1).MainWindowHandle }
function MP-Shot([string]$Name, [double]$Scale = 0.5) {
    $h = MP-Hwnd; $r = New-Object MPUI+RECT; [void][MPUI]::GetWindowRect($h, [ref]$r)
    $w = $r.R - $r.L; $ht = $r.B - $r.T
    $bmp = New-Object System.Drawing.Bitmap $w, $ht
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc(); [void][MPUI]::PrintWindow($h, $dc, 2); $g.ReleaseHdc($dc); $g.Dispose()
    $sw = [int]($w * $Scale); $sh = [int]($ht * $Scale)
    $small = New-Object System.Drawing.Bitmap $sw, $sh
    $g2 = [System.Drawing.Graphics]::FromImage($small); $g2.InterpolationMode = 'HighQualityBicubic'; $g2.DrawImage($bmp, 0, 0, $sw, $sh); $g2.Dispose()
    $p = Join-Path $MPShots "$Name.png"; $small.Save($p, [System.Drawing.Imaging.ImageFormat]::Png); $small.Dispose(); $bmp.Dispose()
    $p
}
function MP-Click([int]$X, [int]$Y) {
    $old = New-Object MPUI+POINT; [void][MPUI]::GetCursorPos([ref]$old)
    [void][MPUI]::SetForegroundWindow((MP-Hwnd)); Start-Sleep -Milliseconds 150
    [void][MPUI]::SetCursorPos($X, $Y); Start-Sleep -Milliseconds 50
    [MPUI]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 40
    [MPUI]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 50
    [void][MPUI]::SetCursorPos($old.X, $old.Y)
}
function MP-Keys([string]$Keys) {
    Add-Type -AssemblyName System.Windows.Forms
    [void][MPUI]::SetForegroundWindow((MP-Hwnd)); Start-Sleep -Milliseconds 150
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
}
function MP-Scan([int[]]$Scan) {
    [void][MPUI]::SetForegroundWindow((MP-Hwnd)); Start-Sleep -Milliseconds 150
    foreach ($s in $Scan) { [MPUI]::Scan([uint16]$s, $false); Start-Sleep -Milliseconds 40 }
    $r = $Scan.Clone(); [array]::Reverse($r)
    foreach ($s in $r) { [MPUI]::Scan([uint16]$s, $true); Start-Sleep -Milliseconds 40 }
}
function MP-Decode([string]$Label, [string]$Filter = '') {
    $out = & $MPPython -I (Join-Path $MPRepo 'tools\decode.py') (Join-Path $MPRepo "captures\$Label.pcap")
    if ($Filter) { $out = $out | Where-Object { $_ -match ' OUT ' -and $_ -match $Filter } }
    $out | ForEach-Object { '{0,-40} {1}' -f $Label, ($_ -replace '^\s*\d+\s+[\d.]+\s+', '') }
}
function MP-Change([string]$Label, [int]$X, [int]$Y, [int]$WaitMs = 2000) {
    $cap = Join-Path $MPRepo 'tools\cap.ps1'
    & $cap start $Label | Out-Null; Start-Sleep -Milliseconds 400
    MP-Click $X $Y; Start-Sleep -Milliseconds $WaitMs
    & $cap stop | Out-Null
}
