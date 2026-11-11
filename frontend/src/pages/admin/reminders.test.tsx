import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Me } from '@/lib/auth'
import type { AutomationSettings, Reminder } from '@/lib/types'
import { mockApi, owner, renderApp } from '@/test/utils'

const staffMe: Me = { ...owner, id: 3, full_name: 'Front Desk', role: 'STAFF', can_export: false }
const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

const reminder = (id: number, patch: Partial<Reminder>): Reminder => ({
  id,
  kind: 'EXPIRING_SOON',
  kind_label: 'Ending soon',
  status: 'PENDING',
  status_label: 'To send',
  channel: '',
  channel_label: '',
  for_date: '2099-01-01',
  student: id,
  student_name: 'Asha Kumari',
  roll_no: 1,
  mobile: '9876543210',
  message: 'Hello Asha, your seat 4 (Day) at Manju Library is booked until 14 Nov 2026.',
  details: { seat: '4', shift: 'Day', end_date: '2026-11-14' },
  note: '',
  sent_at: null,
  sent_by_name: null,
  whatsapp_url: 'https://wa.me/919876543210?text=Hello%20Asha',
  ...patch,
})

const open = [
  reminder(1, {}),
  reminder(2, {
    kind: 'DUES',
    kind_label: 'Fees due',
    student_name: 'Ravi Kumar',
    mobile: '9876500001',
    details: { seat: '7', shift: 'Morning', amount: '250.00' },
    message: 'Hello Ravi, ₹250 of your fees at Manju Library is still due.',
  }),
]

const settings: AutomationSettings = {
  reminders_enabled: true,
  days_before_expiry: 3,
  remind_on_expiry_day: true,
  dues_after_days: 3,
  dues_repeat_days: 7,
  waitlist_alerts: true,
  send_sms: false,
  mark_left_after_days: 0,
  text_expiring_soon: 'Hello {name}, your seat ends on {date}.',
  text_expires_today: 'Hello {name}, today is the last day.',
  text_dues: 'Hello {name}, ₹{amount} is due.',
  text_waitlist: 'Hello {name}, a seat is free.',
  sms: { EXPIRING_SOON: false, EXPIRES_TODAY: false, DUES: false, WAITLIST: false },
  placeholders: { name: 'First name', date: 'Last day of the membership', amount: 'Amount due (₹)' },
}

function setup(me: Me) {
  return mockApi({
    'GET /api/auth/me/': { body: me },
    'POST /api/admin/reminders/refresh/': { body: { created: 0, closed: 0 } },
    'GET /api/admin/reminders/': (_body, url) => ({ body: page(url.includes('open=1') ? open : []) }),
    'GET /api/admin/reminders/summary/': { body: { open: 2, by_kind: { EXPIRING_SOON: 1, DUES: 1 } } },
    'GET /api/admin/automation/': { body: settings },
    'POST /api/admin/reminders/1/sent/': { body: { ...open[0], status: 'SENT' } },
    'POST /api/admin/reminders/2/sent/': { body: { ...open[1], status: 'SENT' } },
    'POST /api/admin/reminders/2/skip/': { body: { ...open[1], status: 'SKIPPED' } },
  })
}

describe('Reminders', () => {
  it('lists who to remind, with WhatsApp ready to send', async () => {
    const user = userEvent.setup()
    const { calls } = setup(staffMe)
    renderApp('/admin/reminders')

    expect(await screen.findByRole('heading', { name: /Ending soon/ })).toBeInTheDocument()
    expect(screen.getByText('₹250 due · seat 7 · Morning')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Reminders, 2 to send' })).toBeInTheDocument()
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/api/admin/reminders/refresh/')).toBe(true))

    const asha = screen.getByText('Asha Kumari').closest('li')!
    const whatsapp = within(asha).getByRole('link', { name: 'WhatsApp' })
    expect(whatsapp).toHaveAttribute('href', 'https://wa.me/919876543210?text=Hello%20Asha')
    expect(whatsapp).toHaveAttribute('target', '_blank')
    whatsapp.addEventListener('click', (event) => event.preventDefault()) // stay on the page in the test
    await user.click(whatsapp)
    await waitFor(() => expect(calls.find((c) => c.path === '/api/admin/reminders/1/sent/')?.body).toEqual({ channel: 'WHATSAPP' }))

    const ravi = screen.getByText('Ravi Kumar').closest('li')!
    await user.click(within(ravi).getByRole('button', { name: 'Called' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/api/admin/reminders/2/sent/')?.body).toEqual({ channel: 'CALL' }))
    await user.click(within(ravi).getByRole('button', { name: 'Skip' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/admin/reminders/2/skip/')).toBe(true))
  })

  it('lets only the Super Admin change when reminders go out', async () => {
    const user = userEvent.setup()
    const { calls } = mockApi({
      'GET /api/auth/me/': { body: owner },
      'GET /api/admin/automation/': { body: settings },
      'PATCH /api/admin/automation/': { body: { ...settings, days_before_expiry: 5 } },
    })
    renderApp('/admin/settings')
    const days = await screen.findByLabelText('Days before a membership ends')
    expect(screen.getByText('Ending soon: no template yet')).toBeInTheDocument()
    await user.clear(days)
    await user.type(days, '5')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Saved.')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toMatchObject({ days_before_expiry: 5, send_sms: false })
  })

  it('shows staff the settings without letting them change them', async () => {
    mockApi({ 'GET /api/auth/me/': { body: staffMe }, 'GET /api/admin/automation/': { body: settings } })
    renderApp('/admin/settings')
    expect(await screen.findByLabelText('Days before a membership ends')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument()
  })

  it('shows the free seats next to each student waiting', async () => {
    mockApi({
      'GET /api/auth/me/': { body: staffMe },
      'GET /api/admin/waitlist/': {
        body: [
          { id: 1, student: 5, student_name: 'Kiran', roll_no: 5, mobile: '9876520001', preferred_shift: 1, preferred_shift_name: 'Morning', position: 1, status: 'WAITING', note: '', created_at: '2026-11-01T10:00:00Z' },
          { id: 2, student: 6, student_name: 'Sonu', roll_no: 6, mobile: '9876520002', preferred_shift: null, preferred_shift_name: null, position: 2, status: 'WAITING', note: '', created_at: '2026-11-02T10:00:00Z' },
        ],
      },
      'GET /api/admin/waitlist/free-seats/': { body: { '1': [], '2': ['3', '9'] } },
      'GET /api/admin/shifts/': { body: [{ id: 1, name: 'Morning' }, { id: 2, name: 'Day' }] },
    })
    renderApp('/admin/waitlist')
    const kiran = (await screen.findByText('Kiran')).closest('tr')!
    expect(within(kiran).getByText('No seat free')).toBeInTheDocument()
    const sonu = screen.getByText('Sonu').closest('tr')!
    expect(within(sonu).getByText('Day: seats 3, 9')).toBeInTheDocument()
  })
})
