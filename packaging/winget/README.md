# WinGet publication preparation

The current source ZIP runs an installer and is not the final WinGet artifact.
Build a self-contained portable ZIP on Windows first:

```powershell
.\packaging\windows\build_portable.ps1
```

Then attach `dist/mDIR-P-<version>-win64.zip` to the matching GitHub Release,
replace `INSTALLER_SHA256` in the manifest template, remove the `.template`
suffixes, and validate on Windows:

```powershell
winget validate .\packaging\winget
winget install --manifest .\packaging\winget
```

After local validation, submit the manifest directory to
`microsoft/winget-pkgs`. Do not submit the templates while the placeholder is
present. Microsoft may run automated validation and a manual review.
