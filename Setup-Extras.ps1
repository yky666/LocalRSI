$ErrorActionPreference='Stop'
$root=$PSScriptRoot
& "$root\python\python.exe" -m pip install --no-warn-script-location -r "$root\requirements.txt"
if($LASTEXITCODE){throw 'Dependency installation failed'}
$zip="$root\data\vosk-model.zip"
if(!(Test-Path "$root\data\vosk-model-small-cn-0.22")){
    Invoke-WebRequest https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip -OutFile $zip
    Expand-Archive $zip "$root\data" -Force
}
& "$root\python\python.exe" -c "import features; print(features.embedding_model())"
