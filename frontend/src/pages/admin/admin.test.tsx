import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Me } from '@/lib/auth'
import type { Membership, Payment, Student } from '@/lib/types'
import { mockApi, owner, renderApp } from '@/test/utils'

const staffMe: Me = { ...owner, id: 3, full_name: 'Front Desk', role: 'STAFF', can_export: false }

const shifts = [{ id: 1, name: 'Day', start_time: '10:15:00', end_time: '18:30:00', sort_order: 0, is_active: true, hours: 8.25, time_label: '10:15 AM – 6:30 PM' }]
const seats = [1, 2, 3].map((n) => ({ id: n, number: String(n), label: '', is_active: true }))
const plans = [{ id: 7, name: '1 month · Day', duration_months: 1, shift: 1, shift_name: 'Day', price: 450, is_active: true }]
const seatMap = {
  date: '2026-11-11',
  allow_seat_sharing: true,
  shifts: [{ id: 1, name: 'Day', time_label: '10:15 AM – 6:30 PM', minutes: [615, 1110] }],
  seats: [
    { id: 1, number: '1', is_active: true, bookings: [{ membership: 9, student: 9, student_name: 'Ravi Kumar', roll_no: 2, shift_name: 'Day', time_label: '10:15 AM – 6:30 PM', start_minute: 615, end_minute: 1110, end_date: '2026-12-01', days_left: 20 }] },
    { id: 2, number: '2', is_active: true, bookings: [] },
    { id: 3, number: '3', is_active: true, bookings: [] },
  ],
  summary: { seats: 3, occupied: 1, free: 2 },
}

const asha: Student = {
  id: 1,
  roll_no: 1,
  full_name: 'Asha Kumari',
  gender: 'F',
  father_name: 'Ramesh',
  mobile: '9876543210',
  alt_mobile: '',
  aadhaar_masked: 'XXXX-XXXX-4321',
  address: '',
  admission_date: '2026-11-11',
  status: 'ACTIVE',
  notes: '',
  created_at: '2026-11-11T10:00:00Z',
  current_membership: { id: 5, seat_number: '2', shift_name: 'Day', time_label: '10:15 AM – 6:30 PM', plan_name: '1 month · Day', start_date: '2026-11-11', end_date: '2026-12-10', days_left: 29, state: 'ACTIVE', due_total: 250 },
  total_due: 250,
}

const membership: Membership = {
  id: 5, student: 1, student_name: 'Asha Kumari', roll_no: 1, plan: 7, plan_name: '1 month · Day', shift: 1, shift_name: 'Day',
  custom_start_time: null, custom_end_time: null, time_label: '10:15 AM – 6:30 PM', seat: 2, seat_number: '2',
  start_date: '2026-11-11', end_date: '2026-12-10', price: 450, discount: 0, net_fee: 450, paid_total: 200, due_total: 250,
  status: 'ACTIVE', state: 'ACTIVE', days_left: 29, renewed_from: null, notes: '', created_at: '2026-11-11T10:00:00Z',
}

const payment: Payment = {
  id: 11, receipt_no: 1107, student: 1, student_name: 'Asha Kumari', roll_no: 1, membership: 5, amount: 200, mode: 'UPI', mode_label: 'UPI',
  paid_on: '2026-11-11', reference: '', notes: '', collected_by_name: 'Front Desk', is_void: false, void_reason: '', voided_at: null, created_at: '2026-11-11T10:00:00Z',
}

const page = <T,>(results: T[]) => ({ body: { count: results.length, next: null, previous: null, results } })

function setupApi(me: Me) {
  return mockApi({
    'GET /api/auth/me/': { body: me },
    'GET /api/admin/shifts/': { body: shifts },
    'GET /api/admin/seats/': { body: seats },
    'GET /api/admin/plans/': { body: plans },
    'GET /api/admin/seat-map/': { body: seatMap },
    'GET /api/admin/branches/': { body: [{ id: 1, name: 'Manju Library', code: 'main', address: '', phone: '', allow_seat_sharing: true, is_active: true }] },
    'GET /api/admin/students/': page([asha]),
    'GET /api/admin/students/1/': { body: asha },
    'GET /api/admin/memberships/': page([membership]),
    'GET /api/admin/payments/': page([payment]),
    'POST /api/admin/admissions/': { status: 201, body: { student: asha, membership, payment } },
  })
}

describe('Admin screens', () => {
  it('admits a student: the plan fills shift and fee, taken seats are marked', async () => {
    const user = userEvent.setup()
    const { calls } = setupApi(staffMe)
    renderApp('/admin/students/new')

    await user.type(await screen.findByLabelText('Full name'), 'Asha Kumari')
    await user.type(screen.getByLabelText(/^Mobile/), '98765 43210')
    await user.selectOptions(screen.getByLabelText('Plan'), '7')
    expect(screen.getByLabelText('Shift')).toHaveValue('1')
    expect(screen.getByLabelText('Fee (₹)')).toHaveValue('450')

    const seatSelect = screen.getByLabelText('Seat')
    expect(within(seatSelect).getByRole('option', { name: /Seat 1 — taken by Ravi Kumar/ })).toBeDisabled()
    await user.selectOptions(seatSelect, '2')
    await user.click(screen.getByRole('button', { name: 'Admit student' }))

    expect(await screen.findByText(/is admitted as roll 1/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Print the receipt' })).toHaveAttribute('href', '/admin/payments/11/receipt')
    const body = calls.find((c) => c.path === '/api/admin/admissions/')?.body as Record<string, Record<string, unknown>>
    expect(body.student.full_name).toBe('Asha Kumari')
    expect(body.membership).toMatchObject({ plan: 7, shift: 1, seat: 2, price: 450, discount: 0 })
    expect(body.payment).toMatchObject({ amount: 450, mode: 'CASH' })
  })

  it('lists students with their seat, end date and dues', async () => {
    setupApi(staffMe)
    renderApp('/admin/students')
    const row = (await screen.findByRole('link', { name: 'Asha Kumari' })).closest('tr') as HTMLElement
    expect(within(row).getByText('Seat 2 · Day')).toBeInTheDocument()
    expect(within(row).getByText('29 days left')).toBeInTheDocument()
    expect(within(row).getByText('Due ₹250')).toBeInTheDocument()
  })

  it('hides owner-only actions from staff', async () => {
    setupApi(staffMe)
    renderApp('/admin/students/1')
    expect(await screen.findByRole('heading', { name: 'Asha Kumari' })).toBeInTheDocument()
    expect(await screen.findByText('#1107')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Void' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show (logged)' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Renew' })).toBeInTheDocument()
  })

  it('shows owner-only actions to the Super Admin', async () => {
    setupApi(owner)
    renderApp('/admin/students/1')
    expect(await screen.findByRole('button', { name: 'Void' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show (logged)' })).toBeInTheDocument()
  })

  it('keeps settings read-only for staff', async () => {
    setupApi(staffMe)
    renderApp('/admin/settings')
    expect(await screen.findByText('Only the Super Admin can change these.')).toBeInTheDocument()
    expect(await screen.findByLabelText('Name')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Add shift' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Staff' })).not.toBeInTheDocument()
  })
})
