# Collecting manual versus Gemini-assisted timings

**Status: procedure prepared and software-tested; no human timing measurements collected.**
No time reduction has been measured. Automated tests use fake clocks/extraction in temporary
directories to verify the software; they are not observations of anyone's performance.

## Before starting

Use one participant alias, one browser tab, the same computer and network, and the same screen
layout for both methods. Set aside an uninterrupted session. Do not open the measured PDFs,
ground-truth CSV, extraction fixtures or answer sheets beforehand. Record outside-app exposure,
interruptions and unusual network conditions privately so they can be disclosed during validation.
The app cannot detect outside-app exposure or every interruption automatically.

The original demo ledger and exported reports are not timing tasks. The timing page uses a fresh
synthetic corpus in `runtime/timing_data`, with different printed amounts/dates from the demo.
Preparation does not create observations, call Gemini, or change the demo database.

From the project directory in PowerShell:

```powershell
.venv\Scripts\python.exe scripts\prepare_timing_documents.py
.venv\Scripts\python.exe -m streamlit run app.py
```

The timing documents have already been prepared locally in this workspace. The preparation
command refuses to overwrite an existing corpus; that refusal preserves it. Do not regenerate
it or edit its PDFs/ground truth once exposed. The app records a fingerprint of the truth and
practice/measured PDF bytes, so changed corpora are not silently pooled in the comparison.

Gemini-assisted measured tasks require `gemini-3.8-flash`. Confirm that a key is configured and
the project has available free quota before collecting live practice or measured attempts.
The latest evaluation stopped on daily quota exhaustion: wait for an actual reset/nonzero
allowance. Do not enable billing. The timing page makes one extraction call per assisted attempt
with SDK retries disabled; it stops an attempt immediately on an explicit quota/credit stop.

## Exactly what to do in the app

1. Open **Time a document**. Enter an **Operator alias**, for example `P01`, and retain it throughout.
   Use the same **Study code** throughout, for example `pilot-1`. Avoid names/email addresses.
2. Choose **Order group A** for participant 1. If there is another participant, assign B to the
   second, then alternate A/B across participants. Choose before viewing the documents and keep
   the assignment. One person must not run both groups: that would repeat the same PDFs.
3. Leave **Practice run (excluded from results)** checked. Choose **Practice method: manual**.
   Click **Start next document**, read the displayed PDF, type the 12 printed fields, choose
   **Accept** or **Reject (anomaly)**, then click **Finish document**. Leave absent fields blank;
   preserve printed date format and decimal strings. Practice all three layouts (three documents).
4. With Practice still checked, choose **assisted**. **Practice extraction: demo** is available to
   learn the controls without quota; these fixture timings are tagged separately and excluded.
   For realistic practice, choose **gemini** only when quota is available, review every proposed
   field, correct it against the PDF and finish. The same three practice PDFs can be reused across
   practice methods, but none appears in the measured set. Do not mix any practice into results.
5. After warming up, uncheck **Practice run**. Check **I had not read the measured timing documents
   before this study** only if true. The app now chooses the next method automatically; it does
   not let you select easier documents or retry one for a better time.
6. Click **Start next document** only when ready. For a manual task, enter the printed fields
   without assistance. For a Gemini task, wait for extraction, inspect all 12 fields against the
   PDF, make necessary corrections, choose the final decision and click **Finish document**.
   Do not stop an external stopwatch at the moment extraction finishes; the app clock keeps running.
7. If an attempt cannot be finished, click **Record incomplete attempt**. It keeps the elapsed
   duration and known API outcome, with final field/decision scores unassessed. If extraction
   fails for a non-quota reason, either finish by typing manually as an assisted fallback or mark
   it incomplete; the failed API call and its wait remain part of that attempt. Do not discard it
   and substitute a successful repeat. A quota/credit stop is saved as incomplete automatically.
8. After a quota stop, pause collection and wait. The checkbox **I have confirmed available Gemini
   quota after a previous quota stop** is an explicit operator confirmation, not a quota detector.
   Check it only after confirming an actual reset/allowance. Disclose the break during validation.
9. Between tasks, take breaks only before clicking Start. Within an attempt, the clock has no pause.
   If interrupted, record the attempt as incomplete rather than subtracting time afterward.
   Do not navigate to other app pages, inspect prior answers or do unrelated work while timing.
10. If the browser/session is lost, return with the same alias. Click **Record interrupted attempts**
    when offered. The durable start record survives, but a lost monotonic clock cannot supply a
    valid end time: its duration stays unknown. Do not replace it with a guessed duration.
11. Continue through all **12 measured tasks**, accounting for incomplete attempts too. Stop once
    the plan is finished. The timing page records measurements only; it does not post invoices or
    change review decisions in the demo database.
12. Tell me collection is complete, confirm the alias/study/order group and disclose interruptions,
    prior exposure, fallback choices and any quota break. The default raw evidence is already local
    in `runtime/timings.csv`. Do not commit or publish that file. Do not edit away slow/error rows.

## Comparable sets and order

The primary pilot deliberately uses ordinary invoices, excluding anomalies and credit notes,
which cannot be balanced with only one credit note and two anomalies in this corpus. Each method
gets two documents in each of three layouts. All have the same field schema and date/amount
format conventions. Documents in a pair are different; layout matching controls some difficulty
but does not make their contents identical.

| Pair | Layout | Group A manual / Gemini document | Group A first method | Group B first method |
| --- | --- | --- | --- | --- |
| 1 | 1 | NC-0010 / NC-0013 | Manual | Gemini |
| 2 | 2 | NC-0011 / NC-0014 | Gemini | Manual |
| 3 | 3 | NC-0012 / NC-0015 | Manual | Gemini |
| 4 | 1 | NC-0016 / NC-0019 | Gemini | Manual |
| 5 | 2 | NC-0017 / NC-0020 | Manual | Gemini |
| 6 | 3 | NC-0018 / NC-0021 | Gemini | Manual |

Group B also swaps which document in each pair goes to manual versus Gemini. Each participant
sees each measured PDF once. Practice uses NC-0001, NC-0002 and NC-0003 from the separate corpus.
No measured filenames or field values are revealed before their timers start; the planned list
above is for reproducibility, not permission to read the PDFs early.

This is a small convenience pilot: six planned attempts per method per participant, clean
one-page text PDFs, GBP only, and no anomaly/credit-note timing generalization. Familiarity with
supplier names, practice PDFs, and the overall workflow can still carry over. Counterbalancing
reduces learning/order effects; it does not eliminate them. More unseen document sets and more
participants would be needed for a broad productivity claim.

## Timer and outcome definitions

The monotonic clock starts in the Start handler **before** the durable event write, PDF loading
and API call. It ends after the form's final submission has reached the server and the submitted
fields/decision have been processed, just before saving the final CSV event. It includes extraction
wait, PDF display time, human reading, review, correction, fallback entry and final submission.
Final CSV disk-write time is excluded. It measures this timing task, not production ledger posting,
payments, exports or a person's whole working day.

The raw CSV is an append-only event log. Loading collapses updates by attempt ID so a Start,
extraction update and Finish count as one attempt. Duplicate final events or changed attempt
identity cause validation to fail. A per-attempt form key prevents fields leaking into the next
document. Failed input/provider messages and extracted/entered values are never written to timing
evidence; only controlled failure categories, scores and metadata are stored.

Final field errors use exact printed strings, forgiving outer whitespace only. Blank/missing
matches blank/missing. Wrong decisions are scored separately using the accounting validation
rules against printed truth. A completed but wrong attempt is still included in completed-time
statistics: accuracy must not be hidden by retaining only correct completions. Incomplete attempts
have no final error score; unassessed does not mean zero errors. Unknown extraction outcomes after
session loss are distinct from known API failures. Corrections count final changed fields when a
proposal was returned, not keystrokes; failed-API fallback corrections are unassessed.

## After collection: validation and publication

No observation file exists yet in this workspace, so there is no timing summary or time-saved
claim to publish. I will validate the supplied observations before generating a measured result:

- Check the alias/study/cohort, matching corpus fingerprint, all 12 plan slots and unique attempt
  identities. Check your account of prior exposure and interruptions; CSV alone cannot verify it.
- Reject non-finite/negative durations, extraction wait longer than total duration, invalid flags,
  statuses, error counts or method/mode combinations. Recover unresolved starts explicitly in the
  app; never fabricate their durations. Preserve all raw evidence locally.
- Keep manual/none, assisted/gemini and assisted/demo descriptive groups separate. Legacy rows
  without plan evidence are descriptive only; they cannot establish a fair percentage comparison.
- Report attempted, completed, incomplete and unresolved sample sizes; median, inclusive Q1/Q3
  and min/max for completed durations; known incomplete durations separately; unknown duration
  counts; final field/document and decision errors; API failures and unknown API outcomes.
- The primary comparison uses only pairs where both attempts completed, after the full plan is
  accounted for. Report how many pairs were excluded for incompletion. This can bias the time
  comparison toward successful attempts; attempt completion/error counts stay visible alongside it.

Then run:

```powershell
.venv\Scripts\python.exe scripts\summarize_timings.py
```

It validates the CSV, refuses unresolved measured attempts, writes nothing for absent/practice-only
data, and writes only aggregate `results/timing_summary.json` and `.md`. If the full comparable
plan is unavailable, it gives descriptive statistics and an explicit no-comparison explanation.
Use `--input PATH` only for a separately validated private CSV; it is not a way to drop failures.

Define **percentage time reduction** as:

```
100 × (median manual seconds − median Gemini-assisted seconds) / median manual seconds
```

Both medians are from the same set of completed matched pairs. This is a difference between
medians, not the median of per-pair percentages, a mean-based reduction or a population estimate.
A negative percentage means assisted entry was slower. Demo fixture times never enter this value.

After validating real measurements, update the README with sample sizes, completed-pair count,
medians/spread, errors/completion and this defined reduction, alongside the small synthetic pilot
and completion-bias limitations. Commit only the aggregate summary files and relevant safe code/
documentation; keep raw CSVs, operator aliases, timestamps, corpus files and notes ignored. Do not push.
