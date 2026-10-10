"""Paced Gemini evaluation that checkpoints after every step and can resume failed documents.

A free-tier quota can stop a 40-document run part way through. Writing the report
atomically after each attempt means an interrupted run loses nothing, and a resume
calls the API only for documents that have not yet succeeded.
"""
import csv
import hashlib
import io
import json
import random
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from .config import ROOT
from .core import FIELDS, validate
from .extract import extract
from .retry import RetryPolicy, run_with_retry


def atomic_save(path, report: dict) -> None:
    """Write to a temporary file and rename, so a crash never leaves half a checkpoint."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
    temporary.replace(path)


def run_stamp() -> str:
    """UTC timestamp used for run ids and report file names."""
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def load_expected(folder: Path) -> dict[str, set[str]]:
    """The intentional anomalies and the rule codes each should trigger."""
    anomalies = json.loads((Path(folder) / 'anomalies.json').read_text())
    return {a['filename']: set(a['expected_errors']) for a in anomalies}


def score_fields(row: dict, result: dict) -> tuple[dict, dict]:
    """Exact string match per field; a failed extraction matches nothing, blank equals missing."""
    matches = {f: not result['error'] and (result['fields'].get(f) or '') == row[f] for f in FIELDS}
    mismatches = {f: dict(expected=row[f], actual=result['fields'].get(f)) for f in FIELDS if not matches[f]}
    return matches, mismatches


def compare(row: dict, result: dict) -> dict:
    """Score one extraction against printed truth by exact string match on every field."""
    matches, mismatches = score_fields(row, result)
    # A failed call has no fields to validate; flagging it would count an outage as an anomaly.
    rules = validate(result['fields']) if not result['error'] else []
    return dict(filename=row['filename'], layout=row['layout'], ground_truth={f: row[f] for f in FIELDS},
                matches=matches, mismatches=mismatches, validation=rules, **result)


def metrics(details: list[dict], expected: dict[str, set[str]]) -> dict:
    """Completion and accuracy, keeping 'on completed documents' and 'overall' separate."""
    completed = [r for r in details if not r['error']]
    n, count = len(details), len(completed)
    correct = {f: sum(bool(r['matches'][f]) for r in completed) for f in FIELDS}
    exact = sum(all(r['matches'].values()) for r in completed)
    anomaly_rows = [r for r in completed if r['filename'] in expected]
    api_failed = [r for r in details if r['error'] and r.get('error_kind') != 'pending']

    def ratio(numerator, denominator):
        return numerator / denominator if denominator else None

    def rule_caught(row):
        return expected[row['filename']].issubset(row['validation'])

    return dict(
        documents=n,
        completed_documents=count,
        completion_rate=count / n,
        failed_documents=len(api_failed),
        pending_documents=sum(r.get('error_kind') == 'pending' for r in details),
        field_accuracy_completed={f: ratio(correct[f], count) for f in FIELDS},
        field_accuracy_overall={f: correct[f] / n for f in FIELDS},
        overall_field_accuracy=sum(correct.values()) / (n * len(FIELDS)),
        completed_field_accuracy=ratio(sum(correct.values()), count * len(FIELDS)),
        overall_document_accuracy=exact / n,
        completed_document_accuracy=ratio(exact, count),
        api_failures=[dict(filename=r['filename'], code=r.get('error_code'),
                           kind=r.get('error_kind', 'legacy_unclassified')) for r in api_failed],
        accounting_anomalies=dict(
            expected=len(expected),
            rules_detected=sum(rule_caught(r) for r in anomaly_rows),
            rules_missed_after_completed_extraction=sum(not rule_caught(r) for r in anomaly_rows),
            unassessed=sum(r['filename'] in expected and bool(r['error']) for r in details),
            false_positives=sum(r['filename'] not in expected and bool(r['validation']) for r in completed),
        ),
    )


def run_evaluation(output, folder=ROOT/'data', resume=None, policy=None, limit=None,
                   call=extract, sleep=time.sleep, monotonic=time.perf_counter, uniform=random.uniform,
                   announce=print, database=None) -> dict:
    """Evaluate every failed or pending document, checkpointing to `output` after each step.

    With `resume`, successful extractions from that report are reused and only its failed
    documents are called again. The source report is never modified.
    """
    policy = policy or RetryPolicy()
    folder, output = Path(folder), Path(output)
    _check_paths(output, resume, limit)
    rows = list(csv.DictReader((folder/'ground_truth.csv').open(encoding='utf-8')))
    expected = load_expected(folder)
    source = _load_source(resume, rows)
    prior_by_name = {r['filename']: r for r in source['details']} if source else {}
    payloads = {r['filename']: (folder/'invoices'/r['filename']).read_bytes() for r in rows}
    details = [_starting_detail(row, payloads[row['filename']], prior_by_name.get(row['filename']))
               for row in rows]
    prior_seconds = source.get('cumulative_observed_seconds', source.get('seconds_total', 0)) if source else 0
    run = _Run(output=output, folder=folder, policy=policy, details=details, expected=expected,
               resume_source=str(resume) if resume else None, prior_seconds=prior_seconds,
               call=call, sleep=sleep, monotonic=monotonic, uniform=uniform, announce=announce,
               database=Path(database) if database else ROOT/'runtime/ar.sqlite')
    return run.execute(rows, payloads, limit)


def _check_paths(output: Path, resume, limit) -> None:
    if limit is not None and limit < 1:
        raise ValueError('limit must be positive')
    if resume and Path(resume).resolve() == output.resolve():
        raise ValueError('Resume source is immutable: choose a new checkpoint path')
    if output.exists():
        raise ValueError('Checkpoint already exists: resume it into a new path')


def _load_source(resume, rows: list[dict]) -> dict | None:
    if not resume:
        return None
    source = json.loads(Path(resume).read_text())
    if source['mode'] != 'gemini' or len(source['details']) != len(rows):
        raise ValueError('Resume requires a full Gemini report for this corpus')
    if {r['filename'] for r in source['details']} != {r['filename'] for r in rows}:
        raise ValueError('Resume source document set differs from dataset')
    return source


def _starting_detail(row: dict, raw: bytes, prior: dict | None) -> dict:
    """Reuse a prior result only if the document and its truth are provably unchanged."""
    digest = hashlib.sha256(raw).hexdigest()
    if prior is None:
        pending = dict(fields={}, text='', error='Not attempted', error_kind='pending',
                       error_code=None, model=None, mode='gemini', seconds=0)
        return dict(compare(row, pending), source_hash=digest)
    if prior['ground_truth'] != {f: row[f] for f in FIELDS}:
        raise ValueError('Ground truth changed; do not reuse this report')
    if prior.get('source_hash'):
        if prior['source_hash'] != digest:
            raise ValueError('PDF changed; do not reuse this report')
    else:
        # Reports written before hashes were recorded can only be checked by their text.
        text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(raw)).pages)
        if text != prior.get('text'):
            raise ValueError('Legacy PDF text changed; cannot safely resume')
    prior = dict(prior, source_hash=digest)
    if prior['error']:
        prior['validation'] = []  # a past API failure is not an accounting anomaly
    return prior


class _Run:
    """State for one evaluator invocation: the report, its checkpoint file and request pacing."""

    def __init__(self, *, output: Path, folder: Path, policy: RetryPolicy, details: list[dict],
                 expected: dict[str, set[str]], resume_source: str | None, prior_seconds: float,
                 call, sleep, monotonic, uniform, announce, database: Path):
        self.output, self.folder, self.policy = output, folder, policy
        self.details, self.expected = details, expected
        self.call, self.sleep, self.monotonic = call, sleep, monotonic
        self.uniform, self.announce = uniform, announce
        self.database = database
        self.database_before = self._fingerprint()
        self.started = monotonic()
        self.last_request_start = None
        self.report = dict(
            mode='gemini', sample='full', run_id=run_stamp(),
            resume_source=resume_source, policy=asdict(policy), details=details,
            state='running', stop_reason=None, attempted_this_run=0,
            successful_calls_reused=sum(not r['error'] for r in details),
            new_request_seconds=0.0, new_retry_wait_seconds=0.0, new_pacing_wait_seconds=0.0,
            prior_observed_seconds=prior_seconds)

    def _fingerprint(self) -> str | None:
        # The evaluator must never touch the review database; comparing hashes proves it didn't.
        return hashlib.sha256(self.database.read_bytes()).hexdigest() if self.database.exists() else None

    def save(self) -> None:
        report = self.report
        report['metrics'] = metrics(self.details, self.expected)
        report['invocation_seconds'] = self.monotonic() - self.started
        report['cumulative_observed_seconds'] = (
            report['prior_observed_seconds'] + report['new_request_seconds']
            + report['new_retry_wait_seconds'] + report['new_pacing_wait_seconds'])
        report['review_database_unchanged'] = self._fingerprint() == self.database_before
        atomic_save(self.output, report)

    def paced_call(self, raw: bytes) -> dict:
        if self.last_request_start is not None:
            delay = max(0, self.policy.pace - (self.monotonic() - self.last_request_start))
            if delay:
                self.announce(f'Pacing: waiting {delay:.1f}s before request', flush=True)
                self.sleep(delay)
                self.report['new_pacing_wait_seconds'] += delay
        self.last_request_start = self.monotonic()
        return self.call(raw, 'gemini', self.folder/'demo_fixtures.json', single_attempt=True)

    def record_attempt(self, attempt: dict) -> None:
        # An attempt is reported again once its retry wait is known; replace it rather than append.
        attempts = self.report['active_attempts']
        if attempts and attempts[-1]['number'] == attempt['number']:
            attempts[-1] = dict(attempt)
        else:
            attempts.append(dict(attempt))
        self.save()
        if attempt['wait_after_seconds']:
            self.announce(f'Retry wait: {attempt["wait_after_seconds"]:.1f}s', flush=True)

    def execute(self, rows: list[dict], payloads: dict[str, bytes], limit: int | None) -> dict:
        report = self.report
        self.save()
        try:
            for index, row in enumerate(rows):
                if not self.details[index]['error']:
                    continue
                if limit and report['attempted_this_run'] >= limit:
                    report['stop_reason'] = 'document_limit_reached'
                    break
                result = self._evaluate_document(index, row, payloads[row['filename']])
                if result.get('stop_reason'):
                    report['stop_reason'] = result['stop_reason']
                    break
            finished = all(not r['error'] for r in self.details)
            report['state'] = 'finished' if finished else 'stopped_with_failures_or_pending'
        except (KeyboardInterrupt, Exception):
            report['state'] = 'interrupted'
            self.save()
            raise
        self.save()
        return report

    def _evaluate_document(self, index: int, row: dict, raw: bytes) -> dict:
        report = self.report
        self.announce(f'Evaluating {row["filename"]}; prior successes will not be repeated', flush=True)
        report['active_document'] = row['filename']
        report['active_attempts'] = []
        self.save()
        result = run_with_retry(lambda: self.paced_call(raw), self.policy, sleep=self.sleep,
                                uniform=self.uniform, on_attempt=self.record_attempt)
        previous = self.details[index]
        new = compare(row, result)
        new['source_hash'] = previous['source_hash']
        # Keep every earlier outcome for this document so retries stay auditable.
        earlier = {k: v for k, v in previous.items() if k != 'previous_results'}
        new['previous_results'] = previous.get('previous_results', []) + [earlier]
        self.details[index] = new
        report['attempted_this_run'] += 1
        report['new_request_seconds'] += result['request_seconds']
        report['new_retry_wait_seconds'] += result['retry_wait_seconds']
        report['active_document'] = None
        report['active_attempts'] = []
        self.save()
        outcome = 'completed' if not result['error'] else result.get('error_kind', 'failed')
        self.announce(f'{row["filename"]}: {outcome}', flush=True)
        return result
