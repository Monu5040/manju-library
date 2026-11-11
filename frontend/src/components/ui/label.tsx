import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Label({ className, ...props }: ComponentProps<'label'>) {
  return <label className={cn('text-sm font-medium leading-none', className)} {...props} />
}

export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) {
    return null
  }
  return (
    <p id={id} className="text-sm text-destructive">
      {message}
    </p>
  )
}
