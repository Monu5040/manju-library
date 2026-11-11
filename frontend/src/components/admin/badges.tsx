import { Badge } from '@/components/ui/badge'
import { daysLeftLabel, formatMoney } from '@/lib/format'
import type { MembershipState } from '@/lib/types'

export function StateBadge({ state, daysLeft }: { state: MembershipState; daysLeft?: number }) {
  if (state === 'CANCELLED') {
    return <Badge>Cancelled</Badge>
  }
  if (state === 'UPCOMING') {
    return <Badge tone="info">Starts later</Badge>
  }
  if (state === 'EXPIRED') {
    return <Badge tone="danger">{daysLeft !== undefined ? daysLeftLabel(daysLeft) : 'Expired'}</Badge>
  }
  const soon = daysLeft !== undefined && daysLeft <= 7
  return (
    <Badge tone={soon ? 'warning' : 'success'}>
      {daysLeft !== undefined ? daysLeftLabel(daysLeft) : 'Active'}
    </Badge>
  )
}

export function DueBadge({ amount }: { amount: number }) {
  if (amount <= 0) {
    return <Badge tone="success">Paid</Badge>
  }
  return <Badge tone="danger">Due {formatMoney(amount)}</Badge>
}
