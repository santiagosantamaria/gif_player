@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

rem Drag the picture to move it. Drag an edge or corner to resize it.
rem Press Ctrl+Shift+Q to quit.

set "PY=python"
set "LAUNCH=pythonw"
where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python 3 was not found.
    echo Install it from https://www.python.org/downloads/ and turn on "Add python.exe to PATH".
    pause
    exit /b 1
  )
  set "PY=py -3"
  set "LAUNCH=pyw -3"
)

%PY% -c "import PIL" >nul 2>&1
if errorlevel 1 (
  echo Installing Pillow...
  %PY% -m pip install --disable-pip-version-check pillow
  if errorlevel 1 (
    echo Could not install Pillow.
    pause
    exit /b 1
  )
)

where pythonw >nul 2>&1
if errorlevel 1 if "!LAUNCH!"=="pythonw" set "LAUNCH=python"

start "" !LAUNCH! "%~dp0gif_player.py"
exit /b 0
