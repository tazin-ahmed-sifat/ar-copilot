// AgedDebtPythonSource: the AgedDebt table exported by Python, as its own query.
// AgedDebtCheck references this query instead of reading the workbook directly; combining
// workbook access and another query in one step raises Excel's Formula.Firewall error.
let
    Source = Excel.CurrentWorkbook(){[Name = "AgedDebt"]}[Content]
in
    Source
