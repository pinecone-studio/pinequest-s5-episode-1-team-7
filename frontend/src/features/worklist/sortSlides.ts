import type { Slide } from '../../shared/api/types.ts'

export type SortMode = 'risk' | 'arrival'

const byOldest = (a: Slide, b: Slide) => a.created_at.localeCompare(b.created_at) || a.id - b.id

/**
 * `risk` keeps the server's order (GET /queue?sort=risk: manual priority first, then AI score).
 * `arrival` is the classic lab order: urgent requests first, then oldest first.
 */
export function sortSlides(slides: Slide[], mode: SortMode): Slide[] {
  if (mode === 'risk') return slides
  return [...slides].sort(
    (a, b) => Number(b.indication === 'Urgent') - Number(a.indication === 'Urgent') || byOldest(a, b),
  )
}
