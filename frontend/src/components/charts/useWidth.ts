import { type RefObject, useLayoutEffect, useState } from 'react'

/** The element's width in pixels, kept up to date as the layout changes. */
export function useWidth(ref: RefObject<HTMLElement | null>, fallback: number): number {
  const [width, setWidth] = useState(fallback)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element || typeof ResizeObserver === 'undefined') {
      return
    }
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.round(entry.contentRect.width) || fallback)
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref, fallback])
  return width
}
