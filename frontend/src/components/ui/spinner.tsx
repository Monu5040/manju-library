import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Spinner({ className, label = 'Loading' }: { className?: string; label?: string }) {
  return (
    <span role="status" className={cn('inline-flex items-center gap-2', className)}>
      <LoaderCircle aria-hidden="true" className="size-5 animate-spin text-muted-foreground" />
      <span className="sr-only">{label}</span>
    </span>
  )
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <Spinner />
    </div>
  )
}
