"""AR Copilot: review extracted invoices, age the approved debt, and time manual against assisted entry.

Start with `python -m streamlit run app.py`. The sidebar loads documents and payments;
the pages live in views/.
"""
import streamlit as st

from ar_copilot.extract import extract
from ar_copilot.payments import parse_payment_csv
from ar_copilot.store import Store
from ar_copilot.ui import apply_base_styles, data_dir, open_store

MAX_PDF_BYTES = 10 * 1024 * 1024
DEMO_DOCUMENTS = 40
MODES = {'demo': 'Offline fixtures', 'gemini': 'Gemini'}

st.set_page_config(page_title='AR Copilot', page_icon=':material/receipt_long:', layout='wide')
apply_base_styles()


def load_demo(store: Store) -> None:
    folder = data_dir()
    paths = sorted((folder / 'invoices').glob('*.pdf'))
    if len(paths) != DEMO_DOCUMENTS or not (folder / 'demo_fixtures.json').exists():
        st.sidebar.error('The demo dataset is missing. Run `python -m ar_copilot.generate`, then try again.')
        return
    before = len(store.documents())
    for path in paths:
        pdf = path.read_bytes()
        store.ingest(path.name, pdf, extract(pdf, 'demo', folder / 'demo_fixtures.json'))
    added = len(store.documents()) - before
    st.session_state['flash'] = f'Loaded {added} new demo documents.' if added else 'Demo documents were already loaded.'
    st.rerun()


def extract_uploads(store: Store, uploads, mode: str) -> None:
    known = {r['hash'] for r in store.documents()}
    for upload in uploads:
        pdf = upload.getvalue()
        if len(pdf) > MAX_PDF_BYTES:
            st.sidebar.error(f'{upload.name} is over 10 MB.')
            continue
        before = len(known)
        document_id = store.ingest(upload.name, pdf, extract(pdf, mode, data_dir() / 'demo_fixtures.json'))
        known = {r['hash'] for r in store.documents()}
        if len(known) == before:
            st.sidebar.info(f'{upload.name} is already in the queue.')
        else:
            st.sidebar.success(f'{upload.name} added to the review queue.')
            st.session_state['selected_document'] = document_id


def import_payments(store: Store, ledger) -> None:
    try:
        rows = parse_payment_csv(ledger.getvalue())
        inserted = store.import_payments(rows)
    except (ValueError, KeyError) as exc:
        st.sidebar.error(str(exc))
        return
    st.sidebar.success(f'{inserted} payments imported, {len(rows) - inserted} already on file.')


store = open_store()
navigation = st.navigation([
    st.Page('views/review.py', title='Review queue', icon=':material/fact_check:', default=True),
    st.Page('views/aged_debt.py', title='Aged debt', icon=':material/stacked_bar_chart:'),
    st.Page('views/timing.py', title='Time a document', icon=':material/timer:'),
])

with st.sidebar:
    st.subheader('Documents')
    if st.button('Load 40 offline demo documents', width='stretch'):
        load_demo(store)
    mode = st.radio('Extract uploads with', list(MODES), format_func=MODES.get, horizontal=True)
    if mode == 'demo':
        st.caption('Fixtures replay the known answer for the generated demo PDFs. They are not Gemini results.')
    else:
        st.caption("Gemini receives each PDF's text when you press Extract.")
    uploads = st.file_uploader('Invoice PDFs', type=['pdf'], accept_multiple_files=True, max_upload_size=10)
    if st.button('Extract', disabled=not uploads, width='stretch'):
        extract_uploads(store, uploads, mode)

    st.subheader('Payments')
    ledger = st.file_uploader('Import payment ledger CSV', type='csv', max_upload_size=2)
    st.caption('The demo ledger is data/payments.csv.')
    if st.button('Import payments', disabled=ledger is None, width='stretch'):
        import_payments(store, ledger)

    st.divider()
    st.caption('Fictional data for Northbridge Auto Components Ltd. Microsoft 365 is not connected.')

if 'flash' in st.session_state:
    st.toast(st.session_state.pop('flash'))
navigation.run()
