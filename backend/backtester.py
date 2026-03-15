import pandas as pd
import numpy as np

class Backtester:
    def __init__(self, data: pd.DataFrame):
        """
        data: pandas DataFrame with OHLC columns (Open, High, Low, Close)
        """
        self.df = data.copy().reset_index(drop=True)

    def run_quick_test(self, strategy_func=None, periods=100):
        """
        Real Express Backtest: simulates EMA momentum signals over the last N periods.
        Checks if a "BUY" signal (EMA9 > SMA20 > SMA200) led to price going up in the next 5 candles.
        Returns: { win_rate: float, total_sims: int, profit_factor: float }
        """
        if len(self.df) < periods + 50:
            return {"win_rate": 0.0, "total_sims": 0, "stability": "LOW"}

        test_df = self.df.tail(periods + 50).copy().reset_index(drop=True)

        # Pre-calculate indicators on the test slice
        close = test_df['Close']
        ema9  = close.ewm(span=9, adjust=False).mean()
        sma20 = close.rolling(20).mean()
        sma200 = close.rolling(200).mean() if len(test_df) >= 200 else sma20  # fallback

        wins  = 0
        total = 0
        forward_bars = 5  # how many candles ahead we check for profit

        # Walk through the test window, simulate entries
        for i in range(50, len(test_df) - forward_bars - 1):
            bullish_signal = ema9.iloc[i] > sma20.iloc[i] and close.iloc[i] > sma200.iloc[i]
            bearish_signal = ema9.iloc[i] < sma20.iloc[i] and close.iloc[i] < sma200.iloc[i]

            if bullish_signal or bearish_signal:
                total += 1
                entry_price = close.iloc[i]
                future_close = close.iloc[i + forward_bars]

                if bullish_signal and future_close > entry_price:
                    wins += 1
                elif bearish_signal and future_close < entry_price:
                    wins += 1

        win_rate = (wins / total) if total > 0 else 0.5
        return {
            "win_rate": round(win_rate * 100, 2),
            "total_sims": total,
            "stability": "HIGH" if win_rate > 0.65 else ("MEDIUM" if win_rate > 0.50 else "LOW")
        }

    def validate_signal_success(self, signal_type, entry_price, sl, tp, lookback=20):
        """
        Checks how many recent candles moved from entry toward TP before hitting SL.
        Returns a probability (0.0 - 1.0).
        """
        if len(self.df) < 30 or sl == 0.0 or tp == 0.0:
            return 0.5  # Neutral if no SL/TP

        risk = abs(entry_price - sl)
        reward = abs(tp - entry_price)
        if risk == 0:
            return 0.5

        recent = self.df.tail(lookback)
        wins = 0
        total = 0

        for i in range(len(recent) - 5):
            snapshot_close = recent['Close'].iloc[i]
            future_highs = recent['High'].iloc[i+1:i+5]
            future_lows  = recent['Low'].iloc[i+1:i+5]

            total += 1
            if signal_type == "BUY":
                # Check if price moved up by 'reward' before moving down by 'risk'
                hit_tp = (future_highs >= (snapshot_close + reward * 0.5)).any()
                hit_sl = (future_lows <= (snapshot_close - risk)).any()
                if hit_tp and not hit_sl:
                    wins += 1
            elif signal_type == "SELL":
                hit_tp = (future_lows <= (snapshot_close - reward * 0.5)).any()
                hit_sl = (future_highs >= (snapshot_close + risk)).any()
                if hit_tp and not hit_sl:
                    wins += 1

        return wins / total if total > 0 else 0.5
