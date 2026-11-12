import { ArrowRight, Armchair, BellRing, Clock, ReceiptText } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const FEATURES = [
  { icon: Armchair, title: 'A seat that is yours', text: 'Reserved for your shift, so you can settle in and start straight away.' },
  { icon: Clock, title: 'Shifts that fit your day', text: 'From early morning to late night, on plans from one month to a year.' },
  { icon: ReceiptText, title: 'Fees and receipts, clearly', text: 'See what you paid, what is due and print any receipt from your phone.' },
  { icon: BellRing, title: 'A reminder before it ends', text: 'Hear from us before your plan runs out, so your seat stays yours.' },
]

const STEPS = [
  { title: 'Join at the front desk', text: 'Choose your shift and seat, and pay in cash or by UPI.' },
  { title: 'Sign in with your mobile', text: 'No password: we text a 6-digit code to the number you gave.' },
  { title: 'Everything in one place', text: 'Your seat, days left, dues, receipts and the library’s notices.' },
]

// A small picture of the reading room: taken seats, free seats and yours, ringed in brass.
const SEATS = Array.from({ length: 24 }, (_, i) => i + 1)
const TAKEN = new Set([1, 2, 4, 5, 6, 8, 9, 11, 13, 14, 15, 17, 19, 20, 22, 23])
const YOURS = 12

function SeatPicture() {
  return (
    <div aria-hidden="true" className="relative mx-auto w-full max-w-md">
      <div className="absolute -inset-10 rounded-[3rem] bg-[radial-gradient(closest-side,oklch(0.8_0.13_82/0.22),transparent)]" />
      <div className="relative rounded-3xl border bg-card p-6 shadow-float">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.1em] text-muted-foreground uppercase">Day shift</p>
            <p className="font-display text-xl font-semibold">Reading room</p>
          </div>
          <span className="rounded-full bg-secondary px-3 py-1 text-xs font-semibold text-secondary-foreground">16 of 24 taken</span>
        </div>
        <div className="grid grid-cols-6 gap-2.5">
          {SEATS.map((n) => (
            <div
              key={n}
              className={cn(
                'grid aspect-square place-items-center rounded-lg text-[11px] font-semibold',
                n === YOURS
                  ? 'bg-primary text-primary-foreground ring-4 ring-accent/60'
                  : TAKEN.has(n)
                    ? 'bg-primary/15 text-primary'
                    : 'border border-dashed border-input text-muted-foreground',
              )}
            >
              {n}
            </div>
          ))}
        </div>
      </div>
      <div className="absolute -right-3 -bottom-8 w-52 rounded-2xl border bg-card p-4 shadow-float sm:-right-8">
        <p className="text-xs text-muted-foreground">Your seat · 12</p>
        <p className="mt-0.5 text-lg font-semibold">12 days left</p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div className="h-full w-2/5 rounded-full bg-primary" />
        </div>
      </div>
    </div>
  )
}

export default function HomePage() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-16 px-5 pt-14 pb-24 sm:pt-20 lg:grid-cols-[1.05fr_1fr] lg:pt-24 lg:pb-32">
          <div className="animate-rise-in">
            <p className="mb-5 inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground shadow-card">
              <span className="size-1.5 rounded-full bg-accent" /> Study library · open early to late
            </p>
            <h1 className="font-display text-[2.75rem] leading-[1.05] font-semibold tracking-[-0.02em] sm:text-6xl">
              A quiet place to study, every day
            </h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted-foreground">
              Reserved seats, flexible shifts from early morning to late night, and plans from one month to a year.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link to="/login">
                  Student login <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/staff/login">Staff login</Link>
              </Button>
            </div>
          </div>
          <SeatPicture />
        </div>
      </section>

      <section aria-labelledby="features" className="border-y bg-card/60">
        <div className="mx-auto w-full max-w-6xl px-5 py-20">
          <h2 id="features" className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            Made for long hours of focus
          </h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-2xl border bg-card p-6 shadow-card">
                <span className="grid size-11 place-items-center rounded-xl bg-secondary text-secondary-foreground">
                  <Icon aria-hidden="true" className="size-5" />
                </span>
                <h3 className="mt-5 font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="how" className="mx-auto w-full max-w-6xl px-5 py-20">
        <h2 id="how" className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
          How it works
        </h2>
        <ol className="mt-10 grid gap-8 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative">
              <span className="font-display text-5xl font-semibold text-accent-ink">{index + 1}</span>
              <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
              <p className="mt-1.5 leading-relaxed text-muted-foreground">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mx-auto w-full max-w-6xl px-5 pb-24">
        <div className="relative overflow-hidden rounded-3xl bg-sidebar px-8 py-12 text-sidebar-foreground sm:px-12">
          <div aria-hidden="true" className="absolute -top-24 -right-16 size-80 rounded-full bg-[radial-gradient(closest-side,oklch(0.8_0.13_82/0.3),transparent)]" />
          <div className="relative flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
            <div>
              <h2 className="font-display text-3xl font-semibold tracking-tight">Already a member?</h2>
              <p className="mt-2 text-sidebar-foreground/80">See your seat, days left and receipts in a minute.</p>
            </div>
            <Button asChild size="lg" variant="accent">
              <Link to="/login">
                Open my portal <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </>
  )
}
