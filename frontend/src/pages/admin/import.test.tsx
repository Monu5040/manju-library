import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Me } from '@/lib/auth'
import type { ImportJobDetail } from '@/lib/types'
import { mockApi, owner, renderApp } from '@/test/utils'

const checked: ImportJobDetail = {
  id: 7,
  file_name: 'Manju Library.xlsx',
  file_format: 'xlsx',
  sheet: 'Admission Sheet',
  header_row: 1,
  mapping: { full_name: 6, mobile: 10, seat: 2 },
  options: { create_missing: true, day_first: true },
  status: 'CHECKED',
  summary: { rows: 100, ready: 94, errors: 6, with_warnings: 38, imported: 0, skipped: 0, memberships: 65, payments: 93, waiting_list: 12, amount_paid: '41850.00' },
  created_by_name: 'Library Owner',
  created_at: '2026-11-11T10:00:00Z',
  imported_at: null,
  undone_at: null,
  can_undo: false,
  sheets: ['Admission Sheet', 'Balance Sheet', 'Formula Items'],
  encoding: '',
  delimiter: '',
  columns: [
    { index: 2, header: 'Seat No.', field: 'seat', ignored: false },
    { index: 6, header: 'Name', field: 'full_name', ignored: false },
    { index: 10, header: 'Mobile No.', field: 'mobile', ignored: false },
    { index: 15, header: 'Days Left', field: null, ignored: true },
  ],
  fields: [
    { key: 'full_name', label: 'Name' },
    { key: 'mobile', label: 'Mobile' },
    { key: 'seat', label: 'Seat (number or W1, W2… for waiting list)' },
  ],
  preview: [],
  problem_rows: [{ row_number: 28, raw: { Name: 'Test Student' }, result: 'ERROR', errors: ['Seat 19 is also given to Another Student (row 12) for the same time.'], warnings: [] }],
  warning_rows: [],
}

const imported: ImportJobDetail = { ...checked, status: 'IMPORTED', imported_at: '2026-11-11T10:05:00Z', can_undo: true, summary: { ...checked.summary, imported: 94, skipped: 6 } }

describe('Import', () => {
  it('uploads, shows problems, and imports only after choosing to skip rows with errors', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: owner },
      'GET /api/admin/imports/': { body: { count: 0, next: null, previous: null, results: [] } },
      'POST /api/admin/imports/': { status: 201, body: checked },
      'GET /api/admin/imports/7/': { body: checked },
      'POST /api/admin/imports/7/commit/': { body: imported },
    })
    renderApp('/admin/import')

    await user.upload(await screen.findByLabelText('Spreadsheet file'), new File(['x'], 'Manju Library.xlsx'))
    await user.click(screen.getByRole('button', { name: 'Check the file' }))

    expect(await screen.findByText('Checked — nothing saved yet')).toBeInTheDocument()
    expect(screen.getByText(/Seat 19 is also given to Another Student/)).toBeInTheDocument()
    expect(screen.getByText('Not needed — calculated by the app')).toBeInTheDocument()
    expect(screen.getByLabelText('Use of column Mobile No.')).toHaveValue('mobile')

    const importButton = screen.getByRole('button', { name: 'Import 94 students' })
    expect(importButton).toBeDisabled()
    await user.click(screen.getByLabelText('Skip the 6 rows with errors'))
    await user.click(importButton)

    expect(await screen.findByRole('button', { name: 'Undo this import' })).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/api/admin/imports/7/commit/')?.body).toEqual({ skip_errors: true })
    expect(calls.find((c) => c.method === 'POST' && c.path === '/api/admin/imports/')?.body).toBeInstanceOf(FormData)
  })

  it('offers exports only to people allowed to export', async () => {
    const page = { body: { count: 0, next: null, previous: null, results: [] } }
    const staff: Me = { ...owner, id: 3, role: 'STAFF', can_export: false }
    mockApi({ 'GET /api/auth/me/': { body: staff }, 'GET /api/admin/students/': page, 'GET /api/admin/shifts/': { body: [] } })
    const first = renderApp('/admin/students?q=asha')
    expect(await screen.findByText('No students match.')).toBeInTheDocument()
    expect(screen.queryByText('Export')).not.toBeInTheDocument()
    first.unmount()

    mockApi({ 'GET /api/auth/me/': { body: owner }, 'GET /api/admin/students/': page, 'GET /api/admin/shifts/': { body: [] } })
    renderApp('/admin/students?q=asha')
    expect(await screen.findByText('Export')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'CSV (.csv)' })).toHaveAttribute('href', '/api/admin/students/export/?status=ACTIVE&q=asha&file_type=csv')
    expect(screen.getByRole('link', { name: /full Aadhaar/ })).toBeInTheDocument()
  })
})
