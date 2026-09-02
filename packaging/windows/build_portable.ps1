param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$version = & $Python -c "import sys; sys.path.insert(0, r'$root'); import mdir; print(mdir.__version__)"
$work = Join-Path $root "build\portable"
$dist = Join-Path $root "dist"
New-Item -ItemType Directory -Force $work, $dist | Out-Null
& $Python -m pip install --upgrade pyinstaller ".[preview]"
& $Python -m PyInstaller --noconfirm --clean --onefile --name mDIR --icon "$root\mdir\assets\mdir.ico" --collect-all textual --collect-all mdir "$root\mdir\__main__.py"
$stage = Join-Path $work "mDIR-P-$version-win64"
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item "$root\dist\mDIR.exe", "$root\LICENSE", "$root\README.md" $stage
$archive = Join-Path $dist "mDIR-P-$version-win64.zip"
Compress-Archive -Path "$stage\*" -DestinationPath $archive -Force
$hash = (Get-FileHash $archive -Algorithm SHA256).Hash
Set-Content -Encoding ascii "$archive.sha256" "$hash  $(Split-Path $archive -Leaf)"
Write-Host "Built $archive"
Write-Host "SHA256 $hash"

