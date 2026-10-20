# Genuine historical source acquisition

This guide accompanies `research/pilot/historical_inventory_v1.json`.
The inventory is preparation, with one retained official session. Historical
acquisition and full calendar/action/identity reconciliation are incomplete.

## Fixed scope

Use the unchanged 20-stock engineering cohort in `research/pilot/cohort_v1.json`.
Keep BREAKOUT_V1.0, VCB_V1.0 and the current costs/universe/regime/research
configuration unchanged. Preserve raw OHLCV and source identities. Do not select
replacement stocks, dates or parameters because of signal frequency or outcomes.
Current-survivor selection does not establish survivorship-safe research.

The proposed source span is 2023-01-01 through the retained 2026-10-08 anchor.
Dates, expected sessions and usable partition/follow-up coverage must be measured
against authenticated sources before admission. The existing 252-session maximum
setup lookback, 60/20/20 split and 5+20-session watch/holding gap remain unchanged.

## Acquisition order

1. Retain original CM trading-calendar notices for every covered year and their
   subsequent amendments. Include special live and Muhurat sessions. Keep
   clearing/bank holidays and T+0-only rules separate from the normal CM calendar.
   Generate a separately versioned, source-linked expected-session CSV only when
   reviewed. Do not derive the authority calendar from weekdays or downloaded bars.
2. Acquire original legacy and UDiFF checkpoint files from official dated report
   links, preserving original filenames and response bytes, SHA-256, acquisition
   time, requested/final URL, headers and member/date checks. The existing official
   fetcher supports UDiFF only. Do not use it as a legacy downloader.
3. Reconcile an authentic legacy checkpoint independently against the parser's
   date, ISIN, reported turnover/units and OHLCV handling. Historical parser
   existence and synthetic tests do not establish genuine legacy support.
4. Retrieve complete dated action exports and issuer/CM notices for every cohort
   member, plus relevant dated security-master/symbol/ISIN-change notices. Preserve
   bytes and source timestamps; a blank dynamic page is not a no-action certificate.
5. Resolve source identity continuity before grouping historical features or
   applying actions. Current `instrument_id` is the raw ISIN. It may change at a
   split or restructuring. Dated mapping must retain those original IDs, not
   overwrite them with a guessed stable entity ID or join solely by ticker.
6. Reconcile each action against original surrounding bars and dates. Announcement,
   scheme-effective, record, ex-date and first-known timestamps must remain distinct.
   The runner accepts explicit SPLIT/BONUS types only. Unsupported restructurings
   keep affected histories blocked pending a documented V1 methodology decision;
   do not drop members or silently treat restructurings as split factors.
7. Expand to every authenticated expected session. Measure source coverage,
   gaps/staleness, warmup, actual partition boundaries and follow-up. Preserve
   missing delivery as null. The full bhavcopy/delivery report needs a genuinely
   verified adapter and units/identity reconciliation before use.
8. Obtain official index history where supplied for regime context. Keep missing
   inputs visible as UNKNOWN. An earlier Yahoo-derived file is not official NSE
   evidence. Cohort breadth remains cohort breadth.

## Located official sources

| Source | Link | What is established now |
|---|---|---|
| Dated report families | [NSE daily/historical reports](https://www.nseindia.com/all-reports) | Listing and July 2024 format-discontinuation notice read; no multi-year backfill acquired. |
| Formats | [NSE UDiFF catalogue](https://www.nseindia.com/static/resources/forms-formats-members) | Format/sample index located; authentic trading-day legacy proof remains missing. |
| Calendar authority | [NSE holidays](https://www.nseindia.com/resources/exchange-communication-holidays) | Calendar entry point; annual closure/amendment files still need retention. |
| Dated security/identity support | [NSE security downloads](https://www.nseindia.com/static/market-data/securities-available-for-trading) | Current equity, symbol-change and company-name-change CSV links resolved; content not acquired. |
| Actions | [NSE corporate actions](https://www.nseindia.com/companies-listing/corporate-filings-actions) | Dynamic export entry point; complete cohort/date coverage remains missing. |
| Index history | [NSE Indices historical data](https://www.niftyindices.com/reports/historical-data) | Official export interface located; history not acquired. |

The catalogue records document-level references and retrieval limits. Original
PDF/CSV response bytes from the web lookups were not retained. Do not assign them
invented hashes or acquisition receipts.

## Immediate reconciliation cases

| Member or date | Located evidence | Required handling |
|---|---|---|
| RELIANCE, 2023-07-20 | [NSE Indices notice](https://nsearchives.nseindia.com/web/sites/default/files/2023-07/ind_prs17072023.pdf) | Financial-services demerger; current split/bonus handling does not reconcile it. |
| RELIANCE, 2024-10-28 | [NSE underlying-action cross-check](https://nsearchives.nseindia.com/content/circulars/FAOP64621.pdf) | 1:1 bonus; candidate factor 2 requires CM notice/identity and raw-bar reconciliation. |
| ITC, 2025 demerger | [Issuer source index](https://itcportal.com/investors/proposed-demerger-hotels-business.html) | Confirm CM ex-date separately from scheme effective/record date; approved factor remains null. |
| BAJFINANCE, 2025-06-16 | [NSE underlying-action cross-check](https://nsearchives.nseindia.com/content/circulars/FAOP68547.pdf) | Split and bonus components 2 and 5; combine once after CM identity/source reconciliation. |
| 2024-03-02 | [NSE CM special-session notice](https://nsearchives.nseindia.com/content/circulars/MSD60677.pdf) | Saturday live session must be addressed by the expected-session source ledger. |
| 2024-05-18 | [NSE CM special-session notice](https://nsearchives.nseindia.com/content/circulars/MSD61893.pdf) | Another Saturday session; distinguish the notice's T+0 settlement restriction. |

The action cross-check notices are issued by NSE's derivatives department. They
are used only as documentary evidence about the underlying equity actions;
contract adjustments, derivatives data and strategies remain outside V1.

These are positive discovery cases, not a complete corporate-action history.
Candidate factors are not an engine-ready action feed, and a return below the
existing quality review threshold does not make a known restructuring safe.

## First command after execution is available

After confirming the requested session against the calendar, a UDiFF checkpoint
can use the existing command:

```bash
python scripts/fetch_official_nse_fixture.py --market-date 2024-07-08 --destination data/raw/historical_checkpoints/udiff
```

That command has **not been run in this source-preparation step**. It does not
fetch pre-transition legacy files. Retain and reconcile a real legacy checkpoint
before extending the supported historical acquisition path.

Do not invoke a full historical pilot until the source, calendar, identity and
unsupported-action gates are resolved. Engineering admission and paper-research
approval remain separate decisions.
