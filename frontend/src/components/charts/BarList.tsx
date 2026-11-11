export interface BarRow {
  key: string
  label: string
  value: number
  /** The value as printed at the bar's tip, for example "₹1,200" or "14". */
  display: string
  /** Only for ordered groups (such as how long a due has been unpaid). */
  color?: string
  detail?: string
}

/**
 * Horizontal bars on one baseline, labelled at the tip: one colour for every bar, or an
 * ordered ramp for ordered groups. The label and value are real text for screen readers.
 */
export function BarList({ rows, label, empty = 'Nothing to show yet.' }: { rows: BarRow[]; label: string; empty?: string }) {
  const max = Math.max(0, ...rows.map((r) => r.value))
  if (!rows.length || max === 0) {
    return <p className="py-4 text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul aria-label={label} className="space-y-2.5">
      {rows.map((row) => (
        <li key={row.key} className="grid grid-cols-[minmax(5.5rem,8.5rem)_1fr] items-center gap-3 text-sm">
          <span className="min-w-0 text-muted-foreground">
            <span className="block truncate" title={row.label}>
              {row.label}
            </span>
            {row.detail && <span className="block text-xs">{row.detail}</span>}
          </span>
          <span className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden="true"
              className="h-3.5 shrink-0 rounded-r-[4px] transition-opacity hover:opacity-80"
              style={{
                width: `calc((100% - 5.5rem) * ${row.value / max})`,
                minWidth: row.value > 0 ? 2 : 0,
                background: row.color ?? 'var(--chart-income)',
              }}
            />
            <span className="shrink-0 font-medium tabular-nums">{row.display}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}
