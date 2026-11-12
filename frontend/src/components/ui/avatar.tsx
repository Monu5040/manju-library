import { cn } from '@/lib/utils'

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
}

/** A person's initials in a circle. Decorative: the name is always written next to it. */
export function Avatar({ name, tone = 'accent', className }: { name: string; tone?: 'accent' | 'soft'; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'grid size-9 shrink-0 place-items-center rounded-full text-[13px] font-bold',
        tone === 'accent' ? 'bg-accent text-accent-foreground' : 'bg-secondary text-secondary-foreground',
        className,
      )}
    >
      {initials(name)}
    </span>
  )
}
