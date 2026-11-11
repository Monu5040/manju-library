import { todayIso } from './format'

/** Date-range presets shared by the analytics and ledger pages. Dates are yyyy-mm-dd. */
export const RANGE_PRESETS = [
  { key: 'this-month', label: 'This month' },
  { key: 'last-month', label: 'Last month' },
  { key: 'last-3-months', label: 'Last 3 months' },
  { key: 'this-fy', label: 'This financial year' },
  { key: 'last-12-months', label: 'Last 12 months' },
  { key: 'custom', label: 'Custom dates' },
] as const

export type RangePreset = (typeof RANGE_PRESETS)[number]['key']

export type DateRange = { from: string; to: string }

function iso(year: number, monthIndex: number, day: number): string {
  // Date handles month and year overflow (month -1 is last December, day 0 a month's end).
  const date = new Date(year, monthIndex, day)
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}

export function presetRange(preset: Exclude<RangePreset, 'custom'>, today: string = todayIso()): DateRange {
  const [year, month] = today.split('-').map(Number)
  const m = month - 1
  switch (preset) {
    case 'last-month':
      return { from: iso(year, m - 1, 1), to: iso(year, m, 0) }
    case 'last-3-months':
      return { from: iso(year, m - 2, 1), to: today }
    case 'this-fy':
      // India's financial year runs from 1 April to 31 March.
      return { from: iso(m >= 3 ? year : year - 1, 3, 1), to: today }
    case 'last-12-months':
      return { from: iso(year, m - 11, 1), to: today }
    default:
      return { from: iso(year, m, 1), to: today }
  }
}

/** The range in the page's search params: a preset (default this month) or custom dates. */
export function rangeFromParams(params: URLSearchParams): { preset: RangePreset; range: DateRange } {
  const preset = (RANGE_PRESETS.find((p) => p.key === params.get('range'))?.key ?? 'this-month') as RangePreset
  if (preset === 'custom') {
    const fallback = presetRange('this-month')
    return { preset, range: { from: params.get('from') || fallback.from, to: params.get('to') || fallback.to } }
  }
  return { preset, range: presetRange(preset) }
}
