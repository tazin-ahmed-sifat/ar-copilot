# Timing study procedure

The extraction evaluation measures how long the model takes, not how long a person takes. To
say anything about time saved, someone has to enter documents by hand and with model
assistance, under the same conditions. The **Time a document** page supports that. **No timings
have been collected yet**, so the project currently makes no time-saving claim.

## Preparation

```powershell
.\.venv\Scripts\python.exe scripts\prepare_timing_documents.py
```

This generates a separate fictional set of documents in `runtime/timing_data/`. It doesn't call
Ollama, record anything or touch the review database. Participants shouldn't see these
documents before they are timed. Make sure Ollama is running, because assisted tasks always use
real extraction.

## Running a session

1. Open **Time a document**. Enter an operator alias and a study code, and pick order group A or
   B. Keep the same group for the whole study.
2. Do a few practice tasks with **Practice run (excluded from results)** ticked. Practice uses
   NC-0001 to NC-0003. Assisted practice uses Ollama unless **Replay offline demo fixtures for
   practice** is ticked.
3. Untick practice and confirm the participant hasn't seen the measured documents. The page
   then works through a fixed plan of twelve tasks.
4. **Start next document** starts the clock. A manual task means typing all twelve fields from
   the PDF. An assisted task means checking the model's fields against the PDF and fixing any
   mistakes. The clock includes waiting for the model.
5. **Finish document** stops the clock. Entries are scored against the printed values only after
   submission, and the participant never sees the ground truth.
6. If extraction fails, either finish the task by hand or choose **Record incomplete attempt**.
   Failed attempts stay in the data and are never replaced with a later successful try.
7. If a session is lost part-way, the page asks for the unfinished attempt to be recorded as
   interrupted before it lets you continue. Its duration is recorded as unknown, not zero.

Raw attempts go to `runtime/timings.csv`, which is not committed.

## The plan

Each participant does six manual and six assisted tasks. Each pair uses two different invoices
with the same layout, and the method that goes first alternates.

| Pair | Layout | Group A: manual / assisted | Group A goes first with | Group B goes first with |
| --- | --- | --- | --- | --- |
| 1 | 1 | NC-0010 / NC-0013 | Manual | Assisted |
| 2 | 2 | NC-0011 / NC-0014 | Assisted | Manual |
| 3 | 3 | NC-0012 / NC-0015 | Manual | Assisted |
| 4 | 1 | NC-0016 / NC-0019 | Assisted | Manual |
| 5 | 2 | NC-0017 / NC-0020 | Manual | Assisted |
| 6 | 3 | NC-0018 / NC-0021 | Assisted | Manual |

Group B swaps which invoice in each pair is manual and which is assisted.

## Summarising

```powershell
.\.venv\Scripts\python.exe scripts\summarize_timings.py
```

This writes `results/timing_summary.json` and `.md`. It refuses to run while there are no
measurements or while any attempt is still unresolved. Medians use completed matched pairs only.
Incomplete attempts are still counted and shown. The headline figure is

```text
100 × (median manual seconds − median assisted seconds) / median manual seconds
```

A negative value means assisted entry was slower. Report it alongside field errors, corrections,
failures and completion rates. With a handful of participants and synthetic documents, this
would be a small pilot, not a controlled experiment.
