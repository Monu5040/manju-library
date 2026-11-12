import { ArrowRight, CalendarDays, CircleCheck, Clock, MapPin, Megaphone, Phone, Pin, RefreshCw, Wallet } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { PayDuesButton, RenewOnlineDialog } from '@/components/portal/OnlinePayment'
import { ProfileSwitcher } from '@/components/portal/ProfileSwitcher'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/page'
import { Skeleton } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { daysLeftLabel, firstName, formatDate, formatDayMonth, formatLongDate, formatMoney, todayIso } from '@/lib/format'
import { usePortalOnline, useSelectedProfile } from '@/lib/portal'
import type { LibraryInfo, Notice, PortalMembership, PortalOnline, PortalStudent } from '@/lib/types'
import { cn } from '@/lib/utils'

export default function PortalHomePage() {
  const { home, profiles, selected, select } = useSelectedProfile()
  const online = usePortalOnline(selected?.id)
  const [renewing, setRenewing] = useState(false)

  if (home.isPending) return <HomeSkeleton />
  if (home.error) return <Alert variant="destructive">{errorMessage(home.error)}</Alert>
  if (!selected) {
    return (
      <EmptyState title="Your login is not linked to a student record yet.">
        Please speak to the front desk and they will connect it.
      </EmptyState>
    )
  }

  const m = selected.current_membership
  const library = home.data.library
  const query = `?profile=${selected.id}`
  // Online payments (Razorpay), when the library has turned them on.
  const pay = online.data?.available ? online.data : undefined
  const renewal = pay?.renewal && pay.renewal.options.some((o) => !o.unavailable) ? pay.renewal : null
  const openRenewal = renewal ? () => setRenewing(true) : undefined

  return (
    <div className="animate-fade-in space-y-6">
      <ProfileSwitcher profiles={profiles} selectedId={selected.id} onSelect={select} />
      <header className="space-y-1">
        <p className="text-xs font-semibold tracking-[0.08em] text-primary uppercase">{formatLongDate(todayIso())}</p>
        <h1 className="font-display text-[2rem] leading-tight font-semibold tracking-[-0.01em] sm:text-[2.375rem]">
          Hello, {firstName(selected.full_name)}
        </h1>
        <p className="text-[15px] text-muted-foreground">
          Roll no. {selected.roll_no}
          {selected.branch_name && ` · ${selected.branch_name}`}
        </p>
      </header>

      {m && (m.state === 'EXPIRED' || (m.state === 'ACTIVE' && m.days_left <= 7)) && (
        <Alert variant={m.state === 'EXPIRED' ? 'destructive' : 'warning'}>
          {m.state === 'EXPIRED' ? `Your membership ended on ${formatDate(m.end_date)}.` : `Your membership ends on ${formatDate(m.end_date)}.`}{' '}
          {openRenewal ? 'Renew online now, or at the front desk, to keep your seat.' : 'Renew at the front desk to keep your seat.'}
          {openRenewal && (
            <Button size="sm" className="mt-2 flex" onClick={openRenewal}>
              <RefreshCw aria-hidden="true" /> Renew online
            </Button>
          )}
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        {m ? (
          <MembershipPass membership={m} student={selected} onRenew={openRenewal} />
        ) : (
          <Card className="flex flex-col justify-center p-6 sm:p-8">
            <h2 className="font-display text-2xl font-semibold">No current membership</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
              Ask at the front desk for a seat. Fees and timings are listed on the Fees page.
            </p>
            <Button asChild variant="outline" className="mt-5 self-start">
              <Link to={`/portal/fees${query}`}>
                See fees and timings <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </Card>
        )}
        <div className="grid content-start gap-5">
          <DuesCard student={selected} membership={m} query={query} online={pay} />
          {library && (library.address || library.phone) && <LibraryCard library={library} query={query} />}
        </div>
      </div>

      <Notices notices={home.data.notices} />

      {renewing && renewal && pay && (
        <RenewOnlineDialog studentId={selected.id} renewal={renewal} testMode={pay.test_mode} onClose={() => setRenewing(false)} />
      )}
    </div>
  )
}

/** The membership as a library pass: seat and timing large, with a ring for the days left. */
function MembershipPass({
  membership: m,
  student,
  onRenew,
}: {
  membership: PortalMembership
  student: PortalStudent
  onRenew?: () => void
}) {
  const total = Math.max(1, (Date.parse(m.end_date) - Date.parse(m.start_date)) / 86_400_000 + 1)
  const left = Math.max(0, Math.min(total, m.days_left + 1))
  const percent = m.state === 'UPCOMING' ? 100 : m.state === 'ACTIVE' ? Math.round((left / total) * 100) : 0
  const soon = m.state === 'ACTIVE' && m.days_left <= 7

  return (
    <section
      aria-label="Your membership"
      className="relative isolate animate-rise-in overflow-hidden rounded-3xl bg-sidebar text-sidebar-foreground shadow-float"
    >
      {/* The reading lamp's light, as on the sign-in page. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 -right-24 -z-10 size-96 rounded-full bg-[radial-gradient(closest-side,oklch(0.8_0.13_82/0.22),transparent)]"
      />
      <div className="flex items-start justify-between gap-4 px-6 pt-6 sm:px-7 sm:pt-7">
        <div>
          <p className="text-[11px] font-bold tracking-[0.14em] text-accent uppercase">Membership pass</p>
          <p className="mt-1 text-sm text-sidebar-muted">{m.plan_name ?? 'Membership'}</p>
        </div>
        <PassState membership={m} />
      </div>

      <div className="flex items-center justify-between gap-5 px-6 pt-5 pb-6 sm:px-7">
        <dl className="min-w-0 space-y-4">
          <div>
            <dt className="text-xs font-semibold tracking-wide text-sidebar-muted uppercase">Seat</dt>
            <dd className="font-display text-[3.5rem] leading-none font-semibold tracking-tight">{m.seat_number ?? '—'}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-sidebar-muted uppercase">
              <Clock aria-hidden="true" className="size-3.5" /> Timing
            </dt>
            <dd className="mt-0.5 font-semibold">{m.shift_name ?? 'Custom time'}</dd>
            <dd className="text-sm text-sidebar-foreground/80">{m.time_label}</dd>
          </div>
        </dl>
        <DaysLeftRing membership={m} percent={percent} soon={soon} />
      </div>

      {/* A ticket's perforation, with the two notches cut from the page. */}
      <div aria-hidden="true" className="relative mx-6 border-t border-dashed border-sidebar-border sm:mx-7">
        <span className="absolute -top-3 -left-9 size-6 rounded-full bg-background sm:-left-10" />
        <span className="absolute -top-3 -right-9 size-6 rounded-full bg-background sm:-right-10" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 px-6 py-4 text-sm sm:px-7">
        <span className="font-semibold">
          {student.full_name} <span className="font-normal text-sidebar-muted">· Roll {student.roll_no}</span>
        </span>
        <span className="inline-flex items-center gap-1.5 text-sidebar-muted">
          <CalendarDays aria-hidden="true" className="size-4" />
          {formatDate(m.start_date)} – {formatDate(m.end_date)}
        </span>
      </div>
      {student.renewed_until ? (
        <p className="mx-6 mb-6 flex items-center gap-2 rounded-xl bg-sidebar-hover px-4 py-2.5 text-sm sm:mx-7">
          <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-accent" />
          Renewed: your seat is yours until {formatDate(student.renewed_until)}.
        </p>
      ) : (
        onRenew && (
          <div className="px-6 pb-6 sm:px-7">
            <Button variant="accent" className="w-full" onClick={onRenew}>
              <RefreshCw aria-hidden="true" /> Renew online
            </Button>
          </div>
        )
      )}
    </section>
  )
}

function PassState({ membership: m }: { membership: PortalMembership }) {
  const [label, tone] =
    m.state === 'EXPIRED'
      ? ['Ended', 'bg-destructive/20 text-[oklch(0.86_0.08_27)] ring-destructive/40']
      : m.state === 'UPCOMING'
        ? ['Starts soon', 'bg-sidebar-active text-sidebar-foreground ring-sidebar-border']
        : m.state === 'CANCELLED'
          ? ['Cancelled', 'bg-sidebar-active text-sidebar-muted ring-sidebar-border']
          : m.days_left <= 7
            ? ['Renew soon', 'bg-accent/20 text-accent ring-accent/40']
            : ['Active', 'bg-[oklch(0.72_0.13_152/0.18)] text-[oklch(0.86_0.1_152)] ring-[oklch(0.72_0.13_152/0.35)]']
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', tone)}>
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      {label}
    </span>
  )
}

function DaysLeftRing({ membership: m, percent, soon }: { membership: PortalMembership; percent: number; soon: boolean }) {
  const radius = 44
  const circumference = 2 * Math.PI * radius
  const [big, small] =
    m.state === 'UPCOMING'
      ? ['Starts', formatDayMonth(m.start_date)]
      : m.state !== 'ACTIVE'
        ? ['Ended', formatDayMonth(m.end_date)]
        : m.days_left === 0
          ? ['Last', 'day today']
          : [String(m.days_left), m.days_left === 1 ? 'day left' : 'days left']
  const spoken = m.state === 'UPCOMING' ? `Starts on ${formatDate(m.start_date)}` : daysLeftLabel(m.days_left)
  return (
    <div
      role="progressbar"
      aria-label="Time left in this membership"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-valuetext={spoken}
      className="relative grid size-32 shrink-0 place-items-center sm:size-36"
    >
      <svg viewBox="0 0 100 100" className="absolute inset-0 size-full -rotate-90" aria-hidden="true">
        <circle cx="50" cy="50" r={radius} fill="none" strokeWidth="7" className="stroke-sidebar-hover" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - percent / 100)}
          className={cn(
            'transition-[stroke-dashoffset] duration-700 ease-out',
            m.state === 'EXPIRED' ? 'stroke-destructive' : soon ? 'stroke-warning' : 'stroke-accent',
          )}
        />
      </svg>
      <span aria-hidden="true" className="text-center">
        <span className={cn('block leading-none font-bold tracking-tight tabular-nums', /^\d+$/.test(big) ? 'text-4xl' : 'text-xl')}>{big}</span>
        <span className="mt-1 block text-xs text-sidebar-muted">{small}</span>
      </span>
    </div>
  )
}

function DuesCard({
  student,
  membership: m,
  query,
  online,
}: {
  student: PortalStudent
  membership: PortalMembership | null
  query: string
  online?: PortalOnline
}) {
  const owes = student.total_due > 0
  const dues = online?.dues ?? []
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start gap-4">
        <span
          className={cn(
            'grid size-11 shrink-0 place-items-center rounded-2xl',
            owes ? 'bg-destructive/10 text-destructive' : 'bg-success/10 text-success',
          )}
        >
          {owes ? <Wallet aria-hidden="true" className="size-5" /> : <CircleCheck aria-hidden="true" className="size-5" />}
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-medium text-muted-foreground">Fees</h2>
          {owes ? (
            <>
              <p className="mt-0.5 text-2xl font-semibold tracking-tight">{formatMoney(student.total_due)} is due</p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {dues.length > 0
                  ? 'Pay online now, or at the front desk. The receipt appears here.'
                  : 'Pay at the front desk (cash or UPI) and the receipt appears here.'}
              </p>
            </>
          ) : (
            <>
              <p className="mt-0.5 text-2xl font-semibold tracking-tight">All paid up</p>
              <p className="mt-1 text-sm text-muted-foreground">Thank you. Your receipts are saved here.</p>
            </>
          )}
        </div>
      </div>
      {m && (
        <dl className="mt-5 grid grid-cols-3 gap-2 rounded-xl bg-muted/70 px-4 py-3 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">Fee</dt>
            <dd className="font-semibold tabular-nums">{formatMoney(m.net_fee)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Paid</dt>
            <dd className="font-semibold tabular-nums">{formatMoney(m.paid_total)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Balance</dt>
            <dd className={cn('font-semibold tabular-nums', m.due_total > 0 && 'text-destructive')}>{formatMoney(m.due_total)}</dd>
          </div>
        </dl>
      )}
      {online && dues.length > 0 && (
        <div className="mt-5 space-y-3">
          {dues.map((due) => (
            <PayDuesButton
              key={due.membership}
              studentId={student.id}
              due={due}
              testMode={online.test_mode}
              label={dues.length > 1 ? `Pay ${formatMoney(due.amount)} for ${formatDate(due.start_date)} – ${formatDate(due.end_date)}` : undefined}
            />
          ))}
        </div>
      )}
      <Link
        to={`/portal/payments${query}`}
        className="group mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline"
      >
        Payments and receipts
        <ArrowRight aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-0.5" />
      </Link>
    </Card>
  )
}

function LibraryCard({ library, query }: { library: LibraryInfo; query: string }) {
  return (
    <Card className="p-5 sm:p-6">
      <h2 className="font-semibold">{library.name}</h2>
      {library.address && (
        <p className="mt-2 flex items-start gap-2 text-sm leading-relaxed text-muted-foreground">
          <MapPin aria-hidden="true" className="mt-0.5 size-4 shrink-0" /> {library.address}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        {library.phone && (
          <Button asChild variant="secondary" size="sm">
            <a href={`tel:${library.phone}`}>
              <Phone aria-hidden="true" /> Call {library.phone}
            </a>
          </Button>
        )}
        <Button asChild variant="ghost" size="sm">
          <Link to={`/portal/fees${query}`}>Fees and timings</Link>
        </Button>
      </div>
    </Card>
  )
}

function Notices({ notices }: { notices: Notice[] }) {
  return (
    <section aria-labelledby="notices" className="pt-2">
      <h2 id="notices" className="mb-3 flex items-center gap-2 text-lg font-semibold">
        <Megaphone aria-hidden="true" className="size-5 text-primary" /> Notices
      </h2>
      {notices.length === 0 ? (
        <p className="rounded-2xl border border-dashed px-5 py-6 text-sm text-muted-foreground">
          Nothing new from the library. Notices about holidays and timings will show up here.
        </p>
      ) : (
        <ul className="space-y-3">
          {notices.map((n) => (
            <li key={n.id}>
              <Card className={cn('p-5', n.is_pinned && 'border-accent/50 bg-[color-mix(in_oklch,var(--accent)_7%,var(--card))]')}>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <h3 className="font-semibold">{n.title}</h3>
                  {n.is_pinned && (
                    <Badge tone="accent">
                      <Pin aria-hidden="true" className="size-3" /> Pinned
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground sm:ml-auto">{formatDate(n.starts_on)}</span>
                </div>
                <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-foreground/85">{n.body}</p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function HomeSkeleton() {
  return (
    <div role="status" aria-label="Loading your details" className="space-y-6">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-10 w-56" />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        <Skeleton className="h-72 rounded-3xl" />
        <div className="space-y-5">
          <Skeleton className="h-40 rounded-2xl" />
          <Skeleton className="h-28 rounded-2xl" />
        </div>
      </div>
    </div>
  )
}
