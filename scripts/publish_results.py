"""Reduce a raw Gemini report to a metrics-only summary that is safe to commit.

Raw reports under reports/ hold extracted text and field values, so they stay
ignored. The summary keeps only counts and rates, which is what the README cites.
"""
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import statistics
from collections import Counter

from ar_copilot.config import ROOT
from ar_copilot.core import FIELDS
from ar_copilot.resilient import load_expected, metrics

RESULTS = ROOT / 'results'
# Output name and table title per evaluation sample.
OUTPUTS = {'full': ('gemini_summary', 'Gemini extraction results'),
           'per-layout': ('gemini_smoke_summary', 'Gemini smoke test: one document per layout')}
FIELD_COUNT = len(FIELDS)


def public_summary(report: dict, expected: dict[str, set[str]]) -> dict:
    """Return run metadata and metrics, never per-document content."""
    details = report['details']
    # Only anomalies inside this run count; a three-document smoke test never saw the others.
    in_run = {r['filename'] for r in details}
    result = metrics(details, {name: rules for name, rules in expected.items() if name in in_run})
    failures = result.pop('api_failures')
    completed = [r for r in details if not r['error']]
    completed_seconds = [r['seconds'] for r in completed]
    return {
        'source_run': report['run_id'],
        'sample': report.get('sample', 'full'),
        'models': sorted({r['model'] for r in details if r.get('model')}),
        'documents': result['documents'],
        'completion': {
            'completed': result['completed_documents'],
            'failed': result['failed_documents'],
            'pending': result['pending_documents'],
            'rate': result['completion_rate'],
            'failures_by_http_status': dict(sorted(Counter(str(f['code']) for f in failures).items())),
        },
        'counts': {
            'correct_fields': sum(sum(bool(v) for v in r['matches'].values()) for r in completed),
            'exact_documents': sum(all(r['matches'].values()) for r in completed),
        },
        # Completed-only accuracy says how good extraction is when the API answers;
        # overall accuracy counts every failed call as wrong on all fields.
        'accuracy_on_completed': {
            'field': result['completed_field_accuracy'],
            'document': result['completed_document_accuracy'],
            'per_field': result['field_accuracy_completed'],
        },
        'accuracy_overall': {
            'field': result['overall_field_accuracy'],
            'document': result['overall_document_accuracy'],
            'per_field': result['field_accuracy_overall'],
        },
        'accounting_anomalies': result['accounting_anomalies'],
        'latency_seconds_completed': {
            'n': len(completed_seconds),
            'median': statistics.median(completed_seconds) if completed_seconds else None,
            'min': min(completed_seconds, default=None),
            'max': max(completed_seconds, default=None),
        },
        'review_database_unchanged': report.get('review_database_unchanged'),
    }


def _ratio(numerator: int, denominator: int) -> str:
    if not denominator:
        return 'n/a'
    return f'{numerator}/{denominator} ({numerator / denominator:.1%})'


def render_markdown(summary: dict) -> str:
    """Render the headline table the README links to."""
    documents = summary['documents']
    completed = summary['completion']['completed']
    counts = summary['counts']
    failures = ', '.join(f'{n} × HTTP {code}' for code, n in summary['completion']['failures_by_http_status'].items())
    anomalies = summary['accounting_anomalies']
    latency = summary['latency_seconds_completed']
    latency_text = 'n/a'
    if latency['n']:
        latency_text = f"{latency['median']:.2f} (range {latency['min']:.2f}–{latency['max']:.2f}, n={latency['n']})"
    anomaly_text = 'none in this sample'
    if anomalies['expected']:
        anomaly_text = (f"{anomalies['rules_detected']}/{anomalies['expected']}"
                        f" ({anomalies['unassessed']} unassessed: extraction failed)")
    rows = [
        ('Documents attempted', str(documents)),
        ('Completion rate (API returned a result)', _ratio(completed, documents)),
        ('API failures', failures or 'none'),
        ('Field accuracy on completed documents', _ratio(counts['correct_fields'], completed * FIELD_COUNT)),
        ('Document accuracy on completed documents', _ratio(counts['exact_documents'], completed)),
        ('Field accuracy overall (failures count as wrong)', _ratio(counts['correct_fields'], documents * FIELD_COUNT)),
        ('Document accuracy overall', _ratio(counts['exact_documents'], documents)),
        ('Intentional anomalies caught by rules', anomaly_text),
        ('Rule false positives on completed documents', str(anomalies['false_positives'])),
        ('Median extraction latency, completed (s)', latency_text),
    ]
    lines = [
        f"# {OUTPUTS[summary['sample']][1]}",
        '',
        f"Run `{summary['source_run']}`, model {', '.join(summary['models'])}, "
        f"{documents} fictional documents, exact string match on {FIELD_COUNT} fields.",
        'Generated by `scripts/publish_results.py`; do not edit by hand.',
        '',
        '| Metric | Value |',
        '| --- | --- |',
        *(f'| {name} | {value} |' for name, value in rows),
        '',
    ]
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('report', type=Path, help='raw full, resilient or per-layout report under reports/gemini/')
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    if report.get('mode') != 'gemini' or report.get('sample') not in OUTPUTS:
        raise SystemExit('Only Gemini runs are published; demo fixture checks are not accuracy.')
    summary = public_summary(report, load_expected(ROOT / 'data'))
    RESULTS.mkdir(exist_ok=True)
    name = OUTPUTS[summary['sample']][0]
    (RESULTS / f'{name}.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (RESULTS / f'{name}.md').write_text(render_markdown(summary), encoding='utf-8')
    print(f'Wrote results/{name}.json and results/{name}.md')


if __name__ == '__main__':
    main()
