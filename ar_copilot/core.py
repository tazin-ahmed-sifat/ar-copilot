"""Independent business rules. Money stays Decimal until spreadsheet export."""
from datetime import datetime, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

FIELDS = ['document_type', 'supplier', 'customer', 'document_number', 'invoice_date',
          'due_date', 'po_number', 'currency', 'net', 'vat', 'total', 'linked_invoice']
SUPPLIER = 'Northbridge Auto Components Ltd'
CUSTOMERS = ['Alder Motors Ltd', 'Beacon Vehicle Works Ltd', 'Cedar Automotive Ltd',
             'Dunmere Mobility Ltd', 'Elmbridge Motor Company Ltd']
BUCKETS = ['current', '1–30', '31–60', '61–90', '91+']

def parse_date(value):
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            pass
    raise ValueError('Date must be ISO, UK dd/mm/yyyy or dd Mon yyyy')

def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount != amount.quantize(Decimal('.01')):
        raise ValueError('Amount must be finite with at most two decimal places')
    return amount

def validate(record):
    errors = []
    credit = record.get('document_type') == 'credit_note'
    required = [f for f in FIELDS if f != 'linked_invoice']
    if credit:
        required.remove('po_number')
        required.append('linked_invoice')
    for field in required:
        if not record.get(field):
            errors.append('missing:' + field)
    if record.get('document_type') not in ('invoice', 'credit_note'):
        errors.append('document_type')
    if record.get('supplier') != SUPPLIER:
        errors.append('supplier')
    if record.get('customer') not in CUSTOMERS:
        errors.append('customer')
    if record.get('currency') != 'GBP':
        errors.append('currency')
    try:
        if parse_date(record.get('due_date')) < parse_date(record.get('invoice_date')):
            errors.append('date_order')
    except ValueError:
        errors.append('dates')
    try:
        net, vat, total = [money(record.get(f)) for f in ('net', 'vat', 'total')]
        if net + vat != total:
            errors.append('totals')
        if (net * Decimal('.20')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) != vat:
            errors.append('vat_rate')
        if (credit and (net >= 0 or vat >= 0 or total >= 0)) or (not credit and min(net, vat, total) < 0):
            errors.append('sign')
    except (InvalidOperation, ValueError, TypeError):
        errors.append('amounts')
    return sorted(set(errors))

def aged_debt(records, payments, reporting_date):
    """Credits reduce their linked invoice; future transactions are excluded."""
    eligible = [r for r in records if r['status'] == 'approved'
                and parse_date(r['invoice_date']) <= reporting_date]
    invoices = [r for r in eligible if r['document_type'] == 'invoice']
    rows = []
    for invoice in invoices:
        number = invoice['document_number']
        paid = sum((money(p['amount']) for p in payments
                    if p['invoice_number'] == number and p['customer'] == invoice['customer']
                    and parse_date(p['payment_date']) <= reporting_date), Decimal('0'))
        credit = sum((money(r['total']) for r in eligible
                      if r['document_type'] == 'credit_note' and r['linked_invoice'] == number
                      and r['customer'] == invoice['customer']), Decimal('0'))
        balance = money(invoice['total']) - paid + credit
        days = (reporting_date - parse_date(invoice['due_date'])).days
        bucket = BUCKETS[0 if days <= 0 else 1 if days <= 30 else 2 if days <= 60 else 3 if days <= 90 else 4]
        rows.append(dict(customer=invoice['customer'], document_number=number,
                         due_date=parse_date(invoice['due_date']).isoformat(), total=money(invoice['total']),
                         payments=paid, credits=credit, balance=balance, days_overdue=max(0, days),
                         bucket=bucket, **{b: balance if b == bucket else Decimal('0') for b in BUCKETS}))
    return rows
