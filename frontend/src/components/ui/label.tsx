import { CircleAlert } from 'lucide-react'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Label({ className, ...props }: ComponentProps<'label'>) {
  return <label className={cn('text-[13px] font-semibold leading-none text-foreground/90', className)} {...props} />
}

export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) {
    return null
  }
  return (
    <p id={id} className="flex items-start gap-1.5 text-sm text-destructive">
      <CircleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
      {message}
    </p>
  )
}
