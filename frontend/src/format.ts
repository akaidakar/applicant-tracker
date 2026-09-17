const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso))
}

// <input type="date"> gives "2026-09-17" with no time or zone. Turn it into
// the start or end of that day in the browser's zone, so "before 17 Sep"
// still includes 17 September.
export function dayBoundary(day: string, edge: 'start' | 'end'): string | undefined {
  if (!day) return undefined
  const [year, month, date] = day.split('-').map(Number)
  const local =
    edge === 'start'
      ? new Date(year, month - 1, date, 0, 0, 0, 0)
      : new Date(year, month - 1, date, 23, 59, 59, 999)
  return local.toISOString()
}
