import { Link, Outlet } from 'react-router'
import { Button } from '@/components/ui/button'
import { homePathFor, useMe } from '@/lib/auth'
import { Brand } from './Brand'

const CURRENT_YEAR = new Date().getFullYear()

export function PublicLayout() {
  const { data: me } = useMe()

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-4">
          <Brand />
          {me ? (
            <Button asChild variant="outline" size="sm">
              <Link to={homePathFor(me.role)}>Go to my dashboard</Link>
            </Button>
          ) : (
            <Button asChild variant="outline" size="sm">
              <Link to="/login">Student login</Link>
            </Button>
          )}
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        © {CURRENT_YEAR} Manju Library
      </footer>
    </div>
  )
}
