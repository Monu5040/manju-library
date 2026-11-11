import { ArrowDownRight, ArrowUpRight, Download } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * A card holding one chart, with a Chart / Table switch: the table is the same numbers in
 * rows, for screen readers, printing and anyone who prefers figures.
 */
export function ChartCard({
  title,
  description,
  actions,
  chart,
  table,
  className,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
  chart: ReactNode
  table?: ReactNode
  className?: string
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const option = (value: 'chart' | 'table', label: string) => (
    <button
      type="button"
      aria-pressed={view === value}
      onClick={() => setView(value)}
      className={cn(
        'rounded px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground',
        view === value && 'bg-muted text-foreground',
      )}
    >
      {label}
    </button>
  )
  return (
    <Card className={cn('min-w-0', className)}>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <CardTitle className="text-lg">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        <div className="flex items-center gap-2 print:hidden">
          {table && (
            <div role="group" aria-label={`Show ${title.toLowerCase()} as`} className="inline-flex rounded-md border p-0.5">
              {option('chart', 'Chart')}
              {option('table', 'Table')}
            </div>
          )}
          {actions}
        </div>
      </CardHeader>
      <CardContent>{view === 'table' && table ? table : chart}</CardContent>
    </Card>
  )
}

/** Download links for analytics tables (Excel or CSV), keeping the page's date range. */
export function ExportLinks({ sections, params }: { sections: { key: string; label: string }[]; params: Record<string, string> }) {
  const href = (section: string, fileType: string) =>
    `/api/admin/analytics/export/?${new URLSearchParams({ ...params, section, file_type: fileType }).toString()}`
  return (
    <details className="relative">
      <summary
        aria-label="Export"
        className="inline-flex h-8 cursor-pointer list-none items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium hover:bg-muted [&::-webkit-details-marker]:hidden"
      >
        <Download aria-hidden="true" className="size-3.5" /> Export
      </summary>
      <div className="absolute right-0 z-20 mt-1 w-60 rounded-md border bg-card p-1 shadow-md">
        {sections.map((s) => (
          <div key={s.key} className="px-2 py-1.5">
            <p className="text-xs text-muted-foreground">{s.label}</p>
            <div className="mt-1 flex gap-3 text-sm">
              <a className="font-medium text-primary hover:underline" href={href(s.key, 'xlsx')}>
                Excel
              </a>
              <a className="font-medium text-primary hover:underline" href={href(s.key, 'csv')}>
                CSV
              </a>
            </div>
          </div>
        ))}
      </div>
    </details>
  )
}

/**
 * A key number with its change against the previous period. The arrow and the words carry
 * the direction; colour only adds whether that direction is good.
 */
export function StatTile({
  label,
  value,
  hint,
  current,
  previous,
  upIsGood = true,
  format,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  current?: number
  previous?: number
  upIsGood?: boolean
  format?: (n: number) => string
}) {
  let delta: ReactNode = null
  if (current !== undefined && previous !== undefined) {
    if (previous === 0) {
      delta = <span>Previous period: {format ? format(0) : 0}</span>
    } else {
      const change = Math.round(((current - previous) / Math.abs(previous)) * 100)
      const up = change > 0
      const good = change === 0 ? null : up === upIsGood
      const Icon = up ? ArrowUpRight : ArrowDownRight
      delta = (
        <span className={cn('inline-flex items-center gap-1', good === true && 'text-success', good === false && 'text-destructive')}>
          {change !== 0 && <Icon aria-hidden="true" className="size-3.5" />}
          {change === 0 ? 'Same as' : `${up ? 'Up' : 'Down'} ${Math.abs(change)}% on`} the previous period
        </span>
      )
    }
  }
  return (
    <div className="rounded-xl border bg-card p-5">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold sm:text-3xl">{value}</dd>
      {(delta || hint) && (
        <dd className="mt-1 space-y-0.5 text-xs text-muted-foreground">
          {delta && <p>{delta}</p>}
          {hint && <p>{hint}</p>}
        </dd>
      )}
    </div>
  )
}
