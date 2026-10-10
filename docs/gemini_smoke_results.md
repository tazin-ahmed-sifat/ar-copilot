# Live Gemini smoke test — 10 October 2026

Three actual API extractions succeeded using **gemini-3.8-flash**. The configured default gemini-2.5-flash returned HTTP 404 for all three documents; a model-list query nevertheless advertised it. This run does not establish why that listed model failed. No key values or provider exception bodies were printed. `.env` was not changed; the successful model was a command-line override for an isolated process.

The successful raw report is `reports/gemini/per-layout_20261010T171717209955Z.json`. It includes actual extracted fields and printed ground truth. All 36 field comparisons matched (100% exact field accuracy); all three documents matched in full (100% document accuracy). There were zero extraction errors and zero validation failures/false positives. These three clean invoices contain no intentional anomalies, so anomaly detection and credit-note extraction remain untested with Gemini.

Actual extraction processing time totaled 21.232813800001168 seconds, averaging 7.077604600000389 seconds per document. This includes PDF text extraction, client setup, network wait and output parsing; it is not model-only latency or a time-saved claim. Read the raw report for individual timings.

The review database file fingerprint was unchanged. No documents were posted, corrected or rejected during this evaluation. Offline reports were not used as extraction outputs and remain separate. Earlier failed connection/404 runs are retained as diagnostic reports, not evidence of zero model accuracy.

## Full 40-document run subsequently executed

The later full run attempted all 40 documents but returned four successful extractions and 36 API failures. Overall accuracy including failures was 10% for fields and documents. See [README measured results](../README.md) and `reports/gemini/full_20261010T172130226758Z.json`. The smoke-test result above remains a separate three-document measurement.

Use the successful model explicitly rather than the default that returned 404:

```
python -m ar_copilot.evaluate --mode gemini --sample full --model gemini-3.8-flash
```

This makes 40 sequential requests, records raw comparisons and actual timings under `reports/gemini/`, and checks the review database is unchanged. The corpus includes the missing PO, inconsistent printed total and linked credit note. Network access and account quota must permit the requests. Do not rerun until the observed API failures and available quotas have been reviewed.
