import { useQuery } from '@tanstack/react-query'
import { FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/ui/page'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { fieldErrors } from '@/lib/errors'
import { formatDate } from '@/lib/format'
import { useAdminMutation } from '@/lib/queries'
import type { ImportJob, ImportJobDetail, Paginated } from '@/lib/types'

const STATUS: Record<ImportJob['status'], { label: string; tone: 'info' | 'success' | 'neutral' }> = {
  CHECKED: { label: 'Checked, not imported', tone: 'info' },
  IMPORTED: { label: 'Imported', tone: 'success' },
  UNDONE: { label: 'Undone', tone: 'neutral' },
}

export default function ImportPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const history = useQuery({
    queryKey: ['admin', 'imports'],
    queryFn: () => api<Paginated<ImportJob>>('/admin/imports/'),
  })
  const upload = useAdminMutation((chosen: File) => {
    const form = new FormData()
    form.append('file', chosen)
    return api<ImportJobDetail>('/admin/imports/', { method: 'POST', body: form })
  })
  const errors = fieldErrors(upload.error)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Import students"
        description="Bring in students from your Excel workbook or a CSV file. Nothing is saved until you choose Import."
      />
      <Card>
        <CardHeader>
          <CardTitle>1. Choose the file</CardTitle>
          <CardDescription>
            Your existing Admission Sheet works as it is. Or start from a template:{' '}
            <a className="underline" href="/api/admin/imports/template/?file_type=xlsx">
              Excel template
            </a>{' '}
            ·{' '}
            <a className="underline" href="/api/admin/imports/template/?file_type=csv">
              CSV template
            </a>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-center gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              if (file) upload.mutate(file, { onSuccess: (job) => navigate(`/admin/import/${job.id}`) })
            }}
          >
            <label className="flex flex-1 cursor-pointer items-center gap-3 rounded-lg border border-dashed px-4 py-6 hover:bg-muted/50">
              <FileSpreadsheet aria-hidden="true" className="size-6 text-muted-foreground" />
              <span className="text-sm">
                {file ? <span className="font-medium">{file.name}</span> : 'Click to choose an .xlsx, .xls or .csv file (up to 10 MB)'}
              </span>
              <input
                type="file"
                className="sr-only"
                aria-label="Spreadsheet file"
                accept=".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <Button type="submit" size="lg" disabled={!file || upload.isPending}>
              {upload.isPending ? 'Reading the file…' : 'Check the file'}
            </Button>
          </form>
          {upload.error && <Alert variant="destructive" className="mt-4">{errors.file ?? errorMessage(upload.error)}</Alert>}
        </CardContent>
      </Card>

      {history.data && history.data.results.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Earlier files</h2>
          <Table>
            <THead>
              <TR>
                <TH>File</TH>
                <TH>Status</TH>
                <TH>Rows</TH>
                <TH>When</TH>
              </TR>
            </THead>
            <TBody>
              {history.data.results.map((job) => (
                <TR key={job.id}>
                  <TD>
                    <Link className="font-medium hover:underline" to={`/admin/import/${job.id}`}>
                      {job.file_name}
                    </Link>
                  </TD>
                  <TD>
                    <Badge tone={STATUS[job.status].tone}>{STATUS[job.status].label}</Badge>
                  </TD>
                  <TD className="text-sm text-muted-foreground">
                    {job.status === 'CHECKED'
                      ? `${job.summary.ready} ready · ${job.summary.errors} with errors`
                      : `${job.summary.imported} imported · ${job.summary.skipped} skipped`}
                  </TD>
                  <TD>{formatDate(job.imported_at ?? job.created_at)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </section>
      )}
    </div>
  )
}
