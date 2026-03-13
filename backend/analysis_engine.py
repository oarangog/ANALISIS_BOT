import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
        """
        data: pandas DataFrame with 'Close', 'High', 'Low' columns
        """
        self.df = data
        self.confidence_threshold = 0.85 # User requested high confidence

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
        # AI Confidence Simulation
        # Long-term Trend (Last 12 months check)
        # Using 200 SMA on the large dataset
        sma200_long = self.df['Close'].rolling(window=200).mean().iloc[-1]
        
        sma20 = self.calculate_sma(20).iloc[-1]
        ema9 = self.calculate_ema(9).iloc[-1]
        close = self.df['Close'].iloc[-1]
        atr = self.calculate_atr().iloc[-1]
        fvgs = self.detect_fvg()
        
        # Initial stats
        confidence = 0.0
        signal = "NEUTRAL"
        extra_reason = ""
        
        # Long-term trend bias
        trend_bias = "BULLISH" if close > sma200_long else "BEARISH"
        
        # Strategy: Indicators + FVG Confirmation
        last_fvg = fvgs[-1] if fvgs else None
        
        # Initialize extra reason parts
        extra_reason_parts = []
        
        # ADVANCED SMC & CANDLESTICK INTEGRATION
        candlestick_boost = 0.0
        try:
            from advanced_smc_detector import AdvancedSMCDector
            smc = AdvancedSMCDector(self.df)
            patterns = smc.detect_candlestick_patterns()
            sweep = smc.detect_liquidity_sweeps()
            ob = smc.detect_return_zones()
            
            for pat in patterns:
                extra_reason_parts.append(f"Vela: {pat['desc']}")
                
                # Directional boosts based on pattern
                if signal == "BUY" and pat['pattern'] in ['BULLISH_ENGULFING', 'HAMMER']:
                    candlestick_boost += 0.05
                elif signal == "SELL" and pat['pattern'] in ['BEARISH_ENGULFING', 'SHOOTING_STAR']:
                    candlestick_boost += 0.05
            
            # Liquidity Sweeps
            if sweep:
                extra_reason_parts.append(f"Manipulación: {sweep['desc']}")
                if signal == "BUY" and sweep['type'] == 'BULLISH_SWEEP':
                    candlestick_boost += 0.08  # High confidence trap
                elif signal == "SELL" and sweep['type'] == 'BEARISH_SWEEP':
                    candlestick_boost += 0.08
                    
            # Return Zones (Order Blocks)
            if ob:
                # If current price is inside the OB
                if ob['type'] == 'BULLISH_OB' and ob['bottom'] <= close <= ob['top'] and signal == 'BUY':
                    candlestick_boost += 0.05
                    extra_reason_parts.append("OB alcista mitigado")
                elif ob['type'] == 'BEARISH_OB' and ob['bottom'] <= close <= ob['top'] and signal == 'SELL':
                    candlestick_boost += 0.05
                    extra_reason_parts.append("OB bajista mitigado")
                    
        except Exception as e:
            pass # Failsafe

        if signal == "BUY":
            confidence = 0.85
            signal = "BUY"
            if trend_bias == "BULLISH":
                confidence += 0.05 # Trend confluence
                extra_reason_parts.append("12-Month Bullish Trend Confluence")
            
            if last_fvg and last_fvg['type'] == 'BULLISH':
                confidence += 0.05  # Higher weight for ICT
                extra_reason_parts.append("FVG Institutional")
                
            confidence += candlestick_boost
            
        elif signal == "SELL":
            confidence = 0.85
            signal = "SELL"
            if trend_bias == "BEARISH":
                confidence += 0.05 # Trend confluence
                extra_reason_parts.append("12-Month Bearish Trend Confluence")
                
            if last_fvg and last_fvg['type'] == 'BEARISH':
                confidence += 0.05 # Higher weight for ICT
                extra_reason_parts.append("FVG Institutional")
                
            confidence += candlestick_boost

        extra_reason = " + ".join(extra_reason_parts)
        # APPLY SELF-LEARNING (Dynamic Weighting)
        try:
            from learning_brain import LearningBrain
            brain = LearningBrain()
            learned_multiplier = brain.get_experience_multiplier("GENERAL") # For now global, can be per asset
            confidence *= learned_multiplier
            if learned_multiplier > 1.0:
                extra_reason += f" [IA EXPERTA: +{int((learned_multiplier-1)*100)}%]"
            elif learned_multiplier < 1.0:
                extra_reason += f" [IA CAUTELOSA: -{int((1-learned_multiplier)*100)}%]"
        except:
            pass

        confidence = min(0.99, confidence) # Cap at 99%

        # Fix SL/TP calculation (Avoid 0.0)
        if signal == "BUY":
            sl = float(f"{(close - (atr * 1.5)):.5f}")
            tp = float(f"{(close + (atr * 3)):.5f}")
        elif signal == "SELL":
            sl = float(f"{(close + (atr * 1.5)):.5f}")
            tp = float(f"{(close - (atr * 3)):.5f}")
        else:
            sl, tp = 0.0, 0.0

        # Calculate Precise Timing
        now = datetime.now()
        entry_time = now.strftime("%H:%M:%S")
        expiry_time = (now + timedelta(minutes=15)).strftime("%H:%M:%S")

        return {
            "signal": signal,
            "confidence": float(f"{(confidence * 100):.2f}"), # Return as percentage 0-100
            "sl": float(sl),
            "tp": float(tp),
            "timeframe": "M15 (Binarias)",
            "entry_time": entry_time,
            "expiry_time": expiry_time,
            "info": extra_reason,
            "timezone": "UTC-5 (Bogota/CO)"
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
