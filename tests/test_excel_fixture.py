"""The hand-computed Excel fixture pins the aging rules that excel/aged_debt.pq must reproduce."""
import csv
from datetime import date
from decimal import Decimal

from ar_copilot.config import ROOT
from ar_copilot.core import aged_debt

FIXTURE = ROOT / 'excel' / 'fixture'
REPORTING_DATE = date(2026, 10, 10)
COMPARED = ['customer', 'document_number', 'due_date', 'total', 'payments', 'credits', 'balance', 'days_overdue', 'bucket']


def read(name: str) -> list[dict]:
    with (FIXTURE / name).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def normalise(row: dict) -> dict:
    values = {key: str(row[key]) for key in COMPARED}
    for key in ('total', 'payments', 'credits', 'balance'):
        values[key] = f'{Decimal(values[key]):.2f}'
    return values


def test_python_rules_match_the_hand_computed_fixture():
    actual = aged_debt(read('documents.csv'), read('payments.csv'), REPORTING_DATE)
    assert [normalise(r) for r in actual] == [normalise(r) for r in read('expected_aged_debt.csv')]
