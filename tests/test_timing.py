"""Timing rows round-trip through CSV and summarise without inventing anything."""
from ar_copilot.core import FIELDS
from ar_copilot.timing import (Timing, append_timing, count_corrections, count_field_errors,
                               load_timings, summarise)


def timing(method='manual', seconds=60.0, errors=0, practice=False, mode='none'):
    return Timing(recorded_at='2026-10-10T12:00:00+00:00', operator='tester', method=method,
                  extraction_mode=mode, filename='NC-0001.pdf', seconds=seconds, extraction_seconds=0.0,
                  fields_corrected=0, field_errors=errors, decision='accept', practice=practice)


def test_csv_round_trip_preserves_types(tmp_path):
    path = tmp_path / 'timings.csv'
    rows = [timing(seconds=61.5), timing(method='assisted', mode='gemini', practice=True)]
    for row in rows:
        append_timing(row, path)
    assert load_timings(path) == rows
    assert path.read_text().count('recorded_at') == 1


def test_scoring_uses_exact_strings_and_counts_blank_as_missing():
    truth = dict.fromkeys(FIELDS, 'x') | {'linked_invoice': ''}
    entered = dict(truth, net='x ', vat='y')
    assert count_field_errors(entered, truth) == 1  # outer whitespace forgiven, wrong value is not
    assert count_corrections({'net': None, 'vat': 'y'}, {'net': '', 'vat': 'z'}) == 1


def test_summary_excludes_practice_and_reports_spread():
    rows = [timing(seconds=s, errors=e) for s, e in [(40, 0), (50, 1), (60, 0), (100, 2)]]
    rows.append(timing(seconds=999, practice=True))
    summary = summarise(rows)
    manual = summary['groups']['manual/none']
    assert summary['practice_rows_excluded'] == 1
    assert manual['documents'] == 4
    assert manual['seconds'] == dict(median=55.0, q1=47.5, q3=70.0, min=40.0, max=100.0)
    assert manual['field_errors_total'] == 3 and manual['documents_with_errors'] == 2
    assert manual['field_error_rate'] == 3 / (4 * len(FIELDS))


def test_empty_file_gives_empty_summary(tmp_path):
    assert summarise(load_timings(tmp_path / 'missing.csv')) == {'practice_rows_excluded': 0, 'groups': {}}


def test_markdown_only_compares_manual_with_live_assisted_runs():
    from scripts.summarize_timings import render_markdown
    manual_only = render_markdown(summarise([timing(seconds=50), timing(method='assisted', mode='demo', seconds=10)]))
    assert 'No time-saved comparison' in manual_only
    both = render_markdown(summarise([timing(seconds=50), timing(method='assisted', mode='gemini', seconds=20)]))
    assert 'manual minus assisted (Gemini): 30.0 s' in both
