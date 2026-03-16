from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from analysis_engine import AnalysisEngine
from mt4_bridge import MT4Bridge
from telegram_service import TelegramService
from learning_brain import LearningBrain
from news_feed import NewsFeedService
import pandas as pd
import uvicorn
import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta

# Setup Logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bot")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create background task
    task = asyncio.create_task(background_scanning_loop())
    yield
    # Shutdown: Cancel task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("🛑 [SYSTEM] Background scanning loop stopped.")

app = FastAPI(title="Anailis Bot API", lifespan=lifespan)
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
        
    start_time_ny = dt_time(9, 30)
    end_time_ny = dt_time(16, 0)
    
    # London Session (approx 03:00 - 11:30 NY time)
    start_time_lon = dt_time(3, 0)
    end_time_lon = dt_time(11, 30)
    
    # Tokyo Session (approx 19:00 - 04:00 NY time next day)
    # We'll check if it's broadly "Asian session" or London overlap
    
    current_time = ny_now.time()
    
    if start_time_ny <= current_time <= end_time_ny:
        return True, "Sesion NYSE Abierta"
    elif start_time_lon <= current_time <= end_time_lon:
        return True, "Sesion LONDRES Abierta (Volatilidad Prime)"
    elif current_time >= dt_time(19, 0) or current_time <= dt_time(4, 0):
        return True, "Sesion ASIA Abierta (Baja Volatilidad)"
    else:
        return False, f"Bolsas Principales Cerradas. Actual NY: {current_time.strftime('%H:%M')}"

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
    logger.info(f"🔄 CONFIG UPDATE: AutoTrading={AUTO_TRADING_ENABLED}, Base=${INVESTMENT_AMOUNT}")
    return {"status": "SUCCESS", "auto_enabled": AUTO_TRADING_ENABLED, "base": INVESTMENT_AMOUNT}

import asyncio

# Shared State (Cache)
GLOBAL_CACHE = {
    "scan_count": 0,
    "elite_symbols": [],
    "results": {},
    "open_positions": [],
    "real_balance": 0.0,
    "last_update": "Esperando primer escaneo...",
    "session_msg": "Iniciando...",
    "is_open": False,
    "currently_scanning": "N/A",
    "all_scores": {} # Full matrix
}

LAST_HEARTBEAT = datetime.now() - timedelta(hours=2) # Initialize for immediate first heartbeat

# CORRELATION GROUPS (Aggressive Risk Management)
CORRELATION_GROUPS = [
    {"EURUSD", "GBPUSD"},
    {"AUDUSD", "NZDUSD"},
    {"US30", "SPX500", "NAS100"},
    {"BTCUSD", "ETHUSD", "LTCUSD"},
    {"XAUUSD", "XAGUSD"}
]

def is_correlated_open(symbol, open_positions):
    """Checks if any asset in the same correlation group is already open."""
    for group in CORRELATION_GROUPS:
        if symbol in group:
            for pos in open_positions:
                if pos['symbol'] in group and pos['symbol'] != symbol:
                    return True, pos['symbol']
    return False, None

async def background_scanning_loop():
    """
    Main autonomous logic running in the background.
    Scans markets, manages trades, and updates the global cache.
    """
    global AUTO_TRADING_ENABLED, CURRENT_COMPOUND_AMOUNT, LAST_OUTCOME
    logger.info("🚀 [SYSTEM] Background scanning loop started.")
    
    while True:
        try:
            # 1. Telemetry
            GLOBAL_CACHE["real_balance"] = bridge.get_balance()
            
            # 2. Market Session
            is_open, session_msg = is_nyse_session()
            GLOBAL_CACHE["is_open"] = is_open
            GLOBAL_CACHE["session_msg"] = session_msg
            
            # 3. Dynamic Scanning
            all_symbols = bridge.get_all_symbols()
            if not all_symbols:
                all_symbols = ["EURUSD", "USDJPY", "AUDUSD", "XAUUSD"]
            
            GLOBAL_CACHE["scan_count"] = len(all_symbols)
            
            current_results = {}
            full_matrix = {}
            
            for asset in all_symbols:
                GLOBAL_CACHE["currently_scanning"] = asset
                df = bridge.get_historical_data(asset, count=1000)
                if df is not None:
                    engine = AnalysisEngine(df)
                    signal_data = engine.get_signals()
                    
                    # Store score for the matrix (always)
                    full_matrix[asset] = {
                        "score": signal_data['confidence'],
                        "signal": signal_data['signal'],
                        "trend": signal_data.get('trend', 'Neutral')
                    }
                    
                    # Store results for dashboard signal cards (> 85%)
                    if signal_data['confidence'] > 85:
                        current_results[asset] = signal_data
            
            GLOBAL_CACHE["results"] = current_results
            GLOBAL_CACHE["all_scores"] = full_matrix
            GLOBAL_CACHE["currently_scanning"] = "Ciclo Completado"
            
            # Console Summary (User visibility)
            # Pull top 5 from full_matrix (even if < 85%) to show movement
            sorted_all = sorted(full_matrix.items(), key=lambda x: x[1]['score'], reverse=True)[:5]
            top_assets_str = ", ".join([f"{k}({v['score']}%)" for k, v in sorted_all]) if sorted_all else "Escaneando..."
            
            print("\n" + "="*40)
            print(f"📊 REPORT [ {datetime.now().strftime('%H:%M:%S')} ]")
            print(f"💰 Balance: ${GLOBAL_CACHE['real_balance']:.2f}")
            print(f"📡 Escaneados: {len(all_symbols)} activos")
            print(f"🔥 Top Scores: {top_assets_str}")
            print("="*40 + "\n")
            
            # 4. Elite Selection
            elite_results = sorted(
                [{"symbol": k, **v} for k, v in current_results.items() if v.get('elite_score', 0) > 0],
                key=lambda x: x['elite_score'],
                reverse=True
            )[:5]
            GLOBAL_CACHE["elite_symbols"] = [item['symbol'] for item in elite_results]

            # 5. Open Positions
            pos_list = []
            positions = mt5.positions_get()
            if positions:
                for p in positions:
                    pos_list.append({
                        "ticket": p.ticket, "symbol": p.symbol,
                        "type": "BUY" if p.type == 0 else "SELL",
                        "price_open": p.price_open, "price_current": p.price_current,
                        "sl": p.sl, "tp": p.tp, "profit": p.profit
                    })
            GLOBAL_CACHE["open_positions"] = pos_list

            # 6. Trade Management (Trailing Stop)
            open_trades_brain = brain.get_open_trades()
            for ot in open_trades_brain:
                ticket_int = int(ot['ticket'])
                mt5_positions = mt5.positions_get(ticket=ticket_int)
                if mt5_positions:
                    pos = mt5_positions[0]
                    profit, entry_price, current_sl = pos.profit, pos.price_open, pos.sl
                    
                    # Break Even
                    if profit > 0.50 and current_sl != entry_price:
                        mt5.OrderSend({"action": mt5.TRADE_ACTION_SLTP, "position": ticket_int, "sl": entry_price, "tp": pos.tp})
                    
                    # Trailing
                    if profit > 1.00:
                        new_sl = entry_price + (profit - 0.50) if pos.type == 0 else entry_price - (profit - 0.50)
                        if (pos.type == 0 and new_sl > current_sl) or (pos.type == 1 and (new_sl < current_sl or current_sl == 0)):
                            mt5.OrderSend({"action": mt5.TRADE_ACTION_SLTP, "position": ticket_int, "sl": new_sl, "tp": pos.tp})

            # 7. Auto-Trading Execution
            if AUTO_TRADING_ENABLED:
                for asset, signal_data in current_results.items():
                    if signal_data['confidence'] >= 90:
                        is_forex = any(p in asset for p in ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"])
                        if is_open or is_forex:
                            in_blackout, _ = news.is_news_blackout(symbol=asset)
                            
                            # Aggressive: Correlation Filter
                            is_corr, corr_sym = is_correlated_open(asset, GLOBAL_CACHE["open_positions"])
                            
                            if not in_blackout and not is_corr:
                                await execute_trade(TradeRequest(
                                    symbol=asset, type=signal_data['signal'], volume=0.01,
                                    amount=CURRENT_COMPOUND_AMOUNT, sl=signal_data['sl'], tp=signal_data['tp'],
                                    strategy=signal_data['strategy'], confidence=signal_data['confidence'],
                                    elite_score=signal_data.get('elite_score', 0)
                                ))

            # 8. Compounding
            history_recent = bridge.get_history(count=10)
            for ot in brain.get_open_trades():
                t_id = str(ot['ticket'])
                for deal in history_recent:
                    if str(deal.get('ticket')) == t_id:
                        p = deal['profit']
                        if p > 0:
                            CURRENT_COMPOUND_AMOUNT += p
                        else:
                            CURRENT_COMPOUND_AMOUNT = INVESTMENT_AMOUNT
                        save_config()
                        brain.update_trade_outcome(t_id, "WIN" if p > 0 else "LOSS")
                        await telegram.send_outcome_report(ot['symbol'], "WIN" if p > 0 else "LOSS", p, ot['strategy'], CURRENT_COMPOUND_AMOUNT)
                        break

            # 9. Telegram Heartbeat (Hourly)
            global LAST_HEARTBEAT
            now_time = datetime.now()
            if 'LAST_HEARTBEAT' not in globals() or (now_time - LAST_HEARTBEAT).total_seconds() >= 3600:
                LAST_HEARTBEAT = now_time
                await telegram.send_heartbeat(GLOBAL_CACHE["real_balance"], GLOBAL_CACHE["scan_count"], GLOBAL_CACHE["is_open"])
                logger.info("💓 [SYSTEM] Telegram heartbeat sent.")

            GLOBAL_CACHE["last_update"] = now_time.strftime("%H:%M:%S")
            
        except Exception as e:
            logger.error(f"❌ Background Loop Error: {e}")
            GLOBAL_CACHE["currently_scanning"] = "Error en ciclo"
            
        await asyncio.sleep(5) # Faster cycle to keep status alive

# FastAPI lifepan and app are now at the top

@app.get("/analysis")
async def get_daily_analysis():
    # Return immediately from cache
    upcoming_news = []
    try: upcoming_news = news.get_upcoming_events(hours_ahead=24)
    except: pass

    return {
        "status": "SUCCESS",
        "scan_count": GLOBAL_CACHE["scan_count"],
        "currently_scanning": GLOBAL_CACHE["currently_scanning"],
        "all_scores": GLOBAL_CACHE["all_scores"],
        "elite_symbols": GLOBAL_CACHE["elite_symbols"],
        "real_balance": GLOBAL_CACHE["real_balance"],
        "open_positions": GLOBAL_CACHE["open_positions"],
        "results": GLOBAL_CACHE["results"],
        "history": bridge.get_history(),
        "market_session": {"is_open": GLOBAL_CACHE["is_open"], "message": GLOBAL_CACHE["session_msg"]},
        "last_scan": GLOBAL_CACHE["last_update"],
        "auto_trading": {
            "enabled": AUTO_TRADING_ENABLED,
            "base_amount": INVESTMENT_AMOUNT,
            "current_amount": CURRENT_COMPOUND_AMOUNT,
            "last_outcome": LAST_OUTCOME
        },
        "upcoming_news": upcoming_news
    }

@app.post("/trade")
async def execute_trade(request: TradeRequest):
    # ... existing implementation (mostly same)
    global CURRENT_COMPOUND_AMOUNT, LAST_OUTCOME
    real_balance = bridge.get_balance()
    if real_balance < request.amount:
        return {"status": "ERROR", "message": f"Fondos insuficientes"}

    if not bridge.connected and not bridge.connect():
        raise HTTPException(status_code=500, detail="Error de conexión MT5")
    
    trade_result = bridge.execute_trade(request.symbol, request.type, request.volume, sl=request.sl, tp=request.tp)
    if trade_result.get("status") == "error":
        return {"status": "ERROR", "message": trade_result.get("message")}

    ticket = trade_result.get("order_id", "N/A")
    global LAST_TICKET
    LAST_TICKET = str(ticket)
    LAST_OUTCOME = "WAITING_RESULT"
    
    if ticket != "N/A":
        try:
            await telegram.send_execution_alert(request.symbol, request.type, 0.0, request.strategy, request.confidence, request.elite_score)
            brain.log_trade_start(str(ticket), request.symbol, request.type, 0.0, {"strategy": request.strategy})
        except: pass

    return {**trade_result, "balance": bridge.get_balance(), "outcome": LAST_OUTCOME, "next_amount": CURRENT_COMPOUND_AMOUNT, "ticket": ticket}

@app.post("/test-trade")
async def execute_test_trade():
    logger.info("🧪 [TEST] Iniciando orden de prueba de $2...")
    # Shortcut logic
    try:
        tick = mt5.symbol_info_tick("EURUSD#")
        if not tick: return {"status": "ERROR", "message": "No tick"}
        price = tick.ask
        test_req = TradeRequest(symbol="EURUSD", type="BUY", volume=0.01, amount=2.0, strategy="TEST_VERIFICATION", confidence=99.9, elite_score=100.0, sl=price-0.0010, tp=price+0.0010)
        return await execute_trade(test_req)
    except Exception as e: return {"status": "ERROR", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
