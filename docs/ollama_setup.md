# Ollama setup and operation

The default provider is Ollama, using only http://127.0.0.1:11434 and the already installed qwen3:8b. No cloud key is needed. The transport bypasses environment proxies and rejects redirects, other endpoints and cloud-backed models. AR_LOCAL_ONLY defaults to 1; Gemini extraction and cloud model discovery are blocked in that mode. To explicitly use Gemini, set AR_LOCAL_ONLY=0 and select Gemini. There is no automatic fallback.

The application has no external integration client. Excel export is a local file operation. OneDrive sync and the separate Power Automate email workflow require internet access and are outside this app's local-only inference boundary. No flow, firewall or network settings were changed.

Streamlit usage telemetry is disabled in .streamlit/config.toml. Remote Google Fonts were removed. Ollama's Windows updater and other installed software can still use the network. For Ollama's supported cloud disable switch, set OLLAMA_NO_CLOUD=1 in the environment of the Ollama server and restart Ollama yourself; setting it in the app terminal cannot change an already-running server. Official instructions: https://docs.ollama.com/faq . This is local-only inference, not verified air-gapped operation.

After dependencies and qwen3:8b are installed, disconnect networking manually if desired, keep Ollama running, then launch from the repository:

```powershell
$env:AR_LOCAL_ONLY = '1'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'qwen3:8b'
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open http://127.0.0.1:8501. Local extraction, review, approvals, payments, ageing and Excel exports work without networking. OneDrive/Power Automate do not.

## Extraction and limits

PDF text alone is passed as an untrusted user message, with extraction instructions in a separate system message. No tools are available to the model. Real extraction never reads ground truth or fixtures; only explicitly selected demo extraction replays fixtures. Human review remains mandatory, and Decimal rules, duplicate checks, SQLite history and posting logic are reused.

Ollama /api/chat uses a required-field JSON schema, independently checked with strict Pydantic validation. Every schema key must exist, with absent printed values represented by null; extra keys and numeric money values are rejected. Business rules then flag missing PO and inconsistent totals. Malformed/incomplete responses, model outages and timeouts return errors to review. Output truncation is rejected.

Settings are fixed conservatively: num_ctx=4096, num_predict=768, temperature=0, seed=42, think=false, 120-second per-request timeout. A UTF-8 byte upper bound reserves 512 tokens for template/grammar overhead plus all output tokens. Oversized inputs are rejected before inference, never silently truncated. This deliberately rejects some documents which might fit with exact tokenization. Scanned PDFs still require unimplemented OCR. Prompt separation reduces instruction injection risk but does not guarantee extraction correctness.

Verified via /api/ps before and after evaluation: context_length 4096, Q4_K_M, total model bytes equal VRAM bytes (5,578,204,118). Largest observed prompt/output counts were 546/150 tokens; counts are in ignored raw reports. No larger context was attempted on the 8 GB GPU. Official API/schema documentation: https://docs.ollama.com/api/chat and https://docs.ollama.com/capabilities/structured-outputs . No Ollama Python dependency is needed; standard-library HTTP is used.

## Measured evaluation

The first three-layout smoke run completed but misread two blank linked-invoice labels. After clarifying blank label handling, the second run matched 36/36 fields. The final sequential full run completed 40/40 documents, matched 480/480 fields and 40/40 documents, with zero runtime failures. Both intentional anomalies (NC-0006 missing PO, NC-0009 inconsistent totals) were detected and there were zero rule false positives. Linked credit notes were scored against their printed invoice references. Review database hash was unchanged.

Request processing total: 104.986654 seconds; full invocation: 105.684811 seconds. These are measured Ollama extraction processing times on fictional documents, not human-assisted timings or time-saved claims. Accuracy on this corpus does not establish real invoice accuracy. See ../results/ollama_summary.md and .json for safe metrics; Gemini summaries are unchanged. Raw text, fields and responses stay in ignored reports/ollama/.

Run a smoke test, then a full sequential checkpoint run:

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample per-layout
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample full --resilient --pace 0 --max-attempts 1
```

Resume the measured checkpoint (it is already complete, so this reuses all 40 successes):

```powershell
.\.venv\Scripts\python.exe -m ar_copilot.evaluate --mode ollama --sample full --resilient --pace 0 --max-attempts 1 --resume .\reports\ollama\resilient_20261010T222850202032Z.json
```

For an interrupted run, use the checkpoint path printed by that run. Resume creates a new report, skips successful extractions, and checks provider, model/settings, PDF hashes and truth against the source. Reports never overwrite Gemini or the source checkpoint. Failures remain in overall accuracy denominators; completed-only accuracy and unassessed anomalies are reported separately.

Generate metrics-only summaries locally (no remote publication):

```powershell
.\.venv\Scripts\python.exe scripts\publish_results.py .\reports\ollama\resilient_20261010T222850202032Z.json
.\.venv\Scripts\python.exe -m pytest -q
```

Timing page supports Ollama for practice and measured trials and records provider/model. Mixed provider/model trials cannot be pooled into a time-reduction comparison. No human Ollama timing study has been collected here.

Verification: the existing suite plus initial Ollama tests passed (119 tests); four additional leakage, redirect, cloud-model and safe-summary checks also passed (18 Ollama tests total). Streamlit AppTest covers isolated review/payment/export and timing workflows; a live loopback server on port 8502 returned HTTP 200 from its health endpoint.
