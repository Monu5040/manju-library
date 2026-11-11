import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { ProfileSwitcher } from '@/components/portal/ProfileSwitcher'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page'
import { Textarea } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { api, errorMessage } from '@/lib/api'
import { fieldErrors } from '@/lib/errors'
import { formatDate } from '@/lib/format'
import { useSelectedProfile } from '@/lib/portal'
import type { PortalStudent } from '@/lib/types'

export default function PortalProfilePage() {
  const { home, profiles, selected, select } = useSelectedProfile()
  if (home.isPending) return <Spinner label="Loading your details" />
  if (home.error) return <Alert variant="destructive">{errorMessage(home.error)}</Alert>
  if (!selected) return null
  return (
    <div className="space-y-6">
      <ProfileSwitcher profiles={profiles} selectedId={selected.id} onSelect={select} />
      <PageHeader title="My details" description="To change your name, mobile number or Aadhaar, please speak to the front desk." />
      <Card>
        <CardContent className="pt-6">
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
            <Detail label="Name" value={selected.full_name} />
            <Detail label="Roll no." value={String(selected.roll_no)} />
            <Detail label="Father's name" value={selected.father_name || '—'} />
            <Detail label="Mobile (login)" value={selected.mobile} />
            <Detail label="Aadhaar" value={selected.aadhaar_masked || '—'} />
            <Detail label="Admitted" value={formatDate(selected.admission_date)} />
          </dl>
        </CardContent>
      </Card>
      {/* key: a fresh form when switching between siblings */}
      <ContactForm key={selected.id} student={selected} />
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  )
}

function ContactForm({ student }: { student: PortalStudent }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState({ address: student.address, alt_mobile: student.alt_mobile })
  const [saved, setSaved] = useState(false)
  const save = useMutation({
    mutationFn: () => api(`/portal/students/${student.id}/`, { method: 'PATCH', body: draft }),
    onSuccess: () => {
      setSaved(true)
      return queryClient.invalidateQueries({ queryKey: ['portal'] })
    },
  })
  const errors = fieldErrors(save.error)
  return (
    <Card>
      <CardHeader>
        <CardTitle>How to reach you</CardTitle>
        <CardDescription>You can change these yourself.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            setSaved(false)
            save.mutate()
          }}
        >
          {saved && <Alert variant="success">Saved.</Alert>}
          {save.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
          <Field label="Other mobile number" id="alt-mobile" error={errors.alt_mobile} hint="For example a parent's number.">
            <Input id="alt-mobile" type="tel" inputMode="numeric" value={draft.alt_mobile} onChange={(e) => setDraft({ ...draft, alt_mobile: e.target.value })} />
          </Field>
          <Field label="Address" id="address" error={errors.address}>
            <Textarea id="address" rows={3} value={draft.address} onChange={(e) => setDraft({ ...draft, address: e.target.value })} />
          </Field>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
