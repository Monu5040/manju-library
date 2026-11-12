import { useMemo, useState } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import type { MembershipDraft } from '@/lib/drafts'
import { formatMoney, todayIso } from '@/lib/format'
import { usePlans, useSeatMap, useSeats, useShifts } from '@/lib/queries'
import { overlaps } from '@/lib/time'

/**
 * Plan, shift, seat, dates and fee. Choosing a plan fills its shift and price. Seats show
 * who already sits there in the chosen shift on the start date; the server makes the
 * final check across the whole date range.
 */
export function MembershipFields({
  value,
  onChange,
  errors = {},
  startOptional = false,
  defaultStart,
}: {
  value: MembershipDraft
  onChange: (next: MembershipDraft) => void
  errors?: Partial<Record<keyof MembershipDraft, string>>
  startOptional?: boolean
  /** The start used when the date is left empty (a renewal starts after the current end). */
  defaultStart?: string
}) {
  const plans = usePlans()
  const shifts = useShifts()
  const seats = useSeats()
  const [today] = useState(todayIso)
  // Who sits where on the day this membership would start, not today: renewing a student
  // must not show their own current seat as taken.
  const seatMap = useSeatMap(value.start_date || defaultStart || today)

  const set = (patch: Partial<MembershipDraft>) => onChange({ ...value, ...patch })

  const choosePlan = (planId: string) => {
    const plan = plans.data?.find((p) => String(p.id) === planId)
    set({
      plan: planId,
      shift: plan?.shift ? String(plan.shift) : value.shift,
      price: plan ? String(plan.price) : value.price,
    })
  }

  const seatNotes = useMemo(() => {
    const notes = new Map<number, string>()
    const shift = seatMap.data?.shifts.find((s) => String(s.id) === value.shift)
    for (const seat of seatMap.data?.seats ?? []) {
      const clash = seat.bookings.find(
        (b) =>
          !seatMap.data?.allow_seat_sharing ||
          !shift ||
          overlaps([b.start_minute, b.end_minute], shift.minutes),
      )
      if (clash) {
        notes.set(seat.id, `taken by ${clash.student_name} (${clash.time_label})`)
      }
    }
    return notes
  }, [seatMap.data, value.shift])

  const net = Number(value.price || 0) - Number(value.discount || 0)

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Plan" id="m-plan" error={errors.plan}>
        <Select id="m-plan" value={value.plan} onChange={(e) => choosePlan(e.target.value)}>
          <option value="">Custom (no plan)</option>
          {plans.data
            ?.filter((p) => p.is_active)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {formatMoney(p.price)}
              </option>
            ))}
        </Select>
      </Field>
      <Field label="Shift" id="m-shift" error={errors.shift}>
        <Select id="m-shift" value={value.shift} onChange={(e) => set({ shift: e.target.value })}>
          <option value="">Choose a shift</option>
          {shifts.data
            ?.filter((s) => s.is_active)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.time_label})
              </option>
            ))}
        </Select>
      </Field>
      <Field label="Seat" id="m-seat" error={errors.seat} className="sm:col-span-2">
        <Select id="m-seat" value={value.seat} onChange={(e) => set({ seat: e.target.value })}>
          <option value="">No seat yet</option>
          {seats.data
            ?.filter((s) => s.is_active)
            .map((s) => {
              const note = seatNotes.get(s.id)
              return (
                <option key={s.id} value={s.id} disabled={Boolean(note) && String(s.id) !== value.seat}>
                  Seat {s.number}
                  {note ? ` — ${note}` : ''}
                </option>
              )
            })}
        </Select>
      </Field>
      <Field label={startOptional ? 'Start date (optional)' : 'Start date'} id="m-start" error={errors.start_date}>
        <Input id="m-start" type="date" value={value.start_date} onChange={(e) => set({ start_date: e.target.value })} />
      </Field>
      <Field label="End date (optional)" id="m-end" error={errors.end_date} hint="Leave empty to follow the plan length.">
        <Input id="m-end" type="date" value={value.end_date} onChange={(e) => set({ end_date: e.target.value })} />
      </Field>
      <Field label="Fee (₹)" id="m-price" error={errors.price}>
        <Input id="m-price" inputMode="decimal" value={value.price} onChange={(e) => set({ price: e.target.value })} />
      </Field>
      <Field label="Discount (₹)" id="m-discount" error={errors.discount} hint={`To pay: ${formatMoney(Math.max(net, 0))}`}>
        <Input id="m-discount" inputMode="decimal" value={value.discount} onChange={(e) => set({ discount: e.target.value })} />
      </Field>
    </div>
  )
}

export function Field({
  label,
  id,
  error,
  hint,
  className,
  children,
}: {
  label: string
  id: string
  error?: string
  hint?: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={['space-y-1.5', className].filter(Boolean).join(' ')}>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}
