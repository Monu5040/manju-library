import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from './button'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed bg-card px-6 py-12 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-muted-foreground">{children}</div>}
    </div>
  )
}

export function Pagination({
  page,
  pageSize,
  count,
  onPage,
}: {
  page: number
  pageSize: number
  count: number
  onPage: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  if (count <= pageSize) {
    return null
  }
  const first = (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, count)
  return (
    <nav aria-label="Pages" className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {first}–{last} of {count}
      </span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft aria-hidden="true" /> Previous
        </Button>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next <ChevronRight aria-hidden="true" />
        </Button>
      </div>
    </nav>
  )
}

export function StatCard({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums sm:text-3xl">{value}</dd>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
