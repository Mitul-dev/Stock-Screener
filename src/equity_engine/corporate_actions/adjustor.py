import polars as pl

class CorporateActionAdjustor:
    @staticmethod
    def adjust_ohlcv(ohlcv_df: pl.DataFrame, actions_df: pl.DataFrame) -> pl.DataFrame:
        """
        Adjusts OHLCV prices backwards based on corporate actions.
        actions_df expects: [date, action_type, factor]
        """
        if ohlcv_df.is_empty():
            return ohlcv_df
            
        if "price_basis" in ohlcv_df.columns and (ohlcv_df["price_basis"] == "adjusted").any():
            raise ValueError("Cannot adjust already-adjusted OHLCV data (price_basis is 'adjusted')")
            
        base = ohlcv_df
        
        if actions_df.is_empty():
            return base.with_columns([
                pl.lit(1.0).alias("adj_factor"),
                pl.col("open").alias("adj_open"),
                pl.col("high").alias("adj_high"),
                pl.col("low").alias("adj_low"),
                pl.col("close").alias("adj_close"),
                pl.col("volume").cast(pl.Float64).alias("adj_volume"),
                pl.lit("adjusted").alias("price_basis")
            ])
            
        if actions_df["date"].null_count():
            raise ValueError("Corporate action dates cannot be null")
        actions_df = actions_df.with_columns(pl.col("factor").cast(pl.Float64, strict=False))
        invalid_factor = pl.col("factor").is_null() | ~pl.col("factor").is_finite() | (pl.col("factor") <= 0)
        if actions_df.filter(invalid_factor).height:
            raise ValueError("Corporate action factors must be finite and positive")

        # Include action dates even when this instrument has no bar on its
        # ex-date. Every strictly earlier bar receives that action's factor.
        daily_actions = actions_df.group_by("date").agg(
            pl.col("factor").product().alias("daily_factor")
        )
        if daily_actions.filter(~pl.col("daily_factor").is_finite() | (pl.col("daily_factor") <= 0)).height:
            raise ValueError("Cumulative corporate action factor must be finite and positive")
        timeline = pl.concat([base.select("date"), daily_actions.select("date")]).unique()
        timeline = timeline.join(daily_actions, on="date", how="left").sort("date", descending=True)
        timeline = timeline.with_columns(pl.col("daily_factor").fill_null(1.0))

        # Ex-date prices already reflect the action, so use factors from dates
        # strictly later than each row rather than including its own factor.
        timeline = timeline.with_columns(
            pl.col("daily_factor").shift(1).fill_null(1.0)
        )
        timeline = timeline.with_columns(
            pl.col("daily_factor").cum_prod().alias("adj_factor")
        )
        if timeline.filter(~pl.col("adj_factor").is_finite() | (pl.col("adj_factor") <= 0)).height:
            raise ValueError("Cumulative corporate action factor must be finite and positive")
        merged = base.join(timeline.select("date", "adj_factor"), on="date", how="left")
        
        # Calculate adjusted OHLCV
        merged = merged.with_columns([
            (pl.col("open") / pl.col("adj_factor")).alias("adj_open"),
            (pl.col("high") / pl.col("adj_factor")).alias("adj_high"),
            (pl.col("low") / pl.col("adj_factor")).alias("adj_low"),
            (pl.col("close") / pl.col("adj_factor")).alias("adj_close"),
            (pl.col("volume") * pl.col("adj_factor")).alias("adj_volume"),
            pl.lit("adjusted").alias("price_basis")
        ]).sort("date")
        
        return merged
