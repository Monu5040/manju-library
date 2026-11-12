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

const compactNumber = new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 1 })
const wholeNumber = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

/**
 * Short amounts for chart axes and labels: ₹950, ₹9,500, ₹12K, ₹1.2L. `compact` shortens
 * small amounts too (₹5K), so every tick on an axis that reaches ₹10K reads the same way.
 */
export function formatMoneyShort(amount: number, compact = false): string {
  const sign = amount < 0 ? '−' : ''
  const value = Math.abs(amount)
  return `${sign}₹${value < 10_000 && !compact ? wholeNumber.format(value) : compactNumber.format(value)}`
}

const monthYear = new Intl.DateTimeFormat('en-IN', { month: 'short', year: 'numeric' })
const dayMonth = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' })

function localDate(iso: string): Date {
  const [year, month, date] = iso.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, date)
}

/** "Nov 2026" */
export function formatMonth(iso: string): string {
  return monthYear.format(localDate(iso))
}

/** "11 Nov" */
export function formatDayMonth(iso: string): string {
  return dayMonth.format(localDate(iso))
}

const weekdayDayMonth = new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })

/** "Thursday, 12 November" */
export function formatLongDate(iso: string): string {
  return weekdayDayMonth.format(localDate(iso))
}

/** "Good morning" before noon, "Good afternoon" until 5 PM, then "Good evening". */
export function greeting(now: Date = new Date()): string {
  const hour = now.getHours()
  if (hour >= 4 && hour < 12) {
    return 'Good morning'
  }
  return hour >= 12 && hour < 17 ? 'Good afternoon' : 'Good evening'
}

export function firstName(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] ?? ''
}
