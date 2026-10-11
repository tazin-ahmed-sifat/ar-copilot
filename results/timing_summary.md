# Time per document

Generated from private local observations by `scripts/summarize_timings.py`; do not edit by hand.
Practice attempts excluded: 1.
Completed durations include extraction wait, review, correction and final submission. Incomplete/unresolved attempts are retained but excluded from completed-time medians.

| Method | Attempts | Completed | Incomplete | Unresolved | Operators | Median s | Q1-Q3 s | Range s | Field errors | Decision errors | API failures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| assisted/ollama | 6 | 6 | 0 | 0 | 1 | 7.0 | 5.3 to 8.3 | 3.7 to 13.4 | 0 (0.0% of completed fields) | 0 (0 unscored) | 0 |
| manual/none | 6 | 6 | 0 | 0 | 1 | 85.0 | 76.4 to 90.6 | 61.2 to 91.0 | 6 (8.3% of completed fields) | 0 (0 unscored) | 0 |

| Method | Median extraction wait, completed (s) | Final fields corrected | API-failure completions with unassessed corrections | Unknown extraction outcomes |
| --- | --- | --- | --- | --- |
| assisted/ollama | 2.2 | 0 | 0 | 0 |
| manual/none | 0.0 | 0 | 0 | 0 |

Matched completed pairs: 6 across 1 participant(s); 0 incomplete pairs excluded from this time comparison. Manual median 85.0 s, Ollama-assisted median 7.0 s. Matched manual Q1-Q3 76.4 to 90.6 s, range 61.2 to 91.0 s; matched assisted Q1-Q3 5.3 to 8.3 s, range 3.7 to 13.4 s. Difference between the two medians (manual minus assisted): 78.1 s. Median of the per-pair differences: 74.5 s. Percentage time reduction: 91.8%. Definition: 100 * (manual median - Ollama-assisted median) / manual median on matched completed pairs; negative means slower. Different invoices matched by layout; synthetic pilot, no causal claim. Incomplete pairs excluded from medians but retained in attempt counts; completion bias remains.

Demo fixtures and legacy measurements are descriptive only and excluded from the live comparison. Errors are reported alongside speed; API failures are distinct from final field/decision errors.
