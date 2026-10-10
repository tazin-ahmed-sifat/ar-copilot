"""Parse an uploaded payment ledger CSV into rows for Store.import_payments."""
import csv
import io

PAYMENT_FIELDS = ['payment_id', 'invoice_number', 'customer', 'payment_date', 'amount']

def parse_payment_csv(content: bytes) -> list[dict]:
    """Reject malformed files up front so a bad upload never half-imports."""
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Payment CSV must use UTF-8 encoding.') from exc
    reader = csv.DictReader(io.StringIO(text), strict=True)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Payment CSV needs unique column headers.')
    missing = set(PAYMENT_FIELDS) - set(reader.fieldnames)
    if missing:
        raise ValueError('Missing payment columns: ' + ', '.join(sorted(missing)))
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise ValueError('Malformed payment CSV.') from exc
    if not rows:
        raise ValueError('Payment CSV contains no payment rows.')
    if any(None in row for row in rows):
        raise ValueError('Payment CSV has rows with too many columns.')
    return [{field: row[field] for field in PAYMENT_FIELDS} for row in rows]
