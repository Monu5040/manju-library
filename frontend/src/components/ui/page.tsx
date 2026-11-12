import { ChevronLeft, ChevronRight, Inbox, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useLocation } from 'react-router'
import { ADMIN_NAV } from '@/components/layout/nav'
import { cn } from '@/lib/utils'
import { Button } from './button'

/** The menu section a back-office page belongs to ("Money" for /admin/payments/12). */
function sectionOf(pathname: string): string | undefined {
  let best: { title?: string; length: number } = { length: 0 }
  for (const group of ADMIN_NAV) {
    for (const item of group.items) {
      const matches = pathname === item.to || pathname.startsWith(`${item.to}/`)
      if (matches && item.to.length > best.length && item.to !== '/admin') {
        best = { title: group.title, length: item.to.length }
      }
    }
  }
  return best.title
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  media,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
  /** Shown left of the title, for example a student's avatar. */
  media?: ReactNode
  /** A short line above the title. Defaults to the menu section ("Money"); false hides it. */
  eyebrow?: ReactNode
}) {
  const { pathname } = useLocation()
  const label = eyebrow === undefined ? sectionOf(pathname) : eyebrow
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 sm:mb-8">
      <div className="flex min-w-0 items-center gap-4">
        {media}
        <div className="min-w-0 space-y-1.5">
          {label && <p className="text-xs font-semibold tracking-[0.08em] text-primary uppercase">{label}</p>}
          <h1 className="font-display text-[1.75rem] leading-[1.15] font-semibold tracking-[-0.01em] sm:text-[2.125rem]">{title}</h1>
          {description && <div className="max-w-2xl text-[15px] leading-relaxed text-muted-foreground">{description}</div>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function EmptyState({
  title,
  children,
  icon: Icon = Inbox,
  action,
}: {
  title: string
  children?: ReactNode
  icon?: LucideIcon
  action?: ReactNode
}) {
  return (
    <div className="rounded-2xl border border-dashed border-input bg-card/60 px-6 py-14 text-center">
      <span className="mx-auto mb-4 grid size-12 place-items-center rounded-2xl bg-secondary text-secondary-foreground">
        <Icon aria-hidden="true" className="size-5" />
      </span>
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-1.5 max-w-sm text-sm leading-relaxed text-muted-foreground">{children}</div>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
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
    <nav aria-label="Pages" className="mt-4 flex items-center justify-between gap-4 text-sm text-muted-foreground">
      <span className="tabular-nums">
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

/**
 * A key number in a card. Use inside a <dl>. The icon sits inside the label so the
 * description-list markup stays valid.
 */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  className,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: LucideIcon
  className?: string
}) {
  return (
    <div className={cn('rounded-2xl border bg-card p-4 shadow-card sm:p-5', className)}>
      <dt className="flex items-start justify-between gap-3 text-sm font-medium text-muted-foreground">
        {label}
        {Icon && (
          <span className="-mt-0.5 hidden size-9 shrink-0 place-items-center rounded-xl bg-secondary text-secondary-foreground sm:grid">
            <Icon aria-hidden="true" className="size-[18px]" />
          </span>
        )}
      </dt>
      <dd className="mt-1.5 text-2xl leading-tight font-semibold tracking-tight sm:text-[1.75rem]">{value}</dd>
      {hint && <dd className="mt-1 text-xs text-muted-foreground">{hint}</dd>}
    </div>
  )
}
