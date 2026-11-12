import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { navigation } from '@/lib/portal'
import type { OnlinePayment, PortalOnline } from '@/lib/types'
import { mockApi, owner, portalHome, renderApp, student } from '@/test/utils'

const online: PortalOnline = {
  available: true,
  test_mode: true,
  dues: [{ membership: 5, amount: 150, start_date: '2026-11-01', end_date: '2026-11-30' }],
  renewal: {
    membership: 5,
    seat_number: '12',
    shift_name: 'Day',
    time_label: '10:15 AM – 6:30 PM',
    end_date: '2026-11-30',
    options: [
      { plan: 1, plan_name: '1 month · Day', months: 1, start_date: '2026-12-01', end_date: '2026-12-31', price: 450, discount: 0, amount: 450, unavailable: '' },
      {
        plan: 3,
        plan_name: '3 months · Day',
        months: 3,
        start_date: '2026-12-01',
        end_date: '2027-02-28',
        price: 1300,
        discount: 0,
        amount: 1300,
        unavailable: 'Seat 12 is booked from 01 Feb 2027. Please renew at the front desk.',
      },
    ],
  },
}

function setup(extra = {}) {
  const assign = vi.spyOn(navigation, 'assign').mockImplementation(() => {})
  const api = mockApi({
    'GET /api/auth/me/': { body: student },
    'GET /api/portal/home/': { body: portalHome },
    'GET /api/portal/students/1/online/': { body: online },
    'POST /api/portal/students/1/online/': { status: 201, body: { id: 9, url: 'https://rzp.io/i/plink_0009' } },
    ...extra,
  })
  return { ...api, assign }
}

afterEach(() => vi.restoreAllMocks())

describe('Paying online (student)', () => {
  it('pays dues on Razorpay’s page; the amount is not sent from the browser', async () => {
    const user = userEvent.setup()
    const { calls, assign } = setup()
    renderApp('/portal')
    await user.click(await screen.findByRole('button', { name: 'Pay ₹150 online' }))
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ purpose: 'DUES', membership: 5 })
    expect(assign).toHaveBeenCalledWith('https://rzp.io/i/plink_0009')
    expect(screen.getAllByText('Test mode: no real money').length).toBeGreaterThan(0)
  })

  it('renews for a chosen plan; plans that cannot be kept are shown but not offered', async () => {
    const user = userEvent.setup()
    const { calls, assign } = setup()
    renderApp('/portal')
    await user.click((await screen.findAllByRole('button', { name: 'Renew online' }))[0])
    const dialog = await screen.findByRole('dialog', { name: 'Renew your membership' })
    expect(within(dialog).getByRole('radio', { name: /1 month · Day/ })).toBeChecked()
    expect(within(dialog).getByRole('radio', { name: /3 months · Day/ })).toBeDisabled()
    expect(within(dialog).getByText(/Seat 12 is booked from/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Pay ₹450' }))
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ purpose: 'RENEWAL', membership: 5, plan: 1 })
    expect(assign).toHaveBeenCalledWith('https://rzp.io/i/plink_0009')
  })

  it('says so when an earlier payment went through, instead of charging again', async () => {
    const user = userEvent.setup()
    const { assign } = setup({
      'POST /api/portal/students/1/online/': {
        status: 409,
        body: {
          detail: 'Your earlier payment for this went through, so there is nothing more to pay.',
          code: 'already_paid',
          id: 8,
          status: 'PAID',
          purpose: 'DUES',
          amount: 150,
          receipt: 30,
          receipt_no: 1209,
          renewal_end: null,
          needs_desk: false,
        },
      },
    })
    renderApp('/portal')
    await user.click(await screen.findByRole('button', { name: 'Pay ₹150 online' }))
    expect(await screen.findByText(/earlier payment for this went through/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'See receipt #1209' })).toHaveAttribute('href', '/portal/receipts/30')
    expect(assign).not.toHaveBeenCalled()
  })

  it('shows nothing to pay online when the library has not turned it on', async () => {
    setup({ 'GET /api/portal/students/1/online/': { body: { available: false, test_mode: false, dues: [], renewal: null } } })
    renderApp('/portal')
    expect(await screen.findByText(/₹150 is due/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /online/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Renew at the front desk/)).toBeInTheDocument()
  })

  it('confirms the payment on return and links the receipt', async () => {
    const { calls } = setup({
      'POST /api/portal/online/confirm/': {
        body: { id: 9, status: 'PAID', purpose: 'RENEWAL', amount: 450, receipt: 31, receipt_no: 1210, renewal_end: '2026-12-31', needs_desk: false },
      },
    })
    renderApp(
      '/portal/pay/return?razorpay_payment_id=pay_1&razorpay_payment_link_id=plink_0009&razorpay_payment_link_reference_id=mlabc&razorpay_payment_link_status=paid&razorpay_signature=sig&profile=1',
    )
    expect(await screen.findByRole('heading', { name: 'Payment received' })).toBeInTheDocument()
    expect(screen.getByText('Receipt #1210')).toBeInTheDocument()
    expect(screen.getByText('Your membership now runs until 31 Dec 2026.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View receipt' })).toHaveAttribute('href', '/portal/receipts/31')
    // Only Razorpay's own fields go to the server.
    expect(calls.find((c) => c.path === '/api/portal/online/confirm/')?.body).toEqual({
      razorpay_payment_id: 'pay_1',
      razorpay_payment_link_id: 'plink_0009',
      razorpay_payment_link_reference_id: 'mlabc',
      razorpay_payment_link_status: 'paid',
      razorpay_signature: 'sig',
    })
  })

  it('says plainly when the payment was not completed', async () => {
    setup({
      'POST /api/portal/online/confirm/': {
        body: { id: 9, status: 'PENDING', purpose: 'DUES', amount: 150, receipt: null, receipt_no: null, renewal_end: null, needs_desk: false },
      },
    })
    renderApp('/portal/pay/return?razorpay_payment_link_id=plink_0009&razorpay_payment_link_status=cancelled')
    expect(await screen.findByRole('heading', { name: 'Payment not completed' })).toBeInTheDocument()
    expect(screen.getByText(/No money was taken/)).toBeInTheDocument()
  })
})

const attempt: OnlinePayment = {
  id: 9,
  student: 1,
  student_name: 'Asha Kumari',
  roll_no: 1,
  purpose: 'RENEWAL',
  purpose_label: 'Renewal',
  membership: 5,
  amount: 450,
  status: 'PAID',
  status_label: 'Paid',
  plan_name: '1 month · Day',
  renewal_start: '2026-12-01',
  renewal_end: '2026-12-31',
  gateway_payment_id: 'pay_1',
  method: 'upi',
  payment: 31,
  receipt_no: 1210,
  renewal: null,
  problem: 'Paid, but the renewal could not be made (seat taken). The money is kept as an advance.',
  created_at: '2026-11-12T09:30:00Z',
  expires_at: '2026-11-12T09:50:00Z',
  paid_at: '2026-11-12T09:31:00Z',
}

describe('Online payments (desk)', () => {
  it('shows what needs sorting out, and the owner can mark it sorted', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: owner },
      'GET /api/admin/payments/online/summary/': {
        body: { configured: true, test_mode: false, test_mobiles_only: false, enabled: true, needs_attention: 1, paid_today: 1, waiting: 0 },
      },
      'GET /api/admin/payments/online/': { body: { count: 1, next: null, previous: null, results: [attempt] } },
      'POST /api/admin/payments/online/9/sorted/': { body: { ...attempt, problem: '' } },
    })
    renderApp('/admin/payments/online')
    expect(await screen.findByText(/renewal could not be made/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Needs attention' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('link', { name: 'Receipt #1210' })).toHaveAttribute('href', '/admin/payments/31/receipt')
    await user.click(screen.getByRole('button', { name: 'Mark as sorted' }))
    const dialog = await screen.findByRole('dialog', { name: 'Mark as sorted' })
    await user.type(within(dialog).getByLabelText(/What was done/), 'Gave seat 3')
    await user.click(within(dialog).getByRole('button', { name: 'Mark as sorted' }))
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ note: 'Gave seat 3' })
  })

  it('explains when the server is not set up yet', async () => {
    mockApi({
      'GET /api/auth/me/': { body: owner },
      'GET /api/admin/payments/online/summary/': {
        body: { configured: false, test_mode: false, test_mobiles_only: false, enabled: false, needs_attention: 0, paid_today: 0, waiting: 0 },
      },
      'GET /api/admin/payments/online/': { body: { count: 0, next: null, previous: null, results: [] } },
    })
    renderApp('/admin/payments/online')
    const notice = (await screen.findByText('Not set up yet')).closest('[role="status"]') as HTMLElement
    expect(within(notice).getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/admin/settings')
  })
})

