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
from ar_copilot.resilient import metrics

DESTINATION = ROOT / 'results' / 'gemini_summary.json'


def load_expected_anomalies() -> dict[str, set[str]]:
    anomalies = json.loads((ROOT / 'data' / 'anomalies.json').read_text())
    return {a['filename']: set(a['expected_errors']) for a in anomalies}


def public_summary(report: dict, expected: dict[str, set[str]]) -> dict:
    """Return run metadata and metrics, never per-document content."""
    details = report['details']
    result = metrics(details, expected)
    failures = result.pop('api_failures')
    completed_seconds = [r['seconds'] for r in details if not r['error']]
    return {
        'source_run': report['run_id'],
        'models': sorted({r['model'] for r in details if r.get('model')}),
        'documents': result['documents'],
        'completion': {
            'completed': result['completed_documents'],
            'failed': result['failed_documents'],
            'pending': result['pending_documents'],
            'rate': result['completion_rate'],
            'failures_by_http_status': dict(sorted(Counter(str(f['code']) for f in failures).items())),
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('report', type=Path, help='raw full or resilient report under reports/gemini/')
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    if report.get('mode') != 'gemini' or report.get('sample') != 'full':
        raise SystemExit('Only full Gemini runs are published; demo fixture checks are not accuracy.')
    summary = public_summary(report, load_expected_anomalies())
    DESTINATION.parent.mkdir(exist_ok=True)
    DESTINATION.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {DESTINATION.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
