import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader, StatCard } from '@/components/ui/page'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { fieldErrors } from '@/lib/errors'
import { formatDate, formatMoney } from '@/lib/format'
import { useLedgerImports } from '@/lib/ledger'
import { useAdminMutation } from '@/lib/queries'
import type { LedgerImport, LedgerImportDay } from '@/lib/types'

const DAY_STATUS: Record<LedgerImportDay['status'], { label: string; tone: 'success' | 'neutral' | 'info' }> = {
  add: { label: 'Will add', tone: 'success' },
  covered: { label: 'Already in payments', tone: 'neutral' },
  already: { label: 'Imported before', tone: 'info' },
}

const money = (value: string | undefined) => formatMoney(Number(value ?? 0))

export default function LedgerImportPage() {
  const imports = useLedgerImports()
  const [file, setFile] = useState<File | null>(null)
  const [job, setJob] = useState<LedgerImport | null>(null)
  const check = useAdminMutation((upload: File) => {
    const body = new FormData()
    body.append('file', upload)
    return api<LedgerImport>('/admin/ledger/imports/', { method: 'POST', body })
  })
  const commit = useAdminMutation((id: number) => api<LedgerImport>(`/admin/ledger/imports/${id}/commit/`, { method: 'POST' }))
  const undo = useAdminMutation((id: number) => api<LedgerImport>(`/admin/ledger/imports/${id}/undo/`, { method: 'POST' }))
  // Opening an earlier import only reads it, so nothing else needs refreshing.
  const open = useMutation({ mutationFn: (id: number) => api<LedgerImport>(`/admin/ledger/imports/${id}/`) })
  const errors = fieldErrors(check.error)
  const actionError = commit.error ?? undo.error ?? open.error

  return (
    <div>
      <PageHeader
        title="Import the old Balance Sheet"
        description="Daily collections from the Excel Balance Sheet become past income, so the ledger and analytics start with history."
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/ledger">Back to the ledger</Link>
          </Button>
        }
      />
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Choose the file</CardTitle>
          <CardDescription>The whole workbook is fine: the Balance Sheet is found by its name or its Date and Daily Collection Amount columns. Nothing is saved until you press Import.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              if (file) check.mutate(file, { onSuccess: setJob })
            }}
          >
            <div className="min-w-64 flex-1 space-y-1.5">
              <Label htmlFor="balance-file">Excel or CSV file</Label>
              <Input id="balance-file" type="file" accept=".xlsx,.xls,.csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
            <Button type="submit" disabled={!file || check.isPending}>
              {check.isPending ? 'Checking…' : 'Check file'}
            </Button>
          </form>
          {check.error && (
            <Alert variant="destructive" className="mt-4">
              {errors.file ?? errorMessage(check.error)}
            </Alert>
          )}
        </CardContent>
      </Card>

      {job && (
        <section aria-label="Check result" className="mb-8 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">
              {job.file_name} <Badge tone={job.status === 'IMPORTED' ? 'success' : 'neutral'}>{job.status_label}</Badge>
            </h2>
            <div className="flex gap-2">
              {job.status === 'CHECKED' && (
                <Button
                  disabled={commit.isPending || (job.summary.days_to_add === 0 && job.summary.expenses_to_add === 0)}
                  onClick={() => commit.mutate(job.id, { onSuccess: setJob })}
                >
                  {commit.isPending ? 'Importing…' : 'Import'}
                </Button>
              )}
              {job.can_undo && (
                <Button variant="outline" disabled={undo.isPending} onClick={() => undo.mutate(job.id, { onSuccess: setJob })}>
                  Undo this import
                </Button>
              )}
            </div>
          </div>
          {actionError && <Alert variant="destructive">{errorMessage(actionError)}</Alert>}
          {job.status === 'IMPORTED' && <Alert variant="success">Imported. The entries are in the ledger as past income from the old Balance Sheet.</Alert>}
          <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard
              label="Days in the sheet"
              value={job.summary.income_days}
              hint={job.summary.first_day ? `${formatDate(job.summary.first_day)} – ${formatDate(job.summary.last_day)}` : undefined}
            />
            <StatCard label="Sheet total" value={money(job.summary.sheet_income)} />
            <StatCard label="Will add as past income" value={money(job.summary.income_to_add)} hint={`${job.summary.days_to_add} days`} />
            <StatCard label="Expenses to add" value={money(job.summary.expense_total_to_add)} hint={`${job.summary.expenses_to_add} lines`} />
          </dl>
          <p className="text-sm text-muted-foreground">
            Excel kept only each student’s latest payment, so part of a day may already be here as a payment. Only the rest is added, so nothing is counted twice.
          </p>
          {job.income && job.income.length > 0 && (
            <Table>
              <THead>
                <TR>
                  <TH>Date</TH>
                  <TH className="text-right">Students</TH>
                  <TH className="text-right">In the sheet</TH>
                  <TH className="text-right">Already recorded</TH>
                  <TH className="text-right">Adds</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {job.income.map((d) => (
                  <TR key={d.day}>
                    <TD className="whitespace-nowrap">{formatDate(d.day)}</TD>
                    <TD className="text-right tabular-nums">{d.students || '—'}</TD>
                    <TD className="text-right tabular-nums">{money(d.sheet_amount)}</TD>
                    <TD className="text-right tabular-nums">{money(d.recorded)}</TD>
                    <TD className="text-right font-medium tabular-nums">{money(d.to_add)}</TD>
                    <TD>
                      <Badge tone={DAY_STATUS[d.status].tone}>{DAY_STATUS[d.status].label}</Badge>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
          {job.expenses && job.expenses.length > 0 && (
            <Table>
              <THead>
                <TR>
                  <TH>Date</TH>
                  <TH>Details</TH>
                  <TH>Category</TH>
                  <TH className="text-right">Amount</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {job.expenses.map((e) => (
                  <TR key={`${e.row}-${e.day}`}>
                    <TD className="whitespace-nowrap">{formatDate(e.day)}</TD>
                    <TD>{e.details}</TD>
                    <TD>{e.category_name}</TD>
                    <TD className="text-right tabular-nums">{money(e.amount)}</TD>
                    <TD>
                      <Badge tone={e.status === 'add' ? 'success' : 'info'}>{e.status === 'add' ? 'Will add' : 'Imported before'}</Badge>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
          {job.errors && job.errors.length > 0 && (
            <Alert variant="destructive">
              <p className="font-medium">These lines could not be read and are left out:</p>
              <ul className="mt-1 list-disc pl-5">
                {job.errors.map((e) => (
                  <li key={`${e.side}-${e.row}`}>
                    Row {e.row} ({e.side.toLowerCase()}): {e.message}
                  </li>
                ))}
              </ul>
            </Alert>
          )}
        </section>
      )}

      {imports.data && imports.data.results.length > 0 && (
        <section aria-label="Earlier imports">
          <h2 className="mb-3 text-lg font-semibold">Earlier imports</h2>
          <Table>
            <THead>
              <TR>
                <TH>File</TH>
                <TH>Checked</TH>
                <TH>Status</TH>
                <TH className="text-right">Past income added</TH>
                <TH>
                  <span className="sr-only">Open</span>
                </TH>
              </TR>
            </THead>
            <TBody>
              {imports.data.results.map((i) => (
                <TR key={i.id}>
                  <TD>{i.file_name}</TD>
                  <TD className="whitespace-nowrap">{formatDate(i.created_at)}</TD>
                  <TD>{i.status_label}</TD>
                  <TD className="text-right tabular-nums">{i.status === 'IMPORTED' ? money(i.summary.income_to_add) : '—'}</TD>
                  <TD className="text-right">
                    <Button size="sm" variant="ghost" onClick={() => open.mutate(i.id, { onSuccess: setJob })}>
                      Open
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </section>
      )}
    </div>
  )
}
