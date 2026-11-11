import { useState } from 'react'
import { Link } from 'react-router'
import { Field } from '@/components/admin/MembershipFields'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { useAdminMutation, useShifts, useStudents, useWaitlist } from '@/lib/queries'
import type { WaitlistEntry } from '@/lib/types'

export default function WaitlistPage() {
  const waitlist = useWaitlist()
  const [adding, setAdding] = useState(false)
  const update = useAdminMutation(({ id, status }: { id: number; status: WaitlistEntry['status'] }) =>
    api(`/admin/waitlist/${id}/`, { method: 'PATCH', body: { status } }),
  )

  return (
    <div>
      <PageHeader
        title="Waiting list"
        description="Students waiting for a seat, in order. Open a student to give them a seat."
        actions={<Button onClick={() => setAdding(true)}>Add to waiting list</Button>}
      />
      {update.error && <Alert variant="destructive" className="mb-4">{errorMessage(update.error)}</Alert>}
      {waitlist.isPending && <Spinner label="Loading waiting list" />}
      {waitlist.error && <Alert variant="destructive">{errorMessage(waitlist.error)}</Alert>}
      {waitlist.data?.length === 0 && <EmptyState title="Nobody is waiting." />}
      {waitlist.data && waitlist.data.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>No.</TH>
              <TH>Student</TH>
              <TH>Wants</TH>
              <TH>Since</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {waitlist.data.map((entry) => (
              <TR key={entry.id}>
                <TD className="tabular-nums">W{entry.position}</TD>
                <TD>
                  <Link className="font-medium hover:underline" to={`/admin/students/${entry.student}`}>
                    {entry.student_name}
                  </Link>
                  <div className="text-xs text-muted-foreground">
                    roll {entry.roll_no} · {entry.mobile}
                  </div>
                </TD>
                <TD>
                  {entry.preferred_shift_name ?? 'Any shift'}
                  {entry.note && <div className="text-xs text-muted-foreground">{entry.note}</div>}
                </TD>
                <TD>{formatDate(entry.created_at)}</TD>
                <TD className="text-right whitespace-nowrap">
                  <Button asChild size="sm">
                    <Link to={`/admin/students/${entry.student}`}>Give a seat</Link>
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: entry.id, status: 'SEATED' })}>
                    Seated
                  </Button>
                  <Button size="sm" variant="ghost" className="text-destructive" onClick={() => update.mutate({ id: entry.id, status: 'REMOVED' })}>
                    Remove
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      {adding && <AddDialog onClose={() => setAdding(false)} />}
    </div>
  )
}

function AddDialog({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState('')
  const [studentId, setStudentId] = useState('')
  const [shift, setShift] = useState('')
  const [note, setNote] = useState('')
  const shifts = useShifts()
  const matches = useStudents({ q, page_size: 10, status: 'ACTIVE' })
  const save = useAdminMutation(() =>
    api('/admin/waitlist/', {
      method: 'POST',
      body: { student: Number(studentId), preferred_shift: shift ? Number(shift) : null, note },
    }),
  )
  return (
    <Dialog open onClose={onClose} title="Add to waiting list" description="New student? Admit them first without a seat, then add them here.">
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(undefined, { onSuccess: onClose })
        }}
      >
        {save.error && <Alert variant="destructive">{errorMessage(save.error)}</Alert>}
        <Field label="Find the student" id="w-q">
          <Input id="w-q" placeholder="Name, mobile or roll no." value={q} onChange={(e) => setQ(e.target.value)} />
        </Field>
        <Field label="Student" id="w-student">
          <Select id="w-student" value={studentId} onChange={(e) => setStudentId(e.target.value)} required>
            <option value="">Choose</option>
            {matches.data?.results.map((s) => (
              <option key={s.id} value={s.id}>
                {s.full_name} · roll {s.roll_no} · {s.mobile}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Preferred shift" id="w-shift">
          <Select id="w-shift" value={shift} onChange={(e) => setShift(e.target.value)}>
            <option value="">Any shift</option>
            {shifts.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.time_label})
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Note (optional)" id="w-note">
          <Input id="w-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!studentId || save.isPending}>
            Add
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
