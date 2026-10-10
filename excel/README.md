# Power Query aged debt

`aged_debt.pq` rebuilds the AgedDebt table inside Excel from three things every exported
aged-debt workbook contains: the `PostedReceivables` and `Payments` tables and the
`ReportingDate` name (cell B2 on the Summary sheet). It follows the same rules as
`ar_copilot.core.aged_debt`, so a finance user can recalculate the buckets for a new
date without Python.

Status: written against the exported table layout; not yet run in Excel. The fixture
below is how to confirm it.

## Fixture

`fixture/` holds a small hand-made case that covers each rule at its boundary:

| Document | What it tests |
| --- | --- |
| FX-01 | due on the reporting date, so current |
| FX-02, FX-03 | 1 and 30 days overdue; a partial payment and a full payment |
| FX-04, FX-05 | 31 and 60 days; a payment dated after the reporting date, a linked credit |
| FX-06, FX-07 | 61 and 90 days; a credit dated after the reporting date, a payment from another customer |
| FX-08 | 91 days; an overpayment that leaves a negative balance |
| FX-09 | invoice dated after the reporting date, so excluded |
| FX-10 | not yet due; a credit from another customer that must not apply |

`expected_aged_debt.csv` is the answer worked out by hand for 10 October 2026.
`tests/test_excel_fixture.py` checks the Python rules against it, and
`aged_debt_fixture.xlsx` is the exporter's output for the same inputs. Rebuild the
workbook after changing the CSVs:

```
python scripts/build_excel_fixture.py
```

## Run and compare in Excel

1. Open `fixture/aged_debt_fixture.xlsx` in Excel for Windows or Mac (Microsoft 365).
2. **Data → Get Data → From Other Sources → Blank Query**. In the Power Query editor choose
   **Advanced Editor**, replace the contents with `aged_debt.pq`, and name the query `AgedDebtPQ`.
3. Add a second blank query from `aged_debt_check.pq` and name it `AgedDebtCheck`.
4. **Close & Load To… → Table → New worksheet** for both.
5. `AgedDebtCheck` should load with no rows. Any row it shows is a document where Power Query
   and Python disagree, with both versions side by side.
6. Cross-check `AgedDebtPQ` against `fixture/expected_aged_debt.csv`: nine rows, FX-09 absent,
   FX-08 at −£40.00.

To age the same data at another date, change Summary!B2 and choose **Data → Refresh All**.
`AgedDebtPQ` follows the new date; the AgedDebt sheet is a Python snapshot and does not, so
`AgedDebtCheck` will then list differences by design.
