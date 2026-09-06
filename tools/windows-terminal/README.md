# Windows Terminal menu cleanup

This optional tool hides Azure Cloud Shell in Windows Terminal. It does not
change mDIR itself or run during mDIR installation. Ubuntu, PowerShell, Command
Prompt, shortcuts, theme and the default profile are preserved. No WSL
distribution is installed, removed or reset.

## Apply

1. In Windows Terminal, choose **Settings → Open JSON file** to identify the
   active `settings.json`. Close the editor before applying.
2. Extract the downloaded repository ZIP and open PowerShell in its root.
3. For the standard Microsoft Store Windows Terminal installation, run:

```powershell
py tools/windows-terminal/hide_azure.py "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json"
```

For Preview or portable installations, pass the actual path from step 1.
Python 3.8+ is required. The tool accepts plain JSON (including UTF-8 BOM).
It safely refuses JSON with comments or trailing commas instead of rewriting it.
It saves a uniquely named backup next to the settings file before replacing it.
Restart Windows Terminal after application.

To undo, close Terminal, copy the printed backup over the original settings file,
and reopen Terminal. To change just one existing Azure profile manually, set
its `hidden` property to `true`. The script also disables the Azure profile
generator so an absent Azure profile is not automatically added later.

## Ubuntu and About

If Ubuntu is missing, inspect `wsl --list --verbose` first. This cleanup does not
recover a missing WSL installation. Existing Ubuntu visibility is preserved.
The built-in **About / 정보** item is not removed by this tool; no supported
per-item hiding option is available in the documented Terminal settings.

References:
- https://learn.microsoft.com/windows/terminal/dynamic-profiles
- https://learn.microsoft.com/windows/terminal/customize-settings/appearance
