@echo off
REM One-click compile: shred new sources in raw\ into wiki\, then commit + push.
REM Keeps the compile MANUAL — you run it (or double-click it) when you want a refresh.

REM Resolve the REAL Desktop (handles OneDrive redirection) via PowerShell.
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESK=%%D"

cd /d "%DESK%\Brain" || (echo Could not find "%DESK%\Brain". Run scaffold.ps1 first. & pause & exit /b 1)

echo Compiling Brain ^(raw\ -^> wiki\^)...
claude -p "Compile every new source in raw\ (including raw\Omi) into wiki\ following CLAUDE.md. Create atomic, wikilinked notes, update wiki\index.md and log.md, then commit and push."

echo.
echo Done. Press any key to close.
pause >nul
