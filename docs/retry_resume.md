# Sequential Ollama evaluation and resume

The sole real LLM is qwen3:8b at http://127.0.0.1:11434. Evaluation reads printed ground truth only to score returned fields; the model receives PDF text alone. Offline demo evaluation replays fixtures and is a plumbing check, not measured LLM accuracy.

A new run can start with one document per layout:

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample per-layout
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample full --resilient --pace 0 --max-attempts 1
```

Sequential checkpoint evaluation saves atomically after each attempt under ignored reports/ollama/. The default is one attempt per document and no pacing delay. Bounded retries for temporary HTTP failures can be configured explicitly. Malformed responses and input/configuration errors are not retried automatically. Extraction errors remain in overall accuracy denominators; completed-only accuracy, runtime failures, unassessed anomalies and false positives are separate metrics.

Resume the saved completed run:

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample full --resilient --pace 0 --max-attempts 1 --resume .\reports\ollama\resilient_20261010T222850202032Z.json
```

This reuses all 40 successful responses without new inference. For an interrupted run, use its printed checkpoint path. Resume creates a new report; the original is immutable. Provider/model/settings, document set, PDF hashes and printed truth are checked before reuse. The review database is fingerprinted and never written by evaluation.

Regenerate metrics-only summaries locally:

```powershell
.\.venv\Scripts\python.exe scripts\publish_results.py .\reports\ollama\resilient_20261010T222850202032Z.json
```

This writes results/ollama_summary.json and .md only. It does not publish externally, include invoice text/field values, or alter raw evidence. Current summaries accept Ollama reports only. Historical raw reports remain ignored locally; no history rewrite is needed.

The saved report supports 40/40 completed, 480/480 fields correct, 40/40 documents correct, 2/2 anomalies detected, zero false positives/runtime failures and 104.99 seconds extraction processing. These are synthetic-dataset results, not real-invoice accuracy or human time savings.
