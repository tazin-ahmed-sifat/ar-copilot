# Microsoft 365: OneDrive, Excel and email

The app itself doesn't connect to Microsoft 365. It exports workbooks, and a separate Power
Automate flow, built by hand in a Brunel University account, reads one of those workbooks from
OneDrive and emails the overdue invoices to the flow owner.

That account can't create SharePoint sites or Teams teams, so OneDrive and an email to yourself
are used instead.

## What was built

**Flow:** *AR Copilot — Read aged debt*. It is an instant (manually triggered) cloud flow in the
default environment and isn't shared with anyone. It uses two connections, Excel Online
(Business) and Office 365 Outlook, both signed in as the owner.

| Step | Action | Settings |
| --- | --- | --- |
| 1 | Manually trigger a flow | none |
| 2 | Excel Online (Business): List rows present in a table | OneDrive for Business, file `/AR Copilot/aged-debt/ar_debt_2026-10-10.xlsx`, table `AgedDebt`, DateTime format ISO 8601, pagination off |
| 3 | Filter array | expression below |
| 4 | Create HTML table | columns below |
| 5 | Office 365 Outlook: Send an email (V2) | To: the owner's own address only. No CC, BCC or Reply To |

Step 3 keeps rows that have a document number, a positive balance and a bucket other than
`current`. The document-number check drops the blank row the exporter writes into an empty table.

```
@and(not(empty(item()?['document_number'])),
     greater(float(if(empty(item()?['balance']), '0', item()?['balance'])), 0),
     not(equals(item()?['bucket'], 'current')))
```

Step 4 columns:

| Header | Value |
| --- | --- |
| Customer | `item()?['customer']` |
| Invoice | `item()?['document_number']` |
| Due date | `formatDateTime(item()?['due_date'], 'dd/MM/yyyy')` |
| Balance (£) | `formatNumber(float(item()?['balance']), 'N2', 'en-GB')` |
| Days overdue | `item()?['days_overdue']` |
| Bucket | `item()?['bucket']` |

The subject is `AR Copilot: overdue receivables at 2026-10-10`. The body is one line of text
saying the data is fictional, followed by the HTML table.

## Manual test (10 October 2026)

The project author ran this test in their own account. It isn't automated, and nobody else has
repeated it.

| Check | Result |
| --- | --- |
| Recipient | Code view showed one To address, the owner's own, and no CC or BCC |
| Run | One manual run. All five steps succeeded, and Send an email returned HTTP 200 |
| Email | Received by the author with the subject above. It rendered as an intro line and a table with one row: Cedar Automotive Ltd, NC-0003, 11/05/2026, 5,218.20, 152, 91+ |
| Schedule | None. The trigger is manual |

NC-0003 appeared at its full value because that workbook was exported before the demo payment
ledger was imported. The flow read the table correctly.

The workbook was then re-exported after importing the ledger. NC-0003 is now paid, so the
current file has no overdue rows. The flow has not been run against this new file.

Two things learned along the way:

- Deleting the old file and uploading the new one gave it a new OneDrive item ID, and step 2
  failed with HTTP 404 (`itemNotFound`) until the file was picked again. Uploading with the same
  name and choosing **Replace** keeps the ID.
- Create HTML table has no borders or padding, so the columns sit close together. It's readable,
  but styling it hasn't been tried.


## What the flow does not do

These are known gaps, not planned features:

- **No freshness check.** The file path is fixed, so the flow reads that file whatever date it
  holds.
- **No duplicate-send protection.** Every run sends another email.
- **No schedule.** It only runs when triggered by hand. Without the two checks above it
  shouldn't be scheduled.
- **256-row cap.** Pagination is off, so step 2 returns at most 256 rows. The demo has 37
  aged-debt rows.
- The posted receivables register download isn't used by any flow.

## Prepared but not installed

Two pieces of local code were written towards those gaps. Neither one is in the live flow.

- [`excel/validate_aged_debt.ts`](../excel/validate_aged_debt.ts) is a read-only Office Script.
  It checks that a workbook's `ReportingDate` matches a date the flow would pass in (meant to be
  today's London date) and that the `AgedDebt` table is well formed, then returns the overdue rows. It has only been run locally, against a mock of
  the Excel API.
- [`scripts/notification_journal.mjs`](../scripts/notification_journal.mjs) models a
  once-per-day-per-recipient send journal (Pending, Sent, Unknown). It is a reference for the
  state transitions only, and can't be deployed as a Power Automate action.

Both are covered by `tests/notification_safeguards.mjs`, which pytest runs when Node is on the
PATH (Node 24+ is needed to load the TypeScript directly; without Node the test is skipped). Passing those tests says nothing about how OneDrive, Excel Online or Outlook would
behave. Office Scripts may not even be enabled in the Brunel account.
