$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$server = Get-ChildItem "$root\runtime" -Filter llama-server.exe -Recurse | Select-Object -First 1
$model = "$root\models\Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
if (!$server -or !(Test-Path $model)) { throw 'Runtime or model download is not complete.' }
try { $health = Invoke-RestMethod 'http://127.0.0.1:8088/health' -TimeoutSec 2 } catch { $health = $null }
if ($health.status -eq 'ok') { Write-Host 'Service already running: http://127.0.0.1:8088'; exit }
$arguments = @('-m', ('"' + $model + '"'), '--host','127.0.0.1','--port','8088','-c','4096','-t','6','-b','256','-ub','128','-ngl','0','-np','1','--jinja','--alias','local-agent-4b')
$process = Start-Process -FilePath $server.FullName -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput "$root\logs\server.out.log" -RedirectStandardError "$root\logs\server.err.log"
$process.Id | Set-Content "$root\logs\server.pid"
Write-Host 'Starting local AI: http://127.0.0.1:8088'
