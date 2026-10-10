"""Sequential evaluation with atomic checkpoints and failed-document resume."""
import csv
import hashlib
import io
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader
from .config import ROOT
from .core import FIELDS, validate
from .extract import extract
from .retry import RetryPolicy, run_with_retry

def atomic_save(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
    temporary.replace(path)

def compare(row, result):
    matches = {f: not result['error'] and (result['fields'].get(f) or '')==row[f] for f in FIELDS}
    # No accounting validation of empty/failed API outputs.
    rules = validate(result['fields']) if not result['error'] else []
    return dict(filename=row['filename'], layout=row['layout'], ground_truth={f:row[f] for f in FIELDS},
        matches=matches, mismatches={f:dict(expected=row[f],actual=result['fields'].get(f)) for f in FIELDS if not matches[f]},
        validation=rules, **result)

def metrics(details, expected):
    completed = [r for r in details if not r['error']]
    n, count = len(details), len(completed)
    correct = {f:sum(bool(r['matches'][f]) for r in completed) for f in FIELDS}
    exact = sum(all(r['matches'].values()) for r in completed)
    anomaly_rows = [r for r in completed if r['filename'] in expected]
    api_failed = [r for r in details if r['error'] and r.get('error_kind')!='pending']
    return dict(documents=n, completed_documents=count, completion_rate=count/n,
        failed_documents=len(api_failed), pending_documents=sum(r.get('error_kind')=='pending' for r in details),
        field_accuracy_completed={f:correct[f]/count if count else None for f in FIELDS},
        field_accuracy_overall={f:correct[f]/n for f in FIELDS},
        overall_field_accuracy=sum(correct.values())/(n*len(FIELDS)),
        completed_field_accuracy=sum(correct.values())/(count*len(FIELDS)) if count else None,
        overall_document_accuracy=exact/n, completed_document_accuracy=exact/count if count else None,
        api_failures=[dict(filename=r['filename'],code=r.get('error_code'),kind=r.get('error_kind','legacy_unclassified')) for r in api_failed],
        accounting_anomalies=dict(expected=len(expected),
            rules_detected=sum(expected[r['filename']].issubset(r['validation']) for r in anomaly_rows),
            rules_missed_after_completed_extraction=sum(not expected[r['filename']].issubset(r['validation']) for r in anomaly_rows),
            unassessed=sum(r['filename'] in expected and bool(r['error']) for r in details),
            false_positives=sum(r['filename'] not in expected and bool(r['validation']) for r in completed)))

def run_evaluation(output, folder=ROOT/'data', resume=None, policy=None, limit=None,
                   call=extract, sleep=time.sleep, monotonic=time.perf_counter, uniform=None,
                   announce=print, database=None):
    policy = policy or RetryPolicy()
    folder, output = Path(folder), Path(output)
    if limit is not None and limit<1:
        raise ValueError('limit must be positive')
    if resume and Path(resume).resolve()==output.resolve():
        raise ValueError('Resume source is immutable: choose a new checkpoint path')
    if output.exists():
        raise ValueError('Checkpoint already exists: resume it into a new path')
    rows=list(csv.DictReader((folder/'ground_truth.csv').open(encoding='utf-8')))
    expected={a['filename']:set(a['expected_errors']) for a in json.loads((folder/'anomalies.json').read_text())}
    source=json.loads(Path(resume).read_text()) if resume else None
    if source and (source['mode']!='gemini' or len(source['details'])!=len(rows)):
        raise ValueError('Resume requires a full Gemini report for this corpus')
    old={r['filename']:r for r in source['details']} if source else {}
    if source and set(old)!={r['filename'] for r in rows}:
        raise ValueError('Resume source document set differs from dataset')
    payloads={r['filename']:(folder/'invoices'/r['filename']).read_bytes() for r in rows}
    details=[]
    for row in rows:
        raw=payloads[row['filename']]
        digest=hashlib.sha256(raw).hexdigest()
        prior=old.get(row['filename'])
        if prior:
            if prior['ground_truth']!={f:row[f] for f in FIELDS}:
                raise ValueError('Ground truth changed; do not reuse this report')
            if prior.get('source_hash') and prior['source_hash']!=digest:
                raise ValueError('PDF changed; do not reuse this report')
            if not prior.get('source_hash'):
                text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
                if text!=prior.get('text'):
                    raise ValueError('Legacy PDF text changed; cannot safely resume')
            prior=dict(prior,source_hash=digest)
            if prior['error']:
                prior['validation']=[]  # Historical API failure is not an accounting anomaly.
            details.append(prior)
        else:
            details.append(dict(compare(row,dict(fields={},text='',error='Not attempted',error_kind='pending',
                error_code=None,model=None,mode='gemini',seconds=0)),source_hash=digest))
    database=Path(database) if database else ROOT/'runtime/ar.sqlite'
    fingerprint=lambda: hashlib.sha256(database.read_bytes()).hexdigest() if database.exists() else None
    before=fingerprint()
    started=monotonic()
    report=dict(mode='gemini',sample='full',run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'),
        resume_source=str(resume) if resume else None, policy=asdict(policy),details=details,
        state='running', stop_reason=None, attempted_this_run=0, successful_calls_reused=sum(not r['error'] for r in details),
        new_request_seconds=0.0,new_retry_wait_seconds=0.0,new_pacing_wait_seconds=0.0,
        prior_observed_seconds=source.get('cumulative_observed_seconds',source.get('seconds_total',0)) if source else 0)
    def save():
        report['metrics']=metrics(details,expected)
        report['invocation_seconds']=monotonic()-started
        report['cumulative_observed_seconds']=report['prior_observed_seconds']+report['new_request_seconds']+report['new_retry_wait_seconds']+report['new_pacing_wait_seconds']
        report['review_database_unchanged']=fingerprint()==before
        atomic_save(output,report)
    save()
    last_start=None
    def paced_call(raw):
        nonlocal last_start
        now=monotonic()
        delay=max(0,policy.pace-(now-last_start)) if last_start is not None else 0
        if delay:
            announce(f'Pacing: waiting {delay:.1f}s before request',flush=True)
            sleep(delay)
            report['new_pacing_wait_seconds']+=delay
        last_start=monotonic()
        return call(raw,'gemini',folder/'demo_fixtures.json',single_attempt=True)
    try:
        for i,row in enumerate(rows):
            if not details[i]['error']:
                continue
            if limit and report['attempted_this_run']>=limit:
                report['stop_reason']='document_limit_reached'
                break
            announce(f'Evaluating {row["filename"]}; prior successes will not be repeated',flush=True)
            report['active_document']=row['filename']
            report['active_attempts']=[]
            save()
            def progress(attempt):
                attempts=report['active_attempts']
                if attempts and attempts[-1]['number']==attempt['number']:
                    attempts[-1]=dict(attempt)
                else:
                    attempts.append(dict(attempt))
                save()
                if attempt['wait_after_seconds']:
                    announce(f'Retry wait: {attempt["wait_after_seconds"]:.1f}s',flush=True)
            kwargs=dict(sleep=sleep,on_attempt=progress)
            if uniform:
                kwargs['uniform']=uniform
            result=run_with_retry(lambda:paced_call(payloads[row['filename']]),policy,**kwargs)
            previous=details[i]
            new=compare(row,result)
            new['source_hash']=previous['source_hash']
            new['previous_results']=previous.get('previous_results',[])+[{k:v for k,v in previous.items() if k!='previous_results'}]
            details[i]=new
            report['attempted_this_run']+=1
            report['new_request_seconds']+=result['request_seconds']
            report['new_retry_wait_seconds']+=result['retry_wait_seconds']
            report['active_document']=None
            report['active_attempts']=[]
            save()
            announce(f'{row["filename"]}: {"completed" if not result["error"] else result.get("error_kind","failed")}',flush=True)
            if result.get('stop_reason'):
                report['stop_reason']=result['stop_reason']
                break
        report['state']='finished' if all(not r['error'] for r in details) else 'stopped_with_failures_or_pending'
    except (KeyboardInterrupt,Exception):
        report['state']='interrupted'
        save()
        raise
    save()
    return report
