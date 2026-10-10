"""Build excel/fixture/aged_debt_fixture.xlsx from the hand-made fixture CSVs.

The workbook comes from the app's own exporter, so excel/aged_debt.pq runs against
exactly the tables a real export contains. Its AgedDebt sheet is the Python result;
excel/fixture/expected_aged_debt.csv is the same answer worked out by hand.
"""
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
from datetime import date

from ar_copilot.config import ROOT
from ar_copilot.core import aged_debt
from ar_copilot.export import workbook

FIXTURE = ROOT / 'excel' / 'fixture'
REPORTING_DATE = date(2026, 10, 10)


def read(name: str) -> list[dict]:
    with (FIXTURE / name).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def fixture_records() -> list[dict]:
    """Shape fixture rows like Store.documents() output, which the exporter expects."""
    return [dict(row, id=index, filename=f"{row['document_number']}.pdf", hash=f"fixture-{row['document_number']}",
                 posting_key=f"fixture|{row['customer']}|{row['document_type']}|{row['document_number']}".casefold())
            for index, row in enumerate(read('documents.csv'), start=1)]


def main() -> None:
    records, payments = fixture_records(), read('payments.csv')
    debt = aged_debt(records, payments, REPORTING_DATE)
    destination = FIXTURE / 'aged_debt_fixture.xlsx'
    destination.write_bytes(workbook(records, debt, REPORTING_DATE, 'debt', payments))
    print(f'Wrote {destination.relative_to(ROOT).as_posix()} ({len(debt)} aged-debt rows)')


if __name__ == '__main__':
    main()
