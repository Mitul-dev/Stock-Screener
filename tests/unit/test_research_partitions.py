from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest
import yaml

from equity_engine.backtest.engine import OUTCOME_SCHEMA, ResearchEngine, empty_outcomes
from equity_engine.outcomes.engine import OutcomeEngine
from equity_engine.setups.breakout import SetupEvent


START = date(2020, 1, 1)


def event(offset=0, instrument="INE000000001"):
    return SetupEvent(
        instrument, "BREAKOUT_V1.0", START + timedelta(days=offset), 100.0,
        {"atr_14": 2.0},
    )


def bars(offsets=(0, 1, 3, 4, 5), *, close=102.0, low=101.0):
    return pl.DataFrame({
        "instrument_id": ["INE000000001"] * len(offsets),
        "date": [START + timedelta(days=offset) for offset in offsets],
        "open": [102.0] * len(offsets),
        "high": [103.0] * len(offsets),
        "low": [low] * len(offsets),
        "close": [close] * len(offsets),
    })


@pytest.mark.parametrize("history", [pl.DataFrame(), bars()])
def test_zero_events_has_the_complete_outcome_schema(history):
    outcomes = ResearchEngine(OutcomeEngine({})).run_backtest([], history)
    assert outcomes.schema == pl.Schema(OUTCOME_SCHEMA)
    assert outcomes.is_empty()
    assert empty_outcomes().schema == outcomes.schema


def test_empty_input_retains_an_observed_watch_as_censored():
    outcomes = ResearchEngine(OutcomeEngine({})).run_backtest(
        [event()], pl.DataFrame(), partition="HOLDOUT",
    )
    assert outcomes["final_state"].item() == "WATCH"
    assert outcomes["censor_reason"].item() == "DATA_END"
    assert not outcomes["evidence_eligible"].item()


def test_partition_censors_holding_with_missing_instrument_sessions_and_never_reads_future():
    outcome_engine = OutcomeEngine({"timeout_days": 3, "watch_expiry_days": 2})
    engine = ResearchEngine(outcome_engine)
    # The missing session at day 2 must not make day 4 available at a day-3 cutoff.
    history = bars()
    boundary = START + timedelta(days=3)
    with patch.object(outcome_engine, "evaluate_event", wraps=outcome_engine.evaluate_event) as spy:
        clipped = engine.run_backtest(
            [event()], history, partition="DISCOVERY",
            partition_start=START, partition_end=boundary,
        )
    seen = spy.call_args.args[1]
    assert seen["date"].to_list() == [START, START + timedelta(days=1), boundary]
    assert clipped["final_state"].item() == "CONFIRMED"
    assert clipped["exit_date"].item() is None
    assert clipped["net_realized_r"].item() is None
    assert clipped["censored"].item()
    assert clipped["censor_reason"].item() == "PARTITION_END"
    assert not clipped["evidence_eligible"].item()
    assert not clipped["is_oos"].item()

    whole = engine.run_backtest([event()], history)
    assert whole["final_state"].item() == "COMPLETED"
    assert whole["exit_date"].item() > boundary
    assert whole["evidence_eligible"].item()


def test_partition_censors_confirmation_without_a_permitted_entry_bar():
    engine = ResearchEngine(OutcomeEngine({"timeout_days": 2}))
    outcomes = engine.run_backtest(
        [event()], bars(), partition="VALIDATION", partition_end=START,
    )
    assert outcomes["confirmation_date"].item() == START
    assert outcomes["entry_price"].item() is None
    assert outcomes["censored"].item()
    assert outcomes["censor_reason"].item() == "PARTITION_END"
    assert outcomes["is_oos"].item()


def test_watch_expiry_is_distinct_from_boundary_censoring():
    engine = ResearchEngine(OutcomeEngine({"watch_expiry_days": 3}))
    history = bars(close=100.0)
    watch = engine.run_backtest(
        [event()], history, partition="DISCOVERY",
        partition_end=START + timedelta(days=1),
    )
    expired = engine.run_backtest(
        [event()], history, partition="DISCOVERY",
        partition_end=START + timedelta(days=3),
    )
    assert watch["final_state"].item() == "WATCH"
    assert watch["censored"].item()
    assert expired["final_state"].item() == "EXPIRED"
    assert not expired["censored"].item()
    assert expired["censor_reason"].item() is None
    assert not expired["evidence_eligible"].item()


def test_terminal_loss_on_the_boundary_is_retained_as_eligible_evidence():
    engine = ResearchEngine(OutcomeEngine({"timeout_days": 5}))
    history = bars(low=98.0)
    outcomes = engine.run_backtest(
        [event()], history, partition="VALIDATION",
        partition_end=START + timedelta(days=1),
    )
    assert outcomes["final_state"].item() == "FAILED"
    assert outcomes["exit_date"].item() == START + timedelta(days=1)
    assert outcomes["net_realized_r"].item() < 0
    assert not outcomes["censored"].item()
    assert outcomes["evidence_eligible"].item()


def test_invalid_entry_remains_recorded_without_entering_evidence():
    engine = ResearchEngine(OutcomeEngine({}))
    history = bars().with_columns(
        pl.when(pl.col("date") > START).then(98.0).otherwise(pl.col("open")).alias("open")
    )
    outcomes = engine.run_backtest([event()], history, partition="HOLDOUT")
    assert outcomes["final_state"].item() == "INVALIDATED"
    assert not outcomes["censored"].item()
    assert not outcomes["evidence_eligible"].item()


def test_event_bounds_and_record_order_are_deterministic():
    engine = ResearchEngine(OutcomeEngine({"watch_expiry_days": 2}))
    events = [event(5), event(1), event(0), event(3)]
    options = dict(
        partition="holdout", partition_start=START + timedelta(days=1),
        partition_end=START + timedelta(days=3),
    )
    actual = engine.run_backtest(events, bars(), **options)
    reversed_result = engine.run_backtest(list(reversed(events)), bars(), **options)
    assert actual.equals(reversed_result)
    assert actual["detection_date"].to_list() == [START + timedelta(days=1), START + timedelta(days=3)]
    assert actual["partition"].to_list() == ["holdout", "holdout"]
    assert engine.run_backtest([event(5)], bars(), **options).schema == actual.schema


def test_invalid_date_boundaries_are_rejected():
    with pytest.raises(ValueError, match="partition_start"):
        ResearchEngine(OutcomeEngine({})).run_backtest(
            [], bars(), partition_start=START + timedelta(days=1), partition_end=START,
        )


@pytest.mark.parametrize("n", [0, 1, 2, 3, 10, 25, 30, 100, 1000])
def test_split_partitions_are_disjoint_even_when_the_history_is_short(n):
    history = pl.DataFrame({
        "date": pl.Series([START + timedelta(days=i) for i in range(n)], dtype=pl.Date),
        "close": pl.Series(range(n), dtype=pl.Int64),
    })
    partitions = ResearchEngine(OutcomeEngine({})).split_data(history)
    for part in partitions:
        assert part.schema == history.schema
    sets = [set(part["date"].to_list()) for part in partitions]
    assert not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
    nonempty = [part for part in partitions if not part.is_empty()]
    assert all(left["date"].max() < right["date"].min() for left, right in zip(nonempty, nonempty[1:]))
    if n == 1000:
        discovery, validation, holdout = partitions
        assert discovery["date"].max() == START + timedelta(days=600)
        assert validation["date"].min() == START + timedelta(days=625)
        assert validation["date"].max() == START + timedelta(days=800)
        assert holdout["date"].min() == START + timedelta(days=825)


@pytest.mark.parametrize("discovery,validation", [
    (0, 0.2), (1, 0.2), (-0.1, 0.2), (0.6, 0), (0.6, 0.4),
    (0.9, 0.2), (float("nan"), 0.2), (0.6, float("inf")), (True, 0.2),
])
def test_invalid_split_fractions_are_rejected(discovery, validation):
    with pytest.raises(ValueError):
        ResearchEngine(None).split_data(bars(), discovery, validation)


def test_configured_gst_is_charged_only_on_brokerage_exchange_and_sebi():
    root = Path(__file__).resolve().parents[2]
    costs = yaml.safe_load((root / "config" / "costs.yaml").read_text())["costs"]
    engine = OutcomeEngine({"timeout_days": 2, "transaction_costs": costs})
    taxable_rate = costs["brokerage_pct"] + costs["exchange_charges_pct"] + costs["sebi_charges_pct"]
    expected_rate = sum(value for key, value in costs.items() if key != "gst_pct") + taxable_rate * costs["gst_pct"]
    assert engine.cost_rate == pytest.approx(expected_rate)
    result = engine.evaluate_event(event(), bars())
    assert result["gross_realized_r"] == 0.0
    assert result["net_realized_r"] == pytest.approx(-(102.0 + 102.0) * expected_rate / 3.0)


def test_legacy_cost_defaults_remain_unchanged_without_an_explicit_gst_rate():
    assert OutcomeEngine({}).cost_rate == pytest.approx(0.002481)
