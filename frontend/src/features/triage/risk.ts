import type { RiskFlag, Slide } from '../../shared/api/types.ts'

/**
 * Red / yellow / green risk flag colours (TDD 6.1) — the "colour budget".
 *
 * - Red is the most salient: highest chroma, vivid orange-red (not the darkest).
 * - Green leans teal so it stays apart from red under red-green colour blindness.
 * - Yellow is pale straw (dark theme) / dark olive (light theme): lightness
 *   separates it from red when hue vision collapses.
 * - Bars, rings and row edges reuse the badge text colours per theme, so every
 *   rendered flag colour is one of the verified pairs:
 *   contrast 5.1–8.3:1 (WCAG AA needs 4.5), every pair ΔE ≥ 20 under
 *   simulated deuteranopia and protanopia.
 * - Each flag also has a shape cue (see TriageBadges: ▲ ◆ ●), so flags work
 *   in greyscale. Row edges appear on red/yellow rows only.
 */
export const RISK_STYLE: Record<RiskFlag, { badge: string; bar: string; ring: string }> = {
  red: {
    badge: 'border border-[#e8b49b] bg-[#fde9e2] text-[#b23a1f] dark:border-[#6b3a2c] dark:bg-[#3a2426] dark:text-[#ff7a45]',
    bar: 'bg-[#b23a1f] dark:bg-[#ff7a45]',
    ring: 'border-l-[#b23a1f] dark:border-l-[#ff7a45]',
  },
  yellow: {
    badge: 'border border-[#d3be8a] bg-[#f6ecd4] text-[#4f4f08] dark:border-[#57492f] dark:bg-[#3a3120] dark:text-[#ebcb8b]',
    bar: 'bg-[#4f4f08] dark:bg-[#ebcb8b]',
    ring: 'border-l-[#4f4f08] dark:border-l-[#ebcb8b]',
  },
  green: {
    badge: 'border border-[#a9cdbf] bg-[#dff0ea] text-[#0b6b5e] dark:border-[#2f5a50] dark:bg-[#1e3833] dark:text-[#7fe3d0]',
    bar: 'bg-[#0b6b5e] dark:bg-[#7fe3d0]',
    ring: 'border-l-[#0b6b5e] dark:border-l-[#7fe3d0]',
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
