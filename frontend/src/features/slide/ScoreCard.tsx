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
    <section className={cn('rounded-xl border border-line-soft border-l-[3px] bg-canvas p-4', slide.risk_flag ? RISK_STYLE[slide.risk_flag].ring : 'border-l-ink-faint')}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-display text-xs font-bold tracking-[0.06em] text-ink-faint uppercase">{t('score.title')}</h2>
        <RiskBadge flag={slide.risk_flag} />
      </div>
      <p className="tnum mt-1 text-[38px] leading-none font-semibold text-ink">
        {scorePoints(slide.risk_score)}
        <span className="text-base font-normal text-ink-faint">/100</span>
      </p>
      {slide.priority_override != null && (
        <p className="mt-1 text-xs text-[#5d4f9e] dark:text-[#b3a6d6]">
          {t('score.manualPriority', { level: t(`common:priority.level.${priorityLevel(slide.priority_override)}`) })}
        </p>
      )}
      <dl className="mt-3 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
        {slide.num_patches != null && (
          <div className="contents">
            <dt className="text-ink-faint">{t('score.patches')}</dt>
            <dd className="tnum text-right">{f.num(slide.num_patches)}</dd>
          </div>
        )}
        {slide.inference_ms != null && (
          <div className="contents">
            <dt className="text-ink-faint">{t('score.inference')}</dt>
            <dd className="tnum text-right">{f.seconds(slide.inference_ms, 2)}</dd>
          </div>
        )}
      </dl>
      <p className="mt-3 text-xs leading-relaxed text-ink-faint">{t('score.aidOnly')}</p>
      {slide.model_name != null && (
        <p className="tnum mt-1 text-xs text-ink-faint" title={slide.model_sha256 ?? undefined}>
          {slide.model_name === 'stub'
            ? t('score.demoStub')
            : t('score.model', { name: slide.model_name, hash: slide.model_sha256?.slice(0, 12) ?? '?' })}
        </p>
      )}
    </section>
  )
}
