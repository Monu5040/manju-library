import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useSearchParams } from 'react-router'
import { ApiError, api } from './api'
import type { PortalHome, PortalOnline, PortalOnlineStatus, PortalReceipt, PortalStudentDetail } from './types'

export const usePortalHome = () =>
  useQuery({ queryKey: ['portal', 'home'], queryFn: () => api<PortalHome>('/portal/home/') })

export const usePortalStudent = (id: number | undefined) =>
  useQuery({
    queryKey: ['portal', 'student', id],
    queryFn: () => api<PortalStudentDetail>(`/portal/students/${id}/`),
    enabled: id !== undefined,
  })

export const usePortalReceipt = (id: number) =>
  useQuery({ queryKey: ['portal', 'receipt', id], queryFn: () => api<PortalReceipt>(`/portal/receipts/${id}/`) })

/** Which of the login's student profiles is shown (siblings share a login): ?profile=<id>. */
export function useSelectedProfile() {
  const home = usePortalHome()
  const [params, setParams] = useSearchParams()
  const profiles = home.data?.profiles ?? []
  const wanted = Number(params.get('profile'))
  const selected = profiles.find((p) => p.id === wanted) ?? profiles[0]
  const select = (id: number) => {
    const next = new URLSearchParams(params)
    next.set('profile', String(id))
    setParams(next, { replace: true })
  }
  return { home, profiles, selected, select }
}

/** What this student can pay online (Razorpay): dues, and renewing their membership. */
export const usePortalOnline = (studentId: number | undefined) =>
  useQuery({
    queryKey: ['portal', 'online', studentId],
    queryFn: () => api<PortalOnline>(`/portal/students/${studentId}/online/`),
    enabled: studentId !== undefined,
  })

export interface OnlineStart {
  purpose: 'DUES' | 'RENEWAL'
  membership: number
  plan?: number
}

/** Opens a Razorpay payment link; the browser then goes to Razorpay's page to pay. */
export function useStartOnlinePayment(studentId: number) {
  const queryClient = useQueryClient()
  const start = useMutation({
    mutationFn: (input: OnlineStart) =>
      api<{ id: number; url: string }>(`/portal/students/${studentId}/online/`, { method: 'POST', body: input }),
    onSuccess: ({ url }) => goTo(url),
    onError: (error) => {
      // An earlier payment turned out to have gone through: show the new balance.
      if (alreadyPaid(error)) void queryClient.invalidateQueries({ queryKey: ['portal'] })
    },
  })
  const { reset } = start
  useEffect(() => {
    // Coming Back from Razorpay's page restores this page as it was, button spinning.
    const onShow = (event: PageTransitionEvent) => event.persisted && reset()
    window.addEventListener('pageshow', onShow)
    return () => window.removeEventListener('pageshow', onShow)
  }, [reset])
  return start
}

/** The server found that an earlier online payment for this was paid after all. */
export function alreadyPaid(error: unknown): { receipt: number | null; receipt_no: number | null } | null {
  if (error instanceof ApiError && error.status === 409) {
    const data = error.data as { code?: string; receipt?: number | null; receipt_no?: number | null } | null
    if (data?.code === 'already_paid') return { receipt: data.receipt ?? null, receipt_no: data.receipt_no ?? null }
  }
  return null
}

/** Leaving the app for Razorpay's page (a function so tests can replace it). */
export const navigation = {
  assign: (url: string) => window.location.assign(url),
}

function goTo(url: string) {
  navigation.assign(url)
}

export const confirmOnlinePayment = (params: Record<string, string>) =>
  api<PortalOnlineStatus>('/portal/online/confirm/', { method: 'POST', body: params })

export const fetchOnlineStatus = (id: number, refresh: boolean) =>
  api<PortalOnlineStatus>(`/portal/online/${id}/${refresh ? '?refresh=1' : ''}`)
