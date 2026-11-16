param([switch]$RequestElevation)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'third_party\OneDragon'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Run uv sync --group dev inside third_party\OneDragon first.'
}
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    if (-not $RequestElevation) { throw 'Game input requires an administrator backend. Use -RequestElevation and confirm Windows UAC manually.' }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -WindowStyle Hidden -ArgumentList @('-NoProfile', '-File', ('"' + $PSCommandPath + '"'))
    return
}
if (Get-NetTCPConnection -LocalPort 23001 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 23001 already has a listener. Stop the existing backend before starting another.'
}
$logRoot = Join-Path $projectRoot 'runs\services\onedragon'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$env:PYTHONPATH = Join-Path $backendRoot 'src'
$env:PYTHONUTF8 = '1'
$backendProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -ArgumentList @('-m', 'zzz_od.backend.entry.server', '--host', '127.0.0.1', '--port', '23001') -RedirectStandardOutput (Join-Path $logRoot 'stdout.log') -RedirectStandardError (Join-Path $logRoot 'stderr.log')
@{ pid = $backendProcess.Id; endpoint = 'http://127.0.0.1:23001/mcp'; elevated = $true; started_at = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot 'service.json') -Encoding UTF8
