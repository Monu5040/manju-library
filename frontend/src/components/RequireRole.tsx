import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { FullPageSpinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { homePathFor, type Role, useMe } from '@/lib/auth'

/**
 * Shows its children only to people with one of `roles`. Anyone else is sent to the right
 * login page, or to their own home if they are signed in with a different role.
 * The server checks every request too; this only keeps the screens tidy.
 */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { data: me, isPending, error } = useMe()
  const location = useLocation()

  if (isPending) {
    return <FullPageSpinner />
  }
  if (error) {
    return (
      <div className="mx-auto max-w-md p-8">
        <Alert variant="destructive">{errorMessage(error)}</Alert>
      </div>
    )
  }
  if (!me) {
    const loginPath = roles.includes('STUDENT') ? '/login' : '/staff/login'
    return <Navigate to={loginPath} replace state={{ from: location.pathname }} />
  }
  if (!roles.includes(me.role)) {
    return <Navigate to={homePathFor(me.role)} replace />
  }
  return children
}
