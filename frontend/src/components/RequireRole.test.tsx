import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, NOT_SIGNED_IN, overview, owner, portalHome, renderApp, student } from '@/test/utils'

describe('Protected areas', () => {
  it('sends visitors who are not signed in to the student login', async () => {
    mockApi({ 'GET /api/auth/me/': NOT_SIGNED_IN })
    renderApp('/portal')
    expect(await screen.findByRole('heading', { name: 'Student login' })).toBeInTheDocument()
  })

  it('sends visitors who are not signed in to the staff login for admin pages', async () => {
    mockApi({ 'GET /api/auth/me/': NOT_SIGNED_IN })
    renderApp('/admin')
    expect(await screen.findByRole('heading', { name: 'Staff login' })).toBeInTheDocument()
  })

  it('keeps students out of the admin area', async () => {
    mockApi({ 'GET /api/auth/me/': { body: student }, 'GET /api/portal/home/': { body: portalHome } })
    renderApp('/admin')
    expect(await screen.findByRole('heading', { name: 'Hello, Asha' })).toBeInTheDocument()
  })

  it('logs out and returns to the home page', async () => {
    const user = userEvent.setup()
    let signedIn = true
    const { calls } = mockApi({
      'GET /api/auth/me/': () => (signedIn ? { body: owner } : NOT_SIGNED_IN),
      'GET /api/admin/overview/': { body: overview },
      'POST /api/auth/logout/': () => {
        signedIn = false
        return { status: 204 }
      },
    })
    renderApp('/admin')

    // The layout has a phone and a desktop copy of the button; CSS shows one at a time.
    await user.click((await screen.findAllByRole('button', { name: 'Log out' }))[0])

    expect(
      await screen.findByRole('heading', { name: 'A quiet place to study, every day' }),
    ).toBeInTheDocument()
    expect(calls.some((call) => call.method === 'POST' && call.path === '/api/auth/logout/')).toBe(
      true,
    )
  })
})
