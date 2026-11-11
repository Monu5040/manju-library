import { LogOut } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import { Button } from '@/components/ui/button'
import { ROLE_LABELS, useLogout, useMe } from '@/lib/auth'
import { cn } from '@/lib/utils'
import { Brand } from './Brand'

const NAV = {
  portal: [{ to: '/portal', label: 'Home' }],
  admin: [{ to: '/admin', label: 'Overview' }],
} as const

export function AppShell({ area }: { area: keyof typeof NAV }) {
  const { data: me } = useMe()
  const logout = useLogout()

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-6 px-4">
          <Brand to={area === 'admin' ? '/admin' : '/portal'} />
          <nav aria-label="Main" className="flex flex-1 items-center gap-1">
            {NAV[area].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground',
                    isActive && 'bg-muted text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          {me && (
            <div className="hidden text-right text-sm sm:block">
              <div className="font-medium">{me.full_name}</div>
              <div className="text-muted-foreground">{ROLE_LABELS[me.role]}</div>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            <LogOut aria-hidden="true" />
            Log out
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
