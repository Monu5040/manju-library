import { type PointerEvent, useRef, useState } from 'react'
import type { Occupancy, SlotState } from '@/lib/types'
import { SLOT_COLORS, SLOT_LABELS } from './slots'

/**
 * Seats across, shifts down: every cell is one seat in one shift. A real table, so screen
 * readers can move through it; hovering a cell names the seat, shift and state.
 */
export function SeatHeatmap({ occupancy }: { occupancy: Occupancy }) {
  const box = useRef<HTMLDivElement>(null)
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)

  const onOver = (event: PointerEvent) => {
    const cell = (event.target as HTMLElement).closest<HTMLElement>('[data-tip]')
    if (!cell || !box.current) {
      setTip(null)
      return
    }
    const outer = box.current.getBoundingClientRect()
    const rect = cell.getBoundingClientRect()
    setTip({ x: rect.left - outer.left + rect.width / 2, y: rect.top - outer.top, text: cell.dataset.tip ?? '' })
  }

  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground" aria-label="Legend">
        {(['taken', 'partly', 'free'] as SlotState[]).map((state) => (
          <li key={state} className="flex items-center gap-2">
            <span aria-hidden="true" className="size-3 rounded-[3px]" style={{ background: SLOT_COLORS[state] }} />
            {SLOT_LABELS[state]}
          </li>
        ))}
      </ul>
      <div ref={box} className="relative" onPointerOver={onOver} onPointerLeave={() => setTip(null)}>
        <div className="overflow-x-auto">
          <table className="border-separate border-spacing-[2px] text-[10px]">
            <caption className="sr-only">Seats in each shift on this day</caption>
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-[1] bg-card pr-2 text-left font-normal text-muted-foreground">
                  Seat
                </th>
                {occupancy.grid.map((row) => (
                  <th key={row.seat} scope="col" className="min-w-3.5 font-normal text-muted-foreground tabular-nums">
                    {row.seat}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {occupancy.shifts.map((shift, s) => (
                <tr key={shift.id}>
                  <th scope="row" className="sticky left-0 z-[1] bg-card pr-2 text-left text-xs font-medium whitespace-nowrap">
                    {shift.name}
                  </th>
                  {occupancy.grid.map((row) => {
                    const state = row.cells[s]
                    const text = `Seat ${row.seat} · ${shift.name}: ${SLOT_LABELS[state]}`
                    return (
                      <td key={row.seat} aria-label={text} data-tip={text} className="p-0">
                        <span className="block size-3.5 rounded-[3px]" style={{ background: SLOT_COLORS[state] }} />
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {tip && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border bg-card px-2 py-1 text-xs whitespace-nowrap shadow-md"
            style={{ left: tip.x, top: tip.y - 4 }}
          >
            {tip.text}
          </div>
        )}
      </div>
    </div>
  )
}
