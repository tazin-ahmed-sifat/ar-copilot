"""Write a detailed local summary next to a raw Ollama report, including per-document mismatches.

The output stays under reports/ (ignored by Git) because it contains extracted values;
scripts/publish_results.py produces the metrics-only version that is committed.
Never calls Ollama and never opens the review database.
"""
import sys
from pathlib import Path

if not __package__:
    # Run as `python scripts/<name>.py`: put the repo root on the path so
    # `ar_copilot` imports the same way it does under `python -m scripts.<name>`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json

from ar_copilot.core import FIELDS

HEADLINE_EXCLUDES = ('mismatches', 'extraction_failures', 'credit_notes', 'false_positive_review_documents')


def summarize(report: dict, anomalies: list[dict]) -> dict:
    expected = {a['filename']: set(a['expected_errors']) for a in anomalies}
    details = report['details']
    n = len(details)
    field_counts = {f: sum(bool(r['matches'][f]) for r in details) for f in FIELDS}
    anomaly_rows = [r for r in details if r['filename'] in expected]
    clean_rows = [r for r in details if r['filename'] not in expected]
    credit_rows = [r for r in details if r['ground_truth']['document_type'] == 'credit_note']

    def exact(row):
        return all(row['matches'].values()) and not row['error']

    def rule_caught(row):
        # An API failure is "unassessed", never a detection, even though it routes to review.
        return not row['error'] and expected[row['filename']].issubset(row['validation'])

    def routed_to_review(row):
        return bool(row['error'] or row['validation'])

    seconds = [r['seconds'] for r in details]
    return dict(
        source_run=report['run_id'],
        model=sorted({r['model'] for r in details}),
        documents=n,
        field_comparisons=n * len(FIELDS),
        correct_fields=sum(field_counts.values()),
        field_correct_counts=field_counts,
        overall_field_accuracy=sum(field_counts.values()) / (n * len(FIELDS)),
        exact_documents=sum(exact(r) for r in details),
        document_accuracy=sum(exact(r) for r in details) / n,
        extraction_failures=[dict(filename=r['filename'], error=r['error'], error_code=r.get('error_code'),
                                  seconds=r['seconds']) for r in details if r['error']],
        intentional_anomalies=[dict(filename=r['filename'], expected_rules=sorted(expected[r['filename']]),
                                    observed_rules=r['validation'], extraction_error=r['error'],
                                    expected_rules_detected=rule_caught(r), routed_to_review=routed_to_review(r))
                               for r in anomaly_rows],
        anomalies_with_expected_rule_detected=sum(rule_caught(r) for r in anomaly_rows),
        anomalies_unassessed_due_to_extraction_failure=sum(bool(r['error']) for r in anomaly_rows),
        anomalies_missed_by_rules_after_successful_extraction=sum(
            not r['error'] and not rule_caught(r) for r in anomaly_rows),
        anomalies_not_routed_to_review=sum(not routed_to_review(r) for r in anomaly_rows),
        false_positive_review_documents=[r['filename'] for r in clean_rows if routed_to_review(r)],
        validation_false_positive_documents=[r['filename'] for r in clean_rows if not r['error'] and r['validation']],
        credit_notes=[dict(filename=r['filename'], fields=r['fields'], ground_truth=r['ground_truth'],
                           all_fields_match=all(r['matches'].values()), validation=r['validation'],
                           error=r['error'], seconds=r['seconds']) for r in credit_rows],
        per_layout={layout: dict(documents=sum(r['layout'] == layout for r in details),
                                 exact_documents=sum(r['layout'] == layout and exact(r) for r in details))
                    for layout in sorted({r['layout'] for r in details})},
        seconds_total=sum(seconds),
        seconds_mean=sum(seconds) / n,
        review_database_unchanged=report['review_database_unchanged'],
        mismatches=[dict(filename=r['filename'], fields=r['mismatches']) for r in details if r['mismatches']],
        manual_entry_measured=False,
        time_saved_claim=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = json.loads(args.report.read_text())
    if report['mode'] != 'ollama':
        raise SystemExit('This summary is for Ollama reports only; demo stays separate.')
    result = summarize(report, json.loads((root/'data/anomalies.json').read_text()))
    destination = args.report.with_name(args.report.stem + '_summary.json')
    destination.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in HEADLINE_EXCLUDES}, indent=2))
    print(f'Detailed summary: {destination}')


if __name__ == '__main__':
    main()
