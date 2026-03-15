from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from analysis_engine import AnalysisEngine
from mt4_bridge import MT4Bridge
from telegram_service import TelegramService
from learning_brain import LearningBrain
from news_feed import NewsFeedService
import pandas as pd
import uvicorn

app = FastAPI()
telegram = TelegramService()
bridge = MT4Bridge()
brain = LearningBrain()
news = NewsFeedService()

import json
import pytz
import os
from datetime import datetime, time as dt_time

# Always resolve config.json relative to THIS file (api.py) - fixes path bug when running from any directory
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

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
    strategy: str = "CORE_V2"
    confidence: float = 0.0   # M2 fix: carry real confidence to telegram alert
    elite_score: float = 0.0  # M2 fix: carry real elite score to telegram alert

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
    global AUTO_TRADING_ENABLED, CURRENT_COMPOUND_AMOUNT, LAST_OUTCOME, INVESTMENT_AMOUNT
    
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
        df = bridge.get_historical_data(asset, count=1000) 
        
        if df is not None:
            engine = AnalysisEngine(df)
            signal_data = engine.get_signals()
            
            # Use high threshold for consideration
            if signal_data['confidence'] > 85:
                results[asset] = {**signal_data, "status": "ACTIVE", "balance": real_balance}

    # ELITE SELECTION: Sort all results by Elite Score and keep only top 5
    elite_results = sorted(
        [{"symbol": k, **v} for k, v in results.items() if v.get('elite_score', 0) > 0],
        key=lambda x: x['elite_score'],
        reverse=True
    )[:5]
    
    # Filter 'results' to only show these elite ones if available
    if elite_results:
        results = {item['symbol']: {k: v for k, v in item.items() if k != 'symbol'} for item in elite_results}

    # AUTO-TRADING EXECUTION for the top winners
    FOREX_PAIRS = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY"}
    for asset, signal_data in results.items():
        if signal_data['confidence'] >= 92 and AUTO_TRADING_ENABLED:
            # M5 fix: Allow Forex 24/5, restrict indices/metals to NYSE hours
            is_forex = any(pair in asset for pair in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"])
            session_clear = is_open or is_forex

            # NEWS BLACKOUT CHECK: Block trading around high-impact news
            in_blackout, news_title = news.is_news_blackout(symbol=asset)
            if in_blackout:
                print(f"🚨 [NEWS BLOCK] Skipping {asset} – Blackout: {news_title}")
                await telegram.send_signal(asset, {  # Reuse send_signal as a warning
                    'signal': 'BLOCKED', 'confidence': signal_data['confidence'],
                    'timeframe': 'N/A', 'entry_time': 'N/A', 'expiry_time': 'N/A',
                    'sl': signal_data['sl'], 'tp': signal_data['tp'],
                    'info': f'⚠️ Noticia de Alto Impacto: {news_title}'
                }) if False else None  # Silently skip for now; can notify via telegram if needed
                continue

            if session_clear:
                print(f"🚀 [AUTO-ELITE] {asset}: {signal_data['strategy']} (Elite: {signal_data.get('elite_score',0)} | Win: {signal_data.get('backtest_winrate',0)}%)")
                await execute_trade(TradeRequest(
                    symbol=asset,
                    type=signal_data['signal'],
                    volume=0.01,
                    amount=CURRENT_COMPOUND_AMOUNT,
                    sl=signal_data['sl'],
                    tp=signal_data['tp'],
                    strategy=signal_data['strategy'],
                    confidence=signal_data['confidence'],
                    elite_score=signal_data.get('elite_score', 0)
                ))
            else:
                print(f"⏳ [SESSION-WAIT] {asset} ({signal_data['confidence']}%) - {session_msg}")
        elif signal_data['confidence'] >= 92:
            print(f"⚠️ [SKIP] Confianza 92%+ en {asset} pero Mando Automático está APAGADO.")
            
    # If no results found, ensure majors are visible
    if not results:
        for asset in ["EURUSD", "XAUUSD"]:
            df = bridge.get_historical_data(asset, count=1000)
            if df is not None:
                engine = AnalysisEngine(df)
                results[asset] = {**engine.get_signals(), "status": "STABLE", "balance": real_balance}

    # --- OUTCOME MONITORING LOOP ---
    # Check if any previously opened trades have closed to report Win/Loss
    open_trades = brain.get_open_trades()
    for ot in open_trades:
        ticket = ot['ticket']
        # Check if ticket is in recent history (closed)
        history = bridge.get_history(count=20)
        for deal in history:
            if str(deal.get('ticket')) == str(ticket):
                profit = deal['profit']
                outcome = "WIN" if profit > 0 else "LOSS"

                # ✅ COMPOUNDING LOGIC
                # WIN: add real profit to running compound total
                # LOSS: reset to original base amount set by user
                if outcome == "WIN":
                    CURRENT_COMPOUND_AMOUNT += profit
                    LAST_OUTCOME = "WIN"
                    print(f"✅ [COMPOUND] WIN +${profit:.2f} → Next trade: ${CURRENT_COMPOUND_AMOUNT:.2f}")
                else:
                    CURRENT_COMPOUND_AMOUNT = INVESTMENT_AMOUNT  # Reset to user's original base
                    LAST_OUTCOME = "LOSS"
                    print(f"❌ [COMPOUND] LOSS ${profit:.2f} → Resetting to base: ${INVESTMENT_AMOUNT:.2f}")

                # Persist compound state so restart preserves it
                save_config()

                # Update Brain
                brain.update_trade_outcome(str(ticket), outcome)

                # Send Report with updated next amount
                await telegram.send_outcome_report(
                    ot['symbol'],
                    outcome,
                    profit,
                    ot['strategy'],
                    CURRENT_COMPOUND_AMOUNT
                )
                print(f"📢 [TELEGRAM REPORT] Ticket {ticket} closed as {outcome}")
                break
    # -------------------------------

    history = bridge.get_history()

    # Fetch upcoming news for the dashboard
    upcoming_news = []
    try:
        upcoming_news = news.get_upcoming_events(hours_ahead=24)
    except Exception:
        pass

    response_data = {
        "results": results,
        "last_ticket": LAST_TICKET,
        "history": history,
        "market_session": {"is_open": is_open, "message": session_msg},
        "auto_trading": {
            "enabled": AUTO_TRADING_ENABLED,
            "base_amount": INVESTMENT_AMOUNT,
            "current_amount": CURRENT_COMPOUND_AMOUNT,
            "last_outcome": LAST_OUTCOME
        },
        "upcoming_news": upcoming_news  # 📰 Economic Calendar for frontend display
    }
    return response_data

@app.post("/trade")
async def execute_trade(request: TradeRequest):
    global CURRENT_COMPOUND_AMOUNT, LAST_OUTCOME
    real_balance = bridge.get_balance()
    
    if real_balance < request.amount:
        return {"status": "ERROR", "message": f"Fondos insuficientes. Saldo: ${real_balance}"}

    if not bridge.connected:
        # C2 fix: Only try to reconnect if not already connected. Don't forcefully reconnect
        if not bridge.connect():
            raise HTTPException(status_code=500, detail="Error de conexión MT5")
    
    # EXECUTE TRADE IN MT5
    trade_result = bridge.execute_trade(
        request.symbol, 
        request.type, 
        request.volume,
        sl=request.sl,
        tp=request.tp
    )
    
    if trade_result.get("status") == "error":
        return {"status": "ERROR", "message": trade_result.get("message")}

    ticket = trade_result.get("order_id", "N/A")
    new_balance = bridge.get_balance()
    global LAST_TICKET
    LAST_TICKET = str(ticket)
    
    # Initialize outcome tracking
    LAST_OUTCOME = "WAITING_RESULT"
    
    # LOG IN BRAIN (Initial context)
    if ticket != "N/A":
        # Send Telegram Execution Alert with REAL confidence and elite_score (M2 fix)
        try:
            current_price = bridge.get_historical_data(request.symbol, count=1)
            if current_price is not None:
                current_price = current_price.iloc[-1]['Close']
            else:
                current_price = 0.0
            await telegram.send_execution_alert(
                request.symbol,
                request.type,
                current_price,
                request.strategy,
                request.confidence,    # M2 fix: use real value
                request.elite_score    # M2 fix: use real value
            )
        except Exception as te:
            print(f"⚠️ Telegram alert error: {te}")

        # Capture basic context for the brain
        brain.log_trade_start(
            str(ticket),
            request.symbol,
            request.type,
            0.0,
            {"strategy": request.strategy}
        )

    # C8 fix: Don't try to instantly match ticket in closed history.
    # Market orders take time to settle. Outcome is tracked by the monitoring loop.
    # Only update LAST_OUTCOME to WAITING so the UI reflects state.
    LAST_OUTCOME = "WAITING_RESULT"

    print(f"🚀 [MT5 EXEC] TICKET: {ticket} | {request.symbol} | {request.strategy}")
    
    return {
        **trade_result, 
        "balance": new_balance, 
        "outcome": LAST_OUTCOME, 
        "next_amount": CURRENT_COMPOUND_AMOUNT,
        "ticket": ticket
    }


if __name__ == "__main__":
    print("🛰️ Intentando conectar con MetaTrader 5...")
    if bridge.connect():
        real_balance = bridge.get_balance()
        print(f"    ANALISIS BOT TRADE - Saldo Real: ${real_balance:.2f}")
    else:
        print("⚠️ Advertencia: No se pudo conectar a MT5. El sistema iniciará en modo espera.")
        
    uvicorn.run(app, host="0.0.0.0", port=8001)
