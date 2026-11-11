import { CircleCheck, CircleMinus } from 'lucide-react'
import { useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/select'
import { api, errorMessage } from '@/lib/api'
import { useAutomationSettings } from '@/lib/automation'
import { fieldErrors } from '@/lib/errors'
import { useAdminMutation } from '@/lib/queries'
import type { AutomationSettings, ReminderKind } from '@/lib/types'

type Draft = Omit<AutomationSettings, 'sms' | 'placeholders'>

const TEXTS: { field: keyof Draft; kind: ReminderKind; label: string }[] = [
  { field: 'text_expiring_soon', kind: 'EXPIRING_SOON', label: 'Ending soon' },
  { field: 'text_expires_today', kind: 'EXPIRES_TODAY', label: 'Ends today' },
  { field: 'text_dues', kind: 'DUES', label: 'Fees due' },
  { field: 'text_waitlist', kind: 'WAITLIST', label: 'Seat free for someone waiting' },
]

/** Settings: when reminders are made, how they are sent, and the nightly tidy-up. */
export function AutomationCard({ canEdit }: { canEdit: boolean }) {
  const settings = useAutomationSettings()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Reminders and automation</CardTitle>
        <CardDescription>Reminders appear on the Reminders page every hour from 8 AM to 8 PM.</CardDescription>
      </CardHeader>
      <CardContent>
        {settings.error && <Alert variant="destructive">{errorMessage(settings.error)}</Alert>}
        {settings.data && <AutomationForm settings={settings.data} canEdit={canEdit} />}
      </CardContent>
    </Card>
  )
}

function AutomationForm({ settings, canEdit }: { settings: AutomationSettings; canEdit: boolean }) {
  const { sms, placeholders, ...initial } = settings
  const [draft, setDraft] = useState<Draft>(initial)
  const [saved, setSaved] = useState(false)
  const save = useAdminMutation(() => api('/admin/automation/', { method: 'PATCH', body: draft }))
  const errors = fieldErrors(save.error)
  const set = (patch: Partial<Draft>) => {
    setSaved(false)
    setDraft({ ...draft, ...patch })
  }
  const number = (field: keyof Draft, label: string, hint: string) => (
    <Field label={label} id={`auto-${field}`} error={errors[field]} hint={hint}>
      <Input
        id={`auto-${field}`}
        type="number"
        min="0"
        disabled={!canEdit}
        value={String(draft[field])}
        onChange={(e) => set({ [field]: Number(e.target.value) } as Partial<Draft>)}
      />
    </Field>
  )
  const toggle = (field: keyof Draft, label: string) => (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" className="size-4" disabled={!canEdit} checked={Boolean(draft[field])} onChange={(e) => set({ [field]: e.target.checked } as Partial<Draft>)} />
      {label}
    </label>
  )

  return (
    <form
      className="space-y-6"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate(undefined, { onSuccess: () => setSaved(true) })
      }}
    >
      {saved && <Alert variant="success">Saved.</Alert>}
      {save.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
      <div className="space-y-3">
        {toggle('reminders_enabled', 'Make reminders')}
        {toggle('remind_on_expiry_day', 'Remind on the last day of a membership')}
        {toggle('waitlist_alerts', 'Tell the first students waiting when a seat is free')}
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {number('days_before_expiry', 'Days before a membership ends', 'Remind this many days ahead; 0 turns it off.')}
        {number('dues_after_days', 'Days before chasing unpaid fees', 'Counted from the start of the membership; 0 = off.')}
        {number('dues_repeat_days', 'Repeat the fees reminder every', 'Days, while fees are still due; 0 = only once.')}
      </div>

      <fieldset className="space-y-2 rounded-lg border p-4">
        <legend className="px-1 text-sm font-medium">Automatic SMS</legend>
        {toggle('send_sms', 'Send by SMS without anyone pressing a button')}
        <p className="text-xs text-muted-foreground">
          Indian SMS needs a DLT-approved template for each kind of reminder, set up on the server. Without one, that reminder waits on the Reminders page for WhatsApp.
        </p>
        <ul className="grid gap-1 text-sm sm:grid-cols-2">
          {TEXTS.map((t) => (
            <li key={t.kind} className="flex items-center gap-2">
              {sms[t.kind] ? (
                <CircleCheck aria-hidden="true" className="size-4 text-success" />
              ) : (
                <CircleMinus aria-hidden="true" className="size-4 text-muted-foreground" />
              )}
              {t.label}: {sms[t.kind] ? 'template ready' : 'no template yet'}
            </li>
          ))}
        </ul>
      </fieldset>

      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium">Messages for WhatsApp</h3>
          <p className="text-xs text-muted-foreground">
            Write them in any language. These words are filled in for each student:{' '}
            {Object.entries(placeholders)
              .map(([key, label]) => `{${key}} ${label.toLowerCase()}`)
              .join(', ')}
            .
          </p>
        </div>
        {TEXTS.map((t) => (
          <Field key={t.field} label={t.label} id={`auto-${t.field}`} error={errors[t.field]}>
            <Textarea id={`auto-${t.field}`} rows={3} disabled={!canEdit} value={String(draft[t.field])} onChange={(e) => set({ [t.field]: e.target.value } as Partial<Draft>)} />
          </Field>
        ))}
      </div>

      <div className="max-w-sm">
        {number('mark_left_after_days', 'Mark students as left after', 'Days without a membership, checked every night. 0 = never. Students waiting for a seat are kept.')}
      </div>
      {canEdit && (
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save'}
        </Button>
      )}
    </form>
  )
}
