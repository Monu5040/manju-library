import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Me } from '@/lib/auth'
import { presetRange } from '@/lib/ranges'
import type { Analytics } from '@/lib/types'
import { mockApi, overview, owner, renderApp } from '@/test/utils'

const staffMe: Me = { ...owner, id: 3, full_name: 'Front Desk', role: 'STAFF', can_export: false }

const analytics: Analytics = {
  from: '2026-11-01',
  to: '2026-11-11',
  as_of: '2026-11-11',
  previous: { from: '2026-10-21', to: '2026-10-31' },
  grain: 'day',
  kpis: {
    income: { value: 12000, previous: 10000 },
    fees: { value: 11500, previous: 10000 },
    expenses: { value: 3000, previous: 2000 },
    profit: { value: 9000, previous: 8000 },
    new_admissions: { value: 4, previous: 0 },
    active_members: { value: 42 },
    occupancy_percent: { value: 64 },
    seats_in_use: { value: 45, of: 51 },
    outstanding_dues: { value: 2350 },
    expiring_in_7_days: { value: 6 },
  },
  revenue: [
    { period: '2026-11-10', label: '10 Nov 2026', fees: 0, other_income: 0, income: 0, expenses: 0, profit: 0 },
    { period: '2026-11-11', label: '11 Nov 2026', fees: 11500, other_income: 500, income: 12000, expenses: 3000, profit: 9000 },
  ],
  occupancy: {
    date: '2026-11-11',
    percent: 64,
    seats_total: 3,
    seats_in_use: 2,
    shifts: [
      { id: 1, name: 'Morning', time_label: '6:00 AM – 10:00 AM', taken: 1, partly: 0, free: 2, free_seats: ['2', '3'] },
      { id: 2, name: 'Day', time_label: '10:15 AM – 6:30 PM', taken: 1, partly: 1, free: 1, free_seats: ['3'] },
    ],
    grid: [
      { seat: '1', cells: ['taken', 'taken'] },
      { seat: '2', cells: ['free', 'partly'] },
      { seat: '3', cells: ['free', 'free'] },
    ],
  },
  retention: {
    ended: 10,
    renewed: 6,
    left: 2,
    undecided: 2,
    renewal_rate: 75,
    average_stay_months: 5.5,
    cohorts: [{ month: '2026-11-01', label: 'Nov 2026', joined: 4, still_members: 4, percent: 100 }],
  },
  mix: {
    date: '2026-11-11',
    by_shift: [{ label: 'Day', count: 30 }],
    by_plan: [{ label: '1 month', count: 25 }],
    by_gender: [{ label: 'Female', count: 22 }],
  },
  collections: {
    dues_by_age: [
      { label: '0–7 days', amount: 900, count: 2 },
      { label: '8–30 days', amount: 1000, count: 2 },
      { label: 'Over 30 days', amount: 450, count: 1 },
    ],
    payment_modes: [{ mode: 'CASH', label: 'Cash', amount: 7000, count: 15 }],
  },
}

describe('Analytics', () => {
  it('shows the key numbers with their change and every chart as a table too', async () => {
    const user = userEvent.setup()
    mockApi({ 'GET /api/auth/me/': { body: owner }, 'GET /api/admin/analytics/': { body: analytics } })
    renderApp('/admin/analytics')

    expect(await screen.findByRole('heading', { name: 'Analytics' })).toBeInTheDocument()
    const income = (await screen.findByText('Income', { selector: 'dt' })).parentElement!
    expect(within(income).getByText('₹12,000')).toBeInTheDocument()
    expect(within(income).getByText(/Up 20% on/)).toBeInTheDocument()
    const expenses = screen.getByText('Expenses', { selector: 'dt' }).parentElement!
    expect(within(expenses).getByText(/Up 50% on/).closest('span')).toHaveClass('text-destructive')
    expect(screen.getByText('Previous period: 0')).toBeInTheDocument() // admissions had none
    expect(screen.getByText('Morning (2)')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Seat 2 · Day: Partly booked' })).toBeInTheDocument()

    await user.click(screen.getByRole('group', { name: 'Show income and expenses as' }).querySelector('button:last-child')!)
    const table = screen.getAllByRole('table')[0]
    expect(within(table).getByText('11 Nov 2026')).toBeInTheDocument()
    expect(within(table).getByText('₹9,000')).toBeInTheDocument()
  })

  it('asks for the chosen period', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({ 'GET /api/auth/me/': { body: owner }, 'GET /api/admin/analytics/': { body: analytics } })
    renderApp('/admin/analytics')
    await user.selectOptions(await screen.findByLabelText('Period'), 'last-month')
    const { from, to } = presetRange('last-month')
    await waitFor(() =>
      expect(calls.some((c) => c.path === '/api/admin/analytics/' && c.url.includes(`from=${from}&to=${to}`))).toBe(true),
    )
  })

  it('is for the Super Admin only', async () => {
    mockApi({ 'GET /api/auth/me/': { body: staffMe }, 'GET /api/admin/overview/': { body: overview } })
    renderApp('/admin/analytics')
    expect(await screen.findByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Analytics' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Ledger' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Expenses' })).toBeInTheDocument()
  })
})

describe('Date ranges', () => {
  it('handles year ends and the April financial year', () => {
    expect(presetRange('last-month', '2026-01-15')).toEqual({ from: '2025-12-01', to: '2025-12-31' })
    expect(presetRange('this-fy', '2026-02-10')).toEqual({ from: '2025-04-01', to: '2026-02-10' })
    expect(presetRange('this-fy', '2026-04-01')).toEqual({ from: '2026-04-01', to: '2026-04-01' })
    expect(presetRange('last-12-months', '2026-11-11')).toEqual({ from: '2025-12-01', to: '2026-11-11' })
  })
})
