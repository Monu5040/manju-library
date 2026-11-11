import type { SlotState } from '@/lib/types'

/** How a seat in a shift is shown: free, partly booked (a custom time) or taken. */
export const SLOT_COLORS: Record<SlotState, string> = {
  free: 'var(--chart-empty)',
  partly: 'var(--chart-step-1)',
  taken: 'var(--chart-step-3)',
}

export const SLOT_LABELS: Record<SlotState, string> = {
  free: 'Free',
  partly: 'Partly booked',
  taken: 'Taken',
}
