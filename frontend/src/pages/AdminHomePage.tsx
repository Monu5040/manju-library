import { useQuery } from '@tanstack/react-query'
import { Alert } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { api, errorMessage } from '@/lib/api'

interface Overview {
  users: { students: number; staff: number; super_admins: number }
}

const COMING_NEXT = [
  'Students and admissions',
  'Seat map and shifts',
  'Plans, renewals and payments with receipts',
  'Excel and CSV import and export',
]

export default function AdminHomePage() {
  const overview = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: () => api<Overview>('/admin/overview/'),
  })

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>

      {overview.isPending && <Spinner label="Loading overview" />}
      {overview.error && <Alert variant="destructive">{errorMessage(overview.error)}</Alert>}
      {overview.data && (
        <dl className="grid gap-4 sm:grid-cols-3">
          <Stat label="Student accounts" value={overview.data.users.students} />
          <Stat label="Staff accounts" value={overview.data.users.staff} />
          <Stat label="Super Admins" value={overview.data.users.super_admins} />
        </dl>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Coming next</CardTitle>
          <CardDescription>The admin panel grows section by section.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {COMING_NEXT.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-3xl font-semibold tabular-nums">{value}</dd>
    </div>
  )
}
