import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset',
  {
    variants: {
      tone: {
        neutral: 'bg-muted text-muted-foreground ring-border',
        success: 'bg-success/10 text-success ring-success/25',
        warning: 'bg-warning/15 text-foreground ring-warning/40',
        danger: 'bg-destructive/10 text-destructive ring-destructive/25',
        info: 'bg-secondary text-secondary-foreground ring-primary/15',
        accent: 'bg-accent/20 text-accent-foreground ring-accent/45',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

const DOTS = {
  neutral: 'bg-muted-foreground',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-destructive',
  info: 'bg-primary',
  accent: 'bg-accent',
} as const

export function Badge({
  className,
  tone,
  dot = false,
  children,
  ...props
}: ComponentProps<'span'> & VariantProps<typeof badgeVariants> & { dot?: boolean }) {
  return (
    <span className={cn(badgeVariants({ tone }), className)} {...props}>
      {dot && <span aria-hidden="true" className={cn('size-1.5 rounded-full', DOTS[tone ?? 'neutral'])} />}
      {children}
    </span>
  )
}
