import polars as pl

class FeatureCalculator:
    @staticmethod
    def calculate_features(df: pl.DataFrame) -> pl.DataFrame:
        """
        Input: OHLCV dataframe for a single instrument, sorted by date.
        Returns the dataframe with technical features added.
        """
        if df.is_empty():
            return df
            
        df = df.sort("date")
        
        c = "adj_close" if "adj_close" in df.columns else "close"
        h = "adj_high" if "adj_high" in df.columns else "high"
        l = "adj_low" if "adj_low" in df.columns else "low"
        v = "adj_volume" if "adj_volume" in df.columns else "volume"
        
        df = df.with_columns([
            pl.col(c).shift(1).alias("prev_close")
        ])
        
        df = df.with_columns([
            pl.max_horizontal([
                pl.col(h) - pl.col(l),
                (pl.col(h) - pl.col("prev_close")).abs(),
                (pl.col(l) - pl.col("prev_close")).abs()
            ]).alias("tr")
        ])
        
        df = df.with_columns([
            pl.col("tr").rolling_mean(window_size=14).alias("atr_14"),
            pl.col("tr").rolling_mean(window_size=20).alias("atr_20")
        ])
        
        df = df.with_columns([
            pl.col(c).rolling_mean(window_size=50).alias("sma_50"),
            pl.col(c).rolling_mean(window_size=200).alias("sma_200"),
            pl.col(v).rolling_mean(window_size=20).alias("vol_sma_20")
        ])
        
        df = df.with_columns([
            (pl.col(v) / pl.col("vol_sma_20")).alias("vol_rel_20")
        ])
        
        df = df.with_columns([
            pl.col(h).rolling_max(window_size=252).shift(1).alias("high_252d")
        ])
        
        df = df.with_columns([
            (pl.col("atr_14") / pl.col(c)).alias("atr_pct"),
            pl.col(c).rolling_std(window_size=20).alias("std_20")
        ])
        
        return df
