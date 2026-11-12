import { Link, Outlet } from 'react-router'
import { Button } from '@/components/ui/button'
import { homePathFor, useMe } from '@/lib/auth'
import { Brand } from './Brand'

const CURRENT_YEAR = new Date().getFullYear()

export function PublicLayout() {
  const { data: me } = useMe()

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/95">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-5">
          <Brand />
          <nav aria-label="Sign in" className="flex items-center gap-2">
            {me ? (
              <Button asChild size="sm">
                <Link to={homePathFor(me.role)}>Go to my dashboard</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                  <Link to="/staff/login">Staff login</Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/login">Student login</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-3 px-5 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center">
          <Brand />
          <p>© {CURRENT_YEAR} Manju Library · A quiet place to study</p>
        </div>
      </footer>
    </div>
  )
}
