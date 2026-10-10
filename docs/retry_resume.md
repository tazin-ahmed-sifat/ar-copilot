# Resilient Gemini evaluation

Google's [official troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting) recommends exponential backoff, jitter, a retry bound and retrying only temporary errors. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) distinguish per-minute and daily project quotas. Daily request quota resets at midnight Pacific time; confirm the project/model's available quota in AI Studio before resuming. No billing changes are required or performed by this prototype.

The resilient evaluator makes sequential requests, with configurable minimum start-to-start pacing (default 12 seconds). It disables nested SDK retries so the configured attempt limit includes every API call. Backoff doubles its ceiling up to max-delay and uses random equal jitter, respects Retry-After seconds/HTTP dates and Google's RetryInfo delay, and never shortens a server delay to fit a wait budget. If a server delay exceeds that budget it stops instead. Each document permits at most four calls and 120 seconds of retry waits by default; pacing waits are separate. Requests have a 60-second timeout. Explicit daily/zero quota or depleted credits stop immediately; an ambiguous 429 is retried within the bounds, then stops with a distinct retry-budget reason. Raw provider exception bodies, keys and request headers are never persisted.

Atomic JSON checkpoints are written before processing, after each attempt and after every document. Successful extractions are reused even if they contain accounting anomalies or mismatches. Only failed/pending documents are called again. Resume validates document identity, printed ground truth and PDF hashes (legacy reports use extracted-text checks). Every resume creates a new file and preserves its source report. Previous results and retry attempts remain auditable. An interrupted call may have reached Google before its result was checkpointed; exactly-once API execution cannot be guaranteed across process termination. Run only one evaluator per checkpoint.

```
# Fresh resilient full run
python -m ar_copilot.evaluate --mode gemini --resilient --model gemini-3.8-flash --pace 12
# Retry one failed/pending document using a previously generated report
python -m ar_copilot.evaluate --mode gemini --model gemini-3.8-flash --resume reports/gemini/YOUR_REPORT.json --limit 1 --pace 12
```

Use --max-attempts, --base-delay, --max-delay and --max-wait to configure bounded retry behavior. Completion rate, field/document accuracy among completed extractions and overall accuracy including failed/pending documents are distinct. Failed API outputs never enter accounting-anomaly counts. Previously unclassified API errors remain explicitly legacy_unclassified.

The latest local one-document resume on 10 October 2026 reused the four successes from the latest compatible checkpoint, after validating document identities, ground truth and PDF hashes. Two HTTP 504 timeouts were retried with bounded backoff, then HTTP 429 was classified as daily_quota_exhausted. The evaluator saved a new checkpoint and stopped immediately, without retrying the daily quota response. Completion remains 4/40 (10%), completed field/document accuracy 100%, and overall field/document accuracy 10%. Both anomalies and the single credit note remain unassessed; completed extractions have zero mismatches and zero rule false positives.

Request processing took 120.362 seconds, retry waits 5.021 seconds and invocation elapsed time 125.414 seconds. The cumulative observed request/wait time across the checkpoint lineage is 172.801 seconds; it excludes gaps between invocations. The safe summary counts each document's latest outcome (34 HTTP 429 and two HTTP 503 failures), rather than counting the temporary 504 attempts as extra documents. Thirty-five legacy failures remain unclassified; the current quota failure is classified. An earlier sandboxed attempt encountered connection errors and was stopped; that interrupted checkpoint remains local and is not the published live result.

The demo database and every original report were verified unchanged by SHA-256 comparison. The new checkpoint remains under ignored reports/gemini; its run ID appears in results/gemini_summary.json. Only GEMINI_MODEL was changed in the local .env, and the effective app/evaluator model was verified as gemini-3.8-flash. No key or other environment value was displayed or published.

Next step: in Google AI Studio's project/model rate-limit view, confirm the gemini-3.8-flash daily quota has reset and is nonzero, then resume the local checkpoint. If the allowance is zero or still exhausted, wait for the shown reset or use an already-authorized model with available free quota after a separate smoke test. Do not enable billing or purchase quota as part of this workflow.

After a paced or resumed run finishes, refresh the committed results from its checkpoint:

```
python scripts/publish_results.py reports/gemini/resilient_<run-id>.json
```

This rewrites `results/gemini_summary.json` and the table in `results/gemini_summary.md`. Completion rate, accuracy on completed documents and overall accuracy are reported separately; commit both files together.
