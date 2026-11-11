import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api } from './api'
import { type Params, withParams } from './queries'
import type {
  Analytics,
  CashClosing,
  CashPreview,
  DailyLedger,
  LedgerCategory,
  LedgerEntry,
  LedgerImport,
  LedgerSummary,
  Paginated,
} from './types'

// Every key starts with 'admin', so useAdminMutation refreshes these after a change.

export const useLedgerCategories = () =>
  useQuery({
    queryKey: ['admin', 'ledger', 'categories'],
    queryFn: () => api<LedgerCategory[]>('/admin/ledger/categories/'),
    staleTime: 60_000,
  })

export const useLedgerEntries = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'ledger', 'entries', params],
    queryFn: () => api<Paginated<LedgerEntry>>(withParams('/admin/ledger/entries/', params)),
    placeholderData: keepPreviousData,
  })

export const useLedgerSummary = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'ledger', 'summary', params],
    queryFn: () => api<LedgerSummary>(withParams('/admin/ledger/entries/summary/', params)),
    placeholderData: keepPreviousData,
  })

export const useDailyLedger = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'ledger', 'daily', params],
    queryFn: () => api<DailyLedger>(withParams('/admin/ledger/daily/', params)),
    placeholderData: keepPreviousData,
  })

export const useCashPreview = (day: string) =>
  useQuery({
    queryKey: ['admin', 'cash', 'preview', day],
    queryFn: () => api<CashPreview>(withParams('/admin/cash-closings/preview/', { day })),
    enabled: Boolean(day),
  })

export const useCashClosings = (page: number) =>
  useQuery({
    queryKey: ['admin', 'cash', 'closings', page],
    queryFn: () => api<Paginated<CashClosing>>(withParams('/admin/cash-closings/', { page })),
    placeholderData: keepPreviousData,
  })

export const useLedgerImports = () =>
  useQuery({
    queryKey: ['admin', 'ledger', 'imports'],
    queryFn: () => api<Paginated<LedgerImport>>('/admin/ledger/imports/'),
  })

export const useAnalytics = (params: Params) =>
  useQuery({
    queryKey: ['admin', 'analytics', params],
    queryFn: () => api<Analytics>(withParams('/admin/analytics/', params)),
    placeholderData: keepPreviousData,
  })
