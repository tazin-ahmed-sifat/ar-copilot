# AR Copilot

A local Python learning prototype for **fictional** Northbridge Auto Components Ltd and five fictional vehicle manufacturers. No production accounting, real customer data, publishing or messaging is configured.

Public repository users: generated datasets, review databases, raw reports and exports are intentionally local and excluded from Git. Create a virtual environment, install requirements, and generate data using the fresh-installation commands below. See [public repository exclusions](docs/public_repository.md) and [retry/resume behavior and current quota stop](docs/retry_resume.md).

## Setup

Requires Python 3.12. Create and activate a virtual environment, install dependencies and generate the fictional dataset.

PowerShell (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m ar_copilot.generate
python -m pytest -q
```

bash / zsh (macOS, Linux, Git Bash):

```bash
python3 -m venv .venv
source .venv/bin/activate     # Git Bash on Windows: source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m ar_copilot.generate
python -m pytest -q
```

With the environment active, every later command is the same in both shells. Start the app with `python -m streamlit run app.py` and open http://localhost:8501. `requirements.lock.txt` records the exact tested environment. In VS Code, Terminal → Run Task offers the same commands on any OS.

Choose **Load 40 offline demo documents** in the sidebar, then review documents one at a time. Enter a reviewer name and decision reason. Approve valid invoices; fix or reject the missing-PO and inconsistent-total documents. Approve NC-0005 before approving its linked credit NC-0040. Upload `data/payments.csv` in the sidebar and click Import payments. Use the aged-debt tab to change the reporting date and download Excel workbooks. Every document starts in human review, even when validation passes. Posted documents are locked.

## Data and architecture

- `generate.py`: fixed seed 20261010 and fixed date range; 40 one-page PDFs (39 invoices, one credit note), three layouts and three UK/unambiguous date formats. Every document is marked fictional. Re-running generation reproduces bytes and truth. Names are invented.
- `data/ground_truth.csv`: raw printed field strings, including blank fields and the deliberately incorrect total; metadata filename/layout are not extraction targets. `anomalies.json` independently specifies NC-0006 missing PO and NC-0009 inconsistent total. NC-0040 is a normal negative credit linked to NC-0005, not an anomaly.
- `payments.csv`: separate simulated ledger with unpaid, partial and full payments; no payment status is claimed on invoice truth. Transactions after the selected reporting date are ignored. Import is transactional and payment IDs are immutable/idempotent.
- `extract.py`: pypdf text extraction → Gemini JSON schema/Pydantic or exact-hash offline fixtures. PDFs with no text need OCR and enter review. Exceptions retain a safe error and source; no automatic posting.
- `core.py`: independent required-field, date-order, finite Decimal, net + VAT = total and rounded 20% VAT validation. Credit notes require a link and negative values, with no required PO. Approval also requires an approved invoice for the same customer and a valid credit date.
- `store.py`: SQLite source bytes, SHA-256 unique constraint, original extraction/provenance, current corrected fields, and append-only decision history in one transaction. Business posting key uses supplier/customer/type/number, normalized for case and outer whitespace. Different PDF bytes cannot post the same business document twice. An approval cannot be edited; reversals are outside this prototype.
- `app.py`: Streamlit side-by-side rendered PDF and editable fields, original extraction and history, rejection, payments, aging and downloads. Data persists in `runtime/ar.sqlite`; this directory is excluded from Git.
- `export.py`: Python application exporter using XlsxWriter produces real named Excel tables, typed financial values/dates and formula-injection-safe text. PostedReceivables is the approved document register (including credits); aged debt uses only transactions eligible at the reporting date. Values are snapshots calculated with Decimal, not live Excel formulas. Decimal → Excel floating point occurs only at the export boundary.

Aging uses due date: due today/future = current; 1–30, 31–60, 61–90, 91+ calendar days overdue. Approved credits reduce their linked original invoice; unapproved documents are excluded and shown separately. Negative balances remain visible as customer credits. Future invoice/credit issue dates and payment dates are excluded. The report is an **as-of transaction-date snapshot of currently approved records**, not historical approval-state reconstruction. Customer allocations and credit signs are checked; unmatched ledger payments do not alter debt and remain visible in the payment ledger.

## Gemini: measured full evaluation

On 10 October 2026, all 40 documents were attempted with `gemini-3.8-flash`. **Overall field accuracy: 48/480 = 10%; document accuracy: 4/40 = 10%.** Each of the 12 fields matched on 4/40 documents (10% per field). Failed extractions remain in both denominators, including absent optional fields; no failed document receives a match. NC-0001 through NC-0004 extracted successfully with every field matching. The other 36 failed: **34 HTTP 429 and two HTTP 503**. Total measured extraction processing time was **46.57 seconds**, averaging **1.16 seconds per attempted document**; this includes rapid failed calls and is not throughput for 40 successfully extracted invoices.

Both intentional anomalies were safely routed to review, so **zero anomalous documents escaped review**. However, neither accounting anomaly was independently recognized from successfully extracted data: NC-0006 (missing PO) failed with HTTP 503 and NC-0009 (inconsistent total) failed with HTTP 429. **Rule-specific anomaly detection: 0/2, with two unassessed due to extraction failure.** The original report's `validation.detected = 2` means review routing, not successful accounting diagnosis. **34 clean documents were also routed to review because of API errors** (false positives relative to the intentional-anomaly labels); accounting-validation false positives among successful extractions were zero. These are distinct metrics.

Credit note NC-0040 failed with HTTP 429. Its negative net/VAT/total and NC-0005 linkage therefore remain **unverified by live Gemini extraction** in this run; offline tests validate those rules but cannot substitute for a live result. Your demo database and review decisions were preserved: the database file fingerprint was unchanged.

Actual outputs, expected printed fields, mismatches, errors and individual durations are saved in [the full Gemini report](reports/gemini/full_20261010T172130226758Z.json), with [a detailed summary](reports/gemini/full_20261010T172130226758Z_summary.json). Offline fixture reports are separate and were not combined with these measurements. The earlier [three-layout smoke test](docs/gemini_smoke_results.md) passed 36/36 fields but does not override this full-run result. The configured `gemini-2.5-flash` returned HTTP 404; this run used a model override without changing `.env`.

**Synthetic-dataset limitations:** only 40 seeded, text-based, one-page documents, three known layouts, five fictional customers, GBP, one assumed 20% VAT rate, two intentional anomalies and one credit note. The corpus is not a representative sample of real supplier invoices, scanned documents, OCR noise, complex line items, currencies or VAT treatments. No repeated-run confidence interval or production generalization is supported. Availability/rate-limit/server failures dominated this single run; HTTP 429 alone does not identify whether a per-minute or daily quota was reached. A future separately labelled run needs confirmed account quotas and appropriate pacing. No automatic retries, billing changes or quota purchases were made. **Manual entry has not been timed; no time-saved claim is made.**

Follow [live Gemini key setup and isolated testing](docs/gemini_live_testing.md). Key loading uses this workspace's `.env` explicitly and refreshes it on each extraction. Verify presence with `python -m ar_copilot.evaluate --check-config`, which never prints credentials. Unique new reports go to `reports/gemini/` or `reports/demo/`; the existing offline fixture report remains separate.

Uses the official `google-genai` SDK, not the retired `google-generativeai` package. Google documents Pydantic/JSON schema structured output at https://ai.google.dev/gemini-api/docs/generate-content/structured-output and SDK configuration at https://github.com/googleapis/python-genai . The installed SDK supports `response_mime_type` and `response_json_schema`; output is separately parsed and business-validated. Schema conformance does not prove accounting correctness.

For a fresh installation, copy `.env.example` to `.env` locally and set `GEMINI_API_KEY`; alternatively set that environment variable. Never paste keys into chat or commit them. `.env` and `.venv` are ignored. `GEMINI_MODEL` defaults to `gemini-3.8-flash` (set in `ar_copilot/config.py`); `--model` overrides it for a single CLI run. List the models your key can use with `python -m ar_copilot.evaluate --list-models`. Provider availability, quotas, cost and model behavior depend on the account and time of testing. Gemini mode sends PDF **text**, not PDF bytes, to Google only on processing. Do not upload sensitive real invoices to this unauthenticated prototype.

```
python -m ar_copilot.evaluate --mode gemini --sample full --model gemini-3.8-flash
```

Evaluation writes a unique JSON report under `reports/gemini/`: raw per-field exact printed-string matches, document accuracy (all 12 fields), errors, model, processing seconds, validation document detection/missed/false-positive/true-negative counts and missed expected rules. Empty and null are equivalent missing values on successful extractions; extraction failures receive no field matches. Date/spacing normalization is deliberately not applied, so exact-match metrics are strict. API failures count as failed extraction and review flags; inspect details to distinguish validator detections from provider failures. A single API run is not statistically representative.

```
python -m ar_copilot.evaluate --mode demo
```

Offline reports are explicitly **fixture checks, not measured Gemini accuracy**. They test plumbing and validation; fixtures encode truth and say nothing about AI quality. Actual perf_counter durations are recorded; no time-saving claim is made. Do not combine demo and Gemini denominators.

## Limitations and manual-entry timing

No OCR, line-item reconciliation, authentication, role permissions, accounting-system posting, production audit hardening, FX, varying VAT, payment allocation UI, reversal workflow or cloud deployment. Amounts are in GBP with an assumed 20% VAT rate, not tax advice. The fictional corpus has only one line description and simple totals. SQLite review history is append-only through the app, but a database administrator can change it. Source corrections must be justified against the source or an independently documented business resolution; a missing PO cannot be guessed from ground truth. Production duplicate identities, supplier/customer master data and allocation controls need stronger design. Keep local backups of the database.

For a manual-entry comparison, predefine fields and success criteria, randomly order the same 40 documents, and use a blank spreadsheet without truth visible. Start a monotonic timer when the operator opens each PDF; stop after all fields and checking are complete. Record document, operator, elapsed seconds, corrections and interruptions; score entries against truth afterward. Separately time the assisted workflow including extraction latency, review, corrections and approval, with the same criteria and comparable operators. Report distributions and errors, include anomaly handling and rejected documents, distinguish initial training from timed work, and avoid reusing memorized documents. Save raw observations. No manual timing has been performed.

## Microsoft 365 — UNCONFIGURED / UNVERIFIED

See [Microsoft 365 setup notes](docs/microsoft365.md). The app only downloads workbooks. No SharePoint upload, flow creation or Teams message has been performed.
