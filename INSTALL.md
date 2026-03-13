# 🛸 ANAILIS BOT - Guía de Instalación Pro

Esta guía detalla los pasos para poner en marcha el sistema de trading autónomo con IA en cualquier computadora Windows.

## 📋 Requisitos Previos

1.  **Python 3.10+**: [Descargar aquí](https://www.python.org/downloads/) (Asegúrate de marcar "Add Python to PATH").
2.  **Node.js LTS**: [Descargar aquí](https://nodejs.org/).
3.  **MetaTrader 5 (XM Global)**: Instalado y con una cuenta activa.
4.  **Token de Telegram**: Necesitas un bot de Telegram (creado con @BotFather).

## 🚀 Pasos de Instalación

### 1. Clonar el Repositorio
```bash
git clone https://github.com/oarangog/ANALISIS_BOT.git
cd ANALISIS_BOT
```

### 2. Configuración del Backend (Python)
Entra en la carpeta del servidor y configura las dependencias:
```bash
cd backend
pip install -r requirements.txt
```

#### Configura el archivo `.env`
Crea un archivo llamado `.env` en la raíz del proyecto con la siguiente estructura:
```env
VITE_MT4_LOGIN=TU_LOGIN_XM
VITE_MT4_PASSWORD=TU_PASSWORD_XM
VITE_MT4_SERVER=TU_SERVIDOR_XM (e.g., XMGlobal-MT5 2)
VITE_MT5_PATH=C:/Program Files/XM Global MT5/terminal64.exe
TELEGRAM_BOT_TOKEN=TU_TOKEN_TELEGRAM
TELEGRAM_CHAT_ID=TU_ID_DE_CHAT
```

### 3. Configuración del Frontend (React)
Vuelve a la raíz del proyecto e instala las dependencias de la web:
```bash
npm install
```

## 🎮 Cómo Iniciar el Sistema

### Paso A: Abrir MetaTrader 5
1.  Abre MT5 y loguéate en tu cuenta.
2.  Ve a **Herramientas > Opciones > Expert Advisors**.
3.  Marca: **"Permitir el Autotrading"** y **"Permitir peticiones WebRequest"**.

### Paso B: Iniciar el Servidor (Backend)
```bash
cd backend
python api.py
```

### Paso C: Iniciar la Interfaz Web (Frontend)
```bash
npm run dev
```
Abre tu navegador en `http://localhost:5173`.

## 🤖 Operación del Bot
1.  En la web, verás el panel de **"Mando Autónomo"**.
2.  Configura tu inversión base (e.g., $10).
3.  Haz clic en **"ENTREGAR MANDO"**.
4.  El bot empezará a escanear el mercado y operará automáticamente cuando detecte una probabilidad mayor al 92%.
5.  **Horario NYSE**: El bot solo ejecutará operaciones de **Lunes a Viernes, de 09:30 AM a 04:00 PM (Hora NY)**. Fuera de este horario, el bot analizará el mercado pero no enviará órdenes.
6.  **Compounding Automático**: Si el bot gana una operación real (verificada en el historial de MT5), reinvertirá la ganancia. Si pierde, reseteará la inversión a tu monto base.
---
**Advertencia**: El trading conlleva riesgos. Este bot es una herramienta de análisis y ejecución automatizada; úsalo con responsabilidad. 🛰️💰
