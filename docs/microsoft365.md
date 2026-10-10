# Microsoft 365 build guide

**Status: not yet built.** Nothing in this repository connects to Microsoft 365. The app
exports workbooks; everything below is built by hand in SharePoint, Power Automate and Teams.
Change this line only after the test checklist at the end has passed, and record the evidence.

What you end up with:

1. A SharePoint library that receives the exported workbooks.
2. **Import posted receivables**: a flow that copies approved documents from each posted
   workbook into a SharePoint list, once per document however often it runs.
3. **Overdue summary**: a weekday flow that posts the overdue balances from the latest
   aged-debt workbook to a Teams channel, at most once per reporting date.

All connectors used (SharePoint, Excel Online (Business), Microsoft Teams, Office 365 Outlook)
are standard connectors. Build in a test site and a test channel first.

## 1. SharePoint

### Library

Create a document library **AR Exports** with two folders: `posted` and `aged-debt`.
The app names its downloads `ar_posted_<date>.xlsx` and `ar_debt_<date>.xlsx`; keep those names,
because the overdue flow reads the reporting date from the file name.

### List: Receivables

Create a list **Receivables**. Rename the built-in **Title** column to **PostingKey**; its internal
name stays `Title`, which is what filter queries use.

| Column | Type | Settings | Filled from (`PostedReceivables`) |
| --- | --- | --- | --- |
| PostingKey (Title) | Single line of text | Required; **Enforce unique values: Yes** | `posting_key` |
| SourceHash | Single line of text | Required | `source_hash` |
| DocumentType | Choice | `invoice`, `credit_note` | `document_type` |
| Supplier | Single line of text | | `supplier` |
| Customer | Single line of text | | `customer` |
| DocumentNumber | Single line of text | | `document_number` |
| InvoiceDate | Date and time | Date only | `invoice_date` |
| DueDate | Date and time | Date only | `due_date` |
| PONumber | Single line of text | | `po_number` |
| Currency | Single line of text | Default `GBP` | `currency` |
| Net | Number | 2 decimal places | `net` |
| VAT | Number | 2 decimal places | `vat` |
| Total | Number | 2 decimal places | `total` |
| LinkedInvoice | Single line of text | | `linked_invoice` |
| SourceWorkbook | Single line of text | | trigger file name |
| ImportedAt | Date and time | Include time | `utcNow()` |

The unique constraint on PostingKey is what actually prevents a double posting; the lookup in
the flow only makes the common case quiet.

### List: NotificationRuns

| Column | Type | Settings |
| --- | --- | --- |
| RunKey (Title) | Single line of text | Required; **Enforce unique values: Yes** |
| ReportingDate | Date and time | Date only |
| State | Choice | `Pending`, `Sent`, `Unknown` |
| MessageId | Single line of text | |
| SentAt | Date and time | Include time |

## 2. Flow: Import posted receivables

Automated cloud flow.

1. **Trigger**: SharePoint, *When a file is created (properties only)*. Site: your test site.
   Library: AR Exports. Folder: `/posted`.
2. **Delay**: 1 minute. A freshly uploaded workbook can be locked briefly, and the Excel
   connector fails on a locked file.
3. **List rows present in a table** (Excel Online (Business)).
   - Location: the site. Document library: AR Exports. File: `triggerOutputs()?['body/{Identifier}']`.
   - Table: `PostedReceivables`.
   - Filter Query: `status eq 'approved'`.
   - Advanced: **DateTime Format: ISO 8601** (the default returns Excel serial numbers).
   - Settings: **Pagination on**, threshold 5000. Without it only the first 256 rows come back.
4. **Filter array**, from `body('List_rows_present_in_a_table')?['value']`:
   `@not(empty(item()?['posting_key']))`. This drops the blank row an empty export keeps.
5. **Initialize variable** `Conflicts`, type Array, value `[]`.
6. **Apply to each** over `body('Filter_array')`. Settings: **Concurrency control on, degree 1**.
   1. **Get items** (SharePoint, Receivables).
      Filter Query: `Title eq '@{replace(items('Apply_to_each')?['posting_key'], '''', '''''')}'`.
      Top Count: 1.
   2. **Condition**: `length(body('Get_items')?['value'])` is equal to `0`.
      - **If yes → Create item** (Receivables), mapping the table above. Money columns:
        `float(items('Apply_to_each')?['net'])`, and the same for `vat` and `total`.
        SourceWorkbook: `triggerOutputs()?['body/{FilenameWithExtension}']`.
      - **If no → Condition**: `first(body('Get_items')?['value'])?['SourceHash']` is not equal to
        `items('Apply_to_each')?['source_hash']`. If yes, **Append to array variable** `Conflicts`:
        `items('Apply_to_each')?['posting_key']`. A matching hash means already imported: do nothing.
   3. On **Create item**, open *Configure run after* for a parallel branch that runs when it
      **has failed**: **Append to array variable** `Conflicts` with the posting key. A failure here
      usually means another run created the same key between the lookup and the create.
7. **Condition**: `length(variables('Conflicts'))` is greater than `0`.
   If yes, **Send an email (V2)** to the list owner: subject `Receivables import needs review`,
   body `join(variables('Conflicts'), '<br>')`. Never overwrite an existing item automatically.

## 3. Flow: Overdue summary

Scheduled cloud flow.

1. **Recurrence**: Frequency Week, Interval 1, On these days Monday–Friday, At these hours 9,
   At these minutes 0, Time zone *(UTC+00:00) Dublin, Edinburgh, Lisbon, London*.
2. **Get files (properties only)** (SharePoint, AR Exports). Filter Query:
   `startswith(FileLeafRef, 'ar_debt_')`. Order By: `Modified desc`. Top Count: 1.
3. **Compose** `ReportingDate`:
   `replace(replace(first(body('Get_files_(properties_only)')?['value'])?['{FilenameWithExtension}'], 'ar_debt_', ''), '.xlsx', '')`
4. **Condition**: `outputs('ReportingDate')` is not equal to
   `convertFromUtc(utcNow(), 'GMT Standard Time', 'yyyy-MM-dd')`.
   If yes, email the owner `No aged-debt workbook for today; nothing was posted.` and
   **Terminate** (Succeeded). Posting a stale balance is worse than posting nothing.
5. **Compose** `RunKey`: `concat('overdue|', outputs('ReportingDate'), '|<channel id>|v1')`.
6. **Get items** (NotificationRuns). Filter Query: `Title eq '@{outputs('RunKey')}'`.
   **Condition**: `length(body('Get_items')?['value'])` greater than `0` → **Terminate** (Succeeded).
   Any existing row, Sent or Unknown, means this date was already handled.
7. **Create item** (NotificationRuns): RunKey, ReportingDate, State `Pending`. If this fails, another
   run holds the key: add a *run after has failed* branch that terminates.
8. **List rows present in a table**: file `first(body('Get_files_(properties_only)')?['value'])?['{Identifier}']`,
   table `AgedDebt`, DateTime Format ISO 8601, pagination on.
9. **Filter array**: `@and(greater(float(item()?['balance']), 0), not(equals(item()?['bucket'], 'current')))`.
   Overdue only; customer credits (negative balances) are left out of the chase list.
10. **Select** `OverdueRows` from the filtered rows, mapping Customer `item()?['customer']`,
    Invoice `item()?['document_number']`, Due `item()?['due_date']`, Days `item()?['days_overdue']`,
    Bucket `item()?['bucket']`, Balance `formatNumber(float(item()?['balance']), 'C2', 'en-GB')`.
11. **Select** `Balances` (text mode): `float(item()?['balance'])`.
    **Compose** `OverdueTotal`:
    `xpath(xml(json(concat('{"r":{"v":', string(body('Balances')), '}}'))), 'sum(/r/v)')`.
    (Power Automate has no array sum; this is the standard workaround.)
12. **Create HTML table** from `sort(body('OverdueRows'), 'Customer')`.
13. **Post message in a chat or channel** (Teams). Post as: Flow bot. Post in: Channel.
    Team and Channel: the test channel. Message:
    ```
    <p><b>Overdue receivables at @{outputs('ReportingDate')}</b></p>
    <p>@{length(body('Filter_array'))} invoices, @{formatNumber(float(outputs('OverdueTotal')), 'C2', 'en-GB')} overdue.</p>
    @{body('Create_HTML_table')}
    <p>Source: @{first(body('Get_files_(properties_only)')?['value'])?['{Link}']}</p>
    ```
14. **Update item** (NotificationRuns): State `Sent`, MessageId `body('Post_message_in_a_chat_or_channel')?['id']`,
    SentAt `utcNow()`.
15. Add a branch after step 13 that runs when it **has failed** or **has timed out**: Update item,
    State `Unknown`, then email the owner. Do not retry: a timeout can still mean the message was
    posted, and Teams has no exactly-once delivery. Check the channel, then set State by hand.

## 4. Test checklist

Use the fictional demo data. Export after approving documents in the app, and upload
by hand into the right folder.

Import posted receivables

- [ ] Upload a posted workbook: the list gains one item per approved row; the count matches the
      `PostedReceivables` table.
- [ ] Spot-check three items: dates are the same calendar day as in Excel (no time-zone shift);
      Net + VAT = Total; the credit note has negative amounts and LinkedInvoice set.
- [ ] Upload the same workbook again under a new name: no new items, no conflict email.
- [ ] Change one `total` in a copy, upload it: one conflict email naming that posting key; the
      existing item is unchanged.
- [ ] Upload a posted workbook exported before any approval (blank template row): no items created.
- [ ] Upload two workbooks at once: no duplicate PostingKey items (the unique constraint holds).

Overdue summary

- [ ] Export an aged-debt workbook dated today, upload it, run the flow manually: one channel post.
      Its total equals the sum of AgedDebt balances that are positive and not `current`.
- [ ] Run it again: no second post; NotificationRuns still has one row for today.
- [ ] Rename the latest workbook to yesterday's date and run: stale-workbook email, no post.
- [ ] Point step 13 at a channel the connection can't post to and run with a new date: State
      becomes `Unknown`, the owner is emailed, nothing retries.
- [ ] Let the schedule fire once on a weekday at 09:00 London time, including once after a clock
      change.

When everything passes, record the flow names, run IDs, site and list URLs, channel, owner and
test date below, then change the status line at the top.

| Item | Value |
| --- | --- |
| Import flow | not built |
| Overdue flow | not built |
| SharePoint site / lists | not built |
| Teams channel | not built |
| Tested on | – |
