import { useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { ROLE_LABELS, useMe } from '@/lib/auth'
import { fieldErrors } from '@/lib/errors'
import { formatDate } from '@/lib/format'
import { useAdminMutation, useStaffAccounts } from '@/lib/queries'
import type { StaffAccount } from '@/lib/types'

export default function StaffPage() {
  const { data: me } = useMe()
  const staff = useStaffAccounts()
  const [adding, setAdding] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const patch = useAdminMutation(({ id, body }: { id: number; body: Partial<StaffAccount> }) =>
    api(`/admin/staff/${id}/`, { method: 'PATCH', body }),
  )
  const reset = useAdminMutation((id: number) => api<{ detail: string }>(`/admin/staff/${id}/reset-authenticator/`, { method: 'POST' }))
  const error = patch.error ?? reset.error

  return (
    <div>
      <PageHeader
        title="Staff accounts"
        description="Staff can admit students, renew and take payments. Only Super Admins delete, void, change settings or see Aadhaar numbers."
        actions={<Button onClick={() => setAdding(true)}>Add staff</Button>}
      />
      {error && <Alert variant="destructive" className="mb-4">{errorMessage(error)}</Alert>}
      {notice && <Alert variant="success" className="mb-4">{notice}</Alert>}
      {staff.isPending && <Spinner label="Loading staff" />}
      {staff.data && (
        <Table>
          <THead>
            <TR>
              <TH>Name</TH>
              <TH>Role</TH>
              <TH>Can export</TH>
              <TH>Last sign-in</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {staff.data.map((u) => {
              const self = u.id === me?.id
              return (
                <TR key={u.id} className={u.is_active ? undefined : 'text-muted-foreground'}>
                  <TD>
                    <div className="font-medium">
                      {u.full_name} {self && <Badge tone="info">you</Badge>} {!u.is_active && <Badge>switched off</Badge>}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {u.email ?? u.mobile} · {u.has_authenticator ? 'app connected' : 'app not connected yet'}
                    </div>
                  </TD>
                  <TD>{ROLE_LABELS[u.role]}</TD>
                  <TD>
                    {u.role === 'SUPER_ADMIN' ? (
                      'Always'
                    ) : (
                      <input
                        type="checkbox"
                        className="size-4"
                        aria-label={`${u.full_name} can export`}
                        checked={u.can_export}
                        onChange={(e) => patch.mutate({ id: u.id, body: { can_export: e.target.checked } })}
                      />
                    )}
                  </TD>
                  <TD>{u.last_login ? formatDate(u.last_login) : 'Never'}</TD>
                  <TD className="text-right whitespace-nowrap">
                    {!self && (
                      <>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => reset.mutate(u.id, { onSuccess: (r) => setNotice(r.detail) })}
                          disabled={!u.has_authenticator}
                        >
                          Reset app
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => patch.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                          {u.is_active ? 'Switch off' : 'Switch on'}
                        </Button>
                      </>
                    )}
                  </TD>
                </TR>
              )
            })}
          </TBody>
        </Table>
      )}
      {adding && <AddStaffDialog onClose={() => setAdding(false)} />}
    </div>
  )
}

function AddStaffDialog({ onClose }: { onClose: () => void }) {
  const [draft, setDraft] = useState({ full_name: '', mobile: '', email: '', role: 'STAFF', password: '', can_export: false })
  const save = useAdminMutation(() => api('/admin/staff/', { method: 'POST', body: draft }))
  const errors = fieldErrors(save.error)
  return (
    <Dialog open onClose={onClose} title="Add staff" description="They sign in at /staff/login and connect an authenticator app the first time.">
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
        <Field label="Full name" id="st-name" error={errors.full_name}>
          <Input id="st-name" value={draft.full_name} onChange={(e) => setDraft({ ...draft, full_name: e.target.value })} />
        </Field>
        <Field label="Mobile" id="st-mobile" error={errors.mobile}>
          <Input id="st-mobile" type="tel" value={draft.mobile} onChange={(e) => setDraft({ ...draft, mobile: e.target.value })} />
        </Field>
        <Field label="Email (optional)" id="st-email" error={errors.email}>
          <Input id="st-email" type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
        </Field>
        <Field label="Role" id="st-role" error={errors.role}>
          <Select id="st-role" value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })}>
            <option value="STAFF">Staff</option>
            <option value="SUPER_ADMIN">Super Admin</option>
          </Select>
        </Field>
        <Field label="First password" id="st-password" error={errors.password} hint="12+ characters. Ask them to change it after signing in.">
          <Input id="st-password" type="password" autoComplete="new-password" value={draft.password} onChange={(e) => setDraft({ ...draft, password: e.target.value })} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={draft.can_export} onChange={(e) => setDraft({ ...draft, can_export: e.target.checked })} />
          Allowed to export data
        </label>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            Add
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
