import { useState } from 'react'
import { Link } from 'react-router'
import { DueBadge, StateBadge } from '@/components/admin/badges'
import { RenewDialog } from '@/components/admin/dialogs'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { EmptyState, PageHeader } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { useMemberships } from '@/lib/queries'
import type { Membership } from '@/lib/types'

export default function RenewalsPage() {
  const [days, setDays] = useState('7')
  const [renewing, setRenewing] = useState<Membership | null>(null)
  const memberships = useMemberships({ expiring_within: days, ordering: 'end_date', page_size: 200 })

  return (
    <div>
      <PageHeader
        title="Renewals due"
        description="Memberships ending soon that have not been renewed yet."
        actions={
          <Select aria-label="Ending within" className="w-auto" value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="3">Next 3 days</option>
            <option value="7">Next 7 days</option>
            <option value="15">Next 15 days</option>
            <option value="30">Next 30 days</option>
          </Select>
        }
      />
      {memberships.isPending && <Spinner label="Loading renewals" />}
      {memberships.error && <Alert variant="destructive">{errorMessage(memberships.error)}</Alert>}
      {memberships.data?.results.length === 0 && <EmptyState title="Nothing to renew in this period." />}
      {memberships.data && memberships.data.results.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>Student</TH>
              <TH>Seat · shift</TH>
              <TH>Ends</TH>
              <TH>Fees</TH>
              <TH>
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {memberships.data.results.map((m) => (
              <TR key={m.id}>
                <TD>
                  <Link className="font-medium hover:underline" to={`/admin/students/${m.student}`}>
                    {m.student_name}
                  </Link>
                  <div className="text-xs text-muted-foreground">roll {m.roll_no}</div>
                </TD>
                <TD>
                  {m.seat_number ? `Seat ${m.seat_number}` : 'No seat'}
                  <div className="text-xs text-muted-foreground">{m.shift_name ?? m.time_label}</div>
                </TD>
                <TD>
                  <div>{formatDate(m.end_date)}</div>
                  <StateBadge state={m.state} daysLeft={m.days_left} />
                </TD>
                <TD>
                  <DueBadge amount={m.due_total} />
                </TD>
                <TD className="text-right">
                  <Button size="sm" onClick={() => setRenewing(m)}>
                    Renew
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      {renewing && <RenewDialog open membership={renewing} onClose={() => setRenewing(null)} />}
    </div>
  )
}
