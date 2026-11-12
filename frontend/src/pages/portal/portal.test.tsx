import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, portalHome, portalProfile, renderApp, student } from '@/test/utils'

const sibling = { ...portalProfile, id: 2, roll_no: 7, full_name: 'Satya Prakash', current_membership: null, total_due: 0 }

describe('Student portal', () => {
  it('shows the seat, time left, dues and notices', async () => {
    mockApi({ 'GET /api/auth/me/': { body: student }, 'GET /api/portal/home/': { body: portalHome } })
    renderApp('/portal')
    expect(await screen.findByRole('heading', { name: 'Hello, Asha' })).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Time left in this membership' })).toHaveAttribute('aria-valuetext', '5 days left')
    expect(screen.getByText(/₹150 is due/)).toBeInTheDocument()
    expect(screen.getByText(/Renew at the front desk/)).toBeInTheDocument()
    expect(screen.getByText('Closed on Diwali')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Call 9000000000' })).toHaveAttribute('href', 'tel:9000000000')
  })

  it('stops asking to renew once the student has renewed', async () => {
    const renewed = { ...portalProfile, renewed_until: '2026-12-30' }
    mockApi({ 'GET /api/auth/me/': { body: student }, 'GET /api/portal/home/': { body: { ...portalHome, profiles: [renewed] } } })
    renderApp('/portal')
    expect(await screen.findByText('Renewed: your seat is yours until 30 Dec 2026.')).toBeInTheDocument()
    expect(screen.queryByText(/Renew at the front desk/)).not.toBeInTheDocument()
    expect(screen.getByText('Renewed')).toBeInTheDocument()
  })

  it('switches between siblings who share a login', async () => {
    const user = userEvent.setup()
    mockApi({ 'GET /api/auth/me/': { body: student }, 'GET /api/portal/home/': { body: { ...portalHome, profiles: [portalProfile, sibling] } } })
    renderApp('/portal')
    await user.click(await screen.findByRole('tab', { name: 'Satya Prakash' }))
    expect(await screen.findByRole('heading', { name: 'Hello, Satya' })).toBeInTheDocument()
    expect(screen.getByText('No current membership')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Satya Prakash' })).toHaveAttribute('aria-selected', 'true')
  })

  it('lets a student update their contact details only', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: student },
      'GET /api/portal/home/': { body: portalHome },
      'PATCH /api/portal/students/1/': { body: portalProfile },
    })
    renderApp('/portal/profile')
    expect(await screen.findByText('XXXX-XXXX-4321')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Address'), 'Ward 4')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Saved.')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ address: 'Ward 4', alt_mobile: '' })
  })
})
