from abc import ABC, abstractmethod
import polars as pl
from datetime import date

class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, start_date: date, end_date: date) -> pl.DataFrame:
        """
        Fetch OHLCV data for a specific symbol.
        Expected schema: date (Date), open (Float), high (Float), low (Float), close (Float), volume (Float)
        """
        pass
    
    @abstractmethod
    def fetch_corporate_actions(self, symbol: str, start_date: date, end_date: date) -> pl.DataFrame:
        """
        Fetch corporate actions.
        Expected schema: date (Date), action_type (String), factor (Float)
        """
        pass
