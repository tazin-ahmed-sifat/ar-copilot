// AgedDebtPQ: rebuilds the AgedDebt table from the exported PostedReceivables and
// Payments tables and the ReportingDate name, using the same rules as
// ar_copilot.core.aged_debt:
//   - only approved documents dated on or before the reporting date count
//   - payments count when dated on or before the reporting date and booked to the
//     same customer and invoice number
//   - approved credit notes reduce the invoice they are linked to, same customer only
//   - balance = total - payments + credits (credits are negative); negatives are kept
//   - days overdue = reporting date - due date; due on or after the reporting date is current
//   - buckets: current, 1–30, 31–60, 61–90, 91+
// Amounts use Currency.Type (fixed four decimal places) so sums don't pick up float noise.
let
    Source = Excel.CurrentWorkbook(),
    ReportingDate = Date.From(Source{[Name = "ReportingDate"]}[Content]{0}[Column1]),
    Buckets = {"current", "1–30", "31–60", "61–90", "91+"},

    // Empty exported tables keep one blank row, so drop rows without a key.
    PostedRaw = Source{[Name = "PostedReceivables"]}[Content],
    Posted = Table.TransformColumnTypes(
        Table.SelectRows(PostedRaw, each [posting_key] <> null and [posting_key] <> "" and [status] = "approved"),
        {{"invoice_date", type date}, {"due_date", type date}, {"total", Currency.Type}}
    ),
    Eligible = Table.SelectRows(Posted, each [invoice_date] <= ReportingDate),
    Invoices = Table.SelectRows(Eligible, each [document_type] = "invoice"),
    Credits = Table.SelectRows(Eligible, each [document_type] = "credit_note"),

    PaymentsRaw = Source{[Name = "Payments"]}[Content],
    Payments = Table.TransformColumnTypes(
        Table.SelectRows(PaymentsRaw, each [payment_id] <> null and [payment_id] <> ""),
        {{"payment_date", type date}, {"amount", Currency.Type}}
    ),
    PaymentsToDate = Table.SelectRows(Payments, each [payment_date] <= ReportingDate),

    // Sum of one column, 0 for no rows (List.Sum of an empty list is null).
    SumColumn = (rows as table, column as text) as number =>
        List.Sum(List.Combine({{0}, Table.Column(rows, column)})),

    PaidFor = (invoice as record) as number =>
        SumColumn(
            Table.SelectRows(PaymentsToDate,
                each [invoice_number] = invoice[document_number] and [customer] = invoice[customer]),
            "amount"),

    CreditedFor = (invoice as record) as number =>
        SumColumn(
            Table.SelectRows(Credits,
                each [linked_invoice] = invoice[document_number] and [customer] = invoice[customer]),
            "total"),

    BucketFor = (days as number) as text =>
        if days <= 0 then "current"
        else if days <= 30 then "1–30"
        else if days <= 60 then "31–60"
        else if days <= 90 then "61–90"
        else "91+",

    WithPayments = Table.AddColumn(Invoices, "payments", PaidFor, Currency.Type),
    WithCredits = Table.AddColumn(WithPayments, "credits", CreditedFor, Currency.Type),
    WithBalance = Table.AddColumn(WithCredits, "balance", each [total] - [payments] + [credits], Currency.Type),
    WithDays = Table.AddColumn(WithBalance, "days", each Duration.Days(ReportingDate - [due_date]), Int64.Type),
    WithOverdue = Table.AddColumn(WithDays, "days_overdue", each List.Max({0, [days]}), Int64.Type),
    WithBucket = Table.AddColumn(WithOverdue, "bucket", each BucketFor([days]), type text),

    // One column per bucket holding the balance in its own bucket and 0 elsewhere.
    WithBucketColumns = List.Accumulate(
        Buckets,
        WithBucket,
        (rows, name) => Table.AddColumn(rows, name, each if [bucket] = name then [balance] else 0, Currency.Type)
    ),

    Result = Table.SelectColumns(
        WithBucketColumns,
        {"customer", "document_number", "due_date", "total", "payments", "credits",
         "balance", "days_overdue", "bucket"} & Buckets
    )
in
    Result
