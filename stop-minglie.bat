@echo off
setlocal enabledelayedexpansion
title Minglie Stop

echo ==================================================
echo   Minglie RAG Workbench  -  stop services
echo ==================================================
echo.

set "FOUND=0"

for %%P in (8010 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
    echo   stopping PID %%A  ^(port %%P^)
    taskkill /F /PID %%A >nul 2>&1
    set "FOUND=1"
  )
)

if "!FOUND!"=="0" (
  echo   nothing to stop - no service is listening on 8010 / 5173.
) else (
  echo.
  echo   done. The "Minglie Backend" / "Minglie Frontend"
  echo   windows will close on their own, or close them manually.
)

ping -n 3 127.0.0.1 >nul
endlocal
