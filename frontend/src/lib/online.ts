import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './api'
import { type Params, withParams } from './queries'
import type { OnlinePayment, OnlineSummary, Paginated } from './types'

// Keys start with 'admin', so useAdminMutation refreshes them after a change.

export const useOnlinePayments = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'online-payments', params],
    queryFn: () => api<Paginated<OnlinePayment>>(withParams('/admin/payments/online/', params)),
    placeholderData: keepPreviousData,
  })

export const useOnlineSummary = () =>
  useQuery({
    queryKey: ['admin', 'online-payments', 'summary'],
    queryFn: () => api<OnlineSummary>('/admin/payments/online/summary/'),
  })

export const checkOnlinePayment = (id: number) =>
  api<OnlinePayment>(`/admin/payments/online/${id}/check/`, { method: 'POST' })

export const markOnlinePaymentSorted = ({ id, note }: { id: number; note: string }) =>
  api<OnlinePayment>(`/admin/payments/online/${id}/sorted/`, { method: 'POST', body: { note } })
