"""Isolated app workflow checks; upload bytes supplied at the public widget boundary."""
import io
import zipfile
from pathlib import Path
from datetime import date
from xml.etree import ElementTree as ET
import pytest
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit.testing.v1 import AppTest
from ar_copilot import config
from ar_copilot.generate import generate
from ar_copilot.store import Store
from ar_copilot.payments import parse_payment_csv
from ar_copilot.export import workbook
from tests.helpers import sheet_xml

ACTION_BUTTONS = {'approve': 'Approve', 'save': 'Save changes', 'reject': 'Reject'}


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    generate(tmp_path/'data')
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=30)
    return app, Store(tmp_path/'runtime/ar.sqlite'), tmp_path

def button(app, label):
    return next(b for b in app.button if b.label == label)

def text_input(app, label):
    return next(t for t in app.text_input if t.label == label)

def open_document(app, document_id):
    app.session_state['selected_document'] = document_id
    app.run()

def decide(app, action, reason='Source checked'):
    text_input(app, 'Reviewer').set_value('Local QA')
    text_input(app, 'Reason').set_value(reason)
    button(app, ACTION_BUTTONS[action]).click().run()
    assert not app.exception

def serve_ledger(monkeypatch, content):
    native = st.file_uploader
    def uploaded(label, *args, **kwargs):
        if label == 'Import payment ledger CSV':
            return io.BytesIO(content)
        return native(label, *args, **kwargs)
    monkeypatch.setattr(st, 'file_uploader', uploaded)

def test_complete_demo_import_review_export(isolated_app, monkeypatch):
    app, store, folder = isolated_app
    captured = {}
    native_download = DeltaGenerator.download_button
    def capture(self, label, data, *args, **kwargs):
        captured[label] = data
        return native_download(self, label, data, *args, **kwargs)
    monkeypatch.setattr(DeltaGenerator, 'download_button', capture)
    app.run()
    assert button(app, 'Import payments').disabled
    button(app, 'Load 40 offline demo documents').click().run()
    assert not app.exception and len(store.documents()) == 40
    button(app, 'Load 40 offline demo documents').click().run()
    assert len(store.documents()) == 40
    serve_ledger(monkeypatch, (folder/'data/payments.csv').read_bytes())
    app.run(); button(app, 'Import payments').click().run()
    assert not app.exception and len(store.payments()) == 26
    button(app, 'Import payments').click().run()
    assert len(store.payments()) == 26

    decide(app, 'approve')
    assert store.documents()[0]['status'] == 'approved'
    open_document(app, 6)
    assert text_input(app, 'PO number').value == ''
    decide(app, 'approve')
    assert app.error and store.documents()[5]['status'] == 'review'
    text_input(app, 'PO number').set_value('PO-QA-RESOLUTION')
    decide(app, 'approve', 'Fictional QA documented PO resolution')
    assert store.documents()[5]['status'] == 'approved'
    open_document(app, 9)
    decide(app, 'reject', 'Inconsistent printed total')
    assert store.documents()[8]['status'] == 'rejected'

    app.button_group[0].set_value('all').run()
    open_document(app, 1)
    assert text_input(app, 'Document number').value == 'NC-0001'
    assert button(app, 'Approve').disabled

    app.switch_page('views/aged_debt.py').run()
    assert not app.exception
    for label in ('Posted register for Power Automate', 'Aged debt workbook'):
        with zipfile.ZipFile(io.BytesIO(captured[label])) as book:
            assert book.testzip() is None
            table = ET.fromstring(book.read('xl/tables/table1.xml'))
            assert table.attrib['name'] == 'PostedReceivables'
            assert table.attrib['ref'] == 'A1:O3'
            ns = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            sheet = ET.fromstring(sheet_xml(book, 'PostedReceivables'))
            assert sheet.find(".//m:c[@r='M2']/m:v",ns) is not None
            assert sheet.find(".//m:c[@r='H2']",ns).attrib.get('t') != 's'
            if label == 'Aged debt workbook':
                aged = ET.fromstring(sheet_xml(book, 'AgedDebt'))
                assert aged.find(".//m:c[@r='G2']/m:v",ns).text == '2066.89'
                assert aged.find(".//m:c[@r='G3']/m:v",ns).text == '0'
                assert ET.fromstring(book.read('xl/tables/table2.xml')).attrib['ref']=='A1:N3'

@pytest.mark.parametrize('content', [b'', b'payment_id\nP1\n', b'payment_id,payment_id\nP1,P1\n',
    b'payment_id,invoice_number,customer,payment_date,amount\n', b'\xff\xfe'])
def test_invalid_csv(content):
    with pytest.raises(ValueError):
        parse_payment_csv(content)

@pytest.mark.parametrize('amount', ['oops', 'NaN', 'Infinity', '-10', '1.001'])
def test_payment_invalid_amount_rolls_back(tmp_path, amount):
    store = Store(tmp_path/'db.sqlite')
    base = dict(payment_id='P1', invoice_number='NC-0001', customer='Alder Motors Ltd',
                payment_date='2026-10-01', amount='10.00')
    with pytest.raises(ValueError):
        store.import_payments([base, dict(base, payment_id='P2', amount=amount)])
    assert store.payments()==[]

def test_empty_exports_have_named_tables():
    for kind in ('posted','debt'):
        with zipfile.ZipFile(io.BytesIO(workbook([],[],date(2026,10,10),kind))) as book:
            assert b'PostedReceivables' in book.read('xl/tables/table1.xml')

def test_missing_demo_and_bad_payment_are_errors(isolated_app, monkeypatch):
    app, store, folder = isolated_app
    (folder/'data/demo_fixtures.json').rename(folder/'data/demo_fixtures.saved.json')
    app.run(); button(app,'Load 40 offline demo documents').click().run()
    assert not app.exception and app.error and not store.documents()
    serve_ledger(monkeypatch, b'payment_id,invoice_number,customer,payment_date,amount\nP1,NC-0001,Alder Motors Ltd,2026-10-01,oops\n')
    app.run(); button(app,'Import payments').click().run()
    assert not app.exception and app.error and not store.payments()
