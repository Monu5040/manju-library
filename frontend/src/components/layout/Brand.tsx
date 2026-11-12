import { LampDesk } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'

/** The reading-lamp mark and the name. `onDark` for the green sidebar. */
export function Brand({ to = '/', onDark = false, className }: { to?: string; onDark?: boolean; className?: string }) {
  return (
    <Link
      to={to}
      className={cn(
        'inline-flex items-center gap-2.5 rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
        className,
      )}
    >
      <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-[linear-gradient(145deg,oklch(0.5_0.09_162),oklch(0.32_0.065_164))] text-accent shadow-[inset_0_1px_0_oklch(1_0_0/0.2),0_2px_8px_-2px_oklch(0.2_0.05_165/0.5)]">
        <LampDesk aria-hidden="true" className="size-[18px]" />
      </span>
      <span className={cn('font-display text-[1.15rem] leading-none font-semibold tracking-tight', onDark ? 'text-sidebar-foreground' : 'text-foreground')}>
        Manju Library
      </span>
    </Link>
  )
}
