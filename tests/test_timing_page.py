"""Drive the timing page end to end against an isolated dataset and CSV."""
import csv

import pytest
from streamlit.testing.v1 import AppTest

from ar_copilot import config, timing
from ar_copilot.generate import generate

PAGE = str(config.ROOT / 'views' / 'timing.py')


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    generate(tmp_path / 'data')
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    return tmp_path


def start(app, operator):
    app.text_input[0].set_value(operator).run()
    next(b for b in app.button if b.label == 'Start next document').click().run()
    assert not app.exception


def test_manual_entry_is_timed_and_scored_without_storing_values(isolated):
    app = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not app.exception
    start(app, 'tester')
    filename = app.session_state['timing']['filename']
    truth = next(r for r in csv.DictReader((isolated / 'data' / 'ground_truth.csv').open()) if r['filename'] == filename)
    for field in app.text_input[1:]:
        key = field.label.lower().replace(' ', '_')
        field.set_value(truth[key])
    next(b for b in app.button if b.label == 'Finish document').click().run()
    assert not app.exception
    rows = timing.load_timings(isolated / 'results' / 'timings.csv')
    assert len(rows) == 1
    assert rows[0].method == 'manual' and rows[0].field_errors == 0 and rows[0].seconds > 0
    assert truth['customer'] not in (isolated / 'results' / 'timings.csv').read_text()


def test_assisted_demo_run_records_extraction_mode_and_corrections(isolated):
    app = AppTest.from_file(PAGE, default_timeout=30).run()
    app.button_group[0].set_value('assisted').run()
    next(r for r in app.radio if r.label == 'Extraction').set_value('demo').run()
    start(app, 'tester')
    next(f for f in app.text_input if f.label == 'Net').set_value('0.00')
    next(r for r in app.radio if r.label == 'Decision').set_value('reject')
    next(b for b in app.button if b.label == 'Finish document').click().run()
    assert not app.exception
    [row] = timing.load_timings(isolated / 'results' / 'timings.csv')
    assert (row.method, row.extraction_mode, row.decision) == ('assisted', 'demo', 'reject')
    assert row.fields_corrected == 1 and row.field_errors == 1
