@echo off
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "EDITOR_DIR=%SCRIPT_DIR%fifa19-editor"

set "PYTHON="
if exist "C:\anaconda3\python.exe" set "PYTHON=C:\anaconda3\python.exe"
if not defined PYTHON if exist "C:\Python313\python.exe" set "PYTHON=C:\Python313\python.exe"
if not defined PYTHON if exist "C:\Python314\python.exe" set "PYTHON=C:\Python314\python.exe"
if not defined PYTHON (
    where python >nul 2>&1 && (
        for /f "delims=" %%i in ('where python') do set "PYTHON=%%i" & goto :found
    )
    echo Python not found. Please install Python 3.10+ or Anaconda.
    pause
    exit /b 1
)
:found

echo FIFA 19 Save Editor - Loading...
rem No SAV file argument - main_gui.py loads last opened file from config.
"%PYTHON%" "%EDITOR_DIR%\main_gui.py"
if errorlevel 1 (
    echo.
    echo GUI exited with an error. Check the console output above.
    pause
)
