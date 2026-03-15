import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from mt4_bridge import MT4Bridge
import MetaTrader5 as mt5

def test_bridge():
    print("Testing MT4Bridge...")
    bridge = MT4Bridge()
    if not bridge.connect():
        print("❌ Failed to connect to MT5. Make sure MT5 is open.")
        return False
    
    print("✅ Connected to MT5.")
    
    print("\nTesting get_all_symbols()...")
    symbols = bridge.get_all_symbols()
    print(f"Total symbols found: {len(symbols)}")
    print(f"Symbols: {symbols}")
    
    if len(symbols) > 0:
        print("✅ Symbols retrieved successfully.")
    else:
        print("⚠️ No symbols retrieved. Check if your broker supports the preferred list.")

    print("\nTesting _resolve_symbol()...")
    test_cases = ["EURUSD", "XAUUSD", "NAS100", "SPX500", "US30", "GER40"]
    for case in test_cases:
        resolved = bridge._resolve_symbol(case)
        print(f"  {case} -> {resolved}")
    
    mt5.shutdown()
    return True

if __name__ == "__main__":
    test_bridge()
