import sqlite3
import os
import json
from datetime import datetime

class LearningBrain:
    def __init__(self, db_path="backend/brain.db"):
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
            cursor.execute('INSERT INTO trades (ticket, symbol, signal_type, entry_price, status) VALUES (?, ?, ?, ?, ?)',
                         (str(ticket), symbol, signal_type, price, 'OPEN'))
            
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
            
            # Fetch symbol for weighting
            cursor.execute('SELECT symbol FROM trades WHERE ticket = ?', (str(ticket),))
            row = cursor.fetchone()
            if row:
                symbol = row[0]
                self._recalculate_weights(symbol)
                
            conn.commit()
        except Exception as e:
            print(f"❌ Brain Learning Error: {e}")
        finally:
            conn.close()

    def _recalculate_weights(self, symbol):
        """The core learning logic: adjusts weights based on win rate per symbol"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Simplified AI: Favor symbols/strategies that win more
        cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END) as wins
            FROM trades WHERE symbol = ? AND status != 'OPEN'
        ''', (symbol,))
        
        stats = cursor.fetchone()
        if stats and stats[0] > 0:
            total, wins = stats
            win_rate = wins / total
            
            # Update weights: Strong win rate -> Higher weight (Max 2.0)
            weight = 1.0 + (win_rate - 0.5) * 2.0
            weight = max(0.5, min(2.0, weight)) # Hard limits
            
            cursor.execute('''
                INSERT OR REPLACE INTO strategy_weights (symbol, strategy_name, win_rate, weight, total_trades)
                VALUES (?, ?, ?, ?, ?)
            ''', (symbol, 'CORE_V1', win_rate, weight, total))
            
        conn.commit()
        conn.close()

    def get_experience_multiplier(self, symbol):
        """Returns the learned multiplier for a specific asset"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT weight FROM strategy_weights WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 1.0
