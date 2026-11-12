import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { LoaderCircle } from 'lucide-react'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  [
    'relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold select-none',
    'transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out active:scale-[0.98]',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
    'disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0',
  ],
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground shadow-[inset_0_1px_0_oklch(1_0_0/0.14),0_1px_2px_oklch(0.2_0.03_165/0.25)] hover:bg-primary/90',
        accent:
          'bg-accent text-accent-foreground shadow-[inset_0_1px_0_oklch(1_0_0/0.3),0_1px_2px_oklch(0.4_0.08_70/0.3)] hover:bg-accent/90',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/75',
        outline:
          'border border-input bg-card text-foreground shadow-[0_1px_1px_oklch(0.2_0.03_165/0.04)] hover:border-foreground/25 hover:bg-muted',
        ghost: 'text-foreground hover:bg-muted',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        link: 'h-auto px-0 text-primary underline-offset-4 hover:underline active:scale-100',
      },
      size: {
        default: 'h-10 px-4',
        sm: 'h-9 px-3 text-[13px]',
        lg: 'h-12 rounded-xl px-6 text-base',
        icon: 'size-10',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

type ButtonProps = ComponentProps<'button'> &
  VariantProps<typeof buttonVariants> & {
    /** Render the child element (for example a router Link) with button styles. */
    asChild?: boolean
    /** Shows a spinner and blocks clicks while something is being saved. */
    loading?: boolean
  }

export function Button({ className, variant, size, asChild = false, loading = false, disabled, children, ...props }: ButtonProps) {
  const Component = asChild ? Slot : 'button'
  return (
    <Component
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={asChild ? undefined : disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && !asChild ? (
        <>
          <LoaderCircle aria-hidden="true" className="animate-spin" />
          {children}
        </>
      ) : (
        children
      )}
    </Component>
  )
}
