"""SQLite transactions preserve immutable source bytes and an append-only review trail."""
import hashlib
import json
import sqlite3
from pathlib import Path
from .core import validate, parse_date

class Store:
    def __init__(self, path='runtime/ar.sqlite'):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY, hash TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
          pdf BLOB NOT NULL, extraction TEXT NOT NULL, fields TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'review', posting_key TEXT UNIQUE,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS history (
          id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL, actor TEXT NOT NULL,
          action TEXT NOT NULL, before_fields TEXT NOT NULL, after_fields TEXT NOT NULL,
          reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS payments (
          payment_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        ''')

    def ingest(self, filename, pdf, extraction):
        digest = hashlib.sha256(pdf).hexdigest()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO documents(hash,filename,pdf,extraction,fields) VALUES(?,?,?,?,?)',
                (digest, Path(filename).name, pdf, json.dumps(extraction), json.dumps(extraction['fields'])))
        return self.db.execute('SELECT id FROM documents WHERE hash=?', (digest,)).fetchone()[0]

    def documents(self):
        return [dict(row, **json.loads(row['fields'])) for row in self.db.execute('SELECT * FROM documents ORDER BY id')]

    def review(self, document_id, fields, action, actor, reason):
        if action not in ('save', 'approve', 'reject') or not actor.strip() or not reason.strip():
            raise ValueError('Provide reviewer name, reason and a valid action.')
        with self.db:
            row = self.db.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            if row is None:
                raise ValueError('Document not found')
            if row['status'] == 'approved':
                raise ValueError('Posted records are locked; a reversal workflow is required.')
            errors = validate(fields)
            posting_key = None
            if action == 'approve':
                if errors:
                    raise ValueError('Correct validation failures before approval: ' + ', '.join(errors))
                if fields['document_type'] == 'credit_note':
                    targets = [r for r in self.documents() if r['status'] == 'approved'
                               and r.get('document_type') == 'invoice'
                               and r.get('document_number') == fields['linked_invoice']
                               and r.get('customer') == fields['customer']]
                    if not targets:
                        raise ValueError('Credit requires an approved invoice for the same customer.')
                    if parse_date(fields['invoice_date']) < parse_date(targets[0]['invoice_date']):
                        raise ValueError('Credit cannot predate its invoice.')
                posting_key = '|'.join(fields[f].strip().casefold() for f in
                                       ('supplier', 'customer', 'document_type', 'document_number'))
            status = {'save': 'review', 'approve': 'approved', 'reject': 'rejected'}[action]
            self.db.execute('UPDATE documents SET fields=?,status=?,posting_key=? WHERE id=?',
                            (json.dumps(fields), status, posting_key, document_id))
            self.db.execute('INSERT INTO history(document_id,actor,action,before_fields,after_fields,reason) VALUES(?,?,?,?,?,?)',
                            (document_id, actor, action, row['fields'], json.dumps(fields), reason))

    def import_payments(self, rows):
        from .core import money
        from .core import CUSTOMERS
        from .payments import PAYMENT_FIELDS
        from decimal import InvalidOperation
        if not rows:
            raise ValueError('No payment rows supplied')
        inserted = 0
        with self.db:
            for number, source in enumerate(rows, start=2):
                if any(not isinstance(source.get(f), str) or not source[f].strip() for f in PAYMENT_FIELDS):
                    raise ValueError(f'CSV row {number}: all payment fields are required')
                row = {f: source[f].strip() for f in PAYMENT_FIELDS}
                try:
                    row['payment_date'] = parse_date(row['payment_date']).isoformat()
                    amount = money(row['amount'])
                    if amount <= 0:
                        raise ValueError('Payments must be positive')
                    row['amount'] = format(amount, '.2f')
                except (InvalidOperation, ValueError) as exc:
                    raise ValueError(f'CSV row {number}: invalid payment date or amount') from exc
                if row['customer'] not in CUSTOMERS:
                    raise ValueError(f'CSV row {number}: unknown fictional customer')
                existing = self.db.execute('SELECT payload FROM payments WHERE payment_id=?', (row['payment_id'],)).fetchone()
                payload = json.dumps(row, sort_keys=True)
                if existing and existing[0] != payload:
                    raise ValueError('Payment ID already exists with different values')
                cursor = self.db.execute('INSERT OR IGNORE INTO payments VALUES(?,?)', (row['payment_id'], payload))
                inserted += cursor.rowcount
        return inserted

    def payments(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM payments')]

    def history(self, document_id):
        return [dict(row) for row in self.db.execute('SELECT * FROM history WHERE document_id=? ORDER BY id', (document_id,))]
