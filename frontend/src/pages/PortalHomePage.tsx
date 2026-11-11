import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useMe } from '@/lib/auth'

export default function PortalHomePage() {
  const { data: me } = useMe()
  const firstName = me?.full_name.split(' ')[0] ?? ''

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Hello, {firstName}</h1>
      <Card>
        <CardHeader>
          <CardTitle>Your membership</CardTitle>
          <CardDescription>
            Your seat, shift, plan and expiry date will show here once the library's records are
            online.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
