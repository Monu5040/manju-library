import { CalendarClock, MapPin, Phone, Pin } from 'lucide-react'
import { Link } from 'react-router'
import { StateBadge } from '@/components/admin/badges'
import { ProfileSwitcher } from '@/components/portal/ProfileSwitcher'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { useSelectedProfile } from '@/lib/portal'
import type { PortalMembership } from '@/lib/types'

export default function PortalHomePage() {
  const { home, profiles, selected, select } = useSelectedProfile()

  if (home.isPending) return <Spinner label="Loading your details" />
  if (home.error) return <Alert variant="destructive">{errorMessage(home.error)}</Alert>
  if (!selected) {
    return (
      <Alert>
        Your login is not linked to a student record yet. Please speak to the front desk.
      </Alert>
    )
  }

  const m = selected.current_membership
  const firstName = selected.full_name.split(' ')[0]
  const library = home.data.library
  const query = `?profile=${selected.id}`

  return (
    <div className="space-y-6">
      <ProfileSwitcher profiles={profiles} selectedId={selected.id} onSelect={select} />
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Hello, {firstName}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Roll no. {selected.roll_no}</p>
      </div>

      {m && (m.state === 'EXPIRED' || m.days_left <= 7) && (
        <Alert variant={m.state === 'EXPIRED' ? 'destructive' : 'info'}>
          {m.state === 'EXPIRED'
            ? `Your membership ended on ${formatDate(m.end_date)}. Renew at the front desk to keep your seat.`
            : `Your membership ends on ${formatDate(m.end_date)}. Renew at the front desk to keep your seat.`}
        </Alert>
      )}
      {selected.total_due > 0 && (
        <Alert variant="destructive">
          {formatMoney(selected.total_due)} is due. Pay at the front desk (cash or UPI) and you will get a receipt
          here.
        </Alert>
      )}

      {m ? <MembershipCard membership={m} /> : (
        <Card>
          <CardHeader>
            <CardTitle>No current membership</CardTitle>
            <CardDescription>Ask at the front desk for a seat. Fees and timings are listed below.</CardDescription>
          </CardHeader>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        <Button asChild variant="outline">
          <Link to={`/portal/payments${query}`}>My payments and receipts</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to={`/portal/profile${query}`}>My details</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to={`/portal/fees${query}`}>Fees and timings</Link>
        </Button>
      </div>

      {home.data.notices.length > 0 && (
        <section aria-labelledby="notices">
          <h2 id="notices" className="mb-3 text-lg font-semibold">
            Notices
          </h2>
          <div className="space-y-3">
            {home.data.notices.map((n) => (
              <Card key={n.id}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    {n.is_pinned && <Pin aria-label="Pinned" className="size-4 text-primary" />}
                    {n.title}
                  </CardTitle>
                  <CardDescription>{formatDate(n.starts_on)}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm whitespace-pre-line">{n.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {library && (library.address || library.phone) && (
        <p className="flex flex-col gap-1 text-sm text-muted-foreground sm:flex-row sm:gap-4">
          {library.address && (
            <span className="inline-flex items-center gap-1.5">
              <MapPin aria-hidden="true" className="size-4" /> {library.address}
            </span>
          )}
          {library.phone && (
            <a className="inline-flex items-center gap-1.5 hover:underline" href={`tel:${library.phone}`}>
              <Phone aria-hidden="true" className="size-4" /> {library.phone}
            </a>
          )}
        </p>
      )}
    </div>
  )
}

function MembershipCard({ membership: m }: { membership: PortalMembership }) {
  const total = Math.max(1, (Date.parse(m.end_date) - Date.parse(m.start_date)) / 86_400_000 + 1)
  const left = Math.max(0, Math.min(total, m.days_left + 1))
  const percent = m.state === 'UPCOMING' ? 100 : Math.round((left / total) * 100)
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>Your seat</CardTitle>
          <CardDescription>{m.plan_name ?? 'Membership'}</CardDescription>
        </div>
        <StateBadge state={m.state} daysLeft={m.days_left} />
      </CardHeader>
      <CardContent className="space-y-5">
        <dl className="grid grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-muted-foreground">Seat</dt>
            <dd className="text-3xl font-semibold">{m.seat_number ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Timing</dt>
            <dd className="font-medium">{m.shift_name ?? 'Custom time'}</dd>
            <dd className="text-sm text-muted-foreground">{m.time_label}</dd>
          </div>
        </dl>
        <div>
          <div className="mb-1.5 flex justify-between text-sm">
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <CalendarClock aria-hidden="true" className="size-4" /> {formatDate(m.start_date)} – {formatDate(m.end_date)}
            </span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Time left in this membership"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
          >
            <div className={m.days_left <= 7 ? 'h-full bg-warning' : 'h-full bg-primary'} style={{ width: `${percent}%` }} />
          </div>
        </div>
        <dl className="grid grid-cols-3 gap-2 border-t pt-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Fee</dt>
            <dd className="font-medium tabular-nums">{formatMoney(m.net_fee)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Paid</dt>
            <dd className="font-medium tabular-nums">{formatMoney(m.paid_total)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Due</dt>
            <dd className={m.due_total > 0 ? 'font-medium text-destructive tabular-nums' : 'font-medium tabular-nums'}>
              {formatMoney(m.due_total)}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
