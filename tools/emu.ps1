# Drive the portable DuckStation in work/emulator/duckstation for testing.
#   tools/emu.ps1 start <cue|exe> [-StateFile path] [-Scale N] [-Renderer Software|D3D11]
#   tools/emu.ps1 keys "<seq>"       e.g. "Return:100 wait:2000 Z x3 Down Z"
#   tools/emu.ps1 shot <out.png>     F10 screenshot copied to <out.png>
#   tools/emu.ps1 save | load        F1 / F3 (selected slot)
#   tools/emu.ps1 stop
# Keys follow settings.ini [Pad1]: Z=Circle X=Cross S=Triangle A=Square Return=Start.
param([string]$Cmd, [string]$Arg, [string]$StateFile, [int]$Scale = 0, [string]$Renderer)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Emu = Join-Path $Root 'work\emulator\duckstation'
$Exe = Join-Path $Emu 'duckstation-qt-x64-ReleaseLTCG.exe'

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class EmuInput {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    public static void Key(byte vk, int holdMs) {
        byte sc = (byte)MapVirtualKey(vk, 0);
        uint ext = (vk >= 0x21 && vk <= 0x28) ? 1u : 0u;
        keybd_event(vk, sc, ext, UIntPtr.Zero);
        System.Threading.Thread.Sleep(holdMs);
        keybd_event(vk, sc, ext | 2u, UIntPtr.Zero);
    }
}
'@

$VK = @{ Up = 0x26; Down = 0x28; Left = 0x25; Right = 0x27; Return = 0x0D; Backspace = 0x08;
         Z = 0x5A; X = 0x58; S = 0x53; A = 0x41; Q = 0x51; E = 0x45; '1' = 0x31; '3' = 0x33;
         Tab = 0x09; Space = 0x20; F1 = 0x70; F3 = 0x72; F10 = 0x79 }

# only the project's test emulator (never another DuckStation the user is running)
function Get-EmuProc { Get-Process -Name 'duckstation-qt-x64-ReleaseLTCG' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Exe } | Select-Object -First 1 }

function Focus-Emu {
    $p = Get-EmuProc
    if (-not $p) { throw 'DuckStation is not running' }
    [EmuInput]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
    [EmuInput]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 150
}

function Send-Keys([string]$seq) {
    Focus-Emu
    foreach ($tok in ($seq -split '\s+' | Where-Object { $_ })) {
        if ($tok -match '^wait:(\d+)$') { Start-Sleep -Milliseconds ([int]$Matches[1]); continue }
        $rep = 1; $hold = 80
        if ($tok -match '^(.+?)x(\d+)$' -and $VK.ContainsKey($Matches[1])) { $tok = $Matches[1]; $rep = [int]$Matches[2] }
        if ($tok -match '^(.+):(\d+)$') { $tok = $Matches[1]; $hold = [int]$Matches[2] }
        if (-not $VK.ContainsKey($tok)) { throw "unknown key $tok" }
        for ($i = 0; $i -lt $rep; $i++) { [EmuInput]::Key([byte]$VK[$tok], $hold); Start-Sleep -Milliseconds 120 }
    }
}

function Set-Ini([string]$section, [string]$key, [string]$value) {
    $ini = Join-Path $Emu 'settings.ini'
    $lines = [System.Collections.ArrayList]@(Get-Content $ini)
    $sec = -1; $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\[(.+)\]') { $sec = ($Matches[1] -eq $section) ; continue }
        if ($sec -eq $true -and $lines[$i] -match "^$key\s*=") { $lines[$i] = "$key = $value"; $found = $true }
    }
    if (-not $found) { throw "missing $section/$key in settings.ini" }
    Set-Content -Path $ini -Value $lines -Encoding ascii
}

switch ($Cmd) {
    'start' {
        if (Get-EmuProc) { throw 'DuckStation already running; stop it first' }
        if ($Scale -gt 0) { Set-Ini 'GPU' 'ResolutionScale' $Scale }
        if ($Renderer) { Set-Ini 'GPU' 'Renderer' $Renderer }
        $a = @('-batch', '-nofullscreen')
        if ($StateFile) { $a += @('-statefile', "`"$((Resolve-Path $StateFile).Path)`"") }
        if ($Arg) {
            $full = (Resolve-Path $Arg).Path
            if ($full -like '*.exe' -or $full -like '*.EXE') { $a += @('-exe', "`"$full`"") } else { $a += @('--', "`"$full`"") }
        }
        Start-Process -FilePath $Exe -ArgumentList $a -WorkingDirectory $Emu | Out-Null
        Start-Sleep -Seconds 4
        'started'
    }
    'keys' { Send-Keys $Arg }
    'shot' {
        $dir = Join-Path $Emu 'screenshots'
        New-Item -ItemType Directory -Force $dir | Out-Null
        $before = Get-Date
        Send-Keys 'F10'
        $f = $null
        for ($i = 0; $i -lt 40 -and -not $f; $i++) {
            Start-Sleep -Milliseconds 250
            $f = Get-ChildItem $dir -Recurse -File | Where-Object { $_.LastWriteTime -gt $before } | Sort-Object LastWriteTime | Select-Object -Last 1
        }
        if (-not $f) { throw 'no screenshot produced' }
        Start-Sleep -Milliseconds 300
        $out = $Arg
        New-Item -ItemType Directory -Force (Split-Path -Parent $out) | Out-Null
        for ($t = 0; $t -lt 20; $t++) { try { Copy-Item $f.FullName $out -Force -ErrorAction Stop; break } catch { Start-Sleep -Milliseconds 250 } }
        $out
    }
    'grab' {
        # capture all top-level windows of the emulator process from the screen
        Add-Type -AssemblyName System.Drawing
        Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class EmuWin {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
}
'@
        $p = Get-EmuProc
        $wins = New-Object System.Collections.ArrayList
        [EmuWin]::EnumWindows({ param($h, $x) $wpid = 0; [EmuWin]::GetWindowThreadProcessId($h, [ref]$wpid) | Out-Null; if ($wpid -eq $p.Id -and [EmuWin]::IsWindowVisible($h)) { $wins.Add($h) | Out-Null }; $true }, [IntPtr]::Zero) | Out-Null
        Focus-Emu
        $i = 0
        foreach ($h in $wins) {
            $r = New-Object EmuWin+RECT
            [EmuWin]::GetWindowRect($h, [ref]$r) | Out-Null
            $w = $r.R - $r.L; $hh = $r.B - $r.T
            if ($w -lt 50 -or $hh -lt 50) { continue }
            $bmp = New-Object System.Drawing.Bitmap $w, $hh
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CopyFromScreen($r.L, $r.T, 0, 0, $bmp.Size)
            $out = $Arg -replace '\.png$', "_$i.png"
            $bmp.Save($out); $g.Dispose(); $bmp.Dispose()
            $out; $i++
        }
    }
    'post' {
        # send key presses as window messages (works without focus / while locked)
        Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class EmuPost {
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  public static List<IntPtr> Windows(uint pid) {
    var all = new List<IntPtr>();
    EnumWindows((h, p) => { uint q; GetWindowThreadProcessId(h, out q); if (q == pid) { all.Add(h);
      EnumChildWindows(h, (c, pp) => { all.Add(c); return true; }, IntPtr.Zero); } return true; }, IntPtr.Zero);
    return all;
  }
  public static void Key(List<IntPtr> wins, uint vk, bool up) {
    uint sc = MapVirtualKey(vk, 0);
    uint ext = (vk >= 0x21 && vk <= 0x28) ? (1u << 24) : 0u;
    uint l = 1u | (sc << 16) | ext | (up ? 0xC0000000u : 0u);
    foreach (var h in wins) PostMessage(h, up ? 0x101u : 0x100u, (IntPtr)vk, (IntPtr)(int)l);
  }
}
'@
        $p = Get-EmuProc
        $wins = [EmuPost]::Windows([uint32]$p.Id)
        foreach ($tok in ($Arg -split '\s+' | Where-Object { $_ })) {
            if ($tok -match '^wait:(\d+)$') { Start-Sleep -Milliseconds ([int]$Matches[1]); continue }
            $rep = 1; $hold = 100
            if ($tok -match '^(.+?)x(\d+)$' -and $VK.ContainsKey($Matches[1])) { $tok = $Matches[1]; $rep = [int]$Matches[2] }
            if ($tok -match '^(.+):(\d+)$') { $tok = $Matches[1]; $hold = [int]$Matches[2] }
            for ($i = 0; $i -lt $rep; $i++) {
                [EmuPost]::Key($wins, [uint32]$VK[$tok], $false); Start-Sleep -Milliseconds $hold
                [EmuPost]::Key($wins, [uint32]$VK[$tok], $true); Start-Sleep -Milliseconds 150
            }
        }
        "posted to $($wins.Count) windows"
    }
    'printwin' {
        # PrintWindow capture of the largest emulator child window (render widget)
        Add-Type -AssemblyName System.Drawing
        Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class EmuPW {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  public static List<IntPtr> All(uint pid) {
    var all = new List<IntPtr>();
    EnumWindows((h, p) => { uint q; GetWindowThreadProcessId(h, out q); if (q == pid) { all.Add(h);
      EnumChildWindows(h, (c, pp) => { all.Add(c); return true; }, IntPtr.Zero); } return true; }, IntPtr.Zero);
    return all;
  }
}
'@
        $p = Get-EmuProc
        $best = $null; $area = 0
        foreach ($h in [EmuPW]::All([uint32]$p.Id)) {
            $r = New-Object EmuPW+RECT; [EmuPW]::GetClientRect($h, [ref]$r) | Out-Null
            $a = ($r.R - $r.L) * ($r.B - $r.T)
            if ($a -gt $area) { $area = $a; $best = $h; $br = $r }
        }
        $bmp = New-Object System.Drawing.Bitmap ($br.R - $br.L), ($br.B - $br.T)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $hdc = $g.GetHdc()
        [EmuPW]::PrintWindow($best, $hdc, 2) | Out-Null
        $g.ReleaseHdc($hdc); $g.Dispose()
        $bmp.Save($Arg); $bmp.Dispose()
        $Arg
    }
    'snap' {
        # stop (writes the resume state), render both framebuffers from its VRAM, resume
        $resume = Join-Path $Emu 'savestates\SLPS-00829_resume.sav'
        $p = Get-EmuProc
        if ($p) { $p.CloseMainWindow() | Out-Null; $p.WaitForExit(20000) | Out-Null }
        $state = $Arg -replace '\.png$', '.sav'
        Copy-Item $resume $state -Force
        & py -3.11 (Join-Path $PSScriptRoot 'dsstate.py') fb $state $Arg 0 0 320 240 2
        & py -3.11 (Join-Path $PSScriptRoot 'dsstate.py') fb $state ($Arg -replace '\.png$', '_b.png') 0 240 320 240 2
        Start-Process -FilePath $Exe -ArgumentList @('-batch', '-nofullscreen', '-statefile', "`"$((Resolve-Path $state).Path)`"") -WorkingDirectory $Emu | Out-Null
        Start-Sleep -Seconds 4
        $Arg
    }
    'save' { Send-Keys 'F1:200' }
    'load' { Send-Keys 'F3' }
    'stop' { $p = Get-EmuProc; if ($p) { $p.CloseMainWindow() | Out-Null; Start-Sleep 2; if (-not $p.HasExited) { $p | Stop-Process -Force } }; 'stopped' }
    default { throw "unknown command $Cmd" }
}
