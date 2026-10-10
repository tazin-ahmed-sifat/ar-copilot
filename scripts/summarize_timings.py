"""Summarise results/timings.csv into results/timing_summary.json and .md.

Writes nothing when no timed documents exist, so no time-saved figure can appear
without raw observations behind it.
"""
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

from ar_copilot.config import ROOT
from ar_copilot.timing import load_timings, summarise

RESULTS = ROOT / 'results'


def _seconds(value: float | None) -> str:
    return 'n/a' if value is None else f'{value:.1f}'


def render_markdown(summary: dict) -> str:
    lines = [
        '# Time per document',
        '',
        'Generated from `results/timings.csv` by `scripts/summarize_timings.py`; do not edit by hand.',
        f"Practice rows excluded: {summary['practice_rows_excluded']}.",
        '',
        '| Method | Docs | Operators | Median s | IQR s | Range s | Field errors | Docs with errors |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for key, group in summary['groups'].items():
        s = group['seconds']
        lines.append(
            f"| {key} | {group['documents']} | {group['operators']} | {_seconds(s['median'])} "
            f"| {_seconds(s['q1'])}–{_seconds(s['q3'])} | {_seconds(s['min'])}–{_seconds(s['max'])} "
            f"| {group['field_errors_total']} ({group['field_error_rate']:.1%}) | {group['documents_with_errors']} |"
        )
    lines += ['', _comparison(summary['groups']), '']
    return '\n'.join(lines)


def _comparison(groups: dict) -> str:
    manual = groups.get('manual/none')
    assisted = groups.get('assisted/gemini')
    if not manual or not assisted:
        return ('No time-saved comparison: it needs both manual/none and assisted/gemini rows. '
                'Assisted runs in demo mode use fixture answers and are not comparable.')
    difference = manual['seconds']['median'] - assisted['seconds']['median']
    return (f"Median difference, manual minus assisted (Gemini): {difference:.1f} s per document "
            f"({manual['documents']} manual vs {assisted['documents']} assisted documents).")


def main() -> None:
    summary = summarise(load_timings())
    if not summary['groups']:
        raise SystemExit('No timed documents in results/timings.csv yet; nothing written.')
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / 'timing_summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (RESULTS / 'timing_summary.md').write_text(render_markdown(summary), encoding='utf-8')
    print('Wrote results/timing_summary.json and results/timing_summary.md')


if __name__ == '__main__':
    main()
