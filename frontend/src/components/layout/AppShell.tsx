import { LogOut, Menu, Search, UserRound, X } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useSearchParams } from 'react-router'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/spinner'
import { type Me, ROLE_LABELS, useLogout, useMe } from '@/lib/auth'
import { useReminderSummary } from '@/lib/automation'
import { cn } from '@/lib/utils'
import { Brand } from './Brand'
import { CommandPalette } from './CommandPalette'
import { type NavGroup, PORTAL_NAV, visibleGroups } from './nav'

const SHORT_LABELS: Record<string, string> = { '/portal/profile': 'Details', '/portal/fees': 'Fees' }

function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null
  return Boolean(element && (element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName)))
}

/** While a page's code loads: the shape of a page, not a spinner in the void. */
function PageSkeleton() {
  return (
    <div role="status" aria-label="Loading page" className="space-y-6">
      <Skeleton className="h-9 w-56" />
      <Skeleton className="h-4 w-80 max-w-full" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((n) => (
          <Skeleton key={n} className="h-28 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-2xl" />
    </div>
  )
}

function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only z-[70] rounded-lg bg-card px-4 py-2 font-semibold shadow-float focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
    >
      Skip to content
    </a>
  )
}

function SidebarContent({
  groups,
  me,
  onSearch,
  onLogout,
  loggingOut,
}: {
  groups: NavGroup[]
  me: Me | null | undefined
  onSearch: () => void
  onLogout: () => void
  loggingOut: boolean
}) {
  const reminders = useReminderSummary()
  const open = reminders.data?.open ?? 0
  return (
    <>
      <div className="px-5 pt-5 pb-4">
        <Brand to="/admin" onDark />
      </div>
      <div className="px-3">
        <button
          type="button"
          onClick={onSearch}
          className="flex w-full items-center gap-2.5 rounded-lg bg-sidebar-hover px-3 py-2 text-left text-[13px] text-sidebar-muted transition-colors hover:bg-sidebar-active hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
        >
          <Search aria-hidden="true" className="size-4" />
          <span className="flex-1">Search students</span>
          <kbd className="hidden rounded border border-sidebar-border px-1.5 text-[10px] font-semibold md:inline">⌘K</kbd>
        </button>
      </div>
      <nav aria-label="Main" className="mt-2 flex-1 overflow-y-auto px-3 pb-4">
        {groups.map((group, index) => (
          <div key={group.title ?? index} className="pt-3">
            {group.title && (
              <p className="px-3 pb-1.5 text-[10.5px] font-bold tracking-[0.12em] text-sidebar-muted uppercase">{group.title}</p>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] font-medium text-sidebar-foreground/75 transition-colors',
                        'hover:bg-sidebar-hover hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none',
                        isActive &&
                          'bg-sidebar-active text-sidebar-foreground before:absolute before:inset-y-2 before:-left-3 before:w-1 before:rounded-r-full before:bg-accent',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon aria-hidden="true" className={cn('size-[18px] shrink-0', isActive ? 'text-accent' : 'text-sidebar-muted group-hover:text-sidebar-foreground')} />
                        <span className="flex-1">{item.label}</span>
                        {item.counter && open > 0 && (
                          <>
                            <span aria-hidden="true" className="rounded-full bg-accent px-1.5 py-0.5 text-[11px] leading-none font-bold text-accent-foreground tabular-nums">
                              {open}
                            </span>
                            <span className="sr-only">{`, ${open} to send`}</span>
                          </>
                        )}
                      </>
                    )}
                  </NavLink>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
      {me && (
        <div className="flex items-center gap-2.5 border-t border-sidebar-border p-3">
          <Avatar name={me.full_name} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-sidebar-foreground">{me.full_name}</p>
            <p className="text-xs text-sidebar-muted">{ROLE_LABELS[me.role]}</p>
          </div>
          <NavLink
            to="/admin/account"
            aria-label="My account"
            title="My account"
            className="rounded-lg p-2 text-sidebar-muted transition-colors hover:bg-sidebar-hover hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <UserRound aria-hidden="true" className="size-[18px]" />
          </NavLink>
          <button
            type="button"
            aria-label="Log out"
            title="Log out"
            disabled={loggingOut}
            onClick={onLogout}
            className="rounded-lg p-2 text-sidebar-muted transition-colors hover:bg-sidebar-hover hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
          >
            <LogOut aria-hidden="true" className="size-[18px]" />
          </button>
        </div>
      )}
    </>
  )
}

function AdminShell() {
  const { data: me } = useMe()
  const logout = useLogout()
  const location = useLocation()
  const groups = visibleGroups(me?.role)
  const [searching, setSearching] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [drawerPath, setDrawerPath] = useState(location.pathname)
  if (drawer && drawerPath !== location.pathname) {
    // A page was chosen in the drawer: close it (state adjusted during render, no effect).
    setDrawer(false)
  }
  if (drawerPath !== location.pathname) {
    setDrawerPath(location.pathname)
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearching(true)
      } else if (event.key === '/' && !isTyping(event.target)) {
        event.preventDefault()
        setSearching(true)
      } else if (event.key === 'Escape') {
        setDrawer(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const sidebar = (
    <SidebarContent
      groups={groups}
      me={me}
      onSearch={() => {
        setDrawer(false)
        setSearching(true)
      }}
      onLogout={() => logout.mutate()}
      loggingOut={logout.isPending}
    />
  )

  return (
    <div className="min-h-dvh bg-background md:grid md:grid-cols-[17rem_minmax(0,1fr)]">
      <SkipLink />
      <aside className="sticky top-0 hidden h-dvh flex-col bg-sidebar text-sidebar-foreground md:flex print:hidden">{sidebar}</aside>

      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b bg-card px-4 md:hidden print:hidden">
        <Brand to="/admin" />
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Search students" onClick={() => setSearching(true)}>
            <Search aria-hidden="true" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Open menu" aria-expanded={drawer} onClick={() => setDrawer(true)}>
            <Menu aria-hidden="true" />
          </Button>
        </div>
      </header>

      {drawer && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div aria-hidden="true" className="absolute inset-0 animate-fade-in bg-[oklch(0.16_0.02_165/0.5)]" onClick={() => setDrawer(false)} />
          <aside aria-label="Menu" className="relative flex h-full w-[85%] max-w-xs animate-slide-in flex-col bg-sidebar text-sidebar-foreground shadow-float">
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setDrawer(false)}
              className="absolute top-5 right-3 rounded-lg p-1.5 text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground"
            >
              <X aria-hidden="true" className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <main id="main" className="min-w-0 px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
        <div className="mx-auto max-w-6xl">
          <Suspense fallback={<PageSkeleton />}>
            <Outlet />
          </Suspense>
        </div>
      </main>

      {searching && <CommandPalette pages={groups.flatMap((g) => g.items)} onClose={() => setSearching(false)} />}
    </div>
  )
}

function PortalShell() {
  const { data: me } = useMe()
  const logout = useLogout()
  // Siblings share a login: keep the chosen student (?profile=) when moving between tabs.
  const [params] = useSearchParams()
  const profile = params.get('profile')
  return (
    <div className="min-h-dvh bg-background">
      <SkipLink />
      <header className="sticky top-0 z-30 border-b bg-card print:hidden">
        <div className="mx-auto flex h-16 w-full max-w-4xl items-center justify-between gap-4 px-4">
          <Brand to="/portal" />
          <div className="flex items-center gap-3">
            {me && (
              <>
                <div className="hidden text-right sm:block">
                  <p className="text-sm leading-tight font-semibold">{me.full_name}</p>
                  <p className="text-xs text-muted-foreground">Student</p>
                </div>
                <Avatar name={me.full_name} />
              </>
            )}
            <Button variant="ghost" size="sm" onClick={() => logout.mutate()} disabled={logout.isPending}>
              <LogOut aria-hidden="true" />
              <span className="hidden sm:inline">Log out</span>
              <span className="sr-only sm:hidden">Log out</span>
            </Button>
          </div>
        </div>
        {/* On phones this sits at the bottom of the screen like an app's tab bar. */}
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t bg-card pb-[env(safe-area-inset-bottom)] sm:static sm:mx-auto sm:flex sm:max-w-4xl sm:gap-1 sm:border-0 sm:bg-transparent sm:px-3 sm:pb-3"
        >
          {PORTAL_NAV.map((item) => {
            const Icon = item.icon
            const short = SHORT_LABELS[item.to]
            return (
              <NavLink
                key={item.to}
                to={profile ? `${item.to}?profile=${encodeURIComponent(profile)}` : item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'flex flex-col items-center gap-1 py-2.5 text-[11px] font-semibold text-muted-foreground transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                    'sm:flex-row sm:gap-2 sm:rounded-full sm:px-3.5 sm:py-1.5 sm:text-sm sm:hover:bg-muted sm:hover:text-foreground',
                    isActive && 'text-primary sm:bg-secondary sm:text-secondary-foreground sm:hover:bg-secondary',
                  )
                }
              >
                <Icon aria-hidden="true" className="size-5 sm:size-4" />
                {short ? (
                  <>
                    <span className="sm:hidden">{short}</span>
                    <span className="hidden sm:inline">{item.label}</span>
                  </>
                ) : (
                  item.label
                )}
              </NavLink>
            )
          })}
        </nav>
      </header>
      <main id="main" className="mx-auto w-full max-w-4xl px-4 pt-6 pb-28 sm:pt-8 sm:pb-12">
        <Suspense fallback={<PageSkeleton />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}

export function AppShell({ area }: { area: 'portal' | 'admin' }) {
  return area === 'admin' ? <AdminShell /> : <PortalShell />
}
