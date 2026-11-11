import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { api, ApiError } from './api'

export type Role = 'SUPER_ADMIN' | 'STAFF' | 'STUDENT'

export interface Me {
  id: number
  full_name: string
  /** Masked, for example 98XXXXXX10. */
  mobile: string
  email: string | null
  role: Role
  can_export: boolean
}

export const ME_QUERY_KEY = ['auth', 'me'] as const

export const ROLE_LABELS: Record<Role, string> = {
  SUPER_ADMIN: 'Super Admin',
  STAFF: 'Staff',
  STUDENT: 'Student',
}

export function isAdminRole(role: Role) {
  return role === 'SUPER_ADMIN' || role === 'STAFF'
}

export function homePathFor(role: Role) {
  return isAdminRole(role) ? '/admin' : '/portal'
}

/** The signed-in person, or null when nobody is signed in. */
export async function fetchMe(): Promise<Me | null> {
  try {
    return await api<Me>('/auth/me/')
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null
    }
    throw error
  }
}

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: fetchMe,
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: () => api<null>('/auth/logout/', { method: 'POST' }),
    onSettled: () => {
      queryClient.clear()
      queryClient.setQueryData(ME_QUERY_KEY, null)
      navigate('/', { replace: true })
    },
  })
}
