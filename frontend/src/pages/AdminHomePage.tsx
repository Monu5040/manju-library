import { Link } from 'react-router'
import { StateBadge } from '@/components/admin/badges'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, PageHeader, StatCard } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { useMemberships, useOverview } from '@/lib/queries'

export default function AdminHomePage() {
  const overview = useOverview()
  const expiring = useMemberships({ expiring_within: 7, ordering: 'end_date', page_size: 8 })
  const stats = overview.data?.library

  return (
    <div>
      <PageHeader
        title="Overview"
        actions={
          <>
            <Button asChild>
              <Link to="/admin/students/new">New admission</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/admin/seats">Seat map</Link>
            </Button>
          </>
        }
      />

      {overview.isPending && <Spinner label="Loading overview" />}
      {overview.error && <Alert variant="destructive">{errorMessage(overview.error)}</Alert>}
      {stats && (
        <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Active members" value={stats.active_members} />
          <StatCard
            label="Seats in use"
            value={`${stats.occupancy_percent}%`}
            hint={`${stats.occupied_seats} of ${stats.seats} seats`}
          />
          <StatCard label="Renewals due in 7 days" value={stats.expiring_in_7_days} />
          <StatCard label="Outstanding dues" value={formatMoney(stats.outstanding_dues)} />
          <StatCard label="Collected today" value={formatMoney(stats.collected_today)} />
          <StatCard label="Collected this month" value={formatMoney(stats.collected_this_month)} />
          <StatCard label="Waiting list" value={stats.waiting} />
          <StatCard label="Staff accounts" value={(overview.data?.users.staff ?? 0) + (overview.data?.users.super_admins ?? 0)} />
        </dl>
      )}

      <Card className="mt-8">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Renewals due this week</CardTitle>
          <Button asChild variant="link" className="px-0">
            <Link to="/admin/renewals">See all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {expiring.data?.results.length === 0 && <EmptyState title="No memberships end in the next 7 days." />}
          <ul className="divide-y">
            {expiring.data?.results.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <Link to={`/admin/students/${m.student}`} className="font-medium hover:underline">
                  {m.student_name} <span className="text-muted-foreground">· roll {m.roll_no}</span>
                </Link>
                <span className="flex items-center gap-3 text-sm text-muted-foreground">
                  Seat {m.seat_number ?? '—'} · ends {formatDate(m.end_date)}
                  <StateBadge state={m.state} daysLeft={m.days_left} />
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
