import polars as pl
from equity_engine.setups.breakout import SetupEvent

class VCBDetector:
    def __init__(self, config: dict):
        self.version = config.get("version", "1.0")
        self.params = config.get("parameters", {})
        self.lookback = self.params.get("lookback_days", 60)
        self.max_atr_pctile = self.params.get("max_atr_percentile", 0.20)
        self.min_consolidation = self.params.get("min_consolidation_days", 10)
        
    def detect(self, instrument_id: str, features_df: pl.DataFrame) -> list[SetupEvent]:
        if features_df.is_empty():
            return []
            
        h_col = "adj_high" if "adj_high" in features_df.columns else "high"
        c_col = "adj_close" if "adj_close" in features_df.columns else "close"
        
        df = features_df.with_columns([
            pl.col("atr_pct").rolling_quantile(quantile=self.max_atr_pctile, window_size=self.lookback, interpolation="nearest").alias("atr_pct_threshold"),
            pl.col(h_col).rolling_max(window_size=self.min_consolidation).shift(1).alias("consolidation_high")
        ])
        
        events = []
        for row in df.iter_rows(named=True):
            if row.get("atr_pct_threshold") is None or row.get("consolidation_high") is None:
                continue
                
            close_price = row.get(c_col) if row.get(c_col) is not None else row["close"]
            is_contracted = row["atr_pct"] <= row["atr_pct_threshold"]
            is_breakout = close_price >= row["consolidation_high"]
            is_vol_high = row.get("vol_rel_20", 0) >= 1.2
            
            if is_contracted and is_breakout and is_vol_high:
                event = SetupEvent(
                    instrument_id=instrument_id,
                    setup_version=f"VCB_V{self.version}",
                    timestamp=row["date"],
                    breakout_level=row["consolidation_high"],
                    features={
                        "atr_14": row.get("atr_14"),
                        "vol_rel_20": row.get("vol_rel_20"),
                        "atr_pct": row.get("atr_pct"),
                        "close": close_price
                    }
                )
                events.append(event)
                
        return events
