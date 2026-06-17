@echo off
REM Runs the Omi -> Obsidian sync. Point Windows Task Scheduler at this file.
REM Set your key here OR in config.json (env var keeps it out of any file).

setlocal
cd /d "%~dp0"

if "%OMI_API_KEY%"=="" set OMI_API_KEY=omi_dev_PUT_YOUR_KEY_HERE

python omi_to_obsidian.py
endlocal
