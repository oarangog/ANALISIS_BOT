from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from analysis_engine import AnalysisEngine
from mt4_bridge import MT4Bridge
from telegram_service import TelegramService
from learning_brain import LearningBrain
import pandas as pd
import uvicorn

app = FastAPI()
telegram = TelegramService()
bridge = MT4Bridge()
brain = LearningBrain()

import json
import pytz
from datetime import datetime, time as dt_time

CONFIG_FILE = "backend/config.json"

def is_nyse_session():
    """
    Checks if the current time is within NYSE hours:
    Monday-Friday, 09:30 AM to 04:00 PM Eastern Time.
    """
    ny_tz = pytz.timezone("America/New_York")
    ny_now = datetime.now(ny_tz)
    
    # 0 = Monday, 4 = Friday
    if ny_now.weekday() > 4:
        return False, "Fin de semana (Cerrado)"
        
    start_time = dt_time(9, 30)
    end_time = dt_time(16, 0)
    current_time = ny_now.time()
    
    if start_time <= current_time <= end_time:
        return True, "Sesion NYSE Abierta"
    elif current_time < start_time:
        return False, f"Esperando Apertura (Abre 09:30 NY). Actual: {current_time.strftime('%H:%M')}"
    else:
        return False, "Bolsa Cerrada (Cierra 16:00 NY)"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {"auto_trading_enabled": False, "investment_amount": 10.0, "current_compound_amount": 10.0}

def save_config():
    config = {
        "auto_trading_enabled": AUTO_TRADING_ENABLED,
        "investment_amount": INVESTMENT_AMOUNT,
        "current_compound_amount": CURRENT_COMPOUND_AMOUNT
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# Financial Configuration
config = load_config()
INVESTMENT_AMOUNT = config["investment_amount"]
AUTO_TRADING_ENABLED = config["auto_trading_enabled"]
CURRENT_COMPOUND_AMOUNT = config["current_compound_amount"]
LAST_OUTCOME = None
LAST_TICKET = "N/A"

class AutoToggle(BaseModel):
    enabled: bool
    base_amount: float

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class TradeRequest(BaseModel):
    symbol: str
    type: str  # BUY or SELL
    volume: float
    amount: float = 10.0
    sl: float = 0.0
    tp: float = 0.0

@app.post("/auto-toggle")
async def toggle_auto(request: AutoToggle):
    global AUTO_TRADING_ENABLED, INVESTMENT_AMOUNT, CURRENT_COMPOUND_AMOUNT
    AUTO_TRADING_ENABLED = request.enabled
    INVESTMENT_AMOUNT = request.base_amount
    if not AUTO_TRADING_ENABLED:
        CURRENT_COMPOUND_AMOUNT = INVESTMENT_AMOUNT
    save_config()
    print(f"🔄 CONFIG UPDATE: AutoTrading={AUTO_TRADING_ENABLED}, Base=${INVESTMENT_AMOUNT}")
    return {"status": "SUCCESS", "auto_enabled": AUTO_TRADING_ENABLED, "base": INVESTMENT_AMOUNT}

@app.get("/analysis")
async def get_daily_analysis():
    global AUTO_TRADING_ENABLED, CURRENT_COMPOUND_AMOUNT, LAST_OUTCOME
    
    # DYNAMIC SCANNING: Fetch all major symbols from MT5
    all_symbols = bridge.get_all_symbols()
    if not all_symbols:
        all_symbols = ["EURUSD", "USDJPY", "AUDUSD", "XAUUSD"] # Fallback
    
    real_balance = bridge.get_balance()
    results = {}
    
    # NYSE Session Check
    is_open, session_msg = is_nyse_session()
    print(f"🕒 [MERCADO] {session_msg}")
    
    print(f"🔍 Escaneando {len(all_symbols)} activos en busca de oportunidades...")
    
    for asset in all_symbols:
        # Fetch data for analysis
        df = bridge.get_historical_data(asset, count=1000) # Use 1000 for faster scanning
        
        if df is not None:
            engine = AnalysisEngine(df)
            signal_data = engine.get_signals()
            
            # Only include if confidence is decent, or if it's one of the user's favorites
            if signal_data['confidence'] > 85:
                results[asset] = {**signal_data, "status": "ACTIVE", "balance": real_balance}
                
                # AUTO-TRADING EXECUTION for high confidence winners
                print(f"🤖 [EVAL] {asset}: Confianza {signal_data['confidence']}% | Auto: {AUTO_TRADING_ENABLED}")
                
                if signal_data['confidence'] >= 92 and AUTO_TRADING_ENABLED:
                    if is_open:
                        print(f"🚀 [AUTO-WINNER] Iniciando trade en {asset} con ${CURRENT_COMPOUND_AMOUNT}")
                        await execute_trade(TradeRequest(
                            symbol=asset, 
                            type=signal_data['signal'], 
                            volume=0.01, 
                            amount=CURRENT_COMPOUND_AMOUNT,
                            sl=signal_data['sl'],
                            tp=signal_data['tp']
                        ))
                    else:
                        print(f"⏳ [SESSION-WAIT] Confianza 92%+ en {asset} pero fuera de horario NYSE: {session_msg}")
                elif signal_data['confidence'] >= 92:
                    print(f"⚠️ [SKIP] Confianza 92%+ encontrada en {asset} pero Mando Automático está APAGADO.")
            
    # If no winners found, ensure at least the majors are visible
    if not results:
        for asset in ["EURUSD", "XAUUSD"]:
            df = bridge.get_historical_data(asset, count=1000)
            if df is not None:
                engine = AnalysisEngine(df)
                results[asset] = {**engine.get_signals(), "status": "STABLE", "balance": real_balance}

    # Get trade history
    history = bridge.get_history()

    response_data = {
        "results": results,
        "last_ticket": LAST_TICKET,
        "history": history,
        "market_session": {
            "is_open": is_open,
            "message": session_msg
        },
        "auto_trading": {
            "enabled": AUTO_TRADING_ENABLED,
            "base_amount": INVESTMENT_AMOUNT,
            "current_amount": CURRENT_COMPOUND_AMOUNT,
            "last_outcome": LAST_OUTCOME
        }
    }
    print(f"DEBUG: Response keys are {list(response_data.keys())}")
    return response_data

@app.post("/trade")
async def execute_trade(request: TradeRequest):
    global CURRENT_COMPOUND_AMOUNT, LAST_OUTCOME
    real_balance = bridge.get_balance()
    
    if real_balance < request.amount:
        return {"status": "ERROR", "message": f"Fondos insuficientes en cuenta real. Saldo: ${real_balance}"}

    if not bridge.connect():
        raise HTTPException(status_code=500, detail="No se pudo conectar a MetaTrader 5")
    
    # EXECUTE TRADE IN MT5
    ticket, new_balance, last_profit = bridge.execute_trade(
        request.symbol, 
        request.type, 
        request.volume,
        sl=request.sl,
        tp=request.tp
    )
    new_balance = bridge.get_balance()
    global LAST_TICKET
    LAST_TICKET = str(ticket)
    
    # COMPOUNDING LOGIC (Synced with REAL MT5 History)
    # We wait a bit or use the last closed deal profit
    history = bridge.get_history(count=1)
    last_profit = 0.0
    if history:
        last_profit = history[0]['profit']
    
    global CURRENT_COMPOUND_AMOUNT, LAST_OUTCOME
    if last_profit > 0:
        CURRENT_COMPOUND_AMOUNT += last_profit
        LAST_OUTCOME = "WIN"
    elif last_profit < 0:
        CURRENT_COMPOUND_AMOUNT = INVESTMENT_AMOUNT
        LAST_OUTCOME = "LOSS"
    else:
        # If no result yet, keep current amount or assume break even
        LAST_OUTCOME = "WAITING_RESULT"

    # UPDATE BRAIN WITH OUTCOME
    if ticket != "N/A" and LAST_OUTCOME in ["WIN", "LOSS"]:
        brain.update_trade_outcome(ticket, LAST_OUTCOME)

    print(f"\n🚀 [MT5 REAL EXECUTION] TICKET: {ticket}")
    print(f"🏦 Activo: {request.symbol} | Volumen: {request.volume} | Tipo: {request.type}")
    print(f"🏦 Saldo Actualizado: ${new_balance:.2f}")
    print(f"📈 Próxima Inversión (Compounding): ${CURRENT_COMPOUND_AMOUNT:.2f} ({LAST_OUTCOME})\n")
    
    return {
        **result, 
        "balance": new_balance, 
        "outcome": LAST_OUTCOME, 
        "next_amount": CURRENT_COMPOUND_AMOUNT,
        "ticket": ticket
    }

if __name__ == "__main__":
    print("🛰️ Intentando conectar con MetaTrader 5...")
    if bridge.connect():
        real_balance = bridge.get_balance()
        print(f"    ANALISIS BOT TRADE - Saldo Real: ${balance:.2f}")
    else:
        print("⚠️ Advertencia: No se pudo conectar a MT5. El sistema iniciará en modo espera.")
        
    uvicorn.run(app, host="0.0.0.0", port=8001)
