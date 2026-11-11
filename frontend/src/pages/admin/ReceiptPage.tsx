import { Printer } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { useBranch, usePayment } from '@/lib/queries'

/** A printable receipt. The browser's print dialog can also save it as a PDF. */
export default function ReceiptPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const payment = usePayment(id)
  const branch = useBranch()

  if (payment.isPending) return <Spinner label="Loading receipt" />
  if (payment.error) return <Alert variant="destructive">{errorMessage(payment.error)}</Alert>
  const p = payment.data

  return (
    <div className="mx-auto max-w-md">
      <div className="mb-4 flex justify-between gap-2 print:hidden">
        <Button variant="outline" onClick={() => navigate(-1)}>
          Back
        </Button>
        <Button onClick={() => window.print()}>
          <Printer aria-hidden="true" /> Print or save as PDF
        </Button>
      </div>
      <article className="rounded-xl border bg-card p-8 text-card-foreground print:border-0 print:p-0" aria-label={`Receipt ${p.receipt_no}`}>
        <header className="border-b pb-4 text-center">
          <h1 className="text-xl font-semibold">{branch.data?.name ?? 'Manju Library'}</h1>
          {branch.data?.address && <p className="text-sm text-muted-foreground">{branch.data.address}</p>}
          {branch.data?.phone && <p className="text-sm text-muted-foreground">{branch.data.phone}</p>}
          <p className="mt-3 text-sm font-medium tracking-wide uppercase">Fee receipt</p>
        </header>
        <dl className="grid grid-cols-2 gap-y-2 py-4 text-sm">
          <dt className="text-muted-foreground">Receipt no.</dt>
          <dd className="text-right font-medium tabular-nums">{p.receipt_no}</dd>
          <dt className="text-muted-foreground">Date</dt>
          <dd className="text-right">{formatDate(p.paid_on)}</dd>
          <dt className="text-muted-foreground">Student</dt>
          <dd className="text-right">{p.student_name}</dd>
          <dt className="text-muted-foreground">Roll no.</dt>
          <dd className="text-right tabular-nums">{p.roll_no}</dd>
          <dt className="text-muted-foreground">Paid by</dt>
          <dd className="text-right">
            {p.mode_label}
            {p.reference && ` · ${p.reference}`}
          </dd>
        </dl>
        <div className="flex items-center justify-between border-t pt-4">
          <span className="font-medium">Amount received</span>
          <span className="text-2xl font-semibold tabular-nums">{formatMoney(p.amount)}</span>
        </div>
        {p.is_void && (
          <p className="mt-4 rounded-md border border-destructive/40 p-2 text-center text-sm font-medium text-destructive">
            VOID — {p.void_reason}
          </p>
        )}
        <footer className="mt-8 text-center text-xs text-muted-foreground">
          Received by {p.collected_by_name ?? 'the library'} · computer-generated receipt
        </footer>
      </article>
    </div>
  )
}
