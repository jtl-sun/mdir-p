@echo off
setlocal
cd /d "%~dp0"

echo Installing or updating mDIR...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
set "MDIR_EXIT=%ERRORLEVEL%"

if not "%MDIR_EXIT%"=="0" (
    echo.
    echo Installation failed. Please copy the error above when asking for help.
) else (
    echo.
    echo Installation complete. You can now run mDIR from the desktop icon.
)

echo.
pause
exit /b %MDIR_EXIT%
