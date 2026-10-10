/** Local reference for a serialized OneDrive JSON journal, not a cloud connection.
 * The flow must durably save/read back the returned journal BEFORE sending.
 * This module intentionally has no mail transport and performs no network I/O.
 */
export function reserve(journal, reportingDate, recipient, verifiedRecipient, runId) {
  if (!Array.isArray(journal) || !/^\d{4}-\d{2}-\d{2}$/.test(reportingDate)
      || !Number.isFinite(Date.parse(reportingDate))
      || new Date(reportingDate).toISOString().slice(0, 10) !== reportingDate
      || typeof recipient !== 'string' || typeof verifiedRecipient !== 'string'
      || !verifiedRecipient || recipient.trim().toLowerCase() !== verifiedRecipient.trim().toLowerCase()
      || !/^[^\s@;,|]+@[^\s@;,|]+$/.test(recipient.trim())
      || typeof runId !== 'string' || !runId) throw new Error('Invalid reservation input');
  const normalized = recipient.trim().toLowerCase();
  const key = `overdue|${reportingDate}|${normalized}`;
  for (const entry of journal) {
    if (!entry || typeof entry.key !== 'string' || !entry.key
        || !['Pending', 'Sent', 'Unknown'].includes(entry.state)
        || typeof entry.runId !== 'string' || !entry.runId) throw new Error('Invalid journal');
  }
  if (new Set(journal.map(entry => entry.key)).size !== journal.length) throw new Error('Duplicate journal keys');
  if (journal.some(entry => entry.key === key)) return { allowed: false, key, journal };
  return { allowed: true, key, journal: [...journal, { key, state: 'Pending', runId }] };
}

export function recordOutcome(journal, key, runId, outcome) {
  // Any email error, timeout or cancellation is Unknown; it never releases the key.
  if (!['Sent', 'Unknown'].includes(outcome)) throw new Error('Invalid outcome');
  const matches = journal.filter(entry => entry.key === key);
  if (matches.length !== 1 || matches[0].runId !== runId || matches[0].state !== 'Pending') {
    throw new Error('Reservation not owned or already finalized');
  }
  return journal.map(entry => entry.key === key ? { ...entry, state: outcome } : entry);
}
