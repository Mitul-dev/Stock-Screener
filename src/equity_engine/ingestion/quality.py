"""Recorded engineering checks; these are not historical-source certification."""

import polars as pl

from equity_engine.ingestion.validator import DataValidator


QUALITY_VERSION = "pilot-quality-1"
# A review trigger for source discontinuities, independent of strategy parameters.
ABNORMAL_RETURN_THRESHOLD = 0.50
CHECK_NAMES = {
    "ohlcv", "source_identity", "requested_cohort", "identifier_collisions",
    "observed_session_coverage", "stale_history", "abnormal_adjusted_returns",
    "delivery_availability", "acquisition_provenance", "calendar_completeness",
    "corporate_action_reconciliation", "identifier_history", "index_availability", "history_depth",
}
CRITICAL_CHECKS = {"ohlcv", "source_identity", "requested_cohort",
                   "identifier_collisions", "abnormal_adjusted_returns"}


def assess_quality(raw, features, inputs, *, cohort=None, calendar=None, actions=None,
                   index=None, warmup_sessions=252):
    """Reuse market validation and retain counts, missing inputs and critical issues.

    Cohort-relative gaps/staleness are warnings: suspensions/listings cannot be
    inferred from missing bars. Without a supplied session calendar, exchange
    calendar completeness is explicitly unavailable. Unexplained adjusted jumps
    withhold evidence; supplied action factors can explain raw split jumps, but
    do not establish official action-source reconciliation.
    """
    checks = []

    def add(name, status, counts, detail, *, blocking=False, examples=None):
        checks.append({"name": name, "status": status, "counts": counts,
                       "detail": detail, "blocking": blocking,
                       "examples": examples or []})

    try:
        DataValidator.validate_ohlcv(raw)
        add("ohlcv", "PASSED", {"rows_checked": raw.height},
            "Existing DataValidator accepted the supplied market rows.")
    except ValueError as error:
        add("ohlcv", "FAILED", {"rows_checked": raw.height}, str(error), blocking=True)

    source_hashes = {item["sha256"] for item in inputs if item["kind"] == "ohlcv"}
    bad_source = raw.filter(
        pl.col("source_sha256").is_null() |
        ~pl.col("source_sha256").is_in(sorted(source_hashes)) |
        pl.col("source_date").is_null() |
        (pl.col("source_date") != pl.col("date").cast(pl.String)))
    add("source_identity", "FAILED" if bad_source.height else "PASSED",
        {"rows_checked": raw.height, "invalid_rows": bad_source.height,
         "source_files": len(source_hashes)},
        "Row source hashes and source dates must match the ingested inputs.",
        blocking=bool(bad_source.height))

    supplied = set(raw["instrument_id"]) | set(raw["symbol"])
    missing = sorted(set(cohort or []) - supplied)
    add("requested_cohort", "FAILED" if missing else "PASSED",
        {"requested": len(set(cohort or [])), "missing": len(missing),
         "instruments_observed": raw["instrument_id"].n_unique()},
        "Every explicitly requested cohort member must have source bars.",
        blocking=bool(missing), examples=missing)

    collisions = raw.group_by(["symbol", "date"]).agg(
        pl.col("instrument_id").n_unique().alias("identities")).filter(pl.col("identities") > 1)
    add("identifier_collisions", "FAILED" if collisions.height else "PASSED",
        {"ambiguous_symbol_dates": collisions.height},
        "Concurrent identities for a symbol require explicit source reconciliation.",
        blocking=bool(collisions.height), examples=collisions.head(10).to_dicts())

    sessions = sorted(set(raw["date"]))
    histories = raw.group_by("instrument_id").agg(
        pl.col("date").min().alias("first"), pl.col("date").max().alias("last"),
        pl.col("date").n_unique().alias("sessions"))
    gaps = []
    stale = []
    for row in histories.sort("instrument_id").iter_rows(named=True):
        observed_missing = sum(row["first"] <= day <= row["last"] for day in sessions) - row["sessions"]
        if observed_missing:
            gaps.append({"instrument_id": row["instrument_id"], "missing_sessions": observed_missing})
        lag = sum(day > row["last"] for day in sessions)
        if lag:
            stale.append({"instrument_id": row["instrument_id"], "lag_sessions": lag})
    add("observed_session_coverage", "WARNING" if gaps else "PASSED",
        {"observed_sessions": len(sessions), "instruments_with_gaps": len(gaps),
         "missing_instrument_sessions": sum(row["missing_sessions"] for row in gaps)},
        "Relative to dates observed in this cohort, not an official exchange calendar.", examples=gaps[:10])
    add("stale_history", "WARNING" if stale else "PASSED",
        {"instruments_ending_early": len(stale)},
        "Relative to the last supplied cohort session, not today's date or a live freshness guarantee.",
        examples=stale[:10])
    short_history = histories.filter(pl.col("sessions") < warmup_sessions)
    add("history_depth", "WARNING" if short_history.height else "PASSED",
        {"required_setup_lookback_sessions": warmup_sessions,
         "instruments_below_lookback": short_history.height},
        "Measured against the longest configured setup lookback; short history and zero setups are not fabricated evidence.")

    returns = features.sort(["instrument_id", "date"]).with_columns(
        (pl.col("adj_close") / pl.col("adj_close").shift(1).over("instrument_id") - 1)
        .alias("adjusted_return"))
    abnormal = returns.filter(pl.col("adjusted_return").is_not_null() &
        (~pl.col("adjusted_return").is_finite() |
         (pl.col("adjusted_return").abs() >= ABNORMAL_RETURN_THRESHOLD)))
    add("abnormal_adjusted_returns", "FAILED" if abnormal.height else "PASSED",
        {"rows_checked": features.height, "unexplained_jumps": abnormal.height},
        f"Absolute adjusted close return at or above {ABNORMAL_RETURN_THRESHOLD:.0%} requires source/action review; no automatic repair.",
        blocking=bool(abnormal.height), examples=abnormal.select(
            "instrument_id", "date", "close", "adj_close", "adjusted_return").head(10).to_dicts())

    delivery_rows = raw.filter(pl.col("deliverable_quantity").is_not_null() |
                               pl.col("deliverable_pct").is_not_null()).height
    add("delivery_availability", "PASSED" if delivery_rows == raw.height else "UNAVAILABLE",
        {"rows_with_delivery": delivery_rows, "rows_without_delivery": raw.height - delivery_rows,
         "quantity_nulls": raw["deliverable_quantity"].null_count(),
         "percentage_nulls": raw["deliverable_pct"].null_count()},
        "Missing optional delivery is retained as null; availability does not certify authentic delivery parsing.")
    no_provenance = sum(not item.get("acquisition", {}).get("source_url") or
                        not item.get("acquisition", {}).get("downloaded_at")
                        for item in inputs if item["kind"] == "ohlcv")
    add("acquisition_provenance", "WARNING" if no_provenance else "PASSED",
        {"files_missing_acquisition_fields": no_provenance},
        "Acquisition fields and input bytes are recorded; a supplied URL is not source authentication.")

    if calendar is None:
        add("calendar_completeness", "UNAVAILABLE", {"observed_sessions": len(sessions)},
            "No session calendar supplied; whole-cohort missing days cannot be detected.")
    else:
        expected = set(calendar["date"])
        missing_dates, unexpected = sorted(expected - set(sessions)), sorted(set(sessions) - expected)
        add("calendar_completeness", "FAILED" if missing_dates or unexpected else "PASSED",
            {"expected_sessions": len(expected), "missing_sessions": len(missing_dates),
             "unexpected_sessions": len(unexpected)},
            "Compared to the supplied calendar covering the run; calendar authenticity requires separate review.",
            blocking=bool(missing_dates or unexpected),
            examples=[{"missing": missing_dates[:10], "unexpected": unexpected[:10]}])

    add("corporate_action_reconciliation", "UNAVAILABLE",
        {"supplied_actions": 0 if actions is None else actions.height},
        "Factor application is checked, but official action dates, notices and completeness are not reconciled.")
    symbol_changes = raw.group_by("instrument_id").agg(
        pl.col("symbol").n_unique().alias("symbols")).filter(pl.col("symbols") > 1).height
    reused = raw.group_by("symbol").agg(
        pl.col("instrument_id").n_unique().alias("identities")).filter(pl.col("identities") > 1).height
    add("identifier_history", "UNAVAILABLE",
        {"instruments_with_symbol_changes": symbol_changes, "reused_symbols": reused},
        "Observed changes are counted; official identity history, delistings and survivorship remain unverified.")
    add("index_availability", "UNAVAILABLE" if index is None or index.is_empty() else "PASSED",
        {"supplied_rows": 0 if index is None else index.height},
        "Regime input availability only; eligible-cohort breadth is not full-market breadth.")

    blocking = [check["name"] for check in checks if check["blocking"]]
    status = "FAILED" if blocking else (
        "PASSED_WITH_WARNINGS" if any(check["status"] != "PASSED" for check in checks) else "PASSED")
    return {"schema_version": 1, "policy_version": QUALITY_VERSION,
            "status": status, "evidence_allowed": not blocking,
            "evidence_scope": "ENGINEERING_ONLY", "blocking_issues": blocking,
            "checks": checks, "policy": {"abnormal_return_threshold": ABNORMAL_RETURN_THRESHOLD},
            "limitations": [check["detail"] for check in checks if check["status"] != "PASSED"],
            "paper_research_approved": False}
