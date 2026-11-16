param([Parameter(Mandatory=$true)][int]$SessionId, [ValidateSet('probe','backend')][string]$Mode)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logRoot = Join-Path $projectRoot 'runs\services\child-session'
$actualSession = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
if ($actualSession -ne $SessionId -or $actualSession -le 1) { throw 'Session mismatch' }
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
@{pid=$PID; session_id=$actualSession; mode=$Mode} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot ($Mode + '.launcher.json')) -Encoding UTF8
try {
    $pythonPath = Join-Path $projectRoot 'third_party\OneDragon\.runtime\cpython-3.11.15\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw 'Base interpreter not found' }
    if ($Mode -eq 'backend' -and (Get-NetTCPConnection -LocalPort 23002 -State Listen -ErrorAction SilentlyContinue)) { throw 'Port 23002 is already occupied' }
    $scriptPath = Join-Path $projectRoot 'tools\child_session_bootstrap.py'
    $env:PYTHONUTF8 = '1'
    $child = Start-Process -FilePath $pythonPath -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -ArgumentList @(('"' + $scriptPath + '"'),'--session',$SessionId,'--mode',$Mode) -RedirectStandardOutput (Join-Path $logRoot ($Mode + '.launcher.stdout.log')) -RedirectStandardError (Join-Path $logRoot ($Mode + '.launcher.stderr.log'))
    $child.WaitForExit()
    @{pid=$child.Id; exit_code=$child.ExitCode; session_id=$actualSession} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot ($Mode + '.exit.json')) -Encoding UTF8
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $logRoot ($Mode + '.launcher.error.log')) -Encoding UTF8
    throw
}
