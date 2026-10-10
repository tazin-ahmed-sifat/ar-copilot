"""Excel exports: an aged-debt workbook for people and a flat document register for flows.

Table values are Decimal snapshots computed in Python. The Summary sheet adds SUMIF
formulas over the AgedDebt table so every total can be traced back to its rows, and
the Payments table lets excel/aged_debt.pq rebuild the buckets independently.
"""
import io
from datetime import date
from decimal import Decimal

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell

from .core import BUCKETS, FIELDS, parse_date

FONT = 'Arial'
INK = '#1C2A35'
MUTED = '#5A6670'
RULE = '#D3D9DD'
# One blue hue, light to dark, so older debt reads as heavier (validated as an ordinal ramp).
BUCKET_COLOURS = ['#86B6EF', '#3987E5', '#256ABF', '#184F95', '#0D366B']
BUCKET_LABELS = ['Current', '1–30 days', '31–60 days', '61–90 days', '91+ days']

GBP = '£#,##0.00;(£#,##0.00);"–"'
MONEY_COLUMNS = {'net', 'vat', 'total', 'payments', 'credits', 'balance', 'amount', *BUCKETS}
DATE_COLUMNS = {'invoice_date', 'due_date', 'payment_date'}
DEBT_COLUMNS = ['customer', 'document_number', 'due_date', 'total', 'payments', 'credits',
                'balance', 'days_overdue', 'bucket', *BUCKETS]
PAYMENT_COLUMNS = ['payment_id', 'invoice_number', 'customer', 'payment_date', 'amount']

README_LINES = [
    'Fictional prototype data. Microsoft 365 integrations are not configured.',
    'Currency GBP; VAT assumed at 20%. A balance due on the reporting date is current.',
    'Approved credit notes reduce the invoice they are linked to. Negative balances are customer credits and are kept.',
    'PostedReceivables is the approved document register. AgedDebt holds only transactions dated on or before the reporting date.',
    'Payments is the full imported ledger; payments after the reporting date are ignored by the aging rules.',
    'Summary totals are SUMIF formulas over AgedDebt. Other values are Python snapshots: re-export to change the date.',
    'Empty tables keep one blank row. Import only rows with status "approved" and a non-empty posting_key.',
]


class _Formats:
    """Every cell format in one place, built once per workbook."""

    def __init__(self, book: xlsxwriter.Workbook):
        self.header = book.add_format({'bold': True, 'font_color': '#FFFFFF', 'bg_color': INK,
                                       'bottom': 1, 'bottom_color': INK, 'valign': 'vcenter'})
        self.money = book.add_format({'num_format': GBP})
        self.date = book.add_format({'num_format': 'dd mmm yyyy', 'align': 'left'})
        self.title = book.add_format({'bold': True, 'font_size': 14, 'font_color': INK})
        self.note = book.add_format({'font_color': MUTED, 'italic': True})
        self.label = book.add_format({'bold': True})
        self.total_label = book.add_format({'bold': True, 'top': 1, 'top_color': INK})
        self.total_money = book.add_format({'bold': True, 'num_format': GBP, 'top': 1, 'top_color': INK})
        self.row_total = book.add_format({'bold': True, 'num_format': GBP})
        self.date_value = book.add_format({'num_format': 'dd mmm yyyy', 'align': 'left', 'bold': True})


def workbook(records: list[dict], debt: list[dict], reporting_date: date, kind: str = 'debt',
             payments: list[dict] = ()) -> bytes:
    """Build the 'posted' register or the full 'debt' workbook and return the .xlsx bytes."""
    output = io.BytesIO()
    book = xlsxwriter.Workbook(output, {
        'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
        'default_format_properties': {'font_name': FONT, 'font_size': 10},
    })
    formats = _Formats(book)
    if kind == 'debt':
        # Created first so it opens on top; it holds no Excel table, so table numbering is unchanged.
        summary = book.add_worksheet('Summary')
    _write_table(book, formats, 'PostedReceivables', _posted_rows(records), ['posting_key', 'source_hash', 'status', *FIELDS])
    if kind == 'debt':
        typed_debt = [dict(r, due_date=parse_date(r['due_date'])) for r in debt]
        _write_table(book, formats, 'AgedDebt', typed_debt, DEBT_COLUMNS)
        typed_payments = [dict(p, payment_date=parse_date(p['payment_date']), amount=Decimal(p['amount']))
                          for p in payments]
        _write_table(book, formats, 'Payments', typed_payments, PAYMENT_COLUMNS)
        unresolved = [dict(id=r['id'], filename=r['filename'], status=r['status'])
                      for r in records if r['status'] != 'approved']
        _write_table(book, formats, 'Unresolved', unresolved, ['id', 'filename', 'status'])
        _write_summary(book, summary, formats, debt, reporting_date, len(unresolved))
    _write_readme(book, formats, reporting_date)
    book.close()
    return output.getvalue()


def _posted_rows(records: list[dict]) -> list[dict]:
    rows = []
    for record in records:
        if record['status'] != 'approved':
            continue
        row = {field: record.get(field, '') for field in FIELDS}
        row.update({k: Decimal(row[k]) for k in ('net', 'vat', 'total')})
        row.update({k: parse_date(row[k]) for k in ('invoice_date', 'due_date')})
        row.update(posting_key=record['posting_key'], source_hash=record['hash'], status=record['status'])
        rows.append(row)
    return rows


def _excel_value(value):
    # Decimal becomes float only here, at the spreadsheet boundary.
    return float(value) if isinstance(value, Decimal) else value


def _column_width(column: str, rows: list[dict]) -> float:
    """Fit the longest cell, within limits that keep hashes from dominating the sheet."""
    if column in DATE_COLUMNS:
        return 13
    longest = max([len(column)] + [len(f'{row.get(column, ""):,.2f}' if column in MONEY_COLUMNS
                                       else str(row.get(column, ''))) for row in rows])
    padding = 5 if column in MONEY_COLUMNS else 3  # room for £ and parentheses on credits
    return min(max(longest + padding, 10), 44)


def _write_table(book, formats: _Formats, name: str, rows: list[dict], columns: list[str]) -> None:
    sheet = book.add_worksheet(name)
    sheet.freeze_panes(1, 0)
    sheet.set_row(0, 20)
    column_options = []
    for index, column in enumerate(columns):
        cell_format = formats.money if column in MONEY_COLUMNS else formats.date if column in DATE_COLUMNS else None
        sheet.set_column(index, index, _column_width(column, rows), cell_format)
        column_options.append({'header': column, 'header_format': formats.header, 'format': cell_format})
    options = {'name': name, 'style': 'Table Style Light 1', 'columns': column_options}
    if rows:
        options['data'] = [[_excel_value(row.get(c, '')) for c in columns] for row in rows]
    # Excel tables need at least one data row, so an empty table keeps a blank one;
    # flows must skip rows without a posting key.
    sheet.add_table(0, 0, max(len(rows), 1), len(columns) - 1, options)


def _write_summary(book, sheet, formats: _Formats, debt: list[dict], reporting_date: date,
                   unresolved_count: int) -> None:
    """Customer × bucket totals as SUMIF formulas over AgedDebt, with cached values and a chart."""
    sheet.hide_gridlines(2)
    sheet.set_column(0, 0, 30)
    sheet.set_column(1, len(BUCKETS) + 1, 15, formats.money)
    sheet.write(0, 0, 'Aged debt summary', formats.title)
    sheet.write(1, 0, 'Reporting date', formats.label)
    sheet.write_datetime(1, 1, reporting_date, formats.date_value)
    book.define_name('ReportingDate', '=Summary!$B$2')
    sheet.write(2, 0, 'Approved invoices after payments and allocated credits. '
                      'Totals are SUMIF formulas over the AgedDebt sheet.', formats.note)

    header_row = 4
    sheet.write_row(header_row, 0, ['Customer', *BUCKET_LABELS, 'Total'], formats.header)
    customers = sorted({r['customer'] for r in debt})
    if not customers:
        sheet.write(header_row + 1, 0, 'No approved invoices are outstanding at this date.', formats.note)
        return

    last_debt_row = len(debt) + 1  # AgedDebt data occupies rows 2..N+1 in Excel terms
    customer_range = f'AgedDebt!$A$2:$A${last_debt_row}'
    first_row = header_row + 1
    for offset, customer in enumerate(customers):
        row = first_row + offset
        sheet.write(row, 0, customer)
        criterion = xl_rowcol_to_cell(row, 0, col_abs=True)
        for index, bucket in enumerate(BUCKETS):
            column = xl_col_to_name(DEBT_COLUMNS.index(bucket))
            cached = sum((r[bucket] for r in debt if r['customer'] == customer), Decimal('0'))
            sheet.write_formula(row, index + 1,
                                f'=SUMIF({customer_range},{criterion},AgedDebt!${column}$2:${column}${last_debt_row})',
                                formats.money, float(cached))
        balance = sum((r['balance'] for r in debt if r['customer'] == customer), Decimal('0'))
        sheet.write_formula(row, len(BUCKETS) + 1,
                            f'=SUM({xl_rowcol_to_cell(row, 1)}:{xl_rowcol_to_cell(row, len(BUCKETS))})',
                            formats.row_total, float(balance))

    total_row = first_row + len(customers)
    sheet.write(total_row, 0, 'Total', formats.total_label)
    for column in range(1, len(BUCKETS) + 2):
        top, bottom = xl_rowcol_to_cell(first_row, column), xl_rowcol_to_cell(total_row - 1, column)
        key = BUCKETS[column - 1] if column <= len(BUCKETS) else 'balance'
        cached = sum((r[key] for r in debt), Decimal('0'))
        sheet.write_formula(total_row, column, f'=SUM({top}:{bottom})', formats.total_money, float(cached))

    sheet.write(total_row + 2, 0, 'Documents excluded (in review or rejected)', formats.label)
    sheet.write_formula(total_row + 2, 1, f'=COUNTA(Unresolved!$B$2:$B${max(unresolved_count, 1) + 1})',
                        None, unresolved_count)
    _insert_bucket_chart(book, sheet, header_row, total_row - 1, total_row + 4)


def _insert_bucket_chart(book, sheet, header_row: int, last_row: int, anchor_row: int) -> None:
    chart = book.add_chart({'type': 'bar', 'subtype': 'stacked'})
    first_row = header_row + 1
    for index, label in enumerate(BUCKET_LABELS):
        chart.add_series({
            'name': ['Summary', header_row, index + 1],
            'categories': ['Summary', first_row, 0, last_row, 0],
            'values': ['Summary', first_row, index + 1, last_row, index + 1],
            'fill': {'color': BUCKET_COLOURS[index]},
            # A thin white edge separates adjacent segments.
            'border': {'color': '#FFFFFF', 'width': 1.25},
            'gap': 70,
        })
    axis_font = {'name': FONT, 'size': 9, 'color': MUTED}
    chart.set_title({'name': 'Outstanding balance by customer and age',
                     'name_font': {'name': FONT, 'size': 11, 'bold': True, 'color': INK}})
    chart.set_x_axis({'num_format': '£#,##0', 'num_font': axis_font, 'line': {'none': True},
                      'major_gridlines': {'visible': True, 'line': {'color': RULE, 'width': 0.75}}})
    chart.set_y_axis({'reverse': True, 'num_font': {**axis_font, 'color': INK}, 'line': {'color': RULE},
                      'major_tick_mark': 'none'})
    chart.set_legend({'position': 'top', 'font': axis_font})
    chart.set_chartarea({'border': {'none': True}})
    chart.set_plotarea({'border': {'none': True}})
    chart.set_size({'width': 760, 'height': 320})
    sheet.insert_chart(anchor_row, 0, chart, {'x_offset': 2, 'y_offset': 4})


def _write_readme(book, formats: _Formats, reporting_date: date) -> None:
    sheet = book.add_worksheet('ReadMe')
    sheet.hide_gridlines(2)
    sheet.set_column(0, 0, 120)
    sheet.write(0, 0, 'About this workbook', formats.title)
    sheet.write(1, 0, f'Reporting date: {reporting_date:%d %B %Y}')
    for offset, line in enumerate(README_LINES, start=3):
        sheet.write(offset, 0, line)
