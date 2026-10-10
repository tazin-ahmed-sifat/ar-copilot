"""Private timing attempt events; publish aggregate summaries only."""
import csv
import math
import hashlib
import statistics
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta
from pathlib import Path
from . import config
from .core import FIELDS

PROTOCOL = 'counterbalanced-v1'
PRACTICE_DOCUMENTS = ('NC-0001.pdf', 'NC-0002.pdf', 'NC-0003.pdf')


def timings_path():
    return config.ROOT / 'runtime' / 'timings.csv'


@dataclass(frozen=True)
class Timing:
    recorded_at: str
    operator: str
    method: str
    extraction_mode: str
    filename: str
    seconds: float
    extraction_seconds: float
    fields_corrected: int
    field_errors: int | None
    decision: str
    practice: bool
    attempt_id: str = ''
    status: str = 'completed'
    duration_known: bool = True
    api_failed: bool = False
    failure_reason: str = ''
    decision_error: bool | None = None
    study_id: str = ''
    cohort: str = ''
    pair_id: str = ''
    sequence: int = 0
    layout: str = ''
    model: str = ''
    protocol: str = 'legacy'
    corpus_id: str = ''
    extraction_finished: bool = True


COLUMNS = [f.name for f in fields(Timing)]


def timing_corpus_id(folder):
    digest = hashlib.sha256((folder / 'ground_truth.csv').read_bytes())
    names = set(PRACTICE_DOCUMENTS) | {task['filename'] for task in collection_plan('A')}
    for name in sorted(names):
        digest.update(name.encode())
        digest.update((folder / 'invoices' / name).read_bytes())
    return digest.hexdigest()


def collection_plan(cohort):
    """Six different-invoice pairs matching layout, with balanced first method."""
    if cohort not in ('A', 'B'):
        raise ValueError('Cohort must be A or B')
    plan = []
    for index, pair in enumerate([(10, 13), (11, 14), (12, 15), (16, 19), (17, 20), (18, 21)]):
        first = 'manual' if (index + (cohort == 'B')) % 2 == 0 else 'assisted'
        assigned = ('manual', 'assisted') if cohort == 'A' else ('assisted', 'manual')
        tasks = [dict(filename=f'NC-{number:04d}.pdf', method=method, pair_id=str(index+1),
                      layout=str((number-1) % 3+1)) for number, method in zip(pair, assigned)]
        tasks.sort(key=lambda task: task['method'] != first)
        for task in tasks:
            plan.append(dict(task, sequence=len(plan)+1))
    return plan


def count_field_errors(entered, truth):
    """Exact printed strings, forgiving outer whitespace only."""
    return sum((entered.get(f) or '').strip() != (truth.get(f) or '').strip() for f in FIELDS)


def count_corrections(extracted, final):
    return sum((extracted.get(f) or '').strip() != (final.get(f) or '').strip() for f in FIELDS)


def validate_timing(t, *, historical=False):
    recorded = datetime.fromisoformat(t.recorded_at)
    if recorded.utcoffset() != timedelta(0) or not t.operator.strip():
        raise ValueError('Timing requires a UTC timestamp and operator alias')
    if t.protocol not in ('legacy', 'practice-v1', PROTOCOL) or (t.protocol == 'practice-v1' and not t.practice):
        raise ValueError('Invalid timing protocol')
    if not historical and (t.method, t.extraction_mode) not in {('manual', 'none'), ('assisted', 'demo'), ('assisted', 'ollama')}:
        raise ValueError('Invalid method/extraction mode')
    if t.status not in ('in_progress', 'completed', 'incomplete'):
        raise ValueError('Invalid attempt status')
    if any(not math.isfinite(v) or v < 0 for v in (t.seconds, t.extraction_seconds)):
        raise ValueError('Durations must be finite and nonnegative')
    if t.duration_known and t.extraction_seconds > t.seconds:
        raise ValueError('Extraction wait exceeds total duration')
    if t.status == 'completed' and (not t.duration_known or t.seconds <= 0 or t.field_errors is None or t.decision not in ('accept', 'reject')):
        raise ValueError('Completed attempt needs duration, score and decision')
    if t.field_errors is not None and not 0 <= t.field_errors <= len(FIELDS):
        raise ValueError('Invalid field error count')
    if not 0 <= t.fields_corrected <= len(FIELDS):
        raise ValueError('Invalid correction count')
    if t.method == 'manual' and (t.extraction_seconds or t.api_failed or t.fields_corrected or t.model):
        raise ValueError('Manual attempt cannot have extraction metadata')
    if not historical and t.failure_reason not in ('', 'abandoned', 'interrupted', 'timeout', 'model_unavailable',
                              'runtime_unavailable', 'invalid_response_or_input', 'temporary_server_error', 'temporary_or_unknown_rate_limit',
                              'non_retryable_error', 'legacy_unclassified'):
        raise ValueError('Invalid failure category')
    if t.protocol == PROTOCOL:
        if not t.study_id or not t.attempt_id or not t.corpus_id or t.practice or t.extraction_mode == 'demo':
            raise ValueError('Invalid measured protocol metadata')
        task = next((p for p in collection_plan(t.cohort) if p['sequence'] == t.sequence), None)
        if not task or any(getattr(t, k) != task[k] for k in ('filename', 'method', 'pair_id', 'layout')):
            raise ValueError('Attempt does not match collection plan')
        if t.status == 'completed' and t.decision_error is None:
            raise ValueError('Measured completed attempt needs decision scoring')


def append_timing(timing, path=None):
    validate_timing(timing)
    path = path or timings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    if not is_new:
        with path.open(newline='', encoding='utf-8') as handle:
            if next(csv.reader(handle)) != COLUMNS:
                raise ValueError('CSV schema differs; preserve the original and use a new file')
    with path.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(asdict(timing))


def _parse_row(row):
    def boolean(key, default=False):
        value = row.get(key, str(default))
        if value not in ('True', 'False'):
            raise ValueError(f'Invalid {key} boolean')
        return value == 'True'
    return Timing(
        recorded_at=row['recorded_at'], operator=row['operator'], method=row['method'],
        extraction_mode=row['extraction_mode'], filename=row['filename'], seconds=float(row['seconds']),
        extraction_seconds=float(row['extraction_seconds']), fields_corrected=int(row['fields_corrected']),
        field_errors=int(row['field_errors']) if row['field_errors'] else None,
        decision=row['decision'], practice=boolean('practice'), attempt_id=row.get('attempt_id', ''),
        status=row.get('status', 'completed'), duration_known=boolean('duration_known', True),
        api_failed=boolean('api_failed'), failure_reason=row.get('failure_reason', ''),
        decision_error=boolean('decision_error') if row.get('decision_error') else None,
        study_id=row.get('study_id', ''), cohort=row.get('cohort', ''), pair_id=row.get('pair_id', ''),
        sequence=int(row.get('sequence') or 0), layout=row.get('layout', ''), model=row.get('model', ''),
        protocol=row.get('protocol', 'legacy'), corpus_id=row.get('corpus_id', ''),
        extraction_finished=boolean('extraction_finished', True))


def load_timings(path=None):
    if path is None:
        # Older evidence remains intact and descriptive; no automatic protocol upgrade.
        return load_timings(timings_path()) + load_timings(config.ROOT / 'results' / 'timings.csv')
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as handle:
        rows = [_parse_row(row) for row in csv.DictReader(handle)]
    latest, legacy = {}, []
    for row in rows:
        validate_timing(row, historical=True)
        if not row.attempt_id:
            legacy.append(row)
            continue
        previous = latest.get(row.attempt_id)
        if previous:
            identity = ('operator', 'method', 'extraction_mode', 'filename', 'practice', 'study_id',
                        'cohort', 'pair_id', 'sequence', 'layout', 'protocol', 'corpus_id')
            if previous.status != 'in_progress' or any(getattr(previous, k) != getattr(row, k) for k in identity):
                raise ValueError('Duplicate final attempt or changed attempt identity')
            if datetime.fromisoformat(row.recorded_at) < datetime.fromisoformat(previous.recorded_at):
                raise ValueError('Attempt event timestamp moved backwards')
        latest[row.attempt_id] = row
    return legacy + list(latest.values())


def _spread(values):
    if len(values) < 2:
        q1 = q3 = values[0] if values else None
    else:
        q1, _, q3 = statistics.quantiles(values, n=4, method='inclusive')
    return dict(median=statistics.median(values) if values else None, q1=q1, q3=q3,
                min=min(values, default=None), max=max(values, default=None))


def comparison(timings):
    measured = [t for t in timings if not t.practice and t.protocol == PROTOCOL]
    unavailable = dict(available=False, reason='Needs all 12 planned attempts per participant; legacy/demo rows are descriptive only.')
    if not measured:
        return unavailable
    if any(r.method == 'assisted' and r.extraction_mode != 'ollama' for r in measured):
        return dict(available=False, reason='Historical extraction modes are excluded from the Ollama comparison.')
    if len({r.corpus_id for r in measured}) != 1:
        return dict(available=False, reason='Different corpora must be summarized separately.')
    if len({(r.extraction_mode, r.model) for r in measured if r.method == 'assisted'}) != 1:
        return dict(available=False, reason='Different providers/models must be summarized separately.')
    batches = {}
    for row in measured:
        batches.setdefault((row.operator, row.study_id), []).append(row)
    paired, excluded = [], 0
    for batch in batches.values():
        if len({r.cohort for r in batch}) != 1 or len(batch) != 12 or {r.sequence for r in batch} != set(range(1, 13)):
            return unavailable
        if any(r.status == 'in_progress' or (r.method == 'assisted' and (r.extraction_mode, r.model) not in {('ollama', 'qwen3:8b')}) for r in batch):
            return unavailable
        if any(r.operator == batch[0].operator and r.corpus_id == batch[0].corpus_id and r not in batch
               and r.filename in {b.filename for b in batch} for r in timings):
            return dict(available=False, reason='Repeated exposure to measured documents; use an unseen corpus.')
        for pair_id in map(str, range(1, 7)):
            pair = [r for r in batch if r.pair_id == pair_id]
            if len(pair) != 2 or {r.method for r in pair} != {'manual', 'assisted'}:
                return unavailable
            if all(r.status == 'completed' for r in pair):
                paired.append(pair)
            else:
                excluded += 1
    if not paired:
        return dict(available=False, reason='No matched completed pairs; no time reduction calculated.')
    manual = [r.seconds for pair in paired for r in pair if r.method == 'manual']
    assisted = [r.seconds for pair in paired for r in pair if r.method == 'assisted']
    m, a = statistics.median(manual), statistics.median(assisted)
    return dict(available=True, protocol=PROTOCOL, participants=len({r.operator for r in measured}),
                completed_pairs=len(paired), incomplete_pairs_excluded=excluded,
                manual_seconds=_spread(manual), assisted_seconds=_spread(assisted),
                median_difference_seconds=m-a, percentage_time_reduction=100*(m-a)/m,
                definition='100 * (manual median - Ollama-assisted median) / manual median on matched completed pairs; negative means slower.',
                limitation='Different invoices matched by layout; synthetic pilot, no causal claim. Incomplete pairs excluded from medians but retained in attempt counts; completion bias remains.')


def summarise(timings):
    groups = {}
    for timing in timings:
        validate_timing(timing, historical=True)
        if not timing.practice:
            groups.setdefault(f'{timing.method}/{timing.extraction_mode}', []).append(timing)
    summary = {}
    for key, rows in sorted(groups.items()):
        completed = [r for r in rows if r.status == 'completed']
        errors = [r.field_errors for r in completed]
        summary[key] = dict(
            documents=len(rows), completed=len(completed), incomplete=sum(r.status == 'incomplete' for r in rows),
            unresolved=sum(r.status == 'in_progress' for r in rows), api_failures=sum(r.api_failed for r in rows),
            unknown_extraction_outcomes=sum(r.method == 'assisted' and not r.extraction_finished for r in rows),
            operators=len({r.operator for r in rows}), seconds=_spread([r.seconds for r in completed]),
            incomplete_seconds=_spread([r.seconds for r in rows if r.status == 'incomplete' and r.duration_known]),
            unknown_durations=sum(not r.duration_known for r in rows),
            extraction_seconds_median=statistics.median(r.extraction_seconds for r in completed) if completed else None,
            field_errors_total=sum(errors), field_error_rate=sum(errors)/(len(completed)*len(FIELDS)) if completed else None,
            documents_with_errors=sum(e > 0 for e in errors), fields_corrected_total=sum(r.fields_corrected for r in rows),
            corrections_unassessed_api_failures=sum(r.api_failed for r in completed),
            decision_errors=sum(r.decision_error is True for r in completed),
            decisions_unscored=sum(r.decision_error is None for r in completed))
    return dict(practice_rows_excluded=sum(t.practice for t in timings), groups=summary, comparison=comparison(timings))
