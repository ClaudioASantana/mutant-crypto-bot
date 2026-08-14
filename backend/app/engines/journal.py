import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TradeJournal:
    def __init__(self):
        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "journal.db"))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id TEXT PRIMARY KEY,
                        symbol TEXT,
                        direction TEXT,
                        strategy TEXT,
                        ai_reason TEXT,
                        entry_time INTEGER,
                        entry_price REAL,
                        atr REAL,
                        rsi REAL,
                        margin REAL,
                        leverage INTEGER,
                        status TEXT,
                        exit_time INTEGER,
                        exit_price REAL,
                        net_pnl REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Erro ao inicializar o banco de dados do Trade Journal: {e}")

    def log_entry(self, trade_id: str, symbol: str, direction: str, strategy: str, ai_reason: str, 
                  entry_time: int, entry_price: float, atr: float, rsi: float, margin: float, leverage: int):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trades (
                        id, symbol, direction, strategy, ai_reason, entry_time, entry_price, 
                        atr, rsi, margin, leverage, status, exit_time, exit_price, net_pnl
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', NULL, NULL, NULL)
                """, (trade_id, symbol, direction, strategy, ai_reason, entry_time, entry_price, atr, rsi, margin, leverage))
                conn.commit()
                logger.info(f"📔 [Journal] Entrada registrada: Trade ID {trade_id}")
        except Exception as e:
            logger.error(f"Erro ao registrar entrada no Trade Journal: {e}")

    def log_exit(self, trade_id: str, exit_time: int, exit_price: float, net_pnl: float, status: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trades 
                    SET exit_time = ?, exit_price = ?, net_pnl = ?, status = ?
                    WHERE id = ?
                """, (exit_time, exit_price, net_pnl, status, trade_id))
                conn.commit()
                logger.info(f"📔 [Journal] Saída registrada: Trade ID {trade_id} ({status})")
        except Exception as e:
            logger.error(f"Erro ao registrar saída no Trade Journal: {e}")
