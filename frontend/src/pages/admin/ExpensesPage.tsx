import { Search } from 'lucide-react'
import { useState } from 'react'
import { ExportMenu } from '@/components/admin/ExportMenu'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader, Pagination, StatCard } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { fieldErrors } from '@/lib/errors'
import { formatDate, formatMoney, todayIso } from '@/lib/format'
import { useLedgerCategories, useLedgerEntries, useLedgerSummary } from '@/lib/ledger'
import { useSearchState } from '@/lib/params'
import { useAdminMutation } from '@/lib/queries'
import { type LedgerEntry, type LedgerKind, PAYMENT_MODES, type PaymentMode } from '@/lib/types'

const PAGE_SIZE = 50
const KIND_WORD: Record<LedgerKind, string> = { EXPENSE: 'expense', INCOME: 'other income' }

export default function ExpensesPage() {
  const { data: me } = useMe()
  const owner = me?.role === 'SUPER_ADMIN'
  const [params, update] = useSearchState()
  const [today] = useState(todayIso)
  const from = params.get('from') ?? today.slice(0, 8) + '01'
  const to = params.get('to') ?? today
  const kind = params.get('kind') ?? ''
  const category = params.get('category') ?? ''
  const page = Number(params.get('page') ?? 1)
  const [q, setQ] = useState(params.get('q') ?? '')
  const filters = { date_from: from, date_to: to, kind, category, q: params.get('q') ?? '' }
  const entries = useLedgerEntries({ ...filters, page, page_size: PAGE_SIZE })
  const summary = useLedgerSummary(filters)
  const categories = useLedgerCategories()
  const [editing, setEditing] = useState<{ kind: LedgerKind; entry?: LedgerEntry } | null>(null)
  const [voiding, setVoiding] = useState<LedgerEntry | null>(null)

  return (
    <div>
      <PageHeader
        title="Expenses"
        description={
          owner
            ? 'Rent, bills, salaries and other money paid out, and income that is not a student’s fee.'
            : 'Money you paid out or received that is not a student’s fee. You see the entries you made.'
        }
        actions={
          <>
            <Button onClick={() => setEditing({ kind: 'EXPENSE' })}>Add expense</Button>
            <Button variant="outline" onClick={() => setEditing({ kind: 'INCOME' })}>
              Add other income
            </Button>
            <ExportMenu path="/admin/ledger/entries/export/" params={filters} />
          </>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_auto_auto_auto_auto]">
        <form
          role="search"
          className="relative"
          onSubmit={(event) => {
            event.preventDefault()
            update({ q })
          }}
        >
          <Search aria-hidden="true" className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
          <Input aria-label="Search expenses" placeholder="Details, paid to, bill no." className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        <Input aria-label="From" type="date" value={from} onChange={(e) => update({ from: e.target.value })} />
        <Input aria-label="To" type="date" value={to} onChange={(e) => update({ to: e.target.value })} />
        <Select aria-label="Type" value={kind} onChange={(e) => update({ kind: e.target.value, category: '' })}>
          <option value="">Expenses and income</option>
          <option value="EXPENSE">Expenses</option>
          <option value="INCOME">Other income</option>
        </Select>
        <Select aria-label="Category" value={category} onChange={(e) => update({ category: e.target.value })}>
          <option value="">All categories</option>
          {categories.data
            ?.filter((c) => !kind || c.kind === kind)
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
        </Select>
      </div>

      {summary.data && (
        <dl className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label={`Expenses ${formatDate(from)} – ${formatDate(to)}`} value={formatMoney(summary.data.expenses)} />
          <StatCard label="Other income" value={formatMoney(summary.data.other_income)} />
          {summary.data.by_category
            .filter((c) => c.kind === 'EXPENSE')
            .slice(0, 2)
            .map((c) => (
              <StatCard key={c.category} label={c.name} value={formatMoney(c.total)} hint={`${c.count} entr${c.count === 1 ? 'y' : 'ies'}`} />
            ))}
        </dl>
      )}

      {entries.isPending && <Spinner label="Loading expenses" />}
      {entries.error && <Alert variant="destructive">{errorMessage(entries.error)}</Alert>}
      {entries.data?.results.length === 0 && <EmptyState title="Nothing recorded in this period." />}
      {entries.data && entries.data.results.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>Date</TH>
              <TH>Category</TH>
              <TH>Details</TH>
              <TH className="text-right">Amount</TH>
              <TH>Paid by</TH>
              <TH>Entered by</TH>
              {owner && (
                <TH>
                  <span className="sr-only">Actions</span>
                </TH>
              )}
            </TR>
          </THead>
          <TBody>
            {entries.data.results.map((e) => (
              <TR key={e.id} className={e.is_void ? 'text-muted-foreground' : undefined}>
                <TD className="whitespace-nowrap">{formatDate(e.entry_date)}</TD>
                <TD>
                  {e.category_name}
                  <div className="mt-0.5 flex flex-wrap gap-1">
                    {e.kind === 'INCOME' && <Badge tone="info">income</Badge>}
                    {e.source === 'BALANCE_SHEET' && <Badge>old sheet</Badge>}
                    {e.is_void && <Badge>void</Badge>}
                  </div>
                </TD>
                <TD className="max-w-xs text-sm">
                  {e.details || '—'}
                  {(e.party || e.reference) && <div className="text-xs text-muted-foreground">{[e.party, e.reference].filter(Boolean).join(' · ')}</div>}
                  {e.is_void && <div className="text-xs">Void: {e.void_reason}</div>}
                </TD>
                <TD className={e.is_void ? 'text-right tabular-nums line-through' : 'text-right font-medium tabular-nums'}>{formatMoney(e.amount)}</TD>
                <TD className="text-sm">{e.mode_label}</TD>
                <TD className="text-sm">{e.created_by_name ?? '—'}</TD>
                {owner && (
                  <TD className="text-right whitespace-nowrap">
                    {!e.is_void && (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => setEditing({ kind: e.kind, entry: e })}>
                          Edit
                        </Button>
                        <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setVoiding(e)}>
                          Void
                        </Button>
                      </>
                    )}
                  </TD>
                )}
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      {entries.data && <Pagination page={page} pageSize={PAGE_SIZE} count={entries.data.count} onPage={(p) => update({ page: String(p) })} />}
      {editing && <EntryDialog kind={editing.kind} entry={editing.entry} onClose={() => setEditing(null)} />}
      {voiding && <VoidDialog entry={voiding} onClose={() => setVoiding(null)} />}
    </div>
  )
}

function EntryDialog({ kind, entry, onClose }: { kind: LedgerKind; entry?: LedgerEntry; onClose: () => void }) {
  const categories = useLedgerCategories()
  const [today] = useState(todayIso)
  const options =
    categories.data?.filter(
      (c) => c.kind === kind && (c.id === entry?.category || (c.is_active && c.code !== 'past-fees')),
    ) ?? []
  const [draft, setDraft] = useState({
    category: entry ? String(entry.category) : '',
    entry_date: entry?.entry_date ?? today,
    amount: entry ? String(entry.amount) : '',
    mode: (entry?.mode ?? 'CASH') as PaymentMode,
    party: entry?.party ?? '',
    details: entry?.details ?? '',
    reference: entry?.reference ?? '',
  })
  const set = (patch: Partial<typeof draft>) => setDraft({ ...draft, ...patch })
  const save = useAdminMutation(() =>
    api(entry ? `/admin/ledger/entries/${entry.id}/` : '/admin/ledger/entries/', {
      method: entry ? 'PATCH' : 'POST',
      body: { ...draft, category: draft.category ? Number(draft.category) : null },
    }),
  )
  const errors = fieldErrors(save.error)
  const word = KIND_WORD[kind]
  return (
    <Dialog open onClose={onClose} wide title={entry ? `Edit ${word}` : kind === 'EXPENSE' ? 'Add an expense' : 'Add other income'}>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive" className="sm:col-span-2">{errorMessage(save.error)}</Alert>}
        <Field label="Category" id="e-category" error={errors.category}>
          <Select id="e-category" required value={draft.category} onChange={(e) => set({ category: e.target.value })}>
            <option value="">Choose…</option>
            {options.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Date" id="e-date" error={errors.entry_date}>
          <Input id="e-date" type="date" required max={today} value={draft.entry_date} onChange={(e) => set({ entry_date: e.target.value })} />
        </Field>
        <Field label="Amount (₹)" id="e-amount" error={errors.amount}>
          <Input id="e-amount" type="number" inputMode="decimal" min="1" step="0.01" required value={draft.amount} onChange={(e) => set({ amount: e.target.value })} />
        </Field>
        <Field label={kind === 'EXPENSE' ? 'Paid by' : 'Received by'} id="e-mode" error={errors.mode} hint="Only cash counts in the cash book.">
          <Select id="e-mode" value={draft.mode} onChange={(e) => set({ mode: e.target.value as PaymentMode })}>
            {PAYMENT_MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={kind === 'EXPENSE' ? 'Paid to' : 'Received from'} id="e-party" error={errors.party}>
          <Input id="e-party" value={draft.party} onChange={(e) => set({ party: e.target.value })} />
        </Field>
        <Field label="Bill no. or reference" id="e-reference" error={errors.reference}>
          <Input id="e-reference" value={draft.reference} onChange={(e) => set({ reference: e.target.value })} />
        </Field>
        <Field label="What for" id="e-details" error={errors.details} className="sm:col-span-2">
          <Input id="e-details" value={draft.details} placeholder={kind === 'EXPENSE' ? 'For example: electricity bill for October' : 'For example: locker rent'} onChange={(e) => set({ details: e.target.value })} />
        </Field>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

function VoidDialog({ entry, onClose }: { entry: LedgerEntry; onClose: () => void }) {
  const [reason, setReason] = useState('')
  const void_ = useAdminMutation(() => api(`/admin/ledger/entries/${entry.id}/void/`, { method: 'POST', body: { reason } }))
  const errors = fieldErrors(void_.error)
  return (
    <Dialog open onClose={onClose} title="Void this entry?" description={`${entry.category_name}, ${formatMoney(entry.amount)} on ${formatDate(entry.entry_date)}. It stays in the list, struck through, and leaves the totals.`}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          void_.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {void_.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(void_.error)}</Alert>}
        <Field label="Reason" id="void-reason" error={errors.reason}>
          <Input id="void-reason" required value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="destructive" disabled={void_.isPending}>
            Void entry
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
