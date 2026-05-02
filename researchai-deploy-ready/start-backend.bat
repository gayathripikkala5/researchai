@echo off
cd /d "%~dp0"
set PYTHON_EXE=C:\Users\haritha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
"%PYTHON_EXE%" -c "import uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Installing backend requirements...
  "%PYTHON_EXE%" -m pip install -r backend\requirements.txt
)
"%PYTHON_EXE%" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
