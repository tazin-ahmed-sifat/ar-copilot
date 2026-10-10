"""Review queue: check each extracted document against its PDF, correct it, then approve or reject."""
import json
import sqlite3
from collections import Counter

import pandas as pd
import streamlit as st

from ar_copilot.core import FIELDS, validate
from ar_copilot.ui import (FIELD_LABELS, STAMPS, amount, check_messages, display_date, heading_with_status,
                           open_store, show_pdf)

FILTERS = {'review': 'Needs review', 'approved': 'Approved', 'rejected': 'Rejected', 'all': 'All'}
ACTION_DONE = {'approve': 'approved', 'save': 'saved', 'reject': 'rejected'}


def queue_table(rows: list[dict]):
    frame = pd.DataFrame([{
        'Document': r.get('document_number') or r['filename'],
        'Customer': r.get('customer') or '–',
        'Total': amount(r.get('total')),
        'Due': display_date(r.get('due_date')),
        'Checks': _checks_label(r),
        'Status': STAMPS[r['status']][0],
    } for r in rows])
    colours = dict(STAMPS.values())
    return frame.style.map(lambda v: f'color: {colours[v]}; font-weight: 600', subset=['Status'])


def _checks_label(record: dict) -> str:
    if json.loads(record['extraction'])['error']:
        return 'Extraction failed'
    problems = len(validate(record))
    return 'Passed' if not problems else f'{problems} to fix'


def choose_document(visible: list[dict], rows: list[int]) -> dict:
    """The row clicked in the table wins; otherwise keep the last choice if it's still listed."""
    if rows and 0 <= rows[0] < len(visible):
        st.session_state['selected_document'] = visible[rows[0]]['id']
    wanted = st.session_state.get('selected_document')
    return next((r for r in visible if r['id'] == wanted), visible[0])


def next_in_queue(visible: list[dict], current_id: int) -> int | None:
    ids = [r['id'] for r in visible]
    position = ids.index(current_id)
    remaining = ids[position + 1:] + ids[:position]
    return remaining[0] if remaining else None


def show_checks(record: dict, extraction: dict) -> None:
    if extraction['error']:
        st.error(f"Extraction failed: {extraction['error']} Enter the fields from the PDF.")
    problems = check_messages(validate(record))
    if problems:
        st.warning('**Fix before approving**\n\n' + '\n'.join(f'- {p}' for p in problems))
    elif record['status'] == 'approved':
        st.success('Approved in the local register. Approved documents are locked.')
    else:
        st.success('All checks pass. A reviewer still has to approve it.')


def review_form(record: dict, extraction: dict) -> tuple[str | None, dict, str, str]:
    locked = record['status'] == 'approved'
    original = extraction['fields']
    with st.form(f'review-{record["id"]}', border=False):
        fields = {}
        left, right = st.columns(2)
        for index, field in enumerate(FIELDS):
            current = record.get(field) or ''
            extracted = original.get(field) or ''
            hint = f'Extracted as “{extracted or "blank"}”' if current != extracted else None
            column = left if index % 2 == 0 else right
            fields[field] = column.text_input(FIELD_LABELS[field], value=current, key=f'{record["id"]}-{field}',
                                              disabled=locked, help=hint)
        # Remembered across documents, so a reviewer types their name once per session.
        reviewer = st.text_input('Reviewer', value=st.session_state.get('reviewer_name', ''),
                                 key=f'{record["id"]}-reviewer', disabled=locked)
        reason = st.text_input('Reason', key=f'{record["id"]}-reason', disabled=locked,
                               placeholder='For example: checked against the PDF')
        approve, save, reject = st.columns(3)
        clicked = {
            'approve': approve.form_submit_button('Approve', type='primary', disabled=locked, width='stretch'),
            'save': save.form_submit_button('Save changes', disabled=locked, width='stretch'),
            'reject': reject.form_submit_button('Reject', disabled=locked, width='stretch'),
        }
    action = next((name for name, pressed in clicked.items() if pressed), None)
    if action:
        st.session_state['reviewer_name'] = reviewer
    return action, fields, reviewer, reason


def apply_decision(store, record: dict, visible: list[dict], action: str, fields: dict, reviewer: str,
                   reason: str) -> None:
    try:
        store.review(record['id'], fields, action, reviewer, reason)
    except sqlite3.IntegrityError:
        st.error('Duplicate approval: another approved document has the same supplier, customer, type and number.')
        return
    except ValueError as exc:
        st.error(str(exc))
        return
    name = fields.get('document_number') or record['filename']
    st.session_state['flash'] = f'{name} {ACTION_DONE[action]}.'
    if action != 'save':
        st.session_state['selected_document'] = next_in_queue(visible, record['id'])
    # A new table key clears the old row selection, which would point at a different document now.
    st.session_state['queue_version'] = st.session_state.get('queue_version', 0) + 1
    st.rerun()


def show_history(store, record: dict, extraction: dict) -> None:
    history = store.history(record['id'])
    with st.expander(f'Decision history ({len(history)})'):
        if history:
            st.dataframe([{'When (UTC)': h['created_at'], 'Reviewer': h['actor'], 'Action': h['action'],
                           'Reason': h['reason']} for h in history], hide_index=True, width='stretch')
        else:
            st.caption('No decisions yet.')
    with st.expander('Extracted text and original fields'):
        st.json(extraction['fields'])
        st.text(extraction['text'] or '(no text)')


store = open_store()
records = store.documents()
st.title('Review queue')
if not records:
    st.info('No documents yet. Load the 40 demo documents or upload PDFs from the sidebar.')
    st.stop()

counts = Counter(r['status'] for r in records)
counts['all'] = len(records)
choice = st.segmented_control('Show', list(FILTERS), format_func=lambda key: f'{FILTERS[key]} ({counts[key]})',
                              default='review', key='queue_filter', label_visibility='collapsed') or 'all'
visible = [r for r in records if choice == 'all' or r['status'] == choice]
if not visible:
    st.success('Nothing needs review.' if choice == 'review' else f'No {FILTERS[choice].lower()} documents.')
    st.stop()

table_key = f'queue-{choice}-{st.session_state.get("queue_version", 0)}'
queue = st.dataframe(queue_table(visible), key=table_key, on_select='rerun', selection_mode='single-cell', hide_index=True,
             height=min(38 + 35 * len(visible), 300), width='stretch',
             column_config={'Total': st.column_config.NumberColumn(format='£%.2f')})

record = choose_document(visible, [cell[0] for cell in queue.selection.cells])
extraction = json.loads(record['extraction'])
heading_with_status(record.get('document_number') or record['filename'], record['status'])
source = 'offline fixtures' if extraction['mode'] == 'demo' else f"Gemini ({extraction.get('model') or 'model unknown'})"
st.caption(f"{record['filename']}, extracted from {source} in {extraction['seconds']:.2f} s.")

pdf_column, form_column = st.columns([1, 1], gap='large')
with pdf_column:
    pdf = store.pdf(record['id'])
    show_pdf(pdf, record['filename'])
    st.download_button('Download PDF', pdf, record['filename'], 'application/pdf')
with form_column:
    show_checks(record, extraction)
    action, fields, reviewer, reason = review_form(record, extraction)
    if action:
        apply_decision(store, record, visible, action, fields, reviewer, reason)
    show_history(store, record, extraction)
