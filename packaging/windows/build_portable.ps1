param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path

Push-Location $root
try {
    $version = & $Python -c "import sys; sys.path.insert(0, r'$root'); import mdir; print(mdir.__version__)"
    if ($LASTEXITCODE -ne 0 -or -not $version) {
        throw "Could not read the mDIR version."
    }
    $version = $version.Trim()

    $work = Join-Path $root "build\portable"
    $dist = Join-Path $root "dist"
    $stage = Join-Path $work "mDIR-P-$version-win64"
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    New-Item -ItemType Directory -Force $work, $dist, $stage | Out-Null

    & $Python -m pip install --upgrade pyinstaller ".[preview]"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install the portable-build dependencies."
    }

    & $Python -m PyInstaller --noconfirm --clean --onefile --name mDIR --icon "$root\mdir\assets\mdir.ico" --collect-all textual --collect-all mdir "$root\mdir\__main__.py"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    Copy-Item "$root\dist\mDIR.exe", "$root\LICENSE", "$root\README.md" $stage
    $archive = Join-Path $dist "mDIR-P-$version-win64.zip"
    Compress-Archive -Path "$stage\*" -DestinationPath $archive -Force
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash
    Set-Content -Encoding ascii "$archive.sha256" "$hash  $(Split-Path $archive -Leaf)"
    Write-Host "Built $archive"
    Write-Host "SHA256 $hash"
}
finally {
    Pop-Location
}
