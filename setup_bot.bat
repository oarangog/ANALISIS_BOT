@echo off
setlocal enabledelayedexpansion

echo 🛸 ==========================================
echo 🛸     ANAILIS BOT - AUTO-INSTALLER
echo 🛸 ==========================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python no encontrado. Por favor instalalo desde python.org
    pause
    exit /b
)

:: Check for Node.js
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js no encontrado. Por favor instalalo desde nodejs.org
    pause
    exit /b
)

echo 🛠️  Instalando dependencias del Backend (Python)...
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ Error instalando dependencias de Python.
    pause
    exit /b
)
cd ..

echo 🛠️  Instalando dependencias del Frontend (React)...
call npm install
if %errorlevel% neq 0 (
    echo ❌ Error instalando dependencias de Node.js.
    pause
    exit /b
)

echo.
echo ✅ INSTALACION COMPLETADA CON EXITO.
echo 🛸 ==========================================
echo.
echo 📖 Para iniciar el sistema:
echo 1. Abre MetaTrader 5 (XM Global).
echo 2. Ejecuta 'start_bot.bat' para iniciar todo automaticamente.
echo.
pause
