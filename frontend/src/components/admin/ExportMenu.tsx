import { Download } from 'lucide-react'
import { useMe } from '@/lib/auth'
import { type Params, withParams } from '@/lib/queries'

/**
 * Download the list as shown (same filters) as Excel or CSV. Only for people allowed to
 * export; the Super Admin can also include full Aadhaar numbers (logged).
 */
export function ExportMenu({ path, params, aadhaar = false }: { path: string; params: Params; aadhaar?: boolean }) {
  const { data: me } = useMe()
  if (!me?.can_export) {
    return null
  }
  const link = (extra: Params) => `/api${withParams(path, { ...params, page: undefined, page_size: undefined, ...extra })}`
  return (
    <details className="relative">
      <summary className="inline-flex h-10 cursor-pointer list-none items-center gap-2 rounded-md border border-input bg-card px-4 text-sm font-medium hover:bg-muted [&::-webkit-details-marker]:hidden">
        <Download aria-hidden="true" className="size-4" /> Export
      </summary>
      <div className="absolute right-0 z-20 mt-1 w-64 rounded-md border bg-card p-1 shadow-md">
        <a className="block rounded px-3 py-2 text-sm hover:bg-muted" href={link({ file_type: 'xlsx' })}>
          Excel (.xlsx)
        </a>
        <a className="block rounded px-3 py-2 text-sm hover:bg-muted" href={link({ file_type: 'csv' })}>
          CSV (.csv)
        </a>
        {aadhaar && me.role === 'SUPER_ADMIN' && (
          <a className="block rounded px-3 py-2 text-sm hover:bg-muted" href={link({ file_type: 'xlsx', include_full_aadhaar: '1' })}>
            Excel with full Aadhaar numbers
            <span className="block text-xs text-muted-foreground">Recorded in the audit log</span>
          </a>
        )}
      </div>
    </details>
  )
}
