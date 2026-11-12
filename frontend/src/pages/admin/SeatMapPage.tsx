import { ChevronLeft, ChevronRight, Clock, UserPlus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Avatar } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Meter } from '@/components/ui/meter'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Segmented } from '@/components/ui/segmented'
import { Skeleton } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { daysLeftLabel, firstName, formatDate, formatLongDate, todayIso } from '@/lib/format'
import { useSeatMap } from '@/lib/queries'
import { MINUTES_PER_DAY, overlaps } from '@/lib/time'
import type { SeatBooking, SeatMap } from '@/lib/types'
import { cn } from '@/lib/utils'

type Seat = SeatMap['seats'][number]
type Shift = SeatMap['shifts'][number]
type SeatState = 'off' | 'free' | 'partial' | 'taken'

interface SeatView {
  seat: Seat
  state: SeatState
  /** The bookings that matter for the time being looked at. */
  bookings: SeatBooking[]
  /** Shifts in which nobody sits here (seat sharing only). */
  freeShifts: Shift[]
  /** Fewest days left among those bookings, when one ends within a week. */
  endsIn: number | null
}

const range = (b: SeatBooking): [number, number] => [b.start_minute, b.end_minute]

function viewSeat(seat: Seat, shifts: Shift[], chosen: Shift | undefined, sharing: boolean): SeatView {
  const freeShifts = !seat.is_active
    ? []
    : shifts.filter((s) => (sharing ? !seat.bookings.some((b) => overlaps(range(b), s.minutes)) : seat.bookings.length === 0))
  // Without sharing a seat belongs to one student whatever the time.
  const bookings = chosen && sharing ? seat.bookings.filter((b) => overlaps(range(b), chosen.minutes)) : seat.bookings
  const soonest = Math.min(...bookings.map((b) => b.days_left))
  const state: SeatState = !seat.is_active
    ? 'off'
    : bookings.length === 0
      ? 'free'
      : !chosen && sharing && freeShifts.length > 0
        ? 'partial'
        : 'taken'
  return { seat, state, bookings, freeShifts, endsIn: bookings.length > 0 && soonest <= 7 ? soonest : null }
}

/** The library's day, from the first shift's start to the last one's end. */
function dayWindow(shifts: Shift[]): [number, number] {
  if (shifts.length === 0) {
    return [6 * 60, 22 * 60]
  }
  return [Math.min(...shifts.map((s) => s.minutes[0])), Math.max(...shifts.map((s) => s.minutes[1]))]
}

function shiftDate(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  const next = new Date(Date.UTC(y, m - 1, d + days))
  return next.toISOString().slice(0, 10)
}

export default function SeatMapPage() {
  const [date, setDate] = useState(todayIso())
  const [shiftId, setShiftId] = useState<number | null>(null)
  const seatMap = useSeatMap(date)
  const [openId, setOpenId] = useState<number | null>(null)
  const data = seatMap.data
  const sharing = data?.allow_seat_sharing ?? false
  const shifts = useMemo(() => data?.shifts ?? [], [data])
  const chosen = shifts.find((s) => s.id === shiftId)
  const hours = useMemo(() => dayWindow(shifts), [shifts])
  const views = useMemo(
    () => (data?.seats ?? []).map((seat) => viewSeat(seat, shifts, chosen, sharing)),
    [data, shifts, chosen, sharing],
  )
  const open = views.find((v) => v.seat.id === openId)

  const active = views.filter((v) => v.state !== 'off').length
  const free = views.filter((v) => v.state === 'free').length
  const partial = views.filter((v) => v.state === 'partial').length
  const inUse = active - free
  const usedPercent = active ? Math.round((inUse / active) * 100) : 0
  const isToday = date === todayIso()

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Seat map"
        description={
          data &&
          (sharing
            ? 'One seat can go to different students in shifts that do not overlap.'
            : 'Each seat goes to one student at a time.')
        }
        actions={
          <div className="flex items-center gap-1.5">
            <Button variant="outline" size="icon" aria-label="Previous day" onClick={() => setDate((d) => shiftDate(d, -1))}>
              <ChevronLeft aria-hidden="true" />
            </Button>
            <Input
              type="date"
              className="w-[10.5rem]"
              value={date}
              onChange={(e) => setDate(e.target.value || todayIso())}
              aria-label="Date"
            />
            <Button variant="outline" size="icon" aria-label="Next day" onClick={() => setDate((d) => shiftDate(d, 1))}>
              <ChevronRight aria-hidden="true" />
            </Button>
            {!isToday && (
              <Button variant="ghost" onClick={() => setDate(todayIso())}>
                Today
              </Button>
            )}
          </div>
        }
      />
      {seatMap.error && <Alert variant="destructive">{errorMessage(seatMap.error)}</Alert>}
      {seatMap.isPending && <MapSkeleton />}

      {data && (
        <>
          <Card className="mb-5 flex flex-wrap items-center gap-x-8 gap-y-4 p-5">
            <dl className="flex flex-wrap gap-x-8 gap-y-3">
              <Figure label="Seats" value={active} />
              <Figure label={chosen ? `Free in ${chosen.name}` : 'Free'} value={free} tone="success" />
              {!chosen && sharing ? (
                <>
                  <Figure label="Part free" value={partial} />
                  <Figure label="Full" value={inUse - partial} />
                </>
              ) : (
                <Figure label="In use" value={inUse} />
              )}
            </dl>
            <div className="min-w-48 flex-1">
              <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
                <span>{isToday ? 'Today' : formatLongDate(date)}</span>
                <span className="font-semibold text-foreground tabular-nums">{usedPercent}% in use</span>
              </div>
              <Meter percent={usedPercent} className="h-2" />
            </div>
          </Card>

          {shifts.length > 0 && (
            <Segmented
              label="Show seats for"
              className="mb-5"
              value={chosen ? String(chosen.id) : 'all'}
              onChange={(v) => setShiftId(v === 'all' ? null : Number(v))}
              options={[{ value: 'all', label: 'Whole day' }, ...shifts.map((s) => ({ value: String(s.id), label: s.name, title: s.time_label }))]}
            />
          )}
          {chosen && <p className="-mt-2 mb-4 text-sm text-muted-foreground">{chosen.name}: {chosen.time_label}</p>}

          {views.length === 0 ? (
            <EmptyState title="No seats yet.">
              Add them under{' '}
              <Link className="font-medium text-primary underline" to="/admin/settings">
                Settings
              </Link>
              .
            </EmptyState>
          ) : (
            <ul className="grid grid-cols-3 gap-2.5 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8" aria-label="Seats">
              {views.map((view) => (
                <li key={view.seat.id}>
                  <SeatTile view={view} chosen={chosen} hours={hours} showDay={shifts.length > 0} onOpen={() => setOpenId(view.seat.id)} />
                </li>
              ))}
            </ul>
          )}

          <ul aria-label="Key" className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
            <Key className={TILE.free} label="Free" />
            {sharing && <Key className={TILE.partial} label="Part of the day free" />}
            <Key className={TILE.taken} label="In use" />
            <li className="inline-flex items-center gap-1.5">
              <span aria-hidden="true" className="rounded-full bg-warning px-1.5 text-[10px] leading-4 font-bold text-accent-foreground">
                3d
              </span>
              Ends within 7 days
            </li>
            <Key className={TILE.off} label="Switched off" />
          </ul>
        </>
      )}

      {open && <SeatDialog view={open} date={date} chosen={chosen} sharing={sharing} onClose={() => setOpenId(null)} />}
    </div>
  )
}

const TILE: Record<SeatState, string> = {
  free: 'border-border bg-card hover:border-primary/50',
  partial: 'border-primary/25 bg-[color-mix(in_oklch,var(--primary)_5%,var(--card))] hover:border-primary/55',
  taken: 'border-primary/35 bg-[color-mix(in_oklch,var(--primary)_12%,var(--card))] hover:border-primary/60',
  off: 'border-dashed border-input bg-muted/60 bg-[repeating-linear-gradient(135deg,transparent_0_7px,var(--border)_7px_8px)] text-muted-foreground',
}

function spokenSeat({ seat, state, bookings, freeShifts, endsIn }: SeatView, chosen: Shift | undefined): string {
  if (state === 'off') return `Seat ${seat.number}: switched off`
  if (state === 'free') return `Seat ${seat.number}: free${chosen ? ` in ${chosen.name}` : ''}`
  const who = bookings.map((b) => `${b.student_name} ${b.time_label}`).join(', ')
  const ending = endsIn !== null ? `, ${daysLeftLabel(endsIn).toLowerCase()}` : ''
  const gaps = state === 'partial' ? `; free in ${freeShifts.map((s) => s.name).join(', ')}` : ''
  return `Seat ${seat.number}: ${who}${ending}${gaps}`
}

function SeatTile({
  view,
  chosen,
  hours,
  showDay,
  onOpen,
}: {
  view: SeatView
  chosen: Shift | undefined
  hours: [number, number]
  showDay: boolean
  onOpen: () => void
}) {
  const { seat, state, bookings, endsIn } = view
  const names = bookings.map((b) => firstName(b.student_name))
  const label =
    state === 'off' ? 'Off' : state === 'free' ? 'Free' : names.length > 2 ? `${names.length} students` : names.join(', ')
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={spokenSeat(view, chosen)}
      className={cn(
        'group flex h-[5.5rem] w-full flex-col rounded-xl border p-2.5 text-left transition-[border-color,box-shadow,translate] duration-150',
        'hover:-translate-y-px hover:shadow-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:outline-none',
        TILE[state],
        endsIn !== null && 'border-warning/80',
      )}
    >
      <span className="flex items-start justify-between gap-1">
        <span className="text-[15px] leading-none font-bold tabular-nums">{seat.number}</span>
        {endsIn !== null ? (
          <span className="rounded-full bg-warning px-1.5 text-[10px] leading-4 font-bold text-accent-foreground tabular-nums">
            {endsIn <= 0 ? 'today' : `${endsIn}d`}
          </span>
        ) : (
          state === 'free' && <span aria-hidden="true" className="mt-0.5 size-2 rounded-full bg-success" />
        )}
      </span>
      <span className={cn('mt-auto truncate text-xs font-medium', state === 'free' ? 'text-success' : state === 'off' ? '' : 'text-foreground/85')}>
        {label}
      </span>
      {showDay && state !== 'off' && <DayBar bookings={view.seat.bookings} hours={hours} chosen={chosen} />}
    </button>
  )
}

/** A thin line for the library's day; filled where someone has the seat. */
function DayBar({ bookings, hours: [lo, hi], chosen }: { bookings: SeatBooking[]; hours: [number, number]; chosen: Shift | undefined }) {
  const span = Math.max(1, hi - lo)
  const part = (start: number, end: number, key: string) => {
    const s = Math.max(lo, start)
    const e = Math.min(hi, end)
    return e > s ? { key, left: ((s - lo) / span) * 100, width: ((e - s) / span) * 100 } : null
  }
  const pieces = (start: number, end: number, key: string) =>
    [0, MINUTES_PER_DAY, -MINUTES_PER_DAY].map((d) => part(start + d, end + d, `${key}:${d}`)).filter((p) => p !== null)
  const filled = bookings.flatMap((b) => pieces(b.start_minute, b.end_minute, String(b.membership)))
  const focus = chosen ? pieces(chosen.minutes[0], chosen.minutes[1], 'chosen') : []
  return (
    <span aria-hidden="true" className="relative mt-1.5 block h-1 w-full rounded-full bg-muted">
      {focus.map((p) => (
        <span key={p.key} className="absolute -inset-y-0.5 rounded-sm bg-foreground/10" style={{ left: `${p.left}%`, width: `${p.width}%` }} />
      ))}
      {filled.map((p) => (
        <span key={p.key} className="absolute inset-y-0 rounded-full bg-primary" style={{ left: `${p.left}%`, width: `${p.width}%` }} />
      ))}
    </span>
  )
}

function SeatDialog({
  view,
  date,
  chosen,
  sharing,
  onClose,
}: {
  view: SeatView
  date: string
  chosen: Shift | undefined
  sharing: boolean
  onClose: () => void
}) {
  const { seat, freeShifts } = view
  const params = new URLSearchParams({ seat: String(seat.id) })
  const admitShift = chosen && freeShifts.some((s) => s.id === chosen.id) ? chosen : freeShifts.length === 1 ? freeShifts[0] : undefined
  if (admitShift) params.set('shift', String(admitShift.id))
  const canAdmit = seat.is_active && (seat.bookings.length === 0 || (sharing && freeShifts.length > 0))

  return (
    <Dialog open onClose={onClose} title={`Seat ${seat.number}`} description={`On ${formatLongDate(date)}`}>
      {!seat.is_active && (
        <Alert className="mb-4">
          This seat is switched off. Turn it on under{' '}
          <Link className="font-medium underline" to="/admin/settings">
            Settings
          </Link>
          .
        </Alert>
      )}
      {seat.bookings.length === 0 ? (
        seat.is_active && <p className="text-sm text-muted-foreground">Nobody has this seat on this day.</p>
      ) : (
        <ul className="-mx-1 divide-y">
          {seat.bookings.map((b) => (
            <li key={b.membership} className="flex items-start gap-3 px-1 py-3">
              <Avatar name={b.student_name} tone="soft" />
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <Link to={`/admin/students/${b.student}`} className="font-semibold hover:underline">
                    {b.student_name}
                  </Link>
                  <span className="text-xs text-muted-foreground">roll {b.roll_no}</span>
                </p>
                <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Clock aria-hidden="true" className="size-3.5 shrink-0" />
                  {b.shift_name ? `${b.shift_name} · ` : ''}
                  {b.time_label}
                </p>
                <p className="mt-0.5 text-sm text-muted-foreground">Until {formatDate(b.end_date)}</p>
              </div>
              <Badge tone={b.days_left < 0 ? 'danger' : b.days_left <= 7 ? 'warning' : 'success'}>{daysLeftLabel(b.days_left)}</Badge>
            </li>
          ))}
        </ul>
      )}

      {sharing && seat.is_active && seat.bookings.length > 0 && (
        <div className="mt-3 rounded-xl bg-muted/70 px-4 py-3 text-sm">
          {freeShifts.length > 0 ? (
            <>
              <p className="font-semibold">Free in</p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {freeShifts.map((s) => (
                  <li key={s.id}>
                    <Badge tone="success">
                      {s.name} · {s.time_label}
                    </Badge>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-muted-foreground">Booked in every shift.</p>
          )}
        </div>
      )}

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
        {canAdmit && (
          <Button asChild>
            <Link to={`/admin/students/new?${params}`}>
              <UserPlus aria-hidden="true" /> Admit to this seat
            </Link>
          </Button>
        )}
      </div>
    </Dialog>
  )
}

function Figure({ label, value, tone }: { label: string; value: number; tone?: 'success' }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className={cn('text-2xl font-semibold tracking-tight tabular-nums', tone === 'success' && 'text-success')}>{value}</dd>
    </div>
  )
}

function Key({ className, label }: { className: string; label: string }) {
  return (
    <li className="inline-flex items-center gap-1.5">
      <span className={cn('size-3.5 rounded-[4px] border', className)} aria-hidden="true" />
      {label}
    </li>
  )
}

function MapSkeleton() {
  return (
    <div role="status" aria-label="Loading seat map">
      <Skeleton className="mb-5 h-24 rounded-2xl" />
      <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
        {Array.from({ length: 24 }, (_, n) => (
          <Skeleton key={n} className="h-[5.5rem] rounded-xl" />
        ))}
      </div>
    </div>
  )
}
