import type { RiskFlag, Slide } from '../../shared/api/types.ts'

/**
 * Red / yellow / green risk flag colours (TDD 6.1).
 * Dusty, desaturated tones in both modes: readable without neon glare.
 */
export const RISK_STYLE: Record<RiskFlag, { badge: string; bar: string; ring: string }> = {
  red: {
    badge: 'border border-[#dfb9b9] bg-[#f3e2e2] text-[#7a3535] dark:border-[#5a3436] dark:bg-[#3a2426] dark:text-[#eec3c3]',
    bar: 'bg-[#a85656] dark:bg-[#cf8d8d]',
    ring: 'border-l-[#a85656] dark:border-l-[#cf8d8d]',
  },
  yellow: {
    badge: 'border border-[#d8c49a] bg-[#f2e8d3] text-[#6d5220] dark:border-[#57492f] dark:bg-[#3a3120] dark:text-[#e6cf9c]',
    bar: 'bg-[#a5813f] dark:bg-[#c9ac7c]',
    ring: 'border-l-[#a5813f] dark:border-l-[#c9ac7c]',
  },
  green: {
    badge: 'border border-[#b3d4c2] bg-[#e2efe6] text-[#2f6b4e] dark:border-[#2f4a3e] dark:bg-[#22382f] dark:text-[#b7dcc4]',
    bar: 'bg-[#4a8f6d] dark:bg-[#8fc0a6]',
    ring: 'border-l-[#4a8f6d] dark:border-l-[#8fc0a6]',
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
