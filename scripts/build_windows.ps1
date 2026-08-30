$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "This build script must run on Windows. PyInstaller does not cross-build Windows executables."
}

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "[1/4] Running tests..."
python -m pytest -q

Write-Host "[2/4] Checking build dependencies..."
python -c "import PyInstaller, PySide6; print('PyInstaller/PySide6 ready')"

$Ffmpeg = Join-Path $Root "vendor\ffmpeg\ffmpeg.exe"
$Ffprobe = Join-Path $Root "vendor\ffmpeg\ffprobe.exe"
if (-not (Test-Path $Ffmpeg) -or -not (Test-Path $Ffprobe)) {
    throw "Place ffmpeg.exe and ffprobe.exe in vendor\ffmpeg before building a self-contained release."
}

Write-Host "[3/4] Building VoiceDatasetBuilder..."
python -m PyInstaller --noconfirm --clean VoiceDatasetBuilder.spec

$Dist = Join-Path $Root "dist\VoiceDatasetBuilder"
$Bin = Join-Path $Dist "bin"
New-Item -ItemType Directory -Force $Bin | Out-Null
Copy-Item $Ffmpeg (Join-Path $Bin "ffmpeg.exe") -Force
Copy-Item $Ffprobe (Join-Path $Bin "ffprobe.exe") -Force

$Exe = Join-Path $Dist "VoiceDatasetBuilder.exe"
if (-not (Test-Path $Exe)) {
    throw "Build finished without producing $Exe"
}
Write-Host "[4/4] Ready: $Exe"
