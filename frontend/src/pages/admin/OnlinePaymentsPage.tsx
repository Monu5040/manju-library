import { ArrowLeft, CircleAlert, Globe, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader, Pagination, StatCard } from '@/components/ui/page'
import { Segmented } from '@/components/ui/segmented'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { formatDate, formatDateTime, formatMoney } from '@/lib/format'
import { checkOnlinePayment, markOnlinePaymentSorted, useOnlinePayments, useOnlineSummary } from '@/lib/online'
import { useAdminMutation } from '@/lib/queries'
import type { OnlinePayment, OnlineStatus } from '@/lib/types'

const PAGE_SIZE = 25

const VIEWS = {
  attention: { label: 'Needs attention', params: { needs_attention: true } },
  all: { label: 'All', params: {} },
  paid: { label: 'Paid', params: { status: 'PAID' } },
  waiting: { label: 'Waiting', params: { status: 'PENDING' } },
  closed: { label: 'Not paid', params: { closed: true } },
} as const
type View = keyof typeof VIEWS

const STATUS_TONE: Record<OnlineStatus, 'success' | 'info' | 'warning' | 'neutral'> = {
  PAID: 'success',
  FLAGGED: 'warning',
  PENDING: 'info',
  EXPIRED: 'neutral',
  CANCELLED: 'neutral',
}

export default function OnlinePaymentsPage() {
  const [search, setSearch] = useSearchParams()
  const summary = useOnlineSummary()
  const attention = summary.data?.needs_attention ?? 0
  const requested = search.get('view') as View | null
  const view: View = requested && requested in VIEWS ? requested : attention > 0 ? 'attention' : 'all'
  const page = Number(search.get('page') ?? 1)
  const attempts = useOnlinePayments({ ...VIEWS[view].params, page, page_size: PAGE_SIZE })
  const { data: me } = useMe()
  const isOwner = me?.role === 'SUPER_ADMIN'
  const check = useAdminMutation(checkOnlinePayment)
  const [sorting, setSorting] = useState<OnlinePayment | null>(null)

  const setView = (next: View) => setSearch({ view: next }, { replace: true })

  return (
    <div>
      <PageHeader
        title="Online payments"
        description="What students paid through Razorpay, and attempts they did not finish. Paid ones get a receipt automatically."
        actions={
          <Button asChild variant="ghost">
            <Link to="/admin/payments">
              <ArrowLeft aria-hidden="true" /> All payments
            </Link>
          </Button>
        }
      />

      {summary.data && !summary.data.configured && (
        <Alert className="mb-6" title="Not set up yet">
          The server needs the Razorpay keys and webhook first (see the README, "Online payments"). Then turn it on in{' '}
          <Link className="font-medium underline" to="/admin/settings">
            Settings
          </Link>
          .
        </Alert>
      )}
      {summary.data?.configured && !summary.data.enabled && (
        <Alert className="mb-6">
          Online payments are turned off, so students do not see them.{' '}
          {isOwner ? (
            <Link className="font-medium underline" to="/admin/settings">
              Turn them on in Settings
            </Link>
          ) : (
            'The owner can turn them on in Settings.'
          )}
        </Alert>
      )}
      {summary.data?.configured && summary.data.test_mode && (
        <Alert variant="warning" className="mb-6">
          Razorpay is in test mode: no real money moves. Switch to the live keys before students pay.
          {summary.data.test_mobiles_only && ' Until then only the test numbers in RAZORPAY_TEST_MOBILES can pay online.'}
        </Alert>
      )}

      {summary.data && (
        <dl className="mb-6 grid grid-cols-3 gap-3 sm:gap-4">
          <StatCard label="Needs attention" icon={CircleAlert} value={summary.data.needs_attention} />
          <StatCard label="Paid today" icon={Globe} value={summary.data.paid_today} />
          <StatCard label="Waiting to be paid" icon={RefreshCw} value={summary.data.waiting} />
        </dl>
      )}

      <Segmented
        label="Which payments"
        className="mb-4"
        value={view}
        onChange={setView}
        options={(Object.keys(VIEWS) as View[]).map((key) => ({ value: key, label: VIEWS[key].label }))}
      />

      {check.error && (
        <Alert variant="destructive" className="mb-4">
          {errorMessage(check.error)}
        </Alert>
      )}
      {attempts.isPending && <Spinner label="Loading online payments" />}
      {attempts.error && <Alert variant="destructive">{errorMessage(attempts.error)}</Alert>}
      {attempts.data?.results.length === 0 && (
        <EmptyState icon={Globe} title={view === 'attention' ? 'Nothing needs attention.' : 'No online payments here yet.'} />
      )}
      {attempts.data && attempts.data.results.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>Started</TH>
              <TH>Student</TH>
              <TH>For</TH>
              <TH>Amount</TH>
              <TH>Status</TH>
              <TH className="hidden md:table-cell">Razorpay</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {attempts.data.results.map((a) => (
              <TR key={a.id}>
                <TD className="text-sm whitespace-nowrap">{formatDateTime(a.created_at)}</TD>
                <TD>
                  <Link className="font-medium hover:underline" to={`/admin/students/${a.student}`}>
                    {a.student_name}
                  </Link>
                  <div className="text-xs text-muted-foreground">roll {a.roll_no}</div>
                </TD>
                <TD className="max-w-xs">
                  {a.purpose === 'RENEWAL' ? (
                    <>
                      Renewal{a.plan_name ? `: ${a.plan_name}` : ''}
                      {a.renewal_start && a.renewal_end && (
                        <div className="text-xs text-muted-foreground">
                          {formatDate(a.renewal_start)} – {formatDate(a.renewal_end)}
                        </div>
                      )}
                    </>
                  ) : (
                    'Dues'
                  )}
                  {a.problem && (
                    <p className="mt-1.5 flex gap-1.5 text-xs text-destructive">
                      <CircleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
                      {a.problem}
                    </p>
                  )}
                </TD>
                <TD className="tabular-nums">{formatMoney(a.amount)}</TD>
                <TD>
                  <Badge tone={STATUS_TONE[a.status]}>{a.status_label}</Badge>
                  {a.receipt_no && (
                    <Link className="mt-1 block text-xs font-medium text-primary hover:underline" to={`/admin/payments/${a.payment}/receipt`}>
                      Receipt #{a.receipt_no}
                    </Link>
                  )}
                </TD>
                <TD className="hidden text-xs text-muted-foreground md:table-cell">
                  {a.gateway_payment_id ?? '—'}
                  {a.method && <div>{a.method}</div>}
                </TD>
                <TD className="text-right whitespace-nowrap">
                  {a.status === 'PENDING' && (
                    <Button size="sm" variant="ghost" loading={check.isPending && check.variables === a.id} onClick={() => check.mutate(a.id)}>
                      Check now
                    </Button>
                  )}
                  {a.problem && isOwner && (
                    <Button size="sm" variant="outline" onClick={() => setSorting(a)}>
                      Mark as sorted
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      {attempts.data && (
        <Pagination page={page} pageSize={PAGE_SIZE} count={attempts.data.count} onPage={(p) => setSearch({ view, page: String(p) })} />
      )}
      {sorting && <SortedDialog attempt={sorting} onClose={() => setSorting(null)} />}
    </div>
  )
}

function SortedDialog({ attempt, onClose }: { attempt: OnlinePayment; onClose: () => void }) {
  const [note, setNote] = useState('')
  const save = useAdminMutation(markOnlinePaymentSorted)
  return (
    <Dialog open onClose={onClose} title="Mark as sorted" description={`${attempt.student_name}, ${formatMoney(attempt.amount)}`}>
      <p className="rounded-lg bg-muted/70 px-3 py-2 text-sm">{attempt.problem}</p>
      <form
        className="mt-4 space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate({ id: attempt.id, note }, { onSuccess: onClose })
        }}
      >
        <label className="block text-sm font-medium" htmlFor="sorted-note">
          What was done (for the record)
        </label>
        <Input id="sorted-note" placeholder="For example: refunded ₹450 on Razorpay" value={note} onChange={(e) => setNote(e.target.value)} />
        {save.error && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={save.isPending}>
            Mark as sorted
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
