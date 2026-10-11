@echo off
REM Starts the DemandIQ sales forecaster on http://localhost:8001 using ML-MODEL\venv
REM (the main project venv does not have xgboost). Opened by the "Sales Forecaster" sidebar button.
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo ML-MODEL\venv not found. Creating it and installing requirements...
  python -m venv venv || goto :fail
  "venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
)
"venv\Scripts\python.exe" -m uvicorn app:app --reload --port 8001
goto :eof

:fail
echo Setup failed.
pause
