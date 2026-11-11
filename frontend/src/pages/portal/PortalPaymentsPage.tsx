import { Link } from 'react-router'
import { StateBadge } from '@/components/admin/badges'
import { ProfileSwitcher } from '@/components/portal/ProfileSwitcher'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { usePortalStudent, useSelectedProfile } from '@/lib/portal'

export default function PortalPaymentsPage() {
  const { home, profiles, selected, select } = useSelectedProfile()
  const detail = usePortalStudent(selected?.id)

  if (home.isPending || (selected && detail.isPending)) return <Spinner label="Loading payments" />
  const error = home.error ?? detail.error
  if (error) return <Alert variant="destructive">{errorMessage(error)}</Alert>
  if (!selected || !detail.data) return null
  const d = detail.data

  return (
    <div className="space-y-6">
      <ProfileSwitcher profiles={profiles} selectedId={selected.id} onSelect={select} />
      <PageHeader title="Payments and receipts" description="Every payment you made, with its receipt." />

      {d.payments.length === 0 ? (
        <EmptyState title="No payments yet." />
      ) : (
        <ul className="divide-y rounded-xl border bg-card">
          {d.payments.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div>
                <div className={p.is_void ? 'font-medium tabular-nums text-muted-foreground line-through' : 'font-medium tabular-nums'}>
                  {formatMoney(p.amount)}
                </div>
                <div className="text-sm text-muted-foreground">
                  {formatDate(p.paid_on)} · {p.mode_label} · receipt #{p.receipt_no}
                </div>
              </div>
              {p.is_void ? (
                <Badge>cancelled</Badge>
              ) : (
                <Button asChild size="sm" variant="outline">
                  <Link to={`/portal/receipts/${p.id}`}>Receipt</Link>
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {d.memberships.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Memberships</h2>
          <ul className="divide-y rounded-xl border bg-card">
            {d.memberships.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
                <span>
                  <span className="font-medium">
                    {formatDate(m.start_date)} – {formatDate(m.end_date)}
                  </span>
                  <span className="block text-muted-foreground">
                    Seat {m.seat_number ?? '—'} · {m.shift_name ?? m.time_label} · {formatMoney(m.net_fee)}
                  </span>
                </span>
                <StateBadge state={m.state} daysLeft={m.days_left} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
