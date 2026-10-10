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

def test_markdown_table_shows_counts_for_each_denominator():
    from scripts.publish_results import public_summary, render_markdown
    def row(filename, error):
        return dict(filename=filename, model='mock', error=error, error_code=503 if error else None,
                    seconds=1.0, validation=[], matches={f: not error for f in FIELDS})
    summary = public_summary(dict(run_id='mock', details=[row('a.pdf', None), row('b.pdf', 'mock API error')]), {})
    table = render_markdown(summary)
    assert '| Completion rate (API returned a result) | 1/2 (50.0%) |' in table
    assert '| Field accuracy on completed documents | 12/12 (100.0%) |' in table
    assert '| Field accuracy overall (failures count as wrong) | 12/24 (50.0%) |' in table
    assert '1 × HTTP 503' in table

def test_smoke_summary_only_counts_anomalies_in_the_run():
    from scripts.publish_results import public_summary, render_markdown
    details = [dict(filename='a.pdf', model='mock', error=None, error_code=None, seconds=1.0,
                    validation=[], matches={f: True for f in FIELDS})]
    summary = public_summary(dict(run_id='mock', sample='per-layout', details=details),
                             {'elsewhere.pdf': {'totals'}})
    assert summary['accounting_anomalies']['expected'] == 0
    assert render_markdown(summary).startswith('# Ollama smoke test')


def test_public_summary_separates_failed_credit_from_extraction_mistake():
    from scripts.publish_results import public_summary, render_markdown
    def row(name, error, credit=False):
        return dict(filename=name, model='mock', error=error, error_code=429 if error else None,
                    error_kind='runtime_unavailable' if error else None, seconds=1,
                    validation=[], matches={f: False for f in FIELDS},
                    ground_truth={'document_type': 'credit_note' if credit else 'invoice'})
    report = dict(run_id='mock', sample='full', details=[row('credit.pdf', 'failed', True),
                  row('invoice.pdf', None)], new_request_seconds=0.5,
                  stop_reason='runtime_unavailable')
    summary = public_summary(report, {})
    assert summary['credit_notes'] == dict(documents=1, completed=0, exact_documents=0, unassessed=1)
    assert summary['extraction_mistakes'] == dict(completed_documents_with_mismatches=1,
                                                 incorrect_fields_on_completed=12)
    assert summary['completion']['failures_by_kind'] == {'runtime_unavailable': 1}
    assert summary['processing_seconds']['new_request_seconds'] == 0.5
    assert 'runtime_unavailable' in render_markdown(summary)
