import { useTranslation } from 'react-i18next'

import type { Slide } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { useFormat } from '../../shared/lib/useFormat.ts'
import { priorityLevel, RISK_STYLE, scorePoints } from '../triage/risk.ts'
import { RiskBadge } from '../triage/TriageBadges.tsx'

/** AI slide score S_slide (TDD 3.1 step 5) with how it was computed. */
export function ScoreCard({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  const f = useFormat()
  return (
    <section className={cn('rounded-lg border-l-4 bg-slate-50 p-4 dark:bg-slate-800/50', slide.risk_flag ? RISK_STYLE[slide.risk_flag].ring : 'border-l-slate-300')}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs font-medium tracking-wide text-slate-500 uppercase">{t('score.title')}</h2>
        <RiskBadge flag={slide.risk_flag} />
      </div>
      <p className="mt-1 text-4xl font-semibold tabular-nums">
        {scorePoints(slide.risk_score)}
        <span className="text-base font-normal text-slate-400">/100</span>
      </p>
      {slide.priority_override != null && (
        <p className="mt-1 text-xs text-violet-700 dark:text-violet-300">
          {t('score.manualPriority', { level: t(`common:priority.level.${priorityLevel(slide.priority_override)}`) })}
        </p>
      )}
      <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
        {slide.num_patches != null && (
          <div className="contents">
            <dt className="text-slate-500">{t('score.patches')}</dt>
            <dd className="text-right tabular-nums">{f.num(slide.num_patches)}</dd>
          </div>
        )}
        {slide.inference_ms != null && (
          <div className="contents">
            <dt className="text-slate-500">{t('score.inference')}</dt>
            <dd className="text-right tabular-nums">{f.seconds(slide.inference_ms, 2)}</dd>
          </div>
        )}
      </dl>
      <p className="mt-3 text-xs text-slate-500">{t('score.aidOnly')}</p>
      {slide.model_name != null && (
        <p className="mt-1 text-xs text-slate-500" title={slide.model_sha256 ?? undefined}>
          {slide.model_name === 'stub'
            ? t('score.demoStub')
            : t('score.model', { name: slide.model_name, hash: slide.model_sha256?.slice(0, 12) ?? '?' })}
        </p>
      )}
    </section>
  )
}
