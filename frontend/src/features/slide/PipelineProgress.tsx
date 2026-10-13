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
      <section className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-900/60 dark:bg-red-950/30">
        <h2 className="font-semibold text-red-800 dark:text-red-200">{t('pipeline.failed')}</h2>
        {slide.error && <p className="mt-1 break-words text-red-700 dark:text-red-300">{slide.error}</p>}
      </section>
    )
  }
  const current = STEPS.indexOf(slide.state)
  return (
    <section aria-labelledby="pipeline-title">
      <h2 id="pipeline-title" className="mb-2 text-sm font-semibold">
        {t('pipeline.title')}
      </h2>
      <ol className="space-y-1.5">
        {STEPS.map((step, i) => (
          <li
            key={step}
            aria-current={i === current ? 'step' : undefined}
            className={cn('flex items-center gap-2 text-sm', i > current ? 'text-slate-400' : i === current ? 'font-medium' : 'text-slate-600 dark:text-slate-300')}
          >
            <span className="flex size-4 items-center justify-center">
              {i < current ? <span className="text-emerald-600">✓</span> : i === current ? <Spinner className="text-sky-600" /> : <span className="size-1.5 rounded-full bg-current" />}
            </span>
            {t(`common:state.${step}`)}
          </li>
        ))}
      </ol>
    </section>
  )
}
