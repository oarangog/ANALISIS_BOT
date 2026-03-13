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

    def detect_liquidity_sweeps(self, lookback=20):
        """
        Detects Manipulations / Stop Hunts / Liquidity Sweeps
        A sweep happens when price breaks a recent swing high/low but quickly closes back inside the range.
        """
        if len(self.df) < lookback + 2:
            return None

        current_candle = self.df.iloc[-1]
        
        # Look for swing highs and lows in the lookback period (excluding the current candle)
        recent_high = self.df['High'].iloc[-lookback:-1].max()
        recent_low = self.df['Low'].iloc[-lookback:-1].min()

        # Check for Sweep of Highs (Bearish indication, trapped long traders)
        if current_candle['High'] > recent_high and current_candle['Close'] < recent_high:
            return {'type': 'BEARISH_SWEEP', 'desc': 'Caza de Stops (Liquidity Sweep) en Máximos', 'level': recent_high}

        # Check for Sweep of Lows (Bullish indication, trapped short traders)
        if current_candle['Low'] < recent_low and current_candle['Close'] > recent_low:
            return {'type': 'BULLISH_SWEEP', 'desc': 'Caza de Stops (Liquidity Sweep) en Mínimos', 'level': recent_low}

        return None

    def detect_return_zones(self, lookback=50):
        """
        Detects Order Blocks / Return Zones.
        Finds the last opposite-colored candle before a strong impulsive push that broke structure.
        Simplified version for time-series iteration.
        """
        # For a robust Return Zone, we look back. Usually, the 'fvg' detection in AnalysisEngine
        # helps with determining where the imbalance is. We can enhance it here to find the 
        # actual Order Block box.
        
        # Mock logic to represent standard OB identification (Last down candle before up move)
        # Detailed implementation often requires complex swing/BOS (Break of Structure) analysis.
        zones = []
        if len(self.df) > lookback:
            # We will use simple strong momentum candles as proxies for impulsive moves
            for i in range(len(self.df) - lookback, len(self.df) - 2):
                c1 = self.df.iloc[i]
                c2 = self.df.iloc[i+1]
                c3 = self.df.iloc[i+2]
                
                # Strong Bullish Imbalance (OB is the c1 down candle)
                if c1['Close'] < c1['Open'] and c2['Close'] > c2['Open'] and c3['Close'] > c3['Open']:
                    if (c3['Close'] - c2['Open']) > 2 * abs(c1['Open'] - c1['Close']): # Strong push
                        zones.append({'type': 'BULLISH_OB', 'top': c1['Open'], 'bottom': c1['Low']})
                
                # Strong Bearish Imbalance (OB is the c1 up candle)
                if c1['Close'] > c1['Open'] and c2['Close'] < c2['Open'] and c3['Close'] < c3['Open']:
                    if (c2['Open'] - c3['Close']) > 2 * abs(c1['Open'] - c1['Close']): # Strong drop
                        zones.append({'type': 'BEARISH_OB', 'top': c1['High'], 'bottom': c1['Open']})

        # Return the most recent valid zone
        if zones:
            return zones[-1]
        return None
