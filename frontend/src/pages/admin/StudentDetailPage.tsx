import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { DueBadge, StateBadge } from '@/components/admin/badges'
import { NewMembershipDialog, RecordPaymentDialog, RenewDialog } from '@/components/admin/dialogs'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Select, Textarea } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { fieldErrors } from '@/lib/errors'
import { formatDate, formatMoney } from '@/lib/format'
import { useAdminMutation, useMemberships, usePayments, useStudent } from '@/lib/queries'
import type { Membership, Payment, Student } from '@/lib/types'

const GENDER: Record<string, string> = { F: 'Female', M: 'Male', O: 'Other', '': '—' }

export default function StudentDetailPage() {
  const id = Number(useParams().id)
  const location = useLocation()
  const notice = (location.state as { notice?: string; receipt?: number } | null) ?? null
  const { data: me } = useMe()
  const isOwner = me?.role === 'SUPER_ADMIN'

  const student = useStudent(id)
  const memberships = useMemberships({ student: id, page_size: 100, ordering: '-start_date' })
  const payments = usePayments({ student: id, page_size: 100 })

  const [dialog, setDialog] = useState<
    | { kind: 'edit' }
    | { kind: 'new' }
    | { kind: 'pay'; membership: Membership | null }
    | { kind: 'renew'; membership: Membership }
    | { kind: 'cancel'; membership: Membership }
    | { kind: 'void'; payment: Payment }
    | null
  >(null)
  const close = () => setDialog(null)

  if (student.isPending) return <Spinner label="Loading student" />
  if (student.error) return <Alert variant="destructive">{errorMessage(student.error)}</Alert>
  const s = student.data
  const live = memberships.data?.results.filter((m) => m.state !== 'CANCELLED') ?? []
  const latest = live[0]

  return (
    <div className="space-y-6">
      <PageHeader
        title={s.full_name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            Roll {s.roll_no} · {s.mobile}
            {s.status === 'LEFT' && <Badge>Left the library</Badge>}
            <DueBadge amount={s.total_due} />
          </span>
        }
        actions={
          <>
            {latest && latest.state !== 'EXPIRED' && <Button onClick={() => setDialog({ kind: 'renew', membership: latest })}>Renew</Button>}
            {(!latest || latest.state === 'EXPIRED') && <Button onClick={() => setDialog({ kind: 'new' })}>Give a seat</Button>}
            <Button variant="outline" onClick={() => setDialog({ kind: 'pay', membership: live.find((m) => m.due_total > 0) ?? latest ?? null })}>
              Record payment
            </Button>
            <Button variant="outline" onClick={() => setDialog({ kind: 'edit' })}>
              Edit details
            </Button>
          </>
        }
      />

      {notice?.notice && (
        <Alert variant="success">
          {notice.notice}{' '}
          {notice.receipt && (
            <Link className="font-medium underline" to={`/admin/payments/${notice.receipt}/receipt`}>
              Print the receipt
            </Link>
          )}
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <Detail label="Father's name" value={s.father_name || '—'} />
            <Detail label="Gender" value={GENDER[s.gender]} />
            <Detail label="Other mobile" value={s.alt_mobile || '—'} />
            <Detail label="Aadhaar" value={<AadhaarValue student={s} canReveal={isOwner} />} />
            <Detail label="Admitted" value={formatDate(s.admission_date)} />
            <Detail label="Address" value={s.address || '—'} />
            {s.notes && <Detail label="Notes" value={s.notes} />}
          </dl>
        </CardContent>
      </Card>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Memberships</h2>
        {memberships.data?.results.length === 0 && <EmptyState title="No memberships yet." />}
        {memberships.data && memberships.data.results.length > 0 && (
          <Table>
            <THead>
              <TR>
                <TH>Dates</TH>
                <TH>Seat · time</TH>
                <TH>Fee</TH>
                <TH>Paid</TH>
                <TH>Status</TH>
                <TH>
                  <span className="sr-only">Actions</span>
                </TH>
              </TR>
            </THead>
            <TBody>
              {memberships.data.results.map((m) => (
                <TR key={m.id}>
                  <TD className="whitespace-nowrap">
                    {formatDate(m.start_date)} – {formatDate(m.end_date)}
                    {m.plan_name && <div className="text-xs text-muted-foreground">{m.plan_name}</div>}
                  </TD>
                  <TD>
                    {m.seat_number ? `Seat ${m.seat_number}` : 'No seat'}
                    <div className="text-xs text-muted-foreground">{m.shift_name ? `${m.shift_name} · ` : ''}{m.time_label}</div>
                  </TD>
                  <TD className="tabular-nums">
                    {formatMoney(m.net_fee)}
                    {m.discount > 0 && <div className="text-xs text-muted-foreground">after {formatMoney(m.discount)} off</div>}
                  </TD>
                  <TD className="tabular-nums">
                    {formatMoney(m.paid_total)}
                    {m.state !== 'CANCELLED' && m.due_total > 0 && <div className="text-xs text-destructive">due {formatMoney(m.due_total)}</div>}
                  </TD>
                  <TD>
                    <StateBadge state={m.state} daysLeft={m.days_left} />
                  </TD>
                  <TD className="text-right whitespace-nowrap">
                    {m.state !== 'CANCELLED' && m.due_total > 0 && (
                      <Button size="sm" variant="ghost" onClick={() => setDialog({ kind: 'pay', membership: m })}>
                        Pay
                      </Button>
                    )}
                    {isOwner && m.state !== 'CANCELLED' && (
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDialog({ kind: 'cancel', membership: m })}>
                        Cancel
                      </Button>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Payments</h2>
        {payments.data?.results.length === 0 && <EmptyState title="No payments yet." />}
        {payments.data && payments.data.results.length > 0 && (
          <Table>
            <THead>
              <TR>
                <TH>Receipt</TH>
                <TH>Date</TH>
                <TH>Amount</TH>
                <TH>Paid by</TH>
                <TH>
                  <span className="sr-only">Actions</span>
                </TH>
              </TR>
            </THead>
            <TBody>
              {payments.data.results.map((p) => (
                <TR key={p.id} className={p.is_void ? 'text-muted-foreground line-through' : undefined}>
                  <TD className="tabular-nums">#{p.receipt_no}</TD>
                  <TD>{formatDate(p.paid_on)}</TD>
                  <TD className="tabular-nums">{formatMoney(p.amount)}</TD>
                  <TD>
                    {p.mode_label}
                    {p.reference && <div className="text-xs">{p.reference}</div>}
                    {p.is_void && <div className="text-xs no-underline">Void: {p.void_reason}</div>}
                  </TD>
                  <TD className="text-right whitespace-nowrap">
                    <Button asChild size="sm" variant="ghost">
                      <Link to={`/admin/payments/${p.id}/receipt`}>Receipt</Link>
                    </Button>
                    {isOwner && !p.is_void && (
                      <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDialog({ kind: 'void', payment: p })}>
                        Void
                      </Button>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </section>

      {dialog?.kind === 'edit' && <EditStudentDialog student={s} onClose={close} />}
      {dialog?.kind === 'new' && <NewMembershipDialog open studentId={s.id} studentName={s.full_name} onClose={close} />}
      {dialog?.kind === 'pay' && <RecordPaymentDialog open studentId={s.id} membership={dialog.membership} onClose={close} />}
      {dialog?.kind === 'renew' && <RenewDialog open membership={dialog.membership} onClose={close} />}
      {dialog?.kind === 'cancel' && (
        <ReasonDialog
          title="Cancel this membership?"
          description="The seat becomes free. Payments stay on record."
          action="Cancel membership"
          path={`/admin/memberships/${dialog.membership.id}/cancel/`}
          onClose={close}
        />
      )}
      {dialog?.kind === 'void' && (
        <ReasonDialog
          title={`Void receipt #${dialog.payment.receipt_no}?`}
          description={`${formatMoney(dialog.payment.amount)} stops counting as paid. The receipt number stays used.`}
          action="Void payment"
          path={`/admin/payments/${dialog.payment.id}/void/`}
          onClose={close}
        />
      )}
    </div>
  )
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  )
}

function AadhaarValue({ student, canReveal }: { student: Student; canReveal: boolean }) {
  const [full, setFull] = useState<string | null>(null)
  const reveal = useAdminMutation(() => api<{ aadhaar: string }>(`/admin/students/${student.id}/reveal-aadhaar/`, { method: 'POST' }))
  if (!student.aadhaar_masked) return <>—</>
  return (
    <span className="inline-flex items-center gap-2">
      <span className="tabular-nums">{full ?? student.aadhaar_masked}</span>
      {canReveal && !full && (
        <Button
          size="sm"
          variant="link"
          className="h-auto px-0"
          onClick={() => reveal.mutate(undefined, { onSuccess: (data) => setFull(data.aadhaar) })}
        >
          Show (logged)
        </Button>
      )}
    </span>
  )
}

function ReasonDialog({
  title,
  description,
  action,
  path,
  onClose,
}: {
  title: string
  description: string
  action: string
  path: string
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const save = useAdminMutation(() => api(path, { method: 'POST', body: { reason } }))
  return (
    <Dialog open onClose={onClose} title={title} description={description}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
        <Field label="Reason" id="reason">
          <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} required />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Keep it
          </Button>
          <Button type="submit" variant="destructive" disabled={save.isPending || !reason.trim()}>
            {action}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

function EditStudentDialog({ student, onClose }: { student: Student; onClose: () => void }) {
  const [draft, setDraft] = useState({
    full_name: student.full_name,
    father_name: student.father_name,
    gender: student.gender as string,
    mobile: student.mobile,
    alt_mobile: student.alt_mobile,
    aadhaar: '',
    address: student.address,
    status: student.status as string,
    notes: student.notes,
  })
  const save = useAdminMutation(() => {
    const body: Record<string, string> = { ...draft }
    if (!draft.aadhaar) delete body.aadhaar
    return api(`/admin/students/${student.id}/`, { method: 'PATCH', body })
  })
  const errors = fieldErrors(save.error)
  const set = (patch: Partial<typeof draft>) => setDraft((d) => ({ ...d, ...patch }))
  return (
    <Dialog open onClose={onClose} wide title="Edit details">
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive" className="sm:col-span-2">{errorMessage(save.error)}</Alert>}
        <Field label="Full name" id="e-name" error={errors.full_name} className="sm:col-span-2">
          <Input id="e-name" value={draft.full_name} onChange={(e) => set({ full_name: e.target.value })} />
        </Field>
        <Field label="Father's name" id="e-father" error={errors.father_name}>
          <Input id="e-father" value={draft.father_name} onChange={(e) => set({ father_name: e.target.value })} />
        </Field>
        <Field label="Gender" id="e-gender" error={errors.gender}>
          <Select id="e-gender" value={draft.gender} onChange={(e) => set({ gender: e.target.value })}>
            <option value="">—</option>
            <option value="F">Female</option>
            <option value="M">Male</option>
            <option value="O">Other</option>
          </Select>
        </Field>
        <Field label="Mobile" id="e-mobile" error={errors.mobile}>
          <Input id="e-mobile" value={draft.mobile} onChange={(e) => set({ mobile: e.target.value })} />
        </Field>
        <Field label="Other mobile" id="e-alt" error={errors.alt_mobile}>
          <Input id="e-alt" value={draft.alt_mobile} onChange={(e) => set({ alt_mobile: e.target.value })} />
        </Field>
        <Field label="New Aadhaar (only to change it)" id="e-aadhaar" error={errors.aadhaar}>
          <Input id="e-aadhaar" autoComplete="off" value={draft.aadhaar} onChange={(e) => set({ aadhaar: e.target.value })} />
        </Field>
        <Field label="Status" id="e-status" error={errors.status}>
          <Select id="e-status" value={draft.status} onChange={(e) => set({ status: e.target.value })}>
            <option value="ACTIVE">Active</option>
            <option value="LEFT">Left the library</option>
          </Select>
        </Field>
        <Field label="Address" id="e-address" error={errors.address} className="sm:col-span-2">
          <Textarea id="e-address" rows={2} value={draft.address} onChange={(e) => set({ address: e.target.value })} />
        </Field>
        <Field label="Notes" id="e-notes" error={errors.notes} className="sm:col-span-2">
          <Textarea id="e-notes" rows={2} value={draft.notes} onChange={(e) => set({ notes: e.target.value })} />
        </Field>
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
