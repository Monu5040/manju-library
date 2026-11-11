import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Me } from '@/lib/auth'
import type { CashPreview, LedgerCategory, LedgerImport } from '@/lib/types'
import { mockApi, owner, renderApp } from '@/test/utils'

const staffMe: Me = { ...owner, id: 3, full_name: 'Front Desk', role: 'STAFF', can_export: false }
const EMPTY = { count: 0, next: null, previous: null, results: [] }

const categories: LedgerCategory[] = [
  { id: 1, name: 'Electricity', kind: 'EXPENSE', code: 'electricity', sort_order: 10, is_active: true, entry_count: 0 },
  { id: 2, name: 'Water', kind: 'EXPENSE', code: 'water', sort_order: 60, is_active: false, entry_count: 0 },
  { id: 3, name: 'Past fees (old Balance Sheet)', kind: 'INCOME', code: 'past-fees', sort_order: 0, is_active: true, entry_count: 0 },
  { id: 4, name: 'Other income', kind: 'INCOME', code: 'other-income', sort_order: 10, is_active: true, entry_count: 0 },
]

describe('Expenses', () => {
  it('lets staff record an expense from an active category', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: staffMe },
      'GET /api/admin/ledger/categories/': { body: categories },
      'GET /api/admin/ledger/entries/': { body: EMPTY },
      'GET /api/admin/ledger/entries/summary/': { body: { expenses: 0, other_income: 0, count: 0, by_category: [] } },
      'POST /api/admin/ledger/entries/': { status: 201, body: {} },
    })
    renderApp('/admin/expenses')

    expect(await screen.findByText('Nothing recorded in this period.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add expense' }))
    const dialog = await screen.findByRole('dialog', { name: 'Add an expense' })
    const category = within(dialog).getByLabelText('Category')
    expect(within(category).queryByRole('option', { name: 'Water' })).not.toBeInTheDocument() // turned off
    await user.selectOptions(category, 'Electricity')
    await user.type(within(dialog).getByLabelText('Amount (₹)'), '1200')
    await user.type(within(dialog).getByLabelText('What for'), 'Bijli bill')
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      category: 1,
      amount: '1200',
      mode: 'CASH',
      details: 'Bijli bill',
    })
    expect(screen.queryByRole('button', { name: 'Void' })).not.toBeInTheDocument()
  })
})

const preview: CashPreview = {
  day: '2026-11-11',
  period_start: '2026-11-11',
  previous_day: null,
  opening: null,
  fees: 450,
  fee_count: 1,
  other_income: 0,
  other_income_count: 0,
  expenses: 120,
  expense_count: 1,
  cash_in: 450,
  cash_out: 120,
  expected: 330,
  can_close: true,
  blocked_reason: '',
  closing: null,
}

describe('Cash book', () => {
  it('works out what should be in the drawer and records the count', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: staffMe },
      'GET /api/admin/cash-closings/preview/': { body: preview },
      'GET /api/admin/cash-closings/': { body: EMPTY },
      'POST /api/admin/cash-closings/': { status: 201, body: {} },
    })
    renderApp('/admin/cash')

    await user.type(await screen.findByLabelText('Cash in the drawer at the start'), '1000')
    expect(screen.getByText('₹1,330')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Counted in the drawer (₹)'), '1300')
    expect(screen.getByRole('status')).toHaveTextContent('Short by ₹30')
    await user.click(screen.getByRole('button', { name: /^Close/ }))

    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      day: preview.day,
      counted: '1300',
      removed: '0',
      note: '',
      opening: '1000',
    })
  })

  it('explains why a day cannot be closed', async () => {
    mockApi({
      'GET /api/auth/me/': { body: staffMe },
      'GET /api/admin/cash-closings/preview/': {
        body: { ...preview, can_close: false, blocked_reason: 'A later day is already closed. Days are closed in order.' },
      },
      'GET /api/admin/cash-closings/': { body: EMPTY },
    })
    renderApp('/admin/cash')
    expect(await screen.findByText('A later day is already closed. Days are closed in order.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Counted in the drawer (₹)')).not.toBeInTheDocument()
  })
})

const checked: LedgerImport = {
  id: 7,
  file_name: 'Manju Library.xlsx',
  sheet: 'Balance Sheet',
  status: 'CHECKED',
  status_label: 'Checked',
  created_by_name: 'Library Owner',
  created_at: '2026-11-11T10:00:00Z',
  imported_at: null,
  undone_at: null,
  can_undo: false,
  summary: {
    first_day: '2025-07-01',
    last_day: '2025-07-03',
    income_days: 3,
    sheet_income: '5550.00',
    days_to_add: 2,
    income_to_add: '2300.00',
    days_covered: 1,
    days_already: 0,
    expense_lines: 0,
    expenses_to_add: 0,
    expense_total_to_add: '0',
    expenses_already: 0,
    errors: 0,
  },
  income: [
    { day: '2025-07-01', rows: [7], students: 1, sheet_amount: '400.00', recorded: '0', to_add: '400.00', remarks: '', status: 'add' },
    { day: '2025-07-02', rows: [8], students: 6, sheet_amount: '2350.00', recorded: '450.00', to_add: '1900.00', remarks: '', status: 'add' },
    { day: '2025-07-03', rows: [9], students: 7, sheet_amount: '2800.00', recorded: '3000.00', to_add: '0', remarks: '', status: 'covered' },
  ],
  expenses: [],
  errors: [],
}

describe('Balance Sheet import', () => {
  it('checks the file, shows what will be added, then imports', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: owner },
      'GET /api/admin/ledger/imports/': { body: EMPTY },
      'POST /api/admin/ledger/imports/': { status: 201, body: checked },
      'POST /api/admin/ledger/imports/7/commit/': { body: { ...checked, status: 'IMPORTED', status_label: 'Imported', can_undo: true } },
    })
    renderApp('/admin/ledger/import')

    const file = new File(['x'], 'Manju Library.xlsx')
    await user.upload(await screen.findByLabelText('Excel or CSV file'), file)
    await user.click(screen.getByRole('button', { name: 'Check file' }))

    const result = await screen.findByRole('region', { name: 'Check result' })
    expect(within(result).getByText('₹2,300')).toBeInTheDocument()
    expect(within(result).getByText('Already in payments')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toBeInstanceOf(FormData)

    await user.click(within(result).getByRole('button', { name: 'Import' }))
    expect(await screen.findByText(/Imported. The entries are in the ledger/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Undo this import' })).toBeInTheDocument()
  })
})
