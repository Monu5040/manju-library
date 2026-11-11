import { CircleCheck } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { EmptyState, PageHeader, Pagination } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { fieldErrors } from '@/lib/errors'
import { formatDate, formatMoney, todayIso } from '@/lib/format'
import { useCashClosings, useCashPreview } from '@/lib/ledger'
import { useAdminMutation } from '@/lib/queries'
import type { CashClosing, CashPreview } from '@/lib/types'
import { cn } from '@/lib/utils'

export default function CashBookPage() {
  const [today] = useState(todayIso)
  const [day, setDay] = useState(today)
  const [page, setPage] = useState(1)
  const preview = useCashPreview(day)
  const closings = useCashClosings(page)

  return (
    <div>
      <PageHeader title="Cash book" description="Count the cash drawer at the end of the day. UPI, card and bank payments are not part of it." />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Close a day</CardTitle>
            <CardDescription>Days are closed in order. Each closing covers every day since the one before.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="cash-day">Day</Label>
              <Input id="cash-day" type="date" max={today} value={day} onChange={(e) => setDay(e.target.value)} />
            </div>
            {preview.isPending && <Spinner label="Working out the cash" />}
            {preview.error && <Alert variant="destructive">{errorMessage(preview.error)}</Alert>}
            {preview.data &&
              (preview.data.closing ? (
                <ClosedDay closing={preview.data.closing} />
              ) : preview.data.can_close ? (
                <CloseForm key={preview.data.day} preview={preview.data} />
              ) : (
                <Alert>{preview.data.blocked_reason}</Alert>
              ))}
          </CardContent>
        </Card>
        <div className="min-w-0">
          <h2 className="mb-3 text-lg font-semibold">Past closings</h2>
          {closings.data?.results.length === 0 && <EmptyState title="No days closed yet." />}
          {closings.data && closings.data.results.length > 0 && (
            <Table>
              <THead>
                <TR>
                  <TH>Day</TH>
                  <TH className="text-right">Opening</TH>
                  <TH className="text-right">In</TH>
                  <TH className="text-right">Out</TH>
                  <TH className="text-right">Expected</TH>
                  <TH className="text-right">Counted</TH>
                  <TH className="text-right">Difference</TH>
                </TR>
              </THead>
              <TBody>
                {closings.data.results.map((c) => (
                  <TR key={c.id}>
                    <TD className="whitespace-nowrap">
                      {formatDate(c.day)}
                      {c.period_start !== c.day && <div className="text-xs text-muted-foreground">from {formatDate(c.period_start)}</div>}
                      <div className="text-xs text-muted-foreground">{c.closed_by_name}</div>
                    </TD>
                    <TD className="text-right tabular-nums">{formatMoney(c.opening)}</TD>
                    <TD className="text-right tabular-nums">{formatMoney(c.cash_in)}</TD>
                    <TD className="text-right tabular-nums">
                      {formatMoney(c.cash_out + c.removed)}
                      {c.removed > 0 && <div className="text-xs text-muted-foreground">{formatMoney(c.removed)} taken out</div>}
                    </TD>
                    <TD className="text-right tabular-nums">{formatMoney(c.expected)}</TD>
                    <TD className="text-right tabular-nums">{formatMoney(c.counted)}</TD>
                    <TD className="text-right">
                      <Difference amount={c.difference} />
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
          {closings.data && <Pagination page={page} pageSize={25} count={closings.data.count} onPage={setPage} />}
        </div>
      </div>
    </div>
  )
}

/** Short, extra or matching: the words carry the meaning, the colour only adds to it. */
function Difference({ amount }: { amount: number }) {
  if (amount === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-success">
        <CircleCheck aria-hidden="true" className="size-4" /> Matches
      </span>
    )
  }
  return amount < 0 ? (
    <span className="font-medium text-destructive">Short by {formatMoney(-amount)}</span>
  ) : (
    <span className="font-medium">{formatMoney(amount)} extra</span>
  )
}

function Line({ label, value, hint, strong }: { label: ReactNode; value: ReactNode; hint?: ReactNode; strong?: boolean }) {
  return (
    <div className={cn('flex items-start justify-between gap-4 py-1.5', strong && 'border-t pt-3 font-semibold')}>
      <dt>
        {label}
        {hint && <span className="block text-xs font-normal text-muted-foreground">{hint}</span>}
      </dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  )
}

function CloseForm({ preview }: { preview: CashPreview }) {
  const firstTime = preview.opening === null
  const [opening, setOpening] = useState('')
  const [removed, setRemoved] = useState('')
  const [counted, setCounted] = useState('')
  const [note, setNote] = useState('')
  const start = firstTime ? Number(opening || 0) : (preview.opening ?? 0)
  const expected = start + preview.cash_in - preview.cash_out - Number(removed || 0)
  const since = preview.period_start !== preview.day ? `since ${formatDate(preview.period_start)}` : undefined
  const close = useAdminMutation(() =>
    api('/admin/cash-closings/', {
      method: 'POST',
      body: { day: preview.day, counted, removed: removed || '0', note, ...(firstTime ? { opening: opening || '0' } : {}) },
    }),
  )
  const errors = fieldErrors(close.error)

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        close.mutate()
      }}
    >
      {close.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(close.error)}</Alert>}
      {firstTime && (
        <Field label="Cash in the drawer at the start" id="cash-opening" error={errors.opening} hint="Only asked for the very first closing.">
          <Input id="cash-opening" type="number" inputMode="decimal" min="0" step="0.01" required value={opening} onChange={(e) => setOpening(e.target.value)} />
        </Field>
      )}
      <dl className="text-sm">
        {!firstTime && <Line label="Opening cash" hint={preview.previous_day && `counted on ${formatDate(preview.previous_day)}`} value={formatMoney(preview.opening)} />}
        <Line label="+ Cash fees" hint={[`${preview.fee_count} payments`, since].filter(Boolean).join(', ')} value={formatMoney(preview.fees)} />
        {preview.other_income > 0 && <Line label="+ Other cash income" value={formatMoney(preview.other_income)} />}
        <Line label="− Cash expenses" hint={`${preview.expense_count} entries`} value={formatMoney(preview.expenses)} />
        {Number(removed) > 0 && <Line label="− Taken out" value={formatMoney(Number(removed))} />}
        <Line strong label="Should be in the drawer" value={formatMoney(expected)} />
      </dl>
      <Field label="Taken out of the drawer (₹)" id="cash-removed" error={errors.removed} hint="A bank deposit, or cash handed to the owner.">
        <Input id="cash-removed" type="number" inputMode="decimal" min="0" step="0.01" value={removed} onChange={(e) => setRemoved(e.target.value)} />
      </Field>
      <Field label="Counted in the drawer (₹)" id="cash-counted" error={errors.counted}>
        <Input id="cash-counted" type="number" inputMode="decimal" min="0" step="0.01" required value={counted} onChange={(e) => setCounted(e.target.value)} />
      </Field>
      {counted !== '' && (
        <p className="text-sm" role="status">
          <Difference amount={Math.round((Number(counted) - expected) * 100) / 100} />
        </p>
      )}
      <Field label="Note" id="cash-note" error={errors.note}>
        <Input id="cash-note" value={note} placeholder="For example: ₹500 change given from my pocket" onChange={(e) => setNote(e.target.value)} />
      </Field>
      <Button type="submit" className="w-full" disabled={close.isPending}>
        {close.isPending ? 'Closing…' : `Close ${formatDate(preview.day)}`}
      </Button>
    </form>
  )
}

function ClosedDay({ closing }: { closing: CashClosing }) {
  const { data: me } = useMe()
  const reopen = useAdminMutation(() => api(`/admin/cash-closings/${closing.id}/`, { method: 'DELETE' }))
  return (
    <div className="space-y-4">
      <dl className="text-sm">
        <Line label="Opening cash" value={formatMoney(closing.opening)} />
        <Line label="+ Cash in" value={formatMoney(closing.cash_in)} />
        <Line label="− Cash out" value={formatMoney(closing.cash_out)} />
        {closing.removed > 0 && <Line label="− Taken out" value={formatMoney(closing.removed)} />}
        <Line strong label="Expected" value={formatMoney(closing.expected)} />
        <Line label="Counted" value={formatMoney(closing.counted)} />
        <Line label="Difference" value={<Difference amount={closing.difference} />} />
      </dl>
      <p className="text-xs text-muted-foreground">
        Closed by {closing.closed_by_name ?? '—'}
        {closing.note && `: ${closing.note}`}
      </p>
      {reopen.error && <Alert variant="destructive">{errorMessage(reopen.error)}</Alert>}
      {me?.role === 'SUPER_ADMIN' && (
        <Button variant="outline" size="sm" disabled={reopen.isPending} onClick={() => reopen.mutate()}>
          Reopen this day
        </Button>
      )}
    </div>
  )
}
