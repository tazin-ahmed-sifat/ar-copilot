# Public repository contents

This repository contains source, tests, setup notes and an empty credential example. All companies/invoices are fictional. Recreate the reproducible dataset with `python -m ar_copilot.generate` after setup.

Local secrets (.env and variants), SQLite review records, generated invoice datasets, raw evaluation outputs, exports, logs, caches, and virtual environments are excluded from Git. Recorded aggregate metrics in README are from the synthetic dataset; no live customer/account data is included. `.env.example` must remain empty. Do not force-add excluded files.

Before each push, inspect `git diff --cached --stat` and confirm `git check-ignore .env runtime/ar.sqlite`. Source commits use a GitHub noreply address rather than the personal address from the global Git configuration. The initial publication uses an explicit file allowlist and scans staged content for the exact configured secret without printing it, plus common token/private-key patterns. If a credential is ever committed, removing the file in a later commit is insufficient: revoke the credential and purge it from history before publishing.

Raw reports stay local. The README cites only the metrics-only files in `results/`, which are regenerated from those reports by the scripts in `scripts/`.

The release audit found a historical `.agents/skills/developing-with-streamlit` symlink containing a local filesystem path. Following user approval, that exact path was removed from all local Git history with git-filter-repo. A complete pre-rewrite Git backup remains private under ignored runtime/. The post-rewrite audit found no remaining symlink or private/raw-data paths. See [release review](release_review.md) for scope and limitations.
