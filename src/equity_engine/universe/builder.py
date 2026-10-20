import polars as pl
from datetime import date

class UniverseBuilder:
    def __init__(self, config: dict):
        self.config = config
        
    def build_daily_universe(
        self,
        as_of_date: date,
        ohlcv_history: pl.DataFrame,
        lookback_days: int = 60
    ) -> pl.DataFrame:
        if lookback_days <= 0:
            raise ValueError("lookback_days must be positive")
        identity = "instrument_id" if "instrument_id" in ohlcv_history.columns else "symbol"
        result_columns = ["instrument_id", "symbol", "tier"] if identity == "instrument_id" else ["symbol", "tier"]
        empty_schema = {column: pl.String for column in result_columns}
        empty_schema.update({"median_traded_value": pl.Float64, "days_traded": pl.UInt32,
                             "coverage": pl.Float64, "latest_price": pl.Float64})
        result_columns += ["median_traded_value", "days_traded", "coverage", "latest_price"]
        if ohlcv_history.is_empty():
            return pl.DataFrame(schema=empty_schema)
            
        # Ensure strict point-in-time calculation to prevent lookahead bias
        df = ohlcv_history.filter(pl.col("date") <= as_of_date)
        
        # Stale stock exclusion: Find the distinct dates and take the last `lookback_days`
        distinct_dates = df.select("date").unique().sort("date")
        if len(distinct_dates) > lookback_days:
            cutoff_date = distinct_dates.row(-lookback_days)[0]
            df = df.filter(pl.col("date") >= cutoff_date)
        
        if df.is_empty():
            return pl.DataFrame(schema=empty_schema)
            
        if "traded_value" not in df.columns:
            df = df.with_columns(
                (pl.col("volume") * pl.col("close")).alias("traded_value")
            )
        
        # The last price and display symbol must come from the latest observed
        # session, regardless of the input file's row order. Symbols can change
        # or be reused; the source instrument identifier is the grouping key.
        df = df.sort("date")
        aggregations = [
            pl.col("traded_value").median().alias("median_traded_value"),
            pl.col("date").n_unique().alias("days_traded"),
            pl.col("close").last().alias("latest_price")
        ]
        if identity == "instrument_id":
            aggregations.append(pl.col("symbol").last().alias("symbol"))
        stats = df.group_by(identity).agg(aggregations)
        
        stats = stats.with_columns(
            (pl.col("days_traded") / lookback_days).alias("coverage")
        )
        
        tiers = self.config.get("liquidity_tiers", {})
        
        def get_tier_condition(tier_config):
            return (
                (pl.col("median_traded_value") >= tier_config["min_median_traded_value"]) &
                (pl.col("coverage") >= tier_config["min_trading_days_coverage"]) &
                (pl.col("latest_price") >= tier_config["min_price"])
            )
            
        tier_1 = tiers.get("tier_1")
        tier_2 = tiers.get("tier_2")
        
        stats = stats.with_columns(pl.lit(None).cast(pl.String).alias("tier"))
        
        if tier_2:
            stats = stats.with_columns(
                pl.when(get_tier_condition(tier_2)).then(pl.lit("tier_2")).otherwise(pl.col("tier")).alias("tier")
            )
            
        if tier_1:
            stats = stats.with_columns(
                pl.when(get_tier_condition(tier_1)).then(pl.lit("tier_1")).otherwise(pl.col("tier")).alias("tier")
            )
            
        eligible = stats.filter(pl.col("tier").is_not_null())
        return eligible.select(result_columns).sort(identity)
