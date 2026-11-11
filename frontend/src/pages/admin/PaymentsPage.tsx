import { Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader, Pagination, StatCard } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney, todayIso } from '@/lib/format'
import { usePaymentSummary, usePayments } from '@/lib/queries'
import { PAYMENT_MODES } from '@/lib/types'

const PAGE_SIZE = 50

export default function PaymentsPage() {
  const [params, setParams] = useSearchParams()
  const paidFrom = params.get('from') ?? todayIso().slice(0, 8) + '01'
  const paidTo = params.get('to') ?? todayIso()
  const mode = params.get('mode') ?? ''
  const page = Number(params.get('page') ?? 1)
  const [q, setQ] = useState(params.get('q') ?? '')

  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in patch)) next.delete('page')
    setParams(next, { replace: true })
  }

  const filters = { paid_from: paidFrom, paid_to: paidTo, mode, q: params.get('q') ?? '' }
  const payments = usePayments({ ...filters, page, page_size: PAGE_SIZE })
  const summary = usePaymentSummary(filters)

  return (
    <div>
      <PageHeader title="Payments" description="Every payment with its receipt number. Void payments are struck through." />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_auto_auto_auto]">
        <form
          role="search"
          className="relative"
          onSubmit={(event) => {
            event.preventDefault()
            update({ q })
          }}
        >
          <Search aria-hidden="true" className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
          <Input aria-label="Search payments" placeholder="Receipt no., name or mobile" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        <Input aria-label="From" type="date" value={paidFrom} onChange={(e) => update({ from: e.target.value })} />
        <Input aria-label="To" type="date" value={paidTo} onChange={(e) => update({ to: e.target.value })} />
        <Select aria-label="Paid by" value={mode} onChange={(e) => update({ mode: e.target.value })}>
          <option value="">All modes</option>
          {PAYMENT_MODES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </Select>
      </div>

      {summary.data && (
        <dl className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label={`Collected ${formatDate(paidFrom)} – ${formatDate(paidTo)}`} value={formatMoney(summary.data.total)} hint={`${summary.data.count} payments`} />
          {summary.data.by_mode.map((row) => (
            <StatCard key={row.mode} label={PAYMENT_MODES.find((m) => m.value === row.mode)?.label ?? row.mode} value={formatMoney(row.total)} hint={`${row.count} payments`} />
          ))}
        </dl>
      )}

      {payments.isPending && <Spinner label="Loading payments" />}
      {payments.error && <Alert variant="destructive">{errorMessage(payments.error)}</Alert>}
      {payments.data?.results.length === 0 && <EmptyState title="No payments in this period." />}
      {payments.data && payments.data.results.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>Receipt</TH>
              <TH>Date</TH>
              <TH>Student</TH>
              <TH>Amount</TH>
              <TH>Paid by</TH>
              <TH>Taken by</TH>
              <TH>
                <span className="sr-only">Receipt</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {payments.data.results.map((p) => (
              <TR key={p.id} className={p.is_void ? 'text-muted-foreground' : undefined}>
                <TD className="tabular-nums">
                  <span className={p.is_void ? 'line-through' : undefined}>#{p.receipt_no}</span>
                  {p.is_void && <Badge className="ml-2">void</Badge>}
                </TD>
                <TD>{formatDate(p.paid_on)}</TD>
                <TD>
                  <Link className="font-medium hover:underline" to={`/admin/students/${p.student}`}>
                    {p.student_name}
                  </Link>
                  <div className="text-xs text-muted-foreground">roll {p.roll_no}</div>
                </TD>
                <TD className={p.is_void ? 'tabular-nums line-through' : 'tabular-nums'}>{formatMoney(p.amount)}</TD>
                <TD>
                  {p.mode_label}
                  {p.reference && <div className="text-xs text-muted-foreground">{p.reference}</div>}
                </TD>
                <TD className="text-sm">{p.collected_by_name ?? '—'}</TD>
                <TD className="text-right">
                  <Button asChild size="sm" variant="ghost">
                    <Link to={`/admin/payments/${p.id}/receipt`}>Receipt</Link>
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      {payments.data && <Pagination page={page} pageSize={PAGE_SIZE} count={payments.data.count} onPage={(p) => update({ page: String(p) })} />}
    </div>
  )
}
