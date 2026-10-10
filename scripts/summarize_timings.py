"""Validate private timing events and publish aggregate summaries only; no observations, no output."""
import sys
from pathlib import Path
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import json
from ar_copilot.config import ROOT
from ar_copilot.timing import load_timings, summarise
RESULTS = ROOT / 'results'


def _seconds(value):
    return 'n/a' if value is None else f'{value:.1f}'


def render_markdown(summary):
    lines = ['# Time per document', '',
             'Generated from private local observations by `scripts/summarize_timings.py`; do not edit by hand.',
             f"Practice attempts excluded: {summary['practice_rows_excluded']}.",
             'Completed durations include extraction wait, review, correction and final submission. '
             'Incomplete/unresolved attempts are retained but excluded from completed-time medians.', '',
             '| Method | Attempts | Completed | Incomplete | Unresolved | Operators | Median s | Q1-Q3 s | Range s | Field errors | Decision errors | API failures |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for key, group in summary['groups'].items():
        s = group['seconds']
        rate = 'n/a' if group['field_error_rate'] is None else f"{group['field_error_rate']:.1%}"
        lines.append(f"| {key} | {group['documents']} | {group['completed']} | {group['incomplete']} | {group['unresolved']} "
                     f"| {group['operators']} | {_seconds(s['median'])} | {_seconds(s['q1'])} to {_seconds(s['q3'])} "
                     f"| {_seconds(s['min'])} to {_seconds(s['max'])} | {group['field_errors_total']} ({rate} of completed fields) "
                     f"| {group['decision_errors']} ({group['decisions_unscored']} unscored) | {group['api_failures']} |")
        if group['incomplete'] or group['unresolved']:
            incomplete = group['incomplete_seconds']
            lines.append('')
            lines.append(f"{key}: incomplete-duration median {_seconds(incomplete['median'])} s, "
                         f"range {_seconds(incomplete['min'])} to {_seconds(incomplete['max'])} s; "
                         f"{group['unknown_durations']} attempt duration(s) unknown. Unscored does not mean error-free.")
            lines.append('')
    lines += ['', '| Method | Median extraction wait, completed (s) | Final fields corrected | API-failure completions with unassessed corrections | Unknown extraction outcomes |',
              '| --- | --- | --- | --- | --- |']
    for key, group in summary['groups'].items():
        lines.append(f"| {key} | {_seconds(group['extraction_seconds_median'])} | {group['fields_corrected_total']} "
                     f"| {group['corrections_unassessed_api_failures']} | {group['unknown_extraction_outcomes']} |")
    lines += ['', _comparison(summary), '',
              'Demo fixtures and legacy measurements are descriptive only and excluded from the live comparison. '
              'Errors are reported alongside speed; API failures are distinct from final field/decision errors.', '']
    return '\n'.join(lines)


def _comparison(summary):
    result = summary['comparison']
    if not result['available']:
        return 'No time-saved comparison: ' + result['reason']
    manual, assisted = result['manual_seconds'], result['assisted_seconds']
    return (f"Matched completed pairs: {result['completed_pairs']} across {result['participants']} participant(s); "
            f"{result['incomplete_pairs_excluded']} incomplete pairs excluded from this time comparison. "
            f"Manual median {_seconds(manual['median'])} s, Ollama-assisted median {_seconds(assisted['median'])} s. "
            f"Matched manual Q1-Q3 {_seconds(manual['q1'])} to {_seconds(manual['q3'])} s, "
            f"range {_seconds(manual['min'])} to {_seconds(manual['max'])} s; "
            f"matched assisted Q1-Q3 {_seconds(assisted['q1'])} to {_seconds(assisted['q3'])} s, "
            f"range {_seconds(assisted['min'])} to {_seconds(assisted['max'])} s. "
            f"Median difference, manual minus assisted (Ollama): {result['median_difference_seconds']:.1f} s. "
            f"Percentage time reduction: {result['percentage_time_reduction']:.1f}%. "
            f"Definition: {result['definition']} {result['limitation']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='private raw CSV; default includes legacy local observations')
    args = parser.parse_args()
    summary = summarise(load_timings(args.input))
    if not summary['groups']:
        raise SystemExit('No measured attempts yet; nothing written.')
    if any(group['unresolved'] for group in summary['groups'].values()):
        raise SystemExit('Unresolved attempts remain; record interruptions in the app before publishing.')
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / 'timing_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (RESULTS / 'timing_summary.md').write_text(render_markdown(summary), encoding='utf-8')
    print('Wrote publication-safe results/timing_summary.json and .md')


if __name__ == '__main__':
    main()
