import duckdb
import polars as pl
from pathlib import Path
from datetime import date, timedelta
from typing import Optional
import uuid

class SecurityMaster:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS instruments (
            instrument_id VARCHAR,
            isin VARCHAR,
            nse_symbol VARCHAR,
            bse_code VARCHAR,
            company_name VARCHAR,
            exchange VARCHAR,
            series VARCHAR,
            sector VARCHAR,
            industry VARCHAR,
            valid_from DATE,
            valid_to DATE,
            PRIMARY KEY (instrument_id, valid_from)
        )
        """)

    def add_instrument(
        self,
        isin: str,
        nse_symbol: str,
        company_name: str,
        valid_from: date,
        instrument_id: Optional[str] = None,
        bse_code: Optional[str] = None,
        exchange: str = "NSE",
        series: str = "EQ",
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        valid_to: Optional[date] = None
    ) -> str:
        if instrument_id is None:
            instrument_id = str(uuid.uuid4())
            
        self.conn.execute("""
            INSERT INTO instruments 
            (instrument_id, isin, nse_symbol, bse_code, company_name, exchange, series, sector, industry, valid_from, valid_to)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (instrument_id, isin, nse_symbol, bse_code, company_name, exchange, series, sector, industry, valid_from, valid_to))
        
        return instrument_id

    def handle_symbol_change(
        self, 
        instrument_id: str, 
        new_nse_symbol: str, 
        new_company_name: str,
        change_date: date
    ):
        df = self.conn.execute(
            "SELECT * FROM instruments WHERE instrument_id = ? ORDER BY valid_from DESC LIMIT 1",
            (instrument_id,)
        ).pl()
        
        if df.is_empty():
            raise ValueError(f"Instrument {instrument_id} not found")
            
        latest = df.row(0, named=True)
        
        # End current record (valid_to is exclusive)
        self.conn.execute(
            "UPDATE instruments SET valid_to = ? WHERE instrument_id = ? AND valid_from = ?",
            (change_date, instrument_id, latest['valid_from'])
        )
        
        # Insert new record
        self.add_instrument(
            instrument_id=instrument_id,
            isin=latest['isin'],
            nse_symbol=new_nse_symbol,
            bse_code=latest['bse_code'],
            company_name=new_company_name,
            exchange=latest['exchange'],
            series=latest['series'],
            sector=latest['sector'],
            industry=latest['industry'],
            valid_from=change_date,
            valid_to=None
        )

    def get_instrument_by_symbol(self, nse_symbol: str, as_of_date: date) -> Optional[dict]:
        df = self.conn.execute("""
            SELECT * FROM instruments 
            WHERE nse_symbol = ? 
            AND valid_from <= ?
            AND (valid_to IS NULL OR valid_to > ?)
        """, (nse_symbol, as_of_date, as_of_date)).pl()
        
        if df.is_empty():
            return None
        return df.row(0, named=True)

    def get_all_instruments(self, as_of_date: date) -> pl.DataFrame:
        df = self.conn.execute("""
            SELECT * FROM instruments 
            WHERE valid_from <= ?
            AND (valid_to IS NULL OR valid_to > ?)
        """, (as_of_date, as_of_date)).pl()
        return df
