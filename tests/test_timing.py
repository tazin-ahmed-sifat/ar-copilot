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
    summary = summarise(load_timings(tmp_path / 'missing.csv'))
    assert summary['groups'] == {} and summary['practice_rows_excluded'] == 0
    assert not summary['comparison']['available']


def test_markdown_only_compares_manual_with_live_assisted_runs():
    from scripts.summarize_timings import render_markdown
    manual_only = render_markdown(summarise([timing(seconds=50), timing(method='assisted', mode='demo', seconds=10)]))
    assert 'No time-saved comparison' in manual_only
    both = render_markdown(summarise([timing(seconds=50), timing(method='assisted', mode='gemini', seconds=20)]))
    assert 'No time-saved comparison' in both  # legacy rows have no comparable-set/order evidence


def planned_rows():
    from dataclasses import replace
    from ar_copilot.timing import PROTOCOL, collection_plan
    return [replace(timing(method=task['method'], mode='none' if task['method'] == 'manual' else 'gemini',
                           seconds=50 if task['method'] == 'manual' else 20),
                    attempt_id=f"test-{task['sequence']}", study_id='TEST-ONLY', cohort='A',
                    filename=task['filename'], pair_id=task['pair_id'], sequence=task['sequence'],
                    layout=task['layout'], protocol=PROTOCOL, decision_error=False, corpus_id='TEST-CORPUS',
                    model='gemini-3.8-flash' if task['method'] == 'assisted' else '')
            for task in collection_plan('A')]


def test_matched_comparison_formula_and_publication_privacy():
    import json
    from scripts.summarize_timings import render_markdown
    summary = summarise(planned_rows())
    result = summary['comparison']
    assert result['completed_pairs'] == 6 and result['percentage_time_reduction'] == 60
    text = render_markdown(summary)
    assert 'manual minus assisted (Gemini): 30.0 s' in text
    assert 'Percentage time reduction: 60.0%' in text
    assert all(private not in json.dumps(summary) + text for private in ('tester', 'NC-', 'TEST-ONLY', 'test-1'))


def test_incomplete_pairs_errors_and_api_failures_are_not_silently_dropped():
    from dataclasses import replace
    rows = planned_rows()
    rows[1] = replace(rows[1], status='incomplete', field_errors=None, decision='',
                      decision_error=None, api_failed=True, failure_reason='daily_quota_exhausted')
    summary = summarise(rows)
    assisted = summary['groups']['assisted/gemini']
    assert assisted['documents'] == 6 and assisted['completed'] == 5 and assisted['incomplete'] == 1
    assert assisted['api_failures'] == 1
    assert summary['comparison']['completed_pairs'] == 5
    assert summary['comparison']['incomplete_pairs_excluded'] == 1
    assert assisted['field_error_rate'] == 0


def test_abandon_and_lost_session_events_survive_reload_once(tmp_path):
    from dataclasses import replace
    path = tmp_path / 'events.csv'
    start = replace(timing(), attempt_id='test-only', seconds=0, status='in_progress',
                    duration_known=False, field_errors=None, decision='')
    append_timing(start, path)
    assert load_timings(path) == [start]
    final = replace(start, status='incomplete', failure_reason='interrupted')
    append_timing(final, path)
    assert load_timings(path) == [final]
    group = summarise(load_timings(path))['groups']['manual/none']
    assert group['seconds']['median'] is None and group['unknown_durations'] == 1


def test_invalid_duration_boolean_and_duplicate_final_events_fail_validation(tmp_path):
    import pytest
    from dataclasses import replace
    from ar_copilot.timing import validate_timing
    for seconds in (float('nan'), float('inf'), -1, 0):
        with pytest.raises(ValueError):
            validate_timing(replace(timing(), seconds=seconds))
    path = tmp_path / 'events.csv'
    row = replace(timing(), attempt_id='duplicate')
    append_timing(row, path)
    append_timing(row, path)
    with pytest.raises(ValueError, match='Duplicate final'):
        load_timings(path)
    path.write_text(path.read_text().replace('False', 'wrong'))
    with pytest.raises(ValueError, match='boolean'):
        load_timings(path)


def test_plan_balances_layout_and_order_and_separates_practice():
    from collections import Counter
    from ar_copilot.timing import PRACTICE_DOCUMENTS, collection_plan
    for cohort in ('A', 'B'):
        plan = collection_plan(cohort)
        assert len({r['filename'] for r in plan}) == 12
        assert not set(PRACTICE_DOCUMENTS) & {r['filename'] for r in plan}
        for method in ('manual', 'assisted'):
            assert Counter(r['layout'] for r in plan if r['method'] == method) == {'1': 2, '2': 2, '3': 2}
        assert Counter(r['method'] for r in plan[::2]) == {'manual': 3, 'assisted': 3}
    assert collection_plan('A')[0]['filename'] == collection_plan('B')[0]['filename']
    assert collection_plan('A')[0]['method'] != collection_plan('B')[0]['method']


def test_incomplete_study_or_repeated_exposure_refuses_percentage():
    from dataclasses import replace
    rows = planned_rows()
    assert not summarise(rows[:-1])['comparison']['available']
    exposed = replace(timing(practice=True), filename=rows[0].filename, corpus_id='TEST-CORPUS')
    assert not summarise(rows + [exposed])['comparison']['available']
    slower = [replace(r, seconds=70) if r.method == 'assisted' else r for r in rows]
    assert summarise(slower)['comparison']['percentage_time_reduction'] == -40


def test_summary_script_refuses_unresolved_or_practice_only_and_publishes_only_aggregates(tmp_path, monkeypatch):
    import json
    import sys
    import pytest
    from dataclasses import replace
    from scripts import summarize_timings as script
    raw = tmp_path / 'private.csv'
    outputs = tmp_path / 'public'
    monkeypatch.setattr(script, 'RESULTS', outputs)
    monkeypatch.setattr(sys, 'argv', ['summarize_timings.py', '--input', str(raw)])
    append_timing(timing(practice=True), raw)
    with pytest.raises(SystemExit, match='No measured attempts'):
        script.main()
    assert not outputs.exists()
    raw.unlink()
    start = replace(timing(), attempt_id='UNFINISHED-TEST', seconds=0, duration_known=False,
                    field_errors=None, decision='', status='in_progress')
    append_timing(start, raw)
    with pytest.raises(SystemExit, match='Unresolved'):
        script.main()
    assert not outputs.exists()
    raw.unlink()
    for row in planned_rows():
        append_timing(row, raw)
    script.main()
    summary = json.loads((outputs / 'timing_summary.json').read_text())
    assert summary['comparison']['percentage_time_reduction'] == 60
    assert 'tester' not in (outputs / 'timing_summary.json').read_text()


def test_mixed_corpus_refuses_comparison():
    from dataclasses import replace
    rows = planned_rows()
    rows[0] = replace(rows[0], corpus_id='OTHER-TEST-CORPUS')
    assert not summarise(rows)['comparison']['available']
