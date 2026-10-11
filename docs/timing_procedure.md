# Timing study procedure

The extraction evaluation measures how long the model takes, not how long a person takes. This
study measures the person: the time to enter a document by hand, compared with the time to
check and correct the model's draft of a similar document. A one-person pilot was run on
11 October 2026. Its results and caveats are in the [README](../README.md#timing-pilot).

## Design

- **Documents.** A separate fictional set in `runtime/timing_data/`, generated with a different
  seed from the demo set. It has the same three layouts, but every value is different.
- **Practice.** NC-0001 to NC-0003, up to three per method. Practice attempts are saved but
  always excluded from results.
- **Measured tasks.** Twelve tasks in six pairs. Each pair is two different invoices with the
  same layout, one entered by hand and one with Ollama assistance. Each layout appears in two
  pairs.
- **Order.** Within each pair, the method that goes first alternates (manual first, then
  assisted first, and so on), so neither method always benefits from warm-up or learning. Group
  B mirrors group A, both in which invoice gets which method and in which method goes first.

| Pair | Layout | Group A: manual / assisted | Group A goes first with | Group B goes first with |
| --- | --- | --- | --- | --- |
| 1 | 1 | NC-0010 / NC-0013 | Manual | Assisted |
| 2 | 2 | NC-0011 / NC-0014 | Assisted | Manual |
| 3 | 3 | NC-0012 / NC-0015 | Manual | Assisted |
| 4 | 1 | NC-0016 / NC-0019 | Assisted | Manual |
| 5 | 2 | NC-0017 / NC-0020 | Manual | Assisted |
| 6 | 3 | NC-0018 / NC-0021 | Assisted | Manual |

**What the clock covers.** It starts when you press **Start next document**. On assisted tasks
that includes waiting for Ollama. It stops when **Finish document** has been processed, so it
also covers reading, typing or correcting, choosing the decision and submitting.
`tests/test_timing_page.py` checks this with a fake clock.

**What is recorded for each attempt.** Total seconds, the extraction wait, field errors (exact
match against the printed value), how many model fields you changed, whether your accept/reject
decision was right, and whether extraction failed and why. Abandoned and interrupted attempts
are saved as incomplete and are never overwritten by a later retry.

**Known weaknesses.**

- With one participant, there are six pairs.
- All twelve measured documents are clean invoices, so the decision check can only catch a
  wrong *reject*. It can't catch a missed anomaly.
- The layouts and customers are already familiar from the demo set.
- After each task the page shows your time and error count. That feedback may make later tasks
  more careful, but it applies to both methods.

## Before you start

1. Ollama is running and the model is listed:

   ```powershell
   ollama list
   ```

2. Timing documents exist (`runtime/timing_data/` is already there in this workspace). On a
   fresh copy, run:

   ```powershell
   .\.venv\Scripts\python.exe scripts\prepare_timing_documents.py
   ```

   The script refuses to overwrite an existing set. If you have already opened the measured PDFs
   (NC-0010 to NC-0021 in that folder), rename `runtime/timing_data` to set it aside and run the
   script again, because a seen set would bias the results.
3. Start the app in one browser tab only, and allow about 30 minutes without breaks. If the gap
   between two assisted tasks is more than five minutes, Ollama unloads the model, and the next
   wait includes reloading it.

## Collecting

On **Time a document**:

1. Enter an **Operator alias** that isn't your name, such as `P01`. Leave **Study code** as
   `pilot-1`. Choose **Order group** A or B (toss a coin), and keep it for the whole study.
2. **Practice.** Leave **Practice run (excluded from results)** ticked.
   1. Choose **Practice method: manual**. Press **Start next document**. Type all twelve fields
      exactly as printed, leave **Decision** on **Accept**, and press **Finish document**. Do this
      two or three times.
   2. Choose **Practice method: assisted**, leaving the fixture checkbox unticked so real Ollama
      runs. Press **Start next document**, check each pre-filled field against the PDF, fix any
      mistakes, and press **Finish document**. Do this two or three times. Make your last
      practice an assisted one, so the model is loaded when measurement starts.
3. **Switch to measured.** Untick **Practice run**. Tick **I had not read the measured timing
   documents before this study**, but only if that's true. The blue line should say
   `Next: key by hand - task 1/12, layout 1` (group A) or `Next: ollama extraction and review -
   task 1/12, layout 1` (group B).
4. **For each of the twelve tasks:**
   1. Press **Start next document**.
   2. Manual task: the fields are empty, so type all twelve from the PDF. Assisted task: the
      fields are filled in by the model, so compare each one with the PDF and fix what's wrong.
   3. Choose **Accept**, or **Reject (anomaly)** if the document looks wrong.
   4. Press **Finish document** as soon as you're done. A toast shows the time and error count.
   5. Go straight on to the next task.
5. When all twelve are done, the page says the plan is finished, and **Start next document**
   stays disabled.

How to enter values so they score correctly:

- Copy dates in the printed format (`2026-05-03`, `04/07/2026` or `29 May 2026`).
- Type amounts as printed, without `£` or commas.
- **Document type** is `invoice` or `credit_note`.
- Leave **Linked invoice** empty on invoices.

If something goes wrong:

- **Extraction fails.** A warning appears and the clock keeps running. Either type the fields in
  yourself and press **Finish document**, or press **Record incomplete attempt**. Don't start the
  task again. The failure stays in the data either way.
- **The tab closes or reloads mid-task.** Open the page again and type the same operator alias.
  When the page asks, press **Record interrupted attempts**, then carry on. That attempt is saved
  with an unknown duration, and the pair it belongs to is left out of the time comparison.
- **You can't finish a task.** Press **Record incomplete attempt**.

Raw attempts are written to `runtime/timings.csv`, which Git ignores. Don't edit it.

## Summarising

```powershell
.\.venv\Scripts\python.exe scripts\summarize_timings.py
```

This writes `results/timing_summary.json` and `results/timing_summary.md`. They contain counts,
medians, quartiles, ranges, error counts and failure counts only, with no aliases or entered
values. The script refuses to run while there are no measurements or while an attempt is still
open.

The time reduction is calculated on completed matched pairs only:

```text
100 × (median manual seconds − median assisted seconds) / median manual seconds
```

A negative value means assisted entry was slower. Incomplete attempts are still counted, and
reported, but left out of the medians. The result should be read alongside the error counts,
and as a one-person pilot on synthetic documents, not a controlled experiment.
