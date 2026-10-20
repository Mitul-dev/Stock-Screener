import polars as pl

class DataValidator:
    @staticmethod
    def validate_ohlcv(df: pl.DataFrame) -> None:
        """
        Validates OHLCV data.
        Raises ValueError if data is invalid.
        """
        if df.is_empty():
            return
            
        required_cols = {"date", "open", "high", "low", "close", "volume"}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(f"Missing columns: {required_cols - set(df.columns)}")

        if df["date"].null_count():
            raise ValueError("Missing market dates")
        for column in ("instrument_id", "symbol", "series"):
            if column in df.columns and df.filter(
                pl.col(column).is_null() | (pl.col(column).cast(pl.String).str.strip_chars() == "")
            ).height:
                raise ValueError(f"Missing identity field: {column}")
            
        # Check impossible OHLC, nulls, non-finites, and negative/zero prices
        invalid_rows = df.filter(
            (pl.col("open").is_null() | pl.col("open").is_nan() | pl.col("open").is_infinite() | (pl.col("open") <= 0)) |
            (pl.col("high").is_null() | pl.col("high").is_nan() | pl.col("high").is_infinite() | (pl.col("high") <= 0)) |
            (pl.col("low").is_null() | pl.col("low").is_nan() | pl.col("low").is_infinite() | (pl.col("low") <= 0)) |
            (pl.col("close").is_null() | pl.col("close").is_nan() | pl.col("close").is_infinite() | (pl.col("close") <= 0)) |
            (pl.col("volume").is_null() | pl.col("volume").is_nan() | pl.col("volume").is_infinite() | (pl.col("volume") < 0)) |
            (pl.col("high") < pl.col("low")) |
            (pl.col("high") < pl.col("open")) |
            (pl.col("high") < pl.col("close")) |
            (pl.col("low") > pl.col("open")) |
            (pl.col("low") > pl.col("close"))
        )
        
        if len(invalid_rows) > 0:
            raise ValueError(f"Found {len(invalid_rows)} invalid OHLCV rows")

        if "traded_value" in df.columns:
            invalid_turnover = df.filter(
                pl.col("traded_value").is_null() | ~pl.col("traded_value").is_finite() |
                (pl.col("traded_value") < 0)
            )
            if invalid_turnover.height:
                raise ValueError("Invalid reported traded value")

        for column, maximum in (("deliverable_quantity", pl.col("volume")),
                                ("deliverable_pct", pl.lit(100.0))):
            if column in df.columns and df.filter(
                pl.col(column).is_not_null() &
                (~pl.col(column).cast(pl.Float64).is_finite() |
                 (pl.col(column).cast(pl.Float64) < 0) |
                 (pl.col(column).cast(pl.Float64) > maximum))
            ).height:
                raise ValueError(f"Invalid delivery field: {column}")
            
        # Check duplicate dates
        group_cols = ["instrument_id", "date"] if "instrument_id" in df.columns else ["date"]
        duplicates = df.group_by(group_cols).len().filter(pl.col("len") > 1)
        if len(duplicates) > 0:
            raise ValueError(f"Found duplicate dates: {duplicates}")
