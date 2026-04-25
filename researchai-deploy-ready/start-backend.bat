@echo off
cd /d "%~dp0"
"C:\Users\haritha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
