import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

class AnalysisEngine:
    def __init__(self, data):
        """
        data: pandas DataFrame with 'Close', 'High', 'Low' columns
        """
        self.df = data
        self.confidence_threshold = 0.90 # User requested 90% confidence

    def calculate_sma(self, period=20):
        return self.df['Close'].rolling(window=period).mean()

    def calculate_ema(self, period=9):
        return self.df['Close'].ewm(span=period, adjust=False).mean()

    def calculate_atr(self, period=14):
        high_low = self.df['High'] - self.df['Low']
        high_close = np.abs(self.df['High'] - self.df['Close'].shift())
        low_close = np.abs(self.df['Low'] - self.df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()

    def calculate_fibonacci(self, high, low):
        diff = high - low
        levels = {
            '0.0': high,
            '38.2': high - 0.382 * diff,
            '50.0': high - 0.5 * diff,
            '61.8': high - 0.618 * diff,
            '100.0': low
        }
        return levels

    def calculate_bollinger_bands(self, period=20, std_dev=2):
        """
        Calculate Bollinger Bands as per ERS RF-008
        """
        sma = self.df['Close'].rolling(window=period).mean()
        std = self.df['Close'].rolling(window=period).std()
        self.df['BB_Upper'] = sma + (std * std_dev)
        self.df['BB_Lower'] = sma - (std * std_dev)
        return self.df['BB_Upper'], self.df['BB_Lower']

    def detect_fvg(self):
        """
        Detect Fair Value Gaps (FVG)
        """
        fvgs = []
        for i in range(2, len(self.df)):
            # Bullish FVG
            if self.df['Low'].iloc[i] > self.df['High'].iloc[i-2]:
                fvgs.append({'type': 'BULLISH', 'top': self.df['Low'].iloc[i], 'bottom': self.df['High'].iloc[i-2]})
            # Bearish FVG
            elif self.df['High'].iloc[i] < self.df['Low'].iloc[i-2]:
                fvgs.append({'type': 'BEARISH', 'top': self.df['Low'].iloc[i-2], 'bottom': self.df['High'].iloc[i]})
        return fvgs

    def detect_order_blocks(self):
        """
        Simplified Order Block detection
        """
        # Logic: Looking for a sharp move that breaks structure
        return "Not implemented - requires volume data"

    def get_signals(self):
        """
        Refined signal generation with multi-confluence and proper logic flow.
        1. Establish Trend/Momentum Bias
        2. Detect SMC/Candlestick Patterns
        3. Apply Confluences (BB, Fibonacci)
        4. Calculate Confidence and Final Signal
        """
        # 1. BASE BIAS (Trend & Momentum)
        sma200 = self.df['Close'].rolling(window=200).mean().iloc[-1]
        sma20 = self.calculate_sma(20).iloc[-1]
        ema9 = self.calculate_ema(9).iloc[-1]
        close = self.df['Close'].iloc[-1]
        atr = self.calculate_atr().iloc[-1]
        
        # Bias based on 200 SMA and 9/20 EMA cross
        trend_bias = "BULLISH" if close > sma200 else "BEARISH"
        momentum = "BULLISH" if close > ema9 > sma20 else ("BEARISH" if close < ema9 < sma20 else "NEUTRAL")
        
        # 2. POTENTIAL SIGNAL IDENTIFICATION
        # We start with a potential signal if momentum and trend align or if there's a strong rejection
        potential_signal = "NEUTRAL"
        if momentum == trend_bias:
            potential_signal = trend_bias
        
        confidence = 0.0
        extra_reason_parts = []
        score_components = 0 # Track how many different strategies align
        
        # 3. ADVANCED DETECTION (SMC & CANDLESTICK)
        # Initialize to safe defaults before try block (fix: C4 undefined vars outside try)
        sweep = None
        ob = None
        last_fvg = None
        patterns = []
        try:
            from advanced_smc_detector import AdvancedSMCDector
            smc = AdvancedSMCDector(self.df)
            patterns = smc.detect_candlestick_patterns()
            sweep = smc.detect_liquidity_sweeps()
            ob = smc.detect_return_zones()
            fvgs = self.detect_fvg()
            last_fvg = fvgs[-1] if fvgs else None
            
            # --- Candlestick Patterns ---
            if patterns:
                for pat in patterns:
                    if (pat['pattern'] in ['BULLISH_ENGULFING', 'HAMMER'] and trend_bias == "BULLISH") or \
                       (pat['pattern'] in ['BEARISH_ENGULFING', 'SHOOTING_STAR'] and trend_bias == "BEARISH"):
                        confidence += 0.15
                        score_components += 1
                        extra_reason_parts.append(f"Vela: {pat['desc']}")
            
            # --- Liquidity Sweeps (Strong Reversal Signal) ---
            if sweep:
                if sweep['type'] == 'BULLISH_SWEEP' and trend_bias == "BULLISH":
                    confidence += 0.20
                    score_components += 1
                    potential_signal = "BULLISH" # Reversal can override neutral momentum
                    extra_reason_parts.append(f"Caza de Liquidez Alcista")
                elif sweep['type'] == 'BEARISH_SWEEP' and trend_bias == "BEARISH":
                    confidence += 0.20
                    score_components += 1
                    potential_signal = "BEARISH"
                    extra_reason_parts.append(f"Caza de Liquidez Bajista")
                    
            # --- Order Blocks & FVG (Institutional) ---
            if ob:
                if ob['type'] == 'BULLISH_OB' and ob['bottom'] <= close <= (ob['top'] + atr*0.2):
                    confidence += 0.15
                    score_components += 1
                    extra_reason_parts.append("Zona de Oferta/Demanda (OB)")
                elif ob['type'] == 'BEARISH_OB' and (ob['bottom'] - atr*0.2) <= close <= ob['top']:
                    confidence += 0.15
                    score_components += 1
                    extra_reason_parts.append("Zona de Oferta/Demanda (OB)")
            
            if last_fvg:
                if last_fvg['type'] == 'BULLISH' and close > last_fvg['bottom']:
                    confidence += 0.10
                    score_components += 1
                    extra_reason_parts.append("Imbalance FVG Alcista")
                elif last_fvg['type'] == 'BEARISH' and close < last_fvg['top']:
                    confidence += 0.10
                    score_components += 1
                    extra_reason_parts.append("Imbalance FVG Bajista")

            # --- Confluences (BB & Fib) ---
            bb_upper, bb_lower = self.calculate_bollinger_bands()
            if close <= bb_lower.iloc[-1]:
                confidence += 0.10
                extra_reason_parts.append("Sobrevendido (BB)")
            elif close >= bb_upper.iloc[-1]:
                confidence += 0.10
                extra_reason_parts.append("Sobrecomprado (BB)")

            # Fibonacci 61.8% (Golden Zone) of recent move
            swing_high = self.df['High'].tail(50).max()
            swing_low = self.df['Low'].tail(50).min()
            fib_levels = self.calculate_fibonacci(swing_high, swing_low)
            if abs(close - fib_levels['61.8']) / close < 0.002: # 0.2% tolerance
                confidence += 0.10
                extra_reason_parts.append("Nivel Fibonacci 61.8%")

        except Exception as e:
            print(f"⚠️ Analysis Engine Sub-module Error: {e}")

        # 4. BACKTEST VALIDATION (New Elite Logic)
        backtest_success = 0.0
        try:
            from backtester import Backtester
            bt = Backtester(self.df)
            # Validate how many times similar setups worked recently
            bt_results = bt.run_quick_test(None, periods=100)
            backtest_success = bt_results.get("win_rate", 0)
            if backtest_success > 90:
                confidence += 0.05
                extra_reason_parts.append(f"Éxito Histórico Probado: {backtest_success}%")
            elif backtest_success < 75:
                confidence *= 0.90 # Penalize unstable assets
        except:
            pass

        # 5. FINAL CALCULATION
        # Base confidence for trend alignment
        if potential_signal != "NEUTRAL":
            confidence += 0.40 # Base weight for trend + momentum
        
        # SELF-LEARNING ADJUSTMENT
        # Determine current primary strategy for weighting
        if sweep:
            strategy_type = "REVERSAL_SWEEP"
        elif ob or last_fvg:
            strategy_type = "INSTITUTIONAL_SMC"
        elif score_components > 0:
            strategy_type = "INDICATOR_CONFLUENCE"
        else:
            strategy_type = "TREND_FOLLOWING"

        try:
            from learning_brain import LearningBrain
            brain = LearningBrain()
            # Fix C3: use actual symbol from context, not "GENERAL"
            # We use a symbol key from the dataframe name or object if available
            symbol_key = getattr(self.df, 'name', None) or getattr(self, 'symbol', 'GENERAL')
            learned_multiplier = brain.get_experience_multiplier(symbol_key, strategy_type)
            confidence *= learned_multiplier
            if learned_multiplier > 1.05:
                extra_reason_parts.append(f"IA Optimizada ({strategy_type}: +{int((learned_multiplier-1)*100)}%)")
        except:
            pass

        # Final Signal Decision
        final_signal = "NEUTRAL"
        if confidence >= 0.85 and potential_signal != "NEUTRAL":
            # Require at least 2 confirming score components or high backtest success
            if score_components >= 2 or backtest_success > 90:
                final_signal = "BUY" if potential_signal == "BULLISH" else "SELL"
            else:
                # Moderate confidence - check if it hits the 90% floor
                if confidence >= 0.90:
                     final_signal = "BUY" if potential_signal == "BULLISH" else "SELL"
        
        # 6. ELITE SCORE (For Top 5 Selection)
        # Combination of Confidence + Backtest Success + Volatility Stability
        # Volatility index (lower is better for stability)
        volatility = atr / close if close > 0 else 1
        stability_score = max(0, 100 - (volatility * 10000))
        
        elite_score = (confidence * 50) + (backtest_success * 0.3) + (stability_score * 0.2) if final_signal != "NEUTRAL" else 0
        
        # 7. STRUCTURAL SL/TP
        if final_signal == "BUY":
            # SL below recent low or OB bottom, whichever is more structural
            swing_low_local = self.df['Low'].tail(20).min()
            sl = min(swing_low_local, close - (atr * 2))
            tp = close + (abs(close - sl) * 2.5) # Risk-Reward 1:2.5
        elif final_signal == "SELL":
            swing_high_local = self.df['High'].tail(20).max()
            # Fix C5: For SELL, SL should be ABOVE current price.
            # min() of close+ATR*2 and swing_high gives wrong result; use max() for SELL SL
            sl = max(swing_high_local, close + (atr * 1.5))
            tp = close - (abs(sl - close) * 2.0) # Risk-Reward 1:2
        else:
            sl, tp = 0.0, 0.0

        extra_reason = " | ".join(extra_reason_parts) if extra_reason_parts else "Analizando mercado..."

        return {
            "signal": final_signal,
            "confidence": float(f"{min(99.9, confidence * 100):.2f}"),
            "elite_score": round(elite_score, 2),
            "backtest_winrate": backtest_success,
            "sl": float(f"{sl:.5f}"),
            "tp": float(f"{tp:.5f}"),
            "timeframe": "Calculado",
            "info": extra_reason,
            "trend": trend_bias,
            "strategy": strategy_type,
            "status": "ACTIVE" if final_signal != "NEUTRAL" else "WAITING"
        }

if __name__ == "__main__":
    # Mock data for testing
    data = {
        'Close': [1.1000 + i*0.0001 for i in range(50)],
        'High': [1.1005 + i*0.0001 for i in range(50)],
        'Low': [1.0995 + i*0.0001 for i in range(50)]
    }
    df = pd.DataFrame(data)
    engine = AnalysisEngine(df)
    print(f"Signal Result: {engine.get_signals()}")
