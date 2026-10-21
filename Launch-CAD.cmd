@echo off
cd /d "%~dp0"
if exist "dist\GDS-Studio-CAD\GDS-Studio-CAD.exe" (
    start "" "dist\GDS-Studio-CAD\GDS-Studio-CAD.exe"
) else (
    if exist ".venv\Scripts\pythonw.exe" (
        start "" ".venv\Scripts\pythonw.exe" "main.py"
    ) else (
        echo Build the desktop package or install the Python environment first.
        pause
    )
)
