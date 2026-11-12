import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'
import { fieldClass } from './field-styles'

const CHEVRON =
  "bg-[url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237a8a82' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")]"

/** A native select (the best picker on phones) with a drawn chevron. */
export function Select({ className, ...props }: ComponentProps<'select'>) {
  return (
    <select
      className={cn(fieldClass, 'h-10 cursor-pointer appearance-none bg-[length:16px] bg-[right_0.65rem_center] bg-no-repeat py-2 pr-9', CHEVRON, className)}
      {...props}
    />
  )
}

export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return <textarea className={cn(fieldClass, 'min-h-20 py-2 leading-relaxed', className)} {...props} />
}
