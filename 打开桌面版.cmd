@echo off
cd /d "%~dp0"
if exist "dist\GDS Studio\GDS Studio.exe" (
    start "" "dist\GDS Studio\GDS Studio.exe"
) else (
    call "启动 GDS Studio.cmd"
)
