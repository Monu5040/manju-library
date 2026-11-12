import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { z } from 'zod'
import { AuthCard } from '@/components/layout/AuthCard'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FieldError, Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { api, ApiError, errorMessage } from '@/lib/api'
import { ME_QUERY_KEY, type Me } from '@/lib/auth'
import { sixDigitCodeSchema } from '@/lib/mobile'

type Step = 'password' | 'setup' | 'verify'

const STEP_TEXT: Record<Step, { title: string; description: string }> = {
  password: {
    title: 'Staff login',
    description: 'For the library owner and front-desk staff.',
  },
  setup: {
    title: 'Connect an authenticator app',
    description:
      'First sign-in only. Scan the QR code with Google Authenticator, Microsoft Authenticator or a similar app, then enter the 6-digit code it shows.',
  },
  verify: {
    title: 'Enter your app code',
    description: 'Open your authenticator app and enter the current 6-digit code for Manju Library.',
  },
}

export default function StaffLoginPage() {
  const [step, setStep] = useState<Step>('password')
  const [notice, setNotice] = useState<string | null>(null)

  function restart(message: string) {
    setNotice(message)
    setStep('password')
  }

  return (
    <AuthCard variant="staff" title={STEP_TEXT[step].title} description={STEP_TEXT[step].description}>
      {step === 'password' && <PasswordStep notice={notice} onNext={setStep} />}
      {step === 'setup' && <SetupStep onExpired={restart} />}
      {step === 'verify' && <AppCodeStep endpoint="/auth/admin/totp/verify/" onExpired={restart} />}
    </AuthCard>
  )
}

const passwordForm = z.object({
  identifier: z.string().trim().min(3, { error: 'Enter your email or mobile number.' }),
  password: z.string().min(1, { error: 'Enter your password.' }),
})

function PasswordStep({
  notice,
  onNext,
}: {
  notice: string | null
  onNext: (step: 'setup' | 'verify') => void
}) {
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof passwordForm>>({
    resolver: zodResolver(passwordForm),
    defaultValues: { identifier: '', password: '' },
  })

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    try {
      const result = await api<{ next: 'setup' | 'verify' }>('/auth/admin/login/', {
        method: 'POST',
        body: values,
      })
      onNext(result.next)
    } catch (error) {
      setServerError(errorMessage(error))
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {notice && !serverError && <Alert>{notice}</Alert>}
      {serverError && <Alert variant="destructive">{serverError}</Alert>}
      <div className="space-y-2">
        <Label htmlFor="identifier">Email or mobile number</Label>
        <Input
          id="identifier"
          autoComplete="username"
          aria-invalid={Boolean(errors.identifier)}
          aria-describedby={errors.identifier ? 'identifier-error' : undefined}
          {...register('identifier')}
        />
        <FieldError id="identifier-error" message={errors.identifier?.message} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? 'password-error' : undefined}
          {...register('password')}
        />
        <FieldError id="password-error" message={errors.password?.message} />
      </div>
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Checking…' : 'Continue'}
      </Button>
    </form>
  )
}

interface TotpSetup {
  otpauth_uri: string
  secret: string
}

function SetupStep({ onExpired }: { onExpired: (message: string) => void }) {
  const setup = useQuery({
    queryKey: ['auth', 'totp-setup'],
    queryFn: () => api<TotpSetup>('/auth/admin/totp/setup/'),
    retry: false,
    gcTime: 0,
    staleTime: Number.POSITIVE_INFINITY,
  })

  useEffect(() => {
    if (setup.error instanceof ApiError && setup.error.status === 403) {
      onExpired(errorMessage(setup.error))
    }
  }, [setup.error, onExpired])

  if (setup.isPending) {
    return <Spinner label="Preparing your QR code" />
  }
  if (setup.error) {
    return <Alert variant="destructive">{errorMessage(setup.error)}</Alert>
  }

  const groupedSecret = setup.data.secret.match(/.{1,4}/g)?.join(' ') ?? setup.data.secret
  return (
    <div className="space-y-6">
      <div className="flex flex-col items-center gap-3">
        <div className="rounded-lg bg-white p-3">
          <QRCodeSVG
            value={setup.data.otpauth_uri}
            size={176}
            title="QR code for your authenticator app"
          />
        </div>
        <p className="text-center text-sm text-muted-foreground">
          Can't scan it? Add this key by hand:
          <br />
          <code className="font-mono text-foreground">{groupedSecret}</code>
        </p>
      </div>
      <AppCodeStep
        endpoint="/auth/admin/totp/setup/"
        onExpired={onExpired}
        submitLabel="Connect and sign in"
      />
    </div>
  )
}

const appCodeForm = z.object({ token: sixDigitCodeSchema })

function AppCodeStep({
  endpoint,
  onExpired,
  submitLabel = 'Sign in',
}: {
  endpoint: string
  onExpired: (message: string) => void
  submitLabel?: string
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof appCodeForm>>({
    resolver: zodResolver(appCodeForm),
    defaultValues: { token: '' },
  })

  const onSubmit = handleSubmit(async ({ token }) => {
    setServerError(null)
    try {
      const me = await api<Me>(endpoint, { method: 'POST', body: { token } })
      queryClient.setQueryData(ME_QUERY_KEY, me)
      navigate('/admin', { replace: true })
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        onExpired(errorMessage(error))
        return
      }
      setServerError(errorMessage(error))
    }
  })

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {serverError && <Alert variant="destructive">{serverError}</Alert>}
      <div className="space-y-2">
        <Label htmlFor="token">6-digit app code</Label>
        <Input
          id="token"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          className="h-14 text-center text-2xl font-semibold tracking-[0.5em] tabular-nums"
          aria-invalid={Boolean(errors.token)}
          aria-describedby={errors.token ? 'token-error' : undefined}
          {...register('token')}
        />
        <FieldError id="token-error" message={errors.token?.message} />
      </div>
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Checking…' : submitLabel}
      </Button>
    </form>
  )
}
