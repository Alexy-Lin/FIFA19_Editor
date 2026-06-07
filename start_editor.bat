@echo off
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "EDITOR_DIR=%SCRIPT_DIR%fifa19-editor"
set "SAV_FILE=%SCRIPT_DIR%Squads20260423210221"

set "PYTHON="
if exist "C:\anaconda3\python.exe" set "PYTHON=C:\anaconda3\python.exe"
if not defined PYTHON if exist "C:\Python313\python.exe" set "PYTHON=C:\Python313\python.exe"
if not defined PYTHON (
    where python >nul 2>&1 && (
        for /f "delims=" %%i in ('where python') do set "PYTHON=%%i" & goto :found
    )
    echo Python not found. Please install Python 3.10+ or Anaconda.
    pause
    exit /b 1
)
:found

if not exist "%SAV_FILE%" (
    echo SAV file not found: %SAV_FILE%
    pause
    exit /b 1
)

echo FIFA 19 Save Editor - Loading...
"%PYTHON%" "%EDITOR_DIR%\main_gui.py" "%SAV_FILE%"
if errorlevel 1 (
    echo.
    echo GUI exited with an error. Check the console output above.
    pause
)