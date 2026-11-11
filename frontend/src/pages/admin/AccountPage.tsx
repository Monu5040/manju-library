import { useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page'
import { api, errorMessage } from '@/lib/api'
import { ROLE_LABELS, useMe } from '@/lib/auth'
import { fieldErrors } from '@/lib/errors'
import { useAdminMutation } from '@/lib/queries'

export default function AccountPage() {
  const { data: me } = useMe()
  const [draft, setDraft] = useState({ current_password: '', new_password: '', confirm: '' })
  const [done, setDone] = useState(false)
  const save = useAdminMutation(() =>
    api('/auth/password/', {
      method: 'POST',
      body: { current_password: draft.current_password, new_password: draft.new_password },
    }),
  )
  const errors = fieldErrors(save.error)
  const mismatch = draft.confirm !== '' && draft.confirm !== draft.new_password

  return (
    <div className="max-w-xl space-y-6">
      <PageHeader title="My account" description={me ? `${me.full_name} · ${ROLE_LABELS[me.role]} · ${me.email ?? me.mobile}` : undefined} />
      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              setDone(false)
              save.mutate(undefined, {
                onSuccess: () => {
                  setDone(true)
                  setDraft({ current_password: '', new_password: '', confirm: '' })
                },
              })
            }}
          >
            {done && <Alert variant="success">Password changed.</Alert>}
            {save.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
            <Field label="Current password" id="pw-current" error={errors.current_password}>
              <Input id="pw-current" type="password" autoComplete="current-password" value={draft.current_password} onChange={(e) => setDraft({ ...draft, current_password: e.target.value })} />
            </Field>
            <Field label="New password" id="pw-new" error={errors.new_password} hint="At least 12 characters; not a common password.">
              <Input id="pw-new" type="password" autoComplete="new-password" value={draft.new_password} onChange={(e) => setDraft({ ...draft, new_password: e.target.value })} />
            </Field>
            <Field label="New password again" id="pw-confirm" error={mismatch ? 'The two new passwords are different.' : undefined}>
              <Input id="pw-confirm" type="password" autoComplete="new-password" value={draft.confirm} onChange={(e) => setDraft({ ...draft, confirm: e.target.value })} />
            </Field>
            <Button type="submit" disabled={save.isPending || mismatch || !draft.new_password}>
              Change password
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
