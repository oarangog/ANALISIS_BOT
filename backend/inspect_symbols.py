import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

load_dotenv()

def list_all_symbols():
    if not mt5.initialize():
        print("initialize() failed")
        return

    symbols = mt5.symbols_get()
    print(f"Total symbols: {len(symbols)}")
    
    print("\nLooking for potential candidates:")
    candidates = []
    for s in symbols:
        name = s.name.upper()
        # Common metals/indices patterns
        if any(x in name for x in ["GOLD", "SILVER", "XAU", "XAG", "US100", "US500", "US30", "GER40", "NAS100", "SPX500", "DAX"]):
            candidates.append(s.name)
            
    # Also look for anything with Cash# if that's a common suffix
    for s in symbols:
        if "CASH#" in s.name.upper() and s.name not in candidates:
            candidates.append(s.name)
            
    for c in sorted(candidates):
        print(f"  {c}")
            
    mt5.shutdown()

if __name__ == "__main__":
    list_all_symbols()
