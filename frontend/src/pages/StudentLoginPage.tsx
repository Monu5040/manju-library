import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useLocation, useNavigate } from 'react-router'
import { z } from 'zod'
import { AuthCard } from '@/components/layout/AuthCard'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FieldError, Label } from '@/components/ui/label'
import { api, errorMessage } from '@/lib/api'
import { ME_QUERY_KEY, type Me } from '@/lib/auth'
import { maskMobile, mobileSchema, normalizeMobile, sixDigitCodeSchema } from '@/lib/mobile'

const RESEND_AFTER_SECONDS = 30

const mobileForm = z.object({ mobile: mobileSchema })
const codeForm = z.object({ code: sixDigitCodeSchema })

export default function StudentLoginPage() {
  const [mobile, setMobile] = useState<string | null>(null)
  // Only for numbers on the server's test list (never in production): the code is shown here.
  const [testCode, setTestCode] = useState<string | null>(null)

  return (
    <AuthCard
      title="Student login"
      description={
        mobile
          ? testCode
            ? 'This number is on the test list, so your code is shown below instead of being sent by SMS.'
            : `We sent a 6-digit code to ${maskMobile(mobile)}. It works for 5 minutes.`
          : 'Enter the mobile number you gave at admission. We will text you a login code.'
      }
    >
      {mobile === null ? (
        <MobileStep
          onSent={(number, code) => {
            setMobile(number)
            setTestCode(code)
          }}
        />
      ) : (
        <CodeStep mobile={mobile} testCode={testCode} onNewTestCode={setTestCode} onChangeNumber={() => setMobile(null)} />
      )}
    </AuthCard>
  )
}

function requestCode(mobile: string) {
  return api<{ detail: string; test_code?: string }>('/auth/otp/request/', { method: 'POST', body: { mobile } })
}

function MobileStep({ onSent }: { onSent: (mobile: string, testCode: string | null) => void }) {
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof mobileForm>>({
    resolver: zodResolver(mobileForm),
    defaultValues: { mobile: '' },
  })

  const onSubmit = handleSubmit(async ({ mobile }) => {
    setServerError(null)
    const normalized = normalizeMobile(mobile)
    try {
      const reply = await requestCode(normalized)
      onSent(normalized, reply?.test_code ?? null)
    } catch (error) {
      setServerError(errorMessage(error))
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {serverError && <Alert variant="destructive">{serverError}</Alert>}
      <div className="space-y-2">
        <Label htmlFor="mobile">Mobile number</Label>
        <Input
          id="mobile"
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          placeholder="98765 43210"
          aria-invalid={Boolean(errors.mobile)}
          aria-describedby={errors.mobile ? 'mobile-error' : undefined}
          {...register('mobile')}
        />
        <FieldError id="mobile-error" message={errors.mobile?.message} />
      </div>
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Sending…' : 'Send code'}
      </Button>
    </form>
  )
}

function CodeStep({
  mobile,
  testCode,
  onNewTestCode,
  onChangeNumber,
}: {
  mobile: string
  testCode: string | null
  onNewTestCode: (code: string | null) => void
  onChangeNumber: () => void
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [serverError, setServerError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(RESEND_AFTER_SECONDS)

  useEffect(() => {
    if (secondsLeft <= 0) {
      return
    }
    const timer = window.setTimeout(() => setSecondsLeft((value) => value - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [secondsLeft])

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof codeForm>>({
    resolver: zodResolver(codeForm),
    defaultValues: { code: '' },
  })

  const onSubmit = handleSubmit(async ({ code }) => {
    setServerError(null)
    try {
      const me = await api<Me>('/auth/otp/verify/', { method: 'POST', body: { mobile, code } })
      queryClient.setQueryData(ME_QUERY_KEY, me)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from?.startsWith('/portal') ? from : '/portal', { replace: true })
    } catch (error) {
      setServerError(errorMessage(error))
    }
  })

  async function resend() {
    setServerError(null)
    setNotice(null)
    try {
      const reply = await requestCode(mobile)
      onNewTestCode(reply?.test_code ?? null)
      setNotice(reply?.test_code ? 'Here is a new code.' : 'A new code is on its way.')
      setSecondsLeft(RESEND_AFTER_SECONDS)
    } catch (error) {
      setServerError(errorMessage(error))
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {serverError && <Alert variant="destructive">{serverError}</Alert>}
      {notice && <Alert variant="success">{notice}</Alert>}
      {testCode && (
        <Alert variant="warning" title="Test number">
          Your code is <strong className="text-base tracking-[0.2em] tabular-nums">{testCode}</strong>. Once SMS is switched on, real
          students get it by SMS instead.
        </Alert>
      )}
      <div className="space-y-2">
        <Label htmlFor="code">6-digit code</Label>
        <Input
          id="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          className="h-14 text-center text-2xl font-semibold tracking-[0.5em] tabular-nums"
          aria-invalid={Boolean(errors.code)}
          aria-describedby={errors.code ? 'code-error' : undefined}
          {...register('code')}
        />
        <FieldError id="code-error" message={errors.code?.message} />
      </div>
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Checking…' : 'Sign in'}
      </Button>
      <div className="flex items-center justify-between text-sm">
        <Button type="button" variant="link" className="px-0" onClick={onChangeNumber}>
          Change number
        </Button>
        <Button
          type="button"
          variant="link"
          className="px-0"
          onClick={resend}
          disabled={secondsLeft > 0}
        >
          {secondsLeft > 0 ? `Resend code in ${secondsLeft}s` : 'Resend code'}
        </Button>
      </div>
    </form>
  )
}
