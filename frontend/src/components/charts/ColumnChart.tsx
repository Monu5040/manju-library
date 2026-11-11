import { type KeyboardEvent, useRef, useState } from 'react'
import { formatMoney, formatMoneyShort } from '@/lib/format'
import { useWidth } from './useWidth'

export interface Series {
  key: string
  label: string
  /** A CSS colour, normally a chart token such as var(--chart-income). */
  color: string
}

export interface ColumnPoint {
  key: string
  /** Full name of the period, for the tooltip: "11 Nov 2026", "Nov 2026". */
  label: string
  /** Short axis label: "11 Nov", "Nov". */
  tick: string
  values: Record<string, number>
  /** Extra tooltip lines after the series, for example profit. */
  extra?: { label: string; value: number }[]
}

const PLOT = 220
const TOP = 22 // room for the peak label
const AXIS = 28
const LEFT = 60
const RIGHT = 8
const MAX_BAR = 24
const GAP = 2
const MIN_BAND = 14

function niceMax(value: number): number {
  if (value <= 0) {
    return 1000
  }
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const step = [1, 2, 2.5, 5, 10].find((s) => value <= s * magnitude) ?? 10
  return step * magnitude
}

/** A column with a 4px rounded data end and a square foot on the baseline. */
function columnPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(4, width / 2, height)
  return `M${x},${y + height}V${y + r}A${r},${r} 0 0 1 ${x + r},${y}H${x + width - r}A${r},${r} 0 0 1 ${x + width},${y + r}V${y + height}Z`
}

export function SeriesLegend({ series }: { series: Series[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground" aria-label="Legend">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-2">
          <span aria-hidden="true" className="size-2.5 rounded-[2px]" style={{ background: s.color }} />
          {s.label}
        </li>
      ))}
    </ul>
  )
}

/**
 * Grouped columns over time, one group per period. Hover, or focus the chart and use the
 * arrow keys, to read every series for a period; the card's table view has the same numbers.
 */
export function ColumnChart({ points, series, summary }: { points: ColumnPoint[]; series: Series[]; summary: string }) {
  const box = useRef<HTMLDivElement>(null)
  const available = useWidth(box, 720)
  const [active, setActive] = useState<number | null>(null)

  const width = Math.max(available, LEFT + RIGHT + points.length * MIN_BAND)
  const plotWidth = width - LEFT - RIGHT
  const band = plotWidth / Math.max(points.length, 1)
  const barWidth = Math.max(2, Math.min(MAX_BAR, (band * 0.72 - GAP * (series.length - 1)) / series.length))
  const groupWidth = barWidth * series.length + GAP * (series.length - 1)
  const max = niceMax(Math.max(0, ...points.flatMap((p) => series.map((s) => p.values[s.key] ?? 0))))
  const y = (value: number) => TOP + PLOT - (value / max) * PLOT
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max)
  const tickText = (value: number) => (max >= 10_000 ? formatMoneyShort(value, true) : formatMoney(value))
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(1, Math.floor(plotWidth / 64))))

  // One direct label: the highest value of the first series (the story is income).
  const lead = series[0]
  let peak = -1
  points.forEach((p, i) => {
    if ((p.values[lead.key] ?? 0) > 0 && (peak < 0 || p.values[lead.key] > points[peak].values[lead.key])) {
      peak = i
    }
  })

  const onKey = (event: KeyboardEvent) => {
    if (event.key === 'ArrowRight') {
      setActive((i) => Math.min(points.length - 1, (i ?? -1) + 1))
    } else if (event.key === 'ArrowLeft') {
      setActive((i) => Math.max(0, (i ?? points.length) - 1))
    } else if (event.key === 'Escape') {
      setActive(null)
    } else {
      return
    }
    event.preventDefault()
  }

  const point = active === null ? null : points[active]
  const tipLeft = active === null ? 0 : Math.min(Math.max(LEFT + (active + 0.5) * band - 90, 0), Math.max(width - 180, 0))

  return (
    <div className="space-y-3">
      <SeriesLegend series={series} />
      <div ref={box} className="relative overflow-x-auto">
        <div
          tabIndex={0}
          role="group"
          aria-label={`${summary}. Use the left and right arrow keys to read each period.`}
          className="relative rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring"
          style={{ width }}
          onKeyDown={onKey}
          onFocus={() => setActive((i) => i ?? points.length - 1)}
          onBlur={() => setActive(null)}
          onPointerLeave={() => setActive(null)}
        >
          <svg width={width} height={TOP + PLOT + AXIS} aria-hidden="true" className="block">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={LEFT} x2={LEFT + plotWidth} y1={y(t)} y2={y(t)} stroke={t === 0 ? 'var(--input)' : 'var(--border)'} shapeRendering="crispEdges" />
                <text x={LEFT - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-muted-foreground text-[11px] tabular-nums">
                  {tickText(t)}
                </text>
              </g>
            ))}
            {points.map((p, i) => {
              const x0 = LEFT + i * band + (band - groupWidth) / 2
              return (
                <g key={p.key}>
                  {active === i && <rect x={LEFT + i * band} y={TOP} width={band} height={PLOT} className="fill-muted" />}
                  {series.map((s, j) => {
                    const value = p.values[s.key] ?? 0
                    if (value <= 0) {
                      return null
                    }
                    const height = Math.max(1, (value / max) * PLOT)
                    return <path key={s.key} d={columnPath(x0 + j * (barWidth + GAP), y(value), barWidth, height)} fill={s.color} />
                  })}
                  {i === peak && band >= 30 && (
                    <text x={x0 + barWidth / 2} y={y(p.values[lead.key]) - 6} textAnchor="middle" className="fill-muted-foreground text-[11px] tabular-nums">
                      {formatMoneyShort(p.values[lead.key])}
                    </text>
                  )}
                  {i % labelEvery === 0 && (
                    <text x={LEFT + i * band + band / 2} y={TOP + PLOT + 18} textAnchor="middle" className="fill-muted-foreground text-[11px]">
                      {p.tick}
                    </text>
                  )}
                  <rect x={LEFT + i * band} y={TOP} width={band} height={PLOT + AXIS} fill="transparent" onPointerEnter={() => setActive(i)} />
                </g>
              )
            })}
          </svg>
          {point && (
            <div role="status" className="pointer-events-none absolute top-0 z-10 w-44 rounded-md border bg-card p-2.5 text-xs shadow-md" style={{ left: tipLeft }}>
              <p className="mb-1.5 font-medium">{point.label}</p>
              <ul className="space-y-1">
                {series.map((s) => (
                  <li key={s.key} className="flex items-center gap-2">
                    <span aria-hidden="true" className="h-0.5 w-3 rounded-full" style={{ background: s.color }} />
                    <span className="font-semibold tabular-nums">{formatMoney(point.values[s.key] ?? 0)}</span>
                    <span className="text-muted-foreground">{s.label}</span>
                  </li>
                ))}
                {point.extra?.map((e) => (
                  <li key={e.label} className="flex items-center gap-2 border-t pt-1">
                    <span aria-hidden="true" className="w-3" />
                    <span className="font-semibold tabular-nums">{formatMoney(e.value)}</span>
                    <span className="text-muted-foreground">{e.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
