import { Alert } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { formatMoney } from '@/lib/format'
import { usePortalHome } from '@/lib/portal'

export default function PortalFeesPage() {
  const home = usePortalHome()
  if (home.isPending) return <Spinner label="Loading fees" />
  if (home.error) return <Alert variant="destructive">{errorMessage(home.error)}</Alert>
  const { shifts, plans, library } = home.data
  return (
    <div className="space-y-6">
      <PageHeader title="Fees and timings" description="Renew or change your plan at the front desk." />
      <Card>
        <CardHeader>
          <CardTitle>Timings</CardTitle>
        </CardHeader>
        <CardContent>
          {shifts.length === 0 ? (
            <EmptyState title="Timings will be listed here soon." />
          ) : (
            <ul className="divide-y">
              {shifts.map((s) => (
                <li key={s.id} className="flex justify-between gap-4 py-2 text-sm">
                  <span className="font-medium">{s.name}</span>
                  <span className="text-muted-foreground">
                    {s.time_label} · {s.hours} h
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Plans and fees</CardTitle>
        </CardHeader>
        <CardContent>
          {plans.length === 0 ? (
            <EmptyState title="Ask at the front desk for current fees." />
          ) : (
            <ul className="divide-y">
              {plans.map((p) => (
                <li key={p.id} className="flex justify-between gap-4 py-2 text-sm">
                  <span>
                    <span className="font-medium">{p.name}</span>
                    <span className="block text-muted-foreground">
                      {p.duration_months} month{p.duration_months > 1 ? 's' : ''}
                      {p.shift_name ? ` · ${p.shift_name}` : ''}
                    </span>
                  </span>
                  <span className="font-medium tabular-nums">{formatMoney(p.price)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      {library?.phone && (
        <p className="text-sm text-muted-foreground">
          Questions? Call <a className="font-medium underline" href={`tel:${library.phone}`}>{library.phone}</a>.
        </p>
      )}
    </div>
  )
}
