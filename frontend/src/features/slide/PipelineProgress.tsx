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
    // Failed analysis is an error (magenta), never a risk colour.
    return (
      <section className="rounded-xl border border-[#dfa3be] bg-[#f9e3ec] p-3 text-sm dark:border-[#6b3450] dark:bg-[#38222e]">
        <h2 className="font-display font-bold text-[#8e2a5b] dark:text-[#f0a6c8]">{t('pipeline.failed')}</h2>
        {slide.error && <p className="tnum mt-1 break-words text-[#a34a76] dark:text-[#d894b8]">{slide.error}</p>}
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
              {i < current ? <span className="text-[#0b6b5e] dark:text-[#7fe3d0]">✓</span> : i === current ? <Spinner className="text-mist" /> : <span className="size-1.5 rounded-full bg-current" />}
            </span>
            {t(`common:state.${step}`)}
          </li>
        ))}
      </ol>
    </section>
  )
}
