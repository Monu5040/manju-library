import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SystemStatus } from '@/lib/types'
import { mockApi, overview, owner, renderApp } from '@/test/utils'

const status: SystemStatus = {
  version: '4ca999f',
  environment: 'staging',
  checked_at: '2026-11-12T10:00:00Z',
  checks: [
    { label: 'Database', ok: true, detail: 'PostgreSQL 17.2', ms: 3 },
    { label: 'Background worker', ok: false, detail: 'RuntimeError: No background worker answered.', ms: 1500 },
  ],
  jobs: [
    { name: 'reminders', label: 'Reminders', schedule: 'Every hour, 8 AM to 8 PM', state: 'ok', last_run: '2026-11-12T04:35:00Z', last_success: '2026-11-12T04:35:00Z', summary: { main: { closed: 0, created: 12, sent: 0 } } },
    { name: 'import-cleanup', label: 'Delete old import files', schedule: 'Every night, 2:40 AM', state: 'failed', last_run: '2026-11-11T21:10:00Z', last_success: null, summary: { error: 'OperationalError: disk full' } },
  ],
  disk: { total_gb: 31.6, free_gb: 10.4, used_percent: 67 },
  launch: [
    { key: 'sms', label: 'Students get their login code by SMS (MSG91)', done: false },
    { key: 'uptime', label: 'An uptime monitor checks /api/health/ every few minutes', done: null },
  ],
}

describe('System status', () => {
  it('shows what works, what does not, and what is left before launch', async () => {
    mockApi({ 'GET /api/auth/me/': { body: owner }, 'GET /api/admin/system/': { body: status } })
    renderApp('/admin/system')

    const worker = (await screen.findByText('Background worker')).closest('li')!
    expect(within(worker).getByText('Not working')).toBeInTheDocument()
    expect(screen.getByText('main: closed 0, created 12, sent 0')).toBeInTheDocument()
    const failed = screen.getByText('Delete old import files').closest('tr')!
    expect(within(failed).getByText('Failed')).toBeInTheDocument()
    expect(within(failed).getByText('OperationalError: disk full')).toBeInTheDocument()
    expect(screen.getByText('67% used, 10.4 GB free')).toBeInTheDocument()
    expect(screen.getByText('(check yourself)')).toBeInTheDocument()
  })

  it('warns the owner on the overview when a job fails', async () => {
    mockApi({
      'GET /api/auth/me/': { body: owner },
      'GET /api/admin/overview/': { body: overview },
      'GET /api/admin/system/': { body: status },
    })
    renderApp('/admin')
    expect(await screen.findByText(/needs attention: delete old import files/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open System status' })).toHaveAttribute('href', '/admin/system')
  })
})
