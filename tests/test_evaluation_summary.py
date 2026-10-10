"""API failures must never masquerade as accounting-anomaly detections."""
import json
from ar_copilot.core import FIELDS
from scripts.summarize_evaluation import summarize

def test_failed_anomaly_is_unassessed_not_detected():
    def row(filename, error, validation):
        return dict(filename=filename,model='mock',layout='1',ground_truth={'document_type':'invoice'},
            fields={},matches={f:not error for f in FIELDS},error=error,error_code=429 if error else None,
            seconds=.5,validation=validation,mismatches={})
    details=[row('anomaly.pdf','mock API error',['missing:po_number']),
             row('clean.pdf','mock API error',[]),row('success.pdf',None,[])]
    result=summarize(dict(run_id='mock',details=details,review_database_unchanged=True),
                     [dict(filename='anomaly.pdf',expected_errors=['missing:po_number'])])
    assert result['anomalies_with_expected_rule_detected']==0
    assert result['anomalies_unassessed_due_to_extraction_failure']==1
    assert result['anomalies_not_routed_to_review']==0
    assert result['anomalies_missed_by_rules_after_successful_extraction']==0
    assert result['false_positive_review_documents']==['clean.pdf']
    assert result['validation_false_positive_documents']==[]
    assert result['correct_fields']==12 and result['field_comparisons']==36
    assert result['exact_documents']==1 and result['documents']==3

def test_public_summary_keeps_metrics_apart_and_drops_document_content():
    from scripts.publish_results import public_summary
    def row(filename, error, seconds):
        return dict(filename=filename, model='mock', error=error, error_code=429 if error else None,
                    seconds=seconds, validation=[], matches={f: not error for f in FIELDS},
                    fields={'customer': 'SECRET-EXTRACTED'}, text='SECRET-TEXT',
                    ground_truth={'customer': 'SECRET-TRUTH'})
    details = [row('a.pdf', None, 2.0), row('b.pdf', None, 4.0), row('c.pdf', 'mock API error', 0.1),
               row('d.pdf', 'mock API error', 0.1)]
    summary = public_summary(dict(run_id='mock', details=details), {})
    assert summary['completion']['rate'] == 0.5
    assert summary['completion']['failures_by_http_status'] == {'429': 2}
    assert summary['accuracy_on_completed']['field'] == 1.0
    assert summary['accuracy_overall']['field'] == 0.5
    assert summary['latency_seconds_completed'] == dict(n=2, median=3.0, min=2.0, max=4.0)
    assert 'SECRET' not in json.dumps(summary)
