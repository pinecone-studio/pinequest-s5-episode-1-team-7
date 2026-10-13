import { useLayoutEffect, useRef } from 'react'

/**
 * FLIP animation: rows glide to their new position when the queue re-sorts.
 * `order` is any string that changes when the row order does (e.g. the joined ids).
 */
export function useReorderAnimation(order: string) {
  const rows = useRef(new Map<number, HTMLElement>())
  const last = useRef(new Map<number, number>())
  useLayoutEffect(() => {
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const next = new Map<number, number>()
    rows.current.forEach((el, id) => {
      const top = el.getBoundingClientRect().top
      next.set(id, top)
      const prev = last.current.get(id)
      if (!reduceMotion && prev != null && prev !== top) {
        el.classList.remove('reorder-move')
        el.style.transform = `translateY(${prev - top}px)`
        requestAnimationFrame(() => {
          el.classList.add('reorder-move')
          el.style.transform = ''
        })
      }
    })
    last.current = next
  }, [order])
  return (id: number) => (el: HTMLElement | null) => {
    if (el) rows.current.set(id, el)
    else rows.current.delete(id)
  }
}
