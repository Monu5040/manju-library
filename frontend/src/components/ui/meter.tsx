import { cn } from '@/lib/utils'

/**
 * A thin bar for one share of a whole (seats in use, time left). Decorative: the number it
 * shows is always written next to it, so screen readers skip it.
 */
export function Meter({ percent, tone = 'primary', className }: { percent: number; tone?: 'primary' | 'warning' | 'accent'; className?: string }) {
  const width = Math.max(0, Math.min(100, percent))
  return (
    <div aria-hidden="true" className={cn('h-1.5 overflow-hidden rounded-full bg-muted', className)}>
      <div
        className={cn(
          'h-full rounded-full transition-[width] duration-500 ease-out',
          tone === 'primary' && 'bg-primary',
          tone === 'warning' && 'bg-warning',
          tone === 'accent' && 'bg-accent',
        )}
        style={{ width: `${width}%` }}
      />
    </div>
  )
}
