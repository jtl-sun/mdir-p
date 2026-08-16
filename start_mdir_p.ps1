$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$PreviousTitle = $Host.UI.RawUI.WindowTitle
try {
    $Host.UI.RawUI.WindowTitle = "mDIR"
    python -m mdir @args
}
finally {
    $Host.UI.RawUI.WindowTitle = $PreviousTitle
}
