import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, NOT_SIGNED_IN, renderApp, student } from '@/test/utils'

describe('Student login', () => {
  it('signs a student in with a mobile number and SMS code', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': NOT_SIGNED_IN,
      'POST /api/auth/otp/request/': { status: 202, body: { detail: 'sent' } },
      'POST /api/auth/otp/verify/': { body: student },
    })
    renderApp('/login')

    await user.type(screen.getByLabelText('Mobile number'), '+91 98765 43210')
    await user.click(screen.getByRole('button', { name: 'Send code' }))

    expect(await screen.findByText(/We sent a 6-digit code to 98XXXXXX10/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('6-digit code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Hello, Asha' })).toBeInTheDocument()
    const request = calls.find((call) => call.path === '/api/auth/otp/request/')
    expect(request?.body).toEqual({ mobile: '9876543210' })
    expect(request?.headers['X-CSRFToken']).toBe('test-csrf-token')
    expect(calls.find((call) => call.path === '/api/auth/otp/verify/')?.body).toEqual({
      mobile: '9876543210',
      code: '123456',
    })
  })

  it('checks the mobile number before calling the server', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({ 'GET /api/auth/me/': NOT_SIGNED_IN })
    renderApp('/login')

    await user.type(screen.getByLabelText('Mobile number'), '12345')
    await user.click(screen.getByRole('button', { name: 'Send code' }))

    expect(await screen.findByText(/Enter a 10-digit mobile number/)).toBeInTheDocument()
    expect(calls.some((call) => call.path === '/api/auth/otp/request/')).toBe(false)
  })

  it("shows the server's message for a wrong code", async () => {
    const user = userEvent.setup()
    mockApi({
      'GET /api/auth/me/': NOT_SIGNED_IN,
      'POST /api/auth/otp/request/': { status: 202, body: { detail: 'sent' } },
      'POST /api/auth/otp/verify/': {
        status: 400,
        body: { code: ['That code is wrong or has expired. Request a new one.'] },
      },
    })
    renderApp('/login')

    await user.type(screen.getByLabelText('Mobile number'), '9876543210')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    await user.type(await screen.findByLabelText('6-digit code'), '000000')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That code is wrong or has expired. Request a new one.',
    )
  })

  it('explains rate limiting in plain words', async () => {
    const user = userEvent.setup()
    mockApi({
      'GET /api/auth/me/': NOT_SIGNED_IN,
      'POST /api/auth/otp/request/': { status: 429, body: { detail: 'Request was throttled.' } },
    })
    renderApp('/login')

    await user.type(screen.getByLabelText('Mobile number'), '9876543210')
    await user.click(screen.getByRole('button', { name: 'Send code' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Too many tries')
  })
})
