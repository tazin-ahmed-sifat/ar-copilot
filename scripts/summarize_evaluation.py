"""Summarize an existing measured report; never calls Gemini or writes SQLite."""
import sys
from pathlib import Path

if not __package__:
    # Run as `python scripts/<name>.py`: put the repo root on the path so
    # `ar_copilot` imports the same way it does under `python -m scripts.<name>`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from ar_copilot.core import FIELDS

def summarize(report, anomalies):
    expected = {a['filename']: set(a['expected_errors']) for a in anomalies}
    details = report['details']
    n = len(details)
    field_counts = {f: sum(bool(r['matches'][f]) for r in details) for f in FIELDS}
    anomaly_rows = [r for r in details if r['filename'] in expected]
    clean_rows = [r for r in details if r['filename'] not in expected]
    credit_rows = [r for r in details if r['ground_truth']['document_type']=='credit_note']
    return dict(
        source_run=report['run_id'], model=sorted({r['model'] for r in details}),
        documents=n, field_comparisons=n*len(FIELDS),
        correct_fields=sum(field_counts.values()), field_correct_counts=field_counts,
        overall_field_accuracy=sum(field_counts.values())/(n*len(FIELDS)),
        exact_documents=sum(all(r['matches'].values()) and not r['error'] for r in details),
        document_accuracy=sum(all(r['matches'].values()) and not r['error'] for r in details)/n,
        extraction_failures=[dict(filename=r['filename'],error=r['error'],error_code=r.get('error_code'),seconds=r['seconds']) for r in details if r['error']],
        intentional_anomalies=[dict(filename=r['filename'], expected_rules=sorted(expected[r['filename']]),
            observed_rules=r['validation'], extraction_error=r['error'],
            expected_rules_detected=not r['error'] and expected[r['filename']].issubset(r['validation']),
            routed_to_review=bool(r['error'] or r['validation'])) for r in anomaly_rows],
        anomalies_with_expected_rule_detected=sum(not r['error'] and expected[r['filename']].issubset(r['validation']) for r in anomaly_rows),
        anomalies_unassessed_due_to_extraction_failure=sum(bool(r['error']) for r in anomaly_rows),
        anomalies_missed_by_rules_after_successful_extraction=sum(not r['error'] and not expected[r['filename']].issubset(r['validation']) for r in anomaly_rows),
        anomalies_not_routed_to_review=sum(not(r['error'] or r['validation']) for r in anomaly_rows),
        false_positive_review_documents=[r['filename'] for r in clean_rows if r['error'] or r['validation']],
        validation_false_positive_documents=[r['filename'] for r in clean_rows if not r['error'] and r['validation']],
        credit_notes=[dict(filename=r['filename'],fields=r['fields'],ground_truth=r['ground_truth'],
            all_fields_match=all(r['matches'].values()),validation=r['validation'],error=r['error'],seconds=r['seconds']) for r in credit_rows],
        per_layout={layout: dict(documents=sum(r['layout']==layout for r in details),
            exact_documents=sum(r['layout']==layout and all(r['matches'].values()) and not r['error'] for r in details))
            for layout in sorted({r['layout'] for r in details})},
        seconds_total=sum(r['seconds'] for r in details),seconds_mean=sum(r['seconds'] for r in details)/n,
        review_database_unchanged=report['review_database_unchanged'],
        mismatches=[dict(filename=r['filename'],fields=r['mismatches']) for r in details if r['mismatches']],
        manual_entry_measured=False, time_saved_claim=None)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=json.loads(args.report.read_text())
    if report['mode']!='gemini':
        raise SystemExit('This summary is for Gemini reports only; demo stays separate.')
    result=summarize(report,json.loads((root/'data/anomalies.json').read_text()))
    destination=args.report.with_name(args.report.stem+'_summary.json')
    destination.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in
        ('mismatches','extraction_failures','credit_notes','false_positive_review_documents')},indent=2))
    print(f'Detailed summary: {destination}')
