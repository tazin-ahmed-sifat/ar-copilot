"""Aged debt: what each customer owes as at a reporting date, by how overdue it is."""
from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from ar_copilot.core import BUCKETS, DEMO_REPORTING_DATE, aged_debt
from ar_copilot.export import BUCKET_COLOURS, BUCKET_LABELS, workbook
from ar_copilot.ui import display_date, gbp, open_store

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def headline_figures(debt: list[dict]) -> None:
    outstanding = sum((r['balance'] for r in debt), Decimal('0'))
    overdue = sum((r['balance'] for r in debt if r['bucket'] != 'current' and r['balance'] > 0), Decimal('0'))
    oldest = sum((r['91+'] for r in debt), Decimal('0'))
    columns = st.columns(4)
    columns[0].metric('Outstanding', gbp(outstanding))
    columns[1].metric('Overdue', gbp(overdue))
    columns[2].metric('Over 90 days', gbp(oldest))
    columns[3].metric('Open invoices', sum(r['balance'] != 0 for r in debt))


def bucket_chart(debt: list[dict]) -> alt.Chart:
    """Stacked bars per customer, one blue step per bucket so older debt reads darker."""
    rows = [{'Customer': r['customer'], 'Age': label, 'Order': index, 'Balance': float(r[bucket])}
            for r in debt for index, (bucket, label) in enumerate(zip(BUCKETS, BUCKET_LABELS)) if r[bucket]]
    frame = pd.DataFrame(rows).groupby(['Customer', 'Age', 'Order'], as_index=False)['Balance'].sum()
    customers = sorted(frame['Customer'].unique())
    return (
        alt.Chart(frame)
        .mark_bar(stroke='#FFFFFF', strokeWidth=1.5, cornerRadius=2)
        .encode(
            y=alt.Y('Customer:N', sort=customers, title=None, axis=alt.Axis(labelLimit=220, ticks=False, domain=False)),
            x=alt.X('sum(Balance):Q', title=None, axis=alt.Axis(format=',.0f', labelExpr="'£' + datum.label", tickCount=6,
                                                               gridColor='#E3E7E9', domain=False, ticks=False)),
            color=alt.Color('Age:N', scale=alt.Scale(domain=BUCKET_LABELS, range=BUCKET_COLOURS),
                            legend=alt.Legend(orient='top', title=None, direction='horizontal')),
            order=alt.Order('Order:Q'),
            tooltip=[alt.Tooltip('Customer:N'), alt.Tooltip('Age:N'),
                     alt.Tooltip('sum(Balance):Q', title='Balance', format=',.2f')],
        )
        .properties(height=48 * len(customers) + 40)
        .configure_view(stroke=None)
        .configure_axis(labelColor='#1C2A35', labelFont='IBM Plex Sans', labelFontSize=12)
        .configure_legend(labelColor='#5A6670', labelFont='IBM Plex Sans', labelFontSize=12, symbolType='square')
    )


def invoice_table(debt: list[dict]) -> None:
    frame = pd.DataFrame([{
        'Customer': r['customer'], 'Invoice': r['document_number'], 'Due': display_date(r['due_date']),
        'Days overdue': r['days_overdue'], 'Age': BUCKET_LABELS[BUCKETS.index(r['bucket'])],
        'Total': float(r['total']), 'Paid': float(r['payments']), 'Credits': float(r['credits']),
        'Balance': float(r['balance']),
    } for r in debt])
    money = st.column_config.NumberColumn(format='£%.2f')
    st.dataframe(frame, hide_index=True, width='stretch',
                 column_config={'Total': money, 'Paid': money, 'Credits': money, 'Balance': money})


def excluded(records: list[dict], payments: list[dict]) -> None:
    unresolved = [r for r in records if r['status'] != 'approved']
    approved_invoices = {(r.get('customer'), r.get('document_number')) for r in records
                         if r['status'] == 'approved' and r.get('document_type') == 'invoice'}
    unmatched = [p for p in payments if (p['customer'], p['invoice_number']) not in approved_invoices]
    if unresolved:
        with st.expander(f'{len(unresolved)} documents not yet approved are left out'):
            st.dataframe([{'Document': r.get('document_number') or r['filename'], 'Status': r['status']}
                          for r in unresolved], hide_index=True, width='stretch')
    if unmatched:
        st.warning(f'{len(unmatched)} payments have no approved invoice to match and are left out of the balances.')
        st.dataframe(unmatched, hide_index=True, width='stretch')


store = open_store()
records, payments = store.documents(), store.payments()
st.title('Aged debt')
reporting_date = st.date_input('Reporting date', DEMO_REPORTING_DATE, format='DD/MM/YYYY', width=200)
debt = aged_debt(records, payments, reporting_date)

if debt:
    headline_figures(debt)
    st.subheader('Balance by customer and age')
    st.altair_chart(bucket_chart(debt), width='stretch')
    st.subheader('Invoices')
    invoice_table(debt)
else:
    st.info('No approved invoices on or before this date. Approve documents in the review queue first.')
excluded(records, payments)

st.subheader('Download')
st.caption(f'Workbooks are snapshots as at {reporting_date:%d %B %Y}.')
left, right = st.columns(2)
left.download_button('Aged debt workbook', workbook(records, debt, reporting_date, 'debt', payments),
                     f'ar_debt_{reporting_date.isoformat()}.xlsx', XLSX, width='stretch')
right.download_button('Posted register for Power Automate', workbook(records, debt, reporting_date, 'posted', payments),
                      f'ar_posted_{reporting_date.isoformat()}.xlsx', XLSX, width='stretch')
with st.expander(f'Payment ledger ({len(payments)})'):
    st.dataframe(payments, hide_index=True, width='stretch')
