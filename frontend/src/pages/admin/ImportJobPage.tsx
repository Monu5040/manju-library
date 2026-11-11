import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { PageHeader, StatCard } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { useAdminMutation } from '@/lib/queries'
import type { ImportJobDetail, ImportRowInfo } from '@/lib/types'

export default function ImportJobPage() {
  const id = Number(useParams().id)
  const queryClient = useQueryClient()
  const job = useQuery({ queryKey: ['admin', 'import', id], queryFn: () => api<ImportJobDetail>(`/admin/imports/${id}/`) })
  const [mapping, setMapping] = useState<Record<string, number> | null>(null)
  const [skipErrors, setSkipErrors] = useState(false)
  const [confirmUndo, setConfirmUndo] = useState(false)

  const setJob = (data: ImportJobDetail) => {
    queryClient.setQueryData(['admin', 'import', id], data)
    setMapping(null)
  }
  const recheck = useAdminMutation((body: Record<string, unknown>) =>
    api<ImportJobDetail>(`/admin/imports/${id}/check/`, { method: 'POST', body }),
  )
  const commit = useAdminMutation(() =>
    api<ImportJobDetail>(`/admin/imports/${id}/commit/`, { method: 'POST', body: { skip_errors: skipErrors } }),
  )
  const undo = useAdminMutation(() => api<ImportJobDetail>(`/admin/imports/${id}/undo/`, { method: 'POST' }))

  if (job.isPending) return <Spinner label="Loading the import" />
  if (job.error) return <Alert variant="destructive">{errorMessage(job.error)}</Alert>
  const j = job.data
  const s = j.summary
  const editing = j.status === 'CHECKED'
  const current = mapping ?? j.mapping
  const fieldOf = (index: number) => Object.entries(current).find(([, i]) => i === index)?.[0] ?? ''
  const setField = (index: number, field: string) => {
    const next = Object.fromEntries(Object.entries(current).filter(([key, i]) => i !== index && key !== field))
    if (field) next[field] = index
    setMapping(next)
  }
  const busy = recheck.isPending || commit.isPending || undo.isPending
  const error = recheck.error ?? commit.error ?? undo.error

  return (
    <div className="space-y-6">
      <PageHeader
        title={j.file_name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {j.status === 'CHECKED' && <Badge tone="info">Checked — nothing saved yet</Badge>}
            {j.status === 'IMPORTED' && <Badge tone="success">Imported {formatDate(j.imported_at)}</Badge>}
            {j.status === 'UNDONE' && <Badge>Undone {formatDate(j.undone_at)}</Badge>}
            {j.file_format === 'csv' ? `CSV · ${j.encoding} · separator "${j.delimiter === '\t' ? 'tab' : j.delimiter}"` : `Sheet "${j.sheet}"`}
          </span>
        }
        actions={
          <Button asChild variant="outline">
            <Link to="/admin/import">Back to imports</Link>
          </Button>
        }
      />

      {j.duplicate_of && editing && (
        <Alert>This same file was already imported on {formatDate(j.duplicate_of.imported_at)}. Importing it again would add the students twice.</Alert>
      )}
      {error && <Alert variant="destructive">{errorMessage(error)}</Alert>}

      <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {editing ? (
          <>
            <StatCard label="Ready to import" value={s.ready} hint={`of ${s.rows} rows`} />
            <StatCard label="Rows with errors" value={s.errors} hint="Fix in the file, or skip them" />
            <StatCard label="Memberships · payments" value={`${s.memberships} · ${s.payments}`} hint={`${formatMoney(Number(s.amount_paid))} paid in all`} />
            <StatCard label="Waiting list" value={s.waiting_list} hint={`${s.with_warnings} rows have notes to read`} />
          </>
        ) : (
          <>
            <StatCard label="Imported" value={s.imported} />
            <StatCard label="Skipped" value={s.skipped} />
            <StatCard label="Memberships · payments" value={`${s.memberships} · ${s.payments}`} />
            <StatCard label="Waiting list" value={s.waiting_list} />
          </>
        )}
      </dl>

      {editing && (
        <Card>
          <CardHeader>
            <CardTitle>2. Check the columns</CardTitle>
            <CardDescription>
              Matched automatically from the column titles. Calculated columns (days left, status, dues) are worked out by the app instead.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-end gap-4 text-sm">
              {j.sheets.length > 1 && (
                <label className="space-y-1.5">
                  <span className="block font-medium">Sheet</span>
                  <Select className="w-56" value={j.sheet} disabled={busy} onChange={(e) => recheck.mutate({ sheet: e.target.value }, { onSuccess: setJob })}>
                    {j.sheets.map((name) => (
                      <option key={name}>{name}</option>
                    ))}
                  </Select>
                </label>
              )}
              <label className="space-y-1.5">
                <span className="block font-medium">Column titles are on row</span>
                <Input
                  className="w-24"
                  inputMode="numeric"
                  defaultValue={j.header_row + 1}
                  disabled={busy}
                  onBlur={(e) => {
                    const row = Number(e.target.value) - 1
                    if (row >= 0 && row !== j.header_row) recheck.mutate({ header_row: row }, { onSuccess: setJob })
                  }}
                />
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={j.options.create_missing ?? true}
                  disabled={busy}
                  onChange={(e) => recheck.mutate({ create_missing: e.target.checked }, { onSuccess: setJob })}
                />
                Create shifts and seats the file needs
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={j.options.day_first ?? true}
                  disabled={busy}
                  onChange={(e) => recheck.mutate({ day_first: e.target.checked }, { onSuccess: setJob })}
                />
                Dates are day first (05/08 = 5 August)
              </label>
            </div>
            <Table>
              <THead>
                <TR>
                  <TH>Column in the file</TH>
                  <TH>Used as</TH>
                </TR>
              </THead>
              <TBody>
                {j.columns.map((column) => (
                  <TR key={column.index}>
                    <TD className="font-medium">{column.header}</TD>
                    <TD>
                      {column.ignored && !fieldOf(column.index) ? (
                        <span className="text-sm text-muted-foreground">Not needed — calculated by the app</span>
                      ) : (
                        <Select
                          aria-label={`Use of column ${column.header}`}
                          className="max-w-xs"
                          value={fieldOf(column.index)}
                          onChange={(e) => setField(column.index, e.target.value)}
                        >
                          <option value="">Not used</option>
                          {j.fields.map((f) => (
                            <option key={f.key} value={f.key}>
                              {f.label}
                            </option>
                          ))}
                        </Select>
                      )}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            {mapping && (
              <Button disabled={busy} onClick={() => recheck.mutate({ mapping }, { onSuccess: setJob })}>
                {recheck.isPending ? 'Checking…' : 'Check again with these columns'}
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {j.problem_rows.length > 0 && (
        <RowsCard
          title={editing ? `Rows with errors (${j.problem_rows.length})` : `Rows not imported (${j.problem_rows.length})`}
          description="Fix these in your file and upload it again, or skip them and add those students by hand."
          rows={j.problem_rows}
          kind="errors"
          actions={
            <>
              <Button asChild size="sm" variant="outline">
                <a href={`/api/admin/imports/${j.id}/error-file/?file_type=xlsx`}>Download as Excel</a>
              </Button>
              <Button asChild size="sm" variant="outline">
                <a href={`/api/admin/imports/${j.id}/error-file/?file_type=csv`}>CSV</a>
              </Button>
            </>
          }
        />
      )}
      {j.warning_rows.length > 0 && (
        <RowsCard
          title={`Rows with notes (${j.warning_rows.length})`}
          description="These rows import, with the change described."
          rows={j.warning_rows}
          kind="warnings"
        />
      )}

      {editing && (
        <Card>
          <CardHeader>
            <CardTitle>3. Import</CardTitle>
            <CardDescription>Everything is saved in one step: either all of it, or nothing.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-4">
            {s.errors > 0 && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4" checked={skipErrors} onChange={(e) => setSkipErrors(e.target.checked)} />
                Skip the {s.errors} rows with errors
              </label>
            )}
            <Button size="lg" disabled={busy || s.ready === 0 || (s.errors > 0 && !skipErrors)} onClick={() => commit.mutate(undefined, { onSuccess: setJob })}>
              {commit.isPending ? 'Importing…' : `Import ${s.ready} students`}
            </Button>
          </CardContent>
        </Card>
      )}

      {j.status === 'IMPORTED' && (
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
            <p className="text-sm">
              Done. <Link className="font-medium underline" to="/admin/students?view=all">See the students</Link> or the{' '}
              <Link className="font-medium underline" to="/admin/seats">seat map</Link>.
            </p>
            {j.can_undo && (
              <Button variant="outline" className="text-destructive" onClick={() => setConfirmUndo(true)}>
                Undo this import
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {confirmUndo && (
        <Dialog
          open
          onClose={() => setConfirmUndo(false)}
          title="Undo this import?"
          description="Removes every student, membership, payment and waiting-list entry this file created. Not possible once those students have new payments or renewals."
        >
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmUndo(false)}>
              Keep it
            </Button>
            <Button
              variant="destructive"
              disabled={undo.isPending}
              onClick={() => undo.mutate(undefined, { onSuccess: (data) => { setJob(data); setConfirmUndo(false) } })}
            >
              Undo import
            </Button>
          </div>
        </Dialog>
      )}
    </div>
  )
}

function RowsCard({
  title,
  description,
  rows,
  kind,
  actions,
}: {
  title: string
  description: string
  rows: ImportRowInfo[]
  kind: 'errors' | 'warnings'
  actions?: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-4">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        {actions && <div className="flex gap-2">{actions}</div>}
      </CardHeader>
      <CardContent>
        <Table>
          <THead>
            <TR>
              <TH>Row</TH>
              <TH>Student</TH>
              <TH>{kind === 'errors' ? 'What is wrong' : 'Note'}</TH>
            </TR>
          </THead>
          <TBody>
            {rows.map((row) => {
              const values = Object.entries(row.raw)
              const name = row.raw['Name'] ?? values[0]?.[1] ?? ''
              return (
                <TR key={row.row_number}>
                  <TD className="tabular-nums text-muted-foreground">{row.row_number}</TD>
                  <TD className="font-medium">{name || '—'}</TD>
                  <TD>
                    <ul className="space-y-1 text-sm">
                      {(kind === 'errors' ? row.errors : row.warnings).map((message) => (
                        <li key={message} className={kind === 'errors' ? 'text-destructive' : undefined}>
                          {message}
                        </li>
                      ))}
                    </ul>
                  </TD>
                </TR>
              )
            })}
          </TBody>
        </Table>
      </CardContent>
    </Card>
  )
}
