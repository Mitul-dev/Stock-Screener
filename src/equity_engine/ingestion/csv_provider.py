import polars as pl
from datetime import date
from pathlib import Path
from .provider import MarketDataProvider

class CSVProvider(MarketDataProvider):
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        
    def fetch_ohlcv(self, symbol: str, start_date: date, end_date: date) -> pl.DataFrame:
        file_path = self.data_dir / f"{symbol}_ohlcv.csv"
        if not file_path.exists():
            return pl.DataFrame(schema={"date": pl.Date, "open": pl.Float64, "high": pl.Float64, "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64})
            
        df = pl.read_csv(file_path).with_columns(pl.col("date").cast(pl.Date))
        return df.filter((pl.col("date") >= start_date) & (pl.col("date") <= end_date))

    def fetch_corporate_actions(self, symbol: str, start_date: date, end_date: date) -> pl.DataFrame:
        file_path = self.data_dir / f"{symbol}_actions.csv"
        if not file_path.exists():
            return pl.DataFrame(schema={"date": pl.Date, "action_type": pl.String, "factor": pl.Float64})
            
        df = pl.read_csv(file_path).with_columns(pl.col("date").cast(pl.Date))
        return df.filter((pl.col("date") >= start_date) & (pl.col("date") <= end_date))
