import { useState } from 'react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { api, errorMessage } from '@/lib/api'
import { fieldErrors, pick } from '@/lib/errors'
import { formatDate, formatMoney, todayIso } from '@/lib/format'
import { useAdminMutation } from '@/lib/queries'
import { type Membership, PAYMENT_MODES, type Payment, type PaymentMode } from '@/lib/types'
import { emptyPayment, type MembershipDraft, membershipPayload, type PaymentDraft, paymentPayload } from '@/lib/drafts'
import { Field, MembershipFields } from './MembershipFields'

export function PaymentFields({
  value,
  onChange,
  errors = {},
  idPrefix = 'p',
}: {
  value: PaymentDraft
  onChange: (next: PaymentDraft) => void
  errors?: Record<string, string>
  idPrefix?: string
}) {
  const set = (patch: Partial<PaymentDraft>) => onChange({ ...value, ...patch })
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Amount (₹)" id={`${idPrefix}-amount`} error={errors.amount}>
        <Input id={`${idPrefix}-amount`} inputMode="decimal" value={value.amount} onChange={(e) => set({ amount: e.target.value })} />
      </Field>
      <Field label="Paid by" id={`${idPrefix}-mode`} error={errors.mode}>
        <Select id={`${idPrefix}-mode`} value={value.mode} onChange={(e) => set({ mode: e.target.value as PaymentMode })}>
          {PAYMENT_MODES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Date" id={`${idPrefix}-date`} error={errors.paid_on}>
        <Input id={`${idPrefix}-date`} type="date" value={value.paid_on} onChange={(e) => set({ paid_on: e.target.value })} />
      </Field>
      <Field label="UPI / bank reference" id={`${idPrefix}-ref`} error={errors.reference}>
        <Input id={`${idPrefix}-ref`} value={value.reference} onChange={(e) => set({ reference: e.target.value })} />
      </Field>
    </div>
  )
}

export function RecordPaymentDialog({
  open,
  onClose,
  studentId,
  membership,
  onDone,
}: {
  open: boolean
  onClose: () => void
  studentId: number
  membership?: Membership | null
  onDone?: (payment: Payment) => void
}) {
  const [draft, setDraft] = useState(() => emptyPayment(membership && membership.due_total > 0 ? String(membership.due_total) : ''))
  const save = useAdminMutation(() =>
    api<Payment>('/admin/payments/', {
      method: 'POST',
      body: { student: studentId, membership: membership?.id ?? null, ...paymentPayload(draft) },
    }),
  )
  const errors = fieldErrors(save.error)
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Record a payment"
      description={
        membership
          ? `For ${membership.start_date ? formatDate(membership.start_date) : ''} – ${formatDate(membership.end_date)}. Still due: ${formatMoney(membership.due_total)}.`
          : undefined
      }
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, {
            onSuccess: (payment) => {
              onDone?.(payment)
              onClose()
            },
          })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
        <PaymentFields value={draft} onChange={setDraft} errors={errors} idPrefix="rp" />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save payment'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

export function RenewDialog({
  open,
  onClose,
  membership,
}: {
  open: boolean
  onClose: () => void
  membership: Membership
}) {
  const [terms, setTerms] = useState<MembershipDraft>({
    plan: membership.plan ? String(membership.plan) : '',
    shift: membership.shift ? String(membership.shift) : '',
    seat: membership.seat ? String(membership.seat) : '',
    start_date: '',
    end_date: '',
    price: String(membership.price),
    discount: String(membership.discount),
  })
  const [payNow, setPayNow] = useState(true)
  const [payment, setPayment] = useState(() => emptyPayment(String(membership.price - membership.discount)))
  const save = useAdminMutation(() =>
    api<Membership>(`/admin/memberships/${membership.id}/renew/`, {
      method: 'POST',
      body: { ...membershipPayload(terms), payment: payNow ? paymentPayload(payment) : null },
    }),
  )
  const errors = fieldErrors(save.error)
  return (
    <Dialog
      open={open}
      onClose={onClose}
      wide
      title={`Renew for ${membership.student_name}`}
      description="Starts the day after the current end date, or today if it has already ended. Leave the start date empty for that."
    >
      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && <Alert variant="destructive">{errors.seat ?? errorMessage(save.error)}</Alert>}
        <MembershipFields value={terms} onChange={setTerms} errors={errors} startOptional />
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={payNow} onChange={(e) => setPayNow(e.target.checked)} className="size-4" />
          Record the payment now
        </label>
        {payNow && <PaymentFields value={payment} onChange={setPayment} errors={pick(errors, 'payment')} idPrefix="renew-pay" />}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Renew'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

export function NewMembershipDialog({
  open,
  onClose,
  studentId,
  studentName,
}: {
  open: boolean
  onClose: () => void
  studentId: number
  studentName: string
}) {
  const [terms, setTerms] = useState<MembershipDraft>({
    plan: '',
    shift: '',
    seat: '',
    start_date: todayIso(),
    end_date: '',
    price: '',
    discount: '0',
  })
  const [payNow, setPayNow] = useState(true)
  const [payment, setPayment] = useState(() => emptyPayment())
  const due = Math.max(Number(terms.price || 0) - Number(terms.discount || 0), 0)
  const save = useAdminMutation(() =>
    api<Membership>('/admin/memberships/', {
      method: 'POST',
      body: {
        student: studentId,
        ...membershipPayload(terms),
        payment: payNow ? paymentPayload({ ...payment, amount: payment.amount || String(due) }) : null,
      },
    }),
  )
  const errors = fieldErrors(save.error)
  return (
    <Dialog open={open} onClose={onClose} wide title={`Give ${studentName} a seat`}>
      <form
        className="space-y-6"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && <Alert variant="destructive">{errors.seat ?? errorMessage(save.error)}</Alert>}
        <MembershipFields value={terms} onChange={setTerms} errors={errors} />
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={payNow} onChange={(e) => setPayNow(e.target.checked)} className="size-4" />
          Collect now (to pay: {formatMoney(due)})
        </label>
        {payNow && <PaymentFields value={payment} onChange={setPayment} errors={pick(errors, 'payment')} idPrefix="new-pay" />}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save membership'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
