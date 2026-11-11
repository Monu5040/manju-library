import { LogOut } from 'lucide-react'
import { Suspense } from 'react'
import { NavLink, Outlet } from 'react-router'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { ROLE_LABELS, type Role, useLogout, useMe } from '@/lib/auth'
import { cn } from '@/lib/utils'
import { Brand } from './Brand'

interface NavItem {
  to: string
  label: string
  end?: boolean
  roles?: Role[]
}

const NAV: Record<'portal' | 'admin', NavItem[]> = {
  portal: [
    { to: '/portal', label: 'Home', end: true },
    { to: '/portal/payments', label: 'Payments' },
    { to: '/portal/profile', label: 'My details' },
    { to: '/portal/fees', label: 'Fees and timings' },
  ],
  admin: [
    { to: '/admin', label: 'Overview', end: true },
    { to: '/admin/students', label: 'Students' },
    { to: '/admin/seats', label: 'Seat map' },
    { to: '/admin/renewals', label: 'Renewals' },
    { to: '/admin/payments', label: 'Payments' },
    { to: '/admin/waitlist', label: 'Waiting list' },
    { to: '/admin/notices', label: 'Notices' },
    { to: '/admin/import', label: 'Import', roles: ['SUPER_ADMIN'] },
    { to: '/admin/settings', label: 'Settings' },
    { to: '/admin/staff', label: 'Staff', roles: ['SUPER_ADMIN'] },
    { to: '/admin/account', label: 'My account' },
  ],
}

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    'rounded-md px-3 py-2 text-sm font-medium whitespace-nowrap text-muted-foreground hover:bg-muted hover:text-foreground',
    isActive && 'bg-muted text-foreground',
  )
}

export function AppShell({ area }: { area: keyof typeof NAV }) {
  const { data: me } = useMe()
  const logout = useLogout()
  const items = NAV[area].filter((item) => !item.roles || (me && item.roles.includes(me.role)))
  const home = area === 'admin' ? '/admin' : '/portal'

  const userBox = me && (
    <div className="text-sm">
      <div className="font-medium">{me.full_name}</div>
      <div className="text-muted-foreground">{ROLE_LABELS[me.role]}</div>
    </div>
  )
  const logoutButton = (
    <Button variant="ghost" size="sm" onClick={() => logout.mutate()} disabled={logout.isPending}>
      <LogOut aria-hidden="true" />
      Log out
    </Button>
  )

  if (area === 'portal') {
    return (
      <div className="flex min-h-dvh flex-col">
        <header className="border-b bg-card print:hidden">
          <div className="mx-auto flex h-16 w-full max-w-4xl items-center justify-between gap-4 px-4">
            <Brand to={home} />
            <div className="flex items-center gap-4">
              <div className="hidden sm:block">{userBox}</div>
              {logoutButton}
            </div>
          </div>
          <nav aria-label="Main" className="mx-auto flex w-full max-w-4xl gap-1 overflow-x-auto px-3 pb-3">
            {items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
          <Suspense fallback={<Spinner label="Loading page" />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    )
  }

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="flex flex-col border-b bg-card md:sticky md:top-0 md:h-dvh md:w-60 md:shrink-0 md:border-r md:border-b-0 print:hidden">
        <div className="flex h-16 items-center justify-between gap-2 px-4">
          <Brand to={home} />
          <div className="md:hidden">{logoutButton}</div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-1 md:flex-col md:overflow-visible">
          {items.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden items-center justify-between gap-2 border-t p-4 md:flex">
          {userBox}
          {logoutButton}
        </div>
      </aside>
      <main className="w-full min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-6xl">
          <Suspense fallback={<Spinner label="Loading page" />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  )
}
