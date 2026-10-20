import polars as pl
from enum import Enum
import hashlib
from datetime import date

class SetupState(Enum):
    DETECTED = "DETECTED"
    WATCH = "WATCH"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    INVALIDATED = "INVALIDATED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"

class SetupEvent:
    def __init__(self, instrument_id: str, setup_version: str, timestamp: date, breakout_level: float, features: dict):
        id_str = f"{instrument_id}_{setup_version}_{timestamp.isoformat()}"
        self.event_id = hashlib.md5(id_str.encode()).hexdigest()
        self.instrument_id = instrument_id
        self.setup_version = setup_version
        self.timestamp = timestamp
        self.state = SetupState.WATCH  # Initially placed into WATCH state
        self.breakout_level = breakout_level
        self.features = features
        
    def transition(self, new_state: SetupState):
        self.state = new_state

class BreakoutDetector:
    def __init__(self, config: dict):
        self.version = config.get("version", "1.0")
        self.params = config.get("parameters", {})
        self.lookback = self.params.get("lookback_days", 252)
        self.min_vol_rel = self.params.get("min_volume_relative", 1.5)
        self.close_near_high = self.params.get("close_near_high_pct", 0.02)
        
    def detect(self, instrument_id: str, features_df: pl.DataFrame) -> list[SetupEvent]:
        if features_df.is_empty():
            return []
            
        events = []
        for row in features_df.iter_rows(named=True):
            if row.get("high_252d") is None or row.get("vol_rel_20") is None:
                continue
                
            close_price = row.get("adj_close") if row.get("adj_close") is not None else row["close"]
            # DETECTED/WATCH condition: close is approaching the breakout level
            is_near_breakout = close_price >= row["high_252d"] * (1 - self.close_near_high)
            is_volume_high = row["vol_rel_20"] >= self.min_vol_rel
            
            if is_near_breakout and is_volume_high:
                event = SetupEvent(
                    instrument_id=instrument_id,
                    setup_version=f"BREAKOUT_V{self.version}",
                    timestamp=row["date"],
                    breakout_level=row["high_252d"], # The exact level needed for confirmation
                    features={
                        "atr_14": row.get("atr_14"),
                        "vol_rel_20": row["vol_rel_20"],
                        "close": close_price
                    }
                )
                events.append(event)
                
        return events
