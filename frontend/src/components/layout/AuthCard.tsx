import { BellRing, CircleCheck, KeyRound, LampDesk, ReceiptText, ShieldCheck, Smartphone } from 'lucide-react'
import type { ReactNode } from 'react'
import { Brand } from './Brand'

const CURRENT_YEAR = new Date().getFullYear()

const POINTS = {
  student: [
    { icon: LampDesk, text: 'Your seat and shift, and how many days are left' },
    { icon: ReceiptText, text: 'Every payment with a receipt you can print' },
    { icon: Smartphone, text: 'No password to remember: a code comes to your mobile' },
  ],
  staff: [
    { icon: CircleCheck, text: 'Admissions, renewals and receipts in seconds' },
    { icon: BellRing, text: 'Reminders ready to send on WhatsApp' },
    { icon: ShieldCheck, text: 'Protected by a password and an authenticator app' },
  ],
}

/**
 * The sign-in pages: the library on one side (wide screens only), a focused form on the
 * other. Keeps the old name so the pages using it did not change.
 */
export function AuthCard({
  title,
  description,
  children,
  variant = 'student',
}: {
  title: string
  description: ReactNode
  children: ReactNode
  variant?: 'student' | 'staff'
}) {
  return (
    <div className="grid min-h-dvh bg-background lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="relative hidden overflow-hidden bg-sidebar p-12 text-sidebar-foreground lg:flex lg:flex-col lg:justify-between">
        {/* The reading lamp's light. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 -left-24 size-[38rem] rounded-full bg-[radial-gradient(closest-side,oklch(0.8_0.13_82/0.28),transparent)]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-0 bottom-0 left-0 h-48 bg-[linear-gradient(to_top,oklch(0.2_0.03_165/0.6),transparent)]"
        />
        <Brand to="/" onDark className="relative" />
        <div className="relative max-w-md">
          <p className="font-display text-[2.6rem] leading-[1.1] font-semibold tracking-tight">A quiet place to study, every day.</p>
          <ul className="mt-9 space-y-4">
            {POINTS[variant].map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-[15px] text-sidebar-foreground/85">
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-sidebar-hover text-accent">
                  <Icon aria-hidden="true" className="size-[18px]" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative flex items-center gap-2 text-sm text-sidebar-muted">
          <KeyRound aria-hidden="true" className="size-4" /> © {CURRENT_YEAR} Manju Library
        </p>
      </aside>
      <div className="flex min-h-dvh flex-col">
        <header className="flex h-16 items-center px-5 lg:hidden">
          <Brand to="/" />
        </header>
        <main className="flex flex-1 items-center justify-center px-5 pt-4 pb-16 sm:px-8">
          <div className="w-full max-w-sm animate-rise-in">
            <h1 className="font-display text-[2rem] leading-tight font-semibold tracking-tight">{title}</h1>
            <div className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{description}</div>
            <div className="mt-8">{children}</div>
          </div>
        </main>
      </div>
    </div>
  )
}
