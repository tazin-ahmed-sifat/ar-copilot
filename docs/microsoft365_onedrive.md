# Microsoft 365: OneDrive, Excel and email demonstration

This is what is built in a Brunel University account, which blocks creating SharePoint sites
and Teams teams. It replaces those with OneDrive for Business and an email to the builder's own
address. The SharePoint list and Teams post in [the design guide](microsoft365.md) remain unbuilt.

**Status: steps 1–4 built and run manually; the email step is not yet built.** No recurring
schedule is enabled, and the flow contacts no one but its owner.

## Flow: AR Copilot — Read aged debt

Instant cloud flow, run by hand. Connections: Excel Online (Business) and, for step 5,
Office 365 Outlook.

| Step | Action | Settings | Status |
| --- | --- | --- | --- |
| 1 | Manually trigger a flow | none | Built |
| 2 | Excel Online (Business): List rows present in a table | Location: OneDrive for Business. File: `/AR Copilot/aged-debt/ar_debt_2026-10-10.xlsx`. Table: `AgedDebt`. DateTime Format: ISO 8601 | Built |
| 3 | Filter array | Keeps rows with a positive balance whose bucket is not `current`, and drops the blank template row | Built |
| 4 | Create HTML table | Columns: Customer, Invoice, Due date, Balance (£), Days overdue, Bucket | Built |
| 5 | Office 365 Outlook: Send an email (V2) | To the owner's own Brunel address only; see below | Not built |

For step 3, the design guide's equivalent expression is
`@and(greater(float(item()?['balance']), 0), not(equals(item()?['bucket'], 'current')))`.
A blank row has no balance, so add `not(empty(item()?['document_number']))` if the flow's
filter handles blank rows that way.

### Observed run

A manual run against the workbook exported for 10 October 2026 produced one overdue row:
NC-0003, Cedar Automotive Ltd, due 11/05/2026, balance £5,218.20, 152 days overdue, bucket 91+.

The balance equals the invoice total, so no payment was applied. The demo ledger
(`data/payments.csv`) pays NC-0003 in full on 16 May 2026 (PAY-0003), which means this workbook
was exported before the ledger was imported. The flow read the table correctly. For a demo that
reflects payments, import the ledger in the app, export again, replace the file in OneDrive, and
rerun: NC-0003 then has a zero balance and drops out of the overdue list.

## Step 5: email to yourself (to build)

1. Add **Send an email (V2)** after Create HTML table.
2. **To**: type your own Brunel address. Do not use a dynamic value, a group or a distribution
   list. Check the address character by character before saving.
3. **Subject**: `AR Copilot: overdue receivables at 2026-10-10`.
4. **Body** (switch the editor to code view `</>`):
   ```
   <p><b>Overdue receivables at 2026-10-10</b></p>
   <p>@{length(body('Filter_array'))} overdue invoices. Fictional demo data.</p>
   @{body('Create_HTML_table')}
   ```
5. **Importance**: Normal. Leave CC, BCC and Reply To empty.
6. Save, then **Test → Manually → Run flow** once.

## Test checklist

- [ ] Before running, the To field holds only your own Brunel address and CC/BCC are empty.
- [ ] The run succeeds and sends exactly one email.
- [ ] In Outlook on the web, the email arrives in your own inbox with the subject above.
- [ ] The table renders with column headings and the same rows as the flow's Create HTML table
      output (with the current workbook: NC-0003, Cedar Automotive Ltd, £5,218.20, 152 days, 91+).
- [ ] Amounts show a £ sign and two decimals, and the due date reads as 11 May 2026.
- [ ] The flow has no recurrence trigger; it stays manual.

When the checklist passes, record the run date and change step 5's status to Built.

| Item | Value |
| --- | --- |
| Flow | AR Copilot — Read aged debt |
| Source workbook | OneDrive: AR Copilot/aged-debt/ar_debt_2026-10-10.xlsx |
| Email recipient | owner only |
| Email test run | not yet |

## Differences from the full design

- The workbook path is fixed rather than found as the latest file, so there is no staleness check
  yet. Add one before any schedule, as in step 4 of the design guide's overdue flow.
- There is no run key, so running it twice sends two emails. That is acceptable for a manual demo,
  not for a scheduled flow.
- An email to yourself replaces the Teams channel post.
