@echo off
rem One-click start (Windows): sets up and runs the backend + AI engine and the dashboard,
rem then opens http://localhost:5173 in the browser. Close both windows to stop.
setlocal
cd /d "%~dp0"

echo.
echo ==^> Checking Python 3.11+ and Node.js
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% -c "import sys; sys.exit(sys.version_info < (3, 11))" 2>nul || (
  echo ERROR: Python 3.11 or newer is required: https://www.python.org/downloads/
  goto :fail
)
where npm >nul 2>nul || (
  echo ERROR: Node.js 20 or newer is required: https://nodejs.org/
  goto :fail
)

echo.
echo ==^> Setting up the backend (first run takes a few minutes)
if not exist backend\.venv\Scripts\python.exe %PY% -m venv backend\.venv || goto :fail
backend\.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r backend\requirements.txt || goto :fail
if not exist engine\model\model_fp32.onnx echo WARNING: engine\model\model_fp32.onnx is missing; every slide will fail until it is there.

echo.
echo ==^> Setting up the dashboard
set NEED_INSTALL=0
if not exist frontend\node_modules set NEED_INSTALL=1
if exist frontend\node_modules if not exist frontend\node_modules\.package-lock.json set NEED_INSTALL=1
if %NEED_INSTALL%==0 (
  %PY% -c "import os,sys;sys.exit(0 if os.path.getmtime('frontend/package-lock.json')>os.path.getmtime('frontend/node_modules/.package-lock.json') else 1)" 2>nul
  if not errorlevel 1 set NEED_INSTALL=1
)
if %NEED_INSTALL%==1 (
  echo Installing updated dashboard packages (this takes a few minutes on first run)...
  pushd frontend
  call npm ci --no-audit --no-fund || (popd & goto :fail)
  popd
)

echo.
echo ==^> Starting the backend in a new window on http://127.0.0.1:8000
start "Pathology Triage backend" /D "%~dp0backend" "%~dp0backend\.venv\Scripts\python.exe" run_server.py

echo.
echo ==^> Starting the dashboard on http://localhost:5173 (close this window to stop)
cd frontend
call npm run dev -- --open
exit /b 0

:fail
echo.
echo Setup failed; see the messages above.
pause
exit /b 1
