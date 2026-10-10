# Microsoft 365: OneDrive, Excel and email demonstration

This is what is built in a Brunel University account, which blocks creating SharePoint sites
and Teams teams. It replaces those with OneDrive for Business and an email to the builder's own
address. The SharePoint list and Teams post in [the design guide](microsoft365.md) remain unbuilt.

**Status: built and tested by hand on 10 October 2026.** The flow runs only when triggered
manually; no recurring schedule is enabled, and it emails no one but its owner.

## Flow: AR Copilot — Read aged debt

Instant cloud flow in the default Brunel environment, not shared with anyone. Connections, both
signed in as the flow owner: Excel Online (Business) and Office 365 Outlook.

| Step | Action | Settings as built |
| --- | --- | --- |
| 1 | Manually trigger a flow | none |
| 2 | Excel Online (Business): List rows present in a table | Location: OneDrive for Business (`me`). File: `/AR Copilot/aged-debt/ar_debt_2026-10-10.xlsx`. Table: `AgedDebt`. DateTime Format: ISO 8601. Pagination off |
| 3 | Filter array | From `outputs('List_rows_present_in_a_table')?['body/value']`, where expression below |
| 4 | Create HTML table | From `body('Filter_array')`; columns below |
| 5 | Office 365 Outlook: Send an email (V2) | To: the flow owner's own Brunel address, typed and resolved to their directory entry. No CC, BCC or Reply To. Importance: Normal |

Step 3's condition keeps rows that have a document number (dropping the blank template row), a
positive balance, and a bucket other than `current`:

```
@and(not(empty(item()?['document_number'])),
     greater(float(if(empty(item()?['balance']), '0', item()?['balance'])), 0),
     not(equals(item()?['bucket'], 'current')))
```

Step 4's columns:

| Header | Value |
| --- | --- |
| Customer | `item()?['customer']` |
| Invoice | `item()?['document_number']` |
| Due date | `formatDateTime(item()?['due_date'], 'dd/MM/yyyy')` |
| Balance (£) | `formatNumber(float(item()?['balance']), 'N2', 'en-GB')` |
| Days overdue | `item()?['days_overdue']` |
| Bucket | `item()?['bucket']` |

Step 5's subject is `AR Copilot: overdue receivables at 2026-10-10`. Its body is one line of
text, "Overdue receivables at 10 October 2026. Fictional demo data from AR Copilot.", followed by
the Create HTML table output, inserted from the dynamic content list.

Pagination is off, which caps step 2 at 256 rows. That is enough for the demo's 37 aged-debt rows;
switch it on (threshold 5000) before using a larger workbook.

## Test run, 10 October 2026

| Check | Result |
| --- | --- |
| Recipient before running | Code view showed a single To address, the owner's own; no CC or BCC fields |
| Run | One manual run at 20:35 GMT. All five steps succeeded; Send an email returned HTTP 200 |
| Email sent | Run history shows one message to the owner's address, with the subject above |
| Rendering in Outlook | Checked by the owner: intro line, bold column headings, and one row reading Cedar Automotive Ltd, NC-0003, 11/05/2026, 5,218.20, 152, 91+ |
| Schedule | None. The trigger is still manual |

Create HTML table produces a table with no borders or cell padding, so the columns sit close
together. It is readable as it stands. To space it out, a Compose step can wrap the output in
styled HTML, for example replacing `<table>` with `<table style="border-collapse:collapse">`
and adding `style="padding:4px 12px"` to `<td>` and `<th>`. That change hasn't been made or tested.

### Why the test email showed NC-0003 at full value

The balance equalled the invoice total, so no payment had been applied. The demo ledger
(`data/payments.csv`) pays NC-0003 in full on 16 May 2026 (PAY-0003); that workbook was exported
before the ledger was imported. The flow read the table correctly.

### Workbook refreshed, 10 October 2026

The demo ledger was imported into the app database and the workbook exported again. In the new
`ar_debt_2026-10-10.xlsx`, NC-0003 is paid in full (balance £0.00), so no invoice is overdue and
the next run would email a table with headings and no rows. The flow has not been run against it.

The old file was deleted and the new one uploaded, which gave it a new OneDrive item ID, and step 2
then failed with HTTP 404 (`itemNotFound`). Step 2 was pointed at the new file and the AgedDebt
table re-selected; the table ID is unchanged because the exporter writes it the same way each time.
To avoid this, upload a new export with the same name and choose **Replace**, which keeps the
item ID; deleting first and uploading again does not.

## Differences from the full design

- The workbook path is fixed rather than found as the latest file, so there is no staleness check.
  Add one before any schedule, as in step 4 of the design guide's overdue flow.
- There is no run key, so each run sends another email. That is fine for a manual demo, not for
  a scheduled flow.
- An email to the owner replaces the Teams channel post, and the SharePoint list import is not
  part of this flow.
