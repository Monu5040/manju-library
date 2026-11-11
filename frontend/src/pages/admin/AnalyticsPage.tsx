import { Download } from 'lucide-react'
import { Link } from 'react-router'
import { RangeFilter } from '@/components/admin/RangeFilter'
import { BarList } from '@/components/charts/BarList'
import { ChartCard, ExportLinks, StatTile } from '@/components/charts/ChartCard'
import { type ColumnPoint, ColumnChart, type Series } from '@/components/charts/ColumnChart'
import { SeatHeatmap } from '@/components/charts/SeatHeatmap'
import { SLOT_COLORS } from '@/components/charts/slots'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDate, formatDayMonth, formatMoney, formatMonth } from '@/lib/format'
import { useAnalytics } from '@/lib/ledger'
import { useSearchState } from '@/lib/params'
import { rangeFromParams } from '@/lib/ranges'
import type { Analytics, Grain, Occupancy } from '@/lib/types'
import { cn } from '@/lib/utils'

const SERIES: Series[] = [
  { key: 'income', label: 'Income', color: 'var(--chart-income)' },
  { key: 'expenses', label: 'Expenses', color: 'var(--chart-expense)' },
]
const DUE_COLORS = ['var(--chart-step-1)', 'var(--chart-step-2)', 'var(--chart-step-3)']
const GRAIN_WORD: Record<Grain, string> = { day: 'day', month: 'month', year: 'year' }

export default function AnalyticsPage() {
  const [params, update] = useSearchState()
  const { preset, range } = rangeFromParams(params)
  const grain = params.get('grain') ?? ''
  const query = useAnalytics({ ...range, grain })
  const data = query.data
  const exportParams: Record<string, string> = { from: range.from, to: range.to, ...(grain ? { grain } : {}) }
  const everything = `/api/admin/analytics/export/?${new URLSearchParams({ ...exportParams, section: 'all', file_type: 'xlsx' }).toString()}`

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="How full the library is, what it earns and who may leave. Only you can see this page."
        actions={
          <Button asChild variant="outline">
            <a href={everything}>
              <Download aria-hidden="true" /> Export everything (Excel)
            </a>
          </Button>
        }
      />
      <RangeFilter preset={preset} range={range} onChange={update}>
        <div className="w-full space-y-1.5 sm:w-44">
          <Label htmlFor="grain">Income by</Label>
          <Select id="grain" value={grain} onChange={(e) => update({ grain: e.target.value })}>
            <option value="">Best fit</option>
            <option value="day">Day</option>
            <option value="month">Month</option>
            <option value="year">Year</option>
          </Select>
        </div>
        {data && (
          <p className="pb-2 text-sm text-muted-foreground">
            {formatDate(data.from)} – {formatDate(data.to)}, compared with {formatDate(data.previous.from)} – {formatDate(data.previous.to)}
          </p>
        )}
      </RangeFilter>

      {query.isPending && <Spinner label="Loading analytics" />}
      {query.error && <Alert variant="destructive">{errorMessage(query.error)}</Alert>}
      {data && (
        <div className={cn('space-y-6 transition-opacity', query.isFetching && 'opacity-60')} aria-busy={query.isFetching}>
          <KeyNumbers data={data} />
          <ChartCard
            title="Income and expenses"
            description={`By ${GRAIN_WORD[data.grain]}. Income is fees plus other income; profit is income minus expenses.`}
            actions={<ExportLinks sections={[{ key: 'revenue', label: 'Income and expenses' }]} params={exportParams} />}
            chart={<RevenueChart data={data} />}
            table={<RevenueTable data={data} />}
          />
          <ChartCard
            title={`Seats on ${formatDate(data.occupancy.date)}`}
            description="Taken for the whole shift, partly booked (a custom time), or free to sell."
            actions={
              <ExportLinks
                sections={[
                  { key: 'occupancy', label: 'Seat by seat' },
                  { key: 'free_slots', label: 'Free slots' },
                ]}
                params={exportParams}
              />
            }
            chart={
              <div className="space-y-8">
                <ShiftBars occupancy={data.occupancy} />
                <SeatHeatmap occupancy={data.occupancy} />
                <FreeSlots occupancy={data.occupancy} />
              </div>
            }
            table={<ShiftTable occupancy={data.occupancy} />}
          />
          <div className="grid items-start gap-6 xl:grid-cols-2">
            <Retention data={data} params={exportParams} />
            <Collections data={data} params={exportParams} />
          </div>
          <Mix data={data} params={exportParams} />
        </div>
      )}
    </div>
  )
}

function KeyNumbers({ data }: { data: Analytics }) {
  const k = data.kpis
  return (
    <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatTile label="Income" value={formatMoney(k.income.value)} current={k.income.value} previous={k.income.previous} format={formatMoney} hint={`Fees ${formatMoney(k.fees.value)}`} />
      <StatTile label="Expenses" value={formatMoney(k.expenses.value)} current={k.expenses.value} previous={k.expenses.previous} format={formatMoney} upIsGood={false} />
      <StatTile label="Profit" value={formatMoney(k.profit.value)} current={k.profit.value} previous={k.profit.previous} format={formatMoney} />
      <StatTile label="New admissions" value={k.new_admissions.value} current={k.new_admissions.value} previous={k.new_admissions.previous} format={String} />
      <StatTile label={`Members on ${formatDate(data.as_of)}`} value={k.active_members.value} />
      <StatTile label="Occupancy" value={`${k.occupancy_percent.value}%`} hint={`of seat-hours sold · ${k.seats_in_use.value} of ${k.seats_in_use.of} seats in use`} />
      <StatTile
        label="Dues outstanding today"
        value={formatMoney(k.outstanding_dues.value)}
        hint={
          <Link className="underline" to="/admin/students?view=due">
            See who owes
          </Link>
        }
      />
      <StatTile
        label="Ending in the next 7 days"
        value={k.expiring_in_7_days.value}
        hint={
          <Link className="underline" to="/admin/renewals">
            Renewals
          </Link>
        }
      />
    </dl>
  )
}

function RevenueChart({ data }: { data: Analytics }) {
  if (!data.revenue.some((r) => r.income || r.expenses)) {
    return <p className="py-10 text-center text-sm text-muted-foreground">No income or expenses recorded in this period.</p>
  }
  const points: ColumnPoint[] = data.revenue.map((r) => ({
    key: r.period,
    label: data.grain === 'day' ? formatDate(r.period) : r.label,
    tick: data.grain === 'day' ? formatDayMonth(r.period) : data.grain === 'month' ? formatMonth(r.period) : r.label,
    values: { income: r.income, expenses: r.expenses },
    extra: [{ label: 'Profit', value: r.profit }],
  }))
  const total = data.revenue.reduce((sum, r) => sum + r.income, 0)
  return <ColumnChart points={points} series={SERIES} summary={`Income and expenses by ${GRAIN_WORD[data.grain]}; income ${formatMoney(total)} in total`} />
}

function RevenueTable({ data }: { data: Analytics }) {
  return (
    <Table>
      <THead>
        <TR>
          <TH>{data.grain === 'day' ? 'Day' : data.grain === 'month' ? 'Month' : 'Year'}</TH>
          <TH className="text-right">Fees</TH>
          <TH className="text-right">Other income</TH>
          <TH className="text-right">Expenses</TH>
          <TH className="text-right">Profit</TH>
        </TR>
      </THead>
      <TBody>
        {data.revenue.map((r) => (
          <TR key={r.period}>
            <TD>{data.grain === 'day' ? formatDate(r.period) : r.label}</TD>
            <TD className="text-right tabular-nums">{formatMoney(r.fees)}</TD>
            <TD className="text-right tabular-nums">{formatMoney(r.other_income)}</TD>
            <TD className="text-right tabular-nums">{formatMoney(r.expenses)}</TD>
            <TD className={cn('text-right font-medium tabular-nums', r.profit < 0 && 'text-destructive')}>{formatMoney(r.profit)}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  )
}

/** One thin segmented bar per shift: taken, partly booked, free. The figures are beside it. */
function ShiftBars({ occupancy }: { occupancy: Occupancy }) {
  if (!occupancy.shifts.length || !occupancy.seats_total) {
    return <p className="text-sm text-muted-foreground">Add shifts and seats in Settings to see occupancy.</p>
  }
  return (
    <ul className="space-y-3" aria-label="Seats taken in each shift">
      {occupancy.shifts.map((s) => {
        const share = (n: number) => `${(n / occupancy.seats_total) * 100}%`
        return (
          <li key={s.id} className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[11rem_1fr_15rem] sm:items-center">
            <span>
              <span className="font-medium">{s.name}</span> <span className="text-xs text-muted-foreground">{s.time_label}</span>
            </span>
            <span aria-hidden="true" className="flex h-2 gap-0.5 overflow-hidden rounded-full">
              {s.taken > 0 && <span style={{ width: share(s.taken), background: SLOT_COLORS.taken }} />}
              {s.partly > 0 && <span style={{ width: share(s.partly), background: SLOT_COLORS.partly }} />}
              {s.free > 0 && <span style={{ width: share(s.free), background: SLOT_COLORS.free }} />}
            </span>
            <span className="text-muted-foreground tabular-nums sm:text-right">
              {s.taken} taken{s.partly ? ` · ${s.partly} partly` : ''} · {s.free} free
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function FreeSlots({ occupancy }: { occupancy: Occupancy }) {
  const open = occupancy.shifts.filter((s) => s.free > 0)
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium">Free seats you can sell</h3>
      {open.length === 0 ? (
        <p className="text-sm text-muted-foreground">Every seat is taken in every shift.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {open.map((s) => (
            <li key={s.id}>
              <span className="font-medium">
                {s.name} ({s.free})
              </span>
              : <span className="text-muted-foreground">seats {s.free_seats.join(', ')}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ShiftTable({ occupancy }: { occupancy: Occupancy }) {
  return (
    <Table>
      <THead>
        <TR>
          <TH>Shift</TH>
          <TH className="text-right">Taken</TH>
          <TH className="text-right">Partly</TH>
          <TH className="text-right">Free</TH>
          <TH>Free seats</TH>
        </TR>
      </THead>
      <TBody>
        {occupancy.shifts.map((s) => (
          <TR key={s.id}>
            <TD>
              {s.name}
              <div className="text-xs text-muted-foreground">{s.time_label}</div>
            </TD>
            <TD className="text-right tabular-nums">{s.taken}</TD>
            <TD className="text-right tabular-nums">{s.partly}</TD>
            <TD className="text-right tabular-nums">{s.free}</TD>
            <TD className="text-sm">{s.free_seats.join(', ') || '—'}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  )
}

function Retention({ data, params }: { data: Analytics; params: Record<string, string> }) {
  const r = data.retention
  return (
    <ChartCard
      title="Renewals"
      description="Memberships that ended in this period. Renewed means a new membership within 15 days."
      actions={
        <ExportLinks
          sections={[
            { key: 'renewals', label: 'Renewals' },
            { key: 'cohorts', label: 'Still members, by month joined' },
          ]}
          params={params}
        />
      }
      chart={
        <div className="space-y-6">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Figure label="Renewal rate" value={r.renewal_rate === null ? '—' : `${r.renewal_rate}%`} />
            <Figure label="Renewed" value={r.renewed} />
            <Figure label="Left" value={r.left} />
            <Figure label="Undecided" value={r.undecided} hint="ended under 15 days ago" />
          </dl>
          <p className="text-sm text-muted-foreground">
            {r.average_stay_months === null
              ? 'No one left in this period.'
              : `Students who left had stayed ${r.average_stay_months} months on average.`}
          </p>
          <div>
            <h3 className="mb-2 text-sm font-medium">Still members, by the month they joined</h3>
            <Table>
              <THead>
                <TR>
                  <TH>Joined</TH>
                  <TH className="text-right">Students</TH>
                  <TH className="text-right">Still here</TH>
                  <TH className="w-1/3">
                    <span className="sr-only">Share still here</span>
                  </TH>
                </TR>
              </THead>
              <TBody>
                {r.cohorts.map((c) => (
                  <TR key={c.month}>
                    <TD>{c.label}</TD>
                    <TD className="text-right tabular-nums">{c.joined}</TD>
                    <TD className="text-right tabular-nums">{c.joined ? `${c.still_members} (${c.percent}%)` : '—'}</TD>
                    <TD>
                      {c.joined > 0 && (
                        <span aria-hidden="true" className="block h-2 overflow-hidden rounded-full" style={{ background: 'var(--chart-empty)' }}>
                          <span className="block h-full rounded-full" style={{ width: `${c.percent ?? 0}%`, background: 'var(--chart-income)' }} />
                        </span>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        </div>
      }
    />
  )
}

function Figure({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-2xl font-semibold">{value}</dd>
      {hint && <dd className="text-xs text-muted-foreground">{hint}</dd>}
    </div>
  )
}

function Collections({ data, params }: { data: Analytics; params: Record<string, string> }) {
  const c = data.collections
  const dues = c.dues_by_age.map((d, i) => ({
    key: d.label,
    label: d.label,
    value: d.amount,
    display: formatMoney(d.amount),
    color: DUE_COLORS[i],
    detail: d.count ? `${d.count} membership${d.count === 1 ? '' : 's'}` : undefined,
  }))
  const modes = c.payment_modes.map((m) => ({
    key: m.mode,
    label: m.label,
    value: m.amount,
    display: formatMoney(m.amount),
    detail: `${m.count} payment${m.count === 1 ? '' : 's'}`,
  }))
  return (
    <ChartCard
      title="Collections"
      description="Dues still unpaid today, by how long since the membership started; and how fees were paid in this period."
      actions={
        <ExportLinks
          sections={[
            { key: 'dues', label: 'Dues by age' },
            { key: 'modes', label: 'Payment modes' },
          ]}
          params={params}
        />
      }
      chart={
        <div className="space-y-6">
          <div>
            <h3 className="mb-3 text-sm font-medium">Unpaid for</h3>
            <BarList rows={dues} label="Dues by how long they have been unpaid" empty="No dues outstanding." />
          </div>
          <div>
            <h3 className="mb-3 text-sm font-medium">Fees paid by</h3>
            <BarList rows={modes} label="Fees by payment mode" empty="No fees collected in this period." />
          </div>
        </div>
      }
      table={
        <Table>
          <THead>
            <TR>
              <TH>Group</TH>
              <TH className="text-right">Amount</TH>
              <TH className="text-right">Count</TH>
            </TR>
          </THead>
          <TBody>
            {c.dues_by_age.map((d) => (
              <TR key={d.label}>
                <TD>Unpaid {d.label}</TD>
                <TD className="text-right tabular-nums">{formatMoney(d.amount)}</TD>
                <TD className="text-right tabular-nums">{d.count}</TD>
              </TR>
            ))}
            {c.payment_modes.map((m) => (
              <TR key={m.mode}>
                <TD>Paid by {m.label}</TD>
                <TD className="text-right tabular-nums">{formatMoney(m.amount)}</TD>
                <TD className="text-right tabular-nums">{m.count}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      }
    />
  )
}

function Mix({ data, params }: { data: Analytics; params: Record<string, string> }) {
  const groups = [
    { key: 'by_shift', title: 'By shift', rows: data.mix.by_shift },
    { key: 'by_plan', title: 'By plan length', rows: data.mix.by_plan },
    { key: 'by_gender', title: 'By gender', rows: data.mix.by_gender },
  ] as const
  return (
    <ChartCard
      title={`Members on ${formatDate(data.mix.date)}`}
      description="Current memberships by shift and plan length, and members by gender."
      actions={<ExportLinks sections={[{ key: 'mix', label: 'Member mix' }]} params={params} />}
      chart={
        <div className="grid gap-8 md:grid-cols-3">
          {groups.map((g) => (
            <div key={g.key} className="min-w-0">
              <h3 className="mb-3 text-sm font-medium">{g.title}</h3>
              <BarList
                rows={g.rows.map((r) => ({ key: r.label, label: r.label, value: r.count, display: String(r.count) }))}
                label={`Members ${g.title.toLowerCase()}`}
                empty="No current members."
              />
            </div>
          ))}
        </div>
      }
      table={
        <Table>
          <THead>
            <TR>
              <TH>By</TH>
              <TH>Group</TH>
              <TH className="text-right">Members</TH>
            </TR>
          </THead>
          <TBody>
            {groups.flatMap((g) =>
              g.rows.map((r) => (
                <TR key={`${g.key}-${r.label}`}>
                  <TD className="text-muted-foreground">{g.title.replace('By ', '')}</TD>
                  <TD>{r.label}</TD>
                  <TD className="text-right tabular-nums">{r.count}</TD>
                </TR>
              )),
            )}
          </TBody>
        </Table>
      }
    />
  )
}
