"""API failures must never masquerade as accounting-anomaly detections."""
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
