"""Application-generated Excel tables; no connector is configured or invoked."""
import io
from decimal import Decimal
import xlsxwriter
from .core import FIELDS, BUCKETS, parse_date

def workbook(records, debt, reporting_date, kind='debt'):
    output = io.BytesIO()
    book = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False})
    currency = book.add_format({'num_format': '#,##0.00'})
    date_format = book.add_format({'num_format': 'yyyy-mm-dd'})

    def table(name, rows, columns):
        sheet = book.add_worksheet(name)
        sheet.freeze_panes(1, 0)
        sheet.set_column(0, len(columns)-1, 23)
        if rows:
            data = [[r.get(c, '') for c in columns] for r in rows]
            for row in data:
                for i, value in enumerate(row):
                    if isinstance(value, Decimal):
                        row[i] = float(value)
            sheet.add_table(0, 0, len(rows), len(columns)-1,
                           {'name': name.replace(' ', ''), 'columns': [{'header': c} for c in columns], 'data': data})
            for j, col in enumerate(columns):
                if col in ('net', 'vat', 'total', 'payments', 'credits', 'balance', *BUCKETS):
                    sheet.set_column(j, j, 18, currency)
                if col in ('invoice_date', 'due_date'):
                    sheet.set_column(j, j, 18, date_format)
        else:
            # Excel tables require a data row. Keep a blank template row;
            # integration flows must filter out empty posting keys.
            sheet.add_table(0, 0, 1, len(columns)-1,
                            {'name': name.replace(' ', ''),
                             'columns': [{'header': c} for c in columns]})
    approved = []
    for r in records:
        if r['status'] == 'approved':
            row = {k: r.get(k, '') for k in FIELDS}
            for k in ('net', 'vat', 'total'):
                row[k] = Decimal(row[k])
            for k in ('invoice_date', 'due_date'):
                row[k] = parse_date(row[k])
            row.update(posting_key=r['posting_key'], source_hash=r['hash'], status=r['status'])
            approved.append(row)
    table('PostedReceivables', approved, ['posting_key', 'source_hash', 'status'] + FIELDS)
    if kind == 'debt':
        typed_debt = [dict(r, due_date=parse_date(r['due_date'])) for r in debt]
        table('AgedDebt', typed_debt, ['customer', 'document_number', 'due_date', 'total', 'payments', 'credits', 'balance', 'days_overdue', 'bucket']+BUCKETS)
        summaries = []
        for customer in sorted({r['customer'] for r in debt}):
            summaries.append(dict(customer=customer, **{b: sum((r[b] for r in debt if r['customer']==customer), Decimal('0')) for b in BUCKETS}))
        table('CustomerSummary', summaries, ['customer']+BUCKETS)
        table('Unresolved', [dict(id=r['id'], filename=r['filename'], status=r['status']) for r in records if r['status'] != 'approved'], ['id', 'filename', 'status'])
    sheet = book.add_worksheet('ReadMe')
    sheet.set_column(0, 0, 110)
    for i, text in enumerate(['FICTIONAL PROTOTYPE - Microsoft 365 integrations UNCONFIGURED',
                             f'Reporting date: {reporting_date.isoformat()}',
                             'GBP. VAT assumption 20%. Due today is current. Credits allocated to original invoice.',
                             'Negative balances are retained as customer credits; do not silently clamp them.',
                             'PostedReceivables is a document register; AgedDebt filters transactions as of reporting date.',
                             'Snapshot values computed with Decimal in Python; regenerate to change reporting date.',
                             'Empty tables contain a blank template row. Import only rows with status approved and a nonempty posting_key.']):
        sheet.write(i, 0, text)
    book.close()
    return output.getvalue()
