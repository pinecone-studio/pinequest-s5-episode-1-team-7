import { useTranslation } from 'react-i18next'

import type { Slide, SlideState } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { Spinner } from '../../shared/ui/Spinner.tsx'

/** TDD 3.2: new -> image processing -> AI running -> risk score calculated -> priority queue. */
const STEPS: SlideState[] = ['new', 'image_processing', 'ai_running', 'scored', 'queued']

/** Where an unscored slide is in the pipeline, or why it failed. */
export function PipelineProgress({ slide }: { slide: Slide }) {
  const { t } = useTranslation(['slide', 'common'])
  if (slide.state === 'failed') {
    return (
      <section className="rounded-xl border border-[#dfb9b9] bg-[#f7e8e8] p-3 text-sm dark:border-[#5a3436] dark:bg-[#2a1e20]">
        <h2 className="font-display font-bold text-[#7a3535] dark:text-[#eec3c3]">{t('pipeline.failed')}</h2>
        {slide.error && <p className="tnum mt-1 break-words text-[#965151] dark:text-[#d8a3a3]">{slide.error}</p>}
      </section>
    )
  }
  const current = STEPS.indexOf(slide.state)
  return (
    <section aria-labelledby="pipeline-title">
      <h2 id="pipeline-title" className="mb-2 font-display text-sm font-bold">
        {t('pipeline.title')}
      </h2>
      <ol className="space-y-1.5">
        {STEPS.map((step, i) => (
          <li
            key={step}
            aria-current={i === current ? 'step' : undefined}
            className={cn('flex items-center gap-2 text-sm', i > current ? 'text-ink-faint' : i === current ? 'font-medium text-ink' : 'text-ink-dim')}
          >
            <span className="flex size-4 items-center justify-center">
              {i < current ? <span className="text-routine">✓</span> : i === current ? <Spinner className="text-mist" /> : <span className="size-1.5 rounded-full bg-current" />}
            </span>
            {t(`common:state.${step}`)}
          </li>
        ))}
      </ol>
    </section>
  )
}
