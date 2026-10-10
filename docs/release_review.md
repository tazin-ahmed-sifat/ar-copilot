# Release review

Reviewed on 10 October 2026. This is a single-user prototype using fictional financial data.

## Supported behavior

The local app extracts text PDFs, requires human review, stores decisions in SQLite and exports
aged debt to Excel. Approval is a local register action, not an accounting-system posting.
The repository contains Codex-assisted code, tests and documentation; it does not establish an
individual contribution percentage.

A separate manually configured Power Automate flow was tested in the Brunel account: OneDrive
workbook, Excel rows, overdue positive balances, HTML table and email to the account owner.
The [implementation guide](microsoft365_onedrive.md) distinguishes that test from proposed
report-date, duplicate-send, ambiguous-send, replacement-file and pagination safeguards.
Those cloud safeguards have not been installed or verified in this review. Keep the flow manual;
no recurring schedule was enabled and no additional email was sent.
SharePoint and Teams are an unbuilt extension; account creation restrictions remain.

## Publication audit before cleanup

The audit scanned 35 commits reachable through refs or reflogs, 190 unique historical blobs and
both historical compressed Excel blobs, including their decompressed members. It also scanned
two unreachable blobs found by Git fsck. No configured private-value matches or common
API-token/private-key patterns were found. The current publication allowlist was scanned too.
No raw-report, local database or private-data paths were identified in the scanned history.
The committed workbook fixture and screenshots contain fictional demonstration data.
Pattern matching cannot prove that every possible credential format or sensitive value is absent.
Local `.env` contents and discovered values were never displayed.

At the initial review, the affected historical path was: `.agents/skills/developing-with-streamlit` was a symlink whose target
contains a local filesystem path. The current tree no longer tracks it; `.agents/` and `.codex/`
are ignored. Deleting it in a later commit does not remove historical exposure.

The initial recommendation was to remove that path from every historical ref. A suitable
remediation is a backed-up, separately reviewed `git filter-repo` operation removing the exact
path, followed by another audit and coordination with any existing clones. This changes commit
identifiers and may require remote-history replacement. At that stage no history rewrite, push or deployment
was performed; the subsequently authorized cleanup is recorded below. If a credential is found in a later audit, revoke it before removing its history.

## Authorized history cleanup

After the pre-cleanup findings were explained, the user authorized history removal. A full Git
metadata backup was created under ignored `runtime/`; keep it private because it retains the
original history. `git-filter-repo` removed only `.agents/skills/developing-with-streamlit`.
Remote configuration was restored without displaying it. No push was performed.

The post-rewrite audit scanned 37 commits, 202 unique blobs and two decompressed Excel blobs.
It found no configured credential matches, common credential patterns, symlinks or private/raw
report paths. Git fsck found no unreachable objects. All 87 checked current source and local
evidence files were unchanged. Commit identifiers changed; public or shared remote history,
if any, still needs a coordinated replacement. Do not merge the old history back into this copy.

## Verification and evidence gaps

- 105 automated tests passed after cleanup, including Streamlit AppTest, timing, evaluation, storage and exports.
- README local links and image paths were checked; Git whitespace checks passed.
- Original reports, exported demonstration workbook and demo database were verified against
  the existing local preservation hashes.
- Browser discovery returned no available browser. Current visual layout and native browser
  upload/download behavior remain unverified; screenshots show an earlier offline session.
- Live extraction completed only 4 of 40 documents. Zero mismatches among those four does not
  establish real-world accuracy. Neither intentional anomaly nor the credit note was assessed.
- Human timing measurements have not been supplied. There is no supported time-saving claim.
- Cloud stale-date and repeat-run tests, persistent duplicate protection, ambiguous-email handling,
  dynamic file resolution and pagination remain UI verification tasks in the implementation guide.

## Release checklist

- [x] Review wording, safe aggregate evidence, tests and README paths.
- [x] Preserve local financial records and raw evaluation evidence.
- [x] Commit safe changes without pushing or deploying.
- [x] Remove the historical symlink after authorization and audit the rewritten history.
- [ ] Coordinate remote history replacement if the old commits were already published.
- [ ] Inspect the current app visually when browser access is available.
- [ ] Verify cloud safeguards before any schedule; retain manual operation meanwhile.
- [ ] Collect human measurements before publishing a timing result.
