# Release review

AR Copilot is a single-user prototype with local LLM extraction and optional online Microsoft 365 automation. Ollama qwen3:8b at http://127.0.0.1:11434 is the sole real LLM. Invoice text is never sent to a cloud LLM. Explicit demo fixture replay is a separate plumbing check.

## Supported behavior and saved evidence

The app requires human review, stores decisions and audit history in SQLite, prevents duplicate posting, handles payments and credit notes, ages debt and exports Excel registers. Approval is a local register action, not an accounting-system posting.

The saved [Ollama summary](../results/ollama_summary.md) supports 40/40 completed documents, 480/480 correct fields, 40/40 correct documents, 2/2 anomalies detected, zero false positives/runtime failures and 104.99 seconds extraction processing. These synthetic-dataset results do not establish real-invoice accuracy or human time savings. Raw reports stay ignored locally. Existing records, review decisions and historical Git commits are preserved; no history rewrite is part of this change.

## Separate online automation

The [OneDrive implementation guide](microsoft365_onedrive.md) records the separate manual Power Automate/email test and distinguishes it from proposed report-date, duplicate-send, ambiguous-send, replacement-file and pagination safeguards. Those safeguards require manual account/UI verification. No flow was changed or email sent by this provider cleanup. SharePoint/Teams remain a proposed extension documented [separately](microsoft365.md).

Internet access is allowed for these intended integrations; the app does not impose a global network-disabling mode. Network isolation has not been verified.

## Remaining verification limits

- Streamlit AppTest covers review, payment/export and timing workflows in temporary files. A server health check does not establish native browser upload/download or full visual behavior.
- OCR is not implemented; scanned invoices require separate handling.
- Conservative context checks reject oversized invoices without silently truncating them.
- Real invoices still require human review. Prompt separation and schema checks do not guarantee semantic correctness.
- Human performance observations are required before any time-savings claim.
- Microsoft 365 delivery safeguards and schedules require manual verification in the user's account.

Only safe aggregate metrics are committed. Do not add raw reports, local credentials, review databases or exported private financial records to Git. No push or external publication is performed by local summary regeneration.
