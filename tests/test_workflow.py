import csv
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from tests.helpers import sheet_xml
from datetime import date, timedelta
from decimal import Decimal
import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest
from ar_copilot.core import validate, aged_debt, BUCKETS, FIELDS
from ar_copilot.generate import generate
from ar_copilot.extract import extract
from ar_copilot.store import Store
from ar_copilot.export import workbook

@pytest.fixture
def corpus(tmp_path):
    rows = generate(tmp_path/'data')
    return tmp_path/'data', rows

def test_reproducible_corpus_and_printed_truth(corpus, tmp_path):
    folder, rows = corpus
    other = tmp_path/'other'
    assert rows == generate(other)
    assert len(rows) == 40
    assert len({r['layout'] for r in rows}) == 3
    for row in rows:
        pdf = (folder/'invoices'/row['filename']).read_bytes()
        assert pdf == (other/'invoices'/row['filename']).read_bytes()
        text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
        assert 'FICTIONAL' in text
        for field in FIELDS:
            if row[field]:
                assert row[field] in text
        result = extract(pdf, fixtures=folder/'demo_fixtures.json')
        assert not result['error']
        assert result['fields'] == {f: row[f] for f in FIELDS}
    assert validate(rows[5]) == ['missing:po_number']
    assert validate(rows[8]) == ['totals']
    assert all(not validate(r) for i,r in enumerate(rows) if i not in (5,8))

@pytest.mark.parametrize('field,value,error', [('net','NaN','amounts'), ('net','1.001','amounts'),
    ('invoice_date','2026-02-30','dates'), ('vat','0.00','vat_rate'), ('total','-1.00','sign')])
def test_validation_mutations(corpus, field, value, error):
    record = dict(corpus[1][0]); record[field] = value
    assert error in validate(record)

def test_review_duplicate_and_payment_idempotency(corpus, tmp_path):
    folder, rows = corpus
    store = Store(tmp_path/'db.sqlite')
    pdf = (folder/'invoices'/rows[0]['filename']).read_bytes()
    result = extract(pdf, fixtures=folder/'demo_fixtures.json')
    document = store.ingest('first.pdf', pdf, result)
    assert store.ingest('renamed.pdf', pdf, result) == document
    store.review(document, result['fields'], 'save', 'Tester', 'Checked fields')
    store.review(document, result['fields'], 'approve', 'Tester', 'Source verified')
    assert len(store.history(document)) == 2
    with pytest.raises(ValueError):
        store.review(document, result['fields'], 'reject', 'Tester', 'Locked')
    second = store.ingest('different.pdf', pdf+b'\n', result)
    with pytest.raises(sqlite3.IntegrityError):
        store.review(second, result['fields'], 'approve', 'Tester', 'Same business identity')
    assert len(store.history(second)) == 0
    payment = dict(payment_id='P1', invoice_number=rows[0]['document_number'], customer=rows[0]['customer'], payment_date='2026-10-01', amount='10.00')
    store.import_payments([payment]); store.import_payments([payment])
    assert len(store.payments()) == 1
    with pytest.raises(ValueError):
        store.import_payments([dict(payment, amount='20.00')])

def test_missing_fields_and_unallocated_credit_block_posting(corpus, tmp_path):
    store = Store(tmp_path/'db.sqlite')
    folder, rows = corpus
    for index in (5, 8, 39):
        pdf = (folder/'invoices'/rows[index]['filename']).read_bytes()
        result = extract(pdf, fixtures=folder/'demo_fixtures.json')
        doc = store.ingest(str(index), pdf, result)
        with pytest.raises(ValueError):
            store.review(doc, result['fields'], 'approve', 'Tester', 'Attempt')
    assert all(r['status']=='review' for r in store.documents())

def test_aging_boundaries_and_as_of(corpus):
    base = dict(corpus[1][0], status='approved', invoice_date='2026-01-01', total='120.00')
    report = date(2026, 10, 10)
    records = [dict(base, document_number=str(i), due_date=(report-timedelta(days=days)).isoformat())
               for i,days in enumerate((-1,0,1,30,31,60,61,90,91))]
    assert [r['bucket'] for r in aged_debt(records, [], report)] == [BUCKETS[i] for i in (0,0,1,1,2,2,3,3,4)]
    credit = dict(base, document_type='credit_note', linked_invoice='0', total='-24.00', invoice_date='2026-10-09')
    payments = [dict(customer=base['customer'], invoice_number='0', amount='60.00', payment_date='2026-10-10'),
                dict(customer=base['customer'], invoice_number='0', amount='10.00', payment_date='2026-10-11')]
    result = aged_debt(records+[credit, dict(base, status='review')], payments, report)
    assert len(result) == 9
    assert result[0]['balance'] == Decimal('36.00')
    assert aged_debt([dict(base, invoice_date='2026-10-11')], [], report) == []

def test_export_real_excel_tables_and_formula_injection(corpus):
    record = dict(corpus[1][0], status='approved', posting_key='=CMD()', hash='hash')
    debt = aged_debt([record], [], date(2026,10,10))
    content = workbook([record], debt, date(2026,10,10))
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert 'xl/tables/table1.xml' in archive.namelist()
        assert b'PostedReceivables' in archive.read('xl/tables/table1.xml')
        assert b'<f>' not in sheet_xml(archive, 'PostedReceivables')
        assert b'=CMD()' in archive.read('xl/sharedStrings.xml')

def test_extraction_errors_are_reviewable():
    result = extract(b'not a pdf')
    assert result['error'] and not result['fields']

def test_corrections_and_credit_allocation(corpus, tmp_path):
    folder, rows = corpus
    store = Store(tmp_path/'db.sqlite')
    for index in (4, 39, 5):
        pdf = (folder/'invoices'/rows[index]['filename']).read_bytes()
        result = extract(pdf, fixtures=folder/'demo_fixtures.json')
        doc = store.ingest(str(index), pdf, result)
        fields = dict(result['fields'])
        if index == 5:
            fields['po_number'] = 'PO-VERIFIED-BY-REVIEWER'
            store.review(doc, fields, 'save', 'Tester', 'Documented business resolution')
            assert store.history(doc)[0]['before_fields'] != store.history(doc)[0]['after_fields']
        store.review(doc, fields, 'approve', 'Tester', 'Local test source verification')
    debt = aged_debt(store.documents(), [], date(2026,10,10))
    original = next(r for r in debt if r['document_number']=='NC-0005')
    assert original['credits'] == Decimal('-120.00')
    assert len(debt) == 2

def test_app_smoke(tmp_path, monkeypatch):
    from ar_copilot import config
    generate(tmp_path/'data')
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    assert not app.exception
    next(b for b in app.button if b.label == 'Load 40 offline demo documents').click().run(timeout=30)
    assert not app.exception
    store = Store(tmp_path/'runtime/ar.sqlite')
    assert len(store.documents()) == 40
    assert len(app.text_input) == 14  # twelve fields, reviewer and reason
    next(t for t in app.text_input if t.label == 'Reviewer').set_value('Test reviewer')
    next(t for t in app.text_input if t.label == 'Reason').set_value('Verified fictional source')
    next(b for b in app.button if b.label == 'Approve').click().run(timeout=30)
    assert not app.exception
    assert store.documents()[0]['status'] == 'approved'

def test_summary_sheet_totals_are_traceable_formulas(corpus):
    from xml.etree import ElementTree as ET
    from tests.helpers import NS
    records = [dict(r, status='approved', posting_key=r['document_number'], hash=r['document_number'])
               for r in corpus[1] if not validate(r) and r['document_type'] == 'invoice']
    debt = aged_debt(records, [], date(2026, 10, 10))
    with zipfile.ZipFile(io.BytesIO(workbook(records, debt, date(2026, 10, 10)))) as archive:
        summary = ET.fromstring(sheet_xml(archive, 'Summary'))
        assert b'<f>' not in sheet_xml(archive, 'AgedDebt')
    formulas = {c.attrib['r']: c for c in summary.iter(f"{{{NS['m']}}}c") if c.find('m:f', NS) is not None}
    customers = sorted({r['customer'] for r in debt})
    total_row = 6 + len(customers)
    assert formulas['B6'].find('m:f', NS).text == f'SUMIF(AgedDebt!$A$2:$A${len(debt) + 1},$A6,AgedDebt!$J$2:$J${len(debt) + 1})'
    grand_total = Decimal(formulas[f'G{total_row}'].find('m:v', NS).text)
    assert grand_total == sum(r['balance'] for r in debt)

@pytest.mark.parametrize('days, bucket', [(-5, 'current'), (0, 'current'), (1, '1–30'), (30, '1–30'),
                                          (31, '31–60'), (60, '31–60'), (61, '61–90'), (90, '61–90'), (91, '91+')])
def test_bucket_boundaries(days, bucket):
    from ar_copilot.core import bucket_for
    assert bucket_for(days) == bucket

def test_summary_excluded_count_is_not_formatted_as_money(corpus):
    import re
    from xml.etree import ElementTree as ET
    from tests.helpers import NS
    records = [dict(r, status='approved', posting_key=r['document_number'], hash=r['document_number'], id=i,
                    filename=r['filename']) for i, r in enumerate(corpus[1]) if not validate(r)]
    records.append(dict(corpus[1][8], status='review', id=99, filename='NC-0009.pdf', posting_key=None, hash='x'))
    debt = aged_debt(records, [], date(2026, 10, 10))
    with zipfile.ZipFile(io.BytesIO(workbook(records, debt, date(2026, 10, 10)))) as archive:
        summary = ET.fromstring(sheet_xml(archive, 'Summary'))
        styles = ET.fromstring(archive.read('xl/styles.xml'))
    count_cell = next(c for c in summary.iter(f"{{{NS['m']}}}c")
                      if (c.find('m:f', NS) is not None and c.find('m:f', NS).text.startswith('COUNTA')))
    xf = styles.find('m:cellXfs', NS)[int(count_cell.get('s', 0))]
    codes = {f.get('numFmtId'): f.get('formatCode') for f in styles.iter(f"{{{NS['m']}}}numFmt")}
    assert '£' not in (codes.get(xf.get('numFmtId')) or '')
