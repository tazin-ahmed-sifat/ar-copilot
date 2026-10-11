# Testing

## Unit and app tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The suite doesn't need Ollama or the internet. Ollama responses are mocked, and each test works
on a temporary copy of the fictional dataset, so `runtime/ar.sqlite` is never touched. It covers:

- **Data generator.** The PDFs are reproducible byte for byte, and the anomalies and credit note
  are where they should be.
- **Ollama client.** Strict JSON parsing, required keys, the loopback-only endpoint and fixed
  model, the size and output limits, and how failures are routed into review.
- **Rules.** Required fields, dates, VAT, signs, bad or sub-penny amounts, and every ageing
  bucket boundary.
- **Storage.** Duplicate blocking by file hash and by document identity, rollback when a
  decision or payment import fails, locked approvals, credit-note linking, and the decision
  history.
- **Exports.** Real Excel tables, typed cells, formula-injection safety, empty tables, and
  Summary formulas that trace back to `AgedDebt`.
- **Evaluation.** Scoring, keeping failed calls separate from rule detections, retries,
  checkpoints and resume.
- **App pages.** The review, payment, download and timing flows, driven through Streamlit's
  `AppTest`. This includes a full twelve-task measured timing run with a fake clock and mocked
  extraction, which checks that the page produces a valid matched comparison. These are software
  tests, not timing measurements. `AppTest` can't open a file chooser, so uploads are passed in
  directly.
- **Excel fixture.** The Python ageing rules against the hand-worked answer in `excel/fixture/`.
- **Office Script and send journal.** `tests/notification_safeguards.mjs`, run through Node.
  These test local code that isn't installed in the live flow (see [microsoft365.md](microsoft365.md)).

If pytest can't create its temporary folder (for example, when the user temp directory is
locked down), point it somewhere writable with `--basetemp`, such as
`--basetemp .\tmp\pytest`.

## End-to-end check without the browser

```powershell
.\.venv\Scripts\python.exe scripts\local_verify.py
```

This loads the demo PDFs into an in-memory database and approves every one that passes the
rules (marked as a scripted fixture approval). It then imports the demo ledger and writes example
workbooks to a new `output/qa_<timestamp>/` folder. It should report 38 approved, 2 unresolved
and 37 aged-debt rows. It also writes a contact sheet of sample PDFs to `tmp/qa/`.

## Not covered by automated tests

- Opening the exports in Excel and running the Power Query. The author checked this manually on
  10 October 2026; see [excel/README.md](../excel/README.md).
- Anything in Microsoft 365. The author ran the flow once by hand on 10 October 2026; see
  [microsoft365.md](microsoft365.md).
- Real file-chooser uploads and downloads in a browser.
