import type { ReactNode } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { type DateRange, RANGE_PRESETS, type RangePreset } from '@/lib/ranges'

/** The one filter row above a report: a period preset, or custom from/to dates. */
export function RangeFilter({
  preset,
  range,
  onChange,
  children,
}: {
  preset: RangePreset
  range: DateRange
  onChange: (patch: Record<string, string>) => void
  children?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-3 print:hidden">
      <div className="w-full space-y-1.5 sm:w-52">
        <Label htmlFor="range-preset">Period</Label>
        <Select
          id="range-preset"
          value={preset}
          onChange={(e) =>
            onChange(e.target.value === 'custom' ? { range: 'custom', ...range } : { range: e.target.value, from: '', to: '' })
          }
        >
          {RANGE_PRESETS.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
        </Select>
      </div>
      {preset === 'custom' && (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="range-from">From</Label>
            <Input id="range-from" type="date" value={range.from} max={range.to} onChange={(e) => onChange({ from: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="range-to">To</Label>
            <Input id="range-to" type="date" value={range.to} min={range.from} onChange={(e) => onChange({ to: e.target.value })} />
          </div>
        </>
      )}
      {children}
    </div>
  )
}
