import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Me } from '@/lib/auth'
import { todayIso } from '@/lib/format'
import { mockApi, owner, renderApp } from '@/test/utils'

const staffMe: Me = { ...owner, id: 3, full_name: 'Front Desk', role: 'STAFF', can_export: false }
const holiday = {
  id: 4,
  title: 'Closed on Diwali',
  body: 'The library is closed on 1 November.',
  starts_on: '2025-10-25',
  ends_on: '2025-11-02',
  is_pinned: true,
  created_by_name: 'Library Owner',
}

describe('Notices', () => {
  it('lets the owner post a notice for students', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: owner },
      'GET /api/admin/notices/': { body: [holiday] },
      'POST /api/admin/notices/': { status: 201, body: { ...holiday, id: 5 } },
    })
    renderApp('/admin/notices')

    expect(await screen.findByText('Closed on Diwali')).toBeInTheDocument()
    expect(screen.getByText('Ended')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'New notice' }))
    const dialog = await screen.findByRole('dialog', { name: 'New notice' })
    await user.type(within(dialog).getByLabelText('Title'), 'Fee change')
    await user.type(within(dialog).getByLabelText('Message'), 'Day plan is 500 from December.')
    await user.click(within(dialog).getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      title: 'Fee change',
      body: 'Day plan is 500 from December.',
      starts_on: todayIso(),
      ends_on: null,
      is_pinned: false,
    })
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
  })

  it('lets staff edit notices but not delete them', async () => {
    mockApi({ 'GET /api/auth/me/': { body: staffMe }, 'GET /api/admin/notices/': { body: [holiday] } })
    renderApp('/admin/notices')

    expect(await screen.findByText('Closed on Diwali')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })
})
