import { Printer } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { errorMessage } from '@/lib/api'
import { formatDate, formatMoney } from '@/lib/format'
import { usePortalReceipt } from '@/lib/portal'

export default function PortalReceiptPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const receipt = usePortalReceipt(id)

  if (receipt.isPending) return <Spinner label="Loading receipt" />
  if (receipt.error) return <Alert variant="destructive">{errorMessage(receipt.error)}</Alert>
  const r = receipt.data

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
      <article className="rounded-xl border bg-card p-8 print:border-0 print:p-0" aria-label={`Receipt ${r.receipt_no}`}>
        <header className="border-b pb-4 text-center">
          <h1 className="text-xl font-semibold">{r.library.name}</h1>
          {r.library.address && <p className="text-sm text-muted-foreground">{r.library.address}</p>}
          <p className="mt-3 text-sm font-medium tracking-wide uppercase">Fee receipt</p>
        </header>
        <dl className="grid grid-cols-2 gap-y-2 py-4 text-sm">
          <dt className="text-muted-foreground">Receipt no.</dt>
          <dd className="text-right font-medium tabular-nums">{r.receipt_no}</dd>
          <dt className="text-muted-foreground">Date</dt>
          <dd className="text-right">{formatDate(r.paid_on)}</dd>
          <dt className="text-muted-foreground">Student</dt>
          <dd className="text-right">{r.student_name}</dd>
          <dt className="text-muted-foreground">Roll no.</dt>
          <dd className="text-right tabular-nums">{r.roll_no}</dd>
          <dt className="text-muted-foreground">Paid by</dt>
          <dd className="text-right">
            {r.mode_label}
            {r.reference && ` · ${r.reference}`}
          </dd>
        </dl>
        <div className="flex items-center justify-between border-t pt-4">
          <span className="font-medium">Amount received</span>
          <span className="text-2xl font-semibold tabular-nums">{formatMoney(r.amount)}</span>
        </div>
        {r.is_void && (
          <p className="mt-4 rounded-md border border-destructive/40 p-2 text-center text-sm font-medium text-destructive">
            This payment was cancelled.
          </p>
        )}
        <footer className="mt-8 text-center text-xs text-muted-foreground">Computer-generated receipt</footer>
      </article>
    </div>
  )
}
