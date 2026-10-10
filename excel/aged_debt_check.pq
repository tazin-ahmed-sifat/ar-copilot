// AgedDebtCheck: compares the AgedDebtPQ query with the AgedDebt table exported by
// Python. It returns only the rows that differ, so an empty result means the two
// implementations agree. Amounts are compared to the penny.
let
    Columns = {"customer", "document_number", "due_date", "total", "payments", "credits",
               "balance", "days_overdue", "bucket"},
    Money = {"total", "payments", "credits", "balance"},

    Normalise = (rows as table) as table =>
        let
            Selected = Table.SelectColumns(Table.SelectRows(rows, each [document_number] <> null), Columns),
            Typed = Table.TransformColumnTypes(Selected, {{"due_date", type date}, {"days_overdue", Int64.Type}}),
            Rounded = Table.TransformColumns(Typed, List.Transform(Money, (name) => {name, each Number.Round(_, 2), type number}))
        in
            Rounded,

    FromPython = Normalise(Excel.CurrentWorkbook(){[Name = "AgedDebt"]}[Content]),
    FromPowerQuery = Normalise(AgedDebtPQ),

    Joined = Table.Join(
        Table.PrefixColumns(FromPython, "python"), {"python.customer", "python.document_number"},
        Table.PrefixColumns(FromPowerQuery, "pq"), {"pq.customer", "pq.document_number"},
        JoinKind.FullOuter
    ),
    Differences = Table.SelectRows(Joined, (row) =>
        List.AnyTrue(List.Transform(Columns, (name) =>
            Record.Field(row, "python." & name) <> Record.Field(row, "pq." & name))))
in
    Differences
