"""No network: deterministic retries, pacing and checkpoints."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from ar_copilot.retry import RetryPolicy, retry_after, error_metadata, run_with_retry
from ar_copilot.resilient import run_evaluation
from ar_copilot import evaluate as legacy
from ar_copilot.generate import generate
from ar_copilot.core import FIELDS

def result(code=None, kind=None, hint=None):
    return dict(fields={},text='',error='mock failure' if code else None,error_code=code,
                error_kind=kind,retry_after_seconds=hint,seconds=.1,model='qwen3:8b',mode='ollama')

def test_backoff_jitter_and_retry_after():
    responses=iter([result(429,'temporary_or_unknown_rate_limit',5),result(503,'temporary_server_error'),result()])
    waits=[]
    output=run_with_retry(lambda:next(responses),RetryPolicy(3,2,10,20,0),sleep=waits.append,uniform=lambda low,high:low)
    assert waits==[5,2]
    assert len(output['attempts'])==3 and not output['error']
    assert output['retry_wait_seconds']==7

def test_retry_after_http_date_and_invalid_values():
    now=datetime(2026,10,10,tzinfo=timezone.utc)
    assert retry_after('Sat, 10 Oct 2026 00:00:10 GMT',now)==10
    assert retry_after('NaN') is None and retry_after('bad') is None
    assert retry_after('-2')==0

def test_retry_budget_and_long_retry_after():
    calls=[]
    def call():
        calls.append(1); return result(429,'temporary_or_unknown_rate_limit')
    output=run_with_retry(call,RetryPolicy(2,1,2,10,0),sleep=lambda _:None)
    assert len(calls)==2 and output['stop_reason']=='rate_limit_retry_budget_exhausted'
    output=run_with_retry(lambda:result(503,'temporary_server_error',100),RetryPolicy(max_attempts=2,max_wait=20),sleep=lambda _:pytest.fail('must not truncate server delay'))
    assert len(output['attempts'])==1 and output['stop_reason']=='server_retry_after_exceeds_wait_budget'
    assert len(run_with_retry(lambda:result(400,'non_retryable_error'),RetryPolicy())['attempts'])==1

@pytest.fixture
def seed(tmp_path,monkeypatch):
    data=tmp_path/'data'; rows=generate(data)
    def fake(pdf,*args,**kwargs):
        i=next(i for i,r in enumerate(rows) if (data/'invoices'/r['filename']).read_bytes()==pdf)
        r=result() if i<4 else result(429,'temporary_or_unknown_rate_limit')
        r['text']='\n'.join(p.extract_text() or '' for p in __import__('pypdf').PdfReader(__import__('io').BytesIO(pdf)).pages)
        if i<4:
            r['fields']={f:rows[i][f] for f in FIELDS}
        return r
    monkeypatch.setattr(legacy,'extract',fake)
    report=legacy.evaluate(data,'ollama')
    report['run_id']='mock'
    from ar_copilot.ollama import OPTIONS
    report['model_settings']=dict(OPTIONS, think=False, timeout_seconds=120)
    source=tmp_path/'original.json'; source.write_text(json.dumps(report))
    database=tmp_path/'db.sqlite'; database.write_bytes(b'unchanged test database')
    return data,rows,source,database

def test_resume_only_failed_and_preserve_original(seed,tmp_path):
    data,rows,source,database=seed
    original=source.read_bytes(); calls=[]
    def call(pdf,*args,**kwargs):
        calls.append(pdf)
        assert kwargs['single_attempt']
        r=result(); r['fields']={f:rows[4][f] for f in FIELDS}
        return r
    output=tmp_path/'new.json'
    report=run_evaluation(output,data,source,RetryPolicy(pace=0),limit=1,call=call,database=database)
    assert len(calls)==1 and calls[0]==(data/'invoices/NC-0005.pdf').read_bytes()
    assert source.read_bytes()==original and database.read_bytes()==b'unchanged test database'
    assert report['metrics']['completion_rate']==.125
    assert report['metrics']['completed_document_accuracy']==1
    assert report['metrics']['overall_document_accuracy']==.125
    assert report['metrics']['accounting_anomalies']['rules_detected']==0
    assert report['metrics']['accounting_anomalies']['false_positives']==0
    assert report['review_database_unchanged'] and json.loads(output.read_text())['attempted_this_run']==1
    with pytest.raises(ValueError):
        run_evaluation(source,data,source)

def test_checkpoint_survives_interruption_and_pacing(seed,tmp_path):
    data,rows,source,database=seed
    calls=[]; clock=[0.0]; waits=[]
    def sleep(delay):
        waits.append(delay); clock[0]+=delay
    def call(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:
            raise KeyboardInterrupt()
        r=result(); r['fields']={f:rows[4][f] for f in FIELDS}; return r
    output=tmp_path/'interrupted.json'
    with pytest.raises(KeyboardInterrupt):
        run_evaluation(output,data,source,RetryPolicy(pace=5),call=call,sleep=sleep,
            monotonic=lambda:clock[0],database=database)
    saved=json.loads(output.read_text())
    assert saved['metrics']['completed_documents']==5 and saved['state']=='interrupted'
    assert waits==[5]
    assert saved['details'][4]['error'] is None

def test_changed_dataset_refuses_resume(seed,tmp_path):
    data,rows,source,database=seed
    report=json.loads(source.read_text()); report['details'][0]['ground_truth']['total']='1'
    source.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='Ground truth changed'):
        run_evaluation(tmp_path/'changed.json',data,source,call=lambda *a,**k:pytest.fail('no API call'))
