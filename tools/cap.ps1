# Client for capture_server.ps1.
#   cap.ps1 start <label> [-Hub N -Devices <list|all>]   cap.ps1 stop   cap.ps1 status   cap.ps1 quit
# Hub/Devices default to $env:MM712_CAP_HUB / $env:MM712_CAP_DEVICES, else the server's defaults.
param([Parameter(Mandatory)][ValidateSet('start', 'stop', 'status', 'quit')][string]$Cmd, [string]$Label,
      [string]$Hub = $env:MM712_CAP_HUB, [string]$Devices = $env:MM712_CAP_DEVICES)
if ($Cmd -eq 'start' -and $Hub -and $Devices) { $Label = "$Label $Hub $Devices" }
$ctl = Join-Path (Split-Path -Parent $PSScriptRoot) '_ctl'
function Wait-Status($pattern) {
    for ($i = 0; $i -lt 50; $i++) {
        $s = Get-Content "$ctl\status" -ErrorAction SilentlyContinue
        if ($s -match $pattern) { return $s }
        Start-Sleep -Milliseconds 100
    }
    return "timeout; status: $(Get-Content "$ctl\status" -ErrorAction SilentlyContinue)"
}
switch ($Cmd) {
    'start'  { Set-Content "$ctl\start" $Label; Wait-Status '^(capturing|error)' }
    'stop'   { Set-Content "$ctl\stop" '';     Wait-Status '^(idle|error)' }
    'quit'   { Set-Content "$ctl\quit" '';     Wait-Status '^exited' }
    'status' { Get-Content "$ctl\status" -ErrorAction SilentlyContinue }
}
