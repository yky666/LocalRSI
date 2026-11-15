param([string]$CredentialFile=(Join-Path $PSScriptRoot 'data\hosted-credentials.clixml'))
$ErrorActionPreference='Stop'
$pidFile=Join-Path $PSScriptRoot 'data\hosted-bridge.pid'
if(Test-Path -LiteralPath $pidFile){
    $existing=Get-CimInstance Win32_Process -Filter "ProcessId = $([int](Get-Content -LiteralPath $pidFile))" -ErrorAction SilentlyContinue
    if($existing -and $existing.CommandLine -like '*hosted_bridge.py*'){Write-Host 'Hosted bridge already running';exit}
}
$secure=Import-Clixml -LiteralPath $CredentialFile
$credentials=([Net.NetworkCredential]::new('', $secure)).Password | ConvertFrom-Json
$env:LOCALRSI_SITE=$credentials.site
$env:LOCALRSI_BRIDGE_KEY=$credentials.bridge_key
$env:LOCALRSI_SITE_KEY=$credentials.site_key
$env:LOCALRSI_CONFIG=Join-Path $PSScriptRoot 'data\hosted-config.json'
try {
    $p=Start-Process "$PSScriptRoot\python\python.exe" -ArgumentList @('-u',('"'+$PSScriptRoot+'\hosted_bridge.py"')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\data\hosted-bridge.out.log" -RedirectStandardError "$PSScriptRoot\data\hosted-bridge.err.log" -PassThru
    $p.Id | Set-Content -LiteralPath $pidFile
    Write-Host "Hosted bridge running (PID $($p.Id))"
} finally {
    Remove-Item Env:LOCALRSI_BRIDGE_KEY,Env:LOCALRSI_SITE_KEY,Env:LOCALRSI_SITE,Env:LOCALRSI_CONFIG -ErrorAction SilentlyContinue
    $credentials=$null
}
