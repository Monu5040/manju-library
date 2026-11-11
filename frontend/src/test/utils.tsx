import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import App from '@/App'
import type { Me } from '@/lib/auth'

export function renderApp(route: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { queryClient, ...result }
}

interface MockResponse {
  status?: number
  body?: unknown
}

type Handler = MockResponse | ((body: unknown) => MockResponse)

export interface RecordedCall {
  method: string
  path: string
  body: unknown
  headers: Record<string, string>
}

/** Replace fetch with a table of "METHOD /path" handlers and record every call. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: RecordedCall[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const path = new URL(url, 'http://localhost').pathname
    const method = (init?.method ?? 'GET').toUpperCase()
    const body = init?.body instanceof FormData ? init.body : init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body, headers: (init?.headers ?? {}) as Record<string, string> })

    const handler = routes[`${method} ${path}`]
    const result: MockResponse = handler
      ? typeof handler === 'function'
        ? handler(body)
        : handler
      : { status: 404, body: { detail: `No mock for ${method} ${path}` } }
    const status = result.status ?? 200
    return new Response(status === 204 ? null : JSON.stringify(result.body ?? {}), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls }
}

export const NOT_SIGNED_IN: MockResponse = {
  status: 403,
  body: { detail: 'Authentication credentials were not provided.' },
}

export const student: Me = {
  id: 1,
  full_name: 'Asha Kumari',
  mobile: '98XXXXXX10',
  email: null,
  role: 'STUDENT',
  can_export: false,
}

export const owner: Me = {
  id: 2,
  full_name: 'Library Owner',
  mobile: '91XXXXXX80',
  email: 'owner@example.com',
  role: 'SUPER_ADMIN',
  can_export: true,
}

export const overview = {
  users: { students: 99, staff: 1, super_admins: 1 },
  library: {
    active_members: 99,
    seats: 51,
    occupied_seats: 46,
    occupancy_percent: 90,
    expiring_in_7_days: 4,
    outstanding_dues: 1250,
    collected_today: 900,
    collected_this_month: 11850,
    waiting: 12,
  },
}

export const portalProfile = {
  id: 1,
  roll_no: 1,
  full_name: 'Asha Kumari',
  father_name: 'Ramesh',
  mobile: '9876543210',
  alt_mobile: '',
  address: '',
  aadhaar_masked: 'XXXX-XXXX-4321',
  admission_date: '2026-11-01',
  status: 'ACTIVE' as const,
  branch_name: 'Manju Library',
  current_membership: {
    id: 5,
    seat_number: '12',
    shift_name: 'Day',
    plan_name: '1 month · Day',
    time_label: '10:15 AM – 6:30 PM',
    start_date: '2026-11-01',
    end_date: '2026-11-30',
    state: 'ACTIVE' as const,
    days_left: 5,
    price: 450,
    discount: 0,
    net_fee: 450,
    paid_total: 300,
    due_total: 150,
  },
  total_due: 150,
}

export const portalHome = {
  profiles: [portalProfile],
  library: { name: 'Manju Library', address: 'Station Road', phone: '9000000000' },
  notices: [{ id: 1, title: 'Closed on Diwali', body: 'The library is closed on 1 November.', starts_on: '2026-10-25', ends_on: null, is_pinned: true }],
  shifts: [{ id: 1, name: 'Day', time_label: '10:15 AM – 6:30 PM', hours: 8.25 }],
  plans: [{ id: 1, name: '1 month · Day', duration_months: 1, shift_name: 'Day', price: 450 }],
}
