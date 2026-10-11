"""Human timing collection: no ledger writes and no ground-truth values displayed."""
import csv
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import streamlit as st
from ar_copilot import config
from ar_copilot.core import FIELDS, validate
from ar_copilot.extract import extract
from ar_copilot.timing import (Timing, PROTOCOL, PRACTICE_DOCUMENTS, append_timing, collection_plan,
                               count_corrections, count_field_errors, load_timings, summarise)
from ar_copilot.timing import timing_corpus_id
from ar_copilot.ui import FIELD_LABELS, show_pdf

st.title('Time a document')
st.markdown('The clock runs from **Start next document** through extraction wait, reading, review, '
            'correction and **Finish document** submission. Use an operator alias. Raw attempts stay '
            'local in `runtime/timings.csv`; this page does not approve or change the demo ledger.')
st.caption('Read docs/timing_procedure.md before collecting. Practice uses separate documents; '
           'measured trials follow 12 fixed tasks with six comparable pairs and alternating first method.')

@st.cache_data(show_spinner=False)
def load_truth(path: Path, corpus_id: str):
    with path.open(encoding='utf-8') as handle:
        return {row['filename']: row for row in csv.DictReader(handle)}

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')

DATA_DIR = config.ROOT / 'runtime' / 'timing_data'
if not (DATA_DIR / 'ground_truth.csv').exists():
    st.error('Prepare fresh timing documents first: python scripts/prepare_timing_documents.py. '
             'This creates a separate corpus without changing the demo ledger.')
    st.stop()
corpus_id = timing_corpus_id(DATA_DIR)
truth = load_truth(DATA_DIR / 'ground_truth.csv', corpus_id)
rows = load_timings()
session = st.session_state.setdefault('timing', {})

with st.container(border=True):
    operator = st.text_input('Operator alias', disabled=bool(session))
    study_id = st.text_input('Study code', value='pilot-1', disabled=bool(session))
    cohort = st.radio('Order group', ['A', 'B'], horizontal=True, disabled=bool(session))
    practice = st.checkbox('Practice run (excluded from results)', value=True, disabled=bool(session))
    practice_method = 'manual'
    practice_mode = 'none'
    if practice:
        practice_method = st.segmented_control('Practice method', ['manual', 'assisted'], default='manual', disabled=bool(session))
        if practice_method == 'assisted':
            practice_mode = 'demo' if st.checkbox('Replay offline demo fixtures for practice', disabled=bool(session)) else 'ollama'
    unseen = st.checkbox('I had not read the measured timing documents before this study', disabled=bool(session))

if not session:
    lost = [r for r in rows if r.operator == operator.strip() and r.status == 'in_progress']
    if lost:
        st.warning('An earlier attempt is unfinished. Its duration is unknown after a lost session; '
                   'record it as interrupted before continuing. Use one tab only.')
        if st.button('Record interrupted attempts'):
            for row in lost:
                append_timing(replace(row, recorded_at=stamp(), status='incomplete', failure_reason='interrupted',
                                      duration_known=False, field_errors=None, decision=''))
            st.rerun()
        st.stop()
    task = None
    if practice:
        if practice_method is not None:
            used = {r.filename for r in rows if r.operator == operator.strip() and r.practice
                    and r.corpus_id == corpus_id
                    and r.method == practice_method and r.extraction_mode == practice_mode}
            filename = next((f for f in PRACTICE_DOCUMENTS if f not in used), None)
            if filename:
                task = dict(filename=filename, method=practice_method, pair_id='', sequence=0,
                            layout=truth[filename]['layout'])
        mode = practice_mode
    else:
        plan = collection_plan(cohort)
        done = [r for r in rows if r.operator == operator.strip() and r.study_id == study_id.strip()
                and r.corpus_id == corpus_id
                and r.protocol == PROTOCOL]
        if any(r.cohort != cohort for r in done):
            st.error('Keep the same order group for this study.')
            st.stop()
        used = {r.sequence for r in done}
        task = next((t for t in plan if t['sequence'] not in used), None)
        # Do not show the next PDF or allow prior exposure through another study.
        if task and any(r.operator == operator.strip() and r.corpus_id == corpus_id and r.filename == task['filename'] for r in rows):
            st.error('This document was already attempted. Repeating it would introduce learning bias. '
                     'Do not restart this plan under a new study code.')
            st.stop()
        mode = 'ollama' if task and task['method'] == 'assisted' else 'none'
    if task:
        st.info(f"Next: {'key by hand' if task['method'] == 'manual' else mode + ' extraction and review'}"
                + (f" - task {task['sequence']}/12, layout {task['layout']}" if not practice else ' - practice'))
    else:
        st.caption('This practice method/set or the measured plan is finished.')
    ready = bool(operator.strip() and study_id.strip() and task) and (practice or unseen)
    if st.button('Start next document', type='primary', disabled=not ready):
        started = time.perf_counter()
        attempt = Timing(recorded_at=stamp(), operator=operator.strip(), method=task['method'],
                         extraction_mode=mode, filename=task['filename'], seconds=0, extraction_seconds=0,
                         fields_corrected=0, field_errors=None, decision='', practice=practice,
                         attempt_id=uuid4().hex, status='in_progress', duration_known=False,
                         study_id=study_id.strip(), cohort=cohort, pair_id=task['pair_id'],
                         sequence=task['sequence'], layout=task['layout'],
                         model=config.DEFAULT_MODEL if mode == 'ollama' else '', protocol='practice-v1' if practice else PROTOCOL,
                         corpus_id=corpus_id, extraction_finished=(task['method'] == 'manual'))
        append_timing(attempt) # record before file loading/API so a crash cannot erase the attempt
        session.update(attempt=attempt, started=started, extraction={'fields': {}, 'seconds': 0, 'error': None})
        pdf = (DATA_DIR / 'invoices' / attempt.filename).read_bytes()
        if attempt.method == 'assisted':
            with st.spinner('Extracting...'):
                session['extraction'] = extract(pdf, mode, DATA_DIR / 'demo_fixtures.json', single_attempt=True)
            result = session['extraction']
            attempt = replace(attempt, recorded_at=stamp(), extraction_seconds=result['seconds'],
                              extraction_finished=True,
                              model=result.get('model') or '', api_failed=bool(result['error']),
                              failure_reason=result.get('error_kind', 'legacy_unclassified') if result['error'] else '')
            session['attempt'] = attempt
            append_timing(attempt)
        st.rerun()
else:
    attempt, extraction = session['attempt'], session['extraction']
    pdf_column, form_column = st.columns([1.1, 1], gap='large')
    with pdf_column:
        st.subheader(attempt.filename.removesuffix('.pdf'))
        show_pdf((DATA_DIR / 'invoices' / attempt.filename).read_bytes(), attempt.filename)
    with form_column:
        if extraction['error']:
            st.warning('Extraction failed. You may finish by manual fallback or record an incomplete attempt; '
                       'the clock keeps running and the API failure remains recorded.')
        with st.form('timed-entry'):
            entered = {f: st.text_input(FIELD_LABELS[f], value=extraction['fields'].get(f) or '',
                                       key=f'{attempt.attempt_id}_{f}') for f in FIELDS}
            decision = st.radio('Decision', ['accept', 'reject'], horizontal=True,
                                format_func={'accept': 'Accept', 'reject': 'Reject (anomaly)'}.get)
            finished = st.form_submit_button('Finish document', type='primary')
            abandoned = st.form_submit_button('Record incomplete attempt')
        if finished or abandoned:
            errors = count_field_errors(entered, truth[attempt.filename]) if finished else None
            expected_decision = 'reject' if validate(truth[attempt.filename]) else 'accept'
            # End after submitted values and final decision have been processed, before CSV I/O.
            elapsed = time.perf_counter() - session['started']
            append_timing(replace(attempt, recorded_at=stamp(), seconds=elapsed,
                                 status='completed' if finished else 'incomplete', duration_known=True,
                                 field_errors=errors, decision=decision if finished else '',
                                 decision_error=(decision != expected_decision) if finished else None,
                                 fields_corrected=count_corrections(extraction['fields'], entered)
                                 if finished and attempt.method == 'assisted' and not attempt.api_failed else 0,
                                 failure_reason=attempt.failure_reason or ('abandoned' if abandoned else '')))
            st.session_state.pop('timing')
            st.session_state['flash'] = (f'Saved completed attempt: {elapsed:.1f} s, {errors} field errors.'
                                         if finished else 'Saved incomplete attempt; final scores unassessed.')
            st.rerun()

st.subheader('Recorded so far')
summary = summarise(load_timings())
if not summary['groups']:
    st.caption('No measured attempts yet. Practice is excluded.')
else:
    st.dataframe([{'Method': key, 'Attempts': g['documents'], 'Completed': g['completed'],
                   'Incomplete': g['incomplete'], 'Unresolved': g['unresolved'],
                   'Median completed s': g['seconds']['median'], 'Field errors': g['field_errors_total'],
                   'API failures': g['api_failures']} for key, g in summary['groups'].items()], hide_index=True)
    st.caption('When the plan is finished, run scripts/summarize_timings.py. Raw attempts stay in runtime/timings.csv.')
