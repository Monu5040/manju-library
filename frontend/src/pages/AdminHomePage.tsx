import {
  Armchair,
  BellRing,
  CalendarCheck,
  CalendarClock,
  ChevronRight,
  HandCoins,
  ListOrdered,
  type LucideIcon,
  ReceiptText,
  UserPlus,
  Users,
  Wallet,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { StateBadge } from '@/components/admin/badges'
import { Alert } from '@/components/ui/alert'
import { Avatar } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Meter } from '@/components/ui/meter'
import { EmptyState, PageHeader, StatCard } from '@/components/ui/page'
import { Skeleton } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { useSystemStatus } from '@/lib/automation'
import { firstName, formatDate, formatDayMonth, formatLongDate, formatMoney, greeting, todayIso } from '@/lib/format'
import { useMemberships, useOverview, usePayments } from '@/lib/queries'
import type { Overview } from '@/lib/types'
import { cn } from '@/lib/utils'

export default function AdminHomePage() {
  const overview = useOverview()
  const { data: me } = useMe()
  const system = useSystemStatus(true, me?.role === 'SUPER_ADMIN')
  const trouble = system.data?.jobs.filter((j) => j.state === 'late' || j.state === 'failed') ?? []
  const diskFull = (system.data?.disk.used_percent ?? 0) >= 90
  const stats = overview.data?.library

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={formatLongDate(todayIso())}
        title={me ? `${greeting()}, ${firstName(me.full_name)}` : 'Overview'}
        description={stats && summaryLine(stats)}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/admin/seats">
                <Armchair aria-hidden="true" /> Seat map
              </Link>
            </Button>
            <Button asChild>
              <Link to="/admin/students/new">
                <UserPlus aria-hidden="true" /> New admission
              </Link>
            </Button>
          </>
        }
      />

      {(trouble.length > 0 || diskFull) && (
        <Alert variant="destructive" className="mb-6">
          {trouble.length > 0 && `Something behind the scenes needs attention: ${trouble.map((j) => j.label.toLowerCase()).join(', ')}. `}
          {diskFull && 'The server disk is nearly full. '}
          <Link className="font-medium underline" to="/admin/system">
            Open System status
          </Link>
        </Alert>
      )}
      {overview.error && <Alert variant="destructive" className="mb-6">{errorMessage(overview.error)}</Alert>}

      {stats ? (
        <dl className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <StatCard
            label="Active members"
            icon={Users}
            value={stats.active_members}
            hint={stats.waiting > 0 ? `${stats.waiting} more on the waiting list` : 'Nobody waiting for a seat'}
          />
          <StatCard
            label="Seats in use"
            icon={Armchair}
            value={`${stats.occupancy_percent}%`}
            hint={
              <span className="block space-y-2">
                <Meter percent={stats.occupancy_percent} className="mt-1" />
                <span className="block">
                  {stats.occupied_seats} of {stats.seats} seats
                </span>
              </span>
            }
          />
          <StatCard
            label="Collected today"
            icon={Wallet}
            value={formatMoney(stats.collected_today)}
            hint={`${formatMoney(stats.collected_this_month)} this month`}
          />
          <StatCard
            label="Outstanding dues"
            icon={HandCoins}
            value={formatMoney(stats.outstanding_dues)}
            hint={
              stats.outstanding_dues > 0 ? (
                <Link className="font-medium text-primary hover:underline" to="/admin/students?view=due">
                  See who owes
                </Link>
              ) : (
                'Everyone has paid'
              )
            }
          />
        </dl>
      ) : (
        overview.isPending && (
          <div role="status" aria-label="Loading overview" className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            {[0, 1, 2, 3].map((n) => (
              <Skeleton key={n} className="h-[8.5rem] rounded-2xl" />
            ))}
          </div>
        )
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
        <ToDo stats={stats} className="lg:col-start-2 lg:row-start-1 lg:self-start" />
        <Renewals className="lg:col-start-1 lg:row-span-2 lg:row-start-1" />
        <LatestPayments className="lg:col-start-2 lg:row-start-2 lg:self-start" />
      </div>
    </div>
  )
}

function summaryLine(stats: Overview['library']): string {
  const free = Math.max(0, stats.seats - stats.occupied_seats)
  const parts = [
    free === 1 ? '1 seat free' : `${free} seats free`,
    stats.expiring_in_7_days === 1 ? '1 renewal due this week' : `${stats.expiring_in_7_days} renewals due this week`,
  ]
  return `${parts.join(' · ')}.`
}

function Panel({
  title,
  link,
  className,
  children,
}: {
  title: string
  link?: { to: string; label: string }
  className?: string
  children: ReactNode
}) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <div className="flex items-center justify-between gap-4 px-5 pt-5 pb-3 sm:px-6">
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {link && (
          <Link to={link.to} className="group inline-flex items-center gap-0.5 text-sm font-semibold text-primary hover:underline">
            {link.label}
            <ChevronRight aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        )}
      </div>
      {children}
    </Card>
  )
}

function ToDo({ stats, className }: { stats: Overview['library'] | undefined; className?: string }) {
  const items: { to: string; icon: LucideIcon; label: string; detail: string; count: number | undefined }[] = [
    { to: '/admin/reminders', icon: BellRing, label: 'Reminders to send', detail: 'Ready for WhatsApp or SMS', count: stats?.reminders_to_send ?? 0 },
    { to: '/admin/renewals', icon: CalendarClock, label: 'Renewals this week', detail: 'Memberships ending in 7 days', count: stats?.expiring_in_7_days },
    { to: '/admin/waitlist', icon: ListOrdered, label: 'Waiting list', detail: 'Students waiting for a seat', count: stats?.waiting },
  ]
  return (
    <Panel title="To do today" className={className}>
      <ul className="px-2 pb-2">
        {items.map(({ to, icon: Icon, label, detail, count }) => (
          <li key={to}>
            <Link
              to={to}
              className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-secondary text-secondary-foreground">
                <Icon aria-hidden="true" className="size-[18px]" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">{label}</span>
                <span className="block truncate text-xs text-muted-foreground">{detail}</span>
              </span>
              {count !== undefined && (
                <span
                  className={cn(
                    'min-w-7 rounded-full px-2 py-0.5 text-center text-xs font-bold tabular-nums',
                    count > 0 ? 'bg-accent text-accent-foreground' : 'bg-muted text-muted-foreground',
                  )}
                >
                  {count}
                </span>
              )}
              <ChevronRight aria-hidden="true" className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function Renewals({ className }: { className?: string }) {
  const expiring = useMemberships({ expiring_within: 7, ordering: 'end_date', page_size: 8 })
  const rows = expiring.data?.results
  return (
    <Panel title="Renewals due this week" link={{ to: '/admin/renewals', label: 'See all' }} className={className}>
      {expiring.isPending && (
        <div className="space-y-3 px-5 pb-5 sm:px-6">
          {[0, 1, 2].map((n) => (
            <Skeleton key={n} className="h-12" />
          ))}
        </div>
      )}
      {expiring.error && <p className="px-6 pb-6 text-sm text-destructive">{errorMessage(expiring.error)}</p>}
      {rows?.length === 0 && (
        <div className="px-5 pb-5 sm:px-6">
          <EmptyState icon={CalendarCheck} title="No memberships end in the next 7 days." />
        </div>
      )}
      {rows && rows.length > 0 && (
        <ul className="divide-y border-t">
          {rows.map((m) => (
            <li key={m.id} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/50 sm:px-6">
              <Avatar name={m.student_name} tone="soft" />
              <div className="min-w-0 flex-1">
                <Link to={`/admin/students/${m.student}`} className="block truncate text-sm font-semibold hover:underline">
                  {m.student_name}
                </Link>
                <p className="truncate text-xs text-muted-foreground">
                  Roll {m.roll_no} · Seat {m.seat_number ?? '—'}
                  {m.shift_name && ` · ${m.shift_name}`}
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-3">
                <span className="text-xs text-muted-foreground">Ends {formatDate(m.end_date)}</span>
                <StateBadge state={m.state} daysLeft={m.days_left} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function LatestPayments({ className }: { className?: string }) {
  const latest = usePayments({ page_size: 5 })
  const rows = latest.data?.results
  return (
    <Panel title="Latest payments" link={{ to: '/admin/payments', label: 'All payments' }} className={className}>
      {latest.isPending && (
        <div className="space-y-3 px-5 pb-5 sm:px-6">
          {[0, 1, 2].map((n) => (
            <Skeleton key={n} className="h-10" />
          ))}
        </div>
      )}
      {latest.error && <p className="px-6 pb-6 text-sm text-destructive">{errorMessage(latest.error)}</p>}
      {rows?.length === 0 && <p className="px-6 pb-6 text-sm text-muted-foreground">No payments yet.</p>}
      {rows && rows.length > 0 && (
        <ul className="divide-y border-t">
          {rows.map((p) => (
            <li key={p.id}>
              <Link
                to={`/admin/payments/${p.id}/receipt`}
                className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/50 focus-visible:bg-muted focus-visible:outline-none sm:px-6"
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-muted text-muted-foreground">
                  <ReceiptText aria-hidden="true" className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">{p.student_name}</span>
                  <span className="block text-xs text-muted-foreground">
                    #{p.receipt_no} · {p.mode_label} · {formatDayMonth(p.paid_on)}
                  </span>
                </span>
                {p.is_void ? (
                  <Badge tone="danger">Void</Badge>
                ) : (
                  <span className="text-sm font-semibold tabular-nums">{formatMoney(p.amount)}</span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
