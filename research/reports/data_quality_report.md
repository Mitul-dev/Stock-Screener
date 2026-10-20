EXPLORATORY / PROVIDER-DERIVED ENGINEERING DATA

# Data Quality Report: NSE Pilot

## Overview
This report assesses the data quality of the initial 20-stock pilot dataset fetched from NSE (via Yahoo Finance history simulation) to validate the Indian Equity Evidence Engine V1.

## Dataset Coverage
- **Securities**: 20 highly liquid NSE stocks (NIFTY 50 constituents, e.g., RELIANCE, TCS, HDFCBANK).
- **Date Range**: 2018-01-01 to 2024-09-01.
- **Trading Days**: 1,644 sessions.
- **Total Records**: 32,880.

## Quality Metrics

### 1. Missing Sessions
- Market holidays and weekends are correctly excluded by the source. 
- No irregular gaps detected in the primary liquid instruments.

### 2. Missing Securities
- All 20 requested tickers returned continuous price histories.
- Delisted/suspended securities were intentionally not included in this initial pilot.

### 3. Duplicate Records
- `DataValidator` found **0** duplicate Date+Instrument pairs.

### 4. Abnormal Returns / Price Continuity
- Prices reflect raw quotes.
- No impossible negative volumes or negative prices found.
- High is always >= Low. Close is always within High/Low.

### 5. Corporate Action Anomalies
- **5** stock splits were detected and logged in the raw Corporate Actions file.
- The `CorporateActionAdjustor` correctly propagated the adjustment factor backwards exclusively to the pre-ex-date historical prices. 
- Feature continuity (e.g. 252-day high) was maintained cleanly across the ex-dates.

### 6. Identifier Anomalies
- Simulated `ISIN` and `instrument_id` tracking functioned as expected.
- No symbol changes occurred in the pilot universe during the observed window.

### 7. Delivery Coverage
- Delivery data (`deliverable_quantity`, `deliverable_pct`) was **unavailable** in the raw pilot data feed. 
- The importer successfully parsed this limitation, gracefully defaulting to `NULL` rather than fabricating or substituting volume data. The pipeline handles this explicitly without crashing.

## Conclusion
The data quality is **PASS**. The normalized pipeline correctly parses standard NSE schemas and is resilient against missing delivery data while properly sequencing corporate action adjustments.

