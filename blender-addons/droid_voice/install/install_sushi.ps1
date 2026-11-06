<#  Droid Voice installer for Windows (Sushi: RTX 5080, Blender 5.2).
    Run in PowerShell:  powershell -ExecutionPolicy Bypass -File install_sushi.ps1 [-Engines kokoro,espeak,voicebox,dia2,zonos,orpheus,openvoice]
    Every step is separate: one failing engine never stops the others.
    Home: Documents\DeepInDoodles\_voice  (models, engine envs, settings.json, line cache)
    Nothing is installed into Blender's own folders: Kokoro goes into _voice\pydeps.
#>
param(
  [string[]]$Engines = @("kokoro","espeak","voicebox","dia2","zonos","orpheus","openvoice"),
  [string]$Blender = $env:BLENDER_PATH
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pkg  = Split-Path -Parent $Here
$Home_ = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "DeepInDoodles\_voice"
New-Item -ItemType Directory -Force -Path $Home_, "$Home_\engines", "$Home_\models", "$Home_\pydeps" | Out-Null
$SettingsPath = "$Home_\settings.json"
function ToHash($o) { if ($o -is [System.Management.Automation.PSCustomObject]) { $h = @{}; foreach ($p in $o.PSObject.Properties) { $h[$p.Name] = ToHash $p.Value }; return $h } return $o }
$S = if (Test-Path $SettingsPath) { ToHash (Get-Content $SettingsPath -Raw | ConvertFrom-Json) } else { @{} }
if (-not $S.ContainsKey("runners")) { $S["runners"] = @{} }
$Report = [ordered]@{}
function Save { $S | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $SettingsPath }
function Step($name, [scriptblock]$body) {
  Write-Host "`n=== $name ===" -ForegroundColor Yellow
  try { & $body; $Report[$name] = "ok" } catch { $Report[$name] = "FAILED: $($_.Exception.Message)"; Write-Host $Report[$name] -ForegroundColor Red }
}
function Need-Uv { if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"; $env:Path = "$env:USERPROFILE\.local\bin;$env:Path" } }
function Need-Git { if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found" } }
# RTX 5080 (Blackwell, sm_120) needs CUDA 12.8 PyTorch wheels.
$TorchIdx = "https://download.pytorch.org/whl/cu128"
function Runner($id, $py, $script) {
  Copy-Item "$Pkg\runners\_common.py", "$Pkg\runners\$script" -Destination "$Home_\engines\$id\" -Force
  $S.runners[$id] = @{ cmd = @($py, "$Home_\engines\$id\$script") }; Save
}

if (-not $Blender) { $Blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" }
$BlenderPy = Get-ChildItem (Split-Path $Blender) -Recurse -Filter python.exe -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "\\python\\bin\\python.exe$" } | Select-Object -First 1 -ExpandProperty FullName

if ($Engines -contains "kokoro") { Step "kokoro (built in)" {
  if (-not $BlenderPy) { throw "Blender's python.exe not found next to $Blender" }
  & $BlenderPy -m pip install --upgrade --target "$Home_\pydeps" kokoro-onnx
  if ($LASTEXITCODE) { throw "pip failed" }
  $base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
  foreach ($f in "kokoro-v1.0.int8.onnx","voices-v1.0.bin") { if (-not (Test-Path "$Home_\models\$f")) { Invoke-WebRequest "$base/$f" -OutFile "$Home_\models\$f" } }
}}

if ($Engines -contains "espeak") { Step "espeak-ng" {
  if (-not (Test-Path "C:\Program Files\eSpeak NG\espeak-ng.exe")) {
    $rel = Invoke-RestMethod "https://api.github.com/repos/espeak-ng/espeak-ng/releases/latest"
    $msi = $rel.assets | Where-Object { $_.name -match "x64\.msi$" } | Select-Object -First 1
    Invoke-WebRequest $msi.browser_download_url -OutFile "$env:TEMP\espeak-ng.msi"
    Start-Process msiexec.exe -Wait -ArgumentList "/i `"$env:TEMP\espeak-ng.msi`" /qn"
  }
  $S["espeak"] = "C:\Program Files\eSpeak NG\espeak-ng.exe"; Save
}}

if ($Engines -contains "voicebox") { Step "voicebox" {
  $exe = Get-ChildItem "$env:LOCALAPPDATA\Programs","C:\Program Files" -Recurse -Filter "voicebox*.exe" -Depth 3 -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $exe) {
    $rel = Invoke-RestMethod "https://api.github.com/repos/jamiepine/voicebox/releases/latest"
    $msi = $rel.assets | Where-Object { $_.name -match "\.msi$" -and $_.name -notmatch "arm" } | Select-Object -First 1
    Invoke-WebRequest $msi.browser_download_url -OutFile "$env:TEMP\$($msi.name)"
    Start-Process msiexec.exe -Wait -ArgumentList "/i `"$env:TEMP\$($msi.name)`" /qn"
  }
  $S["voicebox_url"] = "http://127.0.0.1:17493"; Save
  Write-Host "Open Voicebox once, pick CUDA, and download Qwen3-TTS Voice Design + Chatterbox Turbo in Models."
}}

if ($Engines -contains "dia2") { Step "dia2" { Need-Uv; Need-Git
  $d = "$Home_\engines\dia2"; if (-not (Test-Path "$d\repo")) { git clone --depth 1 https://github.com/nari-labs/dia2 "$d\repo" }
  Push-Location "$d\repo"; uv sync; Pop-Location
  Runner "dia2" "$d\repo\.venv\Scripts\python.exe" "dia2_run.py"
}}

if ($Engines -contains "zonos") { Step "zonos" { Need-Uv; Need-Git
  $d = "$Home_\engines\zonos"; if (-not (Test-Path "$d\repo")) { git clone --depth 1 https://github.com/Zyphra/Zonos "$d\repo" }
  uv venv "$d\venv" --python 3.11
  uv pip install --python "$d\venv\Scripts\python.exe" torch torchaudio --index-url $TorchIdx
  uv pip install --python "$d\venv\Scripts\python.exe" -e "$d\repo" --no-build-isolation
  # Zonos phonemises with eSpeak NG
  [Environment]::SetEnvironmentVariable("PHONEMIZER_ESPEAK_LIBRARY", "C:\Program Files\eSpeak NG\libespeak-ng.dll", "User")
  Runner "zonos" "$d\venv\Scripts\python.exe" "zonos_run.py"
}}

if ($Engines -contains "orpheus") { Step "orpheus" { Need-Uv
  $d = "$Home_\engines\orpheus"; New-Item -ItemType Directory -Force $d | Out-Null
  uv venv "$d\venv" --python 3.11
  uv pip install --python "$d\venv\Scripts\python.exe" torch --index-url $TorchIdx
  uv pip install --python "$d\venv\Scripts\python.exe" transformers accelerate snac numpy huggingface_hub
  Runner "orpheus" "$d\venv\Scripts\python.exe" "orpheus_run.py"
  Write-Host "Orpheus is gated: accept the licence at huggingface.co/canopylabs/orpheus-3b-0.1-ft and run  $d\venv\Scripts\hf.exe auth login"
}}

if ($Engines -contains "openvoice") { Step "openvoice" { Need-Uv; Need-Git
  $d = "$Home_\engines\openvoice"; if (-not (Test-Path "$d\repo")) { git clone --depth 1 https://github.com/myshell-ai/OpenVoice "$d\repo" }
  uv venv "$d\venv" --python 3.10
  uv pip install --python "$d\venv\Scripts\python.exe" torch torchaudio --index-url $TorchIdx
  uv pip install --python "$d\venv\Scripts\python.exe" -e "$d\repo" "git+https://github.com/myshell-ai/MeloTTS.git"
  & "$d\venv\Scripts\python.exe" -m unidic download
  if (-not (Test-Path "$d\checkpoints_v2")) {
    Invoke-WebRequest "https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip" -OutFile "$env:TEMP\ov2.zip"
    Expand-Archive "$env:TEMP\ov2.zip" -DestinationPath $d -Force
  }
  [Environment]::SetEnvironmentVariable("OPENVOICE_CKPT", $d, "User")
  Runner "openvoice" "$d\venv\Scripts\python.exe" "openvoice_run.py"
}}

Write-Host "`n=== Droid Voice install report ===" -ForegroundColor Yellow
$Report.GetEnumerator() | ForEach-Object { "{0,-20} {1}" -f $_.Key, $_.Value }
$Report | ConvertTo-Json | Set-Content -Encoding UTF8 "$Home_\install_report.json"
