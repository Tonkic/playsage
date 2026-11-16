param([switch]$RequestElevation, [int]$ReplacePid = 0, [string]$BuildDirectory = 'bin')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($BuildDirectory -notmatch '^bin(?:-[a-z0-9]+)?$') { throw 'Invalid build directory' }
$hostPath = Join-Path $projectRoot ('runs\services\child-session\' + $BuildDirectory + '\PlaySage.ChildSession.exe')
if (-not (Test-Path -LiteralPath $hostPath -PathType Leaf)) { throw 'Build tools/child-session first.' }
if ($ReplacePid) {
    $old = Get-Process -Id $ReplacePid -ErrorAction Stop
    $allowedRoot = Join-Path $projectRoot 'runs\services\child-session\'
    if ($old.ProcessName -notin @('PlaySage.ChildSession', 'QuestWeaver.ChildSession') -or -not $old.Path.StartsWith($allowedRoot)) { throw 'Host identity changed' }
    Stop-Process -InputObject $old -ErrorAction Stop
    $old.WaitForExit(5000) | Out-Null
}
$existing = Get-Process PlaySage.ChildSession, QuestWeaver.ChildSession -ErrorAction SilentlyContinue
if ($existing) { throw 'A child-session viewer is already running; inspect its status before starting another.' }
$parameters = @{FilePath=$hostPath; ArgumentList=('"' + $projectRoot + '"'); WindowStyle='Normal'; PassThru=$true}
if ($RequestElevation) { $parameters.Verb = 'RunAs' }
Start-Process @parameters | Select-Object Id, ProcessName
