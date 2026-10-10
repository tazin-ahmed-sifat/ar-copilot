"""Shared Streamlit presentation: the status stamp and a few type rules the theme can't express."""
import html
from pathlib import Path

import pymupdf as fitz
import streamlit as st

# Status → (label, ink colour). Colours match the theme in .streamlit/config.toml.
STAMPS = {
    'review': ('Needs review', '#A86A12'),
    'approved': ('Approved', '#2E6A4E'),
    'rejected': ('Rejected', '#9E3A2B'),
}

_CSS = """
<style>
  /* Amounts and durations line up in columns. */
  [data-testid="stMetricValue"], [data-testid="stDataFrame"], .ar-figures { font-variant-numeric: tabular-nums; }
  .ar-stamp {
    display: inline-block; padding: 0.1rem 0.55rem; border: 2px solid currentColor; border-radius: 0.25rem;
    outline: 1px solid currentColor; outline-offset: 2px; transform: rotate(-2deg);
    font-family: "IBM Plex Sans Condensed", sans-serif; font-weight: 600; font-size: 0.85rem; line-height: 1.4;
    letter-spacing: 0.02em; background: transparent;
  }
  .ar-muted { color: #5A6670; }
</style>
"""


def apply_base_styles() -> None:
    st.html(_CSS)


def stamp(status: str) -> str:
    label, colour = STAMPS.get(status, (status.title(), '#5A6670'))
    return f'<span class="ar-stamp" style="color:{colour}">{html.escape(label)}</span>'


@st.cache_data(max_entries=40, show_spinner=False)
def pdf_page_images(pdf_bytes: bytes, zoom: float = 1.5) -> list[bytes]:
    """Render each page to PNG once; reviewing the same document again is instant."""
    with fitz.open(stream=pdf_bytes, filetype='pdf') as pdf:
        return [page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes('png') for page in pdf]


def show_pdf(pdf_bytes: bytes, filename: str) -> None:
    try:
        for number, image in enumerate(pdf_page_images(pdf_bytes), start=1):
            st.image(image, width='stretch', caption=None if number == 1 else f'Page {number}')
    except Exception:
        st.error(f'Could not render {Path(filename).name}. Download the original to check it.')
