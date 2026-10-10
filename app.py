"""Run with: .venv/Scripts/python -m streamlit run app.py"""
import json
import sqlite3
from datetime import date
from pathlib import Path
import pymupdf as fitz
import streamlit as st
from ar_copilot.core import FIELDS, validate, aged_debt
from ar_copilot.extract import extract
from ar_copilot.store import Store
from ar_copilot.export import workbook
from ar_copilot.payments import parse_payment_csv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'

@st.cache_data(max_entries=40)
def preview_pages(pdf_bytes):
    with fitz.open(stream=pdf_bytes, filetype='pdf') as pdf:
        return [page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes('png') for page in pdf]

st.set_page_config(page_title='AR Copilot', layout='wide')
st.title('AR Copilot')
st.caption('Northbridge Auto Components Ltd | FICTIONAL portfolio prototype | Microsoft 365: UNCONFIGURED')
store = Store(BASE_DIR / 'runtime/ar.sqlite')
mode = st.sidebar.selectbox('Extraction mode', ['demo', 'gemini'])
if mode == 'demo':
    st.warning('OFFLINE DEMO: exact generated fixtures, not measured Gemini extraction.')
else:
    st.info('Gemini mode sends extracted PDF text to Google when you click Process uploads.')
uploads = st.file_uploader('Upload fictional invoice PDFs', type=['pdf'], accept_multiple_files=True, max_upload_size=10)
if st.button('Process uploads', disabled=not uploads):
    for upload in uploads:
        pdf = upload.getvalue()
        if len(pdf) > 10 * 1024 * 1024:
            st.error('Maximum PDF size is 10 MB'); continue
        existing = next((r for r in store.documents() if r['pdf'] == pdf), None)
        if existing:
            st.info(f'{upload.name}: already stored as record {existing["id"]}'); continue
        result = extract(pdf, mode, DATA_DIR / 'demo_fixtures.json')
        record_id = store.ingest(upload.name, pdf, result)
        st.success(f'{upload.name}: record {record_id} awaits human review')
if st.sidebar.button('Load 40 offline demo documents'):
    paths = sorted((DATA_DIR / 'invoices').glob('*.pdf'))
    if len(paths) != 40 or not (DATA_DIR / 'demo_fixtures.json').exists():
        st.sidebar.error('Demo dataset missing or incomplete. Run python -m ar_copilot.generate.')
    else:
        before = len(store.documents())
        for path in paths:
            pdf = path.read_bytes()
            store.ingest(path.name, pdf, extract(pdf, 'demo', DATA_DIR / 'demo_fixtures.json'))
        st.session_state['demo_notice'] = f'Demo ready: {len(store.documents())-before} new documents; existing records preserved.'
        st.rerun()
if 'demo_notice' in st.session_state:
    st.sidebar.success(st.session_state.pop('demo_notice'))
payment_file = st.sidebar.file_uploader('Import payment ledger CSV', type='csv', max_upload_size=2)
st.sidebar.caption('Choose data/payments.csv for the fictional demo ledger.')
if st.sidebar.button('Import payments', disabled=payment_file is None):
    try:
        inserted = store.import_payments(parse_payment_csv(payment_file.getvalue()))
        st.sidebar.success(f'{inserted} new payments imported; existing payment IDs skipped.')
    except (ValueError, KeyError) as exc:
        st.sidebar.error(str(exc))
records = store.documents()
review_tab, debt_tab = st.tabs(['Document review', 'Aged debt and exports'])
with review_tab:
    if not records:
        st.info('Upload documents or load the offline demo to begin.')
    else:
        selected = st.selectbox('Document', [r['id'] for r in records],
                                format_func=lambda n: next(f'{r["filename"]} | {r["status"]}' for r in records if r['id']==n))
        record = next(r for r in records if r['id'] == selected)
        left, right = st.columns(2)
        with left:
            st.download_button('Download original PDF', record['pdf'], record['filename'], 'application/pdf')
            try:
                for number, image in enumerate(preview_pages(record['pdf']), start=1):
                    st.image(image, width='stretch', alt=f'{record["filename"]}, source page {number}')
            except Exception:
                st.error('PDF preview unavailable; download the original.')
        with right:
            extraction = json.loads(record['extraction'])
            st.caption(f'Origin: {extraction["mode"]} | Processing: {extraction["seconds"]:.3f} seconds')
            if extraction['error']:
                st.error(extraction['error'])
            st.write('Independent validation:', validate(record) or 'Passed; human approval still required')
            with st.expander('Original extracted text and fields'):
                st.json(extraction['fields']); st.text(extraction['text'])
            with st.form(f'review-{selected}'):
                fields = {f: st.text_input(f, value=record.get(f) or '', key=f'{selected}-{f}', disabled=record['status']=='approved') for f in FIELDS}
                actor = st.text_input('Reviewer name', key=f'{selected}-actor')
                reason = st.text_input('Correction / decision reason', key=f'{selected}-reason')
                action = st.selectbox('Action', ['save', 'approve', 'reject'], key=f'{selected}-action')
                if st.form_submit_button('Save decision', disabled=record['status']=='approved'):
                    try:
                        store.review(selected, fields, action, actor, reason)
                        st.rerun()
                    except (ValueError, sqlite3.IntegrityError) as exc:
                        st.error('Duplicate posting blocked' if isinstance(exc, sqlite3.IntegrityError) else str(exc))
            st.dataframe(store.history(selected))
with debt_tab:
    reporting_date = st.date_input('Reporting date', date(2026, 10, 10))
    debt = aged_debt(records, store.payments(), reporting_date)
    st.dataframe(debt)
    unresolved = [dict(id=r['id'], filename=r['filename'], status=r['status']) for r in records if r['status']!='approved']
    st.write('Unresolved / rejected documents excluded from receivables')
    st.dataframe(unresolved)
    st.write('Payment ledger'); st.dataframe(store.payments())
    approved_targets = {(r.get('customer'), r.get('document_number')) for r in records
                        if r['status']=='approved' and r.get('document_type')=='invoice'}
    unmatched = [p for p in store.payments() if (p['customer'],p['invoice_number']) not in approved_targets]
    if unmatched:
        st.warning('These payments have no approved matching invoice and are excluded from aged debt.')
        st.dataframe(unmatched)
    for kind, label in [('posted', 'Power Automate document table'), ('debt', 'Aged debt workbook')]:
        st.download_button(label, workbook(records, debt, reporting_date, kind, store.payments()), f'ar_{kind}.xlsx',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
