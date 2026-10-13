import type { RiskFlag, Slide } from '../../shared/api/types.ts'

/** Red / yellow / green risk flag colours (TDD 6.1). */
export const RISK_STYLE: Record<RiskFlag, { badge: string; bar: string; ring: string }> = {
  red: { badge: 'bg-red-600 text-white', bar: 'bg-red-600', ring: 'border-l-red-600' },
  yellow: { badge: 'bg-amber-400 text-slate-950', bar: 'bg-amber-400', ring: 'border-l-amber-400' },
  green: {
    badge: 'bg-emerald-600/15 text-emerald-800 dark:text-emerald-300',
    bar: 'bg-emerald-600',
    ring: 'border-l-emerald-600',
  },
}

/**
 * Manual priorities offered by "Re-assign priority" (backend accepts 0–1). The backend lists every
 * manually prioritised slide above the AI-ranked ones, ordered by this value.
 */
export const PRIORITY_LEVELS = [
  { key: 'highest', value: 1 },
  { key: 'high', value: 0.75 },
  { key: 'medium', value: 0.5 },
  { key: 'low', value: 0.25 },
] as const
export type PriorityLevel = (typeof PRIORITY_LEVELS)[number]['key']

/** The named level for a stored override (closest match, so hand-set values still read sensibly). */
export function priorityLevel(value: number): PriorityLevel {
  return PRIORITY_LEVELS.reduce((best, level) => (Math.abs(level.value - value) < Math.abs(best.value - value) ? level : best))
    .key
}

/** 0–1 score as the 0–100 number shown in the UI. */
export const scorePoints = (score: number | null) => (score == null ? null : Math.round(score * 100))

/** Slides the pathologist still has to act on. */
export const isOpen = (s: Pick<Slide, 'state'>) => s.state === 'queued' || s.state === 'under_review'
