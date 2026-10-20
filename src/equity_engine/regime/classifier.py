import polars as pl
from enum import Enum

class MarketRegimeState(Enum):
    UPTREND = "UPTREND"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"

class RegimeClassifier:
    def __init__(self, config: dict):
        self.config = config.get("regimes", {})
        
    def classify_regime(
        self,
        nifty_history: pl.DataFrame,
        breadth_history: pl.DataFrame = None,
        vix_history: pl.DataFrame = None
    ) -> MarketRegimeState:
        """
        Classifies current regime based on latest data.
        """
        if nifty_history.is_empty():
            return MarketRegimeState.NEUTRAL
            
        nifty = nifty_history.sort("date")
        nifty = nifty.with_columns(
            pl.col("close").rolling_mean(window_size=200).alias("sma_200")
        )
        latest_nifty = nifty.row(-1, named=True)
        
        nifty_above_200 = False
        if latest_nifty["sma_200"] is not None and latest_nifty["close"] > latest_nifty["sma_200"]:
            nifty_above_200 = True
            
        nifty_below_200 = False
        if latest_nifty["sma_200"] is not None and latest_nifty["close"] < latest_nifty["sma_200"]:
            nifty_below_200 = True
            
        missing_policy = self.config.get("missing_data_policy", "IGNORE")
        
        breadth_above_50 = None
        if breadth_history is not None and not breadth_history.is_empty():
            breadth_above_50 = breadth_history.sort("date").row(-1, named=True).get("pct_above_50_dma")
            
        current_vix = None
        if vix_history is not None and not vix_history.is_empty():
            current_vix = vix_history.sort("date").row(-1, named=True).get("close")
            
        uptrend_cfg = self.config.get("UPTREND", {})
        risk_off_cfg = self.config.get("RISK_OFF", {})
        
        is_risk_off = False
        if risk_off_cfg.get("nifty_below_200_dma") and nifty_below_200:
            is_risk_off = True
        if "vix_min" in risk_off_cfg:
            if current_vix is None:
                if missing_policy == "FAIL":
                    raise ValueError("Missing VIX data")
            elif current_vix >= risk_off_cfg["vix_min"]:
                is_risk_off = True
            
        if is_risk_off:
            return MarketRegimeState.RISK_OFF
            
        is_uptrend = True
        if uptrend_cfg.get("nifty_above_200_dma") and not nifty_above_200:
            is_uptrend = False
        if "breadth_pct_above_50_dma_min" in uptrend_cfg:
            if breadth_above_50 is None:
                if missing_policy == "FAIL":
                    raise ValueError("Missing breadth data")
            elif breadth_above_50 < uptrend_cfg["breadth_pct_above_50_dma_min"]:
                is_uptrend = False
            
        if is_uptrend:
            return MarketRegimeState.UPTREND
            
        return MarketRegimeState.NEUTRAL
