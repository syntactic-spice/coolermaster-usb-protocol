# Elevated capture helper. Run once as admin; it then starts/stops USBPcapCMD
# on request so captures don't each need a UAC prompt.
#
# Control files in <repo>\_ctl\ (written by tools\cap.ps1):
#   start  -> contains the capture label; starts a capture to captures\<label>.pcap
#   stop   -> stops the running capture
#   quit   -> stops any capture and exits
# Status is reported in _ctl\status.
param(
    [string]$Hub = '\\.\USBPcap2',
    [string]$Devices = '1',
    [string]$USBPcap = 'C:\Program Files\USBPcap\USBPcapCMD.exe'
)
$repo = Split-Path -Parent $PSScriptRoot
$ctl = Join-Path $repo '_ctl'
$out = Join-Path $repo 'captures'
New-Item -ItemType Directory -Force $ctl, $out | Out-Null
Remove-Item "$ctl\*" -ErrorAction SilentlyContinue
function Status($s) { Set-Content -Path "$ctl\status" -Value $s }

$proc = $null
Status 'idle'
while ($true) {
    if (Test-Path "$ctl\start") {
        # Request: "<label> [<hub number> <devices|all>]"
        $req = (Get-Content "$ctl\start" -Raw).Trim() -split '\s+'
        Remove-Item "$ctl\start"
        $label = $req[0]
        if ($label -notmatch '^[A-Za-z0-9_.-]{1,100}$') { Status "error: bad label '$label'"; continue }
        $hubArg = $Hub; $devArgs = @('--devices', $Devices)
        if ($req.Count -ge 3) {
            if ($req[1] -notmatch '^[1-9]$' -or $req[2] -notmatch '^(all|[0-9]{1,3}(,[0-9]{1,3})*)$') { Status 'error: bad hub/devices'; continue }
            $hubArg = "\\.\USBPcap$($req[1])"
            $devArgs = if ($req[2] -eq 'all') { @('-A') } else { @('--devices', $req[2]) }
        }
        if ($proc -and -not $proc.HasExited) { Status 'error: capture already running'; continue }
        $file = Join-Path $out "$label.pcap"
        $proc = Start-Process -FilePath $USBPcap -PassThru -WindowStyle Hidden -ArgumentList (@(
            '-d', $hubArg) + $devArgs + @('--inject-descriptors', '-o', "`"$file`""))
        Start-Sleep -Milliseconds 500
        if ($proc.HasExited) { Status "error: USBPcapCMD exited ($($proc.ExitCode))" } else { Status "capturing $label" }
    }
    if ((Test-Path "$ctl\stop") -or (Test-Path "$ctl\quit")) {
        Remove-Item "$ctl\stop" -ErrorAction SilentlyContinue
        if ($proc -and -not $proc.HasExited) {
            Start-Sleep -Milliseconds 500   # let trailing packets land
            Stop-Process -Id $proc.Id -Force
            $proc.WaitForExit()
        }
        $proc = $null
        Status 'idle'
        if (Test-Path "$ctl\quit") { Remove-Item "$ctl\quit"; Status 'exited'; break }
    }
    Start-Sleep -Milliseconds 100
}
