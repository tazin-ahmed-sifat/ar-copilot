"""Generate the fictional 40-document corpus: PDFs, printed ground truth, payments and fixtures.

Generation is seeded and byte-reproducible, because the offline fixtures are keyed by
each PDF's SHA-256. Changing anything that is drawn or the order of random draws
changes every hash.
"""
import csv
import hashlib
import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from .core import CUSTOMERS, DATE_FORMATS, FIELDS, SUPPLIER, parse_date

SEED = 20261010
DOCUMENT_COUNT = 40
PAGE_SIZE = (595, 842)  # A4 in points
LABELS = dict(zip(FIELDS, ['Document type', 'Supplier', 'Customer', 'Document number', 'Invoice date',
                           'Due date', 'PO number', 'Currency', 'Net', 'VAT', 'Total', 'Linked invoice']))
LAYOUT_COLOURS = ['#17324D', '#315944', '#58354F']
LAYOUT_TITLES = ['NORTHBRIDGE | INVOICE', 'NORTHBRIDGE | ACCOUNT STATEMENT', 'NORTHBRIDGE | BILLING NOTE']

# Deliberate cases, by zero-based document index.
MISSING_PO = 5            # NC-0006: no purchase order printed
WRONG_TOTAL = 8           # NC-0009: printed total is £7.00 more than net + VAT
CREDIT_NOTE = 39          # NC-0040: credit note against NC-0005
CREDITED_INVOICE = 4      # NC-0005


def generate(folder: Path = Path('data'), seed: int = SEED) -> list[dict]:
    """Write the corpus to `folder` and return the ground-truth rows."""
    folder = Path(folder)
    (folder / 'invoices').mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    truth, payments, anomalies, fixtures = [], [], [], {}
    for index in range(DOCUMENT_COUNT):
        layout = index % 3
        record, issued, total = _document(index, layout, rng, truth)
        filename = record['document_number'] + '.pdf'
        path = folder / 'invoices' / filename
        _draw_pdf(path, record, layout)
        truth.append(dict(filename=filename, layout=layout + 1, **record))
        fixtures[hashlib.sha256(path.read_bytes()).hexdigest()] = record
        if index in (MISSING_PO, WRONG_TOTAL):
            expected = ['missing:po_number'] if index == MISSING_PO else ['totals']
            anomalies.append(dict(filename=filename, expected_errors=expected))
        payment = _payment(index, record, issued, total)
        if payment:
            payments.append(payment)
    _write_csv(folder / 'ground_truth.csv', truth)
    _write_csv(folder / 'payments.csv', payments)
    (folder / 'anomalies.json').write_text(json.dumps(anomalies, indent=2))
    (folder / 'demo_fixtures.json').write_text(json.dumps(fixtures, indent=2))
    manifest = dict(seed=seed, documents=DOCUMENT_COUNT, invoices=DOCUMENT_COUNT - 1,
                    credit_notes=1, layouts=3, fictional=True)
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return truth


def _document(index: int, layout: int, rng: random.Random, truth: list[dict]) -> tuple[dict, date, Decimal]:
    """Printed field strings for one document. The two rng draws must stay in this order."""
    issued = date(2026, 4, 1) + timedelta(days=rng.randrange(180))
    net = Decimal(rng.randrange(50000, 500000)) / 100
    is_credit = index == CREDIT_NOTE
    if is_credit:
        net = Decimal('-100.00')
        issued = parse_date(truth[CREDITED_INVOICE]['invoice_date']) + timedelta(days=10)
    vat = net * Decimal('.20')
    total = net + vat + (Decimal('7.00') if index == WRONG_TOTAL else 0)
    date_format = DATE_FORMATS[layout]
    values = ['credit_note' if is_credit else 'invoice', SUPPLIER, CUSTOMERS[index % 5], f'NC-{index + 1:04d}',
              issued.strftime(date_format), (issued + timedelta(days=30)).strftime(date_format),
              '' if index == MISSING_PO else f'PO-{1000 + index}', 'GBP', f'{net:.2f}', f'{vat:.2f}',
              f'{total:.2f}', 'NC-0005' if is_credit else '']
    return dict(zip(FIELDS, values)), issued, total


def _payment(index: int, record: dict, issued: date, total: Decimal) -> dict | None:
    """Every third invoice stays unpaid; the rest are half or fully paid 35 days after issue."""
    if index == CREDIT_NOTE or index % 3 == 0:
        return None
    amount = total if index % 3 == 2 else total / 2
    return dict(payment_id=f'PAY-{index + 1:04d}', invoice_number=record['document_number'],
                customer=record['customer'], payment_date=(issued + timedelta(days=35)).isoformat(),
                amount=f'{amount:.2f}')


def _draw_pdf(path: Path, record: dict, layout: int) -> None:
    pdf = canvas.Canvas(str(path), pagesize=PAGE_SIZE, invariant=1)
    pdf.setTitle('FICTIONAL ' + record['document_number'])
    pdf.setFillColor(HexColor(LAYOUT_COLOURS[layout]))
    pdf.rect(30, 745, 535, 67, fill=1, stroke=0)
    pdf.setFillColor(HexColor('#FFFFFF'))
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(44, 778, LAYOUT_TITLES[layout])
    pdf.setFillColor(HexColor('#222222'))
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(40, 717, 'FICTIONAL DOCUMENT - TRAINING ONLY')
    [_draw_inline, _draw_ruled, _draw_two_column][layout](pdf, record)
    pdf.setFont('Helvetica', 10)
    pdf.drawString(40, 230, 'Description: simulated automotive component supply / return')
    pdf.drawString(40, 210, 'Assumed VAT rate: 20%. All companies and transactions are fictional.')
    pdf.save()


def _draw_inline(pdf: canvas.Canvas, record: dict) -> None:
    for row, field in enumerate(FIELDS):
        pdf.setFont('Helvetica', 11)
        pdf.drawString(40, 675 - row * 32, f'{LABELS[field]}: {record[field]}')


def _draw_ruled(pdf: canvas.Canvas, record: dict) -> None:
    for row, field in enumerate(FIELDS):
        y = 675 - row * 32
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(40, y, LABELS[field] + ':')
        pdf.setFont('Helvetica', 11)
        pdf.drawString(190, y, record[field])
        pdf.line(40, y - 10, 555, y - 10)


def _draw_two_column(pdf: canvas.Canvas, record: dict) -> None:
    for position, field in enumerate(FIELDS):
        x, y = 40 + (position % 2) * 270, 675 - (position // 2) * 62
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(x, y, LABELS[field] + ':')
        pdf.setFont('Helvetica', 9)
        pdf.drawString(x, y - 20, record[field])


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    generate()
    print(f'Generated {DOCUMENT_COUNT} fictional documents with ground truth, anomalies, payments and fixtures.')
