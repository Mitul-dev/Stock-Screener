import duckdb
import polars as pl
from pathlib import Path

class DataStorage:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        self._init_schema()
        
    def _init_schema(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_ohlcv (
            symbol VARCHAR,
            date DATE,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            PRIMARY KEY (symbol, date)
        )
        """)
        
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS corporate_actions (
            symbol VARCHAR,
            date DATE,
            action_type VARCHAR,
            factor DOUBLE
        )
        """)
        
    def save_ohlcv(self, symbol: str, df: pl.DataFrame):
        if df.is_empty():
            return
            
        temp_df = df.with_columns(pl.lit(symbol).alias("symbol"))
        self.conn.register("temp_df", temp_df.to_arrow())
        
        self.conn.execute("""
        INSERT INTO raw_ohlcv (symbol, date, open, high, low, close, volume)
        SELECT symbol, date, open, high, low, close, volume FROM temp_df
        ON CONFLICT (symbol, date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
        """)
        self.conn.unregister("temp_df")

    def get_ohlcv(self, symbol: str) -> pl.DataFrame:
        query = f"SELECT * EXCLUDE (symbol) FROM raw_ohlcv WHERE symbol = '{symbol}' ORDER BY date"
        return self.conn.execute(query).pl()
