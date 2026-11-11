import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, NOT_SIGNED_IN, overview, owner, renderApp } from '@/test/utils'


describe('Staff login', () => {
  it('connects an authenticator app on first sign-in', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': NOT_SIGNED_IN,
      'POST /api/auth/admin/login/': { body: { next: 'setup' } },
      'GET /api/auth/admin/totp/setup/': {
        body: {
          otpauth_uri: 'otpauth://totp/Manju%20Library:9123456780?secret=JBSWY3DPEHPK3PXP',
          secret: 'JBSWY3DPEHPK3PXP',
        },
      },
      'POST /api/auth/admin/totp/setup/': { body: owner },
      'GET /api/admin/overview/': { body: overview },
    })
    renderApp('/staff/login')

    await user.type(screen.getByLabelText('Email or mobile number'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('JBSW Y3DP EHPK 3PXP')).toBeInTheDocument()
    expect(screen.getByTitle('QR code for your authenticator app')).toBeInTheDocument()

    await user.type(screen.getByLabelText('6-digit app code'), '654321')
    await user.click(screen.getByRole('button', { name: 'Connect and sign in' }))

    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    expect(await screen.findByText('Active members')).toBeInTheDocument()
    expect(screen.getByText('99')).toBeInTheDocument()
    expect(calls.find((call) => call.path === '/api/auth/admin/login/')?.body).toEqual({
      identifier: 'owner@example.com',
      password: 'correct-horse-battery-staple',
    })
  })

  it('asks for the app code on later sign-ins', async () => {
    const user = userEvent.setup()
    mockApi({
      'GET /api/auth/me/': NOT_SIGNED_IN,
      'POST /api/auth/admin/login/': { body: { next: 'verify' } },
      'POST /api/auth/admin/totp/verify/': { body: owner },
      'GET /api/admin/overview/': { body: overview },
    })
    renderApp('/staff/login')

    await user.type(screen.getByLabelText('Email or mobile number'), '9123456780')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await user.type(await screen.findByLabelText('6-digit app code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
  })

  it('goes back to the password step when the sign-in has expired', async () => {
    const user = userEvent.setup()
    mockApi({
      'GET /api/auth/me/': NOT_SIGNED_IN,
      'POST /api/auth/admin/login/': { body: { next: 'verify' } },
      'POST /api/auth/admin/totp/verify/': {
        status: 403,
        body: { detail: 'Your sign-in expired. Enter your password again.' },
      },
    })
    renderApp('/staff/login')

    await user.type(screen.getByLabelText('Email or mobile number'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'pw')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await user.type(await screen.findByLabelText('6-digit app code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(
      await screen.findByText('Your sign-in expired. Enter your password again.'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })
})
