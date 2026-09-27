@echo off
setlocal
cd /d "%~dp0"
title Minglie Launcher

echo ==================================================
echo   Minglie RAG Workbench  -  one-click start
echo ==================================================
echo.

set "ROOT=%~dp0"
set "BE_PORT=8010"
set "FE_PORT=5173"

rem ---------------------------------------------------------------
rem  1. sanity checks
rem ---------------------------------------------------------------
if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo [ERROR] backend\.venv not found. Create it first:
  echo             cd backend
  echo             python -m venv .venv
  echo             .venv\Scripts\pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
  echo [SETUP] frontend dependencies missing, running npm install ...
  pushd "%ROOT%frontend"
  call npm install
  popd
)

rem ---------------------------------------------------------------
rem  2. start backend
rem  pushd makes the new window's working directory = backend\
rem  (the .env database and upload paths are relative)
rem ---------------------------------------------------------------
netstat -an | findstr ":%BE_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [SKIP] backend is already running on port %BE_PORT%
) else (
  echo [1/3] starting backend on port %BE_PORT% ...
  pushd "%ROOT%backend"
  start "Minglie Backend" cmd /k .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %BE_PORT%
  popd
)

rem ---------------------------------------------------------------
rem  3. start frontend
rem ---------------------------------------------------------------
netstat -an | findstr ":%FE_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [SKIP] frontend is already running on port %FE_PORT%
) else (
  echo [2/3] starting frontend on port %FE_PORT% ...
  pushd "%ROOT%frontend"
  start "Minglie Frontend" cmd /k npm run dev
  popd
)

rem ---------------------------------------------------------------
rem  4. wait until the web server answers
rem ---------------------------------------------------------------
echo [3/3] waiting for the web server to become ready ...
set /a tries=0
:wait
ping -n 2 127.0.0.1 >nul
set /a tries+=1
curl -s -o nul -m 2 http://127.0.0.1:%FE_PORT%
if %errorlevel%==0 goto ready
if %tries% lss 40 goto wait
echo       [WARN] frontend is slow to start. Open the URL manually in a moment.
goto openbrowser

:ready
echo       ready.

rem ---------------------------------------------------------------
rem  5. open the browser
rem ---------------------------------------------------------------
:openbrowser
start "" http://localhost:%FE_PORT%

echo.
echo --------------------------------------------------
echo   URL      : http://localhost:%FE_PORT%
echo   Login    : admin
echo   Password : see ADMIN_PASSWORD in .env
echo   API docs : http://127.0.0.1:%BE_PORT%/api/docs
echo --------------------------------------------------
echo.
echo You may close THIS window.
echo Keep the "Minglie Backend" and "Minglie Frontend"
echo windows open while you use the app.
echo.
echo To stop everything later, double-click stop-minglie.bat
echo.
pause
endlocal
