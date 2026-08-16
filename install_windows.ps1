$ErrorActionPreference = "Stop"

function Find-Python {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        $Resolved = & $PyLauncher.Source -3 -c "import sys; print(sys.executable)"
        if ($LASTEXITCODE -eq 0 -and $Resolved) {
            return $Resolved.Trim()
        }
    }

    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        return $PythonCommand.Source
    }

    throw "Python 3.11 or newer was not found. Install Python from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH'."
}

$Python = Find-Python
& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "mDIR requires Python 3.11 or newer."
}

$InstallRoot = Join-Path $env:LOCALAPPDATA "mDIR"
$VenvRoot = Join-Path $InstallRoot "venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$BinRoot = Join-Path $InstallRoot "bin"
$IconSource = Join-Path $PSScriptRoot "mdir\assets\mdir.ico"
$InstalledIcon = Join-Path $InstallRoot "mdir.ico"

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
New-Item -ItemType Directory -Path $BinRoot -Force | Out-Null

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating the private mDIR environment..."
    & $Python -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the mDIR Python environment."
    }
}

Write-Host "Installing mDIR and preview support..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Could not update pip."
}
& $VenvPython -m pip install --no-cache-dir --force-reinstall "${PSScriptRoot}[preview]"
if ($LASTEXITCODE -ne 0) {
    throw "Could not install mDIR."
}

if (Test-Path -LiteralPath $IconSource) {
    Copy-Item -LiteralPath $IconSource -Destination $InstalledIcon -Force
}

$Launcher = "@echo off`r`n`"$VenvPython`" -m mdir %*`r`n"
Set-Content -LiteralPath (Join-Path $BinRoot "m.cmd") -Value $Launcher -Encoding Ascii
Set-Content -LiteralPath (Join-Path $BinRoot "mdir.cmd") -Value $Launcher -Encoding Ascii

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathParts = @($UserPath -split ";" | Where-Object { $_ })
if (-not ($PathParts | Where-Object { $_.TrimEnd("\") -ieq $BinRoot.TrimEnd("\") })) {
    $NewUserPath = if ($UserPath) { "$UserPath;$BinRoot" } else { $BinRoot }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
}
if (-not (($env:Path -split ";") -contains $BinRoot)) {
    $env:Path = "$BinRoot;$env:Path"
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "mDIR.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $VenvPython
$Shortcut.Arguments = "-m mdir"
$Shortcut.WorkingDirectory = [Environment]::GetFolderPath("UserProfile")
if (Test-Path -LiteralPath $InstalledIcon) {
    $Shortcut.IconLocation = "$InstalledIcon,0"
}
$Shortcut.Description = "mDIR dual-pane file manager"
$Shortcut.Save()

$Version = & $VenvPython -c "import mdir; print(mdir.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "mDIR validation failed after installation."
}

Write-Host ""
Write-Host "mDIR $Version installed successfully." -ForegroundColor Green
Write-Host "Desktop shortcut: $ShortcutPath"
Write-Host "Commands: m, mdir"
Write-Host "If an open terminal does not recognize m, close and reopen it once."
