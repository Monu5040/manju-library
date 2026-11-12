import { cn } from '@/lib/utils'

/** Shared look of text fields, selects and text areas. */
export const fieldClass = cn(
  'w-full rounded-lg border border-input bg-card px-3 text-base text-foreground shadow-[inset_0_1px_1px_oklch(0.2_0.03_165/0.04)] sm:text-sm',
  'placeholder:text-muted-foreground/80 transition-[border-color,box-shadow] duration-150',
  'hover:border-foreground/25 focus-visible:border-primary focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/15',
  'disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-70',
  'aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive/15',
)
