"""Software-only UI tests in temporary files; never human performance observations."""
from pathlib import Path
import csv
import time

from streamlit.testing.v1 import AppTest

from ar_copilot import config
from ar_copilot.core import FIELDS, FIELD_LABELS
from ar_copilot.generate import generate
from ar_copilot.timing import load_timings, summarise


def page(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    generate(tmp_path / 'runtime' / 'timing_data', seed=20261011)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=20)
    app.switch_page('views/timing.py').run()
    assert not app.exception
    next(w for w in app.text_input if w.label == 'Operator alias').set_value('SOFTWARE-TEST-ONLY').run()
    return app


def button(app, label):
    return next(w for w in app.button if w.label == label)


def test_clock_includes_extraction_and_submission_and_start_is_durable(tmp_path, monkeypatch):
    app = page(tmp_path, monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(time, 'perf_counter', lambda: clock[0])
    def fake_extract(*args, **kwargs):
        assert load_timings()[0].status == 'in_progress'
        clock[0] = 105.0
        return dict(fields={}, seconds=5.0, error=None, model=None)
    monkeypatch.setattr('ar_copilot.extract.extract', fake_extract)
    app.segmented_control[0].set_value('assisted').run()
    button(app, 'Start next document').click().run()
    assert not app.exception
    assert len(load_timings()) == 1 and load_timings()[0].extraction_seconds == 5
    clock[0] = 125.0
    button(app, 'Finish document').click().run()
    assert not app.exception
    result = load_timings()[0]
    assert result.seconds == 25 and result.extraction_seconds == 5
    assert result.practice and result.extraction_mode == 'demo'
    assert result.status == 'completed' and result.field_errors > 0
    assert summarise(load_timings())['groups'] == {}


def test_abandon_retained_and_new_attempt_fields_do_not_reuse_previous_input(tmp_path, monkeypatch):
    app = page(tmp_path, monkeypatch)
    button(app, 'Start next document').click().run()
    assert not app.exception
    next(w for w in app.text_input if w.label == 'Customer').set_value('TEST-INPUT')
    button(app, 'Record incomplete attempt').click().run()
    assert not app.exception
    rows = load_timings()
    assert rows[0].status == 'incomplete' and rows[0].field_errors is None
    button(app, 'Start next document').click().run()
    assert not app.exception
    assert next(w for w in app.text_input if w.label == 'Customer').value == ''


def test_lost_session_is_retained_without_guessing_duration(tmp_path, monkeypatch):
    app = page(tmp_path, monkeypatch)
    button(app, 'Start next document').click().run()
    app.session_state['timing'] = {}
    app.run()
    assert not app.exception
    button(app, 'Record interrupted attempts').click().run()
    assert not app.exception
    row = load_timings()[0]
    assert row.status == 'incomplete' and not row.duration_known
    assert row.failure_reason == 'interrupted'


def test_daily_quota_stops_and_does_not_retry(tmp_path, monkeypatch):
    app = page(tmp_path, monkeypatch)
    app.segmented_control[0].set_value('assisted').run()
    next(w for w in app.radio if w.label == 'Practice extraction').set_value('gemini').run()
    monkeypatch.setattr('ar_copilot.config.configuration_status', lambda: {
        'key_configured': True, 'model': 'gemini-3.8-flash'})
    calls = []
    def fake_extract(*args, **kwargs):
        calls.append(1)
        return dict(fields={}, seconds=0.00001, error='TEST-ONLY', model='gemini-3.8-flash',
                    error_kind='daily_quota_exhausted')
    monkeypatch.setattr('ar_copilot.extract.extract', fake_extract)
    app.run()
    button(app, 'Start next document').click().run()
    assert not app.exception
    assert len(calls) == 1
    assert load_timings()[0].status == 'incomplete'
    assert load_timings()[0].api_failed
    assert button(app, 'Start next document').disabled


def test_manual_entry_scoring_does_not_store_entered_values(tmp_path, monkeypatch):
    app = page(tmp_path, monkeypatch)
    button(app, 'Start next document').click().run()
    filename = app.session_state['timing']['attempt'].filename
    source = tmp_path / 'runtime' / 'timing_data' / 'ground_truth.csv'
    with source.open(encoding='utf-8') as handle:
        truth = next(row for row in csv.DictReader(handle) if row['filename'] == filename)
    for field in FIELDS:
        next(w for w in app.text_input if w.label == FIELD_LABELS[field]).set_value(truth[field])
    button(app, 'Finish document').click().run()
    assert not app.exception
    result = load_timings()[0]
    assert result.field_errors == 0 and result.decision_error is False
    raw = (tmp_path / 'runtime' / 'timings.csv').read_text()
    assert truth['customer'] not in raw and truth['supplier'] not in raw


def test_demo_proposal_corrections_and_decision_errors_are_scored(tmp_path, monkeypatch):
    app = page(tmp_path, monkeypatch)
    app.segmented_control[0].set_value('assisted').run()
    button(app, 'Start next document').click().run()
    assert not app.exception
    next(w for w in app.text_input if w.label == 'Net').set_value('0.00')
    next(w for w in app.radio if w.label == 'Decision').set_value('reject')
    button(app, 'Finish document').click().run()
    assert not app.exception
    result = load_timings()[0]
    assert result.extraction_mode == 'demo' and result.fields_corrected == 1
    assert result.field_errors == 1 and result.decision_error is True
