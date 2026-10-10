# Ollama setup and operation

AR Copilot uses **local LLM extraction with optional online Microsoft 365 automation**. Ollama is the sole real LLM provider: qwen3:8b at http://127.0.0.1:11434. No API key, provider selector, model-listing command or global network restriction is needed. The transport bypasses proxies and rejects redirects, other endpoints, other model names and cloud-backed Ollama models. Invoice text never goes to a cloud LLM.

The application does not disable intended online integrations. Excel exports are local files; optional OneDrive sync and Power Automate/email operate separately and require internet access. See [Microsoft 365 implementation](microsoft365_onedrive.md). No flow, email, firewall or network configuration was changed as part of the Ollama implementation.

## Launch

After Ollama, qwen3:8b and Python dependencies are installed, run from the repository:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open http://127.0.0.1:8501. Optional `.env` entries:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
```

The app validates both values and rejects alternatives. Internet access is allowed for Microsoft 365 and other intended automation. If desired, manually disconnect networking after installation while keeping Ollama running; local extraction, review, payments, ageing and Excel exports still work, while online automation does not. Network isolation has not been verified. Streamlit usage telemetry remains disabled and the theme uses local system fonts. Other installed software, including Ollama's Windows updater, can use the network.

## Extraction and limits

PDF text alone is passed as an untrusted user message, with extraction instructions in a separate system message. No tools are available to the model. Actual extraction never reads ground truth or fixtures. Explicit demo mode replays fixtures and is not LLM extraction. All results require human review; Decimal rules, duplicates, SQLite history and posting logic are reused.

The /api/chat request supplies a JSON schema requiring every key. Strict Pydantic validation accepts strings or null, rejects extra keys and numeric money values, and rejects missing keys. Existing accounting rules then check printed dates, totals, PO and credit references. Malformed or incomplete output, timeouts and model/server failures remain in the review workflow. There is no cloud fallback.

Fixed settings: num_ctx=4096, num_predict=768, temperature=0, seed=42, think=false, 120-second per-request timeout. A UTF-8 byte upper bound reserves 512 tokens for template/grammar overhead plus all output tokens. Oversized inputs are rejected before inference; incomplete or output-limited responses are rejected. Nothing is silently truncated. This conservative policy can reject documents that might fit with exact tokenization. Scanned PDFs still need unimplemented OCR. Prompt separation reduces instruction-injection risk but does not guarantee correct extraction.

Official documentation: [chat API](https://docs.ollama.com/api/chat), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [runtime context](https://docs.ollama.com/faq). Standard-library HTTP is used; no Ollama SDK is required.

## Saved evaluation evidence

The saved sequential report and committed [safe summary](../results/ollama_summary.md) support 40/40 completed documents, 480/480 correct fields, 40/40 correct documents, 2/2 anomalies detected, zero rule false positives and runtime failures, and 104.99 seconds extraction processing. These synthetic-dataset results are not real-invoice accuracy or human time savings. Raw outputs stay ignored under reports/ollama/. Historical raw reports and existing Git history remain intact.

The completed evaluation need not be repeated after removing the unused cloud provider: the Ollama prompt, schema, request payload and generation limits are unchanged. See [checkpoint commands](retry_resume.md) for new evaluation, resume and safe-summary regeneration. Timing collection uses Ollama, records provider/model and requires actual human measurements before a time-savings claim.
