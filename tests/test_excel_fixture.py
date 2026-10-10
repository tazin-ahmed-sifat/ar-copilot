"""The hand-computed Excel fixture pins the aging rules that excel/aged_debt.pq must reproduce."""
from decimal import Decimal

from ar_copilot.core import aged_debt
from scripts.build_excel_fixture import REPORTING_DATE, read

COMPARED = ['customer', 'document_number', 'due_date', 'total', 'payments', 'credits', 'balance', 'days_overdue', 'bucket']


def normalise(row: dict) -> dict:
    values = {key: str(row[key]) for key in COMPARED}
    for key in ('total', 'payments', 'credits', 'balance'):
        values[key] = f'{Decimal(values[key]):.2f}'
    return values


def test_python_rules_match_the_hand_computed_fixture():
    actual = aged_debt(read('documents.csv'), read('payments.csv'), REPORTING_DATE)
    assert [normalise(r) for r in actual] == [normalise(r) for r in read('expected_aged_debt.csv')]
