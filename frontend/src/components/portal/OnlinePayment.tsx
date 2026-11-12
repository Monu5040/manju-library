import { CalendarDays, Lock } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { alreadyPaid, useStartOnlinePayment } from '@/lib/portal'
import type { PortalOnline } from '@/lib/types'
import { cn } from '@/lib/utils'

/** The small print under every online-payment button. */
export function SecureNote({ testMode }: { testMode: boolean }) {
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1">
        <Lock aria-hidden="true" className="size-3.5" /> UPI, cards or net banking on Razorpay's secure page
      </span>
      {testMode && <Badge tone="warning">Test mode: no real money</Badge>}
    </p>
  )
}

/** Either "it was already paid" (good news) or the error itself. */
function StartProblem({ error }: { error: unknown }) {
  const paid = alreadyPaid(error)
  if (paid) {
    return (
      <Alert variant="success">
        Your earlier payment for this went through, so there is nothing more to pay.{' '}
        {paid.receipt && (
          <Link className="font-medium underline" to={`/portal/receipts/${paid.receipt}`}>
            See receipt #{paid.receipt_no}
          </Link>
        )}
      </Alert>
    )
  }
  return <Alert variant="destructive">{errorMessage(error)}</Alert>
}

/** "Pay ₹150 online" for a membership with money still due. */
export function PayDuesButton({
  studentId,
  due,
  testMode,
  label,
}: {
  studentId: number
  due: PortalOnline['dues'][number]
  testMode: boolean
  label?: string
}) {
  const start = useStartOnlinePayment(studentId)
  return (
    <div className="space-y-2">
      {start.error && <StartProblem error={start.error} />}
      <Button
        className="w-full sm:w-auto"
        loading={start.isPending || start.isSuccess}
        onClick={() => start.mutate({ purpose: 'DUES', membership: due.membership })}
      >
        {label ?? `Pay ${formatMoney(due.amount)} online`}
      </Button>
      <SecureNote testMode={testMode} />
    </div>
  )
}

/** Choose how long to renew for, then pay on Razorpay's page. Same seat and timing. */
export function RenewOnlineDialog({
  studentId,
  renewal,
  testMode,
  onClose,
}: {
  studentId: number
  renewal: NonNullable<PortalOnline['renewal']>
  testMode: boolean
  onClose: () => void
}) {
  const choices = renewal.options
  const first = choices.find((o) => !o.unavailable)
  const [planId, setPlanId] = useState<number | undefined>(first?.plan)
  const chosen = choices.find((o) => o.plan === planId)
  const start = useStartOnlinePayment(studentId)
  const where = [renewal.seat_number && `seat ${renewal.seat_number}`, renewal.shift_name ?? renewal.time_label].filter(Boolean).join(', ')

  return (
    <Dialog open onClose={onClose} title="Renew your membership" description={`Same ${where}. Pick how long:`}>
      <fieldset className="space-y-2.5">
        <legend className="sr-only">How long to renew for</legend>
        {choices.map((option) => {
          const disabled = Boolean(option.unavailable)
          const selected = option.plan === planId
          return (
            <label
              key={option.plan}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors',
                selected ? 'border-primary bg-secondary/60 ring-1 ring-primary' : 'hover:bg-muted/60',
                disabled && 'cursor-not-allowed opacity-60',
              )}
            >
              <input
                type="radio"
                name="plan"
                className="mt-1 size-4 accent-primary"
                value={option.plan}
                checked={selected}
                disabled={disabled}
                onChange={() => setPlanId(option.plan)}
              />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="font-semibold">{option.plan_name}</span>
                  <span className="text-lg font-semibold tabular-nums">{formatMoney(option.amount)}</span>
                </span>
                <span className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                  <CalendarDays aria-hidden="true" className="size-3.5" />
                  {formatDate(option.start_date)} – {formatDate(option.end_date)}
                </span>
                {option.discount > 0 && (
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {formatMoney(option.price)} less your {formatMoney(option.discount)} discount
                  </span>
                )}
                {option.unavailable && <span className="mt-1 block text-sm text-destructive">{option.unavailable}</span>}
              </span>
            </label>
          )
        })}
      </fieldset>

      {start.error && (
        <div className="mt-4">
          <StartProblem error={start.error} />
        </div>
      )}
      <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <SecureNote testMode={testMode} />
        <div className="flex gap-2">
          <Button variant="ghost" onClick={onClose}>
            Not now
          </Button>
          <Button
            disabled={!chosen || Boolean(chosen.unavailable)}
            loading={start.isPending || start.isSuccess}
            onClick={() => chosen && start.mutate({ purpose: 'RENEWAL', membership: renewal.membership, plan: chosen.plan })}
          >
            {chosen ? `Pay ${formatMoney(chosen.amount)}` : 'Pay'}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
