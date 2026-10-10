"""Shared Streamlit presentation: status stamps, plain-language check messages and PDF rendering."""
import html
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf as fitz
import streamlit as st

from . import config
from .core import FIELD_LABELS, parse_date  # FIELD_LABELS re-exported for the views
from .store import Store

# Status → (label, ink colour). Colours match the theme in .streamlit/config.toml.
STAMPS = {
    'review': ('Needs review', '#A86A12'),
    'approved': ('Approved', '#2E6A4E'),
    'rejected': ('Rejected', '#9E3A2B'),
}

CHECK_MESSAGES = {
    'document_type': 'Document type must be invoice or credit_note.',
    'supplier': 'Supplier is not Northbridge Auto Components Ltd.',
    'customer': 'Customer is not on the customer list.',
    'currency': 'Currency must be GBP.',
    'dates': 'A date cannot be read. Use 2026-10-10, 10/10/2026 or 10 Oct 2026.',
    'date_order': 'Due date is before the invoice date.',
    'amounts': 'Net, VAT and total must be amounts with at most two decimals.',
    'totals': 'Net plus VAT does not equal the total.',
    'vat_rate': 'VAT is not 20% of net.',
    'sign': 'Credit notes need negative amounts; invoices need positive ones.',
}

_CSS = """
<style>
  /* Amounts and durations line up in columns. */
  [data-testid="stMetricValue"], [data-testid="stDataFrame"], .ar-figures { font-variant-numeric: tabular-nums; }
  .ar-stamp {
    display: inline-block; padding: 0.1rem 0.55rem; border: 2px solid currentColor; border-radius: 0.25rem;
    outline: 1px solid currentColor; outline-offset: 2px; transform: rotate(-2deg);
    font-family: "IBM Plex Sans Condensed", sans-serif; font-weight: 600; font-size: 0.85rem; line-height: 1.4;
    letter-spacing: 0.02em; vertical-align: middle; margin-left: 0.6rem;
  }
  .ar-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem; margin: 0.25rem 0 0.1rem; }
  .ar-heading h3 { margin: 0; padding: 0; }
  .ar-muted { color: #5A6670; font-size: 0.9rem; }
</style>
"""


def apply_base_styles() -> None:
    st.html(_CSS)


def open_store() -> Store:
    # Resolved on every call so tests can point config.ROOT at a temporary dataset.
    return Store(config.ROOT / 'runtime' / 'ar.sqlite')


def data_dir() -> Path:
    return config.ROOT / 'data'


def stamp(status: str) -> str:
    label, colour = STAMPS.get(status, (status.title(), '#5A6670'))
    return f'<span class="ar-stamp" style="color:{colour}">{html.escape(label)}</span>'


def heading_with_stamp(title: str, status: str) -> None:
    st.html(f'<div class="ar-heading"><h3>{html.escape(title)}</h3>{stamp(status)}</div>')


def check_messages(codes: list[str]) -> list[str]:
    messages = []
    for code in codes:
        if code.startswith('missing:'):
            messages.append(f'{FIELD_LABELS.get(code[8:], code[8:])} is missing.')
        else:
            messages.append(CHECK_MESSAGES.get(code, code))
    return messages


def amount(value) -> float | None:
    """Display value for a stored amount string; None when it isn't a number yet."""
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def display_date(value: str | None) -> str:
    """Printed dates come in three formats; tables show one. Unreadable dates are shown as printed."""
    try:
        return f'{parse_date(value):%d %b %Y}'
    except ValueError:
        return value or '–'


def gbp(value: Decimal | float) -> str:
    return f'-£{-value:,.2f}' if value < 0 else f'£{value:,.2f}'


@st.cache_data(max_entries=40, show_spinner=False)
def pdf_page_images(pdf_bytes: bytes, zoom: float = 1.5) -> list[bytes]:
    """Render each page to PNG once; returning to the same document is instant."""
    with fitz.open(stream=pdf_bytes, filetype='pdf') as pdf:
        return [page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes('png') for page in pdf]


def show_pdf(pdf_bytes: bytes, filename: str) -> None:
    try:
        for number, image in enumerate(pdf_page_images(pdf_bytes), start=1):
            st.image(image, width='stretch', caption=None if number == 1 else f'Page {number}')
    except Exception:
        st.error(f'Could not render {Path(filename).name}. Download the original to check it.')
