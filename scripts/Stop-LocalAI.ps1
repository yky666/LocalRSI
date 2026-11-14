$pidFile = "$PSScriptRoot\logs\server.pid"
if (Test-Path $pidFile) {
    $serverPid = [int](Get-Content $pidFile)
    $p = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if ($p -and $p.Path -like "$PSScriptRoot\runtime\*") { Stop-Process -Id $serverPid }
}
