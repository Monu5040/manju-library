import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './api'
import { type Params, withParams } from './queries'
import type { AutomationSettings, Paginated, Reminder } from './types'

// Keys start with 'admin', so useAdminMutation refreshes them after a change.

export const useReminders = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'reminders', params],
    queryFn: () => api<Paginated<Reminder>>(withParams('/admin/reminders/', params)),
    placeholderData: keepPreviousData,
  })

export const useReminderSummary = (enabled = true) =>
  useQuery({
    queryKey: ['admin', 'reminders', 'summary'],
    queryFn: () => api<{ open: number; by_kind: Partial<Record<Reminder['kind'], number>> }>('/admin/reminders/summary/'),
    staleTime: 60_000,
    enabled,
  })

export const useAutomationSettings = () =>
  useQuery({ queryKey: ['admin', 'automation'], queryFn: () => api<AutomationSettings>('/admin/automation/') })

export const useFreeSeats = () =>
  useQuery({
    queryKey: ['admin', 'waitlist', 'free-seats'],
    queryFn: () => api<Record<string, string[]>>('/admin/waitlist/free-seats/'),
  })
