import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Indication, RiskFlag, SlideState } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { Spinner } from '../../shared/ui/Spinner.tsx'
import { RISK_STYLE, scorePoints } from './risk.ts'

/** Non-colour cue per flag: shapes stay apart in greyscale and for colour-blind users. */
const FLAG_SHAPE: Record<RiskFlag, ReactNode> = {
  // ▲ high — upward triangle reads as alarm
  red: <path d="M8 1.5 15 14H1Z" />,
  // ◆ moderate — diamond
  yellow: <path d="M8 1.5 14.5 8 8 14.5 1.5 8Z" />,
  // ● low — calm circle
  green: <circle cx="8" cy="8" r="5.5" />,
}

/** AI risk flag (red / yellow / green): filled badge + shape + text label. */
export function RiskBadge({ flag }: { flag: RiskFlag | null }) {
  const { t } = useTranslation()
  if (!flag) return null
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-display text-xs font-bold tracking-[-0.005em] whitespace-nowrap', RISK_STYLE[flag].badge)}>
      <svg viewBox="0 0 16 16" className="size-2.5 shrink-0" fill="currentColor" aria-hidden role="presentation">
        {FLAG_SHAPE[flag]}
      </svg>
      {t(`risk.${flag}`)}
    </span>
  )
}

/** Shown on slides a pathologist re-prioritised by hand. */
export function ManualPriorityBadge() {
  const { t } = useTranslation()
  return (
    <span
      title={t('priority.manualHint')}
      className="inline-flex items-center gap-1 rounded-md border border-[#c2b8e0] bg-[#ece7f7] px-1.5 py-0.5 text-[11px] font-semibold text-[#4a3f7d] dark:border-[#4a4370] dark:bg-[#2b2740] dark:text-[#c3b8e6]"
    >
      <svg viewBox="0 0 16 16" className="size-3" fill="currentColor" aria-hidden>
        <path d="M11.3 1.3a1 1 0 0 1 1.4 0l2 2a1 1 0 0 1 0 1.4l-8 8L3 13.5l.8-3.7 7.5-8.5Z" />
      </svg>
      {t('priority.manual')}
    </span>
  )
}

/** AI slide score as a 0–100 bar. */
export function ScoreBar({ score, flag }: { score: number | null; flag: RiskFlag | null }) {
  const { t } = useTranslation()
  const points = scorePoints(score)
  return (
    <div className="flex items-center gap-2" title={t('risk.scoreHint')}>
      <div className="h-2 w-20 overflow-hidden rounded-full bg-canvas ring-1 ring-line-soft" aria-hidden>
        {points != null && flag && (
          <div className={cn('h-full rounded-full', RISK_STYLE[flag].bar)} style={{ width: `${Math.max(3, points)}%` }} />
        )}
      </div>
      <span className="tnum w-8 text-right text-sm text-ink-dim">{points ?? '—'}</span>
    </div>
  )
}

/**
 * Pipeline / case states. Paired light/dark values (single tokens fail
 * contrast in one theme). Failed uses error magenta, never risk red.
 */
const STATE_STYLE: Record<SlideState, string> = {
  new: 'text-ink-faint',
  image_processing: 'text-[#3d5f86] dark:text-[#8fa9c6]',
  ai_running: 'text-[#3d5f86] dark:text-[#8fa9c6]',
  scored: 'text-[#3d5f86] dark:text-[#8fa9c6]',
  queued: 'text-ink-dim',
  under_review: 'text-[#5d4f9e] dark:text-[#b3a6d6]',
  archived: 'text-[#0b6b5e] dark:text-[#7fe3d0]',
  failed: 'text-[#8e2a5b] dark:text-[#f0a6c8]',
}

const WORKING: SlideState[] = ['new', 'image_processing', 'ai_running', 'scored']

export function StateLabel({ state }: { state: SlideState }) {
  const { t } = useTranslation()
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', STATE_STYLE[state])}>
      {WORKING.includes(state) && <Spinner />}
      {t(`state.${state}`)}
    </span>
  )
}

/**
 * Clinical indication. Urgent is a human request, not an AI score, so it gets
 * its own language: unfilled dashed outline + bolt icon, never a risk colour.
 */
export function IndicationBadge({ indication }: { indication: Indication }) {
  const { t } = useTranslation()
  return indication === 'Urgent' ? (
    <span className="inline-flex items-center gap-1 rounded-md border border-dashed border-line bg-transparent px-1.5 py-0.5 text-[11px] font-bold text-ink-dim">
      <svg viewBox="0 0 16 16" className="size-3 shrink-0" fill="currentColor" aria-hidden>
        <path d="M9.5 1 3 9h4l-1 6 6.5-8.5H8.7L9.5 1Z" />
      </svg>
      {t('indication.Urgent')}
    </span>
  ) : (
    <span className="text-xs text-ink-faint">{t('indication.Routine')}</span>
  )
}
