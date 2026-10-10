"""Seeded, wholly fictional one-line invoice corpus; truth mirrors printed strings."""
import csv
import hashlib
import json
import random
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from .core import FIELDS, SUPPLIER, CUSTOMERS, parse_date

LABELS = dict(zip(FIELDS, ['Document type', 'Supplier', 'Customer', 'Document number',
    'Invoice date', 'Due date', 'PO number', 'Currency', 'Net', 'VAT', 'Total', 'Linked invoice']))

def generate(folder=Path('data'), seed=20261010):
    folder = Path(folder)
    (folder / 'invoices').mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    truth, payments, anomalies, fixtures = [], [], [], {}
    for i in range(40):
        layout = i % 3
        issued = date(2026, 4, 1) + timedelta(days=rng.randrange(180))
        fmt = ['%Y-%m-%d', '%d/%m/%Y', '%d %b %Y'][layout]
        net = Decimal(rng.randrange(50000, 500000)) / 100
        if i == 39:
            net = Decimal('-100.00')
            # A linked credit is issued after the original NC-0005 invoice.
            issued = parse_date(truth[4]['invoice_date']) + timedelta(days=10)
        vat = net * Decimal('.20')
        total = net + vat + (Decimal('7.00') if i == 8 else 0)
        record = dict(zip(FIELDS, ['credit_note' if i == 39 else 'invoice', SUPPLIER,
            CUSTOMERS[i % 5], f'NC-{i+1:04d}', issued.strftime(fmt),
            (issued + timedelta(days=30)).strftime(fmt), '' if i == 5 else f'PO-{1000+i}',
            'GBP', f'{net:.2f}', f'{vat:.2f}', f'{total:.2f}', 'NC-0005' if i == 39 else '']))
        filename = record['document_number'] + '.pdf'
        path = folder / 'invoices' / filename
        c = canvas.Canvas(str(path), pagesize=(595, 842), invariant=1)
        c.setTitle('FICTIONAL ' + record['document_number'])
        c.setFillColor(HexColor(['#17324D', '#315944', '#58354F'][layout]))
        c.rect(30, 745, 535, 67, fill=1, stroke=0)
        c.setFillColor(HexColor('#FFFFFF'))
        c.setFont('Helvetica-Bold', 18)
        c.drawString(44, 778, ['NORTHBRIDGE | INVOICE', 'NORTHBRIDGE | ACCOUNT STATEMENT',
                              'NORTHBRIDGE | BILLING NOTE'][layout])
        c.setFillColor(HexColor('#222222'))
        c.setFont('Helvetica-Bold', 12)
        c.drawString(40, 717, 'FICTIONAL DOCUMENT - TRAINING ONLY')
        if layout == 0:
            for j, field in enumerate(FIELDS):
                c.setFont('Helvetica', 11)
                c.drawString(40, 675-j*32, f'{LABELS[field]}: {record[field]}')
        elif layout == 1:
            for j, field in enumerate(FIELDS):
                y = 675-j*32
                c.setFont('Helvetica-Bold', 10)
                c.drawString(40, y, LABELS[field] + ':')
                c.setFont('Helvetica', 11)
                c.drawString(190, y, record[field])
                c.line(40, y-10, 555, y-10)
        else:
            for j, field in enumerate(FIELDS):
                x, y = 40+(j % 2)*270, 675-(j//2)*62
                c.setFont('Helvetica-Bold', 10)
                c.drawString(x, y, LABELS[field] + ':')
                c.setFont('Helvetica', 9)
                c.drawString(x, y-20, record[field])
        c.setFont('Helvetica', 10)
        c.drawString(40, 230, 'Description: simulated automotive component supply / return')
        c.drawString(40, 210, 'Assumed VAT rate: 20%. All companies and transactions are fictional.')
        c.save()
        truth.append(dict(filename=filename, layout=layout+1, **record))
        fixtures[hashlib.sha256(path.read_bytes()).hexdigest()] = record
        if i in (5, 8):
            anomalies.append(dict(filename=filename, expected_errors=['missing:po_number'] if i == 5 else ['totals']))
        if i != 39 and i % 3:
            payments.append(dict(payment_id=f'PAY-{i+1:04d}', invoice_number=record['document_number'],
                customer=record['customer'], payment_date=(issued+timedelta(days=35)).isoformat(),
                amount=f'{total if i % 3 == 2 else total/2:.2f}'))
    for name, rows in [('ground_truth.csv', truth), ('payments.csv', payments)]:
        with (folder / name).open('w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (folder / 'anomalies.json').write_text(json.dumps(anomalies, indent=2))
    (folder / 'demo_fixtures.json').write_text(json.dumps(fixtures, indent=2))
    (folder / 'manifest.json').write_text(json.dumps(dict(seed=seed, documents=40, invoices=39,
        credit_notes=1, layouts=3, fictional=True), indent=2))
    return truth

if __name__ == '__main__':
    generate()
    print('Generated 40 fictional documents and separate truth, anomalies, payments and demo fixtures.')
