import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { api } from './api'
import type { PortalHome, PortalReceipt, PortalStudentDetail } from './types'

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
