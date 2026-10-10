# Public repository contents

This repository contains source, tests, setup notes and an empty credential example. All companies/invoices are fictional. Recreate the reproducible dataset with `python -m ar_copilot.generate` after setup.

Local secrets (.env and variants), SQLite review records, generated invoice datasets, raw evaluation outputs, exports, logs, caches, virtual environments and local agent/config directories are excluded from Git. Recorded aggregate metrics in README are from the synthetic dataset; no live customer/account data is included. `.env.example` must remain empty. Do not force-add excluded files.

Before each push, inspect `git diff --cached --stat` and confirm `git check-ignore .env runtime/ar.sqlite`. Source commits use a GitHub noreply address rather than the personal address from the global Git configuration. The initial publication uses an explicit file allowlist and scans staged content for the exact configured secret without printing it, plus common token/private-key patterns. If a credential is ever committed, removing the file in a later commit is insufficient: revoke the credential and purge it from history before publishing.

Raw local report links in README may not resolve in a fresh clone; generate your own reports. Published measured summaries remain labelled synthetic and do not imply production accuracy or time saved.
