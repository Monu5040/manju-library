import { cva, type VariantProps } from 'class-variance-authority'
import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

const alertVariants = cva('flex gap-3 rounded-xl border px-4 py-3 text-sm leading-relaxed', {
  variants: {
    variant: {
      info: 'border-border bg-muted/70 text-foreground',
      success: 'border-success/30 bg-success/10 text-foreground',
      warning: 'border-warning/45 bg-warning/10 text-foreground',
      destructive: 'border-destructive/30 bg-destructive/[0.07] text-destructive',
    },
  },
  defaultVariants: { variant: 'info' },
})

const ICONS = { info: Info, success: CircleCheck, warning: TriangleAlert, destructive: CircleAlert }
const ICON_COLOURS = { info: 'text-primary', success: 'text-success', warning: 'text-warning', destructive: 'text-destructive' }

export function Alert({
  className,
  variant,
  title,
  children,
  ...props
}: ComponentProps<'div'> & VariantProps<typeof alertVariants> & { title?: ReactNode }) {
  const kind = variant ?? 'info'
  const Icon = ICONS[kind]
  return (
    <div role={kind === 'destructive' ? 'alert' : 'status'} className={cn(alertVariants({ variant }), className)} {...props}>
      <Icon aria-hidden="true" className={cn('mt-0.5 size-[18px] shrink-0', ICON_COLOURS[kind])} />
      <div className="min-w-0 flex-1">
        {title && <p className="mb-0.5 font-semibold">{title}</p>}
        {children}
      </div>
    </div>
  )
}
