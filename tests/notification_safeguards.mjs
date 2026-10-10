// Execute the actual Office Script with a workbook API double; no cloud services or email.
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { stripTypeScriptTypes } from 'node:module';
import { runInNewContext } from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
import { reserve, recordOutcome } from '../scripts/notification_journal.mjs';

const source = readFileSync(new URL('../excel/validate_aged_debt.ts', import.meta.url), 'utf8');
const validate = runInNewContext(stripTypeScriptTypes(source) + '\nmain;');
const today = '2026-10-10';
const serial = iso => Date.parse(iso) / 86400000 + 25569;
const headers = ['customer', 'document_number', 'due_date', 'balance', 'days_overdue', 'bucket'];
const row = ['Fictional Customer', 'TEST-1', serial('2026-10-09'), 120.25, 1, '1–30'];
function workbook(rows = [row], date = serial(today), columnNames = headers) {
  return {
    getNamedItem(name) {
      assert.equal(name, 'ReportingDate');
      return { getRange: () => ({ getValue: () => date, getRowCount: () => 1, getColumnCount: () => 1 }) };
    },
    getTable(name) {
      assert.equal(name, 'AgedDebt');
      return { getHeaderRowRange: () => ({ getValues: () => [columnNames] }),
        getRangeBetweenHeaderAndTotal: () => ({ getValues: () => rows }) };
    }
  };
}

test('today is accepted and only overdue positive balances are returned', () => {
  const validRows = [row, ['Paid', 'TEST-2', serial('2026-10-09'), 0, 1, '1–30'],
    ['Credit', 'TEST-3', serial('2026-10-09'), -20, 1, '1–30'],
    ['Current', 'TEST-4', serial('2026-10-11'), 10, 0, 'current']];
  const valid = validate(workbook(validRows), today);
  assert.equal(valid.valid, true);
  assert.equal(valid.overdueRows.length, 1);
  assert.equal(valid.overdueRows[0].balance, 120.25);
});

test('stale and future reporting dates expose no balances', () => {
  for (const date of ['2026-10-09', '2026-10-11']) {
    const result = validate(workbook([row], serial(date)), today);
    assert.equal(result.valid, false);
    assert.equal(result.reason, 'stale_or_future_reporting_date');
    assert.equal(result.overdueRows.length, 0);
  }
});

test('missing or invalid workbook, date and headers stop without balances', () => {
  const cases = [workbook([row], '#VALUE!'), workbook([row], true), workbook([row], 60),
    workbook([row], serial(today) + .5), workbook([row], serial(today), ['customer']), {},
    { ...workbook(), getTable: () => { throw new Error('Missing table'); } },
    { ...workbook(), getNamedItem: () => { throw new Error('Missing named cell'); } }];
  for (const book of cases) {
    const result = validate(book, today);
    assert.equal(result.valid, false);
    assert.equal(result.overdueRows.length, 0);
  }
  assert.equal(validate(workbook(), '2026-02-30').valid, false);
});

test('duplicate invoice identities reject even paid rows', () => {
  const result = validate(workbook([row, [...row.slice(0, 3), 0, 1, '1–30']]), today);
  assert.equal(result.valid, false);
  assert.equal(result.overdueRows.length, 0);
});

test('invalid balances, dates, days and buckets reject the entire workbook', () => {
  for (const [column, value] of [[3, '120.25'], [3, NaN], [3, Infinity], [3, 1.001],
    [2, 'bad date'], [4, 2], [5, 'unknown'], [5, 'current'], [1, ''], [0, '']]) {
    const bad = [...row]; bad[column] = value;
    const result = validate(workbook([row, bad]), today);
    assert.equal(result.valid, false);
    assert.equal(result.overdueRows.length, 0);
  }
});

test('blank template row succeeds but partially blank row is invalid', () => {
  const result = validate(workbook([headers.map(() => '')]), today);
  assert.equal(result.valid, true);
  assert.equal(result.overdueRows.length, 0);
  assert.equal(validate(workbook([['', '', '', 0, '', '']]), today).valid, false);
});

test('pagination capacity stops at threshold, and validates over 256 rows below it', () => {
  const rows = Array.from({ length: 300 }, (_, i) => [row[0], `TEST-${i}`, ...row.slice(2)]);
  assert.equal(validate(workbook(rows), today, 5000).tableRows, 300);
  assert.equal(validate(workbook(rows), today, 300).reason, 'pagination_capacity');
  assert.equal(validate(workbook(rows), today, 100000).valid, false);
});

test('London calendar differs from UTC at midnight and respects winter time', () => {
  const london = instant => {
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London',
      year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(instant));
    const value = type => parts.find(part => part.type === type).value;
    return `${value('year')}-${value('month')}-${value('day')}`;
  };
  assert.equal(london('2026-10-09T23:30:00Z'), today);
  assert.equal(validate(workbook(), london('2026-10-09T23:30:00Z')).valid, true);
  assert.equal(london('2026-12-10T23:30:00Z'), '2026-12-10');
});

test('repeat runs stay blocked after journal reload for Pending, Sent and Unknown', () => {
  const directory = mkdtempSync(join(tmpdir(), 'ar-notification-test-'));
  const path = join(directory, 'journal.json');
  const recipient = 'owner@example.invalid'; // fictional; no mail transport exists
  try {
    for (const outcome of ['Pending', 'Sent', 'Unknown']) {
      const claim = reserve([], today, recipient, recipient, 'run-1');
      assert.equal(claim.allowed, true);
      const journal = outcome === 'Pending' ? claim.journal
        : recordOutcome(claim.journal, claim.key, 'run-1', outcome);
      writeFileSync(path, JSON.stringify(journal));
      const reloaded = JSON.parse(readFileSync(path, 'utf8'));
      assert.equal(reserve(reloaded, today, recipient.toUpperCase(), recipient, 'run-2').allowed, false);
    }
  } finally { rmSync(directory, { recursive: true }); }
});

test('ambiguous email failure retains reservation and wrong owner cannot finalize it', () => {
  const claim = reserve([], today, 'owner@example.invalid', 'owner@example.invalid', 'run-1');
  assert.throws(() => recordOutcome(claim.journal, claim.key, 'run-2', 'Sent'));
  const unknown = recordOutcome(claim.journal, claim.key, 'run-1', 'Unknown');
  assert.equal(reserve(unknown, today, 'owner@example.invalid', 'owner@example.invalid', 'run-3').allowed, false);
  assert.throws(() => reserve([], today, 'other@example.invalid', 'owner@example.invalid', 'run-1'));
  assert.throws(() => reserve([{ key: claim.key, state: 'broken', runId: 'run-1' }], today,
    'owner@example.invalid', 'owner@example.invalid', 'run-2'));
});
