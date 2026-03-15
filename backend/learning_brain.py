import sqlite3
import os
import json
from datetime import datetime

class LearningBrain:
    def __init__(self, db_path=None):
        if db_path is None:
            # Pone la DB en la misma carpeta que este script
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(base_dir, "brain.db")
        else:
            self.db_path = db_path
            
        self._init_db()

    def _init_db(self):
        """Initializes SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for trades and outcomes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                ticket TEXT PRIMARY KEY,
                symbol TEXT,
                signal_type TEXT,
                entry_price REAL,
                status TEXT, -- WIN, LOSS, OPEN
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for market context at entry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_context (
                ticket TEXT PRIMARY KEY,
                rsi REAL,
                ema_spread REAL,
                trend_bias TEXT,
                fvg_present INTEGER,
                volatility REAL,
                FOREIGN KEY (ticket) REFERENCES trades(ticket)
            )
        ''')
        
        # Table for strategy weights (The "Experience")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_weights (
                symbol TEXT,
                strategy_name TEXT,
                win_rate REAL DEFAULT 0.0,
                weight REAL DEFAULT 1.0,
                total_trades INTEGER DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, strategy_name)
            )
        ''')
        
        conn.commit()
        conn.close()

    def log_trade_start(self, ticket, symbol, signal_type, price, context):
        """Records a new trade and its market context"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # We also store the primary reason (strategy) if provided in context
            strategy = context.get('strategy', 'CORE_V2')
            
            cursor.execute('INSERT INTO trades (ticket, symbol, signal_type, entry_price, status) VALUES (?, ?, ?, ?, ?)',
                         (str(ticket), symbol, f"{signal_type}_{strategy}", price, 'OPEN'))
            
            cursor.execute('''
                INSERT INTO market_context (ticket, rsi, ema_spread, trend_bias, fvg_present, volatility)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(ticket), context.get('rsi', 0), context.get('ema_spread', 0), 
                  context.get('trend_bias', 'NEUTRAL'), 1 if context.get('fvg', False) else 0,
                  context.get('volatility', 0)))
            
            conn.commit()
        except Exception as e:
            print(f"❌ Brain Log Error: {e}")
        finally:
            conn.close()

    def update_trade_outcome(self, ticket, outcome):
        """Updates trade status and recalculates weights (Learning)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Update status
            cursor.execute('UPDATE trades SET status = ? WHERE ticket = ?', (outcome, str(ticket)))
            
            # Fetch details for weighting
            cursor.execute('SELECT symbol, signal_type FROM trades WHERE ticket = ?', (str(ticket),))
            row = cursor.fetchone()
            if row:
                symbol, sig_strat = row
                strategy = sig_strat.split('_')[-1] if '_' in sig_strat else 'CORE_V2'
                self._recalculate_weights(symbol, strategy)
                
            conn.commit()
        except Exception as e:
            print(f"❌ Brain Learning Error: {e}")
        finally:
            conn.close()

    def _recalculate_weights(self, symbol, strategy):
        """The core learning logic: adjusts weights based on strategy performance per symbol"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # AI: Favor strategies that win more in specific assets
        cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins
            FROM trades 
            WHERE symbol = ? AND signal_type LIKE ? AND status != 'OPEN'
        ''', (symbol, f"%_{strategy}"))
        
        stats = cursor.fetchone()
        if stats and stats[0] > 0:
            total, wins = stats
            win_rate = wins / total
            
            # Learning sensitivity: If high trades, be more aggressive with weight change
            sensitivity = 2.0 if total > 5 else 1.2
            
            # Update weights: Strong win rate -> Higher weight (Max 2.0, Min 0.5)
            weight = 1.0 + (win_rate - 0.55) * sensitivity # Bias toward 55% win rate
            weight = max(0.4, min(2.5, weight)) 
            
            cursor.execute('''
                INSERT OR REPLACE INTO strategy_weights (symbol, strategy_name, win_rate, weight, total_trades, last_updated)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (symbol, strategy, win_rate, weight, total))
            
        conn.commit()
        conn.close()

    def get_experience_multiplier(self, symbol, strategy="CORE_V2"):
        """Returns the learned multiplier for a specific asset and strategy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Try specific strategy first
        cursor.execute('SELECT weight FROM strategy_weights WHERE symbol = ? AND strategy_name = ?', (symbol, strategy))
        row = cursor.fetchone()
        
        if not row:
            # Fallback to general symbol performance (average of all strategies for this symbol)
            cursor.execute('SELECT AVG(weight) FROM strategy_weights WHERE symbol = ?', (symbol,))
            row = cursor.fetchone()
            
        conn.close()
        
        # If still no data, return 1.0 (Neutral)
        multiplier = row[0] if row and row[0] is not None else 1.0
        return multiplier

