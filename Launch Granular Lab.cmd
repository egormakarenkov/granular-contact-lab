@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
  ".venv\Scripts\python.exe" -m pip install -r requirements-tested.txt
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" portable_launcher.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Launch failed. See README.md. Python 3.13 x64 is the tested source runtime.
pause
exit /b 1
