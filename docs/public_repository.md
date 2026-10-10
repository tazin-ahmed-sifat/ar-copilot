# Public repository contents

The repository contains source, tests, setup notes and an example containing only the enforced Ollama endpoint/model. Synthetic documents contain fictional companies and transactions. Regenerate the dataset only when needed with `python -m ar_copilot.generate`.

Local secrets (.env and variants), SQLite review records, generated datasets, raw reports, exports, logs, caches and virtual environments are ignored. Preserve existing runtime/ar.sqlite and raw reports; do not force-add them. Existing Git history is retained.

The current results directory contains safe Ollama aggregates regenerated from saved evidence by scripts/publish_results.py. Current documentation cites only the saved synthetic-dataset results, not real-invoice accuracy or human time savings. Older raw reports remain ignored locally. Removing obsolete published files from the current tree does not remove their historical commits.

Use scripts/audit_public_files.py to scan the source allowlist and staged content without printing private values. The scan checks configured private values and common credential patterns; pattern matching cannot prove absence of every credential format. Before any separately authorised publication, inspect staged files and confirm `.env` and the review database remain ignored.

The architecture is local LLM extraction with optional online Microsoft 365 automation. OneDrive, Power Automate and email are documented separately and need internet access. No global network-disabling mode or verified network-isolation claim is made.
