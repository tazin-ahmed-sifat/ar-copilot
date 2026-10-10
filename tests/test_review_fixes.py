"""Regression tests for bugs found in review of the redesigned app."""
import io
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ar_copilot import config
from ar_copilot.core import FIELDS
from ar_copilot.generate import generate
from ar_copilot.store import Store

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    rows = generate(tmp_path / 'data')
    monkeypatch.setattr(config, 'ROOT', tmp_path)
    store = Store(tmp_path / 'runtime' / 'ar.sqlite')
    first = rows[0]
    pdf = (tmp_path / 'data' / 'invoices' / first['filename']).read_bytes()
    document_id = store.ingest(first['filename'], pdf, dict(fields={f: first[f] for f in FIELDS}, text='',
                                                             error=None, mode='demo', seconds=0.0))
    store.review(document_id, {f: first[f] for f in FIELDS}, 'approve', 'QA', 'Checked')
    return store, first, tmp_path


def pay(store, invoice, amount):
    store.import_payments([dict(payment_id=f'P-{amount}', invoice_number=invoice['document_number'],
                                customer=invoice['customer'], payment_date='2026-10-01', amount=amount)])


def test_aged_debt_page_survives_all_balances_settled(seeded):
    store, invoice, _ = seeded
    pay(store, invoice, invoice['total'])
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.switch_page('views/aged_debt.py').run()
    assert not app.exception


def test_overpaid_invoice_is_not_an_open_invoice(seeded):
    store, invoice, _ = seeded
    pay(store, invoice, f"{float(invoice['total']) + 40:.2f}")
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.switch_page('views/aged_debt.py').run()
    assert not app.exception
    assert next(m for m in app.metric if m.label == 'Open invoices').value == '0'


class Upload(io.BytesIO):
    def __init__(self, name, content):
        super().__init__(content)
        self.name = name


def test_new_upload_is_shown_even_when_another_filter_is_active(seeded, monkeypatch):
    store, _, folder = seeded
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button_group[0].set_value('approved').run()
    second = folder / 'data' / 'invoices' / 'NC-0002.pdf'
    native = st.file_uploader
    monkeypatch.setattr(st, 'file_uploader', lambda label, *a, **k: [Upload(second.name, second.read_bytes())]
                        if label == 'Invoice PDFs' else native(label, *a, **k))
    app.run()
    next(b for b in app.button if b.label == 'Extract').click().run()
    assert not app.exception
    assert next(t for t in app.text_input if t.label == 'Document number').value == 'NC-0002'


def test_timing_save_confirmation_survives_the_rerun(seeded):
    generate(seeded[2] / 'runtime' / 'timing_data', seed=20261011)
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.switch_page('views/timing.py').run()
    app.text_input[0].set_value('tester').run()
    next(b for b in app.button if b.label == 'Start next document').click().run()
    next(b for b in app.button if b.label == 'Finish document').click().run()
    assert not app.exception
    assert any('Saved' in t.value for t in app.toast)


def test_failures_without_an_http_status_are_labelled_plainly():
    from scripts.publish_results import public_summary, render_markdown
    row = dict(filename='a.pdf', model='mock', error='mock failure', error_code=None, seconds=0.1,
               validation=[], matches={f: False for f in FIELDS})
    table = render_markdown(public_summary(dict(run_id='mock', details=[row]), {}))
    assert 'HTTP None' not in table and '1 × no HTTP status' in table


def test_audit_sees_inside_zip_based_files():
    import zipfile
    from scripts.audit_public_files import _leaks
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('xl/sharedStrings.xml', 'FAKE-SECRET-VALUE ' * 50)
    assert b'FAKE-SECRET-VALUE' not in buffer.getvalue()  # compressed, invisible to a raw scan
    assert _leaks(buffer.getvalue(), 'FAKE-SECRET-VALUE', [])


def test_audit_skips_office_lock_files():
    from scripts.audit_public_files import is_publishable
    assert not is_publishable(Path('excel/fixture/~$aged_debt_fixture.xlsx'))
    assert not is_publishable(Path('ar_copilot/__pycache__/core.cpython-312.pyc'))
    assert is_publishable(Path('excel/fixture/aged_debt_fixture.xlsx'))
