import { CircleAlert, CircleCheck, CircleDashed, Clock, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { useSystemStatus } from '@/lib/automation'
import type { JobState, SystemStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

const GUIDE = 'https://github.com/Monu5040/manju-library#going-live'

const JOB_STATES: Record<JobState, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' | 'info' }> = {
  ok: { label: 'On time', tone: 'success' },
  running: { label: 'Running now', tone: 'info' },
  late: { label: 'Late', tone: 'warning' },
  failed: { label: 'Failed', tone: 'danger' },
  waiting: { label: 'Waiting for its first run', tone: 'neutral' },
}

const time = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })

/** "reminders: closed 0, created 12" from what a job returned. */
function describe(summary: Record<string, unknown>): string {
  if (typeof summary.error === 'string') return summary.error
  const words = (key: string) => key.replace(/_/g, ' ')
  return Object.entries(summary)
    .map(([key, value]) =>
      value && typeof value === 'object'
        ? `${key}: ${Object.entries(value as Record<string, unknown>)
            .map(([k, v]) => `${words(k)} ${v}`)
            .join(', ')}`
        : `${words(key)} ${value}`,
    )
    .join('; ')
}

function Status({ ok, children }: { ok: boolean; children: ReactNode }) {
  const Icon = ok ? CircleCheck : CircleAlert
  return (
    <span className={cn('inline-flex items-center gap-1.5 font-medium', ok ? 'text-success' : 'text-destructive')}>
      <Icon aria-hidden="true" className="size-4" />
      {children}
    </span>
  )
}

export default function SystemPage() {
  const status = useSystemStatus()
  const data = status.data
  return (
    <div>
      <PageHeader
        title="System status"
        description="Whether everything behind the scenes is working. Checked when you open this page."
        actions={
          <Button variant="outline" disabled={status.isFetching} onClick={() => status.refetch()}>
            <RefreshCw aria-hidden="true" className={status.isFetching ? 'animate-spin' : undefined} /> Check again
          </Button>
        }
      />
      {status.isPending && <Spinner label="Checking the system" />}
      {status.error && <Alert variant="destructive">{errorMessage(status.error)}</Alert>}
      {data && (
        <div className={cn('grid gap-6 lg:grid-cols-2', status.isFetching && 'opacity-60')}>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Services</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="divide-y">
                {data.checks.map((c) => (
                  <li key={c.label} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5 text-sm">
                    <span className="font-medium">{c.label}</span>
                    <Status ok={c.ok}>{c.ok ? 'Working' : 'Not working'}</Status>
                    <span className="w-full text-xs text-muted-foreground">{c.detail}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Server data={data} />
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg">Scheduled jobs</CardTitle>
              <CardDescription>Times are India time. A job is late when it has missed its usual run.</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <THead>
                  <TR>
                    <TH>Job</TH>
                    <TH>State</TH>
                    <TH>Last run</TH>
                    <TH>What it did</TH>
                  </TR>
                </THead>
                <TBody>
                  {data.jobs.map((job) => (
                    <TR key={job.name}>
                      <TD>
                        {job.label}
                        <div className="text-xs text-muted-foreground">{job.schedule}</div>
                      </TD>
                      <TD>
                        <Badge tone={JOB_STATES[job.state].tone}>{JOB_STATES[job.state].label}</Badge>
                      </TD>
                      <TD className="text-sm whitespace-nowrap">{job.last_run ? time.format(new Date(job.last_run)) : '—'}</TD>
                      <TD className={cn('text-sm', job.state === 'failed' && 'text-destructive')}>{describe(job.summary) || '—'}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
          <Launch data={data} />
        </div>
      )}
    </div>
  )
}

function Server({ data }: { data: SystemStatus }) {
  const full = data.disk.used_percent >= 85
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Server</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Version</dt>
            <dd className="font-mono">{data.version}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Running as</dt>
            <dd>{data.environment}</dd>
          </div>
          <div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Disk</dt>
              <dd className={cn(full && 'font-medium text-destructive')}>
                {data.disk.used_percent}% used, {data.disk.free_gb} GB free
              </dd>
            </div>
            <div aria-hidden="true" className="mt-1.5 h-2 overflow-hidden rounded-full" style={{ background: 'var(--chart-empty)' }}>
              <div className="h-full rounded-full" style={{ width: `${data.disk.used_percent}%`, background: full ? 'var(--destructive)' : 'var(--chart-income)' }} />
            </div>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}

function Launch({ data }: { data: SystemStatus }) {
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-lg">Before launch</CardTitle>
        <CardDescription>
          What is left before students rely on the site.{' '}
          <a className="underline" href={GUIDE} target="_blank" rel="noopener noreferrer">
            How to do each one
          </a>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {data.launch.map((item) => {
            const Icon = item.done === null ? Clock : item.done ? CircleCheck : CircleDashed
            return (
              <li key={item.key} className="flex items-center gap-2">
                <Icon aria-hidden="true" className={cn('size-4 shrink-0', item.done ? 'text-success' : 'text-muted-foreground')} />
                <span>{item.label}</span>
                <span className="text-xs text-muted-foreground">{item.done === null ? '(check yourself)' : item.done ? '(done)' : '(not yet)'}</span>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
