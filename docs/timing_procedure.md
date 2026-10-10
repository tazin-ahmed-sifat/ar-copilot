# Collecting manual versus Ollama-assisted timings

This procedure measures actual human entry/review time. The saved extraction evaluation is not a timing study and does not support a time-savings claim. Ollama is the sole real LLM provider, using qwen3:8b at http://127.0.0.1:11434; fixture replay is separate practice only.

## Preparation

```powershell
.\.venv\Scripts\python.exe scripts\prepare_timing_documents.py
```

This creates a separate synthetic corpus under ignored runtime/timing_data/. It does not create observations, call Ollama or change the review database. Keep the corpus unseen by measured participants, and do not publish raw timing CSVs or operator aliases. Use one browser tab per participant.

Check that Ollama and qwen3:8b are running before live practice. No key or cloud quota is needed. Measured tasks use Ollama automatically; there is no provider selection or cloud fallback. The timer includes extraction wait, reading, review, correction and final submission.

## Collection

1. Open **Time a document**, enter an operator alias and study code, and select order group A or B. Keep that group throughout the study.
2. Start with **Practice run** enabled. Choose manual or assisted practice. Assisted practice defaults to actual Ollama extraction; **Replay offline demo fixtures for practice** explicitly selects fixture replay. All practice is excluded from measured comparisons.
3. Disable practice only for unseen measured documents. Confirm no prior exposure. The app follows the fixed 12-task counterbalanced plan below.
4. Press **Start next document**. Manual tasks require entry from the PDF. Ollama-assisted tasks require checking all twelve returned fields against the PDF, correcting errors and resolving the appropriate accept/reject decision.
5. Press **Finish document** when review and entry are complete. The app scores exact printed strings and decision accuracy after submission; ground-truth values are not displayed to the participant or passed to the model.
6. On extraction failure, either finish manually within the assisted attempt or select **Record incomplete attempt**. Failures and elapsed wait stay recorded. Do not silently substitute a successful repeat. Local model/server failure does not disable Microsoft 365 automation.
7. If a session is lost, record the unfinished attempt as interrupted. Its duration is unknown, not zero. Preserve raw attempt events in runtime/timings.csv.

## Counterbalanced plan

Each participant completes six manual and six assisted tasks, matched by layout with different invoices. Practice uses NC-0001 to NC-0003 and is excluded from the measured plan.

| Pair | Layout | Group A manual / Ollama document | Group A first method | Group B first method |
| --- | --- | --- | --- | --- |
| 1 | 1 | NC-0010 / NC-0013 | Manual | Ollama |
| 2 | 2 | NC-0011 / NC-0014 | Ollama | Manual |
| 3 | 3 | NC-0012 / NC-0015 | Manual | Ollama |
| 4 | 1 | NC-0016 / NC-0019 | Ollama | Manual |
| 5 | 2 | NC-0017 / NC-0020 | Manual | Ollama |
| 6 | 3 | NC-0018 / NC-0021 | Ollama | Manual |

Group B swaps the manual/assisted document assignment as well as first method. No document is repeated within a participant's study. The app refuses known prior exposure. Record interruptions and fallback choices; incomplete/unresolved attempts remain in counts.

## Analysis and privacy

```powershell
.\.venv\Scripts\python.exe scripts\summarize_timings.py
```

The script writes aggregate summaries locally only when measurements exist and no attempt remains unresolved. Keep manual/none, assisted/ollama and assisted/demo groups separate. Historical extraction-mode rows remain locally readable and descriptive; they are excluded from the current Ollama comparison. Different corpus/model sets must be analysed separately. No historical row is relabelled or migrated automatically.

A percentage comparison requires all twelve planned tasks per participant, valid cohort/corpus metadata and matched completed pairs. Incomplete pairs are excluded from medians but retained in counts. The formula is:

```text
100 * (median manual seconds - median Ollama-assisted seconds) / median manual seconds
```

Negative values mean assisted entry was slower. Report field errors, decision errors, corrections, runtime failures, completion rates and incomplete attempts alongside speed. Different invoices matched by layout form a synthetic pilot, not a causal experiment; completion bias remains. Only actually measured human timings may support a labelled Ollama-assisted timing result.

Internet access for optional OneDrive/Power Automate/email remains independent of this timing study. See [Microsoft 365 workflow](microsoft365_onedrive.md).
