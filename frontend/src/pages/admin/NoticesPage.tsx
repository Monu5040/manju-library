import { useQuery } from '@tanstack/react-query'
import { Pin } from 'lucide-react'
import { useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Textarea } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { api, errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { fieldErrors } from '@/lib/errors'
import { formatDate, todayIso } from '@/lib/format'
import { useAdminMutation } from '@/lib/queries'
import type { Notice } from '@/lib/types'

function status(n: Notice, today: string): { label: string; tone: 'success' | 'info' | 'neutral' } {
  if (n.starts_on > today) return { label: `From ${formatDate(n.starts_on)}`, tone: 'info' }
  if (n.ends_on && n.ends_on < today) return { label: 'Ended', tone: 'neutral' }
  return { label: 'Showing now', tone: 'success' }
}

export default function NoticesPage() {
  const { data: me } = useMe()
  const notices = useQuery({ queryKey: ['admin', 'notices'], queryFn: () => api<Notice[]>('/admin/notices/') })
  const [editing, setEditing] = useState<Partial<Notice> | null>(null)
  const remove = useAdminMutation((id: number) => api(`/admin/notices/${id}/`, { method: 'DELETE' }))
  const [today] = useState(todayIso)

  return (
    <div>
      <PageHeader
        title="Notices"
        description="Messages on every student's portal home page: holidays, rules, fee changes."
        actions={<Button onClick={() => setEditing({ starts_on: today, is_pinned: false })}>New notice</Button>}
      />
      {remove.error && <Alert variant="destructive" className="mb-4">{errorMessage(remove.error)}</Alert>}
      {notices.isPending && <Spinner label="Loading notices" />}
      {notices.data?.length === 0 && <EmptyState title="No notices yet." />}
      <div className="space-y-3">
        {notices.data?.map((n) => {
          const s = status(n, today)
          return (
            <Card key={n.id}>
              <CardHeader className="flex-row items-start justify-between gap-4">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    {n.is_pinned && <Pin aria-label="Pinned" className="size-4 text-primary" />}
                    {n.title}
                  </CardTitle>
                  <CardDescription>
                    {formatDate(n.starts_on)}
                    {n.ends_on ? ` – ${formatDate(n.ends_on)}` : ''} · by {n.created_by_name ?? '—'}
                  </CardDescription>
                </div>
                <Badge tone={s.tone}>{s.label}</Badge>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm whitespace-pre-line">{n.body}</p>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setEditing(n)}>
                    Edit
                  </Button>
                  <CopyButton text={`*${n.title}*\n${n.body}`} />
                  {me?.role === 'SUPER_ADMIN' && (
                    <Button size="sm" variant="ghost" className="text-destructive" onClick={() => remove.mutate(n.id)}>
                      Delete
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
      {editing && <NoticeDialog notice={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

function NoticeDialog({ notice, onClose }: { notice: Partial<Notice>; onClose: () => void }) {
  const [draft, setDraft] = useState({
    title: notice.title ?? '',
    body: notice.body ?? '',
    starts_on: notice.starts_on ?? '',
    ends_on: notice.ends_on ?? '',
    is_pinned: notice.is_pinned ?? false,
  })
  const save = useAdminMutation(() =>
    api(notice.id ? `/admin/notices/${notice.id}/` : '/admin/notices/', {
      method: notice.id ? 'PATCH' : 'POST',
      body: { ...draft, ends_on: draft.ends_on || null },
    }),
  )
  const errors = fieldErrors(save.error)
  return (
    <Dialog open onClose={onClose} wide title={notice.id ? 'Edit notice' : 'New notice'}>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive" className="sm:col-span-2">{errorMessage(save.error)}</Alert>}
        <Field label="Title" id="n-title" error={errors.title} className="sm:col-span-2">
          <Input id="n-title" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
        </Field>
        <Field label="Message" id="n-body" error={errors.body} className="sm:col-span-2">
          <Textarea id="n-body" rows={5} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
        </Field>
        <Field label="Show from" id="n-start" error={errors.starts_on}>
          <Input id="n-start" type="date" value={draft.starts_on} onChange={(e) => setDraft({ ...draft, starts_on: e.target.value })} />
        </Field>
        <Field label="Show until (optional)" id="n-end" error={errors.ends_on}>
          <Input id="n-end" type="date" value={draft.ends_on} onChange={(e) => setDraft({ ...draft, ends_on: e.target.value })} />
        </Field>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" className="size-4" checked={draft.is_pinned} onChange={(e) => setDraft({ ...draft, is_pinned: e.target.checked })} />
          Pin to the top
        </label>
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

/** Copies a notice with WhatsApp formatting (*bold* title), to paste into the library's group. */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(true)
          setTimeout(() => setCopied(false), 2000)
        } catch {
          setCopied(false)
        }
      }}
    >
      {copied ? 'Copied' : 'Copy for WhatsApp'}
    </Button>
  )
}
