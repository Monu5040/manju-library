import type { PortalStudent } from '@/lib/types'
import { cn } from '@/lib/utils'

/** For a login shared by siblings: pick whose details to show. Hidden for one profile. */
export function ProfileSwitcher({
  profiles,
  selectedId,
  onSelect,
}: {
  profiles: PortalStudent[]
  selectedId: number | undefined
  onSelect: (id: number) => void
}) {
  if (profiles.length < 2) {
    return null
  }
  return (
    <div role="tablist" aria-label="Student" className="mb-6 flex gap-2 overflow-x-auto">
      {profiles.map((p) => (
        <button
          key={p.id}
          type="button"
          role="tab"
          aria-selected={p.id === selectedId}
          onClick={() => onSelect(p.id)}
          className={cn(
            'rounded-full border px-4 py-2 text-sm font-medium whitespace-nowrap',
            p.id === selectedId ? 'border-primary bg-primary text-primary-foreground' : 'bg-card hover:bg-muted',
          )}
        >
          {p.full_name}
        </button>
      ))}
    </div>
  )
}
