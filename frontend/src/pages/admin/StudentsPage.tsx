import { Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { DueBadge, StateBadge } from '@/components/admin/badges'
import { ExportMenu } from '@/components/admin/ExportMenu'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { EmptyState, PageHeader, Pagination } from '@/components/ui/page'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { errorMessage } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { useShifts, useStudents } from '@/lib/queries'

const PAGE_SIZE = 25

const VIEWS: Record<string, { label: string; params: Record<string, string | number | boolean> }> = {
  active: { label: 'Current students', params: { status: 'ACTIVE' } },
  expiring: { label: 'Ending in 7 days', params: { expiring_within: 7 } },
  due: { label: 'With dues', params: { has_due: true } },
  none: { label: 'No current membership', params: { without_membership: true, status: 'ACTIVE' } },
  left: { label: 'Left the library', params: { status: 'LEFT' } },
  all: { label: 'Everyone', params: {} },
}

export default function StudentsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const view = searchParams.get('view') ?? 'active'
  const page = Number(searchParams.get('page') ?? 1)
  const shift = searchParams.get('shift') ?? ''
  const [q, setQ] = useState(searchParams.get('q') ?? '')
  const shifts = useShifts()

  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in patch)) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  const filters = { ...(VIEWS[view] ?? VIEWS.active).params, q: searchParams.get('q') ?? '', shift }
  const students = useStudents({ ...filters, page, page_size: PAGE_SIZE })

  return (
    <div>
      <PageHeader
        title="Students"
        description={students.data ? `${students.data.count} found` : undefined}
        actions={
          <>
            <ExportMenu path="/admin/students/export/" params={filters} aadhaar />
            <Button asChild>
              <Link to="/admin/students/new">New admission</Link>
            </Button>
          </>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <form
          role="search"
          onSubmit={(event) => {
            event.preventDefault()
            update({ q })
          }}
          className="relative"
        >
          <Search aria-hidden="true" className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
          <Input
            aria-label="Search students"
            placeholder="Name, father's name, mobile or roll no."
            className="pl-9"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onBlur={() => q !== (searchParams.get('q') ?? '') && update({ q })}
          />
        </form>
        <Select aria-label="Which students" value={view} onChange={(e) => update({ view: e.target.value })}>
          {Object.entries(VIEWS).map(([key, v]) => (
            <option key={key} value={key}>
              {v.label}
            </option>
          ))}
        </Select>
        <Select aria-label="Shift" value={shift} onChange={(e) => update({ shift: e.target.value })}>
          <option value="">All shifts</option>
          {shifts.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </div>

      {students.isPending && <Spinner label="Loading students" />}
      {students.error && <Alert variant="destructive">{errorMessage(students.error)}</Alert>}
      {students.data?.results.length === 0 && (
        <EmptyState title="No students match.">Try another search or view.</EmptyState>
      )}
      {students.data && students.data.results.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>Roll</TH>
              <TH>Name</TH>
              <TH>Mobile</TH>
              <TH>Seat · shift</TH>
              <TH>Ends</TH>
              <TH>Fees</TH>
            </TR>
          </THead>
          <TBody>
            {students.data.results.map((s) => {
              const m = s.current_membership
              return (
                <TR
                  key={s.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/admin/students/${s.id}`)}
                >
                  <TD className="tabular-nums text-muted-foreground">{s.roll_no}</TD>
                  <TD>
                    <Link to={`/admin/students/${s.id}`} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
                      {s.full_name}
                    </Link>
                    {s.father_name && <div className="text-xs text-muted-foreground">c/o {s.father_name}</div>}
                  </TD>
                  <TD className="tabular-nums">{s.mobile}</TD>
                  <TD>{m ? `${m.seat_number ? `Seat ${m.seat_number}` : 'No seat'} · ${m.shift_name ?? m.time_label}` : '—'}</TD>
                  <TD>
                    {m ? (
                      <div className="flex flex-col items-start gap-1">
                        <span className="text-sm">{formatDate(m.end_date)}</span>
                        <StateBadge state={m.state} daysLeft={m.days_left} />
                      </div>
                    ) : (
                      '—'
                    )}
                  </TD>
                  <TD>
                    <DueBadge amount={s.total_due} />
                  </TD>
                </TR>
              )
            })}
          </TBody>
        </Table>
      )}
      {students.data && (
        <Pagination page={page} pageSize={PAGE_SIZE} count={students.data.count} onPage={(p) => update({ page: String(p) })} />
      )}
    </div>
  )
}
