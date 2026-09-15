$ErrorActionPreference = "Stop"
Push-Location -LiteralPath $PSScriptRoot
$PreviousTitle = $Host.UI.RawUI.WindowTitle
try {
    $Host.UI.RawUI.WindowTitle = "mDIR"
    $MdirPython = Join-Path $env:LOCALAPPDATA 'mDIR\venv\Scripts\python.exe'
    $SourcePython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $SourcePython) {
        $MdirPython = $SourcePython
    }
    elseif (-not (Test-Path -LiteralPath $MdirPython)) {
        $MdirPython = (Get-Command python -ErrorAction Stop).Source
    }
    & $MdirPython -c 'import textual, PIL, tkinter'
    if ($LASTEXITCODE -ne 0) {
        throw 'mDIR dependencies are missing. Run INSTALL_MDIR.bat once, then start again.'
    }
    & $MdirPython -m mdir @args
}
finally {
    $Host.UI.RawUI.WindowTitle = $PreviousTitle
    Pop-Location
}
