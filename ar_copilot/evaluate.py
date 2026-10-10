"""Evaluate raw extraction BEFORE any human correction; demo is never Gemini accuracy."""
import argparse
import csv
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from .extract import extract
from .core import FIELDS, validate
from .config import ROOT, configuration_status

def evaluate(folder=ROOT/'data', mode='demo', sample='full'):
    folder = Path(folder)
    truth = list(csv.DictReader((folder/'ground_truth.csv').open(encoding='utf-8')))
    if sample == 'per-layout':
        truth = [next(row for row in truth if row['layout'] == str(layout)) for layout in (1,2,3)]
    elif sample != 'full':
        raise ValueError('Unknown evaluation sample')
    expected = {a['filename']: set(a['expected_errors']) for a in json.loads((folder/'anomalies.json').read_text())}
    correct = dict.fromkeys(FIELDS, 0)
    details, exact, tp, fn, fp, tn = [], 0, 0, 0, 0, 0
    for row in truth:
        result = extract((folder/'invoices'/row['filename']).read_bytes(), mode, folder/'demo_fixtures.json')
        matches = {f: not result['error'] and (result['fields'].get(f) or '') == row[f] for f in FIELDS}
        for f in FIELDS:
            correct[f] += int(matches[f])
        exact += int(all(matches.values()) and not result['error'])
        failures = validate(result['fields'])
        flagged = bool(failures or result['error'])
        anomaly = row['filename'] in expected
        tp += int(anomaly and flagged); fn += int(anomaly and not flagged)
        fp += int(not anomaly and flagged); tn += int(not anomaly and not flagged)
        details.append(dict(filename=row['filename'], layout=row['layout'],
            ground_truth={f: row[f] for f in FIELDS}, matches=matches,
            mismatches={f: {'expected': row[f], 'actual': result['fields'].get(f)} for f in FIELDS if not matches[f]}, validation=failures,
            missed_rules=sorted(expected.get(row['filename'], set())-set(failures)), **result))
    n = len(truth)
    successes = sum(not r['error'] for r in details)
    return dict(mode=mode, sample=sample, measured_gemini_accuracy=mode == 'gemini' and successes > 0,
                label='OFFLINE FIXTURE CHECK - NOT GEMINI ACCURACY' if mode=='demo' else 'Gemini raw extraction evaluation',
                documents=n, successful_extractions=successes, extraction_errors=n-successes,
                fields=FIELDS, field_accuracy={f: correct[f]/n for f in FIELDS},
                overall_field_accuracy=sum(correct.values())/(n*len(FIELDS)),
                document_accuracy=exact/n, validation=dict(detected=tp, missed=fn, false_positives=fp, true_negatives=tn),
                seconds_total=sum(r['seconds'] for r in details),
                seconds_mean=sum(r['seconds'] for r in details)/n,
                full_evaluation_ready=mode=='gemini' and sample=='per-layout' and exact==n
                    and not any(r['validation'] for r in details), details=details)

def database_fingerprint():
    """Read-only preservation check; never open or write the review database."""
    path = ROOT/'runtime/ar.sqlite'
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['demo', 'gemini'], default='demo')
    parser.add_argument('--sample', choices=['full', 'per-layout'], default='full')
    parser.add_argument('--check-config', action='store_true')
    parser.add_argument('--list-models', action='store_true')
    parser.add_argument('--model', help='Override the model for this isolated run without changing .env')
    parser.add_argument('--resume', type=Path, help='Resume only failed/pending documents from a full Gemini report')
    parser.add_argument('--resilient', action='store_true')
    parser.add_argument('--limit', type=int, help='Maximum failed/pending documents to attempt this run')
    parser.add_argument('--pace', type=float, default=12)
    parser.add_argument('--max-attempts', type=int, default=4)
    parser.add_argument('--base-delay', type=float, default=2)
    parser.add_argument('--max-delay', type=float, default=30)
    parser.add_argument('--max-wait', type=float, default=120)
    args = parser.parse_args()
    if args.check_config:
        print(json.dumps(configuration_status(), indent=2))
        raise SystemExit(0)
    if args.model:
        import os
        os.environ['GEMINI_MODEL'] = args.model
    if args.list_models:
        from google import genai
        from .config import gemini_settings
        key, _ = gemini_settings()
        if not key:
            print('Gemini key is not configured.')
            raise SystemExit(2)
        try:
            with genai.Client(api_key=key, http_options={'timeout': 60000}) as client:
                for model in client.models.list():
                    if 'generateContent' in (model.supported_actions or []):
                        print(model.name)
        except Exception as exc:
            print(f'Model discovery failed: {type(exc).__name__}; HTTP code: {getattr(exc, "code", None)}')
            raise SystemExit(2)
        raise SystemExit(0)
    if args.mode == 'gemini' and not configuration_status()['key_configured']:
        print('Gemini key not configured. Save it locally in .env; no API calls or measured results produced.')
        raise SystemExit(2)
    if args.resilient or args.resume:
        if args.mode!='gemini' or args.sample!='full':
            parser.error('Resilient/resume runs require --mode gemini --sample full')
        from .resilient import run_evaluation
        from .retry import RetryPolicy
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination=ROOT/'reports/gemini'/f'resilient_{stamp}.json'
        policy=RetryPolicy(args.max_attempts,args.base_delay,args.max_delay,args.max_wait,args.pace)
        report=run_evaluation(destination,resume=args.resume,policy=policy,limit=args.limit)
        print(json.dumps({k:v for k,v in report.items() if k not in ('details','active_attempts')},indent=2))
        print(f'Checkpoint: {destination}')
        raise SystemExit(0)
    before = database_fingerprint()
    report = evaluate(mode=args.mode, sample=args.sample)
    report['review_database_unchanged'] = database_fingerprint() == before
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report['run_id'] = stamp
    report['started_or_completed_at_note'] = 'Run ID is completion time in UTC; per-document durations use perf_counter.'
    destination = ROOT/'reports'/args.mode
    destination.mkdir(parents=True, exist_ok=True)
    path = destination/f'{args.sample}_{stamp}.json'
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'details'}, indent=2))
    print(f'Report: {path}')
    if report['full_evaluation_ready']:
        tested_model = report['details'][0]['model']
        print(f'Three-layout smoke test passed. Full run prepared: .venv/Scripts/python -m ar_copilot.evaluate --mode gemini --sample full --model {tested_model}')
