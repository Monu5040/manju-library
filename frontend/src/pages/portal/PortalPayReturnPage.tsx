import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, CircleX, Clock } from 'lucide-react'
import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { confirmOnlinePayment, fetchOnlineStatus } from '@/lib/portal'
import type { PortalOnlineStatus } from '@/lib/types'

const POLL_MS = 5000
const CHECKS = 24 // about two minutes

/**
 * Razorpay sends the student back here after paying. The server checks the payment with
 * Razorpay before recording it; this page only shows the outcome and waits if needed.
 */
export default function PortalPayReturnPage() {
  const [search] = useSearchParams()
  const params = useMemo(
    () => Object.fromEntries([...search.entries()].filter(([key]) => key.startsWith('razorpay_'))),
    [search],
  )
  const paidAtRazorpay = params.razorpay_payment_link_status === 'paid'
  const queryClient = useQueryClient()
  const [startedAt] = useState(() => Date.now())

  const confirmed = useQuery({
    queryKey: ['online-return', params.razorpay_payment_link_id],
    queryFn: () => confirmOnlinePayment(params),
    enabled: Boolean(params.razorpay_payment_link_id),
    staleTime: Infinity,
    retry: 1,
  })
  const waiting = paidAtRazorpay && confirmed.data?.status === 'PENDING'
  const polled = useQuery({
    queryKey: ['online-return', 'status', confirmed.data?.id],
    queryFn: () => fetchOnlineStatus(confirmed.data!.id, true),
    enabled: waiting,
    refetchInterval: (query) => (query.state.data?.status === 'PENDING' && query.state.dataUpdateCount < CHECKS ? POLL_MS : false),
  })
  const result: PortalOnlineStatus | undefined = polled.data ?? confirmed.data
  const done = result?.status === 'PAID'

  useEffect(() => {
    if (done) {
      // Dues, receipts and the membership have changed.
      void queryClient.invalidateQueries({ queryKey: ['portal'] })
    }
  }, [done, queryClient])

  if (!params.razorpay_payment_link_id) {
    return <Outcome tone="neutral" title="Nothing to show here" body="Payments you make online show up under Payments." />
  }
  if (confirmed.isPending) {
    return <Spinner label="Checking your payment with Razorpay" />
  }
  if (confirmed.error) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">{errorMessage(confirmed.error)}</Alert>
        <p className="text-sm text-muted-foreground">
          If money left your account, it will show under Payments within a few minutes. Please do not pay twice.
        </p>
        <HomeButton />
      </div>
    )
  }
  if (result && done) {
    return (
      <Outcome
        tone="success"
        title="Payment received"
        body={
          <>
            <span className="block text-3xl font-semibold text-foreground tabular-nums">{formatMoney(result.amount)}</span>
            {result.receipt_no && <span className="mt-1 block">Receipt #{result.receipt_no}</span>}
            {result.renewal_end && (
              <span className="mt-3 block text-foreground">Your membership now runs until {formatDate(result.renewal_end)}.</span>
            )}
          </>
        }
      >
        {result.needs_desk && (
          <Alert className="text-left">
            We have your payment. The front desk needs to confirm one detail, so please ask them on your next visit.
          </Alert>
        )}
        <div className="flex flex-wrap justify-center gap-2">
          {result.receipt && (
            <Button asChild>
              <Link to={`/portal/receipts/${result.receipt}`}>View receipt</Link>
            </Button>
          )}
          <HomeButton variant="outline" />
        </div>
      </Outcome>
    )
  }
  if (result?.status === 'FLAGGED') {
    return (
      <Outcome
        tone="waiting"
        title="We have your payment"
        body="The front desk needs to check one detail before it shows here. You do not need to pay again; please ask them on your next visit."
      >
        <HomeButton variant="outline" />
      </Outcome>
    )
  }
  if (waiting || (paidAtRazorpay && result?.status === 'PENDING')) {
    // Polling stops after about two minutes; then say so plainly instead of spinning on.
    const gaveUp = polled.data?.status === 'PENDING' && polled.dataUpdatedAt - startedAt >= (CHECKS - 1) * POLL_MS
    return (
      <Outcome
        tone="waiting"
        title={gaveUp ? 'Your payment is on its way' : 'Confirming your payment…'}
        body={
          gaveUp
            ? 'Razorpay has your payment; it will show under Payments within a few minutes. You do not need to pay again.'
            : 'This usually takes a few seconds. Please keep this page open.'
        }
      >
        <HomeButton variant="outline" />
      </Outcome>
    )
  }
  return (
    <Outcome tone="failed" title="Payment not completed" body="No money was taken. You can try again, or pay at the front desk.">
      <HomeButton />
    </Outcome>
  )
}

function HomeButton({ variant = 'default' }: { variant?: 'default' | 'outline' }) {
  return (
    <Button asChild variant={variant}>
      <Link to="/portal">Back to home</Link>
    </Button>
  )
}

const TONES = {
  success: { icon: CircleCheck, ring: 'bg-success/10 text-success' },
  waiting: { icon: Clock, ring: 'bg-accent/20 text-accent-foreground' },
  failed: { icon: CircleX, ring: 'bg-destructive/10 text-destructive' },
  neutral: { icon: Clock, ring: 'bg-muted text-muted-foreground' },
} as const

function Outcome({
  tone,
  title,
  body,
  children,
}: {
  tone: keyof typeof TONES
  title: string
  body: ReactNode
  children?: ReactNode
}) {
  const { icon: Icon, ring } = TONES[tone]
  return (
    <Card className="mx-auto max-w-md animate-rise-in p-8 text-center">
      <span className={`mx-auto mb-5 grid size-16 place-items-center rounded-full ${ring}`}>
        <Icon aria-hidden="true" className="size-8" />
      </span>
      <h1 className="font-display text-2xl font-semibold">{title}</h1>
      <div className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{body}</div>
      {children && <div className="mt-6 space-y-4">{children}</div>}
    </Card>
  )
}
