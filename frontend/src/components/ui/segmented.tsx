import { cn } from '@/lib/utils'

export interface SegmentOption<T extends string> {
  value: T
  label: string
  /** Extra detail shown on hover, for example a shift's hours. */
  title?: string
}

/**
 * A row of pressed/unpressed buttons for switching what a list shows (one is always on).
 * Scrolls sideways on narrow screens instead of wrapping.
 */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: {
  /** What the choice is about, for screen readers ("Show seats for"). */
  label: string
  options: SegmentOption<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('flex max-w-full gap-1 overflow-x-auto rounded-xl border bg-card p-1 shadow-card sm:w-fit', className)}
    >
      {options.map((option) => {
        const pressed = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={pressed}
            title={option.title}
            onClick={() => onChange(option.value)}
            className={cn(
              'shrink-0 rounded-lg px-3.5 py-1.5 text-sm font-semibold whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
              pressed ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
