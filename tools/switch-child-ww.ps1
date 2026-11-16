param([Parameter(Mandatory=$true)][int]$SessionId, [ValidateSet('Switch','Backend')][string]$Mode = 'Switch')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logRoot = Join-Path $projectRoot 'runs\services\okww'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
try {
    $actualSession = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
    if ($actualSession -ne $SessionId -or $SessionId -le 1) { throw 'Child session mismatch' }
    $appRoot = 'C:\Users\23614\AppData\Local\ok-ww\data\apps\ok-ww'
    $pythonPath = Join-Path $appRoot 'python\python.exe'
    $workingRoot = Join-Path $appRoot 'working'
    $gamePath = 'D:\Wuthering Waves Game\Wuthering Waves.exe'
    foreach ($required in @($pythonPath, $gamePath, (Join-Path $workingRoot 'ok\core\mcp_server.py'))) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Required file unavailable in child session: $required" }
    }
    if (Get-NetTCPConnection -LocalPort 23003 -State Listen -ErrorAction SilentlyContinue) { throw '23003 already occupied' }
    if ($Mode -eq 'Switch') {
        if (Get-Process -Name 'Client-Win64-Shipping' -ErrorAction SilentlyContinue) { throw 'Wuthering Waves already running; inspect before switching' }
        $oldMetadata = Get-Content -LiteralPath (Join-Path $projectRoot 'runs\services\child-session\backend.json') -Raw | ConvertFrom-Json
        if ($oldMetadata.session_id -ne $SessionId) { throw 'OneDragon metadata belongs to another session' }
        $oldBackend = Get-Process -Id $oldMetadata.pid -ErrorAction SilentlyContinue
        if ($oldBackend) {
            $expectedPython = Join-Path $projectRoot 'third_party\OneDragon\.runtime\cpython-3.11.15\python.exe'
            if ($oldBackend.SessionId -ne $SessionId -or $oldBackend.Path -ne $expectedPython) { throw 'OneDragon process identity mismatch' }
            Stop-Process -InputObject $oldBackend -ErrorAction Stop
            if (-not $oldBackend.WaitForExit(5000)) { throw 'OneDragon did not exit' }
        }
        foreach ($game in @(Get-Process -Name 'ZenlessZoneZero' -ErrorAction SilentlyContinue)) {
            # The protected game can withhold its path. Check the explicitly
            # requested name and session, plus its path when Windows exposes it.
            if ($game.SessionId -ne $SessionId -or ($game.Path -and $game.Path -ne 'D:\ZenlessZoneZero Game\ZenlessZoneZero.exe')) { throw "ZZZ identity mismatch: session=$($game.SessionId), path=$($game.Path)" }
            $null = $game.CloseMainWindow()
            if (-not $game.WaitForExit(5000)) {
                Stop-Process -InputObject $game -ErrorAction Stop
                if (-not $game.WaitForExit(5000)) { throw 'ZZZ did not exit' }
            }
        }
    }
    $env:PYTHONUTF8 = '1'
    $env:PLAYSAGE_CHILD_SESSION_ID = [string]$SessionId
    # Compatibility for already installed native tasks during the rename.
    $env:QUESTWEAVER_CHILD_SESSION_ID = $env:PLAYSAGE_CHILD_SESSION_ID
    $backend = Start-Process -FilePath $pythonPath -WorkingDirectory $workingRoot -WindowStyle Hidden -PassThru -ArgumentList @('-m','ok','mcp','--config','config:config','--port','23003') -RedirectStandardOutput (Join-Path $logRoot 'stdout.log') -RedirectStandardError (Join-Path $logRoot 'stderr.log')
    $game = $null
    if ($Mode -eq 'Switch') {
        $game = Start-Process -FilePath $gamePath -WorkingDirectory (Split-Path -Parent $gamePath) -WindowStyle Hidden -PassThru
    }
    $launcherPid = if ($null -ne $game) { $game.Id } else { $null }
    @{session_id=$SessionId; backend_pid=$backend.Id; game_launcher_pid=$launcherPid; project=$workingRoot; python=$pythonPath; started_at=[DateTimeOffset]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot 'launch.json') -Encoding UTF8
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $logRoot 'launch-error.log') -Encoding UTF8
    throw
}
