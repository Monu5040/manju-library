import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-3xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-muted-foreground">The page you asked for does not exist.</p>
      <Button asChild>
        <Link to="/">Go to the home page</Link>
      </Button>
    </div>
  )
}
