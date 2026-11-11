import { useState } from 'react'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AutomationCard } from '@/components/admin/AutomationCard'
import { CategoriesCard } from '@/components/admin/CategoriesCard'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page'
import { Select, Textarea } from '@/components/ui/select'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { fieldErrors } from '@/lib/errors'
import { formatMoney, timeShort } from '@/lib/format'
import { useAdminMutation, useBranch, usePlans, useSeats, useShifts } from '@/lib/queries'
import type { Branch, Plan, Shift } from '@/lib/types'

export default function SettingsPage() {
  const { data: me } = useMe()
  const canEdit = me?.role === 'SUPER_ADMIN'
  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description={canEdit ? 'How the library is set up.' : 'Only the Super Admin can change these.'} />
      <BranchCard canEdit={canEdit} />
      <ShiftsCard canEdit={canEdit} />
      <SeatsCard canEdit={canEdit} />
      <PlansCard canEdit={canEdit} />
      <AutomationCard canEdit={canEdit} />
      <CategoriesCard canEdit={canEdit} />
    </div>
  )
}

function BranchCard({ canEdit }: { canEdit: boolean }) {
  const branch = useBranch()
  const [draft, setDraft] = useState<Partial<Branch> | null>(null)
  const save = useAdminMutation((body: Partial<Branch>) => api(`/admin/branches/${branch.data?.id}/`, { method: 'PATCH', body }))
  if (!branch.data) return null
  const value = { ...branch.data, ...draft }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Library</CardTitle>
        <CardDescription>Shown on receipts.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (draft) save.mutate(draft, { onSuccess: () => setDraft(null) })
          }}
        >
          {save.error && <Alert variant="destructive" className="sm:col-span-2">{errorMessage(save.error)}</Alert>}
          <Field label="Name" id="b-name">
            <Input id="b-name" disabled={!canEdit} value={value.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </Field>
          <Field label="Phone" id="b-phone">
            <Input id="b-phone" disabled={!canEdit} value={value.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
          </Field>
          <Field label="Address" id="b-address" className="sm:col-span-2">
            <Textarea id="b-address" rows={2} disabled={!canEdit} value={value.address} onChange={(e) => setDraft({ ...draft, address: e.target.value })} />
          </Field>
          <label className="flex items-start gap-3 text-sm sm:col-span-2">
            <input
              type="checkbox"
              className="mt-0.5 size-4"
              disabled={!canEdit}
              checked={value.allow_seat_sharing}
              onChange={(e) => setDraft({ ...draft, allow_seat_sharing: e.target.checked })}
            />
            <span>
              <span className="font-medium">Share seats between shifts</span>
              <span className="block text-muted-foreground">A seat can go to different students in shifts that do not overlap, such as morning and evening.</span>
            </span>
          </label>
          {canEdit && (
            <div className="sm:col-span-2">
              <Button type="submit" disabled={!draft || save.isPending}>
                Save
              </Button>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  )
}

function ShiftsCard({ canEdit }: { canEdit: boolean }) {
  const shifts = useShifts()
  const [editing, setEditing] = useState<Partial<Shift> | null>(null)
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle>Shifts</CardTitle>
          <CardDescription>An end time before the start time means the shift runs past midnight.</CardDescription>
        </div>
        {canEdit && <Button size="sm" onClick={() => setEditing({ is_active: true, sort_order: shifts.data?.length ?? 0 })}>Add shift</Button>}
      </CardHeader>
      <CardContent>
        <Table>
          <THead>
            <TR>
              <TH>Name</TH>
              <TH>Time</TH>
              <TH>Hours</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {shifts.data?.map((s) => (
              <TR key={s.id}>
                <TD className="font-medium">
                  {s.name} {!s.is_active && <Badge>off</Badge>}
                </TD>
                <TD>{s.time_label}</TD>
                <TD className="tabular-nums">{s.hours}</TD>
                <TD className="text-right">
                  {canEdit && (
                    <Button size="sm" variant="ghost" onClick={() => setEditing(s)}>
                      Edit
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </CardContent>
      {editing && <ShiftDialog shift={editing} onClose={() => setEditing(null)} />}
    </Card>
  )
}

function ShiftDialog({ shift, onClose }: { shift: Partial<Shift>; onClose: () => void }) {
  const [draft, setDraft] = useState({
    name: shift.name ?? '',
    start_time: shift.start_time?.slice(0, 5) ?? '',
    end_time: shift.end_time?.slice(0, 5) ?? '',
    sort_order: String(shift.sort_order ?? 0),
    is_active: shift.is_active ?? true,
  })
  const save = useAdminMutation(() =>
    api(shift.id ? `/admin/shifts/${shift.id}/` : '/admin/shifts/', {
      method: shift.id ? 'PATCH' : 'POST',
      body: { ...draft, sort_order: Number(draft.sort_order) },
    }),
  )
  const errors = fieldErrors(save.error)
  return (
    <Dialog open onClose={onClose} title={shift.id ? `Edit ${shift.name}` : 'Add shift'}>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive" className="sm:col-span-2">{errorMessage(save.error)}</Alert>}
        <Field label="Name" id="sh-name" error={errors.name} className="sm:col-span-2">
          <Input id="sh-name" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </Field>
        <Field label="Starts" id="sh-start" error={errors.start_time} hint={timeShort(draft.start_time)}>
          <Input id="sh-start" type="time" value={draft.start_time} onChange={(e) => setDraft({ ...draft, start_time: e.target.value })} />
        </Field>
        <Field label="Ends" id="sh-end" error={errors.end_time} hint={timeShort(draft.end_time)}>
          <Input id="sh-end" type="time" value={draft.end_time} onChange={(e) => setDraft({ ...draft, end_time: e.target.value })} />
        </Field>
        <Field label="Order in lists" id="sh-order" error={errors.sort_order}>
          <Input id="sh-order" inputMode="numeric" value={draft.sort_order} onChange={(e) => setDraft({ ...draft, sort_order: e.target.value })} />
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input type="checkbox" className="size-4" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />
          In use
        </label>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

function SeatsCard({ canEdit }: { canEdit: boolean }) {
  const seats = useSeats()
  const [range, setRange] = useState({ first: '1', last: '51' })
  const add = useAdminMutation(() =>
    api('/admin/seats/add-range/', { method: 'POST', body: { first: Number(range.first), last: Number(range.last) } }),
  )
  const toggle = useAdminMutation(({ id, is_active }: { id: number; is_active: boolean }) =>
    api(`/admin/seats/${id}/`, { method: 'PATCH', body: { is_active } }),
  )
  const active = seats.data?.filter((s) => s.is_active).length ?? 0
  return (
    <Card>
      <CardHeader>
        <CardTitle>Seats</CardTitle>
        <CardDescription>
          {active} in use{canEdit ? '. Click a seat to switch it off or on.' : '.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {(add.error || toggle.error) && <Alert variant="destructive">{errorMessage(add.error ?? toggle.error)}</Alert>}
        {canEdit && (
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              add.mutate(undefined)
            }}
          >
            <Field label="From seat" id="seat-first">
              <Input id="seat-first" className="w-24" inputMode="numeric" value={range.first} onChange={(e) => setRange({ ...range, first: e.target.value })} />
            </Field>
            <Field label="To seat" id="seat-last">
              <Input id="seat-last" className="w-24" inputMode="numeric" value={range.last} onChange={(e) => setRange({ ...range, last: e.target.value })} />
            </Field>
            <Button type="submit" variant="outline" disabled={add.isPending}>
              Add seats
            </Button>
          </form>
        )}
        <ul className="flex flex-wrap gap-2" aria-label="Seats">
          {seats.data?.map((seat) => (
            <li key={seat.id}>
              <button
                type="button"
                disabled={!canEdit || toggle.isPending}
                onClick={() => toggle.mutate({ id: seat.id, is_active: !seat.is_active })}
                className={
                  seat.is_active
                    ? 'min-w-10 rounded-md border bg-card px-2 py-1 text-sm tabular-nums'
                    : 'min-w-10 rounded-md border border-dashed bg-muted px-2 py-1 text-sm text-muted-foreground tabular-nums line-through'
                }
                aria-label={`Seat ${seat.number}, ${seat.is_active ? 'in use' : 'switched off'}`}
              >
                {seat.number}
              </button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

function PlansCard({ canEdit }: { canEdit: boolean }) {
  const plans = usePlans()
  const [editing, setEditing] = useState<Partial<Plan> | null>(null)
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle>Plans and fees</CardTitle>
          <CardDescription>Fees can still be changed for a single student.</CardDescription>
        </div>
        {canEdit && <Button size="sm" onClick={() => setEditing({ duration_months: 1, is_active: true })}>Add plan</Button>}
      </CardHeader>
      <CardContent>
        <Table>
          <THead>
            <TR>
              <TH>Plan</TH>
              <TH>Length</TH>
              <TH>Shift</TH>
              <TH>Fee</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {plans.data?.map((p) => (
              <TR key={p.id}>
                <TD className="font-medium">
                  {p.name} {!p.is_active && <Badge>off</Badge>}
                </TD>
                <TD>
                  {p.duration_months} month{p.duration_months > 1 ? 's' : ''}
                </TD>
                <TD>{p.shift_name ?? 'Any'}</TD>
                <TD className="tabular-nums">{formatMoney(p.price)}</TD>
                <TD className="text-right">
                  {canEdit && (
                    <Button size="sm" variant="ghost" onClick={() => setEditing(p)}>
                      Edit
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </CardContent>
      {editing && <PlanDialog plan={editing} onClose={() => setEditing(null)} />}
    </Card>
  )
}

function PlanDialog({ plan, onClose }: { plan: Partial<Plan>; onClose: () => void }) {
  const shifts = useShifts()
  const [draft, setDraft] = useState({
    name: plan.name ?? '',
    duration_months: String(plan.duration_months ?? 1),
    shift: plan.shift ? String(plan.shift) : '',
    price: plan.price !== undefined ? String(plan.price) : '',
    is_active: plan.is_active ?? true,
  })
  const save = useAdminMutation(() =>
    api(plan.id ? `/admin/plans/${plan.id}/` : '/admin/plans/', {
      method: plan.id ? 'PATCH' : 'POST',
      body: { ...draft, duration_months: Number(draft.duration_months), shift: draft.shift ? Number(draft.shift) : null, price: Number(draft.price) },
    }),
  )
  const errors = fieldErrors(save.error)
  return (
    <Dialog open onClose={onClose} title={plan.id ? `Edit ${plan.name}` : 'Add plan'}>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && !Object.keys(errors).length && <Alert variant="destructive" className="sm:col-span-2">{errorMessage(save.error)}</Alert>}
        <Field label="Name" id="pl-name" error={errors.name} className="sm:col-span-2">
          <Input id="pl-name" placeholder="1 month · Day" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
        </Field>
        <Field label="Length" id="pl-months" error={errors.duration_months}>
          <Select id="pl-months" value={draft.duration_months} onChange={(e) => setDraft({ ...draft, duration_months: e.target.value })}>
            {[1, 2, 3, 6, 12].map((m) => (
              <option key={m} value={m}>
                {m} month{m > 1 ? 's' : ''}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Fee (₹)" id="pl-price" error={errors.price}>
          <Input id="pl-price" inputMode="decimal" value={draft.price} onChange={(e) => setDraft({ ...draft, price: e.target.value })} />
        </Field>
        <Field label="Shift" id="pl-shift" error={errors.shift} className="sm:col-span-2">
          <Select id="pl-shift" value={draft.shift} onChange={(e) => setDraft({ ...draft, shift: e.target.value })}>
            <option value="">Any shift</option>
            {shifts.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.time_label})
              </option>
            ))}
          </Select>
        </Field>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" className="size-4" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />
          Offered to new students
        </label>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
