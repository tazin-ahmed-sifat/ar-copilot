# Local QA

## Tests

```
python -m pytest -q
```

The suite runs offline against temporary copies of the fictional dataset and never touches
`runtime/ar.sqlite`. It covers:

- **Corpus:** byte-reproducible PDFs, printed ground truth, the two intentional anomalies and the credit note.
- **Rules:** required fields, dates, VAT, signs, malformed or sub-penny amounts, and every aging bucket boundary.
- **Storage:** duplicate prevention by file hash and by business key, rollback on a bad decision or payment row,
  locked approvals, credit allocation and the decision history.
- **Exports:** real Excel tables, typed cells, formula-injection safety, empty-table templates, and Summary formulas
  that trace back to AgedDebt.
- **Evaluation:** strict scoring, failed calls kept apart from rule detections, retries, quota stops, checkpoints and resume.
- **App:** the review, payment and download flow and the timing page, driven through Streamlit's AppTest.
  AppTest can't open a native file chooser, so uploads are supplied at the uploader call.
- **Excel fixture:** the Python aging rules against the hand-computed answer in `excel/fixture/`.

## End-to-end check without the UI

```
python scripts/local_verify.py
```

This builds an in-memory database from the demo PDFs, approves every document that passes
validation (marked as an automated fixture decision), imports the demo ledger and writes example
workbooks to `output/`. It should report 38 approved documents, 2 unresolved and 37 aged-debt
rows. PDF contact sheets go to `tmp/qa/`.

## Offline evaluation

```
python -m ar_copilot.evaluate --mode demo
```

Fixtures were built from the ground truth, so a perfect score is expected and proves only that
extraction, scoring and validation are wired together. It is not Gemini accuracy and is never
reported as such.

## Not covered locally

- Opening the exported workbooks in Excel and running the Power Query: see [excel/README.md](../excel/README.md).
- Microsoft 365 cloud behavior: the [manual OneDrive test](microsoft365_onedrive.md) was performed
  separately; proposed safeguards and the [SharePoint/Teams extension](microsoft365.md) are not locally verified.
- Browser-level upload and download clicks.
