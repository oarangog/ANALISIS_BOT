import pandas as pd
import numpy as np

class AdvancedSMCDector:
    def __init__(self, data: pd.DataFrame):
        """
        data: pandas DataFrame with 'Open', 'High', 'Low', 'Close'
        """
        self.df = data

    def detect_candlestick_patterns(self):
        """
        Detects primary Candlestick patterns (from 'La Biblia del Trading con Velas')
        Returns a list of patterns found on the most recent completed candle.
        """
        patterns = []
        if len(self.df) < 3:
            return patterns

        # Get the last two candles
        current = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        # Calculate bodies and shadows for Current
        body_curr = abs(current['Close'] - current['Open'])
        upper_shadow_curr = current['High'] - max(current['Open'], current['Close'])
        lower_shadow_curr = min(current['Open'], current['Close']) - current['Low']
        total_size_curr = current['High'] - current['Low']
        
        is_bullish_curr = current['Close'] > current['Open']
        
        # Calculate bodies for Previous
        body_prev = abs(prev['Close'] - prev['Open'])
        is_bullish_prev = prev['Close'] > prev['Open']

        # 1. Engulfing (Envolvente)
        if body_curr > body_prev and is_bullish_curr != is_bullish_prev:
            if is_bullish_curr and current['Close'] >= prev['Open'] and current['Open'] <= prev['Close']:
                patterns.append({'pattern': 'BULLISH_ENGULFING', 'weight': 1.5, 'desc': 'Vela Envolvente Alcista'})
            elif not is_bullish_curr and current['Close'] <= prev['Open'] and current['Open'] >= prev['Close']:
                patterns.append({'pattern': 'BEARISH_ENGULFING', 'weight': 1.5, 'desc': 'Vela Envolvente Bajista'})

        # 2. Hammer / Pin Bar (Martillo / Pin) - Bulllish Reversal
        if lower_shadow_curr > (body_curr * 2) and upper_shadow_curr < (body_curr * 0.5):
            patterns.append({'pattern': 'HAMMER', 'weight': 1.0, 'desc': 'Pin Bar / Martillo Alcista'})

        # 3. Shooting Star (Estrella Fugaz) - Bearish Reversal
        if upper_shadow_curr > (body_curr * 2) and lower_shadow_curr < (body_curr * 0.5):
            patterns.append({'pattern': 'SHOOTING_STAR', 'weight': 1.0, 'desc': 'Estrella Fugaz Bajista'})

        # 4. Doji (Indecisión/Reversión)
        if total_size_curr > 0 and (body_curr / total_size_curr) < 0.1:
            patterns.append({'pattern': 'DOJI', 'weight': 0.5, 'desc': 'Doji (Giro Inminente)'})

        return patterns

    def detect_bos(self, lookback=50):
        """
        Detects Break of Structure (BOS)
        A BOS occurs when price closes beyond a previous swing high/low.
        """
        if len(self.df) < lookback + 5:
            return None
            
        # Identify previous major swing high/low
        prev_swing_high = self.df['High'].iloc[-lookback:-5].max()
        prev_swing_low = self.df['Low'].iloc[-lookback:-5].min()
        
        last_close = self.df['Close'].iloc[-1]
        
        if last_close > prev_swing_high:
            return {'type': 'BOS_UP', 'level': prev_swing_high}
        elif last_close < prev_swing_low:
            return {'type': 'BOS_DOWN', 'level': prev_swing_low}
            
        return None

    def detect_liquidity_sweeps(self, lookback=20):
        """
        Detects Manipulations / Stop Hunts / Liquidity Sweeps
        """
        if len(self.df) < lookback + 2:
            return None

        current_candle = self.df.iloc[-1]
        recent_high = self.df['High'].iloc[-lookback:-1].max()
        recent_low = self.df['Low'].iloc[-lookback:-1].min()

        # Check for Sweep of Highs
        if current_candle['High'] > recent_high and current_candle['Close'] < recent_high:
            return {'type': 'BEARISH_SWEEP', 'desc': 'Caza de Stops en Máximos', 'level': recent_high}

        # Check for Sweep of Lows
        if current_candle['Low'] < recent_low and current_candle['Close'] > recent_low:
            return {'type': 'BULLISH_SWEEP', 'desc': 'Caza de Stops en Mínimos', 'level': recent_low}

        return None

    def detect_liquidity_targets(self, lookback=50):
        """
        Detects Equal Highs (EQH) or Equal Lows (EQL) that act as price magnets.
        """
        # Simplified: look for levels hit multiple times but not broken
        highs = self.df['High'].tail(lookback)
        lows = self.df['Low'].tail(lookback)
        
        # This would require more complex grouping logic, for now we skip or mock
        return None

    def detect_return_zones(self, lookback=50):
        """
        Refined Order Block detection: only valid if it lead to a BOS or strong impulse.
        """
        zones = []
        if len(self.df) < lookback:
            return None
            
        # Detect if we have a current BOS to validate an OB
        bos = self.detect_bos(lookback)
        
        for i in range(len(self.df) - lookback, len(self.df) - 5):
            c1 = self.df.iloc[i]
            c2 = self.df.iloc[i+1]
            c3 = self.df.iloc[i+2]
            
            # BULLISH OB: Last down candle before strong up move
            if c1['Close'] < c1['Open'] and c2['Close'] > c2['Open'] and c3['Close'] > c3['Open']:
                # Strong push validation
                if (c3['Close'] - c1['Low']) > (c1['Open'] - c1['Low']) * 3:
                     # If we have a BOS UP recently, this OB is high probability
                     prob = 1.5 if (bos and bos['type'] == 'BOS_UP') else 1.0
                     zones.append({'type': 'BULLISH_OB', 'top': c1['Open'], 'bottom': c1['Low'], 'probability': prob})
            
            # BEARISH OB: Last up candle before strong down move
            if c1['Close'] > c1['Open'] and c2['Close'] < c2['Open'] and c3['Close'] < c3['Open']:
                if (c1['High'] - c3['Close']) > (c1['High'] - c1['Open']) * 3:
                     prob = 1.5 if (bos and bos['type'] == 'BOS_DOWN') else 1.0
                     zones.append({'type': 'BEARISH_OB', 'top': c1['High'], 'bottom': c1['Open'], 'probability': prob})

        if zones:
            # Sort by proximity to current price and probability
            return zones[-1]
        return None
