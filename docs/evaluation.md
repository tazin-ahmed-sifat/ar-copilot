# Running the evaluation

The evaluation extracts each generated document and compares the raw model output with the
printed values in `data/ground_truth.csv`. It scores the output before any human correction.
The model only ever sees the PDF text. Ground truth is used for scoring and nothing else.

Results for the saved run, and how to read them, are in the [README](../README.md#evaluation).
This page covers the commands.

## Dataset

`python -m ar_copilot.generate` writes 40 fictional PDFs into `data/invoices/` from a fixed seed
(39 invoices, one credit note, three layouts), along with:

- `ground_truth.csv` — the printed values for each document
- `anomalies.json` — the two deliberate problems: NC-0006 has no PO number and NC-0009's total
  doesn't match net plus VAT
- `payments.csv` — the demo payment ledger
- `demo_fixtures.json` — the stored answers that demo mode replays

## Commands

A quick check on one document from each layout:

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample per-layout
```

The full run, checkpointed after every document:

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample full --resilient --pace 0 --max-attempts 1
```

Reports are written to `reports/ollama/`, which Git ignores because they contain invoice text
and model output. The last line printed is the checkpoint path.

If a run is interrupted, resume it from that checkpoint. Documents that already succeeded are
reused rather than sent to the model again. The original report is left as it was, and a new
one is written.

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample full --resilient --pace 0 --max-attempts 1 --resume .\reports\ollama\<checkpoint>.json
```

Before reusing anything, resume checks that the model, settings, PDF hashes and ground truth all
match the earlier run. Resuming the saved run (`resilient_20261010T222850202032Z.json`) made no
new model calls and reused all 40 results.

`--max-attempts` above 1 retries temporary HTTP failures with backoff (`--base-delay`,
`--max-delay`, `--max-wait`). Malformed output and input errors are never retried.

## Publishing a summary

```powershell
.\.venv\Scripts\python.exe scripts\publish_results.py .\reports\ollama\resilient_20261010T222850202032Z.json
```

This writes `results/ollama_summary.json` and `results/ollama_summary.md`. They contain counts,
rates and timings only, with no invoice text or field values. The script refuses demo-mode
reports.

## Scoring rules

- Each field is an exact string match against the printed value, so `2026-06-29` and `29/06/2026`
  count as different.
- A document only counts as correct if all twelve fields match.
- A failed extraction counts as wrong in the overall figures. Accuracy on completed documents
  is reported as a separate figure.
- An anomaly counts as caught only if a validation rule flagged it on a completed extraction.
  A failed call is listed as "unassessed", never as a catch.
- A false positive is a rule firing on a document that has no deliberate problem.
- The evaluation never writes to `runtime/ar.sqlite`. It fingerprints the file before and after
  the run and records whether it changed.

## Demo mode

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode demo
```

This replays the stored answers, which were built from the ground truth, so it always scores
100%. Use it to check that the scoring code works. It doesn't measure anything about the model.
