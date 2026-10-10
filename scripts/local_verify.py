"""Produce local QA previews and example exports without changing the app database."""
import sys
from pathlib import Path

if not __package__:
    # Run as `python scripts/<name>.py`: put the repo root on the path so
    # `ar_copilot` imports the same way it does under `python -m scripts.<name>`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import io
import json
from datetime import date
from decimal import Decimal
import pymupdf as fitz
from PIL import Image, ImageDraw
from streamlit.testing.v1 import AppTest
from google.genai import types
from ar_copilot.core import FIELDS, validate, aged_debt
from ar_copilot.extract import extract, Invoice
from ar_copilot.store import Store
from ar_copilot.export import workbook

def main():
    tmp = Path('tmp/qa'); tmp.mkdir(parents=True, exist_ok=True)
    output = Path('output'); output.mkdir(exist_ok=True)
    # Explicit QA database, separate from the app's user review database.
    store = Store(':memory:')
    for path in sorted(Path('data/invoices').glob('*.pdf')):
        raw = path.read_bytes()
        result = extract(raw)
        document_id = store.ingest(path.name, raw, result)
        record = next(r for r in store.documents() if r['id']==document_id)
        if not validate(result['fields']) and record['status'] != 'approved':
            store.review(document_id, result['fields'], 'approve', 'Automated local QA',
                         'OFFLINE TEST FIXTURE approval; not a user decision')
    payments = list(csv.DictReader(Path('data/payments.csv').open()))
    store.import_payments(payments)
    records = store.documents()
    debt = aged_debt(records, store.payments(), date(2026,10,10))
    for kind in ('posted','debt'):
        (output/f'offline_example_{kind}.xlsx').write_bytes(workbook(records, debt, date(2026,10,10), kind))
    images = []
    for number in (1,2,3,6,9,40):
        path = Path('data/invoices')/f'NC-{number:04d}.pdf'
        with fitz.open(path) as pdf:
            pix = pdf[0].get_pixmap(matrix=fitz.Matrix(.9,.9))
            images.append(Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB'))
    sheet = Image.new('RGB', (images[0].width*3, images[0].height*2), 'white')
    for i, image in enumerate(images):
        sheet.paste(image, ((i%3)*image.width, (i//3)*image.height))
    sheet.save(tmp/'pdf_contact_sheet.png')
    # Installed official SDK accepts the documented structured output configuration.
    types.GenerateContentConfig(response_mime_type='application/json', response_json_schema=Invoice.model_json_schema())
    summary = dict(approved=sum(r['status']=='approved' for r in records),
                   unresolved=sum(r['status']!='approved' for r in records),
                   debt_rows=len(debt), balance=str(sum((r['balance'] for r in debt), Decimal('0'))),
                   live_gemini_verified=False, microsoft365_configured=False)
    (output/'local_verification.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
