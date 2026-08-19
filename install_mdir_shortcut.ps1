$ErrorActionPreference = "Stop"

$PrivatePython = Join-Path $env:LOCALAPPDATA "mDIR\venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $PrivatePython) {
    $PrivatePython
} else {
    (Get-Command python -ErrorAction Stop).Source
}
$IconSource = Join-Path $PSScriptRoot "mdir\assets\mdir.ico"
if (-not (Test-Path -LiteralPath $IconSource)) {
    throw "mDIR icon not found: $IconSource"
}

$InstallFolder = Join-Path $env:LOCALAPPDATA "mDIR"
$InstalledIcon = Join-Path $InstallFolder "mdir.ico"
New-Item -ItemType Directory -Path $InstallFolder -Force | Out-Null
Copy-Item -LiteralPath $IconSource -Destination $InstalledIcon -Force

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "mDIR.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Python
$Shortcut.Arguments = "-P -m mdir"
$Shortcut.WorkingDirectory = [Environment]::GetFolderPath("UserProfile")
$Shortcut.IconLocation = "$InstalledIcon,0"
$Shortcut.Description = "mDIR dual-pane file manager"
$Shortcut.Save()

Write-Host "Created mDIR desktop shortcut: $ShortcutPath"
