import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'
import { fieldClass } from './field-styles'

export function Input({ className, type = 'text', ...props }: ComponentProps<'input'>) {
  return (
    <input
      type={type}
      className={cn(
        fieldClass,
        'h-10 py-2 file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1 file:text-sm file:font-medium file:text-secondary-foreground',
        className,
      )}
      {...props}
    />
  )
}
