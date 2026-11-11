import { useState } from 'react'
import { useNavigate } from 'react-router'
import { PaymentFields } from '@/components/admin/dialogs'
import { Field, MembershipFields } from '@/components/admin/MembershipFields'
import { emptyPayment, type MembershipDraft, membershipPayload, paymentPayload } from '@/lib/drafts'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page'
import { Select, Textarea } from '@/components/ui/select'
import { api, errorMessage } from '@/lib/api'
import { fieldErrors, pick } from '@/lib/errors'
import { formatMoney, todayIso } from '@/lib/format'
import { useAdminMutation } from '@/lib/queries'
import type { Membership, Payment, Student } from '@/lib/types'

interface StudentDraft {
  full_name: string
  father_name: string
  gender: string
  mobile: string
  alt_mobile: string
  aadhaar: string
  address: string
  admission_date: string
  roll_no: string
  notes: string
}

const emptyStudent = (): StudentDraft => ({
  full_name: '',
  father_name: '',
  gender: '',
  mobile: '',
  alt_mobile: '',
  aadhaar: '',
  address: '',
  admission_date: todayIso(),
  roll_no: '',
  notes: '',
})

export default function AdmissionPage() {
  const navigate = useNavigate()
  const [student, setStudent] = useState(emptyStudent)
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
    api<{ student: Student; membership: Membership; payment: Payment | null }>('/admin/admissions/', {
      method: 'POST',
      body: {
        student: { ...student, roll_no: student.roll_no ? Number(student.roll_no) : undefined, admission_date: student.admission_date || null },
        membership: membershipPayload(terms),
        payment: payNow ? paymentPayload({ ...payment, amount: payment.amount || String(due) }) : null,
      },
    }),
  )
  const errors = fieldErrors(save.error)
  const studentErrors = pick(errors, 'student')
  const termErrors = pick(errors, 'membership')
  const set = (patch: Partial<StudentDraft>) => setStudent((s) => ({ ...s, ...patch }))

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate(undefined, {
          onSuccess: (result) =>
            navigate(`/admin/students/${result.student.id}`, {
              state: { notice: `${result.student.full_name} is admitted as roll ${result.student.roll_no}.`, receipt: result.payment?.id },
            }),
        })
      }}
      noValidate
    >
      <PageHeader title="New admission" description="Student details, seat and fee, and the first payment, saved together." />
      {save.error && <Alert variant="destructive" className="mb-6">{Object.keys(errors).length ? 'Please fix the highlighted fields.' : errorMessage(save.error)}</Alert>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Student</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" id="s-name" error={studentErrors.full_name} className="sm:col-span-2">
              <Input id="s-name" value={student.full_name} onChange={(e) => set({ full_name: e.target.value })} />
            </Field>
            <Field label="Father's name" id="s-father" error={studentErrors.father_name}>
              <Input id="s-father" value={student.father_name} onChange={(e) => set({ father_name: e.target.value })} />
            </Field>
            <Field label="Gender" id="s-gender" error={studentErrors.gender}>
              <Select id="s-gender" value={student.gender} onChange={(e) => set({ gender: e.target.value })}>
                <option value="">—</option>
                <option value="F">Female</option>
                <option value="M">Male</option>
                <option value="O">Other</option>
              </Select>
            </Field>
            <Field label="Mobile" id="s-mobile" error={studentErrors.mobile} hint="The student logs in with this number.">
              <Input id="s-mobile" type="tel" inputMode="numeric" value={student.mobile} onChange={(e) => set({ mobile: e.target.value })} />
            </Field>
            <Field label="Other mobile (optional)" id="s-alt" error={studentErrors.alt_mobile}>
              <Input id="s-alt" type="tel" inputMode="numeric" value={student.alt_mobile} onChange={(e) => set({ alt_mobile: e.target.value })} />
            </Field>
            <Field label="Aadhaar (optional)" id="s-aadhaar" error={studentErrors.aadhaar} hint="Stored encrypted; shown as XXXX-XXXX-1234.">
              <Input id="s-aadhaar" inputMode="numeric" autoComplete="off" value={student.aadhaar} onChange={(e) => set({ aadhaar: e.target.value })} />
            </Field>
            <Field label="Admission date" id="s-date" error={studentErrors.admission_date}>
              <Input id="s-date" type="date" value={student.admission_date} onChange={(e) => set({ admission_date: e.target.value })} />
            </Field>
            <Field label="Roll no. (optional)" id="s-roll" error={studentErrors.roll_no} hint="Leave empty for the next number.">
              <Input id="s-roll" inputMode="numeric" value={student.roll_no} onChange={(e) => set({ roll_no: e.target.value })} />
            </Field>
            <Field label="Address (optional)" id="s-address" error={studentErrors.address} className="sm:col-span-2">
              <Textarea id="s-address" rows={2} value={student.address} onChange={(e) => set({ address: e.target.value })} />
            </Field>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Seat and fee</CardTitle>
              <CardDescription>Choosing a plan fills in its shift and fee.</CardDescription>
            </CardHeader>
            <CardContent>
              <MembershipFields value={terms} onChange={setTerms} errors={termErrors} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>First payment</CardTitle>
              <CardDescription>
                <label className="flex items-center gap-2 font-medium text-foreground">
                  <input type="checkbox" className="size-4" checked={payNow} onChange={(e) => setPayNow(e.target.checked)} />
                  Collect now (to pay: {formatMoney(due)})
                </label>
              </CardDescription>
            </CardHeader>
            {payNow && (
              <CardContent>
                <PaymentFields
                  value={{ ...payment, amount: payment.amount }}
                  onChange={setPayment}
                  errors={pick(errors, 'payment')}
                  idPrefix="adm-pay"
                />
                {!payment.amount && <p className="mt-2 text-xs text-muted-foreground">Leave the amount empty to collect the full {formatMoney(due)}.</p>}
              </CardContent>
            )}
          </Card>
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        <Button type="submit" size="lg" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Admit student'}
        </Button>
      </div>
    </form>
  )
}
