import { X } from 'lucide-react'
import { type ReactNode, useEffect, useId, useRef } from 'react'
import { cn } from '@/lib/utils'

/**
 * A modal dialog: overlay, Escape and the close button dismiss it, focus moves into it
 * on open and returns to the opener on close.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean
  onClose: () => void
  title: string
  description?: ReactNode
  children: ReactNode
  wide?: boolean
}) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      return
    }
    const opener = document.activeElement as HTMLElement | null
    const first = panel.current?.querySelector<HTMLElement>('input, select, textarea, button:not([data-close])')
    ;(first ?? panel.current)?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      opener?.focus?.()
    }
  }, [open, onClose])

  if (!open) {
    return null
  }
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0" aria-hidden="true" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          'relative max-h-[92dvh] w-full overflow-y-auto rounded-t-xl border bg-card p-6 shadow-lg sm:rounded-xl',
          wide ? 'sm:max-w-2xl' : 'sm:max-w-md',
        )}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
          </div>
          <button
            type="button"
            data-close
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
