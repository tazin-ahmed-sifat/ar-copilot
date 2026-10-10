# Microsoft 365: OneDrive, Excel and email demonstration

This is what is built in a Brunel University account, which blocks creating SharePoint sites
and Teams teams. It replaces those with OneDrive for Business and an email to the builder's own
address. The SharePoint list and Teams post in [the design guide](microsoft365.md) remain unbuilt.

**Status: the original manual demonstration was tested by hand on 10 October 2026;
safeguards are prepared locally but not installed or verified in the account.** Browser setup
returned `No browser is available`, and browser discovery returned an empty list on the latest
inspection. No cloud action, test email or schedule change was performed in this session.
The sections through "Differences from the full design" record the earlier implementation.
Keep the flow manual. Before another email, install and verify the safeguards below; until then,
disable the send branch. The current live definition could not be re-inspected.

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
the remaining UI steps below explain how to enable it within the account's supported threshold.

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
- There is no run key, so each run sends another email. Manual triggering also needs duplicate
  protection before another send.
- An email to the owner replaces the Teams channel post, and the SharePoint list import is not
  part of this flow.

## Safeguards: remaining UI implementation

These are preparation, not claims about the live flow. OneDrive for Business, Excel Online
(Business) and Office 365 Outlook are the proposed surfaces. Only the latter two connections
were recorded in the original demonstration; OneDrive connector permissions, Office Scripts
and pagination settings must still be checked in this account. Do not create a SharePoint site
or Teams team, buy a license, or switch on a recurring trigger.

### 1. Keep sending disabled while editing

1. Open Power Automate, **My flows > AR Copilot — Read aged debt > Edit**. Save/export a backup
   of the current flow before edits. Keep **Manually trigger a flow**; do not add Recurrence.
2. In trigger **Settings**, turn **Concurrency control** on and set **Degree of parallelism: 1**.
   If unavailable, do not use the journal design below. Only this flow may write its journal;
   do not copy the flow or share the journal with another writer.
3. Wrap the send action in a condition controlled by Boolean `AllowTestEmail`, initialized to
   `false`. Leave it false for all no-send tests. All error branches end in **Terminate** without
   an email containing balances; do not add failure-notification emails for this task.
4. Verify the owner in the signed-in account profile, the Outlook connection, and the recipient's
   resolved Brunel directory entry. Store that exact own address in `VerifiedRecipient` locally
   in the flow, not in this repository. Use it as the only **To** value; clear **CC**, **BCC**,
   **Reply To** and any alternate sender. Do not infer the address from a display name or domain.

### 2. Resolve the file on every run and validate its contents

1. Add **Compose** named `LondonToday`:

   ```
   convertTimeZone(utcNow(), 'UTC', 'GMT Standard Time', 'yyyy-MM-dd')
   ```

   `GMT Standard Time` includes London's summer-time rules. Today for this inspection is
   **2026-10-10**; do not hard-code that date in the flow.
2. Add **Compose** named `WorkbookPath`:

   ```
   concat('/AR Copilot/aged-debt/ar_debt_', outputs('LondonToday'), '.xlsx')
   ```

3. Add OneDrive for Business **Get file metadata using path**, named `Resolve_workbook`, using
   `WorkbookPath`. Its failure/timeout branch must terminate without sending. A missing today's
   workbook must not fall back to an older file.
4. Every Excel File input uses the current **Id** from `Resolve_workbook`, inserted as dynamic
   content/custom value, not the old picker value. Set the table by custom value **AgedDebt**
   rather than retaining a table ID from a deleted workbook. Take the initial **ETag** as well;
   if the action does not expose a usable version identifier, keep sending disabled pending a
   reliable snapshot mechanism. Resolving a path, rather than trusting **Replace** to keep an
   ID, handles delete-and-upload too. Do not replace a file during a run.
5. In Excel Web, open a disposable copy of the export, go to **Automate > New Script**, and paste
   [validate_aged_debt.ts](../excel/validate_aged_debt.ts). Save as `Validate AR aged debt`.
   It is read-only. If Automate or **Run script** is unavailable in this account, stop here and
   leave the flow manual with sending disabled: checking a filename alone is insufficient.
6. Add Excel Online (Business) **Run script**, named `Validate_workbook`, File = resolved Id,
   Script = `Validate AR aged debt`, `londonToday` = LondonToday, `paginationThreshold` = the
   supported threshold chosen below. Add a condition:

   ```
   equals(body('Validate_workbook')?['result']?['valid'], true)
   ```

   Only its **Yes** branch may continue. Script failures/timeouts also terminate without sending.
   The script checks the actual named cell **ReportingDate** (`Summary!B2` in the exporter),
   rejects stale/future/invalid dates, missing tables/columns, malformed balances/dates, duplicate
   invoice identities, and inconsistent days/buckets. Invalid results contain no balances.
   It expects the exporter's 1900 Excel date system and numeric money/days; do not use hand-edited
   date-system variants. A completely blank template row is valid but supplies no overdue rows.

### 3. Enable pagination and reject incomplete reads

1. On **List rows present in a table**, File = resolved Id, Table = custom value `AgedDebt`,
   DateTime Format = **ISO 8601**. Clear **Top Count**, **Skip Count**, connector **Filter Query**
   and **Order By**; retrieve the full table before filtering.
2. Open action **Settings > Pagination**, switch it **On**, and try **Threshold 5000**. Save and
   confirm the designer accepts it in this account. If it rejects 5000, choose an accepted lower
   threshold and pass that same value to the validation script. Do not use 100000 or change billing.
3. After listing, require:

   ```
   equals(length(body('List_rows_present_in_a_table')?['value']),
          body('Validate_workbook')?['result']?['tableRows'])
   ```

   A mismatch terminates without sending. The script stops at or above the threshold, deliberately
   leaving headroom rather than assuming an exactly-full page is complete. Test more than 256 rows
   in a disposable workbook. Do not add a sending loop to work around a pagination limit.
4. Resolve `WorkbookPath` again after the reads and immediately before sending. Require both its
   Id and ETag to equal the initial values, and recompute LondonToday to require the same calendar
   day. Any missing/replaced/changed file or midnight rollover terminates without sending. No
   replacement should occur between this final check and send; these checks do not create a
   transactional snapshot across OneDrive and Outlook.
5. Use the script's **result > overdueRows** as the authoritative email rows. They are validated
   from one workbook read and contain positive balances with actual due dates before the reporting
   date. The paginated connector read checks coverage; do not email a separately cached array of
   unvalidated Excel values. For zero overdue rows, terminate without sending balances.

Microsoft documents the [Excel connector's 256-row default, delayed writes and concurrent-write
limitations](https://learn.microsoft.com/en-us/connectors/excelonlinebusiness/). Pagination is
[limited by flow performance profile](https://learn.microsoft.com/en-us/power-automate/limits-and-config),
so 5000 is a conservative proposed setting, not an observed Brunel setting. Office Scripts
[availability depends on account and admin settings](https://learn.microsoft.com/en-us/office/dev/scripts/develop/power-automate-integration).

### 4. Persistent duplicate guard: conditional OneDrive preparation

**Reliability is not verified. Keep the flow manual; do not enable sending merely because this
design or its local tests pass.** An Excel lookup followed by Add row has no unique constraint
and is not a dependable lock. Sent Items search is also not a lock. No usable SharePoint unique
list or another atomic service was established in this account.

A possible single-writer guard uses a separate owner-only OneDrive JSON journal. It must survive
workbook replacement and flow restarts. [notification_journal.mjs](../scripts/notification_journal.mjs)
is the executable local reference for the state transitions; it is **not** a deployable Power
Automate action or a connection to OneDrive. Translate the following actions only if the account
supports OneDrive content reads/updates and serialization can be enforced.

1. Outside the run, initialize `/AR Copilot/notification-state/overdue-journal.json`, owner-only.
   Use `[]` only for a disposable no-mail test journal or when run history confirms no earlier
   sends. Seed the production journal from prior sends: this guide records an email on 2026-10-10,
   so its verified date/recipient key must already be `Sent`. Preserve ambiguous prior attempts as
   `Unknown`; do not treat installation as permission to send the same day's balances again.
   Use the historical run ID from run history. Do not store the journal inside the replaceable
   aged-debt workbook. A missing, unreadable or
   malformed journal during a run terminates without sending; never recreate an empty one then.
2. **Compose** `RunKey` and `RunId`:

   ```
   concat('overdue|', outputs('LondonToday'), '|', toLower(trim(variables('VerifiedRecipient'))))
   workflow()?['run']?['name']
   ```

   Key only by reporting date and normalized recipient. Do not add a run ID, workbook ID, content
   hash or flow version to the key; those would allow another send for the same date/recipient.
3. After validation and the zero-row check, get journal metadata **using path** and content **using
   path**. Decode **File content** into JSON; inspect the action's actual output type before using
   `json(...)` (binary content may require `base64ToString(...['$content'])`). **Parse JSON** requires
   an array of objects with string `key`, nonempty string `runId`, and `state` restricted to
   `Pending`, `Sent` or `Unknown`. Use this schema (it also rejects empty keys/run IDs):

   ```json
   {
     "type": "array",
     "items": {
       "type": "object",
       "additionalProperties": false,
       "required": ["key", "state", "runId"],
       "properties": {
         "key": {"type": "string", "minLength": 1},
         "state": {"type": "string", "enum": ["Pending", "Sent", "Unknown"]},
         "runId": {"type": "string", "minLength": 1}
       }
     }
   }
   ```

   Add **Select** `Journal_keys`, From parsed journal, mapping in text mode `item()?['key']`.
   Require `equals(length(body('Journal_keys')), length(union(body('Journal_keys'), body('Journal_keys'))))`;
   otherwise terminate. This rejects duplicate keys. Filter the parsed
   array on `equals(item()?['key'], outputs('RunKey'))`. Any match terminates, regardless of state.
4. Create a **Compose** object `Pending_entry`, with `key` = RunKey, `state` = `Pending`, `runId`
   = RunId. Compose `Reserved_journal` as:

   ```
   union(body('Parse_journal'), createArray(outputs('Pending_entry')))
   ```

   OneDrive **Update file**, File = freshly resolved journal Id, content =
   `string(outputs('Reserved_journal'))`. Set retry policy **None**. If it fails/times out, stop
   without sending. A write may already have landed; never clear or overwrite a pending claim.
5. Read the journal again and parse it. Continue only if its entire content matches the proposed
   reservation and exactly one matching RunKey has `Pending` and this RunId. If anything is
   stale, inconsistent or inaccessible, stop. A readback alone does not prove storage consistency
   for future reads: verify it across a fresh run and connection/session before trusting it.
6. Perform the final workbook/version/date check, then enter the gated send branch. All later
   runs must honor the saved key. Crashing before send leaves `Pending`; that is intentional and
   blocks another attempt until the owner investigates.
7. On send success, update the owned Pending entry to `Sent`. On send failure, timeout or an
   ambiguous outcome, update it to `Unknown`. Use **Select** over the reserved journal to retain
   every other entry and replace only RunKey; never initialize a new journal. If the state update
   fails, leave the persisted `Pending` entry in place. Both states block subsequent sends.
8. Do not automatically delete a claim or make it eligible again. Reconcile Unknown/Pending
   against Outlook Sent Items and run history manually. Absence from Sent Items does not by itself
   prove the email was not submitted. This design favors suppressing a message over duplicating it.

The [OneDrive connector](https://learn.microsoft.com/en-us/connectors/onedriveforbusiness/)
documents file content and update actions, but provides no conditional unique-create contract for
this journal design. Serialization applies only to this flow, not another flow, manual edits or
another client. Storage behavior, restart persistence and competing-run behavior have not been
tested here. If those cannot be demonstrated, **reliable duplicate protection remains unavailable**:
retain the manual no-send gate and owner reconciliation, and do not schedule the flow.

### 5. Style the email and handle ambiguous send outcomes

Create HTML table from `body('Validate_workbook')?['result']?['overdueRows']`, retaining the original
custom columns. Add **Compose** `Styled_table`:

```
replace(replace(replace(body('Create_HTML_table'),
  '<table>', '<table style="border-collapse:collapse">'),
  '<th>', '<th style="border:1px solid #b8c0c8;padding:6px 12px;text-align:left">'),
  '<td>', '<td style="border:1px solid #b8c0c8;padding:6px 12px">')
```

Insert that output in the email body's HTML/code view. Keep table data HTML-encoded through
Create HTML table; do not concatenate customer text directly as HTML. Subject:
`concat('AR Copilot: overdue receivables at ', outputs('LondonToday'))`. Body introduction uses
the validated reporting date and identifies fictional data; it must not retain a hard-coded date.

On **Send an email (V2) > Settings**, set **Retry policy: None**. It runs only after every validation,
reservation, ownership, final version/date check and the `AllowTestEmail` gate succeeds. Add a
success branch for Sent and a failure/timeout branch for Unknown, ending with Terminate. Do not
resubmit a failed flow run as a resend. Do not send a second email from the error handler.
Microsoft explicitly warns that [Outlook 504 responses can occur after a send and default retries
can duplicate emails](https://learn.microsoft.com/en-us/connectors/office365/).

## Verification record, 10 October 2026

| Check | Actually verified in this session |
| --- | --- |
| Browser/live flow | Unavailable; runtime reported no browser, discovery returned `[]` |
| Local workbook | Read-only inspection of `output/ar_debt_2026-10-10.xlsx`: named ReportingDate points to Summary B2, date 2026-10-10, one blank AgedDebt template row, zero overdue rows; the Office Script accepted its values using a local API double |
| Stale-date test | Actual Office Script locally rejects yesterday and tomorrow and returns no balances |
| Invalid/missing workbook | Local tests reject missing named cell/table, invalid dates/headers/balances, duplicate identities and inconsistent aging |
| Pagination | Local test validates 300 rows and rejects rows at the configured cap; cloud setting and connector completeness not verified |
| London date | Local test covers a summer-time UTC/London midnight boundary and winter time; the Power Automate expression is not live-tested |
| Repeat-run test | Local JSON journal saved to disk and reloaded; Pending, Sent and Unknown each block the same date/recipient, including recipient case changes |
| Ambiguous failure | Local state-transition test retains Unknown and blocks another reservation; no Outlook failure was induced |
| Tests | `node --test tests/notification_safeguards.mjs`: 10 passed; full pytest suite: 87 passed. Node tests are included through `tests/test_notification_safeguards.py` (Node 24+) |
| Test email | None sent; recipient could not be re-verified |
| Cloud persistence/replacement/rendering | Not tested; local code is preparation only |
| Original assets | Local workbook, demo/review database and existing reports preserved by SHA-256 comparison |
| Schedule | No schedule action performed; original documented trigger is manual |

### Live acceptance tests still required (at most one test email)

Keep `AllowTestEmail=false` for every test except the single authorized send. Use disposable
workbook copies; preserve the original export and journal. Do not delete existing journal entries.

1. Put a yesterday-dated workbook under today's filename: validation must stop and Send must show
   **Skipped**. Repeat with an invalid ReportingDate and with today's file missing. Save the run IDs.
2. Use a valid current-day workbook with at least one fictional overdue positive balance. If the
   real demo export has no overdue rows, use a separate disposable test copy, not a ledger edit.
   Confirm current/zero/negative balances are excluded and the script/count/version checks pass.
3. With a separate disposable journal and email gate false, verify a Pending reservation survives
   a stopped run and a fresh run/session. Repeat: no new key, no send. Exercise Unknown and Sent
   state transitions without calling Outlook. Trigger two manual runs close together: only one may
   reserve. This is a test of account storage/serialization, not a substitute for a unique lock.
4. Replace the disposable workbook by deleting/uploading at the same path, then run: the newly
   resolved Id must be used. Replacing during validation must stop the version check. Confirm the
   journal remains intact. Verify pagination on more than 256 test rows below the accepted cap.
5. Only after persistent suppression and all no-send tests pass, re-verify the one own Brunel
   recipient and Send retry policy None. Use the production journal with a fresh eligible key;
   enable `AllowTestEmail` for **one manual run only**. If any existing Pending/Sent/Unknown key
   already covers today's owner address, do not bypass it: send no additional test email.
6. Immediately set `AllowTestEmail=false` again. Inspect the single email for borders/padding and
   correct date/rows, then repeat the flow with the gate false: duplicate guard must stop before
   Send. Record the actual run IDs and journal state, not just a green flow status.
7. For ambiguity, test an injected failed/timeout **Compose** in a disposable no-mail branch after
   reservation. Confirm Unknown blocks a fresh run; do not deliberately call Outlook repeatedly
   to induce a failure. Leave the trigger manual regardless of results: no recurring schedule is
   authorized in this task.
