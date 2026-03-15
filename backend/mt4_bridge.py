import os
import MetaTrader5 as mt5
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

class MT4Bridge:
    def __init__(self):
        self.login = int(os.getenv("VITE_MT4_LOGIN", 0))
        self.password = os.getenv("VITE_MT4_PASSWORD")
        self.server = os.getenv("VITE_MT4_SERVER")
        self.path = os.getenv("VITE_MT5_PATH")
        self.connected = False

    def connect(self):
        # Try to initialize MT5 with explicit path
        print(f"Connecting to MetaTrader 5 at: {self.path}...")
        
        init_args = {}
        if self.path:
            init_args["path"] = self.path
            
        if not mt5.initialize(**init_args):
            error = mt5.last_error()
            print(f"❌ mt5.initialize() failed, error code = {error}")
            if error[0] == -10005:
                print("💡 TIP: Asegúrate de que MetaTrader 5 esté ABIERTO.")
            elif error[0] == -6:
                print("💡 TIP: Error de Autorización. Verifica tu Login/Password en el archivo .env")
            return False
        
        # login to account
        authorized = mt5.login(self.login, password=self.password, server=self.server)
        if authorized:
            print(f"✅ Connected to MT5 Account: {self.login}")
            self.connected = True
            return True
        else:
            print(f"❌ Failed to connect to account {self.login}, error code = {mt5.last_error()}")
            return False

    def get_balance(self):
        if not self.connected and not self.connect():
            return 0.0
        account_info = mt5.account_info()
        if account_info is None:
            return 0.0
        return account_info.balance

    def _resolve_symbol(self, symbol):
        """
        Detects the real symbol name in MT5 and ensures it's active in Market Watch
        Handles common aliases (NAS100 -> US100, SPX500 -> US500, XAUUSD -> GOLD)
        """
        if not self.connected and not self.connect():
            return symbol
            
        # Try exact match first
        sym = mt5.symbol_info(symbol)
        if sym:
            if not sym.visible:
                mt5.symbol_select(sym.name, True)
            return sym.name
            
        # Common Aliases (Broker specific naming)
        aliases = {
            "NAS100": "US100",
            "SPX500": "US500",
            "XAUUSD": "GOLD",
            "XAGUSD": "SILVER",
            "US30": "US30",
            "GER40": "GER40"
        }
        
        search_names = [symbol]
        if symbol in aliases:
            search_names.append(aliases[symbol])
            
        # Common Forex/CFD suffixes (Priority order)
        suffixes = ["Cash#", "#", "Cash", "+", ".m", ".i", "_i", ".st", ".pro", ""]
        
        for name in search_names:
            for suffix in suffixes:
                candidate = name + suffix
                sym_s = mt5.symbol_info(candidate)
                if sym_s:
                    if not sym_s.visible:
                        mt5.symbol_select(sym_s.name, True)
                    return sym_s.name
                
        # Search for any symbol containing the base name or alias
        # Priority: Symbols ending in Cash# or #
        for name in search_names:
            found = mt5.symbols_get(group=f"*{name}*")
            if found:
                # Filter for trading-like symbols first
                trading_symbols = [s.name for s in found if s.name.endswith("#") or "Cash" in s.name]
                if trading_symbols:
                    # Pick the shortest or most 'cash-like'
                    res = sorted(trading_symbols, key=len)[0]
                else:
                    res = found[0].name
                    
                if not mt5.symbol_info(res).visible:
                    mt5.symbol_select(res, True)
                print(f"🔍 Symbol resolved (Smart Pattern {name}): {symbol} -> {res}")
                return res
            
        print(f"⚠️ Symbol NOT resolved: {symbol}. Using as is.")
        return symbol

    def get_historical_data(self, symbol, timeframe=mt5.TIMEFRAME_M15, count=1000):
        """
        Fetch historical bars from MT5
        """
        if not self.connected and not self.connect():
            return None
        
        real_symbol = self._resolve_symbol(symbol)
        rates = mt5.copy_rates_from_pos(real_symbol, timeframe, 0, count)
        if rates is None:
            print(f"❌ Failed to fetch rates for {real_symbol}")
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        # Rename columns to match AnalysisEngine expectation
        df = df.rename(columns={'close': 'Close', 'high': 'High', 'low': 'Low', 'open': 'Open'})
        # Store symbol name on DataFrame so AnalysisEngine can pass it to LearningBrain (C3 fix)
        df.name = real_symbol
        return df

    def get_all_symbols(self, group="*", sector=None):
        """
        Returns the 18 preferred assets for the bot as indicated by the user.
        Ensures they are resolved to the broker's specific naming convention.
        """
        preferred = [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", # Forex Majors
            "EURJPY", "GBPJPY",                                              # Forex Minors/Crosses
            "XAUUSD", "XAGUSD",                                              # Metals
            "BTCUSD", "ETHUSD", "LTCUSD",                                    # Crypto
            "US30", "SPX500", "NAS100", "GER40"                               # Indices
        ]
        
        if not self.connected and not self.connect():
            return preferred
            
        resolved_list = []
        for sym in preferred:
            real_name = self._resolve_symbol(sym)
            # Only add if we can actually get info for it (broker supports it)
            info = mt5.symbol_info(real_name)
            if info:
                resolved_list.append(real_name)
                
        return resolved_list

    def get_history(self, count=5):
        """
        Get last N closed trades. Looks back 7 days to catch long-duration trades. (Fix C6)
        """
        if not self.connected and not self.connect():
            return []
            
        from datetime import datetime, timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)  # Was 1 day - now 7 to catch all trades
        
        deals = mt5.history_deals_get(start_time, end_time)
        if deals is None or len(deals) == 0:
            return []
            
        history = []
        # Get elements one by one if slicing causes issues
        count_to_fetch = min(len(deals), count)
        for i in range(len(deals) - count_to_fetch, len(deals)):
            d = deals[i]
            history.append({
                "ticket": d.ticket,
                "symbol": d.symbol,
                "profit": d.profit,
                "type": "BUY" if d.type == mt5.ORDER_TYPE_BUY else "SELL",
                "time": datetime.fromtimestamp(d.time).strftime("%H:%M:%S")
            })
        return history

    def execute_trade(self, symbol, type, volume, price=None, sl=0.0, tp=0.0):
        if not self.connected and not self.connect():
            return {"status": "error", "message": "MT5 Not Connected"}

        real_symbol = self._resolve_symbol(symbol)
        order_type = mt5.ORDER_TYPE_BUY if type == "BUY" else mt5.ORDER_TYPE_SELL
        
        # Get current price if not provided
        if price is None:
            tick = mt5.symbol_info_tick(real_symbol)
            if tick is None:
                return {"status": "error", "message": f"Could not get ticks for {real_symbol}"}
            price = tick.ask if type == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": real_symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "magic": 123456,
            "comment": "ANAILIS BOT LIVE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
             return {"status": "error", "message": "No response from MT5"}
             
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Trade failed for {real_symbol}: {result.comment}")
            return {"status": "error", "message": result.comment}
        
        print(f"✅ Trade Executed: {real_symbol} {type} @ {price}")
        return {"status": "success", "order_id": result.order}

    def shutdown(self):
        mt5.shutdown()
