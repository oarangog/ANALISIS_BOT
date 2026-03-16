@echo off
setlocal
cd /d %~dp0

:: Absolute paths for system utilities to avoid PATH issues
set TASKKILL=C:\Windows\System32\taskkill.exe
set PING=C:\Windows\System32\ping.exe
set FIND=C:\Windows\System32\find.exe
set NETSTAT=C:\Windows\System32\netstat.exe

echo ===================================================
echo    ANAILIS BOT - INICIO MAESTRO (V2.5)
echo ===================================================

echo [*] Limpiando procesos y liberando puertos...
:: Kill by process name
%TASKKILL% /F /IM node.exe /T 2>nul
%TASKKILL% /F /IM python.exe /T 2>nul

:: Kill by port (High reliability) using absolute netstat path
for /f "tokens=5" %%a in ('%NETSTAT% -aon ^| %FIND% ":8001" ^| %FIND% "LISTENING"') do %TASKKILL% /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('%NETSTAT% -aon ^| %FIND% ":5173" ^| %FIND% "LISTENING"') do %TASKKILL% /F /PID %%a 2>nul

%PING% -n 3 127.0.0.1 >nul

echo [*] Iniciando Backend...
echo [!] Esta ventana mostrara el escaneo y balance en vivo.
cd /d %~dp0backend
start "BOT_BACKEND_LIVE" cmd /k "python api.py"

echo [*] Iniciando Dashboard...
%PING% -n 8 127.0.0.1 >nul
cd /d %~dp0
start "BOT_FRONTEND" /min cmd /c "cd /d %~dp0 && npm run dev -- --port 5173 --host 0.0.0.0"

echo.
echo ===================================================
echo   SISTEMA ACTIVO Y VISIBLE
echo   Dashboard: http://localhost:5173
echo ===================================================
echo.
pause
