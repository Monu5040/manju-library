import { BookOpen } from 'lucide-react'
import { Link } from 'react-router'

export function Brand({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2 font-semibold tracking-tight">
      <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
        <BookOpen aria-hidden="true" className="size-4" />
      </span>
      Manju Library
    </Link>
  )
}
