$ErrorActionPreference='Stop'
$root=$PSScriptRoot
try {$s=Invoke-RestMethod http://127.0.0.1:8090/api/status -TimeoutSec 2} catch {$s=$null}
if(!$s){
    $p=Start-Process -FilePath "$root\python\python.exe" -ArgumentList @('-u',('"'+$root+'\app.py"')) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput "$root\data\server.out.log" -RedirectStandardError "$root\data\server.err.log"
    $p.Id|Set-Content "$root\data\server.pid"
}
Write-Host 'LocalRSI: http://127.0.0.1:8090'
