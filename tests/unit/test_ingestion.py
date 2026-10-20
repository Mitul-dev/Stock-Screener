import pytest
import polars as pl
from datetime import date
from equity_engine.ingestion.validator import DataValidator
from equity_engine.ingestion.csv_provider import CSVProvider

def test_validator_valid_data():
    df = pl.DataFrame({
        "date": [date(2023, 1, 1), date(2023, 1, 2)],
        "open": [100.0, 102.0],
        "high": [105.0, 104.0],
        "low": [99.0, 100.0],
        "close": [102.0, 103.0],
        "volume": [1000.0, 1500.0]
    })
    DataValidator.validate_ohlcv(df)

def test_validator_invalid_high_low():
    df = pl.DataFrame({
        "date": [date(2023, 1, 1)],
        "open": [100.0],
        "high": [90.0],
        "low": [95.0],
        "close": [92.0],
        "volume": [1000.0]
    })
    with pytest.raises(ValueError, match="invalid OHLCV rows"):
        DataValidator.validate_ohlcv(df)

def test_csv_provider(tmp_path):
    csv_file = tmp_path / "RELIANCE_ohlcv.csv"
    df = pl.DataFrame({
        "date": ["2023-01-01", "2023-01-02"],
        "open": [100.0, 102.0],
        "high": [105.0, 104.0],
        "low": [99.0, 100.0],
        "close": [102.0, 103.0],
        "volume": [1000.0, 1500.0]
    })
    df.write_csv(csv_file)
    
    provider = CSVProvider(str(tmp_path))
    res = provider.fetch_ohlcv("RELIANCE", date(2023, 1, 1), date(2023, 1, 2))
    assert len(res) == 2

from equity_engine.ingestion.storage import DataStorage

def test_data_storage(tmp_path):
    db_file = tmp_path / "test.db"
    storage = DataStorage(str(db_file))
    
    df = pl.DataFrame({
        "date": [date(2023, 1, 1), date(2023, 1, 2)],
        "open": [100.0, 102.0],
        "high": [105.0, 104.0],
        "low": [99.0, 100.0],
        "close": [102.0, 103.0],
        "volume": [1000.0, 1500.0]
    })
    
    storage.save_ohlcv("RELIANCE", df)
    
    loaded = storage.get_ohlcv("RELIANCE")
    assert len(loaded) == 2
    assert loaded["close"][1] == 103.0

