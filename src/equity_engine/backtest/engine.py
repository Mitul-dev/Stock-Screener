"""Chronological research execution and stable outcome records."""

from datetime import date
import math
from typing import List

import polars as pl

from equity_engine.setups.breakout import SetupEvent
from equity_engine.outcomes.engine import OutcomeEngine


OUTCOME_SCHEMA = {
    "event_id": pl.String,
    "instrument_id": pl.String,
    "setup": pl.String,
    "detection_date": pl.Date,
    "final_state": pl.String,
    "confirmation_date": pl.Date,
    "entry_price": pl.Float64,
    "stop_price": pl.Float64,
    "exit_date": pl.Date,
    "exit_price": pl.Float64,
    "price_basis": pl.String,
    "raw_entry_price": pl.Float64,
    "raw_stop_price": pl.Float64,
    "raw_exit_price": pl.Float64,
    "gross_realized_r": pl.Float64,
    "net_realized_r": pl.Float64,
    "mfe": pl.Float64,
    "mae": pl.Float64,
    "hit_1r": pl.Boolean,
    "hit_2r": pl.Boolean,
    "partition": pl.String,
    "is_oos": pl.Boolean,
    "censored": pl.Boolean,
    "censor_reason": pl.String,
    "evidence_eligible": pl.Boolean,
}


def empty_outcomes() -> pl.DataFrame:
    """Return the same schema as a populated research result."""
    return pl.DataFrame(schema=OUTCOME_SCHEMA)


class ResearchEngine:
    def __init__(self, outcome_engine: OutcomeEngine):
        self.outcome_engine = outcome_engine

    def run_backtest(
        self,
        events: List[SetupEvent],
        data_history: pl.DataFrame,
        *,
        partition: str | None = None,
        partition_start: date | None = None,
        partition_end: date | None = None,
    ) -> pl.DataFrame:
        """Evaluate events using only bars within the requested date boundaries.

        Feature history may precede ``partition_start``; outcome evaluation cannot
        precede the event or extend beyond ``partition_end``. Unfinished watches
        and holdings remain visible as censored records and cannot enter evidence.
        """
        if partition_start is not None and partition_end is not None:
            if partition_start > partition_end:
                raise ValueError("partition_start must not be after partition_end")

        partition_name = partition.lower() if partition else None
        full_history_end = (
            data_history["date"].max() if not data_history.is_empty() else None
        )
        crosses_boundary = (
            partition_end is not None
            and full_history_end is not None
            and partition_end < full_history_end
        )
        censor_reason = (
            "PARTITION_END"
            if crosses_boundary or partition_name in {"discovery", "validation"}
            else "DATA_END"
        )

        results = []
        for event in sorted(
            events,
            key=lambda item: (
                item.timestamp,
                item.instrument_id,
                item.setup_version,
                item.event_id,
            ),
        ):
            if partition_start is not None and event.timestamp < partition_start:
                continue
            if partition_end is not None and event.timestamp > partition_end:
                continue

            instrument_df = data_history
            if not data_history.is_empty():
                instrument_df = data_history.filter(
                    (pl.col("instrument_id") == event.instrument_id)
                    & (pl.col("date") >= event.timestamp)
                )
            if partition_end is not None and not instrument_df.is_empty():
                instrument_df = instrument_df.filter(pl.col("date") <= partition_end)

            outcome = self.outcome_engine.evaluate_event(event, instrument_df)
            censored = outcome["final_state"] in {"WATCH", "CONFIRMED"}
            net_r = outcome.get("net_realized_r")
            outcome.update(
                partition=partition_name,
                is_oos=partition_name in {"validation", "holdout"},
                censored=censored,
                censor_reason=censor_reason if censored else None,
                evidence_eligible=(
                    outcome["final_state"] in {"COMPLETED", "FAILED"}
                    and net_r is not None
                    and math.isfinite(net_r)
                    and not censored
                ),
            )
            results.append(outcome)

        return (
            pl.DataFrame(results, schema=OUTCOME_SCHEMA, strict=False)
            if results
            else empty_outcomes()
        )

    def split_data(self, df: pl.DataFrame, discovery_pct=0.6, validation_pct=0.2):
        """Split by distinct sessions, leaving the existing outcome-window gap.

        Short histories can have empty validation or holdout partitions. They
        never reuse a discovery or validation session to manufacture a partition.
        """
        for name, value in (
            ("discovery_pct", discovery_pct),
            ("validation_pct", validation_pct),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number between 0 and 1")
            if not math.isfinite(value) or not 0 < value < 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if discovery_pct + validation_pct >= 1:
            raise ValueError("discovery_pct + validation_pct must be less than 1")

        if df.is_empty():
            return df.clone(), df.clone(), df.clone()

        dates = df["date"].unique().sort()
        n = len(dates)
        disc_idx = max(1, min(int(n * discovery_pct), n - 1)) if n > 2 else 0
        val_idx = (
            max(disc_idx, min(int(n * (discovery_pct + validation_pct)), n - 1))
            if n > 2
            else n - 1
        )
        purge_sessions = 25
        if self.outcome_engine:
            purge_sessions = (
                self.outcome_engine.timeout_days + self.outcome_engine.watch_expiry_days
            )

        val_start_idx = max(disc_idx + purge_sessions, disc_idx + 1)
        hold_start_idx = max(val_idx + purge_sessions, val_idx + 1)
        discovery = df.filter(pl.col("date") <= dates[disc_idx])
        validation = df.head(0)
        if val_start_idx <= val_idx and val_start_idx < n:
            validation = df.filter(
                (pl.col("date") >= dates[val_start_idx])
                & (pl.col("date") <= dates[val_idx])
            )
        holdout = df.head(0)
        if hold_start_idx < n:
            holdout = df.filter(pl.col("date") >= dates[hold_start_idx])
        return discovery, validation, holdout
