const rupees = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
  minimumFractionDigits: 0,
})

const day = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

/** ₹1,23,450 — Indian digit grouping. */
export function formatMoney(amount: number | null | undefined): string {
  return rupees.format(amount ?? 0)
}

/** "11 Nov 2026" from an ISO date (yyyy-mm-dd) without timezone surprises. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) {
    return '—'
  }
  const [year, month, date] = iso.slice(0, 10).split('-').map(Number)
  return day.format(new Date(year, month - 1, date))
}

export function todayIso(): string {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

export function daysLeftLabel(days: number): string {
  if (days < 0) {
    return `Expired ${-days} day${days === -1 ? '' : 's'} ago`
  }
  if (days === 0) {
    return 'Ends today'
  }
  return `${days} day${days === 1 ? '' : 's'} left`
}

export function timeShort(value: string | null): string {
  if (!value) {
    return ''
  }
  const [h, m] = value.split(':').map(Number)
  const suffix = h < 12 ? 'AM' : 'PM'
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${suffix}`
}
