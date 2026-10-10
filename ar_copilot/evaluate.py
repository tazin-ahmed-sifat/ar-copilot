"""Score raw extraction against printed ground truth, before any human correction.

Demo mode replays fixtures that were built from the truth, so its scores test the
plumbing only; they are labelled as such and never reported as Gemini accuracy.
"""
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT, configuration_status, gemini_settings
from .core import FIELDS, validate
from .extract import extract


def evaluate(folder=ROOT/'data', mode: str = 'demo', sample: str = 'full') -> dict:
    """Extract every sampled document once and score fields, documents and anomaly routing."""
    folder = Path(folder)
    truth = list(csv.DictReader((folder/'ground_truth.csv').open(encoding='utf-8')))
    if sample == 'per-layout':
        truth = [next(row for row in truth if row['layout'] == str(layout)) for layout in (1, 2, 3)]
    elif sample != 'full':
        raise ValueError('Unknown evaluation sample')
    expected = {a['filename']: set(a['expected_errors']) for a in json.loads((folder/'anomalies.json').read_text())}
    details = [_score(row, extract((folder/'invoices'/row['filename']).read_bytes(), mode, folder/'demo_fixtures.json'),
                      expected) for row in truth]
    return _report(details, mode, sample, expected)


def _score(row: dict, result: dict, expected: dict[str, set[str]]) -> dict:
    matches = {f: not result['error'] and (result['fields'].get(f) or '') == row[f] for f in FIELDS}
    failures = validate(result['fields'])
    mismatches = {f: {'expected': row[f], 'actual': result['fields'].get(f)} for f in FIELDS if not matches[f]}
    return dict(filename=row['filename'], layout=row['layout'], ground_truth={f: row[f] for f in FIELDS},
                matches=matches, mismatches=mismatches, validation=failures,
                missed_rules=sorted(expected.get(row['filename'], set()) - set(failures)), **result)


def _report(details: list[dict], mode: str, sample: str, expected: dict[str, set[str]]) -> dict:
    n = len(details)
    correct = {f: sum(bool(r['matches'][f]) for r in details) for f in FIELDS}
    exact = sum(all(r['matches'].values()) and not r['error'] for r in details)
    successes = sum(not r['error'] for r in details)
    # Routing to review counts as "detected" here, whether a rule fired or the API failed;
    # results/ keeps rule detections and API failures apart.
    flagged = {r['filename']: bool(r['validation'] or r['error']) for r in details}
    is_anomaly = {r['filename']: r['filename'] in expected for r in details}
    validation = dict(
        detected=sum(is_anomaly[f] and flagged[f] for f in flagged),
        missed=sum(is_anomaly[f] and not flagged[f] for f in flagged),
        false_positives=sum(not is_anomaly[f] and flagged[f] for f in flagged),
        true_negatives=sum(not is_anomaly[f] and not flagged[f] for f in flagged),
    )
    seconds = [r['seconds'] for r in details]
    return dict(
        mode=mode, sample=sample, measured_gemini_accuracy=mode == 'gemini' and successes > 0,
        label='OFFLINE FIXTURE CHECK - NOT GEMINI ACCURACY' if mode == 'demo' else 'Gemini raw extraction evaluation',
        documents=n, successful_extractions=successes, extraction_errors=n - successes,
        fields=FIELDS, field_accuracy={f: correct[f] / n for f in FIELDS},
        overall_field_accuracy=sum(correct.values()) / (n * len(FIELDS)),
        document_accuracy=exact / n, validation=validation,
        seconds_total=sum(seconds), seconds_mean=sum(seconds) / n,
        # A clean three-layout smoke test is the gate before spending quota on all 40.
        full_evaluation_ready=(mode == 'gemini' and sample == 'per-layout' and exact == n
                               and not any(r['validation'] for r in details)),
        details=details,
    )


def database_fingerprint() -> str | None:
    """Hash the review database so a run can prove it never wrote to it."""
    path = ROOT/'runtime/ar.sqlite'
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Evaluate extraction against the fictional ground truth.')
    parser.add_argument('--mode', choices=['demo', 'gemini'], default='demo')
    parser.add_argument('--sample', choices=['full', 'per-layout'], default='full')
    parser.add_argument('--check-config', action='store_true', help='show whether a key is set, never the key')
    parser.add_argument('--list-models', action='store_true', help='list models this key can call')
    parser.add_argument('--model', help='override the model for this run without changing .env')
    parser.add_argument('--resume', type=Path, help='retry only failed or pending documents from a full Gemini report')
    parser.add_argument('--resilient', action='store_true', help='paced run with retries and checkpoints')
    parser.add_argument('--limit', type=int, help='maximum failed or pending documents to attempt')
    parser.add_argument('--pace', type=float, default=12)
    parser.add_argument('--max-attempts', type=int, default=4)
    parser.add_argument('--base-delay', type=float, default=2)
    parser.add_argument('--max-delay', type=float, default=30)
    parser.add_argument('--max-wait', type=float, default=120)
    return parser


def _list_models() -> int:
    from google import genai

    key, _ = gemini_settings()
    if not key:
        print('Gemini key is not configured.')
        return 2
    try:
        with genai.Client(api_key=key, http_options={'timeout': 60000}) as client:
            for model in client.models.list():
                if 'generateContent' in (model.supported_actions or []):
                    print(model.name)
    except Exception as exc:
        print(f'Model discovery failed: {type(exc).__name__}; HTTP code: {getattr(exc, "code", None)}')
        return 2
    return 0


def _run_resilient(args) -> int:
    from .resilient import run_evaluation
    from .retry import RetryPolicy

    destination = ROOT/'reports/gemini'/f'resilient_{_timestamp()}.json'
    policy = RetryPolicy(args.max_attempts, args.base_delay, args.max_delay, args.max_wait, args.pace)
    report = run_evaluation(destination, resume=args.resume, policy=policy, limit=args.limit)
    print(json.dumps({k: v for k, v in report.items() if k not in ('details', 'active_attempts')}, indent=2))
    print(f'Checkpoint: {destination}')
    return 0


def _run_single(args) -> int:
    before = database_fingerprint()
    report = evaluate(mode=args.mode, sample=args.sample)
    report['review_database_unchanged'] = database_fingerprint() == before
    report['run_id'] = _timestamp()
    report['started_or_completed_at_note'] = 'Run ID is completion time in UTC; per-document durations use perf_counter.'
    destination = ROOT/'reports'/args.mode
    destination.mkdir(parents=True, exist_ok=True)
    path = destination/f'{args.sample}_{report["run_id"]}.json'
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'details'}, indent=2))
    print(f'Report: {path}')
    if report['full_evaluation_ready']:
        tested_model = report['details'][0]['model']
        print('Three-layout smoke test passed. Full run: '
              f'python -m ar_copilot.evaluate --mode gemini --sample full --model {tested_model}')
    return 0


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    if args.check_config:
        print(json.dumps(configuration_status(), indent=2))
        return 0
    if args.model:
        os.environ['GEMINI_MODEL'] = args.model
    if args.list_models:
        return _list_models()
    if args.mode == 'gemini' and not configuration_status()['key_configured']:
        print('Gemini key not configured. Save it locally in .env; no API calls or measured results produced.')
        return 2
    if args.resilient or args.resume:
        if args.mode != 'gemini' or args.sample != 'full':
            parser.error('Resilient/resume runs require --mode gemini --sample full')
        return _run_resilient(args)
    return _run_single(args)


if __name__ == '__main__':
    raise SystemExit(main())
