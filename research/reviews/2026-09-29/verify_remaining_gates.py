"""Independent observations only; no application source/configuration changes.

All market inputs below are explicitly SYNTHETIC, never official-data evidence.
Run from the repository with its existing virtual environment.
"""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
from unittest.mock import patch

import polars as pl

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parent
fixture = runpy.run_path(str(ROOT / 'research/reviews/2026-09-28/reverification/test_pipeline_gates.py'))
source_frame, raw_frame, sessions, CONFIG = [fixture[k] for k in ('source_frame', 'raw_frame', 'sessions', 'CONFIG')]
from equity_engine.ingestion.nse_importer import NSEImporter
from equity_engine.corporate_actions.adjustor import CorporateActionAdjustor
from equity_engine.features.calculator import FeatureCalculator
from equity_engine.setups.breakout import BreakoutDetector, SetupEvent
from equity_engine.setups.vcb import VCBDetector
from equity_engine.outcomes.engine import OutcomeEngine
from equity_engine.backtest.engine import ResearchEngine
from equity_engine.backtest.controls import ControlEngine
from equity_engine.evidence.snapshot import EvidenceSnapshot
from equity_engine.alerts.telegram import TelegramAlerter


def bounds(frame):
    return {'rows': frame.height, 'sessions': frame['date'].n_unique(),
            'first': frame['date'].min(), 'last': frame['date'].max()}


def production(frame):
    observations = {'split_calls': [], 'backtest_calls': [], 'snapshots': []}
    split_impl, backtest_impl = ResearchEngine.split_data, ResearchEngine.run_backtest
    snapshot_impl = EvidenceSnapshot.create_snapshot

    def split(self, data, *args, **kwargs):
        parts = split_impl(self, data, *args, **kwargs)
        observations['split_calls'].append(dict(zip(('discovery', 'validation', 'holdout'), map(bounds, parts))))
        return parts

    def backtest(self, events, data, *args, **kwargs):
        observations['backtest_calls'].append({'data': bounds(data), 'events': len(events),
            'event_dates': [e.timestamp for e in events], 'instrument_ids': sorted(set(e.instrument_id for e in events))})
        return backtest_impl(self, events, data, *args, **kwargs)

    def snapshot(self, *args, **kwargs):
        snapshot_id = snapshot_impl(self, *args, **kwargs)
        meta, outcomes = self.load_snapshot(snapshot_id)
        observations['snapshots'].append({'metadata': meta, 'outcomes': outcomes.to_dicts()})
        return snapshot_id

    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix='independent-pilot-') as directory:
        root = Path(directory)
        raw = root / 'data/raw'
        raw.mkdir(parents=True)
        (root / 'data/processed').mkdir()
        frame.write_csv(raw / 'NSE_Pilot_Bhavcopy.csv')
        pl.DataFrame(schema={'TradDt': pl.String, 'TckrSymb': pl.String, 'Ratio': pl.Float64}).write_csv(raw / 'NSE_Pilot_CorpActions.csv')
        dates = frame['TradDt'].unique().sort().to_list()
        pl.DataFrame({'date': dates, 'close': [100.] * len(dates)}).write_csv(raw / 'NIFTY50.csv')
        output = io.StringIO()
        try:
            os.chdir(root)
            with patch.object(ResearchEngine, 'split_data', split), patch.object(ResearchEngine, 'run_backtest', backtest), patch.object(EvidenceSnapshot, 'create_snapshot', snapshot), contextlib.redirect_stdout(output):
                runpy.run_path(str(ROOT / 'scripts/run_pilot_pipeline.py'))['run_pilot']()
            observations['outcomes'] = pl.read_parquet(root / 'data/processed/pilot_outcomes.parquet').to_dicts()
            observations['artifacts'] = sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
            observations['stdout'] = output.getvalue()
        finally:
            os.chdir(original_cwd)
    return observations


def split_frames(symbol, split_index, false_watch=False):
    raw = raw_frame(symbol)
    dates = raw['date'].to_list()
    if false_watch:
        raw = raw.with_columns([pl.when(pl.col('date') == dates[260]).then(pl.lit(v)).otherwise(pl.col(c)).alias(c)
            for c, v in [('open', 94.), ('high', 95.), ('low', 93.), ('close', 94.)]])
    raw = raw.with_columns([pl.when(pl.col('date') >= dates[split_index]).then(pl.col(c) / 2).otherwise(pl.col(c)).alias(c)
        for c in ['open', 'high', 'low', 'close']] + [pl.when(pl.col('date') >= dates[split_index]).then(pl.col('volume') * 2).otherwise(pl.col('volume')).alias('volume')])
    actions = pl.DataFrame({'date': [dates[split_index]], 'factor': [2.]})
    adjusted = CorporateActionAdjustor.adjust_ohlcv(raw, actions)
    projected = adjusted.with_columns([pl.col('adj_' + c).alias(c) for c in ['open', 'high', 'low', 'close', 'volume']])
    return adjusted, projected, actions


def split_probe(symbol, split_index, detector, false_watch=False):
    adjusted, projected, actions = split_frames(symbol, split_index, false_watch)
    result = {'split_date': adjusted['date'][split_index], 'event_date': adjusted['date'][260],
              'raw_close': adjusted['close'][260], 'adjusted_close': adjusted['adj_close'][260]}
    for label, data in [('actual', adjusted), ('consistent_basis_reference', projected)]:
        features = FeatureCalculator.calculate_features(data)
        events = [e for e in detector.detect('TEST_' + symbol, features) if e.timestamp == data['date'][260]]
        result[label] = [{'breakout_level': e.breakout_level, 'result': OutcomeEngine({}).evaluate_event(e, features)} for e in events]
    return result


def main():
    results = {'notice': 'Synthetic diagnostic inputs only. No official NSE fixture used.'}
    combined = pl.concat([source_frame(s) for s in ['BREAKOUT', 'VCB', 'EXPIRED', 'CENSORED', 'INVALID', 'FAILED']])
    results['production_acceptance'] = production(combined)

    # A candidate in the helper's supposed purge gap is still evaluated through
    # the first validation session by the real runner; no detached backtest.
    frame = source_frame('BOUNDARY', 600)
    days = sessions(600)
    frame = frame.with_columns(pl.when(pl.col('TradDt') == days[361].isoformat()).then(pl.lit(2000)).otherwise(pl.col('TtlTradgVol')).alias('TtlTradgVol'))
    for col, confirmation, later in [('OpnPric', 101., 103.), ('HghPric', 103., 104.), ('LwPric', 100., 102.), ('ClsPric', 102., 103.)]:
        frame = frame.with_columns(pl.when(pl.col('TradDt') == days[365].isoformat()).then(pl.lit(confirmation)).when(pl.col('TradDt') > days[365].isoformat()).then(pl.lit(later)).otherwise(pl.col(col)).alias(col))
    frame = frame.with_columns((pl.col('ClsPric') * pl.col('TtlTradgVol')).alias('TtlTrfVal'))
    results['production_boundary'] = production(frame)

    # The purge is counted over all market dates, but outcomes count available
    # instrument bars. Missing sessions let a DISCOVERY event cross validation.
    sparse = source_frame('SPARSE', 600)
    sparse = sparse.with_columns(pl.when(pl.col('TradDt') == days[360].isoformat()).then(pl.lit(2000)).otherwise(pl.col('TtlTradgVol')).alias('TtlTradgVol'))
    for col, confirmation, later in [('OpnPric', 101., 103.), ('HghPric', 103., 104.), ('LwPric', 100., 102.), ('ClsPric', 102., 103.)]:
        sparse = sparse.with_columns(pl.when(pl.col('TradDt') == days[364].isoformat()).then(pl.lit(confirmation)).when(pl.col('TradDt') > days[364].isoformat()).then(pl.lit(later)).otherwise(pl.col(col)).alias(col))
    sparse = sparse.filter(~pl.col('TradDt').is_in([d.isoformat() for d in days[370:390]]))
    sparse = sparse.with_columns((pl.col('ClsPric') * pl.col('TtlTradgVol')).alias('TtlTrfVal'))
    results['production_discovery_crosses_validation'] = production(pl.concat([sparse, source_frame('CALENDAR', 600)]))

    results['split_watch_false_candidate'] = split_probe('EXPIRED', 262, BreakoutDetector(CONFIG['BREAKOUT_V1']), True)
    results['split_watch_vcb'] = split_probe('VCB', 261, VCBDetector(CONFIG['VCB_V1']))
    results['split_holding_breakout'] = split_probe('BREAKOUT', 270, BreakoutDetector(CONFIG['BREAKOUT_V1']))
    adjusted, projected, actions = split_frames('EXPIRED', 262)
    try:
        twice = CorporateActionAdjustor.adjust_ohlcv(projected.with_columns(pl.lit('adjusted').alias('price_basis')), actions)
        results['double_adjustment'] = {'first_before': adjusted['adj_close'][260], 'second_before': twice['adj_close'][260],
                                       'first_after': adjusted['adj_close'][263], 'second_after': twice['adj_close'][263], 'rejected': False}
    except ValueError:
        results['double_adjustment'] = {'first_before': adjusted['adj_close'][260], 'second_before': None,
                                       'first_after': adjusted['adj_close'][263], 'second_after': None, 'rejected': True}

    day = sessions(1)[0]
    def metrics(values):
        return ControlEngine.calculate_metrics(pl.DataFrame({'setup': ['BREAKOUT_V1.0'] * len(values),
            'net_realized_r': values, 'detection_date': [day] * len(values)}), seed=123)
    results['statistics'] = {'n1': metrics([1.]), 'n2_same_date_without_oos': metrics([1., 1.]),
        'bootstrap_n5_first': metrics([-1., .2, .5, 1., 2.]), 'bootstrap_n5_second': metrics([-1., .2, .5, 1., 2.])}

    with tempfile.TemporaryDirectory(prefix='independent-boundaries-') as directory:
        root = Path(directory)
        importer = NSEImporter(str(root), str(root / 'processed'))
        source = root / 'same_name.csv'
        source_frame(n=1).write_csv(source)
        output = Path(importer.process_bhavcopy(str(source)))
        old_hash = hashlib.sha256(output.read_bytes()).hexdigest()
        source_frame(n=1).with_columns(pl.lit(100.5).alias('ClsPric')).write_csv(source)
        try:
            output2 = Path(importer.process_bhavcopy(str(source)))
            overwrite_rejected = False
        except (FileExistsError, ValueError):
            output2 = output
            overwrite_rejected = True
        results['immutability'] = {'same_output_path': output == output2, 'original_hash': old_hash,
            'replacement_hash': hashlib.sha256(output2.read_bytes()).hexdigest(), 'overwrite_rejected': overwrite_rejected}
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_CHAT_ID': '', 'TEST_ENV': '1'}):
            manager = EvidenceSnapshot(str(root))
            snapshot_id = manager.create_snapshot('BREAKOUT_V1.0', 'test', 'test', day, metrics([1.]), pl.DataFrame({'value': [1]}))
            alert = TelegramAlerter(str(root / 'outbox.db'))
            try:
                missing = alert.send_alert('missing-snapshot-event', 'TEST', 'BREAKOUT_V1.0', 'Caller supplied text')
                valid = alert.send_alert(snapshot_id, 'TEST', 'BREAKOUT_V1.0', 'Existing snapshot')
                results['alerts'] = {'missing_evidence_accepted': missing, 'valid_snapshot_accepted': valid,
                    'outbox': alert.conn.execute('SELECT alert_id, message FROM outbox ORDER BY alert_id').fetchall(),
                    'network_requests': 0}
            finally:
                alert.conn.close()

    from equity_engine.dashboard import app
    displayed = []
    class Column:
        def metric(self, label, value): displayed.append([label, value])
    class Display:
        def columns(self, count): return [Column() for _ in range(count)]
        def title(self, *args): pass
        def subheader(self, *args): pass
        def info(self, *args): pass
    with patch.object(app, 'st', Display()):
        app.render_overview()
    results['dashboard_metrics'] = displayed
    results['source_changes_since_review_started'] = [item['path'] for item in json.loads((DEST / 'source_snapshot.json').read_text(encoding='utf-8-sig'))
        if hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() != item['sha256']]
    (DEST / 'observations.json').write_text(json.dumps(results, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'report': str(DEST / 'observations.json'), 'source_changes': results['source_changes_since_review_started'],
        'split_watch_false_candidate': results['split_watch_false_candidate'], 'split_watch_vcb': results['split_watch_vcb'],
        'double_adjustment': results['double_adjustment'], 'n2': results['statistics']['n2_same_date_without_oos'],
        'dashboard': displayed}, indent=2, default=str))


if __name__ == '__main__':
    main()
