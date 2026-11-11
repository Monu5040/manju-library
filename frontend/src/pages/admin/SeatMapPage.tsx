import { useState } from 'react'
import { Link } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader, StatCard } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { daysLeftLabel, formatDate, todayIso } from '@/lib/format'
import { useSeatMap } from '@/lib/queries'
import type { SeatMap } from '@/lib/types'
import { cn } from '@/lib/utils'

type SeatRow = SeatMap['seats'][number]

export default function SeatMapPage() {
  const [date, setDate] = useState(todayIso())
  const seatMap = useSeatMap(date)
  const [open, setOpen] = useState<SeatRow | null>(null)

  return (
    <div>
      <PageHeader
        title="Seat map"
        description={seatMap.data?.allow_seat_sharing ? 'Seats can be shared by shifts that do not overlap.' : 'Each seat goes to one student at a time.'}
        actions={
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">On</span>
            <Input type="date" className="w-auto" value={date} onChange={(e) => setDate(e.target.value || todayIso())} aria-label="Date" />
          </label>
        }
      />
      {seatMap.isPending && <Spinner label="Loading seat map" />}
      {seatMap.error && <Alert variant="destructive">{errorMessage(seatMap.error)}</Alert>}
      {seatMap.data && (
        <>
          <dl className="mb-6 grid grid-cols-3 gap-4">
            <StatCard label="Seats" value={seatMap.data.summary.seats} />
            <StatCard label="In use" value={seatMap.data.summary.occupied} />
            <StatCard label="Free" value={seatMap.data.summary.free} />
          </dl>
          {seatMap.data.seats.length === 0 ? (
            <EmptyState title="No seats yet.">
              Add them under <Link className="underline" to="/admin/settings">Settings</Link>.
            </EmptyState>
          ) : (
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-8" aria-label="Seats">
              {seatMap.data.seats.map((seat) => {
                const taken = seat.bookings.length > 0
                const endingSoon = seat.bookings.some((b) => b.days_left <= 7)
                return (
                  <li key={seat.id}>
                    <button
                      type="button"
                      onClick={() => setOpen(seat)}
                      className={cn(
                        'flex h-20 w-full flex-col items-center justify-center rounded-lg border text-sm transition-colors hover:ring-2 hover:ring-ring',
                        !seat.is_active && 'border-dashed bg-muted text-muted-foreground',
                        seat.is_active && !taken && 'bg-card',
                        taken && !endingSoon && 'border-primary/40 bg-primary/10',
                        taken && endingSoon && 'border-warning/60 bg-warning/15',
                      )}
                      aria-label={`Seat ${seat.number}: ${taken ? seat.bookings.map((b) => `${b.student_name} ${b.time_label}`).join(', ') : seat.is_active ? 'free' : 'switched off'}`}
                    >
                      <span className="text-base font-semibold">{seat.number}</span>
                      <span className="text-xs text-muted-foreground">
                        {!seat.is_active ? 'off' : taken ? `${seat.bookings.length} booked` : 'free'}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          <p className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
            <Legend className="bg-card" label="Free" />
            <Legend className="border-primary/40 bg-primary/10" label="In use" />
            <Legend className="border-warning/60 bg-warning/15" label="Ends within 7 days" />
          </p>
        </>
      )}

      {open && (
        <Dialog open onClose={() => setOpen(null)} title={`Seat ${open.number}`} description={`On ${formatDate(date)}`}>
          {open.bookings.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nobody has this seat on this day.</p>
          ) : (
            <ul className="divide-y">
              {open.bookings.map((b) => (
                <li key={b.membership} className="py-3">
                  <Link to={`/admin/students/${b.student}`} className="font-medium hover:underline">
                    {b.student_name}
                  </Link>{' '}
                  <span className="text-sm text-muted-foreground">roll {b.roll_no}</span>
                  <div className="text-sm text-muted-foreground">
                    {b.shift_name ? `${b.shift_name} · ` : ''}
                    {b.time_label} · until {formatDate(b.end_date)} ({daysLeftLabel(b.days_left)})
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex justify-end">
            <Button asChild>
              <Link to="/admin/students/new">New admission</Link>
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  )
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn('size-3 rounded border', className)} aria-hidden="true" />
      {label}
    </span>
  )
}
