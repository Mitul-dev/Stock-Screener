# Indian Equity Evidence Engine — V1

A personal-use Indian equity research and alerting system.

## Core Purpose

> "When a clearly defined technical setup appears, what historically happened after comparable setups?"

## Features
- Market Data Ingestion
- Corporate Actions & Security Master
- Point-in-Time Universe
- Technical Features
- Rule-Based Setups (Breakout, VCB)
- Historical Outcomes Labeling
- Statistical Evidence
- Alerts (Telegram) & Dashboard (Streamlit)

## Setup
1. Clone the repository.
2. Create virtual environment: `python -m venv .venv`
3. Activate virtual environment.
4. Install dependencies: `pip install -e .[test]`

## Official NSE ingestion milestone

An unchanged official CM UDiFF fixture for 2026-10-08 is retained under
`tests/fixtures/nse/`, with acquisition provenance and offline reconciliation tests.
Import it with:

```powershell
.venv\Scripts\python.exe scripts/import_nse_eod.py tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip --provenance tests/fixtures/nse/BhavCopy_NSE_CM_0_0_0_20261008_F_0000.csv.zip.provenance.json
```

Repeated imports verify and reuse the same artifact; changed bytes create a distinct
version. See `docs/data.md` for the ingestion contract and `BUILD_STATUS.md` for the
remaining pilot gates. The full 20–30-stock historical pipeline is not yet verified.

## Production research runner

`scripts/run_pilot_pipeline.py` now loads the existing setup/universe/cost/regime
configuration, applies event-date universe eligibility and runs discovery,
validation and holdout separately. Each invocation preserves a run directory with
source hashes, configuration, date boundaries, typed outcomes and linked frozen
snapshots. See `docs/pilot_pipeline.md` for usage and limits of the verified milestone.
