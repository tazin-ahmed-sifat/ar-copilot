"""Time-per-document measurements for manual keying versus the assisted review flow.

Each timed document becomes one CSV row. Rows hold durations and error counts only,
never the values the operator typed, so the raw file can be committed as evidence.
"""
import csv
import statistics
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import config
from .core import FIELDS

def timings_path() -> Path:
    return config.ROOT / 'results' / 'timings.csv'


@dataclass(frozen=True)
class Timing:
    recorded_at: str          # UTC ISO timestamp when the document was finished
    operator: str
    method: str               # 'manual' or 'assisted'
    extraction_mode: str      # 'none' for manual; 'demo' or 'gemini' for assisted
    filename: str
    seconds: float            # whole document: open to final decision
    extraction_seconds: float  # part of `seconds` spent waiting for extraction
    fields_corrected: int     # assisted only: fields changed from the extracted value
    field_errors: int         # fields that differ from the printed ground truth
    decision: str             # 'accept' or 'reject'
    practice: bool            # warm-up rows are kept but left out of the summary


COLUMNS = [f.name for f in fields(Timing)]


def count_field_errors(entered: dict[str, str], truth: dict[str, str]) -> int:
    """Score with the same exact-string rule as the extraction evaluation."""
    return sum((entered.get(f) or '').strip() != (truth.get(f) or '') for f in FIELDS)


def count_corrections(extracted: dict[str, str | None], final: dict[str, str]) -> int:
    return sum((extracted.get(f) or '') != (final.get(f) or '') for f in FIELDS)


def append_timing(timing: Timing, path: Path | None = None) -> None:
    path = path or timings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(asdict(timing))


def load_timings(path: Path | None = None) -> list[Timing]:
    path = path or timings_path()
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as handle:
        return [_parse_row(row) for row in csv.DictReader(handle)]


def _parse_row(row: dict[str, str]) -> Timing:
    return Timing(
        recorded_at=row['recorded_at'], operator=row['operator'], method=row['method'],
        extraction_mode=row['extraction_mode'], filename=row['filename'],
        seconds=float(row['seconds']), extraction_seconds=float(row['extraction_seconds']),
        fields_corrected=int(row['fields_corrected']), field_errors=int(row['field_errors']),
        decision=row['decision'], practice=row['practice'] == 'True',
    )


def _spread(values: list[float]) -> dict[str, float | None]:
    """Median and interquartile range: robust to the odd interrupted document."""
    if len(values) < 2:
        q1 = q3 = values[0] if values else None
    else:
        q1, _, q3 = statistics.quantiles(values, n=4, method='inclusive')
    return {
        'median': statistics.median(values) if values else None,
        'q1': q1,
        'q3': q3,
        'min': min(values, default=None),
        'max': max(values, default=None),
    }


def summarise(timings: list[Timing]) -> dict:
    """Group timed (non-practice) rows by method and extraction mode."""
    groups: dict[str, list[Timing]] = {}
    for timing in timings:
        if not timing.practice:
            groups.setdefault(f'{timing.method}/{timing.extraction_mode}', []).append(timing)
    summary = {}
    for key, rows in sorted(groups.items()):
        errors = [r.field_errors for r in rows]
        summary[key] = {
            'documents': len(rows),
            'operators': len({r.operator for r in rows}),
            'seconds': _spread([r.seconds for r in rows]),
            'extraction_seconds_median': statistics.median(r.extraction_seconds for r in rows),
            'field_errors_total': sum(errors),
            'field_error_rate': sum(errors) / (len(rows) * len(FIELDS)),
            'documents_with_errors': sum(e > 0 for e in errors),
            'fields_corrected_total': sum(r.fields_corrected for r in rows),
        }
    return {
        'practice_rows_excluded': sum(t.practice for t in timings),
        'groups': summary,
    }
