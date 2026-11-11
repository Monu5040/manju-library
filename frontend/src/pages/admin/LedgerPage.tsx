import { useState } from 'react'
import { Link } from 'react-router'
import { ExportMenu } from '@/components/admin/ExportMenu'
import { RangeFilter } from '@/components/admin/RangeFilter'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { PageHeader, StatCard } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { useDailyLedger } from '@/lib/ledger'
import { useSearchState } from '@/lib/params'
import { rangeFromParams } from '@/lib/ranges'
import { cn } from '@/lib/utils'

export default function LedgerPage() {
  const [params, update] = useSearchState()
  const { preset, range } = rangeFromParams(params)
  const ledger = useDailyLedger(range)
  const [showQuiet, setShowQuiet] = useState(false)
  const data = ledger.data
  const days = data?.days.filter((d) => showQuiet || d.income || d.expenses) ?? []

  return (
    <div>
      <PageHeader
        title="Ledger"
        description="Money in and out, day by day: what the Balance Sheet in Excel used to show."
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/admin/ledger/import">Import old Balance Sheet</Link>
            </Button>
            <ExportMenu path="/admin/ledger/daily/" params={range} />
          </>
        }
      />
      <RangeFilter preset={preset} range={range} onChange={update}>
        <label className="flex items-center gap-2 pb-2.5 text-sm">
          <input type="checkbox" className="size-4" checked={showQuiet} onChange={(e) => setShowQuiet(e.target.checked)} />
          Show days with nothing recorded
        </label>
      </RangeFilter>

      {ledger.isPending && <Spinner label="Loading the ledger" />}
      {ledger.error && <Alert variant="destructive">{errorMessage(ledger.error)}</Alert>}
      {data && (
        <div className={cn('transition-opacity', ledger.isFetching && 'opacity-60')}>
          <dl className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Fees" value={formatMoney(data.totals.fees)} hint={`${data.totals.students} student payments`} />
            <StatCard label="Other income" value={formatMoney(data.totals.other_income)} />
            <StatCard label="Expenses" value={formatMoney(data.totals.expenses)} />
            <StatCard label="Balance" value={formatMoney(data.totals.balance)} hint="Income minus expenses" />
          </dl>
          {days.length === 0 ? (
            <p className="rounded-xl border border-dashed bg-card px-6 py-12 text-center text-sm text-muted-foreground">Nothing recorded between these dates.</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Date</TH>
                  <TH className="text-right">Students paid</TH>
                  <TH className="text-right">Fees</TH>
                  <TH className="text-right">Other income</TH>
                  <TH className="text-right">Expenses</TH>
                  <TH className="text-right">Balance</TH>
                </TR>
              </THead>
              <TBody>
                {days.map((d) => (
                  <TR key={d.day} className={!d.income && !d.expenses ? 'text-muted-foreground' : undefined}>
                    <TD className="whitespace-nowrap">{formatDate(d.day)}</TD>
                    <TD className="text-right tabular-nums">{d.students || '—'}</TD>
                    <TD className="text-right tabular-nums">
                      {d.fees ? (
                        <Link className="hover:underline" to={`/admin/payments?from=${d.day}&to=${d.day}`}>
                          {formatMoney(d.fees)}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </TD>
                    <TD className="text-right tabular-nums">{d.other_income ? formatMoney(d.other_income) : '—'}</TD>
                    <TD className="text-right tabular-nums">
                      {d.expenses ? (
                        <Link className="hover:underline" to={`/admin/expenses?from=${d.day}&to=${d.day}`}>
                          {formatMoney(d.expenses)}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </TD>
                    <TD className={cn('text-right font-medium tabular-nums', d.balance < 0 && 'text-destructive')}>{formatMoney(d.balance)}</TD>
                  </TR>
                ))}
              </TBody>
              <tfoot>
                <TR className="border-t-2 font-semibold">
                  <TD>Total</TD>
                  <TD className="text-right tabular-nums">{data.totals.students}</TD>
                  <TD className="text-right tabular-nums">{formatMoney(data.totals.fees)}</TD>
                  <TD className="text-right tabular-nums">{formatMoney(data.totals.other_income)}</TD>
                  <TD className="text-right tabular-nums">{formatMoney(data.totals.expenses)}</TD>
                  <TD className={cn('text-right tabular-nums', data.totals.balance < 0 && 'text-destructive')}>{formatMoney(data.totals.balance)}</TD>
                </TR>
              </tfoot>
            </Table>
          )}
        </div>
      )}
    </div>
  )
}
