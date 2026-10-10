// Read-only Office Script. Paste into Excel Web > Automate > New Script.
// Pass LondonToday from Power Automate; never infer it from this runtime's timezone.
interface OverdueRow {
  customer: string;
  document_number: string;
  due_date: string;
  balance: number;
  days_overdue: number;
  bucket: string;
}
interface ValidationResult {
  valid: boolean;
  reason: string;
  reportingDate: string;
  tableRows: number;
  overdueRows: OverdueRow[];
}

function main(workbook: ExcelScript.Workbook, londonToday: string,
              paginationThreshold: number = 5000): ValidationResult {
  const rejected: ValidationResult = {
    valid: false, reason: 'invalid_workbook', reportingDate: '', tableRows: 0, overdueRows: []
  };
  try {
    if (!validISO(londonToday) || !Number.isInteger(paginationThreshold)
        || paginationThreshold < 1 || paginationThreshold > 5000) return rejected;
    const dateRange = workbook.getNamedItem('ReportingDate').getRange();
    if (dateRange.getRowCount() !== 1 || dateRange.getColumnCount() !== 1) return rejected;
    const reportingDate = excelDate(dateRange.getValue());
    if (reportingDate !== londonToday) {
      return { ...rejected, reason: 'stale_or_future_reporting_date', reportingDate };
    }
    const table = workbook.getTable('AgedDebt');
    const headers = table.getHeaderRowRange().getValues()[0].map(value => String(value));
    const required = ['customer', 'document_number', 'due_date', 'balance', 'days_overdue', 'bucket'];
    if (required.some(name => headers.filter(header => header === name).length !== 1)) return rejected;
    const values = table.getRangeBetweenHeaderAndTotal().getValues();
    // Conservative cap: stop even at the threshold rather than risk truncation.
    if (values.length >= paginationThreshold) return { ...rejected, reason: 'pagination_capacity' };
    const overdueRows: OverdueRow[] = [];
    const seen: string[] = [];
    for (const valuesRow of values) {
      if (valuesRow.every(value => value === '')) continue; // exporter keeps one blank template row
      const cell = (name: string): string | number | boolean => valuesRow[headers.indexOf(name)];
      const customer = cell('customer');
      const document = cell('document_number');
      const balance = cell('balance');
      const days = cell('days_overdue');
      const bucket = cell('bucket');
      if (typeof customer !== 'string' || !customer.trim()
          || typeof document !== 'string' || !document.trim()
          || typeof balance !== 'number' || !Number.isFinite(balance)
          || Math.abs(balance * 100 - Math.round(balance * 100)) > 0.000001
          || typeof days !== 'number' || !Number.isInteger(days)) return rejected;
      const dueDate = excelDate(cell('due_date'));
      const expectedDays = Math.round((Date.parse(reportingDate) - Date.parse(dueDate)) / 86400000);
      const expectedBucket = expectedDays <= 0 ? 'current' : expectedDays <= 30 ? '1–30'
        : expectedDays <= 60 ? '31–60' : expectedDays <= 90 ? '61–90' : '91+';
      // The exporter clamps days_overdue to zero for current balances.
      if (days !== Math.max(0, expectedDays) || bucket !== expectedBucket) return rejected;
      const identity = JSON.stringify([customer, document]);
      if (seen.includes(identity)) return rejected;
      seen.push(identity);
      if (balance > 0 && expectedDays > 0) overdueRows.push({
        customer, document_number: document, due_date: dueDate,
        balance, days_overdue: days, bucket: String(bucket)
      });
    }
    return { valid: true, reason: 'validated', reportingDate, tableRows: values.length, overdueRows };
  } catch {
    // No exception text or workbook balances escape on rejection.
    return rejected;
  }
}

function validISO(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 10) === value;
}

function excelDate(value: string | number | boolean): string {
  if (typeof value === 'string' && validISO(value)) return value;
  // AR Copilot exports the 1900 date system. Reject times, errors and non-date values.
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 60 || value > 2958465) {
    throw new Error('Invalid date');
  }
  return new Date((value - 25569) * 86400000).toISOString().slice(0, 10);
}
