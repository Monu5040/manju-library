import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type {
  Branch,
  Membership,
  Overview,
  Paginated,
  Payment,
  PaymentSummary,
  Plan,
  Seat,
  SeatMap,
  Shift,
  StaffAccount,
  Student,
  WaitlistEntry,
} from './types'

export type Params = Record<string, string | number | boolean | undefined | null>

export function withParams(path: string, params: Params = {}): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '' && value !== false) {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

// --- setup -----------------------------------------------------------------

export const useBranch = () =>
  useQuery({
    queryKey: ['admin', 'branches'],
    queryFn: async () => (await api<Branch[]>('/admin/branches/'))[0] ?? null,
    staleTime: 60_000,
  })

export const useShifts = () =>
  useQuery({ queryKey: ['admin', 'shifts'], queryFn: () => api<Shift[]>('/admin/shifts/'), staleTime: 60_000 })

export const useSeats = () =>
  useQuery({ queryKey: ['admin', 'seats'], queryFn: () => api<Seat[]>('/admin/seats/'), staleTime: 60_000 })

export const usePlans = () =>
  useQuery({ queryKey: ['admin', 'plans'], queryFn: () => api<Plan[]>('/admin/plans/'), staleTime: 60_000 })

// --- people and money -----------------------------------------------------------

export const useOverview = () =>
  useQuery({ queryKey: ['admin', 'overview'], queryFn: () => api<Overview>('/admin/overview/') })

export const useStudents = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'students', params],
    queryFn: () => api<Paginated<Student>>(withParams('/admin/students/', params)),
    placeholderData: keepPreviousData,
  })

export const useStudent = (id: number) =>
  useQuery({ queryKey: ['admin', 'student', id], queryFn: () => api<Student>(`/admin/students/${id}/`) })

export const useMemberships = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'memberships', params],
    queryFn: () => api<Paginated<Membership>>(withParams('/admin/memberships/', params)),
    placeholderData: keepPreviousData,
  })

export const usePayments = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'payments', params],
    queryFn: () => api<Paginated<Payment>>(withParams('/admin/payments/', params)),
    placeholderData: keepPreviousData,
  })

export const usePaymentSummary = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'payments', 'summary', params],
    queryFn: () => api<PaymentSummary>(withParams('/admin/payments/summary/', params)),
  })

export const usePayment = (id: number) =>
  useQuery({ queryKey: ['admin', 'payment', id], queryFn: () => api<Payment>(`/admin/payments/${id}/`) })

export const useSeatMap = (date: string) =>
  useQuery({
    queryKey: ['admin', 'seat-map', date],
    queryFn: () => api<SeatMap>(withParams('/admin/seat-map/', { date })),
    placeholderData: keepPreviousData,
  })

export const useWaitlist = () =>
  useQuery({
    queryKey: ['admin', 'waitlist'],
    queryFn: () => api<WaitlistEntry[]>('/admin/waitlist/?status=WAITING'),
  })

export const useStaffAccounts = () =>
  useQuery({ queryKey: ['admin', 'staff'], queryFn: () => api<StaffAccount[]>('/admin/staff/') })

/**
 * A mutation that refreshes all admin data when it succeeds. Admin data changes together
 * (a payment changes dues, the dashboard and the student), so refreshing it all is simplest.
 */
export function useAdminMutation<TInput, TResult>(fn: (input: TInput) => Promise<TResult>) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  })
}
