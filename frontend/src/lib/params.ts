import { useSearchParams } from 'react-router'

/** Search params as page state: update({ key: 'value' }) sets, an empty value removes. */
export function useSearchState() {
  const [params, setParams] = useSearchParams()
  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in patch)) next.delete('page')
    setParams(next, { replace: true })
  }
  return [params, update] as const
}
