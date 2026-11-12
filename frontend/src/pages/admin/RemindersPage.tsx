import { MessageCircle, Phone, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Spinner } from '@/components/ui/spinner'
import { api, errorMessage } from '@/lib/api'
import { useAutomationSettings, useReminders } from '@/lib/automation'
import { formatDate, formatMoney, todayIso } from '@/lib/format'
import { useAdminMutation } from '@/lib/queries'
import type { Reminder, ReminderKind } from '@/lib/types'
import { cn } from '@/lib/utils'

const GROUPS: { kind: ReminderKind; title: string }[] = [
  { kind: 'EXPIRES_TODAY', title: 'Ending today' },
  { kind: 'EXPIRING_SOON', title: 'Ending soon' },
  { kind: 'DUES', title: 'Fees due' },
  { kind: 'WAITLIST', title: 'A seat is free for someone waiting' },
]

type Act = { id: number; action: 'sent' | 'skip' | 'reopen'; body?: unknown }

function detailLine(r: Reminder): string {
  const d = r.details
  switch (r.kind) {
    case 'DUES':
      return `${formatMoney(Number(d.amount ?? 0))} due · seat ${d.seat || '—'} · ${d.shift ?? ''}`
    case 'WAITLIST':
      return `Seat ${d.seat} is free in ${d.shift} · W${d.position}`
    default:
      return `Seat ${d.seat || '—'} · ${d.shift ?? ''} · ends ${formatDate(d.end_date)}`
  }
}

export default function RemindersPage() {
  const [tab, setTab] = useState<'open' | 'done'>('open')
  const [today] = useState(todayIso)
  const refresh = useAdminMutation(() => api<{ created: number; closed: number }>('/admin/reminders/refresh/', { method: 'POST' }))
  const { mutate: runRefresh } = refresh
  // Bring the list up to date on opening: renewed or paid reminders close, new ones appear.
  useEffect(() => runRefresh(), [runRefresh])
  const open = useReminders({ open: 1, page_size: 200 })
  const done = useReminders({ done: 1, ordering: '-for_date,-created_at', page_size: 50 })
  const conf = useAutomationSettings()
  const act = useAdminMutation(({ id, action, body }: Act) => api(`/admin/reminders/${id}/${action}/`, { method: 'POST', body: body ?? {} }))
  const smsKinds = conf.data?.send_sms ? GROUPS.filter((g) => conf.data?.sms[g.kind]).map((g) => g.title.toLowerCase()) : []
  const openCount = open.data?.count ?? 0

  return (
    <div>
      <PageHeader
        title="Reminders"
        description="Messages to send today. New ones are added every hour from 8 AM to 8 PM."
        actions={
          <Button variant="outline" disabled={refresh.isPending} onClick={() => runRefresh()}>
            <RefreshCw aria-hidden="true" className={refresh.isPending ? 'animate-spin' : undefined} /> Refresh
          </Button>
        }
      />
      {conf.data && !conf.data.reminders_enabled && (
        <Alert className="mb-4">Reminders are turned off in Settings, so no new ones are being made.</Alert>
      )}
      <p className="mb-4 text-sm text-muted-foreground">
        {smsKinds.length > 0
          ? `SMS goes out automatically for: ${smsKinds.join(', ')}. The rest wait here.`
          : 'Tap WhatsApp to open the chat with the message written for you, then press send in WhatsApp.'}
      </p>
      {(refresh.error || act.error) && <Alert variant="destructive" className="mb-4">{errorMessage(refresh.error ?? act.error)}</Alert>}

      <div role="tablist" aria-label="Reminders" className="mb-5 flex w-fit gap-1 rounded-xl border bg-card p-1 shadow-card">
        {(
          [
            ['open', `To send (${openCount})`],
            ['done', 'Done'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            type="button"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={cn(
              'rounded-lg px-3.5 py-1.5 text-sm font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
              tab === value ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'open' && (
        <>
          {open.isPending && <Spinner label="Loading reminders" />}
          {open.data?.results.length === 0 && <EmptyState title="Nothing to send right now.">Everyone is up to date.</EmptyState>}
          <div className="space-y-6">
            {GROUPS.map((group) => {
              const rows = open.data?.results.filter((r) => r.kind === group.kind) ?? []
              if (!rows.length) return null
              return (
                <Card key={group.kind}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">
                      {group.title} <span className="text-muted-foreground">({rows.length})</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="divide-y">
                      {rows.map((r) => (
                        <OpenRow key={r.id} reminder={r} today={today} busy={act.isPending} onAct={(a) => act.mutate(a)} />
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </>
      )}

      {tab === 'done' && (
        <>
          {done.data?.results.length === 0 && <EmptyState title="Nothing done yet." />}
          <ul className="divide-y rounded-xl border bg-card">
            {done.data?.results.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                <div className="min-w-0">
                  <Link to={`/admin/students/${r.student}`} className="font-medium hover:underline">
                    {r.student_name}
                  </Link>{' '}
                  <span className="text-muted-foreground">
                    · {r.kind_label} · {formatDate(r.for_date)}
                  </span>
                  <div className="text-xs text-muted-foreground">
                    {r.status === 'SENT'
                      ? `Sent ${r.channel === 'SMS' ? 'by SMS' : `(${r.channel_label})`}${r.sent_by_name ? ` by ${r.sent_by_name}` : ''}`
                      : `Skipped: ${r.note}`}
                  </div>
                </div>
                {r.channel !== 'SMS' && (
                  <Button size="sm" variant="ghost" disabled={act.isPending} onClick={() => act.mutate({ id: r.id, action: 'reopen' })}>
                    Put back
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function OpenRow({ reminder: r, today, busy, onAct }: { reminder: Reminder; today: string; busy: boolean; onAct: (a: Act) => void }) {
  return (
    <li className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Link to={`/admin/students/${r.student}`} className="font-medium hover:underline">
            {r.student_name}
          </Link>
          <span className="text-xs text-muted-foreground">
            roll {r.roll_no} ·{' '}
            <a href={`tel:+91${r.mobile}`} className="hover:underline">
              {r.mobile}
            </a>
          </span>
          {r.for_date < today && <Badge tone="warning">since {formatDate(r.for_date)}</Badge>}
          {r.status === 'FAILED' && <Badge tone="danger">SMS failed</Badge>}
        </div>
        <p className="text-sm">{detailLine(r)}</p>
        <p className="line-clamp-2 text-sm text-muted-foreground">{r.message}</p>
        {r.status === 'FAILED' && r.note && <p className="text-xs text-destructive">{r.note}</p>}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Button asChild size="sm">
          <a href={r.whatsapp_url} target="_blank" rel="noopener noreferrer" onClick={() => onAct({ id: r.id, action: 'sent', body: { channel: 'WHATSAPP' } })}>
            <MessageCircle aria-hidden="true" /> WhatsApp
          </a>
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => onAct({ id: r.id, action: 'sent', body: { channel: 'CALL' } })}>
          <Phone aria-hidden="true" /> Called
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAct({ id: r.id, action: 'skip' })}>
          Skip
        </Button>
      </div>
    </li>
  )
}
