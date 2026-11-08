<#  Droid Voice installer for Windows (Sushi: RTX 5080, Blender 5.2).
    Run in PowerShell:  powershell -ExecutionPolicy Bypass -File install_sushi.ps1 [-Engines kokoro,espeak,voicebox,dia2,zonos,orpheus,openvoice]
    Every step is separate: one failing engine never stops the others.
    Home: Documents\DeepInDoodles\_voice  (models, engine envs, settings.json, line cache)
    Nothing is installed into Blender's own folders: Kokoro goes into _voice\pydeps.
#>
param(
  [string[]]$Engines = @("kokoro","espeak","voicebox","dia2","zonos","orpheus","openvoice"),
  [string]$Blender = $env:BLENDER_PATH,
  # Optional big drive for engine envs + model downloads (C: on Sushi is nearly full).
  # _voice\engines becomes a junction to <DataRoot>\engines, so every path stays the same.
  [string]$DataRoot = ""
)
$ErrorActionPreference = "Stop"
$Engines = @($Engines | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })   # -File passes "a,b" as one string
$ProgressPreference = "SilentlyContinue"   # PS 5.1 downloads crawl with the progress bar on
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Pkg  = Split-Path -Parent $Here
$Home_ = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "DeepInDoodles\_voice"
New-Item -ItemType Directory -Force -Path $Home_, "$Home_\models", "$Home_\pydeps" | Out-Null
if ($DataRoot) {
  New-Item -ItemType Directory -Force -Path "$DataRoot\engines", "$DataRoot\uv-cache", "$DataRoot\pip-cache" | Out-Null
  $e = Get-Item "$Home_\engines" -ErrorAction SilentlyContinue
  if ($e -and -not $e.LinkType) { if (@(Get-ChildItem $e.FullName -Force).Count) { throw "$Home_\engines already has files; move them to $DataRoot\engines first" }; Remove-Item $e.FullName }
  if (-not (Test-Path "$Home_\engines")) { New-Item -ItemType Junction -Path "$Home_\engines" -Target "$DataRoot\engines" | Out-Null }
  $env:UV_CACHE_DIR = "$DataRoot\uv-cache"; $env:PIP_CACHE_DIR = "$DataRoot\pip-cache"
  # uv-managed Pythons too (a half-written 3.10 under %APPDATA%\uv broke "uv venv")
  $env:UV_PYTHON_INSTALL_DIR = "$DataRoot\uv-python"
}
New-Item -ItemType Directory -Force -Path "$Home_\engines" | Out-Null
# Engine model downloads (Hugging Face) stay inside the engines folder, per runner env only.
$HfHome = "$Home_\engines\_hf"; $env:HF_HOME = $HfHome
$env:UV_LINK_MODE = "copy"
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
# Run a native command and fail the step on a non-zero exit code.
# Retries: PyPI downloads on Sushi drop now and then.
$env:UV_HTTP_TIMEOUT = "300"; $env:UV_HTTP_RETRIES = "10"
function N([scriptblock]$cmd, [int]$tries = 3) {
  for ($i = 1; $i -le $tries; $i++) {
    $global:LASTEXITCODE = 0; & $cmd
    if (-not $LASTEXITCODE) { return }
    Write-Host "attempt $i/$tries failed (exit $LASTEXITCODE): $($cmd.ToString().Trim())" -ForegroundColor DarkYellow
    Start-Sleep -Seconds (10 * $i)
  }
  throw "exit $LASTEXITCODE from: $($cmd.ToString().Trim())"
}
function Need-Git { if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found" } }
# RTX 5080 (Blackwell, sm_120) needs CUDA 12.8 PyTorch wheels.
$TorchIdx = "https://download.pytorch.org/whl/cu128"
function Runner($id, $py, $script, $extraEnv = @{}) {
  Copy-Item "$Pkg\runners\_common.py", "$Pkg\runners\$script" -Destination "$Home_\engines\$id\" -Force
  $env_ = @{ HF_HOME = $HfHome; PYTHONIOENCODING = "utf-8" }; foreach ($k in $extraEnv.Keys) { $env_[$k] = $extraEnv[$k] }
  $S.runners[$id] = @{ cmd = @($py, "$Home_\engines\$id\$script"); env = $env_ }; Save
}
# Every GPU env must see the RTX 5080 (sm_120) through CUDA 12.8 torch.
function Check-Cuda($id, $py) {
  $o = & $py -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
  Write-Host "$id torch: $o"; $Report["$id cuda"] = "$o"
  if ("$o" -notmatch "True") { throw "${id}: CUDA not available ($o)" }
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
  # Use a system install if there is one; otherwise unpack the MSI (admin extract,
  # no elevation needed) into _voice\tools\espeak-ng. Asset is "espeak-ng.msi" since 1.52.
  $exe = "C:\Program Files\eSpeak NG\espeak-ng.exe"
  if (-not (Test-Path $exe)) {
    $t = "$Home_\tools\espeak-ng"
    $exe = Get-ChildItem $t -Recurse -Filter espeak-ng.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if (-not $exe) {
      $rel = Invoke-RestMethod "https://api.github.com/repos/espeak-ng/espeak-ng/releases/latest"
      $msi = $rel.assets | Where-Object { $_.name -match "\.msi$" -and $_.name -notmatch "x86|arm" } | Select-Object -First 1
      Invoke-WebRequest $msi.browser_download_url -OutFile "$env:TEMP\espeak-ng.msi"
      New-Item -ItemType Directory -Force $t | Out-Null
      Start-Process msiexec.exe -Wait -ArgumentList "/a `"$env:TEMP\espeak-ng.msi`" /qn TARGETDIR=`"$t`""
      $exe = Get-ChildItem $t -Recurse -Filter espeak-ng.exe | Select-Object -First 1 -ExpandProperty FullName
      if (-not $exe) { throw "espeak-ng.exe not found after unpacking the MSI" }
    }
  }
  $S["espeak"] = $exe; Save
  $env:ESPEAK_DATA_PATH = Split-Path $exe; & $exe --version; if ($LASTEXITCODE) { throw "espeak-ng --version exited $LASTEXITCODE" }
}}

if ($Engines -contains "voicebox") { Step "voicebox" {
  $exe = Get-ChildItem "$env:LOCALAPPDATA","$env:LOCALAPPDATA\Programs","C:\Program Files" -Filter "voicebox*.exe" -Recurse -Depth 2 -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "setup|uninstall|server|mcp" } | Select-Object -First 1
  if (-not $exe) {
    # NSIS setup installs per user (no admin); the MSI needs an elevated shell.
    $rel = Invoke-RestMethod "https://api.github.com/repos/jamiepine/voicebox/releases/latest"
    $set = $rel.assets | Where-Object { $_.name -match "x64-setup\.exe$" } | Select-Object -First 1
    Invoke-WebRequest $set.browser_download_url -OutFile "$env:TEMP\$($set.name)"
    Start-Process "$env:TEMP\$($set.name)" -Wait -ArgumentList "/S"
    $exe = Get-ChildItem "$env:LOCALAPPDATA","$env:LOCALAPPDATA\Programs" -Filter "voicebox*.exe" -Recurse -Depth 2 -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch "setup|uninstall|server|mcp" } | Select-Object -First 1
    if (-not $exe) { throw "Voicebox installed but its exe wasn't found" }
  }
  $S["voicebox_exe"] = $exe.FullName
  $S["voicebox_url"] = "http://127.0.0.1:17493"; Save
  Write-Host "Open Voicebox once, pick CUDA, and download Qwen3-TTS Voice Design + Chatterbox Turbo in Models."
}}

if ($Engines -contains "dia2") { Step "dia2" { Need-Uv; Need-Git
  $d = "$Home_\engines\dia2"; if (-not (Test-Path "$d\repo")) { git clone --depth 1 https://github.com/nari-labs/dia2 "$d\repo" }
  Push-Location "$d\repo"; try { N { uv sync } } finally { Pop-Location }
  Check-Cuda "dia2" "$d\repo\.venv\Scripts\python.exe"
  Runner "dia2" "$d\repo\.venv\Scripts\python.exe" "dia2_run.py"
}}

if ($Engines -contains "zonos") { Step "zonos" { Need-Uv; Need-Git
  $d = "$Home_\engines\zonos"; if (-not (Test-Path "$d\repo")) { git clone --depth 1 https://github.com/Zyphra/Zonos "$d\repo" }
  if (-not (Test-Path "$d\venv\Scripts\python.exe")) { N { uv venv "$d\venv" --python 3.11 } }
  N { uv pip install --python "$d\venv\Scripts\python.exe" torch torchaudio --index-url $TorchIdx }
  N { uv pip install --python "$d\venv\Scripts\python.exe" -e "$d\repo" }
  # Zonos phonemises with eSpeak NG
  $dll = if ($S["espeak"] -and (Test-Path $S["espeak"])) { Join-Path (Split-Path $S["espeak"]) "libespeak-ng.dll" } else { "C:\Program Files\eSpeak NG\libespeak-ng.dll" }
  Check-Cuda "zonos" "$d\venv\Scripts\python.exe"
  Runner "zonos" "$d\venv\Scripts\python.exe" "zonos_run.py" @{ PHONEMIZER_ESPEAK_LIBRARY = $dll; PHONEMIZER_ESPEAK_PATH = (Split-Path $dll); ESPEAK_DATA_PATH = (Split-Path $dll) }
}}

if ($Engines -contains "orpheus") { Step "orpheus" { Need-Uv
  $d = "$Home_\engines\orpheus"; New-Item -ItemType Directory -Force $d | Out-Null
  if (-not (Test-Path "$d\venv\Scripts\python.exe")) { N { uv venv "$d\venv" --python 3.11 } }
  N { uv pip install --python "$d\venv\Scripts\python.exe" torch --index-url $TorchIdx }
  N { uv pip install --python "$d\venv\Scripts\python.exe" transformers accelerate snac numpy huggingface_hub }
  Check-Cuda "orpheus" "$d\venv\Scripts\python.exe"
  Runner "orpheus" "$d\venv\Scripts\python.exe" "orpheus_run.py"
  Write-Host "Orpheus is gated: accept the licence at huggingface.co/canopylabs/orpheus-3b-0.1-ft and run  $d\venv\Scripts\hf.exe auth login"
}}

if ($Engines -contains "openvoice") { Step "openvoice" { Need-Uv; Need-Git
  $d = "$Home_\engines\openvoice"; if (-not (Test-Path "$d\repo")) { git clone --depth 1 https://github.com/myshell-ai/OpenVoice "$d\repo" }
  if (-not (Test-Path "$d\venv\Scripts\python.exe")) { N { uv venv "$d\venv" --python 3.10 } }
  N { uv pip install --python "$d\venv\Scripts\python.exe" torch torchaudio --index-url $TorchIdx }
  N { uv pip install --python "$d\venv\Scripts\python.exe" -e "$d\repo" "git+https://github.com/myshell-ai/MeloTTS.git" }
  N { & "$d\venv\Scripts\python.exe" -m unidic download }
  if (-not (Test-Path "$d\checkpoints_v2")) {
    Invoke-WebRequest "https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip" -OutFile "$env:TEMP\ov2.zip"
    Expand-Archive "$env:TEMP\ov2.zip" -DestinationPath $d -Force
  }
  Check-Cuda "openvoice" "$d\venv\Scripts\python.exe"
  Runner "openvoice" "$d\venv\Scripts\python.exe" "openvoice_run.py" @{ OPENVOICE_CKPT = $d }
}}

Write-Host "`n=== Droid Voice install report ===" -ForegroundColor Yellow
$Report.GetEnumerator() | ForEach-Object { "{0,-20} {1}" -f $_.Key, $_.Value }
$Report | ConvertTo-Json | Set-Content -Encoding UTF8 "$Home_\install_report.json"
