@echo off
echo 🚀 Iniciando ANAILIS BOT...

start cmd /k "title ANAILIS_BACKEND && cd backend && python api.py"
timeout /t 5
start cmd /k "title ANAILIS_FRONTEND && npm run dev"

echo ✅ Sistema lanzado. 
echo 🌐 Abre http://localhost:5173 en tu navegador.
