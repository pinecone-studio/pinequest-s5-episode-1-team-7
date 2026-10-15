import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Slide } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { useFormat } from '../../shared/lib/useFormat.ts'
import { RISK_STYLE } from '../triage/risk.ts'
import { IndicationBadge, ManualPriorityBadge, RiskBadge, ScoreBar, StateLabel } from '../triage/TriageBadges.tsx'

/** One worklist row: a link to the slide. Columns collapse into two lines on narrow screens. */
export function SlideRow({ s, now }: { s: Slide; now: number }) {
  const { t } = useTranslation()
  const f = useFormat()
  return (
    <Link
      to={`/slides/${s.id}`}
      className={cn(
        'group grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 border-b border-l-[3px] border-b-line-soft px-4 py-3 transition duration-150 hover:bg-raised/70 focus-visible:bg-raised/70 focus-visible:outline-none md:grid-cols-[116px_minmax(0,1fr)_90px_120px_150px] md:items-center',
        // Colour budget: the left edge is a scrolling cue for red/yellow rows only.
        // Green rows stay quiet (no edge) so red slides stand out at a glance.
        s.risk_flag === 'red' || s.risk_flag === 'yellow' ? RISK_STYLE[s.risk_flag].ring : 'border-l-transparent',
      )}
    >
      <span className="order-2 flex flex-wrap items-center gap-1 md:order-none">
        <RiskBadge flag={s.risk_flag} />
      </span>
      <span className="order-1 min-w-0 md:order-none">
        <span className="block truncate font-display text-[14px] font-bold tracking-[-0.01em] text-ink">
          {t('slide.title', { id: s.id })}
        </span>
        <span className="tnum block truncate text-xs text-ink-faint">
          {t('slide.code', { code: s.local_hash.slice(0, 8) })} · {f.ago(s.created_at, now)} ·{' '}
          {t(`organ.names.${s.organ ?? 'lymph_node'}`, { defaultValue: s.organ ?? 'lymph_node' })}
        </span>
      </span>
      <span className="order-3 md:order-none">
        <IndicationBadge indication={s.indication} />
      </span>
      <span className="order-4 md:order-none">
        <ScoreBar score={s.risk_score} flag={s.risk_flag} />
      </span>
      <span className="order-5 col-span-2 flex flex-wrap items-center gap-2 md:order-none md:col-span-1">
        {s.state === 'archived' && s.decision ? (
          <span className="text-xs font-medium text-[#0b6b5e] dark:text-[#7fe3d0]">{t(`decision.${s.decision}`)}</span>
        ) : (
          <StateLabel state={s.state} />
        )}
        {s.priority_override != null && s.state === 'queued' && <ManualPriorityBadge />}
      </span>
    </Link>
  )
}
