# Resilient Gemini evaluation

Google's [official troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting) recommends exponential backoff, jitter, a retry bound and retrying only temporary errors. [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) distinguish per-minute and daily project quotas. Daily request quota resets at midnight Pacific time; confirm the project/model's available quota in AI Studio before resuming. No billing changes are required or performed by this prototype.

The resilient evaluator makes sequential requests, with configurable minimum start-to-start pacing (default 12 seconds). It disables nested SDK retries so the configured attempt limit includes every API call. Backoff doubles its ceiling up to max-delay and uses random equal jitter, respects Retry-After seconds/HTTP dates and Google's RetryInfo delay, and never shortens a server delay to fit a wait budget. If a server delay exceeds that budget it stops instead. Each document permits at most four calls and 120 seconds of retry waits by default; pacing waits are separate. Requests have a 60-second timeout. Explicit daily/zero quota or depleted credits stop immediately; an ambiguous 429 is retried within the bounds, then stops with a distinct retry-budget reason. Raw provider exception bodies, keys and request headers are never persisted.

Atomic JSON checkpoints are written before processing, after each attempt and after every document. Successful extractions are reused even if they contain accounting anomalies or mismatches. Only failed/pending documents are called again. Resume validates document identity, printed ground truth and PDF hashes (legacy reports use extracted-text checks). Every resume creates a new file and preserves its source report. Previous results and retry attempts remain auditable. An interrupted call may have reached Google before its result was checkpointed; exactly-once API execution cannot be guaranteed across process termination. Run only one evaluator per checkpoint.

```powershell
# Fresh resilient full run
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode gemini --resilient --model gemini-3.8-flash --pace 12
# Retry one failed/pending document using a previously generated report
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode gemini --model gemini-3.8-flash --resume reports/gemini/YOUR_REPORT.json --limit 1 --pace 12
```

Use --max-attempts, --base-delay, --max-delay and --max-wait to configure bounded retry behavior. Completion rate, field/document accuracy among completed extractions and overall accuracy including failed/pending documents are distinct. Failed API outputs never enter accounting-anomaly counts. Previously unclassified API errors remain explicitly legacy_unclassified.

The local one-document retry on 10 October 2026 returned HTTP 429 classified as daily_quota_exhausted. The evaluator stopped after one request without further retries. Four prior successes were reused: completion 4/40 (10%), completed field/document accuracy 100%, overall field/document accuracy 10%. Both anomalies remain unassessed. The retry took 0.856 seconds of request processing. The demo database was unchanged. The original report was preserved; the new checkpoint remains local under ignored reports/gemini.

Next step: in Google AI Studio's project/model rate-limit view, confirm the gemini-3.8-flash daily quota has reset and is nonzero, then resume the local checkpoint. If the allowance is zero or still exhausted, wait for the shown reset or use an already-authorized model with available free quota after a separate smoke test. Do not enable billing or purchase quota as part of this workflow.
