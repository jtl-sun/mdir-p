$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python -m mdir @args
