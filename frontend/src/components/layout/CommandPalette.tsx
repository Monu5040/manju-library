import { useQuery } from '@tanstack/react-query'
import { CornerDownLeft, LoaderCircle, Search, UserRound } from 'lucide-react'
import { type KeyboardEvent, useEffect, useId, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '@/lib/api'
import { withParams } from '@/lib/queries'
import type { Paginated, Student } from '@/lib/types'
import { cn } from '@/lib/utils'
import type { NavItem } from './nav'

interface Result {
  key: string
  label: string
  hint: string
  to: string
  icon: NavItem['icon']
}

/**
 * ⌘K: find any student by name, roll number or mobile, or jump to a page, from anywhere.
 * Mounted only while open, so every opening starts empty.
 */
export function CommandPalette({ pages, onClose }: { pages: NavItem[]; onClose: () => void }) {
  const navigate = useNavigate()
  const listId = useId()
  const input = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const term = query.trim()
  const students = useQuery({
    queryKey: ['admin', 'students', 'search', term],
    queryFn: () => api<Paginated<Student>>(withParams('/admin/students/', { q: term, page_size: 6 })),
    enabled: term.length >= 2,
    staleTime: 30_000,
  })

  useEffect(() => {
    input.current?.focus()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
    }
  }, [])

  const lower = term.toLowerCase()
  const results: Result[] = [
    ...(term.length >= 2 ? (students.data?.results ?? []) : []).map((s) => ({
      key: `student-${s.id}`,
      label: s.full_name,
      hint: `Roll ${s.roll_no} · ${s.mobile}`,
      to: `/admin/students/${s.id}`,
      icon: UserRound,
    })),
    ...pages
      .filter((p) => !lower || p.label.toLowerCase().includes(lower))
      .slice(0, term ? 5 : 8)
      .map((p) => ({ key: p.to, label: p.label, hint: 'Go to page', to: p.to, icon: p.icon })),
  ]
  const current = Math.min(active, Math.max(results.length - 1, 0))

  const go = (result: Result | undefined) => {
    if (!result) return
    onClose()
    navigate(result.to)
  }

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'ArrowDown') {
      setActive((i) => Math.min(i + 1, results.length - 1))
    } else if (event.key === 'ArrowUp') {
      setActive((i) => Math.max(i - 1, 0))
    } else if (event.key === 'Enter') {
      go(results[current])
    } else if (event.key === 'Escape') {
      onClose()
    } else {
      return
    }
    event.preventDefault()
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center p-3 pt-[12vh] sm:p-6 sm:pt-[14vh]">
      <div aria-hidden="true" className="absolute inset-0 animate-fade-in bg-[oklch(0.16_0.02_165/0.5)] backdrop-blur-[2px]" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search students and pages"
        className="relative w-full max-w-xl animate-rise-in overflow-hidden rounded-2xl border bg-card shadow-float"
      >
        <div className="flex items-center gap-3 border-b px-4">
          <Search aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
          <input
            ref={input}
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={results[current] ? `${listId}-${results[current].key}` : undefined}
            aria-label="Search students and pages"
            placeholder="Search a name, roll no. or mobile…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setActive(0)
            }}
            onKeyDown={onKeyDown}
            className="h-14 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground/80"
          />
          {students.isFetching && <LoaderCircle aria-hidden="true" className="size-4 animate-spin text-muted-foreground" />}
          <kbd className="hidden rounded-md border bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground sm:block">Esc</kbd>
        </div>
        <ul id={listId} role="listbox" aria-label="Results" className="max-h-[55vh] overflow-y-auto p-2">
          {results.length === 0 && (
            <li className="px-3 py-8 text-center text-sm text-muted-foreground">
              {term.length >= 2 && !students.isFetching ? 'No student or page matches.' : 'Keep typing…'}
            </li>
          )}
          {results.map((result, index) => {
            const Icon = result.icon
            const selected = index === current
            return (
              <li
                key={result.key}
                id={`${listId}-${result.key}`}
                role="option"
                aria-selected={selected}
                onMouseMove={() => setActive(index)}
                onClick={() => go(result)}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm',
                  selected ? 'bg-secondary text-secondary-foreground' : 'text-foreground',
                )}
              >
                <span className={cn('grid size-8 shrink-0 place-items-center rounded-lg', selected ? 'bg-card' : 'bg-muted')}>
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{result.label}</span>
                  <span className="block truncate text-xs text-muted-foreground">{result.hint}</span>
                </span>
                {selected && <CornerDownLeft aria-hidden="true" className="size-4 text-muted-foreground" />}
              </li>
            )
          })}
        </ul>
        <div className="flex items-center justify-between border-t bg-muted/40 px-4 py-2 text-[11px] text-muted-foreground">
          <span>↑ ↓ to move · Enter to open</span>
          <span>{term.length >= 2 ? 'Name, mobile or roll no.' : 'Type 2 letters to search students'}</span>
        </div>
      </div>
    </div>
  )
}
