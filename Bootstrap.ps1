$ErrorActionPreference='Stop'
$root=$PSScriptRoot
New-Item -ItemType Directory -Force "$root\data","$root\workspace","$root\python" | Out-Null
if(!(Test-Path "$root\python\python.exe")){
    Invoke-WebRequest https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip -OutFile "$root\data\python.zip"
    Expand-Archive "$root\data\python.zip" "$root\python" -Force
    Add-Content "$root\python\python312._pth" 'Lib\site-packages'
    Add-Content "$root\python\python312._pth" '..'
    Add-Content "$root\python\python312._pth" 'import site'
}
& "$root\python\python.exe" -m pip --version 2>$null
if($LASTEXITCODE){Invoke-WebRequest https://bootstrap.pypa.io/get-pip.py -OutFile "$root\data\get-pip.py"; & "$root\python\python.exe" "$root\data\get-pip.py"}
& "$root\python\python.exe" -m pip install --no-warn-script-location setuptools wheel
& "$root\python\python.exe" -m pip install --no-build-isolation --no-warn-script-location -r "$root\requirements.txt"
if($LASTEXITCODE){throw 'Dependency installation failed'}
& "$root\python\python.exe" "$root\scripts\bootstrap_models.py"
if($LASTEXITCODE){throw 'Model setup failed'}
Write-Host 'Run Start-GUI.cmd. Run Setup-Extras.ps1 for offline audio and embedding downloads.'
