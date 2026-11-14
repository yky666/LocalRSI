$file="$PSScriptRoot\data\server.pid"
if(Test-Path $file){
    $serverPid=[int](Get-Content $file)
    $p=Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if($p -and $p.Path -eq "$PSScriptRoot\python\python.exe"){Stop-Process -Id $serverPid}
}
