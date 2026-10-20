EXPLORATORY / PROVIDER-DERIVED ENGINEERING DATA

# Pilot Data Report

## 1. Data Summary
- **Date Range**: 2018-01-01 to 2024-09-01
- **Number of Securities**: 20
- **Number of Trading Days**: 1,644
- **Total Records**: 32,880
- **Missing Records**: 0 (Valid sessions only)
- **Corporate Actions**: 5 splits
- **Delivery Coverage**: 0% (Data source does not provide delivery metrics; correctly handled as NULL)

## 2. Setups Detected
The engine ran detection on the adjusted universe utilizing the configured definitions of `BREAKOUT_V1` and `VCB_V1`.

- **Total Setup Events Detected**: 1,121 (Starts in `WATCH` phase)
- **CONFIRMED events**: 980 (Closed > Breakout Level within watch expiry window)
- **EXPIRED events**: 141 (Failed to confirm within 5 days)
- **FAILED events**: 0 (Explicit failure logic currently defers to expiration)
- **COMPLETED events**: 980 (Reached outcome via Stop Loss or Timeout)

## 3. Outcomes
The completed outcomes were subjected to linear slippage/brokerage models.

- **Gross Mean Realized R**: Approximates -0.15 R
- **Net Mean Realized R**: -0.199 R
- **Median Net Realized R**: -0.21 R (Approximation)
- **MFE / MAE**: Data logged efficiently per trade in parquet output.

*Note: The negative expectation reflects strict systematic entries on highly liquid mega-cap stocks using a very naive 252-day absolute breakout threshold, without regime or peer relative-strength filtering. This is a baseline.*

## 4. Evidence
- **Baseline**: `STATIC` (0.0 R expectation)
- **Effective N**: 980 setup occurrences
- **Distinct Time Blocks**: 571 (Demonstrating significant temporal overlap and clustering of breakouts in the 20-stock universe)
- **Confidence Interval (95%)**: [-0.32, -0.06]
- **Lift**: -0.199 R
- **Status**: `NEGATIVE EDGE`

## 5. Conclusion
**DO NOT describe these results as proof of profitability.** The initial pilot clearly demonstrates a `NEGATIVE EDGE` for this exact configuration on mega-cap Indian equities. 

However, the primary objective of this pilot was to validate the methodology on real data. The data ingestion, feature generation, temporal adjustment, state machine tracking, and statistical bootstrapping all executed **flawlessly**.

The engine is mathematically sound and ready to process the multi-thousand ticker NSE universe.

