# Power Query aged debt

`aged_debt.pq` rebuilds the AgedDebt table inside Excel from three things every exported
aged-debt workbook contains: the `PostedReceivables` and `Payments` tables and the
`ReportingDate` name (cell B2 on the Summary sheet). It follows the same rules as
`ar_copilot.core.aged_debt`, so a finance user can recalculate the buckets for a new
date without Python.

This was checked by hand in Excel desktop against the fixture on 10 October 2026.
AgedDebtCheck returned zero differences, and AgedDebtPQ had nine rows, left out FX-09, and
showed FX-08 with a balance of -£40.00.

`validate_aged_debt.ts` in this folder is an Office Script that isn't used yet; see
[docs/microsoft365.md](../docs/microsoft365.md).

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

1. Open `fixture/aged_debt_fixture.xlsx` in Excel desktop.

2. Choose **Data → Get Data → From Other Sources → Blank Query**.
   Open **Advanced Editor**, replace its contents with `aged_debt.pq`,
   and name the query `AgedDebtPQ`.
   Choose **Close & Load To… → Table → New worksheet**.

3. Create another blank query. In **Advanced Editor**, paste the contents
   of `aged_debt_python_source.pq` and name it `AgedDebtPythonSource`.
   Choose **Close & Load To… → Only Create Connection**.
   This separates workbook access from the comparison query to avoid
   the Formula.Firewall error.

4. Create a third blank query using `aged_debt_check.pq` and name it
   `AgedDebtCheck`.
   Choose **Close & Load To… → Table → New worksheet**.

5. `AgedDebtCheck` should load with no data rows. Any row indicates a
   difference between Power Query and Python, shown side by side.

6. Cross-check `AgedDebtPQ` against `fixture/expected_aged_debt.csv`:
   nine data rows, FX-09 absent, and FX-08's balance at -£40.00.

To age the same data at another date, change `Summary!B2` and choose
**Data → Refresh All**. `AgedDebtPQ` follows the new date.
The AgedDebt sheet remains a Python snapshot, so `AgedDebtCheck`
will then show differences by design.
