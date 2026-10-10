"""Business rules for receivables: field validation and aged debt.

Money stays Decimal from parsing to the spreadsheet boundary, so totals never pick up
floating-point error.
"""
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

FIELDS = ['document_type', 'supplier', 'customer', 'document_number', 'invoice_date',
          'due_date', 'po_number', 'currency', 'net', 'vat', 'total', 'linked_invoice']
FIELD_LABELS = dict(zip(FIELDS, ['Document type', 'Supplier', 'Customer', 'Document number', 'Invoice date',
                                 'Due date', 'PO number', 'Currency', 'Net', 'VAT', 'Total', 'Linked invoice']))
SUPPLIER = 'Northbridge Auto Components Ltd'
CUSTOMERS = ['Alder Motors Ltd', 'Beacon Vehicle Works Ltd', 'Cedar Automotive Ltd',
             'Dunmere Mobility Ltd', 'Elmbridge Motor Company Ltd']
BUCKETS = ['current', '1–30', '31–60', '61–90', '91+']
# Upper bound in days overdue for each bucket after 'current'; anything beyond is '91+'.
BUCKET_LIMITS = [(30, '1–30'), (60, '31–60'), (90, '61–90')]
VAT_RATE = Decimal('0.20')
# The fictional corpus is dated around this day; the app, fixture and QA exports default to it.
DEMO_REPORTING_DATE = date(2026, 10, 10)
PENNY = Decimal('0.01')
DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d %b %Y')


def parse_date(value: str | None) -> date:
    """Accept the three printed formats in the corpus; all are unambiguous for UK dates."""
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except (ValueError, TypeError):
            pass
    raise ValueError('Date must be ISO, UK dd/mm/yyyy or dd Mon yyyy')


def money(value) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount != amount.quantize(PENNY):
        raise ValueError('Amount must be finite with at most two decimal places')
    return amount


def validate(record: dict) -> list[str]:
    """Return sorted rule codes that fail; an empty list means the document may be approved."""
    errors = _missing_fields(record) + _reference_errors(record) + _date_errors(record) + _amount_errors(record)
    return sorted(set(errors))


def _is_credit(record: dict) -> bool:
    return record.get('document_type') == 'credit_note'


def _missing_fields(record: dict) -> list[str]:
    # Credit notes need the invoice they correct instead of a purchase order.
    required = [f for f in FIELDS if f not in ('linked_invoice', 'po_number')]
    required.append('linked_invoice' if _is_credit(record) else 'po_number')
    return [f'missing:{field}' for field in required if not record.get(field)]


def _reference_errors(record: dict) -> list[str]:
    checks = {
        'document_type': record.get('document_type') in ('invoice', 'credit_note'),
        'supplier': record.get('supplier') == SUPPLIER,
        'customer': record.get('customer') in CUSTOMERS,
        'currency': record.get('currency') == 'GBP',
    }
    return [code for code, passed in checks.items() if not passed]


def _date_errors(record: dict) -> list[str]:
    try:
        due, issued = parse_date(record.get('due_date')), parse_date(record.get('invoice_date'))
    except ValueError:
        return ['dates']
    return ['date_order'] if due < issued else []


def _amount_errors(record: dict) -> list[str]:
    try:
        net, vat, total = (money(record.get(f)) for f in ('net', 'vat', 'total'))
    except (InvalidOperation, ValueError, TypeError):
        return ['amounts']
    errors = []
    if net + vat != total:
        errors.append('totals')
    if (net * VAT_RATE).quantize(PENNY, rounding=ROUND_HALF_UP) != vat:
        errors.append('vat_rate')
    if _is_credit(record):
        wrong_sign = net >= 0 or vat >= 0 or total >= 0
    else:
        wrong_sign = min(net, vat, total) < 0
    if wrong_sign:
        errors.append('sign')
    return errors


def bucket_for(days_overdue: int) -> str:
    """Due today or later is current; otherwise the first bucket whose limit covers the days."""
    if days_overdue <= 0:
        return 'current'
    for limit, bucket in BUCKET_LIMITS:
        if days_overdue <= limit:
            return bucket
    return '91+'


def aged_debt(records: list[dict], payments: list[dict], reporting_date: date) -> list[dict]:
    """One row per approved invoice, as at the reporting date.

    Only approved documents issued on or before the reporting date count. Payments and
    credit notes reduce an invoice only when they share its customer, and payments dated
    after the reporting date are ignored. Negative balances (overpayments) are kept.
    """
    eligible = [r for r in records
                if r['status'] == 'approved' and parse_date(r['invoice_date']) <= reporting_date]
    credits = [r for r in eligible if r['document_type'] == 'credit_note']
    return [_aged_row(invoice, payments, credits, reporting_date)
            for invoice in eligible if invoice['document_type'] == 'invoice']


def _aged_row(invoice: dict, payments: list[dict], credits: list[dict], reporting_date: date) -> dict:
    number, customer = invoice['document_number'], invoice['customer']
    paid = sum((money(p['amount']) for p in payments
                if p['invoice_number'] == number and p['customer'] == customer
                and parse_date(p['payment_date']) <= reporting_date), Decimal('0'))
    # Credit totals are negative, so adding them reduces the balance.
    credited = sum((money(c['total']) for c in credits
                    if c['linked_invoice'] == number and c['customer'] == customer), Decimal('0'))
    total = money(invoice['total'])
    balance = total - paid + credited
    due = parse_date(invoice['due_date'])
    days = (reporting_date - due).days
    bucket = bucket_for(days)
    return {
        'customer': customer,
        'document_number': number,
        'due_date': due.isoformat(),
        'total': total,
        'payments': paid,
        'credits': credited,
        'balance': balance,
        'days_overdue': max(0, days),
        'bucket': bucket,
        **{name: balance if name == bucket else Decimal('0') for name in BUCKETS},
    }
