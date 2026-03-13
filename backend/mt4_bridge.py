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
        Detects the real symbol name in MT5 (handling suffixes like #)
        """
        if not self.connected and not self.connect():
            return symbol
            
        # Try exact match
        sym = mt5.symbol_info(symbol)
        if sym:
            # print(f"🔍 Symbol match: {symbol} -> {sym.name}")
            return sym.name
            
        # Try with # suffix (XM Global style)
        sym_sharp = mt5.symbol_info(symbol + "#")
        if sym_sharp:
            print(f"🔍 Symbol resolved (XM Suffix): {symbol} -> {sym_sharp.name}")
            return sym_sharp.name
            
        # Search for any symbol containing the base name
        found = mt5.symbols_get(group=f"*{symbol}*")
        if found:
            print(f"🔍 Symbol resolved (Pattern): {symbol} -> {found[0].name}")
            return found[0].name
            
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
        return df

    def get_all_symbols(self, group="*", sector=None):
        """
        Get major symbols from MT5
        """
        if not self.connected and not self.connect():
            return []
            
        symbols = mt5.symbols_get(group)
        if symbols is None:
            return []
            
        # Return only a manageable list of symbols
        filtered = []
        for s in symbols:
            if s.visible and ('.com' not in s.name) and (len(s.name) <= 6 or 'USD' in s.name):
                filtered.append(s.name)
        
        # Ensure we don't exceed the list bounds
        return filtered[0:20] 

    def get_history(self, count=5):
        """
        Get last N closed trades
        """
        if not self.connected and not self.connect():
            return []
            
        from datetime import datetime, timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        
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
