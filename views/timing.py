"""Time how long a document takes to key by hand versus through extract-review-approve."""
import csv
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from ar_copilot.core import FIELDS
from ar_copilot.extract import extract
from ar_copilot.timing import (Timing, append_timing, count_corrections, count_field_errors, load_timings,
                               summarise)
from ar_copilot.ui import FIELD_LABELS, data_dir, show_pdf

METHOD_LABELS = {'manual': 'Key by hand', 'assisted': 'Extract, review, approve'}
MODE_LABELS = {'gemini': 'Gemini', 'demo': 'Offline fixtures'}

st.title('Time a document')
st.markdown(
    'Each document is timed from **Start** to **Finish**. Ground truth stays hidden until the row is saved, '
    'and only durations and error counts are written to `results/timings.csv`.'
)


@st.cache_data(show_spinner=False)
def load_truth(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding='utf-8') as handle:
        return {row['filename']: row for row in csv.DictReader(handle)}


def next_document(operator: str, method: str, truth: dict) -> str | None:
    """Random order, skipping documents this operator already timed with this method."""
    done = {t.filename for t in load_timings() if t.operator == operator and t.method == method and not t.practice}
    remaining = sorted(set(truth) - done)
    return random.choice(remaining) if remaining else None


DATA_DIR = data_dir()
if not (DATA_DIR / 'ground_truth.csv').exists():
    st.error('The fictional dataset is missing. Run `python -m ar_copilot.generate`, then reload this page.')
    st.stop()
truth = load_truth(DATA_DIR / 'ground_truth.csv')
session = st.session_state.setdefault('timing', {})

with st.container(border=True):
    left, middle, right = st.columns([2, 2, 1.4])
    operator = left.text_input('Operator', placeholder='Your name or initials', disabled=bool(session))
    method = middle.segmented_control('Method', list(METHOD_LABELS), format_func=METHOD_LABELS.get,
                                      default='manual', disabled=bool(session))
    mode = 'none'
    if method == 'assisted':
        mode = right.radio('Extraction', list(MODE_LABELS), format_func=MODE_LABELS.get, disabled=bool(session))
    practice = st.checkbox('Practice run (saved, but left out of the summary)', disabled=bool(session))
    if mode == 'demo':
        st.caption('Offline fixtures return the correct answer instantly, so these timings are labelled '
                   'separately and never used for a time-saved comparison.')

if not session:
    ready = bool(operator.strip()) and method is not None
    if st.button('Start next document', type='primary', disabled=not ready):
        filename = next_document(operator.strip(), method, truth)
        if filename is None:
            st.success('You have timed every document with this method.')
            st.stop()
        pdf = (DATA_DIR / 'invoices' / filename).read_bytes()
        started = time.perf_counter()
        extraction = {'fields': {}, 'seconds': 0.0, 'error': None}
        if method == 'assisted':
            with st.spinner('Extracting…'):
                extraction = extract(pdf, mode, DATA_DIR / 'demo_fixtures.json')
        session.update(filename=filename, started=started, extraction=extraction, operator=operator.strip(),
                       method=method, mode=mode, practice=practice)
        st.rerun()
else:
    filename, extraction = session['filename'], session['extraction']
    pdf_column, form_column = st.columns([1.1, 1], gap='large')
    with pdf_column:
        st.subheader(filename.removesuffix('.pdf'))
        show_pdf((DATA_DIR / 'invoices' / filename).read_bytes(), filename)
    with form_column:
        if extraction['error']:
            st.warning(f"Extraction failed ({extraction['error']}). Key the fields by hand; the clock is still running.")
        with st.form('timed-entry'):
            entered = {f: st.text_input(FIELD_LABELS[f], value=extraction['fields'].get(f) or '')
                       for f in FIELDS}
            decision = st.radio('Decision', ['accept', 'reject'], horizontal=True,
                                format_func={'accept': 'Accept', 'reject': 'Reject (anomaly)'}.get)
            finished = st.form_submit_button('Finish document', type='primary')
        if st.button('Abandon without saving'):
            st.session_state.pop('timing')
            st.rerun()
        if finished:
            seconds = time.perf_counter() - session['started']
            errors = count_field_errors(entered, truth[filename])
            append_timing(Timing(
                recorded_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                operator=session['operator'], method=session['method'], extraction_mode=session['mode'],
                filename=filename, seconds=round(seconds, 2), extraction_seconds=round(extraction['seconds'], 2),
                fields_corrected=count_corrections(extraction['fields'], entered) if session['method'] == 'assisted' else 0,
                field_errors=errors, decision=decision, practice=session['practice'],
            ))
            st.session_state.pop('timing')
            st.toast(f'Saved {filename}: {seconds:.1f} s, {errors} field error{"s" * (errors != 1)}.')
            st.rerun()

st.subheader('Recorded so far')
summary = summarise(load_timings())
if not summary['groups']:
    st.caption('No timed documents yet. Practice a couple first, then time a full set with each method.')
else:
    st.dataframe(
        [{'Method': key, 'Documents': g['documents'], 'Median s': g['seconds']['median'],
          'IQR s': f"{g['seconds']['q1']:.1f}–{g['seconds']['q3']:.1f}", 'Field errors': g['field_errors_total'],
          'Docs with errors': g['documents_with_errors']} for key, g in summary['groups'].items()],
        hide_index=True,
    )
    st.caption('Run `python scripts/summarize_timings.py` to write the committed summary in results/.')
